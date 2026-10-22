import logging
import os

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
ADMIN_USER_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_USER_IDS", "").split(",")
    if x.strip().isdigit()
}

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("tg-channel-manager")


def is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id in ADMIN_USER_IDS)


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📤 Create Post", callback_data="create"),
            InlineKeyboardButton("🛠 Manage Post", callback_data="manage"),
        ],
        [
            InlineKeyboardButton("📌 Pin / Unpin", callback_data="pin_menu"),
            InlineKeyboardButton("ℹ️ Channel Info", callback_data="channel_info"),
        ],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])


def cancel_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ])


async def deny(update: Update) -> None:
    if update.callback_query:
        await update.callback_query.answer("Unauthorized.", show_alert=True)
    elif update.effective_message:
        await update.effective_message.reply_text("Unauthorized.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    context.user_data.clear()
    await update.effective_message.reply_text(
        "🎬 <b>CHANNEL MANAGER</b>\n\nChoose what you want to do.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    await update.effective_message.reply_text(
        "<b>Channel Manager</b>\n\n"
        "Use /start for the control panel.\n\n"
        "<b>Commands</b>\n"
        "/post &lt;text&gt; — publish text\n"
        "/edit &lt;message_id&gt; &lt;text&gt; — edit a bot-authored text post\n"
        "/delete &lt;message_id&gt; — delete a channel post the bot may delete\n"
        "/pin &lt;message_id&gt; — pin a post\n"
        "/unpin &lt;message_id&gt; — unpin a post\n"
        "/id — show your Telegram user ID\n\n"
        "The control panel also supports text, photos, videos and documents.",
        parse_mode="HTML",
    )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user and update.effective_message:
        await update.effective_message.reply_text(f"Your Telegram user ID: {user.id}")


async def post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    text = " ".join(context.args).strip()
    if not text:
        return await update.effective_message.reply_text("Usage: /post <text>")
    message = await context.bot.send_message(chat_id=CHANNEL_ID, text=text)
    await update.effective_message.reply_text(
        f"✅ Posted. Message ID: <code>{message.message_id}</code>",
        parse_mode="HTML",
    )


async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    if len(context.args) < 2 or not context.args[0].isdigit():
        return await update.effective_message.reply_text(
            "Usage: /edit <message_id> <new text>"
        )
    message_id = int(context.args[0])
    text = " ".join(context.args[1:]).strip()
    try:
        await context.bot.edit_message_text(
            chat_id=CHANNEL_ID, message_id=message_id, text=text
        )
        await update.effective_message.reply_text("✅ Post updated.")
    except BadRequest as exc:
        await update.effective_message.reply_text(f"Could not edit that post: {exc}")


async def delete_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    if not context.args or not context.args[0].isdigit():
        return await update.effective_message.reply_text("Usage: /delete <message_id>")
    try:
        await context.bot.delete_message(
            chat_id=CHANNEL_ID, message_id=int(context.args[0])
        )
        await update.effective_message.reply_text("🗑 Post deleted.")
    except (BadRequest, Forbidden) as exc:
        await update.effective_message.reply_text(f"Could not delete that post: {exc}")


async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    if not context.args or not context.args[0].isdigit():
        return await update.effective_message.reply_text("Usage: /pin <message_id>")
    try:
        await context.bot.pin_chat_message(
            chat_id=CHANNEL_ID,
            message_id=int(context.args[0]),
            disable_notification=True,
        )
        await update.effective_message.reply_text("📌 Post pinned.")
    except (BadRequest, Forbidden) as exc:
        await update.effective_message.reply_text(f"Could not pin that post: {exc}")


async def unpin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    if not context.args or not context.args[0].isdigit():
        return await update.effective_message.reply_text("Usage: /unpin <message_id>")
    try:
        await context.bot.unpin_chat_message(
            chat_id=CHANNEL_ID, message_id=int(context.args[0])
        )
        await update.effective_message.reply_text("📍 Post unpinned.")
    except (BadRequest, Forbidden) as exc:
        await update.effective_message.reply_text(f"Could not unpin that post: {exc}")


async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "cancel":
        context.user_data.clear()
        return await query.edit_message_text(
            "🎬 <b>CHANNEL MANAGER</b>\n\nChoose what you want to do.",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )

    if action == "create":
        context.user_data["mode"] = "create"
        return await query.edit_message_text(
            "📤 <b>Create Post</b>\n\n"
            "Send me the content you want published.\n\n"
            "Supported: 📝 text, 🖼 photo, 🎥 video, 📁 document.\n"
            "For media, add the caption before sending it.",
            parse_mode="HTML",
            reply_markup=cancel_menu(),
        )

    if action == "manage":
        context.user_data["mode"] = "manage_id"
        return await query.edit_message_text(
            "🛠 <b>Manage Post</b>\n\nSend the channel message ID you want to manage.",
            parse_mode="HTML",
            reply_markup=cancel_menu(),
        )

    if action == "pin_menu":
        context.user_data["mode"] = "pin_id"
        return await query.edit_message_text(
            "📌 <b>Pin / Unpin</b>\n\nSend the channel message ID.",
            parse_mode="HTML",
            reply_markup=cancel_menu(),
        )

    if action == "channel_info":
        try:
            chat = await context.bot.get_chat(CHANNEL_ID)
            count = await context.bot.get_chat_member_count(CHANNEL_ID)
            return await query.edit_message_text(
                f"ℹ️ <b>{chat.title or 'Channel'}</b>\n\n"
                f"ID: <code>{chat.id}</code>\n"
                f"Members/Subscribers: <b>{count}</b>\n"
                f"Type: {chat.type}",
                parse_mode="HTML",
                reply_markup=main_menu(),
            )
        except (BadRequest, Forbidden) as exc:
            return await query.edit_message_text(
                f"Could not read channel info: {exc}", reply_markup=main_menu()
            )

    if action == "help":
        return await query.edit_message_text(
            "❓ <b>How to use it</b>\n\n"
            "Create Post lets you send text/media to the channel.\n"
            "Manage Post lets you edit text/captions or delete a post.\n"
            "Pin / Unpin manages pinned messages.\n\n"
            "Tip: posts created through this bot are the easiest to manage later.",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )

    if action.startswith("publish:"):
        source_id = int(action.split(":", 1)[1])
        try:
            sent = await context.bot.copy_message(
                chat_id=CHANNEL_ID,
                from_chat_id=query.message.chat_id,
                message_id=source_id,
            )
            context.user_data.clear()
            return await query.edit_message_text(
                f"✅ Published. Channel message ID: <code>{sent.message_id}</code>",
                parse_mode="HTML",
                reply_markup=main_menu(),
            )
        except (BadRequest, Forbidden) as exc:
            return await query.edit_message_text(
                f"Could not publish: {exc}", reply_markup=main_menu()
            )

    if action == "discard":
        context.user_data.clear()
        return await query.edit_message_text("Draft discarded.", reply_markup=main_menu())

    if action.startswith("manage_edit:"):
        message_id = int(action.split(":", 1)[1])
        context.user_data["mode"] = "edit_content"
        context.user_data["target_message_id"] = message_id
        return await query.edit_message_text(
            "✏️ Send the replacement text or new caption.",
            reply_markup=cancel_menu(),
        )

    if action.startswith("manage_delete:"):
        message_id = int(action.split(":", 1)[1])
        context.user_data["target_message_id"] = message_id
        return await query.edit_message_text(
            f"Delete channel message <code>{message_id}</code>?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 Yes, delete", callback_data=f"confirm_delete:{message_id}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
            ]),
        )

    if action.startswith("confirm_delete:"):
        message_id = int(action.split(":", 1)[1])
        try:
            await context.bot.delete_message(CHANNEL_ID, message_id)
            context.user_data.clear()
            return await query.edit_message_text(
                "🗑 Post deleted.", reply_markup=main_menu()
            )
        except (BadRequest, Forbidden) as exc:
            return await query.edit_message_text(
                f"Could not delete that post: {exc}", reply_markup=main_menu()
            )

    if action.startswith("do_pin:") or action.startswith("do_unpin:"):
        message_id = int(action.split(":", 1)[1])
        try:
            if action.startswith("do_pin:"):
                await context.bot.pin_chat_message(
                    CHANNEL_ID, message_id, disable_notification=True
                )
                result = "📌 Post pinned."
            else:
                await context.bot.unpin_chat_message(CHANNEL_ID, message_id)
                result = "📍 Post unpinned."
            context.user_data.clear()
            return await query.edit_message_text(result, reply_markup=main_menu())
        except (BadRequest, Forbidden) as exc:
            return await query.edit_message_text(
                f"Could not update pin: {exc}", reply_markup=main_menu()
            )


