import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    manager_bot_token: str
    database_path: Path
    timezone: ZoneInfo

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")
        return cls(
            manager_bot_token=token,
            database_path=Path(os.getenv("DATABASE_PATH", "channel_manager.db")),
            timezone=ZoneInfo(os.getenv("TIMEZONE", "Africa/Kampala")),
        )
