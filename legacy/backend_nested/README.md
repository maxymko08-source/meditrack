# ============================================================
#  MediTrack — README.md
#  Розумний диспенсер таблеток — бекенд
# ============================================================

# MediTrack Backend 💊

**Університетський IoT-проєкт.** Серверна частина для розумного диспенсера таблеток на базі ESP8266.

## Структура проєкту

```
meditrack/
├── .env.example        # Шаблон змінних середовища
├── .env                # Ваш .env (не комітити в Git!)
├── requirements.txt    # Python залежності
├── schema.sql          # DDL-скрипт для MySQL
├── config.py           # Конфігурація (зчитує з .env)
├── database.py         # Рівень доступу до БД (async + sync)
├── bot.py              # Telegram-бот (aiogram 3.x)
└── api.py              # Flask REST API для плати ESP8266
```

## Стек технологій

| Компонент | Технологія |
|---|---|
| Мова | Python 3.10+ |
| Telegram-бот | aiogram 3.x |
| База даних | MySQL 8+ |
| Async DB driver | aiomysql |
| Sync DB driver | PyMySQL |
| Web API | Flask |
| Конфігурація | python-dotenv |

---

## Швидкий старт

### 1. Клонування та встановлення залежностей

```bash
git clone <your-repo-url>
cd meditrack
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Налаштування бази даних

Виконайте SQL-скрипт для створення схеми:

```bash
mysql -u root -p < schema.sql
```

Або вручну у MySQL:
```sql
SOURCE /path/to/schema.sql;
```

### 3. Налаштування .env

```bash
cp .env.example .env
# Відредагуйте .env та вкажіть реальні значення
```

Обов'язкові змінні:
- `BOT_TOKEN` — токен бота від [@BotFather](https://t.me/BotFather)
- `DB_USER` — ім'я користувача MySQL
- `DB_PASSWORD` — пароль MySQL

### 4. Запуск Telegram-бота

```bash
python bot.py
```

### 5. Запуск Flask API

**Для розробки:**
```bash
python api.py
```

**Для продакшну (gunicorn):**
```bash
gunicorn --bind 0.0.0.0:5000 api:app
```

> **Примітка:** Бот та API — незалежні процеси. Запускайте їх у двох окремих терміналах або через systemd/supervisor.

---

## API Reference для ESP8266

### `GET /api/check`

Плата викликає цей ендпоінт кожну хвилину.

**Відповідь — час видачі:**
```json
{"status": "DISPENSE", "schedule_id": 42}
```

**Відповідь — нічого видавати:**
```json
{"status": "WAIT"}
```

---

### `POST /api/confirm`

Плата підтверджує видачу таблетки.

**Тіло запиту:**
```json
{"schedule_id": 42}
```

**Успішна відповідь:**
```json
{"ok": true, "message": "Dispensed and user notified."}
```

---

## Arduino/ESP8266 — приклад коду

```cpp
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h>

const char* ssid     = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* serverBase = "http://YOUR_SERVER_IP:5000";

void checkAndDispense() {
  WiFiClient client;
  HTTPClient http;

  // --- GET /api/check ---
  http.begin(client, String(serverBase) + "/api/check");
  int httpCode = http.GET();

  if (httpCode == 200) {
    String payload = http.getString();
    StaticJsonDocument<256> doc;
    deserializeJson(doc, payload);

    if (String((const char*)doc["status"]) == "DISPENSE") {
      int scheduleId = doc["schedule_id"];

      // TODO: фізично повернути мотор / відкрити відсік

      // --- POST /api/confirm ---
      http.begin(client, String(serverBase) + "/api/confirm");
      http.addHeader("Content-Type", "application/json");
      String body = "{\"schedule_id\":" + String(scheduleId) + "}";
      http.POST(body);
    }
  }
  http.end();
}
```

---

## Безпека

- Ніколи не комітьте `.env` у Git. Додайте його до `.gitignore`.
- У продакшні розмістіть API за реверс-проксі (nginx) з HTTPS.
- Розгляньте додавання API-ключа для автентифікації запитів від ESP8266.
