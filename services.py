from datetime import datetime, timezone

from telegram.error import BadRequest


def content_kind(message):
    if message.photo:
        return "photo"
    if message.video:
        return "video"
    if message.document:
        return "document"
    return "text"


async def copy_to_channel(bot, channel_id, source_chat_id, source_message_id):
    return await bot.copy_message(
        chat_id=channel_id,
        from_chat_id=source_chat_id,
        message_id=source_message_id,
    )


async def edit_post(bot, channel_id, message_id, text):
    try:
        await bot.edit_message_text(
            chat_id=channel_id, message_id=message_id, text=text
        )
    except BadRequest:
        await bot.edit_message_caption(
            chat_id=channel_id, message_id=message_id, caption=text
        )


def parse_local_datetime(raw, tz):
    raw = raw.strip()
    formats = ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S")
    for fmt in formats:
        try:
            local = datetime.strptime(raw, fmt).replace(tzinfo=tz)
            return local.astimezone(timezone.utc)
        except ValueError:
            pass
    raise ValueError("Use YYYY-MM-DD HH:MM")


def display_time(iso_value, tz):
    return datetime.fromisoformat(iso_value).astimezone(tz).strftime("%Y-%m-%d %H:%M")
