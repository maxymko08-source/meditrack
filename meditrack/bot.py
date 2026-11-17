"""Telegram commands; all access is scoped to the sender's private chat."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from html import escape
import logging
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import Message

from .config import Settings, load
from .database import Store

logger = logging.getLogger(__name__)
KYIV = ZoneInfo("Europe/Kyiv")

HELP = """<b>MediTrack — вісім підготовлених доз</b>
/devices — мої пристрої
/schedules ПРИСТРІЙ — щоденні розклади
/add ПРИСТРІЙ ГГ:ХХ НАЗВА — додати розклад
/edit ID ГГ:ХХ НАЗВА — змінити розклад
/cancel ID — скасувати розклад
/status ПРИСТРІЙ — комірки та стан механізму
/events ПРИСТРІЙ — останні події
/service ПРИСТРІЙ — зупинити видачу, запросити повернення
/plan ПРИСТРІЙ — план завантаження наступних восьми доз
/refill ПРИСТРІЙ ID_ПЛАНУ — підтвердити завантаження

Час: <b>Europe/Kyiv</b>. Одна комірка — одна вручну відміряна доза.
Перед зміною завантаженого плану виконайте /service. Видаліть усі дози,
підтвердьте EMPTY у Serial Monitor та дочекайтеся повернення на 0°.
Потім змініть розклади, викличте /plan, завантажте за планом і /refill.
Завершення команди сервопривода не підтверджує потрапляння дози в лоток."""

STATE_NAMES = {
    "maintenance": "обслуговування", "awaiting_refill": "очікує завантаження",
    "ready": "готовий", "locked": "заблоковано: потрібна перевірка",
    "exhausted": "усі комірки використано", "empty": "порожня",
    "loaded": "завантажена", "reserved": "зарезервована",
    "planned": "заплановано", "pending": "очікує", "issued": "команду отримано",
    "command_completed": "рух завершено; дозу в лотку не перевірено",
    "uncertain": "фізичний результат невідомий", "not_started": "рух не розпочато",
    "missed": "час пропущено", "homed": "повернення завершено",
    "consumed": "використана", "cancelled": "скасовано",
    "spent": "використана", "none": "не потрібне", "sending": "надсилається",
    "sent": "Telegram прийняв повідомлення", "failed": "помилка сповіщення",
}


def safe(value) -> str:
    return escape(str(value), quote=True)


def state_name(value) -> str:
    return safe(STATE_NAMES.get(value, value))


def local_time(value) -> str:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc).astimezone(KYIV).strftime("%d.%m.%Y %H:%M %z")
    return safe(value or "—")


def render_slots(slots: list[dict]) -> str:
    lines = []
    for slot in slots:
        number = slot.get("compartment", slot.get("number", "?"))
        due = slot.get("scheduled_at", slot.get("scheduled_local"))
        label = safe(slot.get("label", ""))
        state = state_name(slot.get("state", "planned"))
        lines.append(f"{safe(number)}: {local_time(due)} — {label} ({state})")
    return "\n".join(lines) or "Комірки порожні."


def positive_id(text: str) -> int:
    if not text.isascii() or not text.isdecimal() or not 0 < int(text) <= 2**63 - 1:
        raise ValueError("ID має бути додатним цілим числом.")
    return int(text)


class CommandService:
    """Synchronous command layer, also exercised without a Telegram network."""

    def __init__(self, store: Store):
        self.store = store

    def execute(self, owner: int, text: str, name: str = "") -> str:
        if not isinstance(text, str) or len(text) > 1200:
            raise ValueError("Надішліть коротку текстову команду.")
        words = text.strip().split()
        if not words:
            return HELP
        command = words[0].split("@", 1)[0].lower()
        args = words[1:]
        if command in {"/start", "/help"}:
            return f"Вітаємо, {safe(name)}!\n\n" + HELP
        if command == "/devices" and not args:
            rows = self.store.list_devices(owner)
            return "Ваші пристрої:\n" + ("\n".join(
                f"<code>{safe(r['id'])}</code>: {state_name(r['mode'])}" for r in rows
            ) or "Немає. Власника пристрою задає адміністратор у конфігурації.")
        if command == "/schedules" and len(args) == 1:
            rows = self.store.schedules(owner, args[0])
            return "Щоденні розклади (Europe/Kyiv):\n" + ("\n".join(
                f"ID {safe(r['id'])}: {safe(r['time'])} — {safe(r['label'])}"
                + ("" if r.get("enabled", True) else " [скасований]") for r in rows
            ) or "Розкладів немає.")
        if command == "/add" and len(args) >= 3:
            sid = self.store.add_schedule(owner, args[0], args[1], " ".join(args[2:]))
            return f"Щоденний розклад збережено. ID: {safe(sid)}. Отримайте новий план через /plan."
        if command == "/edit" and len(args) >= 3:
            self.store.update_schedule(owner, positive_id(args[0]), args[1], " ".join(args[2:]))
            return "Розклад змінено. Отримайте новий план через /plan."
        if command == "/cancel" and len(args) == 1:
            self.store.cancel_schedule(owner, positive_id(args[0]))
            return "Щоденний розклад скасовано. Отримайте новий план через /plan."
        if command == "/status" and len(args) == 1:
            info = self.store.status(owner, args[0])
            return (f"Пристрій {safe(args[0])}: {state_name(info['mode'])}\n"
                    f"Позиція: {safe(info['position'])}; цикл: {safe(info['cycle_id'])}\n"
                    + render_slots(info.get("compartments", [])))
        if command == "/events" and len(args) == 1:
            rows = self.store.events(owner, args[0])[:10]
            return "Останні події:\n" + ("\n".join(
                f"<code>{safe(r['id'])}</code>\n"
                f"{local_time(r.get('scheduled_at'))}, комірка {safe(r.get('compartment', '—'))}: "
                f"{state_name(r['state'])}; сповіщення: {state_name(r.get('notification_status', 'pending'))}"
                for r in rows) or "Подій немає.")
        if command == "/service" and len(args) == 1:
            self.store.request_home(owner, args[0])
            return ("Запит обслуговування збережено. Видачу зупинено.\n"
                    "Видаліть усі дози з комірок і каналу. Після огляду введіть EMPTY у Serial Monitor. "
                    "Дочекайтеся повернення на 0° та стану «очікує завантаження». "
                    "Тільки потім викликайте /plan.")
        if command == "/plan" and len(args) == 1:
            plan = self.store.prepare_refill(owner, args[0])
            return ("<b>План ручного завантаження</b>\n" + render_slots(plan["slots"])
                    + f"\n\nЗавантажте відповідні дози в комірки 1–8, закрийте кришку.\n"
                    f"Після цього: <code>/refill {safe(args[0])} {safe(plan['plan_id'])}</code>\n"
                    "Якщо план прострочився, отримайте новий /plan і перевірте вміст усіх комірок.")
        if command == "/refill" and len(args) == 2:
            result = self.store.refill(owner, args[0], args[1])
            if result.get("already_registered"):
                return "Цей план уже зареєстрований. Повторної зміни комірок немає; поточний стан: /status " + safe(args[0])
            return ("Завантаження восьми доз зареєстровано, послідовну видачу дозволено. "
                    "Після перезапуску ESP32 огляньте позицію та виконайте процедуру ALIGN із інструкції.")
        return "Невідома команда або неправильні аргументи.\n\n" + HELP


def message_pages(text: str, limit: int = 3500) -> list[str]:
    """Split on complete lines, preserving the HTML generated by this module."""
    pages, current = [], ""
    for line in text.splitlines():
        if len(current) + len(line) + 1 > limit and current:
            pages.append(current)
            current = ""
        current += line + "\n"
    if current:
        pages.append(current.rstrip())
    return pages


def build_router(store: Store) -> Router:
    router = Router()
    service = CommandService(store)

    @router.message(F.text)
    async def handle(message: Message) -> None:
        if message.chat.type != "private" or message.from_user is None or message.from_user.is_bot:
            await message.answer("Особисті розклади доступні лише в приватному чаті з ботом.")
            return
        try:
            result = await asyncio.to_thread(service.execute, message.from_user.id,
                                            message.text, message.from_user.full_name)
        except (ValueError, PermissionError, LookupError) as exc:
            result = safe(exc)
        except Exception:
            logger.exception("Помилка обробки команди Telegram")
            result = "Не вдалося виконати команду. Перевірте стан сервера та повторіть запит."
        for page in message_pages(result):
            await message.answer(page, parse_mode="HTML")

    @router.message()
    async def non_text(message: Message) -> None:
        await message.answer("Надішліть текстову команду /help.")

    return router


async def main(settings: Settings | None = None, store: Store | None = None) -> None:
    settings = settings or load()
    if not settings.bot_token or settings.bot_token == "your_telegram_bot_token_here":
        raise ValueError("У кореневому .env потрібно задати BOT_TOKEN.")
    if store is None:
        store = Store(settings.database_path, late_seconds=settings.late_seconds)
        store.initialize()
    dispatcher = Dispatcher()
    dispatcher.include_router(build_router(store))
    async with Bot(settings.bot_token, session=AiohttpSession(timeout=35)) as bot:
        await dispatcher.start_polling(bot, polling_timeout=20, allowed_updates=["message"])


if __name__ == "__main__":
    asyncio.run(main())
