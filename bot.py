import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestManagedBot,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ManagedBotUpdatedHandler,
)

from child_runtime import ChildBotRuntime
from config import Settings
from database import Database

settings = Settings.from_env()
db = Database(settings.database_path)
runtimes: dict[int, ChildBotRuntime] = {}

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("tg-channel-manager.manager")


def create_bot_keyboard():
    return ReplyKeyboardMarkup(
        [[
            KeyboardButton(
                "🤖 Create your own bot",
                request_managed_bot=KeyboardButtonRequestManagedBot(
                    request_id=1,
                    suggested_name="My Channel Manager",
                    suggested_username="MyChannelManagerBot",
                ),
            )
        ]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def manager_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🤖 My Bots", callback_data="my_bots"),
            InlineKeyboardButton("➕ Create Bot", callback_data="create_help"),
        ],
        [InlineKeyboardButton("❓ How it works", callback_data="help")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not update.effective_message:
        return
    db.upsert_user(user)
    await update.effective_message.reply_text(
        "👑 <b>TG CHANNEL MANAGER</b>\n\n"
        "Create your own Telegram management bot, then add that bot to the "
        "groups and channels you want it to manage.\n\n"
        "No BotFather token needs to be pasted here.",
        parse_mode="HTML",
        reply_markup=create_bot_keyboard(),
    )
    await update.effective_message.reply_text(
        "Your manager dashboard:",
        reply_markup=manager_menu(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "<b>How it works</b>\n\n"
        "1. Tap <b>Create your own bot</b>.\n"
        "2. Telegram asks for the bot's name and @username.\n"
        "3. The new bot is linked to this manager automatically.\n"
        "4. Add your new bot to channels/groups you own.\n"
        "5. Open the new bot and use /start.\n\n"
        "You remain the owner of the created bot.",
        parse_mode="HTML",
        reply_markup=create_bot_keyboard(),
    )


async def mybots_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    await show_bots(update.effective_message.reply_text, user.id)


async def show_bots(send, user_id: int):
    rows = db.managed_bots(owner_user_id=user_id)
    if not rows:
        return await send(
            "You have no managed bots yet. Tap “🤖 Create your own bot” below.",
            reply_markup=create_bot_keyboard(),
        )
    lines = ["🤖 <b>Your managed bots</b>"]
    for row in rows:
        username = f"@{row['username']}" if row["username"] else str(row["bot_id"])
        chats = len(db.chats(row["bot_id"]))
        lines.append(f"• <b>{row['display_name']}</b> — {username} — {chats} chats")
    await send("\n".join(lines), parse_mode="HTML")


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user

    if q.data == "my_bots":
        rows = db.managed_bots(owner_user_id=user.id)
        if not rows:
            return await q.edit_message_text(
                "No managed bots yet. Use the “🤖 Create your own bot” button "
                "in the reply keyboard."
            )
        lines = ["🤖 <b>Your managed bots</b>"]
        for row in rows:
            username = f"@{row['username']}" if row["username"] else str(row["bot_id"])
            chats = len(db.chats(row["bot_id"]))
            running = "🟢" if row["bot_id"] in runtimes else "🔴"
            lines.append(
                f"{running} <b>{row['display_name']}</b> — {username} — {chats} chats"
            )
        return await q.edit_message_text(
            "\n".join(lines), parse_mode="HTML", reply_markup=manager_menu()
        )

    if q.data == "create_help":
        return await q.edit_message_text(
            "Use the <b>🤖 Create your own bot</b> button shown at the bottom of "
            "this chat. Telegram itself opens the secure bot creation window.",
            parse_mode="HTML",
            reply_markup=manager_menu(),
        )

    if q.data == "help":
        return await q.edit_message_text(
            "Telegram creates the bot under your ownership and authorizes this "
            "manager to operate it. After creation, add your new bot to the "
            "channels/groups you want managed, then open that bot and send /start.",
            reply_markup=manager_menu(),
        )


async def start_child(bot_id: int, owner_user_id: int, token: str):
    old = runtimes.pop(bot_id, None)
    if old:
        try:
            await old.stop_runtime()
        except Exception:
            logger.exception("Failed stopping old runtime for %s", bot_id)

    runtime = ChildBotRuntime(
        token=token,
        bot_id=bot_id,
        owner_user_id=owner_user_id,
        db=db,
        timezone=settings.timezone,
    )
    await runtime.start_runtime()
    runtimes[bot_id] = runtime


async def managed_bot_updated(update: Update, context: ContextTypes.DEFAULT_TYPE):
    managed = update.managed_bot
    if not managed:
        return

    owner = managed.user
    child = managed.bot
    db.upsert_managed_bot(owner, child)

    try:
        token = await context.bot.get_managed_bot_token(user_id=child.id)
        await start_child(child.id, owner.id, token)
    except TelegramError as exc:
        logger.exception("Could not start managed bot @%s", child.username)
        db.deactivate_managed_bot(child.id)
        try:
            await context.bot.send_message(
                owner.id,
                f"⚠️ I received @{child.username or child.id}, but Telegram did not "
                f"allow me to start it: {exc}",
            )
        except TelegramError:
            pass
        return

    try:
        await context.bot.send_message(
            owner.id,
            "✅ <b>Your bot is connected.</b>\n\n"
            f"Bot: @{child.username}\n"
            "Open it and send /start, then add it to any groups or channels you "
            "want it to manage.",
            parse_mode="HTML",
        )
    except TelegramError:
        logger.exception("Could not notify owner %s", owner.id)


async def post_init(app: Application):
    me = await app.bot.get_me()
    if not getattr(me, "can_manage_bots", False):
        logger.warning(
            "Bot Management Mode is NOT enabled for @%s. Enable it in BotFather.",
            me.username,
        )
    else:
        logger.info("Bot Management Mode confirmed for @%s", me.username)

    for row in db.managed_bots():
        try:
            token = await app.bot.get_managed_bot_token(user_id=row["bot_id"])
            await start_child(row["bot_id"], row["owner_user_id"], token)
        except Exception:
            logger.exception("Could not restore managed bot %s", row["bot_id"])
            db.deactivate_managed_bot(row["bot_id"])


async def post_shutdown(app: Application):
    for bot_id, runtime in list(runtimes.items()):
        try:
            await runtime.stop_runtime()
        except Exception:
            logger.exception("Could not stop managed bot %s", bot_id)
    runtimes.clear()


async def error_handler(update, context):
    logger.exception("Manager bot error", exc_info=context.error)


def main():
    app = (
        Application.builder()
        .token(settings.manager_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("mybots", mybots_command))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(ManagedBotUpdatedHandler(managed_bot_updated))
    app.add_error_handler(error_handler)

    logger.info("TG-CHANNEL-MANAGER platform starting")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
