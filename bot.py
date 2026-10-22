import logging
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes,
    MessageHandler, filters,
)

from config import Settings
from database import Database, utcnow
from keyboards import cancel_menu, channel_picker, main_menu
from services import content_kind, copy_to_channel, display_time, edit_post, parse_local_datetime

settings = Settings.from_env()
db = Database(settings.database_path)
if settings.default_channel:
    db.add_channel(settings.default_channel, alias="Default")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("tg-channel-manager")


def is_admin(update):
    return bool(update.effective_user and update.effective_user.id in settings.admin_user_ids)


async def deny(update):
    if update.callback_query:
        await update.callback_query.answer("Unauthorized.", show_alert=True)
    elif update.effective_message:
        await update.effective_message.reply_text("Unauthorized.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)
    context.user_data.clear()
    await update.effective_message.reply_text(
        "👑 <b>TG CHANNEL MANAGER</b>\n\nFull control panel",
        parse_mode="HTML", reply_markup=main_menu()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)
    await update.effective_message.reply_text(
        "<b>Commands</b>\n"
        "/start — control panel\n"
        "/id — your Telegram ID\n"
        "/addchannel &lt;@username|-100id&gt; [alias] — add a channel\n"
        "/removechannel &lt;@username|-100id&gt; — disable a channel\n"
        "/channels — list channels\n"
        "/post &lt;text&gt; — quick-post text to the first channel\n"
        "/edit &lt;channel&gt; &lt;message_id&gt; &lt;text&gt;\n"
        "/delete &lt;channel&gt; &lt;message_id&gt;\n"
        "/pin &lt;channel&gt; &lt;message_id&gt;\n"
        "/unpin &lt;channel&gt; &lt;message_id&gt;",
        parse_mode="HTML",
    )


async def id_command(update, context):
    if update.effective_user:
        await update.effective_message.reply_text(
            f"Your Telegram user ID: {update.effective_user.id}"
        )


async def add_channel(update, context):
    if not is_admin(update):
        return await deny(update)
    if not context.args:
        return await update.effective_message.reply_text(
            "Usage: /addchannel <@username|-100id> [alias]"
        )
    chat_id = context.args[0]
    alias = " ".join(context.args[1:]).strip()
    try:
        chat = await context.bot.get_chat(chat_id)
        me = await context.bot.get_me()
        member = await context.bot.get_chat_member(chat.id, me.id)
        if member.status not in ("administrator", "creator"):
            return await update.effective_message.reply_text(
                "Add this bot as a channel administrator first."
            )
        db.add_channel(str(chat.id), chat.title or "", alias)
        await update.effective_message.reply_text(
            f"✅ Added {chat.title or chat.id}."
        )
    except (BadRequest, Forbidden) as exc:
        await update.effective_message.reply_text(f"Could not add channel: {exc}")


async def remove_channel(update, context):
    if not is_admin(update):
        return await deny(update)
    if not context.args:
        return await update.effective_message.reply_text(
            "Usage: /removechannel <channel id>"
        )
    db.remove_channel(context.args[0])
    await update.effective_message.reply_text("Channel disabled.")


async def list_channels(update, context):
    if not is_admin(update):
        return await deny(update)
    rows = db.channels()
    if not rows:
        return await update.effective_message.reply_text("No channels configured.")
    text = ["<b>Managed channels</b>"]
    for row in rows:
        text.append(
            f"• {row['alias'] or row['title'] or 'Channel'} — <code>{row['chat_id']}</code>"
        )
    await update.effective_message.reply_text("\n".join(text), parse_mode="HTML")


def first_channel():
    rows = db.channels()
    return rows[0] if rows else None


async def quick_post(update, context):
    if not is_admin(update):
        return await deny(update)
    channel = first_channel()
    if not channel:
        return await update.effective_message.reply_text("Add a channel first.")
    text = " ".join(context.args).strip()
    if not text:
        return await update.effective_message.reply_text("Usage: /post <text>")
    sent = await context.bot.send_message(channel["chat_id"], text)
    pid = db.save_post(
        channel_chat_id=channel["chat_id"], telegram_message_id=sent.message_id,
        kind="text", text=text, status="published",
        created_by=update.effective_user.id, created_at=utcnow(), published_at=utcnow()
    )
    await update.effective_message.reply_text(
        f"✅ Published. Record #{pid}, Telegram message {sent.message_id}."
    )


async def direct_action(update, context, action):
    if not is_admin(update):
        return await deny(update)
    minimum = 3 if action == "edit" else 2
    if len(context.args) < minimum or not context.args[1].isdigit():
        return await update.effective_message.reply_text(
            f"Usage: /{action} <channel> <message_id>"
            + (" <text>" if action == "edit" else "")
        )
    channel, mid = context.args[0], int(context.args[1])
    try:
        if action == "edit":
            await edit_post(context.bot, channel, mid, " ".join(context.args[2:]))
        elif action == "delete":
            await context.bot.delete_message(channel, mid)
        elif action == "pin":
            await context.bot.pin_chat_message(channel, mid, disable_notification=True)
        else:
            await context.bot.unpin_chat_message(channel, mid)
        await update.effective_message.reply_text("✅ Done.")
    except (BadRequest, Forbidden) as exc:
        await update.effective_message.reply_text(f"Telegram refused that action: {exc}")


async def edit_cmd(u,c): return await direct_action(u,c,"edit")
async def delete_cmd(u,c): return await direct_action(u,c,"delete")
async def pin_cmd(u,c): return await direct_action(u,c,"pin")
async def unpin_cmd(u,c): return await direct_action(u,c,"unpin")


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)
    q = update.callback_query
    await q.answer()
    action = q.data

    if action == "cancel":
        context.user_data.clear()
        return await q.edit_message_text(
            "👑 <b>TG CHANNEL MANAGER</b>\n\nFull control panel",
            parse_mode="HTML", reply_markup=main_menu()
        )

    if action == "create":
        channels = db.channels()
        if not channels:
            return await q.edit_message_text(
                "No channels yet. Use /addchannel first.", reply_markup=main_menu()
            )
        context.user_data.clear()
        return await q.edit_message_text(
            "📤 <b>Create Post</b>\nChoose destination:",
            parse_mode="HTML", reply_markup=channel_picker(channels, "create_channel")
        )

    if action.startswith("create_channel:"):
        channel_db_id = int(action.split(":")[1])
        channel = next((x for x in db.channels() if x["id"] == channel_db_id), None)
        if not channel:
            return await q.edit_message_text("Channel unavailable.", reply_markup=main_menu())
        context.user_data.update(mode="compose", channel_id=channel["chat_id"])
        return await q.edit_message_text(
            "Send the post now. Text, photo, video and documents are supported. "
            "Add captions before sending media.",
            reply_markup=cancel_menu()
        )

    if action.startswith("publish:"):
        source_id = int(action.split(":")[1])
        channel_id = context.user_data.get("channel_id")
        sent = await copy_to_channel(context.bot, channel_id, q.message.chat_id, source_id)
        source = context.user_data.get("draft", {})
        pid = db.save_post(
            channel_chat_id=channel_id, telegram_message_id=sent.message_id,
            kind=source.get("kind","unknown"), text=source.get("text"),
            source_chat_id=str(q.message.chat_id), source_message_id=source_id,
            status="published", created_by=q.from_user.id, created_at=utcnow(),
            published_at=utcnow()
        )
        context.user_data.clear()
        return await q.edit_message_text(
            f"✅ Published. Record #{pid}; message <code>{sent.message_id}</code>.",
            parse_mode="HTML", reply_markup=main_menu()
        )

    if action.startswith("schedule:"):
        context.user_data["mode"] = "schedule_time"
        context.user_data["source_message_id"] = int(action.split(":")[1])
        return await q.edit_message_text(
            "⏰ Send local time as <code>YYYY-MM-DD HH:MM</code>\n"
            f"Timezone: <b>{settings.timezone.key}</b>",
            parse_mode="HTML", reply_markup=cancel_menu()
        )

    if action == "posts":
        rows = db.recent_posts()
        lines = ["🗂 <b>Recent post history</b>"]
        for row in rows:
            lines.append(
                f"#{row['id']} • {row['status']} • {row['kind']} • "
                f"<code>{row['telegram_message_id'] or '-'}</code>"
            )
        if len(lines) == 1:
            lines.append("No recorded posts yet.")
        return await q.edit_message_text(
            "\n".join(lines), parse_mode="HTML", reply_markup=main_menu()
        )

    if action == "scheduled":
        rows = db.scheduled_posts()
        lines = ["⏰ <b>Scheduled posts</b>"]
        for row in rows:
            lines.append(
                f"#{row['id']} • {display_time(row['scheduled_for'], settings.timezone)}"
            )
        if len(lines) == 1:
            lines.append("Nothing scheduled.")
        return await q.edit_message_text(
            "\n".join(lines), parse_mode="HTML", reply_markup=main_menu()
        )

    if action == "channels":
        rows = db.channels()
        lines = ["📺 <b>Channels</b>"]
        for row in rows:
            lines.append(
                f"• {row['alias'] or row['title']} — <code>{row['chat_id']}</code>"
            )
        if len(lines) == 1:
            lines.append("Use /addchannel to connect one.")
        return await q.edit_message_text(
            "\n".join(lines), parse_mode="HTML", reply_markup=main_menu()
        )

    if action == "dashboard":
        channels = db.channels()
        recent = db.recent_posts(100)
        published = sum(1 for x in recent if x["status"] == "published")
        scheduled = sum(1 for x in recent if x["status"] == "scheduled")
        return await q.edit_message_text(
            "📊 <b>Dashboard</b>\n\n"
            f"Managed channels: <b>{len(channels)}</b>\n"
            f"Recent published records: <b>{published}</b>\n"
            f"Scheduled: <b>{scheduled}</b>",
            parse_mode="HTML", reply_markup=main_menu()
        )

    if action == "manage":
        context.user_data.clear()
        context.user_data["mode"] = "manage_channel"
        return await q.edit_message_text(
            "Send: <code>&lt;channel id/@username&gt; &lt;message id&gt;</code>",
            parse_mode="HTML", reply_markup=cancel_menu()
        )

    if action == "help":
        return await q.edit_message_text(
            "❓ <b>Full Manager</b>\n\n"
            "• Multiple channels\n• Text + media publishing\n"
            "• Preview/publish/schedule\n• Persistent post history\n"
            "• Edit/delete/pin/unpin by message ID\n• Dashboard\n\n"
            "Use /help for direct commands.",
            parse_mode="HTML", reply_markup=main_menu()
        )

    if action.startswith("manage_edit:"):
        _, channel, mid = action.split(":", 2)
        context.user_data.update(mode="manage_edit_text", channel_id=channel, message_id=int(mid))
        return await q.edit_message_text("Send replacement text/caption.", reply_markup=cancel_menu())

    if action.startswith("manage_delete:"):
        _, channel, mid = action.split(":", 2)
        try:
            await context.bot.delete_message(channel, int(mid))
            return await q.edit_message_text("🗑 Deleted.", reply_markup=main_menu())
        except (BadRequest, Forbidden) as exc:
            return await q.edit_message_text(f"Could not delete: {exc}", reply_markup=main_menu())

    if action.startswith("manage_pin:") or action.startswith("manage_unpin:"):
        parts = action.split(":")
        verb, channel, mid = parts[0], parts[1], int(parts[2])
        try:
            if verb == "manage_pin":
                await context.bot.pin_chat_message(channel, mid, disable_notification=True)
            else:
                await context.bot.unpin_chat_message(channel, mid)
            return await q.edit_message_text("✅ Done.", reply_markup=main_menu())
        except (BadRequest, Forbidden) as exc:
            return await q.edit_message_text(f"Could not update pin: {exc}", reply_markup=main_menu())


