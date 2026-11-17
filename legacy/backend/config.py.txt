# ============================================================
#  MediTrack — config.py
#  Централізована конфігурація через .env файл
# ============================================================

import os
from dotenv import load_dotenv

# Завантажуємо змінні з файлу .env (якщо він є)
load_dotenv()


# --- Telegram ---
BOT_TOKEN: str = os.environ["BOT_TOKEN"]

# --- MySQL (спільні параметри) ---
DB_HOST: str     = os.getenv("DB_HOST", "localhost")
DB_PORT: int     = int(os.getenv("DB_PORT", "3306"))
DB_NAME: str     = os.getenv("DB_NAME", "meditrack")
DB_USER: str     = os.environ["DB_USER"]
DB_PASSWORD: str = os.environ["DB_PASSWORD"]

# --- Flask API ---
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "5000"))
API_DEBUG: bool = os.getenv("API_DEBUG", "false").lower() == "true"

# --- Логіка диспенсера ---
# Скільки хвилин тому вважати розклад «актуальним»
DISPENSE_WINDOW_MINUTES: int = int(os.getenv("DISPENSE_WINDOW_MINUTES", "5"))
