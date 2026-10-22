import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_user_ids: frozenset[int]
    database_path: Path
    timezone: ZoneInfo
    default_channel: str

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        admins = frozenset(
            int(x.strip())
            for x in os.getenv("ADMIN_USER_IDS", "").split(",")
            if x.strip().isdigit()
        )
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")
        if not admins:
            raise RuntimeError("ADMIN_USER_IDS is missing.")
        return cls(
            bot_token=token,
            admin_user_ids=admins,
            database_path=Path(os.getenv("DATABASE_PATH", "channel_manager.db")),
            timezone=ZoneInfo(os.getenv("TIMEZONE", "Africa/Kampala")),
            default_channel=os.getenv("TELEGRAM_CHANNEL_ID", "").strip(),
        )
