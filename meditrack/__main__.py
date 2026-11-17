"""Run from repository root: python -m meditrack [init|api|bot|notify|run]."""
import argparse
import asyncio
import logging
import threading
from .config import load
from .database import Store


def main(argv=None):
    parser = argparse.ArgumentParser(description="MediTrack — керування прототипом диспенсера")
    parser.add_argument("command", nargs="?", default="run", choices=["init", "api", "bot", "notify", "run"])
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load()
    store = Store(settings.database_path, late_seconds=settings.late_seconds)
    store.initialize()
    if not settings.device_secret or not settings.owner_telegram_id:
        parser.error("Налаштуйте DEVICE_SECRET (щонайменше 32 символи) та OWNER_TELEGRAM_ID у кореневому .env.")
    store.register_device(settings.device_id, settings.owner_telegram_id, settings.device_secret)
    if args.command == "init":
        print("БД ініціалізовано. Пристрій потребує /service перед завантаженням.")
        return
    if args.command == "bot":
        from .bot import main as bot_main
        asyncio.run(bot_main(settings, store))
        return
    if args.command == "notify":
        from .notifications import run_worker
        run_worker(store, settings.bot_token)
        return
    from waitress import serve
    from .api import create_app
    app = create_app(settings, store)
    if args.command == "api":
        serve(app, host=settings.api_host, port=settings.api_port, threads=4)
        return
    from .notifications import run_worker
    stop = threading.Event()
    worker = threading.Thread(target=run_worker, args=(store, settings.bot_token, stop), daemon=True)
    worker.start()
    try:
        if settings.bot_token:
            from .bot import main as bot_main
            api_thread = threading.Thread(target=serve, args=(app,), kwargs={"host": settings.api_host, "port": settings.api_port, "threads": 4}, daemon=True)
            api_thread.start()
            asyncio.run(bot_main(settings, store))
        else:
            logging.warning("BOT_TOKEN відсутній; Telegram не запущено.")
            serve(app, host=settings.api_host, port=settings.api_port, threads=4)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()


if __name__ == "__main__":
    main()
