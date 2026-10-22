# TG-CHANNEL-MANAGER

A multi-user Telegram bot-management platform.

Users create their own Telegram bots through Telegram's native **Managed Bots**
flow. They do not paste BotFather tokens into the manager. Each created bot is
owned by the user and managed by this platform.

## Architecture

```
Master Manager Bot
        |
        +-- User A
        |     +-- @UserABot
        |            +-- Channel 1
        |            +-- Group 1
        |
        +-- User B
              +-- @UserBBot
                     +-- Channel 2
                     +-- Group 2
```

The master bot receives Telegram's `managed_bot` update, obtains the managed
bot token through Telegram's authorized `getManagedBotToken` method, and
starts that bot dynamically. Child tokens are **not stored in SQLite**.

## What users do

1. Open the master manager bot.
2. Tap **🤖 Create your own bot**.
3. Telegram opens its native Create Bot window.
4. Enter a bot name and @username.
5. Telegram creates the bot under that user's ownership.
6. TG-CHANNEL-MANAGER detects and starts it automatically.
7. The user opens their new bot and sends `/start`.
8. They add their bot to groups/channels they want it to manage.

No BotFather token is copied or pasted by the user.

## Child bot features

Each created bot is automatically bound to its Telegram owner.

- Detect groups/channels it is added to
- List managed chats
- Publish text posts
- Schedule text posts
- Edit posts/captions
- Delete posts
- Pin/unpin posts
- Persistent SQLite chat and post records
- Owner-only control

For a channel, the child bot must be made an administrator with the permissions
needed for the desired actions.

## Manager bot setup

The only bot that must be created manually is the master manager bot.

1. Create it in BotFather.
2. Open its settings in BotFather's Mini App.
3. Enable **Bot Management Mode**.
4. Put its token in `.env`.

Telegram should report the manager bot with `can_manage_bots=true`.

## Environment

```env
TELEGRAM_BOT_TOKEN=YOUR_MANAGER_BOT_TOKEN
DATABASE_PATH=channel_manager.db
TIMEZONE=Africa/Kampala
```

There is intentionally no hard-coded admin user ID and no hard-coded channel.

## Windows installation

Project home:

```
C:\Users\USER\Desktop\Bots\Telegram-Channel_Manager
```

Install/update:

```bat
cd /d "C:\Users\USER\Desktop\Bots\Telegram-Channel_Manager" && git pull && pip install -r requirements.txt
```

Create local environment file if needed:

```bat
copy .env.example .env
notepad .env
```

Run:

```bat
python bot.py
```

## Main manager commands

- `/start` — manager dashboard and native Create Bot control
- `/mybots` — bots owned by the current Telegram user
- `/help`

## Child bot commands

- `/start`
- `/chats`
- `/post <chat_id> <text>`
- `/schedule <chat_id> <YYYY-MM-DD HH:MM> | <text>`
- `/edit <chat_id> <message_id> <text>`
- `/delete <chat_id> <message_id>`
- `/pin <chat_id> <message_id>`
- `/unpin <chat_id> <message_id>`

## Files

- `bot.py` — master manager bot
- `child_runtime.py` — dynamically runs managed user bots
- `database.py` — users, bots, managed chats and post records
- `config.py` — local runtime configuration
- `services.py` — shared post/time helpers

## Security model

The platform stores Telegram user IDs, bot IDs and managed chat metadata.
Managed child-bot tokens are fetched from Telegram at runtime by the authorized
manager bot rather than persisted in the database.

Users remain owners of the bots they create and can manage them through
Telegram/BotFather as Telegram permits.
