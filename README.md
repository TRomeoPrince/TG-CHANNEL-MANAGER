# TG-CHANNEL-MANAGER

Full Telegram channel operations bot for managing one or many channels from a private admin control panel.

## Full version

### Publishing
- Text, photo, video and document posts
- Media captions
- Preview before publish
- Publish immediately or schedule for later
- Quick text publishing command
- No local media archive required: Telegram message references are reused

### Channel management
- Multiple managed channels
- Add/disable channels without changing code
- Verify the bot is an administrator before adding a channel
- Channel aliases
- Per-channel publishing

### Post management
- Persistent SQLite post history
- Edit text posts and media captions
- Delete posts
- Pin/unpin posts
- Manage arbitrary channel message IDs when Telegram permits the bot action
- Scheduled-post records survive bot restarts

### Administration
- Strict admin-user allowlist
- Button-based private control panel
- Dashboard
- Direct command fallback
- Secrets/configuration through environment variables
- Configurable timezone and database location

## Install

```bash
git clone https://github.com/TRomeoPrince/TG-CHANNEL-MANAGER.git
cd TG-CHANNEL-MANAGER
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python bot.py
```

Fill in `.env` before running.

## Telegram setup

Create the bot with BotFather, add it as administrator to every channel it should manage, and grant only the permissions you need: posting, editing/deleting messages and pinning.

Open the bot privately and send `/id`. Put your Telegram ID in `ADMIN_USER_IDS`, restart, then use `/start`.

## Main commands

- `/start` — full control panel
- `/id`
- `/addchannel <@username|-100id> [alias]`
- `/removechannel <channel id>`
- `/channels`
- `/post <text>`
- `/edit <channel> <message_id> <text>`
- `/delete <channel> <message_id>`
- `/pin <channel> <message_id>`
- `/unpin <channel> <message_id>`

## Editing limitation

The Telegram Bot API does not allow a bot to impersonate your personal Telegram account. The manager can fully manage posts it authored and can perform administrator moderation actions Telegram exposes to bots. Arbitrarily editing the text of a message authored by your personal account is not a Bot API capability.

An MTProto user-account controller is possible as a separate optional architecture, but it requires authenticating and protecting a real Telegram account session. It is deliberately not bundled into the default bot.

## Architecture

- `bot.py` — Telegram UI, commands and workflows
- `config.py` — environment configuration
- `database.py` — SQLite channels/post history/scheduling
- `keyboards.py` — reusable control-panel keyboards
- `services.py` — publishing/editing/time helpers

## Planned advanced modules

The architecture is ready to extend with subscriber/access management, invite-link lifecycle, payment integrations, richer analytics, reusable post templates, recurring schedules, moderation workflows and an optional AI content assistant.

A smaller client-specific edition can be derived from this project without exposing or requiring the full manager feature set.
