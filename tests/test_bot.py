import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from meditrack.bot import CommandService, message_pages
from meditrack.database import Store, StoreError


class BotWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "bot.sqlite3",
                           clock=lambda: datetime(2026, 11, 17, 5, 0, tzinfo=timezone.utc))
        self.store.initialize()
        self.store.register_device("demo", 123, "s" * 40)
        self.commands = CommandService(self.store)

    def test_personal_access_and_html_escaping(self):
        greeting = self.commands.execute(123, "/start", "<b>A&B</b>")
        self.assertIn("&lt;b&gt;A&amp;B&lt;/b&gt;", greeting)
        self.commands.execute(123, "/add demo 08:00 <dose>&")
        listing = self.commands.execute(123, "/schedules demo")
        self.assertIn("08:00", listing)
        self.assertIn("&lt;dose&gt;&amp;", listing)
        with self.assertRaises(StoreError):
            self.commands.execute(456, "/schedules demo")
        with self.assertRaises(StoreError):
            self.commands.execute(456, "/cancel 1")
        self.assertNotIn("demo", self.commands.execute(456, "/devices"))

    def test_complete_loading_and_edit_interlock(self):
        self.commands.execute(123, "/add demo 08:00 Ранкова доза")
        self.commands.execute(123, "/service demo")
        home = self.store.poll("demo")
        self.store.confirm("demo", home["event_id"], "homed")
        plan_text = self.commands.execute(123, "/plan demo")
        self.assertIn("1:", plan_text)
        self.assertIn("8:", plan_text)
        with self.store.connection() as conn:
            plan = conn.execute("SELECT id FROM refill_plans WHERE state='prepared'").fetchone()[0]
        result = self.commands.execute(123, f"/refill demo {plan}")
        self.assertIn("восьми доз", result)
        self.assertIn("уже зареєстрований", self.commands.execute(123, f"/refill demo {plan}"))
        with self.assertRaises(StoreError):
            self.commands.execute(123, "/edit 1 09:00 Інша доза")
        with self.assertRaises(StoreError):
            self.commands.execute(123, "/cancel 1")
        self.assertIn("готовий", self.commands.execute(123, "/status demo"))

    def test_cancel_edit_and_validation(self):
        self.commands.execute(123, "/add demo 08:00 Доза")
        self.commands.execute(123, "/edit 1 09:00 Змінена")
        self.assertIn("09:00", self.commands.execute(123, "/schedules demo"))
        self.commands.execute(123, "/cancel 1")
        self.assertIn("скасований", self.commands.execute(123, "/schedules demo"))
        for invalid in ("/cancel 0", "/cancel -1", "/cancel 1.0", "/add demo 24:00 Доза"):
            with self.subTest(command=invalid), self.assertRaises(ValueError):
                self.commands.execute(123, invalid)

    def test_long_listing_pages_keep_tags_intact(self):
        text = "\n".join(f"ID {n}: <code>08:00</code> &lt;назва&gt;" for n in range(200))
        pages = message_pages(text)
        self.assertGreater(len(pages), 1)
        for page in pages:
            self.assertLessEqual(len(page), 3500)
            self.assertEqual(page.count("<code>"), page.count("</code>"))


if __name__ == "__main__":
    unittest.main()