async def private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await deny(update)
    msg = update.effective_message
    mode = context.user_data.get("mode")

    if mode == "compose":
        context.user_data["draft"] = {
            "kind": content_kind(msg),
            "text": msg.text or msg.caption,
        }
        return await msg.reply_text(
            "👀 Draft received. What next?",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Publish now", callback_data=f"publish:{msg.message_id}"),
                    InlineKeyboardButton("⏰ Schedule", callback_data=f"schedule:{msg.message_id}"),
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
            ])
        )

    if mode == "schedule_time":
        try:
            when = parse_local_datetime(msg.text or "", settings.timezone)
        except ValueError as exc:
            return await msg.reply_text(str(exc))
        if when <= datetime.now(timezone.utc):
            return await msg.reply_text("Schedule time must be in the future.")
        draft = context.user_data.get("draft", {})
        pid = db.save_post(
            channel_chat_id=context.user_data["channel_id"],
            kind=draft.get("kind","unknown"), text=draft.get("text"),
            source_chat_id=str(msg.chat_id),
            source_message_id=context.user_data["source_message_id"],
            status="scheduled", scheduled_for=when.isoformat(),
            created_by=msg.from_user.id, created_at=utcnow()
        )
        context.user_data.clear()
        return await msg.reply_text(
            f"⏰ Scheduled as record #{pid}.", reply_markup=main_menu()
        )

    if mode == "manage_channel":
        parts = (msg.text or "").split()
        if len(parts) != 2 or not parts[1].isdigit():
            return await msg.reply_text("Use: <channel> <message_id>")
        channel, mid = parts[0], int(parts[1])
        return await msg.reply_text(
            f"Manage <code>{channel}</code> message <code>{mid}</code>:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Edit", callback_data=f"manage_edit:{channel}:{mid}")],
                [InlineKeyboardButton("🗑 Delete", callback_data=f"manage_delete:{channel}:{mid}")],
                [
                    InlineKeyboardButton("📌 Pin", callback_data=f"manage_pin:{channel}:{mid}"),
                    InlineKeyboardButton("📍 Unpin", callback_data=f"manage_unpin:{channel}:{mid}"),
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
            ])
        )

    if mode == "manage_edit_text":
        try:
            await edit_post(
                context.bot, context.user_data["channel_id"],
                context.user_data["message_id"], msg.text or msg.caption or ""
            )
            context.user_data.clear()
            return await msg.reply_text("✅ Updated.", reply_markup=main_menu())
        except (BadRequest, Forbidden) as exc:
            return await msg.reply_text(f"Could not edit: {exc}", reply_markup=main_menu())

    await msg.reply_text("Use /start to open the control panel.")


