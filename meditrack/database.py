"""Transactional SQLite store. Every connection is bounded and always closed.

The refill plan binds actual doses to dated events. A missed/uncertain dose locks
the sequence: advancing to a later schedule would dispense the wrong contents.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, date, time, timedelta, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo
import hmac
import json
import re
import sqlite3

KYIV = ZoneInfo("Europe/Kyiv")
UTC = timezone.utc
TIME_PATTERN = re.compile(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]\Z")
DEVICE_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
TERMINAL = {"command_completed", "uncertain", "not_started", "homed", "missed", "cancelled"}


class StoreError(ValueError):
    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.status = status


def validate_time(value):
    if not isinstance(value, str) or not TIME_PATTERN.fullmatch(value):
        raise StoreError("Час має бути у форматі ГГ:ХХ (00:00–23:59).", 400)
    return value


def validate_uuid(value):
    if not isinstance(value, str):
        raise StoreError("Некоректний ідентифікатор події.", 400)
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except ValueError:
        raise StoreError("Некоректний ідентифікатор події.", 400) from None
    return value


def occurrence(day: date, hhmm: str):
    """Fall overlap: first occurrence only. Spring gap: skip nonexistent time."""
    local = datetime.combine(day, time.fromisoformat(hhmm), KYIV).replace(fold=0)
    utc = local.astimezone(UTC)
    if utc.astimezone(KYIV).replace(tzinfo=None) != local.replace(tzinfo=None):
        return None
    return int(utc.timestamp())


class Store:
    def __init__(self, path, *, clock=None, late_seconds=300):
        self.path = str(path)
        self.clock = clock or (lambda: datetime.now(UTC))
        self.late_seconds = late_seconds

    def now(self):
        value = self.clock()
        if value.tzinfo is None:
            raise ValueError("Clock must return timezone-aware datetime")
        return int(value.timestamp())

    @contextmanager
    def connection(self, write=False):
        conn = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            if write:
                conn.execute("BEGIN IMMEDIATE")
            yield conn
            if write:
                conn.commit()
        except Exception:
            if write:
                conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise RuntimeError("Непідтримувана версія БД; потрібна явна міграція.")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))

    def register_device(self, device_id, owner, secret):
        if not isinstance(device_id, str) or not DEVICE_PATTERN.fullmatch(device_id):
            raise StoreError("Некоректний ідентифікатор пристрою.", 400)
        if type(owner) is not int or owner <= 0 or len(secret) < 32:
            raise StoreError("Вкажіть Telegram ID власника та DEVICE_SECRET довжиною щонайменше 32 символи.", 400)
        with self.connection(True) as conn:
            old = conn.execute("SELECT owner FROM devices WHERE id=?", (device_id,)).fetchone()
            if old and old["owner"] != owner:
                raise StoreError("Пристрій уже належить іншому власнику.")
            conn.execute("""INSERT INTO devices(id,owner,secret_hash,cycle_id,created_at)
                VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET secret_hash=excluded.secret_hash""",
                (device_id, owner, sha256(secret.encode()).hexdigest(), str(uuid4()), self.now()))
            conn.executemany("INSERT OR IGNORE INTO compartments(device_id,number,state) VALUES(?,?,'empty')",
                             [(device_id, i) for i in range(1, 9)])

    def authenticate(self, device_id, secret):
        if not isinstance(device_id, str) or not DEVICE_PATTERN.fullmatch(device_id):
            return False
        with self.connection() as conn:
            row = conn.execute("SELECT secret_hash FROM devices WHERE id=?", (device_id,)).fetchone()
        candidate = sha256(secret.encode()).hexdigest()
        return bool(row and hmac.compare_digest(row[0], candidate))

    @staticmethod
    def _device(conn, device_id, owner=None):
        row = conn.execute("SELECT * FROM devices WHERE id=?", (device_id,)).fetchone()
        if not row or (owner is not None and row["owner"] != owner):
            raise StoreError("Пристрій не знайдено або доступ відсутній.", 404)
        return row

    def list_devices(self, owner):
        with self.connection() as conn:
            return [dict(r) for r in conn.execute("SELECT id,mode,position,cycle_id FROM devices WHERE owner=? ORDER BY id", (owner,))]

    def schedules(self, owner, device_id):
        with self.connection() as conn:
            self._device(conn, device_id, owner)
            return [dict(r) for r in conn.execute("SELECT id,time,label,enabled FROM schedules WHERE device_id=? ORDER BY time,id", (device_id,))]

    @staticmethod
    def _editable(conn, device):
        if device["mode"] not in ("maintenance", "awaiting_refill"):
            raise StoreError("Спочатку виконайте /service та спорожніть пристрій: завантажені дози прив'язані до розкладу.")
        conn.execute("UPDATE refill_plans SET state='cancelled' WHERE device_id=? AND state='prepared'", (device["id"],))

    def add_schedule(self, owner, device_id, hhmm, label=""):
        validate_time(hhmm)
        if not isinstance(label, str) or len(label) > 120:
            raise StoreError("Назва дози має містити до 120 символів.", 400)
        with self.connection(True) as conn:
            self._editable(conn, self._device(conn, device_id, owner))
            try:
                return conn.execute("INSERT INTO schedules(device_id,time,label,created_at) VALUES(?,?,?,?)",
                                    (device_id, hhmm, label, self.now())).lastrowid
            except sqlite3.IntegrityError:
                raise StoreError("На цей час уже є активний розклад.") from None

    def update_schedule(self, owner, schedule_id, hhmm, label=""):
        validate_time(hhmm)
        if type(schedule_id) is not int or schedule_id < 1 or not isinstance(label, str) or len(label) > 120:
            raise StoreError("Некоректний номер розкладу або назва.", 400)
        with self.connection(True) as conn:
            row = conn.execute("SELECT device_id FROM schedules WHERE id=?", (schedule_id,)).fetchone()
            if not row:
                raise StoreError("Розклад не знайдено.", 404)
            self._editable(conn, self._device(conn, row[0], owner))
            try:
                conn.execute("UPDATE schedules SET time=?,label=?,enabled=1 WHERE id=?", (hhmm, label, schedule_id))
            except sqlite3.IntegrityError:
                raise StoreError("На цей час уже є активний розклад.") from None

    def cancel_schedule(self, owner, schedule_id):
        if type(schedule_id) is not int or schedule_id < 1:
            raise StoreError("Некоректний номер розкладу.", 400)
        with self.connection(True) as conn:
            row = conn.execute("SELECT device_id FROM schedules WHERE id=?", (schedule_id,)).fetchone()
            if not row:
                raise StoreError("Розклад не знайдено.", 404)
            self._editable(conn, self._device(conn, row[0], owner))
            conn.execute("UPDATE schedules SET enabled=0 WHERE id=?", (schedule_id,))

    def request_home(self, owner, device_id):
        now = self.now()
        with self.connection(True) as conn:
            device = self._device(conn, device_id, owner)
            issued = conn.execute("SELECT * FROM events WHERE device_id=? AND state='issued'", (device_id,)).fetchone()
            if issued:
                if issued["kind"] == "home":
                    return self._command(issued)
                raise StoreError("Є непідтверджена команда. Підключіть ESP32 та отримайте її результат; автоматичне повернення заборонене.")
            conn.execute("UPDATE events SET state='cancelled' WHERE device_id=? AND state='pending'", (device_id,))
            conn.execute("UPDATE refill_plans SET state='cancelled' WHERE device_id=? AND state='prepared'", (device_id,))
            conn.execute("UPDATE devices SET mode='maintenance' WHERE id=?", (device_id,))
            event_id, cycle_id = str(uuid4()), str(uuid4())
            # HOME is never executed without the local EMPTY confirmation.
            conn.execute("""INSERT INTO events(id,device_id,kind,scheduled_local,scheduled_at,expires_at,cycle_id,state,created_at)
                VALUES(?,?,'home',?,?,?,?, 'issued',?)""",
                (event_id, device_id, datetime.fromtimestamp(now, KYIV).isoformat(), now, now + 86400, cycle_id, now))
            return self._command(conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone())

    def prepare_refill(self, owner, device_id):
        now = self.now()
        with self.connection(True) as conn:
            device = self._device(conn, device_id, owner)
            if device["mode"] != "awaiting_refill":
                raise StoreError("Спочатку /service, фізичне спорожнення й локальна команда EMPTY на ESP32.")
            rows = conn.execute("SELECT * FROM schedules WHERE device_id=? AND enabled=1 ORDER BY time,id", (device_id,)).fetchall()
            if not rows:
                raise StoreError("Спочатку додайте хоча б один щоденний розклад.")
            slots = []
            first_day = datetime.fromtimestamp(now, KYIV).date()
            for offset in range(16):
                day = first_day + timedelta(days=offset)
                for schedule in rows:
                    stamp = occurrence(day, schedule["time"])
                    local_key = f"{day.isoformat()}T{schedule['time']}"
                    if stamp is None or stamp < now + 30:
                        continue
                    if conn.execute("SELECT 1 FROM events WHERE schedule_id=? AND scheduled_local=? AND state!='cancelled'", (schedule["id"], local_key)).fetchone():
                        continue
                    slots.append({"compartment": len(slots)+1, "schedule_id": schedule["id"],
                                  "scheduled_local": local_key, "scheduled_at": stamp,
                                  "label": schedule["label"], "angle": 20*(len(slots)+1)})
                    if len(slots) == 8:
                        break
                if len(slots) == 8:
                    break
            if len(slots) != 8:
                raise StoreError("Не вдалося сформувати вісім майбутніх доз.")
            conn.execute("UPDATE refill_plans SET state='cancelled' WHERE device_id=? AND state='prepared'", (device_id,))
            plan_id = str(uuid4())
            conn.execute("INSERT INTO refill_plans VALUES(?,?,?,?, 'prepared',?)",
                         (plan_id, device_id, device["cycle_id"], json.dumps(slots, ensure_ascii=False), now))
            return {"plan_id": plan_id, "cycle_id": device["cycle_id"], "slots": slots}

    def refill(self, owner, device_id, plan_id):
        validate_uuid(plan_id)
        now = self.now()
        with self.connection(True) as conn:
            device = self._device(conn, device_id, owner)
            plan = conn.execute("SELECT * FROM refill_plans WHERE id=? AND device_id=?", (plan_id, device_id)).fetchone()
            if plan and plan["state"] == "used" and plan["cycle_id"] == device["cycle_id"]:
                return {"plan_id": plan_id, "slots": json.loads(plan["slots_json"]), "already_registered": True}
            if device["mode"] != "awaiting_refill" or not plan or plan["state"] != "prepared" or plan["cycle_id"] != device["cycle_id"]:
                raise StoreError("План недійсний. Виконайте /plan після повернення Home.")
            slots = json.loads(plan["slots_json"])
            if any(s["scheduled_at"] < now+30 for s in slots):
                raise StoreError("Час першої дози надто близько або минув. Зніміть дози, створіть новий /plan і завантажте за ним.")
            for slot in slots:
                event_id = str(uuid4())
                conn.execute("""INSERT INTO events(id,device_id,schedule_id,kind,scheduled_local,scheduled_at,expires_at,
                    cycle_id,compartment,state,label,created_at) VALUES(?,?,?,'dispense',?,?,?,?,?,'pending',?,?)""",
                    (event_id, device_id, slot["schedule_id"], slot["scheduled_local"], slot["scheduled_at"],
                     slot["scheduled_at"] + self.late_seconds, device["cycle_id"], slot["compartment"], slot["label"], now))
                conn.execute("UPDATE compartments SET state='loaded',event_id=? WHERE device_id=? AND number=?",
                             (event_id, device_id, slot["compartment"]))
            conn.execute("UPDATE devices SET mode='ready' WHERE id=?", (device_id,))
            conn.execute("UPDATE refill_plans SET state='used' WHERE id=?", (plan_id,))
            return {"plan_id": plan_id, "slots": slots, "already_registered": False}

    @staticmethod
    def _command(row):
        return {"status": "HOME" if row["kind"] == "home" else "DISPENSE", "event_id": row["id"],
                "cycle_id": row["cycle_id"], "compartment": row["compartment"] or 0,
                "previous_compartment": (row["compartment"]-1) if row["compartment"] else 0,
                "angle": 20*(row["compartment"] or 0), "expires_at": row["expires_at"],
                "scheduled_at": row["scheduled_at"], "scheduled_local": row["scheduled_local"]}

    def poll(self, device_id):
        now = self.now()
        with self.connection(True) as conn:
            device = self._device(conn, device_id)
            active = conn.execute("SELECT * FROM events WHERE device_id=? AND state='issued'", (device_id,)).fetchone()
            if active:
                # A receipt may be lost after physical movement. Never replace this event.
                return self._command(active)
            if device["mode"] == "ready":
                event = conn.execute("SELECT * FROM events WHERE device_id=? AND cycle_id=? AND compartment=? AND state='pending'",
                                     (device_id, device["cycle_id"], device["position"]+1)).fetchone()
                if event and now >= event["scheduled_at"]:
                    if now > event["expires_at"]:
                        conn.execute("UPDATE events SET state='missed',confirmed_at=? WHERE id=?", (now, event["id"]))
                        conn.execute("UPDATE devices SET mode='locked' WHERE id=?", (device_id,))
                        self._enqueue(conn, event, device["owner"], "missed", now)
                        device = self._device(conn, device_id)
                    else:
                        conn.execute("UPDATE events SET state='issued' WHERE id=?", (event["id"],))
                        conn.execute("UPDATE compartments SET state='reserved' WHERE device_id=? AND number=?", (device_id, event["compartment"]))
                        return self._command(event)
            return {"status": "WAIT", "mode": device["mode"], "position": device["position"],
                    "cycle_id": device["cycle_id"]}

    @staticmethod
    def _enqueue(conn, event, owner, outcome, now):
        descriptions = {
            "command_completed": "Команду сервоприводу завершено. Наявність дози в лотку не підтверджена датчиком; перевірте лоток.",
            "uncertain": "Фізичний результат невідомий. Видачу заблоковано; потрібен огляд і спорожнення перед Home.",
            "not_started": "Команда не починалась. Видачу заблоковано; перевірте пристрій і план завантаження.",
            "missed": "Дозволені 5 хвилин запізнення минули. Дозу не запускали; видачу заблоковано до обслуговування.",
            "homed": "Home підтверджено після локальної перевірки порожніх комірок. Створіть /plan перед завантаженням.",
        }
        text = f"MediTrack · {escape(event['device_id'])}\n{descriptions[outcome]}\nПодія: {event['id']}"
        if event["compartment"]:
            text += f"\nКомірка {event['compartment']} · {escape(event['label'])} · {event['scheduled_local']} (Europe/Kyiv)"
        conn.execute("INSERT OR IGNORE INTO notifications(event_id,owner,text,next_attempt) VALUES(?,?,?,?)",
                     (event["id"], owner, text, now))

    def confirm(self, device_id, event_id, outcome):
        validate_uuid(event_id)
        if outcome not in {"command_completed", "uncertain", "not_started", "homed"}:
            raise StoreError("Непідтримуваний результат команди.", 400)
        now = self.now()
        with self.connection(True) as conn:
            device = self._device(conn, device_id)
            event = conn.execute("SELECT * FROM events WHERE id=? AND device_id=?", (event_id, device_id)).fetchone()
            if not event:
                raise StoreError("Подію не знайдено.", 404)
            if event["state"] in TERMINAL:
                return self._receipt(conn, event)
            if event["state"] != "issued":
                raise StoreError("Цю подію ще не видано пристрою.")
            if (event["kind"] == "home" and outcome == "command_completed") or (event["kind"] == "dispense" and outcome == "homed"):
                raise StoreError("Результат не відповідає типу команди.", 400)
            conn.execute("UPDATE events SET state=?,confirmed_at=? WHERE id=?", (outcome, now, event_id))
            if outcome == "command_completed":
                if event["cycle_id"] != device["cycle_id"] or event["compartment"] != device["position"]+1:
                    raise StoreError("Порушена послідовність механізму.")
                conn.execute("UPDATE compartments SET state='spent' WHERE device_id=? AND number=?", (device_id, event["compartment"]))
                conn.execute("UPDATE devices SET position=?,mode=? WHERE id=?",
                             (event["compartment"], "exhausted" if event["compartment"] == 8 else "ready", device_id))
            elif outcome == "homed":
                conn.execute("UPDATE devices SET position=0,mode='awaiting_refill',cycle_id=? WHERE id=?", (event["cycle_id"], device_id))
                conn.execute("UPDATE compartments SET state='empty',event_id=NULL WHERE device_id=?", (device_id,))
            else:
                conn.execute("UPDATE devices SET mode='locked' WHERE id=?", (device_id,))
                if event["compartment"]:
                    conn.execute("UPDATE compartments SET state=? WHERE device_id=? AND number=?",
                                 ("uncertain" if outcome == "uncertain" else "loaded", device_id, event["compartment"]))
            self._enqueue(conn, event, device["owner"], outcome, now)
            return self._receipt(conn, conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone())

    @staticmethod
    def _receipt(conn, event):
        notify = conn.execute("SELECT state FROM notifications WHERE event_id=?", (event["id"],)).fetchone()
        return {"ok": True, "event_id": event["id"], "state": event["state"],
                "cycle_id": event["cycle_id"], "compartment": event["compartment"] or 0,
                "notification_status": notify[0] if notify else "none"}

    def status(self, owner, device_id):
        with self.connection() as conn:
            device = dict(self._device(conn, device_id, owner))
            device.pop("secret_hash")
            device["compartments"] = [dict(r) for r in conn.execute("""SELECT c.number,c.state,c.event_id,
                e.scheduled_local,e.label FROM compartments c LEFT JOIN events e ON e.id=c.event_id
                WHERE c.device_id=? ORDER BY c.number""", (device_id,))]
            return device

    def events(self, owner, device_id):
        with self.connection() as conn:
            self._device(conn, device_id, owner)
            return [dict(r) for r in conn.execute("""SELECT e.*,COALESCE(n.state,'none') AS notification_status
                FROM events e LEFT JOIN notifications n ON n.event_id=e.id WHERE e.device_id=?
                ORDER BY e.created_at DESC,e.scheduled_at DESC LIMIT 100""", (device_id,))]
