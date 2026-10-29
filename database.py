import logging
import pymysql
import aiomysql
import config

logger = logging.getLogger(__name__)


def get_sync_connection():
    """Створює синхронне підключення до бази даних MySQL через PyMySQL (для Flask)."""
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def init_db():
    """
    Ініціалізує базу даних:
    1. Створює базу даних, якщо вона ще не існує.
    2. Створює таблицю medication_schedules для збереження розкладу ліків.
    """
    # Підключаємося до сервера без вибору бази, щоб створити її за необхідності
    conn = pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{config.DB_NAME}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
            cursor.execute(f"USE `{config.DB_NAME}`;")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS medication_schedules (
                    user_id BIGINT PRIMARY KEY,
                    user_name VARCHAR(255),
                    med_time VARCHAR(5) NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """
            )
        logger.info(f"База даних '{config.DB_NAME}' та таблиця 'medication_schedules' готові.")
    finally:
        conn.close()


async def async_save_medication_time(user_id: int, user_name: str, med_time: str) -> bool:
    """
    Асинхронно зберігає або оновлює час прийому ліків для користувача через aiomysql.
    Використовується в aiogram 3.x боті.
    """
    conn = await aiomysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        db=config.DB_NAME,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        async with conn.cursor() as cursor:
            query = """
                INSERT INTO medication_schedules (user_id, user_name, med_time)
                VALUES (%s, %s, %s) AS new_row
                ON DUPLICATE KEY UPDATE
                    user_name = new_row.user_name,
                    med_time = new_row.med_time;
            """
            await cursor.execute(query, (user_id, user_name, med_time))
            return True
    finally:
        conn.close()


async def async_get_user_schedule(user_id: int):
    """Отримує збережений запис користувача через aiomysql."""
    conn = await aiomysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        db=config.DB_NAME,
        charset="utf8mb4",
    )
    try:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(
                "SELECT user_id, user_name, med_time, updated_at FROM medication_schedules WHERE user_id = %s",
                (user_id,),
            )
            return await cursor.fetchone()
    finally:
        conn.close()


def check_schedule_time(target_time: str) -> bool:
    """
    Синхронно перевіряє, чи є в базі хоча б один запис із вказаним часом (ГГ:ХХ).
    Використовується у Flask ендпоінті /api/check.
    """
    conn = get_sync_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM medication_schedules WHERE med_time = %s LIMIT 1",
                (target_time,),
            )
            result = cursor.fetchone()
            return result is not None
    finally:
        conn.close()


def get_all_schedules():
    """Повертає всі збережені розклади (для налагодження та перевірки)."""
    conn = get_sync_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id, user_name, med_time, updated_at FROM medication_schedules")
            return cursor.fetchall()
    finally:
        conn.close()
