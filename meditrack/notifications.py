"""Durable Telegram outbox, separate from physical execution.

A timeout after Telegram accepted a message can cause a duplicate notification;
Telegram sendMessage has no idempotency key. It cannot cause a second movement.
"""
import logging
import threading
import requests

logger = logging.getLogger(__name__)


def deliver_one(store, token, session=None):
    if not token:
        return False
    now = store.now()
    with store.connection(True) as conn:
        row = conn.execute("""SELECT * FROM notifications WHERE
            (state IN ('pending','failed') AND next_attempt<=?) OR
            (state='sending' AND lease_until<=?) ORDER BY next_attempt,event_id LIMIT 1""", (now, now)).fetchone()
        if not row:
            return False
        # The monotonically increasing attempt number is also the fencing token:
        # a suspended worker cannot overwrite a later worker after its lease expires.
        attempt = row["attempts"] + 1
        conn.execute("UPDATE notifications SET state='sending',lease_until=?,attempts=attempts+1 WHERE event_id=?",
                     (now+120, row["event_id"]))
    own_session = session is None
    session = session or requests.Session()
    error = None
    try:
        response = session.post(f"https://api.telegram.org/bot{token}/sendMessage",
                                json={"chat_id": row["owner"], "text": row["text"], "parse_mode": "HTML"},
                                timeout=(5, 15))
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            error = "TelegramRejected"
    except (requests.RequestException, ValueError) as exc:
        # Exception strings can contain the secret URL; never persist or log it.
        error = type(exc).__name__
    finally:
        if own_session:
            session.close()
    with store.connection(True) as conn:
        if error:
            delay = min(3600, 30 * 2 ** min(row["attempts"], 7))
            changed = conn.execute("""UPDATE notifications SET state='failed',error=?,next_attempt=?,lease_until=NULL
                WHERE event_id=? AND state='sending' AND attempts=?""",
                (error, store.now()+delay, row["event_id"], attempt)).rowcount
            if changed:
                logger.warning("Повідомлення ще не доставлено: %s", error)
        else:
            conn.execute("""UPDATE notifications SET state='sent',sent_at=?,error=NULL,lease_until=NULL
                WHERE event_id=? AND state='sending' AND attempts=?""",
                (store.now(), row["event_id"], attempt))
    return True


def run_worker(store, token, stop=None):
    stop = stop or threading.Event()
    while not stop.is_set():
        try:
            if deliver_one(store, token):
                continue
        except Exception as exc:
            logger.error("Працівник сповіщень: %s", type(exc).__name__)
        stop.wait(5)
