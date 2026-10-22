# TG-CHANNEL-MANAGER

Telegram channel management bot with an admin-only control panel.

## V1 features

- Admin-only access
- Button-based control panel
- Publish text, photos, videos and documents
- Preview before publishing
- Edit bot-authored text posts and media captions
- Delete channel posts where the bot has permission
- Pin and unpin posts
- View channel information and subscriber/member count
- Legacy command controls remain available
- Secrets stay outside GitHub with `.env`

## Telegram limitation

The normal Telegram Bot API does not let a bot impersonate a personal Telegram account. Posts created through this bot can be managed reliably by the bot. Some channel moderation actions on other messages may be available when Telegram grants the bot the corresponding administrator permission, but arbitrary editing of messages authored by a personal account is not supported by the Bot API.

Using a user account through MTProto is a different architecture and requires user-account authentication/session credentials. It is intentionally not part of V1.

## Setup

1. Create a bot with **@BotFather** and copy its token.
2. Add the bot to the Telegram channel as an administrator.
3. Give it permissions to post, edit, delete and pin messages.
4. Clone this repository.
5. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

6. Copy `.env.example` to `.env`.
7. Set the bot token, channel username/ID and admin Telegram user ID.
8. Run:

```bash
python bot.py
```

Open a private chat with the bot and send `/start`.

## Commands

- `/start` — open control panel
- `/help`
- `/id`
- `/post <text>`
- `/edit <message_id> <new text>`
- `/delete <message_id>`
- `/pin <message_id>`
- `/unpin <message_id>`

## Next phase

Planned additions: persistent post history, scheduling, multi-channel support, subscription/access management and payments.
