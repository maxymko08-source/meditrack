"""Every test uses a fresh TemporaryDirectory; never loads .env or MySQL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch
import requests

from meditrack.api import create_app
from meditrack.config import Settings
from meditrack.database import Store, StoreError, occurrence, validate_time
from meditrack.migrate import import_snapshot
from meditrack.notifications import deliver_one

UTC = timezone.utc


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="meditrack-test-")
        self.addCleanup(self.directory.cleanup)
        self.current = datetime(2026, 11, 17, 6, 50, tzinfo=UTC)
        self.store = Store(Path(self.directory.name) / "test.sqlite3", clock=lambda: self.current)
        self.store.initialize()
        self.store.register_device("device-a", 101, "a"*40)
        self.store.register_device("device-b", 202, "b"*40)
        self.app = create_app(Settings(database_path=self.store.path), self.store)
        self.client = self.app.test_client()
        self.headers = {"X-Device-ID": "device-a", "Authorization": "Bearer " + "a"*40}

    def home(self):
        home = self.store.request_home(101, "device-a")
        self.store.confirm("device-a", home["event_id"], "homed")
        return home

    def load(self, hhmm="09:00", label="доза"):
        self.home()
        schedule_id = self.store.add_schedule(101, "device-a", hhmm, label)
        plan = self.store.prepare_refill(101, "device-a")
        self.store.refill(101, "device-a", plan["plan_id"])
        return schedule_id, plan

    def due(self, plan, slot=0):
        self.current = datetime.fromtimestamp(plan["slots"][slot]["scheduled_at"], UTC)

    def test_normal_daily_event_and_truthful_receipt(self):
        schedule, plan = self.load()
        self.due(plan)
        event = self.client.get("/api/check", headers=self.headers).get_json()
        self.assertEqual((event["status"], event["compartment"], event["angle"]), ("DISPENSE", 1, 20))
        reply = self.client.post("/api/confirm", headers=self.headers, json={"event_id": event["event_id"], "outcome": "command_completed"}).get_json()
        self.assertEqual(reply["state"], "command_completed")
        self.assertEqual(reply["notification_status"], "pending")
        self.assertEqual(self.store.schedules(101, "device-a")[0]["enabled"], 1)
        self.assertEqual(self.store.status(101, "device-a")["position"], 1)

    def test_poll_before_scheduled_time_is_wait(self):
        _, plan = self.load()
        self.due(plan)
        self.current -= timedelta(seconds=1)
        self.assertEqual(self.store.poll("device-a")["status"], "WAIT")

    def test_repeated_polling_returns_one_event(self):
        _, plan = self.load()
        self.due(plan)
        first = self.store.poll("device-a")
        for _ in range(10):
            self.assertEqual(self.store.poll("device-a"), first)

    def test_concurrent_retrieval_returns_one_claim(self):
        _, plan = self.load()
        self.due(plan)
        with ThreadPoolExecutor(max_workers=8) as executor:
            commands = list(executor.map(lambda _: self.store.poll("device-a"), range(32)))
        self.assertEqual(len({r["event_id"] for r in commands}), 1)
        with self.store.connection() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM events WHERE state='issued'").fetchone()[0], 1)

    def test_duplicate_confirmation_returns_known_result(self):
        _, plan = self.load()
        self.due(plan)
        event = self.store.poll("device-a")
        first = self.store.confirm("device-a", event["event_id"], "command_completed")
        second = self.store.confirm("device-a", event["event_id"], "uncertain")
        self.assertEqual(first, second)
        self.assertEqual(self.store.status(101, "device-a")["position"], 1)

    def test_concurrent_confirmation_does_not_advance_twice(self):
        _, plan = self.load()
        self.due(plan)
        event = self.store.poll("device-a")
        with ThreadPoolExecutor(max_workers=4) as executor:
            receipts = list(executor.map(lambda _: self.store.confirm("device-a", event["event_id"], "command_completed"), range(12)))
        self.assertTrue(all(r["state"] == "command_completed" for r in receipts))
        self.assertEqual(self.store.status(101, "device-a")["position"], 1)

    def test_backend_restart_preserves_issued_and_receipt(self):
        _, plan = self.load()
        self.due(plan)
        event = self.store.poll("device-a")
        restarted = Store(self.store.path, clock=lambda: self.current)
        restarted.initialize()
        self.assertEqual(restarted.poll("device-a"), event)
        result = restarted.confirm("device-a", event["event_id"], "command_completed")
        self.assertEqual(Store(self.store.path).confirm("device-a", event["event_id"], "command_completed"), result)

    def test_backend_unavailability_has_no_dispense_command(self):
        with patch.object(self.store, "poll", side_effect=sqlite3.OperationalError("offline")):
            response = self.client.get("/api/check", headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("status", response.get_json())

    def test_authentication_and_owner_isolation(self):
        self.assertEqual(self.client.get("/api/check").status_code, 401)
        wrong = {**self.headers, "X-Device-ID": "device-b"}
        self.assertEqual(self.client.get("/api/check", headers=wrong).status_code, 401)
        with self.assertRaises(StoreError):
            self.store.status(202, "device-a")
        schedule, _ = self.load()
        with self.assertRaises(StoreError):
            self.store.cancel_schedule(202, schedule)
        self.assertEqual(len(self.store.list_devices(202)), 1)

    def test_cross_device_confirmation_forbidden(self):
        _, plan = self.load()
        self.due(plan)
        event = self.store.poll("device-a")
        with self.assertRaises(StoreError) as error:
            self.store.confirm("device-b", event["event_id"], "command_completed")
        self.assertEqual(error.exception.status, 404)

    def test_input_validation(self):
        for hhmm in ["9:00", "24:00", "12:60", "00:00\n", "９:００"]:
            with self.assertRaises(StoreError):
                validate_time(hhmm)
        for body in [[], {}, {"event_id": 42, "outcome": "homed"}, {"event_id": "x", "outcome": []}]:
            response = self.client.post("/api/confirm", headers=self.headers, json=body)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/api/check?time=09:00", headers=self.headers).status_code, 400)

    def test_midnight_uses_previous_dates_event(self):
        self.current = datetime(2026, 11, 16, 21, 0, tzinfo=UTC)
        _, plan = self.load("23:59")
        self.due(plan)
        self.current += timedelta(minutes=2)
        event = self.store.poll("device-a")
        self.assertEqual(event["scheduled_local"], "2026-11-16T23:59")
        self.assertEqual(event["status"], "DISPENSE")

    def test_lateness_inclusive_boundary(self):
        _, plan = self.load()
        self.due(plan)
        self.current += timedelta(seconds=300)
        self.assertEqual(self.store.poll("device-a")["status"], "DISPENSE")

    def test_missed_event_locks_without_consuming_compartment(self):
        _, plan = self.load()
        self.due(plan)
        self.current += timedelta(seconds=301)
        result = self.store.poll("device-a")
        self.assertEqual((result["status"], result["mode"], result["position"]), ("WAIT", "locked", 0))
        self.assertEqual(self.store.status(101, "device-a")["compartments"][0]["state"], "loaded")
        self.assertIn("missed", [e["state"] for e in self.store.events(101, "device-a")])

    def test_expired_issued_event_still_has_original_identity(self):
        _, plan = self.load()
        self.due(plan)
        event = self.store.poll("device-a")
        self.current += timedelta(hours=1)
        self.assertEqual(self.store.poll("device-a"), event)
        self.store.confirm("device-a", event["event_id"], "not_started")
        self.assertEqual(self.store.poll("device-a")["mode"], "locked")

    def test_dst_gap_skipped_and_overlap_once(self):
        self.assertIsNone(occurrence(date(2026, 3, 29), "03:30"))
        fold = occurrence(date(2026, 10, 25), "03:30")
        self.assertEqual(datetime.fromtimestamp(fold, UTC), datetime(2026, 10, 25, 0, 30, tzinfo=UTC))
        self.current = datetime(2026, 3, 28, 23, 0, tzinfo=UTC)
        _, plan = self.load("03:30")
        self.assertEqual(plan["slots"][0]["scheduled_local"], "2026-03-30T03:30")

    def test_eight_compartments_then_supervised_next_cycle(self):
        _, plan = self.load()
        cycle = plan["cycle_id"]
        for i in range(8):
            self.due(plan, i)
            event = self.store.poll("device-a")
            self.assertEqual((event["compartment"], event["previous_compartment"], event["angle"]), (i+1, i, 20*(i+1)))
            self.store.confirm("device-a", event["event_id"], "command_completed")
            self.assertEqual(self.store.poll("device-a")["status"], "WAIT")
        self.assertEqual(self.store.status(101, "device-a")["mode"], "exhausted")
        home = self.store.request_home(101, "device-a")
        self.assertEqual(home["angle"], 0)
        self.assertNotEqual(home["cycle_id"], cycle)
        with self.assertRaises(StoreError):
            self.store.prepare_refill(101, "device-a")
        self.store.confirm("device-a", home["event_id"], "homed")
        next_plan = self.store.prepare_refill(101, "device-a")
        self.store.refill(101, "device-a", next_plan["plan_id"])
        self.due(next_plan)
        self.assertEqual(self.store.poll("device-a")["compartment"], 1)

    def test_uncertain_result_requires_maintenance(self):
        _, plan = self.load()
        self.due(plan)
        event = self.store.poll("device-a")
        self.store.confirm("device-a", event["event_id"], "uncertain")
        status = self.store.status(101, "device-a")
        self.assertEqual(status["mode"], "locked")
        self.assertEqual(status["compartments"][0]["state"], "uncertain")
        self.assertEqual(self.store.poll("device-a")["status"], "WAIT")

    def test_service_never_clears_unconfirmed_movement(self):
        _, plan = self.load()
        self.due(plan)
        self.store.poll("device-a")
        with self.assertRaises(StoreError):
            self.store.request_home(101, "device-a")

    def test_refill_is_bound_to_plan_and_idempotent(self):
        self.home()
        self.store.add_schedule(101, "device-a", "09:00")
        first = self.store.prepare_refill(101, "device-a")
        second = self.store.prepare_refill(101, "device-a")
        with self.assertRaises(StoreError):
            self.store.refill(101, "device-a", first["plan_id"])
        self.assertFalse(self.store.refill(101, "device-a", second["plan_id"])["already_registered"])
        self.assertTrue(self.store.refill(101, "device-a", second["plan_id"])["already_registered"])

    def test_expired_loading_plan_is_not_armed(self):
        self.home()
        self.store.add_schedule(101, "device-a", "09:00")
        plan = self.store.prepare_refill(101, "device-a")
        self.due(plan)
        with self.assertRaises(StoreError):
            self.store.refill(101, "device-a", plan["plan_id"])
        self.assertEqual(self.store.status(101, "device-a")["mode"], "awaiting_refill")

    def test_service_reload_retains_unissued_dates(self):
        _, plan = self.load()
        self.home()
        new_plan = self.store.prepare_refill(101, "device-a")
        self.assertEqual(new_plan["slots"], plan["slots"])
        self.store.refill(101, "device-a", new_plan["plan_id"])

    def test_schedule_changes_require_unloaded_state(self):
        schedule, plan = self.load()
        with self.assertRaises(StoreError):
            self.store.update_schedule(101, schedule, "10:00")
        self.home()
        self.store.update_schedule(101, schedule, "10:00", "нова доза")
        self.assertEqual(self.store.schedules(101, "device-a")[0]["time"], "10:00")
        self.store.cancel_schedule(101, schedule)
        self.assertEqual(self.store.schedules(101, "device-a")[0]["enabled"], 0)

    def test_telegram_failure_does_not_change_execution(self):
        _, plan = self.load(label="<unsafe>&")
        self.due(plan)
        event = self.store.poll("device-a")
        self.store.confirm("device-a", event["event_id"], "command_completed")
        # Isolate one outbox record: the home message is unrelated to this test.
        with self.store.connection(True) as conn:
            conn.execute("UPDATE notifications SET state='sent' WHERE event_id!=?", (event["event_id"],))
        failed = Mock()
        failed.post.side_effect = requests.Timeout("must-not-persist-token")
        self.assertTrue(deliver_one(self.store, "fake-token", failed))
        result = self.store.confirm("device-a", event["event_id"], "command_completed")
        self.assertEqual((result["state"], result["notification_status"]), ("command_completed", "failed"))
        with self.store.connection() as conn:
            message = conn.execute("SELECT * FROM notifications WHERE event_id=?", (event["event_id"],)).fetchone()
            self.assertIn("&lt;unsafe&gt;&amp;", message["text"])
            self.assertEqual(message["error"], "Timeout")
        self.current += timedelta(minutes=1)
        success = Mock()
        success.post.return_value.json.return_value = {"ok": True, "result": {"message_id": 1}}
        self.assertTrue(deliver_one(self.store, "fake-token", success))
        self.assertEqual(self.store.confirm("device-a", event["event_id"], "command_completed")["notification_status"], "sent")
        self.assertEqual(success.post.call_args.kwargs["timeout"], (5, 15))

    def test_telegram_reject_is_not_reported_as_delivered(self):
        home = self.home()
        session = Mock()
        session.post.return_value.json.return_value = {"ok": False, "description": "rejected"}
        self.assertTrue(deliver_one(self.store, "fake-token", session))
        receipt = self.store.confirm("device-a", home["event_id"], "homed")
        self.assertEqual(receipt["notification_status"], "failed")

    def test_notification_claim_is_atomic(self):
        self.home()
        session = Mock()
        session.post.return_value.json.return_value = {"ok": True}
        with ThreadPoolExecutor(max_workers=4) as executor:
            result = list(executor.map(lambda _: deliver_one(self.store, "fake-token", session), range(8)))
        self.assertEqual(sum(result), 1)
        self.assertEqual(session.post.call_count, 1)

    def test_expired_notification_worker_cannot_overwrite_newer_success(self):
        home = self.home()
        late_session = Mock()
        current_session = Mock()
        current_session.post.return_value.json.return_value = {"ok": True}

        def delayed_post(*args, **kwargs):
            self.current += timedelta(seconds=121)
            self.assertTrue(deliver_one(self.store, "fake-token", current_session))
            raise requests.Timeout("old worker woke after newer success")

        late_session.post.side_effect = delayed_post
        self.assertTrue(deliver_one(self.store, "fake-token", late_session))
        with self.store.connection() as conn:
            row = conn.execute("SELECT state,attempts,error FROM notifications WHERE event_id=?", (home["event_id"],)).fetchone()
        self.assertEqual(tuple(row), ("sent", 2, None))

    def test_migration_archives_root_rows_and_is_idempotent(self):
        snapshot = {"format_version": 1, "layout": "root", "source": "fixture:root", "tables": {"medication_schedules": [
            {"user_id": 101, "user_name": "Олена", "med_time": "08:30", "updated_at": "2026-01-01"},
            {"user_id": 999, "user_name": "Без пристрою", "med_time": "09:00"}]}}
        result = import_snapshot(self.store, snapshot, {"101": "device-a"})
        self.assertTrue(Path(result["backup"]).exists())
        self.assertEqual((result["archived"], result["imported_disabled"], result["unmapped_preserved"]), (2, 1, 1))
        self.assertEqual(self.store.schedules(101, "device-a")[0]["enabled"], 0)
        again = import_snapshot(self.store, snapshot, {"101": "device-a"})
        self.assertEqual((again["archived"], again["imported_disabled"]), (0, 0))
        with self.store.connection() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM legacy_records").fetchone()[0], 2)

    def test_nested_migration_keeps_legacy_status_without_fabricating_events(self):
        snapshot = {"format_version": 1, "layout": "nested", "source": "fixture:nested", "tables": {
            "users": [{"id": 1, "telegram_id": 101, "name": "Олена"}],
            "schedules": [{"id": 2, "user_id": 1, "dispense_time": "8:30:00", "status": "dispensed"}]}}
        import_snapshot(self.store, snapshot, {"101": "device-a"})
        self.assertEqual(self.store.schedules(101, "device-a")[0]["time"], "08:30")
        self.assertEqual(self.store.events(101, "device-a"), [])
        with self.store.connection() as conn:
            row = conn.execute("SELECT payload FROM legacy_records WHERE source_key='schedules:2'").fetchone()
            self.assertEqual(json.loads(row[0])["status"], "dispensed")


if __name__ == "__main__":
    unittest.main()
