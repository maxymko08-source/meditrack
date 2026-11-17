# MediTrack — єдиний пакет застосунку

Встановлення та запуск описані у [кореневому README](../README.md).
Усі команди виконуються з кореня репозиторію:

```powershell
.venv\Scripts\python.exe -m meditrack init
.venv\Scripts\python.exe -m meditrack run
```

Не запускайте старі незалежні `api.py` чи `bot.py` із цього каталогу.
Конфігурація читає лише кореневий `.env`; `meditrack/.env` є застарілим
і збережений для явного перенесення старих даних.

- [Архітектура і протокол](../docs/ARCHITECTURE.md)
- [Міграція MySQL](../docs/MIGRATION.md)
- [Керування й відновлення](../docs/OPERATION.md)
- [CAD і друк](3d_model/README_3D_PRINTING.md)
- [ESP32](../firmware/README.md)

Робоча схема SQLite — `schema.sql`. Основні модулі `api`, `bot`, `database`,
`config`, `notifications` використовують відносні імпорти пакета.
Старі вихідні тексти збережені в `../legacy/`.