async def publish_due(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc).isoformat()
    for row in db.due_posts(now):
        try:
            sent = await copy_to_channel(
                context.bot, row["channel_chat_id"],
                row["source_chat_id"], row["source_message_id"]
            )
            db.mark_published(row["id"], sent.message_id)
        except Exception:
            logger.exception("Failed scheduled post #%s", row["id"])


async def error_handler(update, context):
    logger.exception("Unhandled update error", exc_info=context.error)


def main():
    app = Application.builder().token(settings.bot_token).build()
    for name, fn in [
        ("start", start), ("help", help_command), ("id", id_command),
        ("addchannel", add_channel), ("removechannel", remove_channel),
        ("channels", list_channels), ("post", quick_post),
        ("edit", edit_cmd), ("delete", delete_cmd), ("pin", pin_cmd),
        ("unpin", unpin_cmd),
    ]:
        app.add_handler(CommandHandler(name, fn))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE
        & (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL)
        & ~filters.COMMAND,
        private_message
    ))
    app.add_error_handler(error_handler)
    if app.job_queue is None:
        raise RuntimeError("JobQueue unavailable. Install python-telegram-bot[job-queue].")
    app.job_queue.run_repeating(publish_due, interval=20, first=5)
    logger.info("TG-CHANNEL-MANAGER full version started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
