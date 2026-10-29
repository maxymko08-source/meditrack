import unittest
import asyncio
from datetime import datetime
import config
import database
import server
import bot


class TestMedicationSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ініціалізація бази даних
        database.init_db()

    def setUp(self):
        # Очищуємо таблицю перед кожним тестом
        conn = database.get_sync_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM medication_schedules")
        conn.close()

    def test_time_regex_validation(self):
        """Тестування регулярного виразу для валідації часу ГГ:ХХ."""
        valid_times = ["00:00", "08:30", "12:00", "19:45", "23:59"]
        invalid_times = ["24:00", "25:10", "12:60", "8:30", "abc", "12-30", "12:5", ""]

        for t in valid_times:
            self.assertIsNotNone(bot.TIME_REGEX.match(t), f"Час '{t}' мав бути валідним")

        for t in invalid_times:
            self.assertIsNone(bot.TIME_REGEX.match(t), f"Час '{t}' мав бути невалідним")

    def test_database_async_save_and_sync_check(self):
        """Тестування збереження через aiomysql та перевірки через pymysql."""
        async def run_async_test():
            # 1. Зберігаємо запис користувача
            success = await database.async_save_medication_time(
                user_id=987654321,
                user_name="Олександр",
                med_time="10:15"
            )
            self.assertTrue(success)

            # 2. Перевіряємо отримання даних
            record = await database.async_get_user_schedule(987654321)
            self.assertIsNotNone(record)
            self.assertEqual(record["med_time"], "10:15")
            self.assertEqual(record["user_name"], "Олександр")

            # 3. Оновлення часу для того ж користувача
            await database.async_save_medication_time(
                user_id=987654321,
                user_name="Олександр Новий",
                med_time="11:30"
            )
            updated_record = await database.async_get_user_schedule(987654321)
            self.assertEqual(updated_record["med_time"], "11:30")

        asyncio.run(run_async_test())

        # 4. Перевірка синхронною функцією (використовуваною у Flask)
        self.assertTrue(database.check_schedule_time("11:30"))
        self.assertFalse(database.check_schedule_time("10:15"))
        self.assertFalse(database.check_schedule_time("22:00"))

    def test_flask_api_check_endpoint(self):
        """Тестування ендпоінту /api/check у Flask."""
        client = server.app.test_client()

        # База порожня -> очікуємо WAIT
        resp = client.get("/api/check?time=09:00")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"status": "WAIT"})

        # Додаємо запис у базу на 09:00
        asyncio.run(database.async_save_medication_time(111, "Тест", "09:00"))

        # Перевіряємо збіг -> очікуємо DISPENSE
        resp_match = client.get("/api/check?time=09:00")
        self.assertEqual(resp_match.status_code, 200)
        self.assertEqual(resp_match.get_json(), {"status": "DISPENSE"})

        # Інший час -> очікуємо WAIT
        resp_no_match = client.get("/api/check?time=09:01")
        self.assertEqual(resp_no_match.status_code, 200)
        self.assertEqual(resp_no_match.get_json(), {"status": "WAIT"})

    def test_flask_schedules_list(self):
        """Тестування ендпоінту списку розкладів /api/schedules."""
        client = server.app.test_client()

        asyncio.run(database.async_save_medication_time(101, "Іван", "08:00"))
        asyncio.run(database.async_save_medication_time(102, "Марія", "20:00"))

        resp = client.get("/api/schedules")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["count"], 2)


if __name__ == "__main__":
    unittest.main()
