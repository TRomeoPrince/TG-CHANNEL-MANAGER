from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📤 Create", callback_data="create"),
            InlineKeyboardButton("🗂 Posts", callback_data="posts"),
        ],
        [
            InlineKeyboardButton("⏰ Scheduled", callback_data="scheduled"),
            InlineKeyboardButton("📺 Channels", callback_data="channels"),
        ],
        [
            InlineKeyboardButton("🛠 Manage by ID", callback_data="manage"),
            InlineKeyboardButton("📊 Dashboard", callback_data="dashboard"),
        ],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])


def cancel_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ])


def channel_picker(channels, prefix: str):
    rows = []
    for channel in channels:
        label = channel["alias"] or channel["title"] or channel["chat_id"]
        rows.append([
            InlineKeyboardButton(
                f"📺 {label}", callback_data=f"{prefix}:{channel['id']}"
            )
        ])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)
