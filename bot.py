import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

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


async def deny(update: Update) -> None:
    if update.effective_message:
        await update.effective_message.reply_text("Unauthorized.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    await update.effective_message.reply_text(
        "TG-CHANNEL-MANAGER is online. Use /help for commands."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    await update.effective_message.reply_text(
        "/post <text> - publish to channel\n"
        "/edit <message_id> <text> - edit a bot-authored channel post\n"
        "/pin <message_id> - pin a channel post\n"
        "/unpin <message_id> - unpin a channel post\n"
        "/projectindex - publish a starter project index\n"
        "/id - show your Telegram user ID"
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
    await update.effective_message.reply_text(f"Posted. Message ID: {message.message_id}")


async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    if len(context.args) < 2 or not context.args[0].isdigit():
        return await update.effective_message.reply_text(
            "Usage: /edit <message_id> <new text>"
        )
    message_id = int(context.args[0])
    text = " ".join(context.args[1:]).strip()
    await context.bot.edit_message_text(
        chat_id=CHANNEL_ID, message_id=message_id, text=text
    )
    await update.effective_message.reply_text("Post updated.")


async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    if not context.args or not context.args[0].isdigit():
        return await update.effective_message.reply_text("Usage: /pin <message_id>")
    await context.bot.pin_chat_message(
        chat_id=CHANNEL_ID,
        message_id=int(context.args[0]),
        disable_notification=True,
    )
    await update.effective_message.reply_text("Post pinned.")


async def unpin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    if not context.args or not context.args[0].isdigit():
        return await update.effective_message.reply_text("Usage: /unpin <message_id>")
    await context.bot.unpin_chat_message(
        chat_id=CHANNEL_ID, message_id=int(context.args[0])
    )
    await update.effective_message.reply_text("Post unpinned.")


async def project_index(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    text = (
        "<b>PROJECT INDEX</b>\n\n"
        "A living index of the software, AI, trading and university projects "
        "being built here.\n\n"
        "Use this post as the channel's project hub. Individual project links "
        "and statuses can be added as the portfolio grows."
    )
    message = await context.bot.send_message(
        chat_id=CHANNEL_ID, text=text, parse_mode=ParseMode.HTML
    )
    await update.effective_message.reply_text(
        f"Project index published. Message ID: {message.message_id}"
    )


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")
    if not CHANNEL_ID:
        raise RuntimeError("TELEGRAM_CHANNEL_ID is missing.")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("post", post))
    app.add_handler(CommandHandler("edit", edit))
    app.add_handler(CommandHandler("pin", pin))
    app.add_handler(CommandHandler("unpin", unpin))
    app.add_handler(CommandHandler("projectindex", project_index))

    logger.info("TG-CHANNEL-MANAGER started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
