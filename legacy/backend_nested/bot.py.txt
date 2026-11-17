# ============================================================
#  MediTrack — bot.py
#  Telegram-бот на aiogram 3.x
#
#  Команди:
#    /start    — реєстрація користувача
#    /set_time — встановити час прийому ліків
# ============================================================

from __future__ import annotations

import asyncio
import logging
import re

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

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
#  Ініціалізація
# -----------------------------------------------------------
bot = Bot(token=config.BOT_TOKEN)
router = Router()


# -----------------------------------------------------------
#  FSM — стани для /set_time
# -----------------------------------------------------------
class ScheduleForm(StatesGroup):
    waiting_for_time = State()


# -----------------------------------------------------------
#  Допоміжна функція: валідація часу HH:MM
# -----------------------------------------------------------
TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def is_valid_time(text: str) -> bool:
    """Перевіряє, чи рядок відповідає формату HH:MM (00:00 – 23:59)."""
    return bool(TIME_PATTERN.match(text.strip()))


# ============================================================
#  Обробники команд
# ============================================================

@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Реєструє користувача або вітає повторно."""
    telegram_id = message.from_user.id
    # Визначаємо ім'я: full_name або username як запасний варіант
    name = message.from_user.full_name or message.from_user.username or f"User{telegram_id}"

    user_id, created = await db.async_get_or_create_user(telegram_id, name)

    if created:
        logger.info("New user registered: telegram_id=%d, name=%s", telegram_id, name)
        await message.answer(
            f"👋 Вітаємо у MediTrack, <b>{name}</b>!\n\n"
            "Я допоможу вам не пропустити час прийому ліків.\n"
            "Щоб встановити час — введіть /set_time.",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"🔄 Ви вже зареєстровані, <b>{name}</b>!\n"
            "Щоб змінити або додати час прийому — введіть /set_time.",
            parse_mode="HTML",
        )


@router.message(Command("set_time"))
async def cmd_set_time(message: Message, state: FSMContext) -> None:
    """Запускає FSM для введення часу прийому ліків."""
    # Переконуємось, що користувач зареєстрований
    telegram_id = message.from_user.id
    name = message.from_user.full_name or message.from_user.username or f"User{telegram_id}"
    await db.async_get_or_create_user(telegram_id, name)

    await state.set_state(ScheduleForm.waiting_for_time)
    await message.answer(
        "⏰ Введіть час прийому ліків у форматі <b>ГГ:ХХ</b>\n"
        "Наприклад: <code>08:30</code> або <code>21:00</code>",
        parse_mode="HTML",
    )


@router.message(ScheduleForm.waiting_for_time, F.text)
async def process_time_input(message: Message, state: FSMContext) -> None:
    """Обробляє введений час і зберігає розклад у базу."""
    raw_text = message.text.strip()

    # Валідація формату
    if not is_valid_time(raw_text):
        await message.answer(
            "❌ Невірний формат часу. Будь ласка, введіть час у форматі <b>ГГ:ХХ</b>.\n"
            "Наприклад: <code>08:30</code>",
            parse_mode="HTML",
        )
        return  # Залишаємось у поточному стані — чекаємо правильного вводу

    dispense_time = raw_text  # Рядок виду '08:30'

    # Знаходимо user_id за telegram_id
    telegram_id = message.from_user.id
    name = message.from_user.full_name or f"User{telegram_id}"
    user_id, _ = await db.async_get_or_create_user(telegram_id, name)

    schedule_id = await db.async_create_schedule(user_id, dispense_time)

    await state.clear()  # Виходимо зі стану FSM

    logger.info(
        "Schedule created: schedule_id=%d, user_id=%d, time=%s",
        schedule_id, user_id, dispense_time,
    )

    await message.answer(
        f"✅ Час прийому ліків встановлено на <b>{dispense_time}</b>.\n\n"
        "Ваш розумний диспенсер автоматично видасть таблетку у вказаний час.\n"
        "Ви отримаєте сповіщення після видачі.",
        parse_mode="HTML",
    )


@router.message(ScheduleForm.waiting_for_time)
async def process_time_input_wrong_type(message: Message) -> None:
    """Обробляє нетекстові повідомлення під час очікування часу."""
    await message.answer(
        "⚠️ Будь ласка, надішліть час у текстовому форматі <b>ГГ:ХХ</b>.",
        parse_mode="HTML",
    )


# ============================================================
#  Точка входу
# ============================================================

async def main() -> None:
    """Запускає бота в режимі polling."""
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)

    # Хуки lifecycle: підключення / відключення пулу БД
    dispatcher.startup.register(db.create_async_pool)
    dispatcher.shutdown.register(db.close_async_pool)

    logger.info("Starting MediTrack Telegram Bot (polling)...")
    await dispatcher.start_polling(bot, allowed_updates=["message"])


if __name__ == "__main__":
    asyncio.run(main())
