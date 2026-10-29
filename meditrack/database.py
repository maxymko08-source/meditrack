# ============================================================
#  MediTrack — database.py
#  Рівень доступу до бази даних:
#    - async пул (aiomysql) — для Telegram-бота
#    - sync з'єднання (PyMySQL) — для Flask API
# ============================================================

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

import aiomysql
import pymysql
import pymysql.cursors

import config

logger = logging.getLogger(__name__)


# ================================================================
#  ASYNC частина (aiomysql) — використовується ботом
# ================================================================

# Глобальний пул з'єднань; ініціалізується під час старту бота
_async_pool: aiomysql.Pool | None = None


async def create_async_pool() -> None:
    """Створює асинхронний пул з'єднань до MySQL.

    Викликається один раз при старті бота (on_startup).
    """
    global _async_pool
    _async_pool = await aiomysql.create_pool(
        host=config.DB_HOST,
        port=config.DB_PORT,
        db=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        autocommit=True,
        charset="utf8mb4",
        minsize=1,
        maxsize=10,
    )
    logger.info("Async MySQL pool created.")


async def close_async_pool() -> None:
    """Закриває асинхронний пул. Викликається при зупинці бота."""
    global _async_pool
    if _async_pool:
        _async_pool.close()
        await _async_pool.wait_closed()
        logger.info("Async MySQL pool closed.")


def get_async_pool() -> aiomysql.Pool:
    """Повертає активний пул. Кидає RuntimeError, якщо пул не ініціалізовано."""
    if _async_pool is None:
        raise RuntimeError("Async DB pool is not initialized. Call create_async_pool() first.")
    return _async_pool


# ---------------------------------------------------------------
#  Async CRUD — users
# ---------------------------------------------------------------

async def async_get_or_create_user(
    telegram_id: int,
    name: str,
) -> tuple[int, bool]:
    """Повертає (user_id, created).

    Якщо користувач вже є — повертає його id та created=False.
    Якщо новий — вставляє і повертає created=True.
    """
    pool = get_async_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # Спочатку шукаємо
            await cur.execute(
                "SELECT id FROM users WHERE telegram_id = %s",
                (telegram_id,),
            )
            row = await cur.fetchone()
            if row:
                return row["id"], False

            # Вставляємо нового користувача
            await cur.execute(
                "INSERT INTO users (telegram_id, name) VALUES (%s, %s)",
                (telegram_id, name),
            )
            return cur.lastrowid, True


# ---------------------------------------------------------------
#  Async CRUD — schedules
# ---------------------------------------------------------------

async def async_create_schedule(user_id: int, dispense_time: str) -> int:
    """Додає новий запис у розклад.

    Args:
        user_id:      ID користувача з таблиці users.
        dispense_time: Час у форматі 'HH:MM'.

    Returns:
        ID щойно створеного розкладу.
    """
    pool = get_async_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO schedules (user_id, dispense_time, status)
                VALUES (%s, %s, 'pending')
                """,
                (user_id, dispense_time),
            )
            return cur.lastrowid


# ================================================================
#  SYNC частина (PyMySQL) — використовується Flask API
# ================================================================

def get_sync_connection() -> pymysql.connections.Connection:
    """Відкриває та повертає нове синхронне з'єднання до MySQL.

    ВАЖЛИВО: Завжди закривайте з'єднання після використання.
    Краще використовувати get_sync_db() як context manager.
    """
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        db=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


@contextmanager
def get_sync_db() -> Generator[pymysql.connections.Connection, None, None]:
    """Context manager для синхронного з'єднання.

    Використання:
        with get_sync_db() as db:
            with db.cursor() as cur:
                cur.execute(...)
    """
    conn = get_sync_connection()
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------
#  Sync CRUD — schedules (для Flask)
# ---------------------------------------------------------------

def sync_find_pending_schedule(window_minutes: int) -> dict | None:
    """Шукає активний (pending) розклад у вікні часу.

    Повертає перший знайдений рядок або None.

    Логіка: порівнюємо поточний час сервера з dispense_time.
    Вважаємо запис актуальним, якщо різниця від -window_minutes до 0 хвилин.
    """
    sql = """
        SELECT s.id, s.user_id, s.dispense_time
        FROM schedules s
        WHERE s.status = 'pending'
          AND TIMEDIFF(TIME(NOW()), s.dispense_time) BETWEEN -SEC_TO_TIME(%s * 60) AND '00:00:00'
        ORDER BY s.dispense_time ASC
        LIMIT 1
    """
    with get_sync_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (window_minutes,))
            return cur.fetchone()  # dict або None


def sync_mark_dispensed(schedule_id: int) -> int:
    """Змінює статус розкладу на 'dispensed'.

    Returns:
        Кількість оновлених рядків (0 або 1).
    """
    sql = "UPDATE schedules SET status = 'dispensed' WHERE id = %s AND status = 'pending'"
    with get_sync_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (schedule_id,))
            return cur.rowcount


def sync_get_telegram_id_by_schedule(schedule_id: int) -> int | None:
    """Повертає telegram_id користувача, якому належить розклад."""
    sql = """
        SELECT u.telegram_id
        FROM schedules s
        JOIN users u ON u.id = s.user_id
        WHERE s.id = %s
    """
    with get_sync_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (schedule_id,))
            row = cur.fetchone()
            return row["telegram_id"] if row else None
