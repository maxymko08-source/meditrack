import asyncio
import logging
import threading
import config
import database
import server
import bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def start_flask():
    """Запуск Flask сервера у фоновому потоці."""
    try:
        server.run_server()
    except Exception as e:
        logger.error(f"Помилка роботи Flask сервера: {e}", exc_info=True)


def main():
    """Головна точка входу для одночасного запуску Flask сервера та Telegram-бота."""
    print("=" * 60)
    print("  Система контролю прийому ліків (Telegram Bot + Flask API)")
    print("=" * 60)

    # 1. Ініціалізація бази даних MySQL
    try:
        database.init_db()
    except Exception as e:
        logger.error(
            f"Не вдалося підключитися до MySQL: {e}\n"
            "Перевірте, чи запущено службу MySQL та правильність реквізитів у файлі .env"
        )
        return

    # 2. Запуск Flask сервера в окремому потоці
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    logger.info(f"Flask API сервер запущено на http://localhost:{config.FLASK_PORT}")

    # 3. Перевірка токена Telegram-бота
    if not config.BOT_TOKEN or config.BOT_TOKEN == "your_telegram_bot_token_here":
        print("\n" + "!" * 60)
        print("УВАГА: Токен Telegram-бота не налаштовано у файлі .env!")
        print("1. Отримайте токен у @BotFather в Telegram.")
        print("2. Вкажіть його у файлі .env: BOT_TOKEN=ваш_токен")
        print("3. Перезапустіть програму.")
        print("Flask API сервер продовжує працювати на http://localhost:5000/api/check")
        print("!" * 60 + "\n")

        # Тримаємо Flask сервер активним, якщо бот не запущено
        try:
            while True:
                threading.Event().wait(1)
        except KeyboardInterrupt:
            print("\nРоботу сервера завершено.")
        return

    # 4. Запуск Telegram-бота в основному асинхронному циклі
    logger.info("Запуск Telegram-бота...")
    try:
        asyncio.run(bot.main())
    except KeyboardInterrupt:
        print("\nРоботу системи зупинено користувачем.")


if __name__ == "__main__":
    main()
