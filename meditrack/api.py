# ============================================================
#  MediTrack — api.py
#  Flask REST API для ESP8266 (плата диспенсера)
#
#  Ендпоінти:
#    GET  /api/check    — перевірка наявності активного розкладу
#    POST /api/confirm  — підтвердження видачі таблетки
# ============================================================

from __future__ import annotations

import asyncio
import logging
import threading

from flask import Flask, jsonify, request

import config
import database as db

# -----------------------------------------------------------
#  Логування
# -----------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------
#  Flask application
# -----------------------------------------------------------
app = Flask(__name__)


# ============================================================
#  Async helper для відправки Telegram-повідомлень із sync-коду
#
#  Flask є синхронним фреймворком, тому для відправки
#  повідомлення через aiogram Bot (asyncio) потрібен
#  окремий event loop, запущений у фоновому потоці.
# ============================================================

# Фоновий event loop для Telegram-сповіщень
_tg_loop: asyncio.AbstractEventLoop | None = None
_tg_loop_thread: threading.Thread | None = None


def _start_background_loop() -> None:
    """Запускає та тримає event loop у фоновому потоці."""
    global _tg_loop
    _tg_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_tg_loop)
    _tg_loop.run_forever()


def _ensure_tg_loop() -> asyncio.AbstractEventLoop:
    """Гарантує, що фоновий event loop запущений."""
    global _tg_loop_thread, _tg_loop
    if _tg_loop is None or not _tg_loop.is_running():
        _tg_loop_thread = threading.Thread(
            target=_start_background_loop,
            daemon=True,
            name="TelegramNotifyLoop",
        )
        _tg_loop_thread.start()
        # Чекаємо старту loop
        import time
        while _tg_loop is None or not _tg_loop.is_running():
            time.sleep(0.01)
    return _tg_loop


def send_telegram_notification(telegram_id: int, text: str) -> None:
    """Відправляє Telegram-повідомлення асинхронно з синхронного контексту Flask."""
    from aiogram import Bot

    async def _send() -> None:
        bot = Bot(token=config.BOT_TOKEN)
        try:
            await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML")
            logger.info("Telegram notification sent to telegram_id=%d", telegram_id)
        except Exception as exc:
            logger.error("Failed to send Telegram notification: %s", exc)
        finally:
            await bot.session.close()

    loop = _ensure_tg_loop()
    asyncio.run_coroutine_threadsafe(_send(), loop)


# ============================================================
#  Ендпоінти
# ============================================================

@app.get("/api/check")
def check_schedule():
    """Ендпоінт для ESP8266: перевіряє наявність активного розкладу.

    Плата звертається сюди кожну хвилину.

    Responses:
        200 {"status": "DISPENSE", "schedule_id": <int>}
            — є активний розклад, потрібно видати таблетку.
        200 {"status": "WAIT"}
            — нічого видавати не потрібно.
        500 {"error": "..."}
            — помилка сервера.
    """
    logger.debug("GET /api/check — checking for pending schedules.")
    try:
        row = db.sync_find_pending_schedule(config.DISPENSE_WINDOW_MINUTES)
    except Exception as exc:
        logger.exception("DB error in /api/check: %s", exc)
        return jsonify({"error": "Database error"}), 500

    if row:
        logger.info(
            "DISPENSE signal: schedule_id=%d, dispense_time=%s",
            row["id"], row["dispense_time"],
        )
        return jsonify({"status": "DISPENSE", "schedule_id": row["id"]}), 200

    return jsonify({"status": "WAIT"}), 200


@app.post("/api/confirm")
def confirm_dispense():
    """Ендпоінт для ESP8266: підтверджує фізичну видачу таблетки.

    Тіло запиту (JSON):
        {"schedule_id": <int>}

    Responses:
        200 {"ok": true, "message": "Dispensed and user notified."}
            — статус оновлено, користувача сповіщено.
        400 {"error": "..."}
            — невірні вхідні дані.
        404 {"error": "Schedule not found or already dispensed."}
            — запис не знайдено або вже оброблено.
        500 {"error": "..."}
            — помилка сервера.
    """
    # -------------------------------------------------------
    #  Парсинг тіла запиту
    # -------------------------------------------------------
    data = request.get_json(silent=True)
    if not data or "schedule_id" not in data:
        return jsonify({"error": "Missing 'schedule_id' in request body."}), 400

    try:
        schedule_id = int(data["schedule_id"])
    except (ValueError, TypeError):
        return jsonify({"error": "'schedule_id' must be an integer."}), 400

    logger.info("POST /api/confirm — schedule_id=%d", schedule_id)

    # -------------------------------------------------------
    #  Оновлення статусу в БД
    # -------------------------------------------------------
    try:
        updated_rows = db.sync_mark_dispensed(schedule_id)
    except Exception as exc:
        logger.exception("DB error in /api/confirm: %s", exc)
        return jsonify({"error": "Database error"}), 500

    if updated_rows == 0:
        return (
            jsonify({"error": "Schedule not found or already dispensed."}),
            404,
        )

    # -------------------------------------------------------
    #  Відправляємо Telegram-сповіщення користувачу
    # -------------------------------------------------------
    try:
        telegram_id = db.sync_get_telegram_id_by_schedule(schedule_id)
    except Exception as exc:
        logger.exception("Failed to fetch telegram_id for schedule_id=%d: %s", schedule_id, exc)
        telegram_id = None

    if telegram_id:
        send_telegram_notification(
            telegram_id=telegram_id,
            text="✅ <b>Вашу таблетку успішно видано!</b>\n\nБережіть своє здоров'я! 💊",
        )
    else:
        logger.warning("Could not find telegram_id for schedule_id=%d", schedule_id)

    return jsonify({"ok": True, "message": "Dispensed and user notified."}), 200


# ============================================================
#  Точка входу (для розробки)
#  У продакшні використовуйте: gunicorn api:app
# ============================================================

if __name__ == "__main__":
    app.run(
        host=config.API_HOST,
        port=config.API_PORT,
        debug=config.API_DEBUG,
    )
