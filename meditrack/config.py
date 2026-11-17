"""Single configuration source: repository .env; imports have no side effects."""
from dataclasses import dataclass
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    database_path: str = str(BASE_DIR / "data" / "meditrack.sqlite3")
    bot_token: str = ""
    device_id: str = "meditrack-01"
    device_secret: str = ""
    owner_telegram_id: int = 0
    api_host: str = "127.0.0.1"
    api_port: int = 5000
    late_seconds: int = 300


def load() -> Settings:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env", override=False)
    path = Path(os.getenv("DATABASE_PATH", "data/meditrack.sqlite3"))
    if not path.is_absolute():
        path = BASE_DIR / path
    return Settings(
        database_path=str(path), bot_token=os.getenv("BOT_TOKEN", "").strip(),
        device_id=os.getenv("DEVICE_ID", "meditrack-01"),
        device_secret=os.getenv("DEVICE_SECRET", ""),
        owner_telegram_id=int(os.getenv("OWNER_TELEGRAM_ID", "0")),
        api_host=os.getenv("API_HOST", "127.0.0.1"),
        api_port=int(os.getenv("API_PORT", "5000")),
    )
