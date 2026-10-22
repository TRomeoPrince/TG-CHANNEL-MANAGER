import logging
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import (
    Application, CallbackQueryHandler, ChatMemberHandler, CommandHandler,
    ContextTypes,
)

from database import Database
from services import edit_post, parse_local_datetime

logger = logging.getLogger("tg-channel-manager.child")


class ChildBotRuntime:
    def __init__(self, token: str, bot_id: int, owner_user_id: int, db: Database, timezone):
        self.bot_id = bot_id
        self.owner_user_id = owner_user_id
        self.db = db
        self.timezone = timezone
        self.app = Application.builder().token(token).build()
        self._configure()

    def _configure(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help))
        self.app.add_handler(CommandHandler("chats", self.chats))
        self.app.add_handler(CommandHandler("post", self.post))
        self.app.add_handler(CommandHandler("schedule", self.schedule))
        self.app.add_handler(CommandHandler("edit", self.edit))
        self.app.add_handler(CommandHandler("delete", self.delete))
        self.app.add_handler(CommandHandler("pin", self.pin))
        self.app.add_handler(CommandHandler("unpin", self.unpin))
        self.app.add_handler(CallbackQueryHandler(self.callback))
        self.app.add_handler(
            ChatMemberHandler(self.my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER)
        )
        self.app.add_error_handler(self.error)
        if self.app.job_queue:
            self.app.job_queue.run_repeating(self.publish_due, interval=20, first=5)

    def is_owner(self, update: Update) -> bool:
        return bool(
            update.effective_user
            and update.effective_user.id == self.owner_user_id
        )

    async def deny(self, update: Update):
        if update.callback_query:
            await update.callback_query.answer("Only this bot's owner can use this control.", show_alert=True)
        elif update.effective_message:
            await update.effective_message.reply_text("Only this bot's owner can use this control.")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            return await self.deny(update)
        await update.effective_message.reply_text(
            "🤖 <b>Your Channel & Group Manager</b>\n\n"
            "Add this bot to any group/channel you own. For channels, make it an "
            "administrator with the permissions you want it to use.\n\n"
            "Then use the controls below.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📺 My Chats", callback_data="chats"),
                    InlineKeyboardButton("❓ Help", callback_data="help"),
                ]
            ]),
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            return await self.deny(update)
        await update.effective_message.reply_text(
            "<b>Commands</b>\n"
            "/chats — list groups/channels where this bot is active\n"
            "/post &lt;chat_id&gt; &lt;text&gt;\n"
            "/schedule &lt;chat_id&gt; &lt;YYYY-MM-DD HH:MM&gt; | &lt;text&gt;\n"
            "/edit &lt;chat_id&gt; &lt;message_id&gt; &lt;text&gt;\n"
            "/delete &lt;chat_id&gt; &lt;message_id&gt;\n"
            "/pin &lt;chat_id&gt; &lt;message_id&gt;\n"
            "/unpin &lt;chat_id&gt; &lt;message_id&gt;",
            parse_mode="HTML",
        )

    async def chats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            return await self.deny(update)
        rows = self.db.chats(self.bot_id)
        if not rows:
            return await update.effective_message.reply_text(
                "No chats detected yet. Add this bot to a group or channel first."
            )
        lines = ["<b>Managed chats</b>"]
        for row in rows:
            title = row["title"] or row["username"] or str(row["chat_id"])
            lines.append(
                f"• {title} — <code>{row['chat_id']}</code> ({row['chat_type']})"
            )
        await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")

    def _allowed_chat(self, chat_id: int) -> bool:
        return any(row["chat_id"] == chat_id for row in self.db.chats(self.bot_id))

    async def post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            return await self.deny(update)
        if len(context.args) < 2:
            return await update.effective_message.reply_text(
                "Usage: /post <chat_id> <text>"
            )
        try:
            chat_id = int(context.args[0])
        except ValueError:
            return await update.effective_message.reply_text("chat_id must be numeric.")
        if not self._allowed_chat(chat_id):
            return await update.effective_message.reply_text(
                "That chat is not registered to this bot."
            )
        text = " ".join(context.args[1:]).strip()
        try:
            sent = await context.bot.send_message(chat_id, text)
            self.db.save_post(
                self.bot_id, chat_id, text, "published",
                telegram_message_id=sent.message_id,
            )
            await update.effective_message.reply_text(
                f"✅ Published as message {sent.message_id}."
            )
        except (BadRequest, Forbidden) as exc:
            await update.effective_message.reply_text(f"Telegram refused the post: {exc}")

    async def schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            return await self.deny(update)
        raw = " ".join(context.args)
        if "|" not in raw:
            return await update.effective_message.reply_text(
                "Usage: /schedule <chat_id> <YYYY-MM-DD HH:MM> | <text>"
            )
        left, text = [x.strip() for x in raw.split("|", 1)]
        parts = left.split(maxsplit=1)
        if len(parts) != 2:
            return await update.effective_message.reply_text(
                "Usage: /schedule <chat_id> <YYYY-MM-DD HH:MM> | <text>"
            )
        try:
            chat_id = int(parts[0])
            when = parse_local_datetime(parts[1], self.timezone)
        except (ValueError, TypeError) as exc:
            return await update.effective_message.reply_text(str(exc))
        if not self._allowed_chat(chat_id):
            return await update.effective_message.reply_text(
                "That chat is not registered to this bot."
            )
        if when <= datetime.now(timezone.utc):
            return await update.effective_message.reply_text("Schedule time must be in the future.")
        post_id = self.db.save_post(
            self.bot_id, chat_id, text, "scheduled",
            scheduled_for=when.isoformat(),
        )
        await update.effective_message.reply_text(f"⏰ Scheduled as post #{post_id}.")

    async def _message_action(self, update, context, action):
        if not self.is_owner(update):
            return await self.deny(update)
        minimum = 3 if action == "edit" else 2
        if len(context.args) < minimum:
            return await update.effective_message.reply_text(
                f"Usage: /{action} <chat_id> <message_id>"
                + (" <text>" if action == "edit" else "")
            )
        try:
            chat_id = int(context.args[0])
            message_id = int(context.args[1])
        except ValueError:
            return await update.effective_message.reply_text(
                "chat_id and message_id must be numeric."
            )
        if not self._allowed_chat(chat_id):
            return await update.effective_message.reply_text(
                "That chat is not registered to this bot."
            )
        try:
            if action == "edit":
                await edit_post(context.bot, chat_id, message_id, " ".join(context.args[2:]))
            elif action == "delete":
                await context.bot.delete_message(chat_id, message_id)
            elif action == "pin":
                await context.bot.pin_chat_message(
                    chat_id, message_id, disable_notification=True
                )
            else:
                await context.bot.unpin_chat_message(chat_id, message_id)
            await update.effective_message.reply_text("✅ Done.")
        except (BadRequest, Forbidden) as exc:
            await update.effective_message.reply_text(f"Telegram refused that action: {exc}")

    async def edit(self, u, c): return await self._message_action(u, c, "edit")
    async def delete(self, u, c): return await self._message_action(u, c, "delete")
    async def pin(self, u, c): return await self._message_action(u, c, "pin")
    async def unpin(self, u, c): return await self._message_action(u, c, "unpin")

    async def callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            return await self.deny(update)
        q = update.callback_query
        await q.answer()
        if q.data == "chats":
            rows = self.db.chats(self.bot_id)
            text = ["📺 <b>Managed chats</b>"]
            for row in rows:
                text.append(
                    f"• {row['title'] or row['username'] or row['chat_id']} — "
                    f"<code>{row['chat_id']}</code>"
                )
            if len(text) == 1:
                text.append("No chats detected yet.")
            return await q.edit_message_text("\n".join(text), parse_mode="HTML")
        if q.data == "help":
            return await q.edit_message_text(
                "Use /chats, /post, /schedule, /edit, /delete, /pin and /unpin."
            )

    async def my_chat_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        change = update.my_chat_member
        if not change:
            return
        status = change.new_chat_member.status
        self.db.upsert_chat(self.bot_id, change.chat, status)
        logger.info(
            "Managed bot %s chat %s status -> %s",
            self.bot_id, change.chat.id, status
        )

    async def publish_due(self, context: ContextTypes.DEFAULT_TYPE):
        now = datetime.now(timezone.utc).isoformat()
        for row in self.db.due_posts(self.bot_id, now):
            try:
                sent = await context.bot.send_message(row["chat_id"], row["text"])
                self.db.mark_post_published(row["id"], sent.message_id)
            except Exception:
                logger.exception("Scheduled post %s failed", row["id"])

    async def error(self, update, context):
        logger.exception("Child bot error %s", self.bot_id, exc_info=context.error)

    async def start_runtime(self):
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Started managed bot runtime %s", self.bot_id)

    async def stop_runtime(self):
        if self.app.updater and self.app.updater.running:
            await self.app.updater.stop()
        if self.app.running:
            await self.app.stop()
        await self.app.shutdown()
        logger.info("Stopped managed bot runtime %s", self.bot_id)
