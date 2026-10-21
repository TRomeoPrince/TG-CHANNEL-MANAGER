# TG-CHANNEL-MANAGER

Telegram management bot for a developer/tech-community portfolio channel.

## MVP features

- Admin-only control
- Publish channel posts
- Edit bot-authored channel posts
- Pin and unpin posts
- Publish a starter project index
- Keep secrets outside GitHub with `.env`

> Telegram Bot API limitation: a bot can edit messages it sent itself. It cannot arbitrarily rewrite old messages posted manually by your personal Telegram account.

## Setup

1. Create a bot with **@BotFather** and copy its token.
2. Add the bot to your Telegram channel as an administrator.
3. Give it permission to post, edit and pin messages.
4. Clone this repository.
5. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

6. Copy `.env.example` to `.env`.
7. Put your bot token, channel username/ID and Telegram user ID in `.env`.
8. Run:

```bash
python bot.py
```

Message the bot with `/id` to learn your Telegram user ID, then add it to `ADMIN_USER_IDS`.

## Commands

- `/start`
- `/help`
- `/id`
- `/post <text>`
- `/edit <message_id> <new text>`
- `/pin <message_id>`
- `/unpin <message_id>`
- `/projectindex`

## Next phase

Planned additions include persistent project records, rich project cards, GitHub synchronization, scheduled updates, media posting, drafts/approval flow, analytics and multi-channel support.
