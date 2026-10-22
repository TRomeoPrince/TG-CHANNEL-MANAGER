import sqlite3
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL UNIQUE,
    title TEXT,
    alias TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_chat_id TEXT NOT NULL,
    telegram_message_id INTEGER,
    kind TEXT NOT NULL,
    text TEXT,
    source_chat_id TEXT,
    source_message_id INTEGER,
    status TEXT NOT NULL,
    scheduled_for TEXT,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    published_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_posts_status_schedule
ON posts(status, scheduled_for);
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
            con.executescript(SCHEMA)

    def add_channel(self, chat_id: str, title: str = "", alias: str = ""):
        with self.connect() as con:
            con.execute(
                """INSERT INTO channels(chat_id,title,alias,created_at)
                   VALUES(?,?,?,?)
                   ON CONFLICT(chat_id) DO UPDATE SET
                   title=excluded.title, alias=excluded.alias, enabled=1""",
                (chat_id, title, alias, utcnow()),
            )

    def remove_channel(self, chat_id: str):
        with self.connect() as con:
            con.execute("UPDATE channels SET enabled=0 WHERE chat_id=?", (chat_id,))

    def channels(self):
        with self.connect() as con:
            return con.execute(
                "SELECT * FROM channels WHERE enabled=1 ORDER BY id"
            ).fetchall()

    def channel(self, chat_id: str):
        with self.connect() as con:
            return con.execute(
                "SELECT * FROM channels WHERE chat_id=? AND enabled=1", (chat_id,)
            ).fetchone()

    def save_post(self, **values):
        fields = ",".join(values)
        marks = ",".join("?" for _ in values)
        with self.connect() as con:
            cur = con.execute(
                f"INSERT INTO posts({fields}) VALUES({marks})", tuple(values.values())
            )
            return cur.lastrowid

    def mark_published(self, post_id: int, telegram_message_id: int):
        with self.connect() as con:
            con.execute(
                """UPDATE posts SET status='published', telegram_message_id=?,
                   published_at=? WHERE id=?""",
                (telegram_message_id, utcnow(), post_id),
            )

    def cancel_post(self, post_id: int):
        with self.connect() as con:
            con.execute(
                "UPDATE posts SET status='cancelled' WHERE id=? AND status='scheduled'",
                (post_id,),
            )

    def recent_posts(self, limit=10):
        with self.connect() as con:
            return con.execute(
                "SELECT * FROM posts ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()

    def scheduled_posts(self):
        with self.connect() as con:
            return con.execute(
                "SELECT * FROM posts WHERE status='scheduled' ORDER BY scheduled_for"
            ).fetchall()

    def due_posts(self, now_iso: str):
        with self.connect() as con:
            return con.execute(
                """SELECT * FROM posts WHERE status='scheduled'
                   AND scheduled_for<=? ORDER BY scheduled_for""",
                (now_iso,),
            ).fetchall()
