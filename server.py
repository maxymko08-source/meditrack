import logging
from datetime import datetime
from flask import Flask, jsonify, request

import config
import database

import requests  # Якщо бібліотеки немає, додайте import requests зверху файлу

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route("/api/confirm", methods=["POST"])
def confirm_dispense():
    """
    Ендпоінт підтвердження видачі від ESP8266:
    1. Приймає JSON від плати (наприклад: {"user_id": 5144680721}).
    2. Надсилає сповіщення користувачу в Telegram.
    """
    data = request.get_json() or {}
    # Вкажіть ваш telegram_id за замовчуванням для тесту
    user_id = data.get("user_id", 5144680721)

    # Відправка повідомлення в Telegram через Bot API
    bot_token = config.BOT_TOKEN
    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        "chat_id": user_id,
        "text": "✅ Вашу таблетку успішно видано!"
    }
    
    try:
        res = requests.post(telegram_url, json=payload)
        if res.status_code == 200:
            logger.info(f"Сповіщення про видачу надіслано користувачу {user_id}")
            return jsonify({"status": "SUCCESS", "message": "Notification sent"})
        else:
            return jsonify({"status": "ERROR", "telegram_response": res.json()}), 500
    except Exception as e:
        logger.error(f"Помилка надсилання в Telegram: {e}")
        return jsonify({"status": "ERROR", "details": str(e)}), 500

@app.route("/", methods=["GET"])
def index():
    """Головна сторінка для перевірки працездатності сервера."""
    current_time = datetime.now().strftime("%H:%M:%S")
    return jsonify({
        "service": "Medication Dispenser API",
        "server_time": current_time,
        "endpoints": {
            "/api/check": "Перевірка збігу поточного часу з розкладом у БД (повертає DISPENSE або WAIT)",
            "/api/schedules": "Список усіх збережених розкладів"
        }
    })


@app.route("/api/check", methods=["GET"])
def check_medication_time():
    """
    Основний ендпоінт перевірки:
    1. Визначає поточний час сервера у форматі ГГ:ХХ (наприклад, '14:30').
       (Також підтримує необов'язковий параметр ?time=ГГ:ХХ для зручного тестування).
    2. Підключається до бази даних MySQL.
    3. Якщо поточний час збігається із записом у базі — повертає {"status": "DISPENSE"}.
    4. Якщо ні — повертає {"status": "WAIT"}.
    """
    # За замовчуванням беремо поточний час сервера (ГГ:ХХ)
    # Якщо передано параметр ?time=... (наприклад, /api/check?time=08:30), використовуємо його
    current_time = request.args.get("time") or datetime.now().strftime("%H:%M")

    try:
        is_match = database.check_schedule_time(current_time)

        if is_match:
            logger.info(f"Час '{current_time}' знайдено в базі! Відповідь: DISPENSE")
            return jsonify({"status": "DISPENSE"})
        else:
            return jsonify({"status": "WAIT"})

    except Exception as e:
        logger.error(f"Помилка при перевірці розкладу в базі: {e}", exc_info=True)
        return jsonify({
            "error": "Database connection error",
            "message": str(e)
        }), 500


@app.route("/api/schedules", methods=["GET"])
def list_schedules():
    """Додатковий ендпоінт для перегляду всіх записів у базі даних."""
    try:
        schedules = database.get_all_schedules()
        # Форматуємо datetime для коректної серіалізації в JSON
        formatted = []
        for s in schedules:
            item = dict(s)
            if "updated_at" in item and item["updated_at"]:
                item["updated_at"] = item["updated_at"].strftime("%Y-%m-%d %H:%M:%S")
            formatted.append(item)

        return jsonify({
            "count": len(formatted),
            "schedules": formatted
        })
    except Exception as e:
        logger.error(f"Помилка отримання розкладів: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def run_server():
    """Ініціалізує базу даних та запускає Flask сервер."""
    database.init_db()
    logger.info(f"Запуск Flask API сервера на http://{config.FLASK_HOST}:{config.FLASK_PORT}...")
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=False)


if __name__ == "__main__":
    run_server()
