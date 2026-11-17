"""Сумісний запуск API. Реалізація лише у meditrack.api."""
from meditrack.api import create_app

if __name__ == "__main__":
    from meditrack.__main__ import main
    main(["api"])
