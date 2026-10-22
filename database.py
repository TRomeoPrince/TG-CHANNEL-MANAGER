import sqlite3
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS platform_users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS managed_bots (
    bot_id INTEGER PRIMARY KEY,
    owner_user_id INTEGER NOT NULL,
    username TEXT,
    display_name TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(owner_user_id) REFERENCES platform_users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_managed_bots_owner
ON managed_bots(owner_user_id);

CREATE TABLE IF NOT EXISTS managed_chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    chat_type TEXT NOT NULL,
    title TEXT,
    username TEXT,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(bot_id, chat_id),
    FOREIGN KEY(bot_id) REFERENCES managed_bots(bot_id)
);

CREATE INDEX IF NOT EXISTS idx_managed_chats_bot
ON managed_chats(bot_id, status);

CREATE TABLE IF NOT EXISTS managed_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    telegram_message_id INTEGER,
    text TEXT,
    status TEXT NOT NULL,
    scheduled_for TEXT,
    created_at TEXT NOT NULL,
    published_at TEXT,
    FOREIGN KEY(bot_id) REFERENCES managed_bots(bot_id)
);

CREATE INDEX IF NOT EXISTS idx_managed_posts_due
ON managed_posts(bot_id, status, scheduled_for);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.init()

    def connect(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con

    def init(self):
        with self.connect() as con:
            con.execute("PRAGMA foreign_keys=ON")
            con.executescript(SCHEMA)

    def upsert_user(self, user):
        now = utcnow()
        with self.connect() as con:
            con.execute(
                """INSERT INTO platform_users(user_id,username,first_name,created_at,updated_at)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(user_id) DO UPDATE SET
                   username=excluded.username,
                   first_name=excluded.first_name,
                   updated_at=excluded.updated_at""",
                (user.id, user.username, user.first_name, now, now),
            )

    def upsert_managed_bot(self, owner, bot):
        self.upsert_user(owner)
        now = utcnow()
        with self.connect() as con:
            con.execute(
                """INSERT INTO managed_bots(
                       bot_id,owner_user_id,username,display_name,active,created_at,updated_at
                   ) VALUES(?,?,?,?,1,?,?)
                   ON CONFLICT(bot_id) DO UPDATE SET
                   owner_user_id=excluded.owner_user_id,
                   username=excluded.username,
                   display_name=excluded.display_name,
                   active=1,
                   updated_at=excluded.updated_at""",
                (bot.id, owner.id, bot.username, bot.full_name, now, now),
            )

    def deactivate_managed_bot(self, bot_id: int):
        with self.connect() as con:
            con.execute(
                "UPDATE managed_bots SET active=0, updated_at=? WHERE bot_id=?",
                (utcnow(), bot_id),
            )

    def managed_bots(self, owner_user_id=None, active_only=True):
        sql = "SELECT * FROM managed_bots WHERE 1=1"
        params = []
        if owner_user_id is not None:
            sql += " AND owner_user_id=?"
            params.append(owner_user_id)
        if active_only:
            sql += " AND active=1"
        sql += " ORDER BY id" if False else " ORDER BY created_at"
        with self.connect() as con:
            return con.execute(sql, params).fetchall()

    def managed_bot(self, bot_id: int):
        with self.connect() as con:
            return con.execute(
                "SELECT * FROM managed_bots WHERE bot_id=?", (bot_id,)
            ).fetchone()

    def owner_id(self, bot_id: int):
        row = self.managed_bot(bot_id)
        return row["owner_user_id"] if row else None

    def upsert_chat(self, bot_id: int, chat, status: str):
        with self.connect() as con:
            con.execute(
                """INSERT INTO managed_chats(
                       bot_id,chat_id,chat_type,title,username,status,updated_at
                   ) VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(bot_id,chat_id) DO UPDATE SET
                   chat_type=excluded.chat_type,
                   title=excluded.title,
                   username=excluded.username,
                   status=excluded.status,
                   updated_at=excluded.updated_at""",
                (
                    bot_id, chat.id, chat.type, chat.title or chat.full_name or "",
                    chat.username, status, utcnow(),
                ),
            )

    def chats(self, bot_id: int, active_only=True):
        sql = "SELECT * FROM managed_chats WHERE bot_id=?"
        params = [bot_id]
        if active_only:
            sql += " AND status IN ('member','administrator','creator')"
        sql += " ORDER BY title, chat_id"
        with self.connect() as con:
            return con.execute(sql, params).fetchall()

    def save_post(
        self, bot_id: int, chat_id: int, text: str, status: str,
        telegram_message_id=None, scheduled_for=None
    ):
        with self.connect() as con:
            cur = con.execute(
                """INSERT INTO managed_posts(
                       bot_id,chat_id,telegram_message_id,text,status,
                       scheduled_for,created_at,published_at
                   ) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    bot_id, chat_id, telegram_message_id, text, status,
                    scheduled_for, utcnow(),
                    utcnow() if status == "published" else None,
                ),
            )
            return cur.lastrowid

    def due_posts(self, bot_id: int, now_iso: str):
        with self.connect() as con:
            return con.execute(
                """SELECT * FROM managed_posts
                   WHERE bot_id=? AND status='scheduled' AND scheduled_for<=?
                   ORDER BY scheduled_for""",
                (bot_id, now_iso),
            ).fetchall()

    def mark_post_published(self, post_id: int, message_id: int):
        with self.connect() as con:
            con.execute(
                """UPDATE managed_posts
                   SET status='published',telegram_message_id=?,published_at=?
                   WHERE id=?""",
                (message_id, utcnow(), post_id),
            )