async def admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    message = update.effective_message
    mode = context.user_data.get("mode")

    if mode == "create":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Publish", callback_data=f"publish:{message.message_id}")],
            [InlineKeyboardButton("❌ Discard", callback_data="discard")],
        ])
        return await message.reply_text(
            "👀 Preview received. Publish this to the channel?",
            reply_markup=keyboard,
        )

    if mode == "manage_id":
        if not message.text or not message.text.strip().isdigit():
            return await message.reply_text("Send a numeric message ID.")
        mid = int(message.text.strip())
        context.user_data["target_message_id"] = mid
        return await message.reply_text(
            f"Managing channel message <code>{mid}</code>.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Edit text/caption", callback_data=f"manage_edit:{mid}")],
                [InlineKeyboardButton("🗑 Delete", callback_data=f"manage_delete:{mid}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
            ]),
        )

    if mode == "edit_content":
        mid = context.user_data.get("target_message_id")
        new_text = (message.text or message.caption or "").strip()
        if not new_text:
            return await message.reply_text("Send text for the new message/caption.")
        try:
            try:
                await context.bot.edit_message_text(CHANNEL_ID, mid, text=new_text)
            except BadRequest:
                await context.bot.edit_message_caption(CHANNEL_ID, mid, caption=new_text)
            context.user_data.clear()
            return await message.reply_text("✅ Post updated.", reply_markup=main_menu())
        except (BadRequest, Forbidden) as exc:
            return await message.reply_text(
                f"Could not edit that post: {exc}", reply_markup=main_menu()
            )

    if mode == "pin_id":
        if not message.text or not message.text.strip().isdigit():
            return await message.reply_text("Send a numeric message ID.")
        mid = int(message.text.strip())
        return await message.reply_text(
            f"What should I do with message <code>{mid}</code>?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📌 Pin", callback_data=f"do_pin:{mid}"),
                    InlineKeyboardButton("📍 Unpin", callback_data=f"do_unpin:{mid}"),
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
            ]),
        )

    await message.reply_text("Use /start to open the channel control panel.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled update error", exc_info=context.error)


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")
    if not CHANNEL_ID:
        raise RuntimeError("TELEGRAM_CHANNEL_ID is missing.")
    if not ADMIN_USER_IDS:
        raise RuntimeError("ADMIN_USER_IDS is missing.")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("post", post))
    app.add_handler(CommandHandler("edit", edit))
    app.add_handler(CommandHandler("delete", delete_post))
    app.add_handler(CommandHandler("pin", pin))
    app.add_handler(CommandHandler("unpin", unpin))
    app.add_handler(CallbackQueryHandler(panel_callback))
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL)
            & ~filters.COMMAND,
            admin_message,
        )
    )
    app.add_error_handler(error_handler)

    logger.info("TG-CHANNEL-MANAGER started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
