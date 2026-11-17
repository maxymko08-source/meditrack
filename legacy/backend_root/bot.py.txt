import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import config
import database

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Регулярний вираз для перевірки формату ГГ:ХХ (від 00:00 до 23:59)
TIME_REGEX = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class MedicationStates(StatesGroup):
    """Стани FSM для діалогу встановлення часу прийому ліків."""
    waiting_for_time = State()


dp = Dispatcher(storage=MemoryStorage())


@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    """
    Обробник команди /start.
    Вітає користувача та запитує час прийому ліків у форматі ГГ:ХХ.
    """
    user_name = message.from_user.full_name or message.from_user.first_name or "Користувач"
    await state.set_state(MedicationStates.waiting_for_time)

    await message.answer(
        f"Привіт, {user_name}! 👋\n\n"
        "Я бот для нагадування про прийом ліків.\n"
        "Будь ласка, введіть бажаний час прийому ліків у форматі <b>ГГ:ХХ</b>\n"
        "(наприклад: <code>08:30</code>, <code>14:00</code> або <code>21:45</code>):",
        parse_mode="HTML"
    )


@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    """Скасування поточного введення."""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Наразі немає активного процесу для скасування.")
        return

    await state.clear()
    await message.answer("Дію скасовано. Щоб встановити час знову, надішліть /start.")


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    """Перевірка поточного збереженого часу в базі даних."""
    user_id = message.from_user.id
    schedule = await database.async_get_user_schedule(user_id)
    if schedule:
        await message.answer(
            f"📋 Ваш поточний збережений час прийому: <b>{schedule['med_time']}</b>\n"
            f"Ім'я: {schedule['user_name']}\n\n"
            "Щоб змінити його, надішліть команду /start.",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "У вас ще не встановлено час прийому ліків.\n"
            "Надішліть команду /start, щоб задати час."
        )


@dp.message(MedicationStates.waiting_for_time, F.text)
async def process_medication_time(message: types.Message, state: FSMContext):
    """
    Обробляє введений час від користувача:
    валідує формат ГГ:ХХ та зберігає в базу даних MySQL.
    """
    input_text = message.text.strip()

    # Перевірка валідності формату ГГ:ХХ
    if not TIME_REGEX.match(input_text):
        await message.answer(
            "⚠️ <b>Неправильний формат часу!</b>\n\n"
            "Будь ласка, введіть час у 24-годинному форматі <b>ГГ:ХХ</b> (від 00:00 до 23:59).\n"
            "Приклади: <code>08:00</code>, <code>12:30</code>, <code>20:15</code>.\n\n"
            "Спробуйте ще раз або введіть /cancel для скасування:",
            parse_mode="HTML"
        )
        return

    user_id = message.from_user.id
    user_name = message.from_user.full_name or message.from_user.first_name or f"id_{user_id}"

    try:
        # Зберігаємо в MySQL через aiomysql
        await database.async_save_medication_time(
            user_id=user_id,
            user_name=user_name,
            med_time=input_text
        )

        await state.clear()

        await message.answer(
            f"✅ <b>Успішно збережено!</b>\n\n"
            f"👤 Користувач: <b>{user_name}</b> (ID: <code>{user_id}</code>)\n"
            f"⏰ Час прийому ліків: <b>{input_text}</b>\n\n"
            "Тепер система перевірятиме цей час через API. "
            "Якщо захочете змінити час, просто введіть команду /start знову.",
            parse_mode="HTML"
        )
        logger.info(f"Збережено розклад: user_id={user_id}, name='{user_name}', time='{input_text}'")

    except Exception as e:
        logger.error(f"Помилка при збереженні в базу даних: {e}", exc_info=True)
        await message.answer(
            "❌ <b>Помилка під час збереження даних.</b>\n"
            "Перевірте підключення до бази даних MySQL або зверніться до адміністратора.",
            parse_mode="HTML"
        )


async def main():
    """Запуск Telegram-бота."""
    if not config.BOT_TOKEN or config.BOT_TOKEN == "your_telegram_bot_token_here":
        logger.error(
            "ПОМИЛКА: Не вказано BOT_TOKEN у файлі .env!\n"
            "Отримайте токен у Telegram через @BotFather та додайте його в .env"
        )
        return

    # Ініціалізація бази даних перед запуском
    database.init_db()

    bot = Bot(token=config.BOT_TOKEN)
    logger.info("Запуск Telegram-бота (aiogram 3.x)...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
