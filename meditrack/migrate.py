"""Explicit, non-destructive migration of either legacy MySQL layout.

Export uses a read-only transaction. Import archives every original row, imports
only explicitly mapped owners, and keeps imported schedules disabled for review.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
from .database import Store, StoreError, validate_time


def export_mysql(env_path, layout, output):
    import pymysql
    from dotenv import dotenv_values
    config = dotenv_values(env_path)
    source_db = config.get("DB_NAME", "medication_db" if layout == "root" else "meditrack")
    conn = pymysql.connect(host=config.get("DB_HOST", "127.0.0.1"), port=int(config.get("DB_PORT", "3306")),
                           user=config.get("DB_USER"), password=config.get("DB_PASSWORD", ""), database=source_db,
                           charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
                           connect_timeout=5, read_timeout=15, write_timeout=15)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
            tables = ["medication_schedules"] if layout == "root" else ["users", "schedules"]
            rows = {}
            for table in tables:
                # Names are constants, never supplied SQL identifiers.
                cursor.execute(f"SELECT * FROM `{table}`")
                rows[table] = cursor.fetchall()
        conn.rollback()
    finally:
        conn.close()
    payload = {"format_version": 1, "layout": layout, "source": f"{layout}:{source_db}", "tables": rows}
    # Exclusive creation prevents accidental overwrite of a previous export.
    with Path(output).open("x", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2, default=str)
    return {table: len(records) for table, records in rows.items()}


def backup_database(store):
    target = Path(store.path).with_name(Path(store.path).name + f".before-migration-{uuid4().hex[:8]}.bak")
    with store.connection() as source:
        dest = sqlite3.connect(target)
        try:
            source.backup(dest)
        finally:
            dest.close()
    return str(target)


def import_snapshot(store, snapshot, mapping):
    if snapshot.get("format_version") != 1 or snapshot.get("layout") not in {"root", "nested"}:
        raise StoreError("Непідтримуваний формат знімка.", 400)
    source = snapshot.get("source")
    if not isinstance(source, str) or not source:
        raise StoreError("У знімку відсутнє джерело.", 400)
    tables = snapshot["tables"]
    layout = snapshot["layout"]
    expected = {"medication_schedules"} if layout == "root" else {"users", "schedules"}
    if set(tables) != expected or not all(isinstance(rows, list) for rows in tables.values()):
        raise StoreError("Некоректні таблиці знімка.", 400)
    store.initialize()
    backup = backup_database(store)
    archived = imported = unmapped = 0
    now = store.now()
    with store.connection(True) as conn:
        # Archive all rows, including unmapped users and historical status values.
        for table, rows in tables.items():
            for row in rows:
                key = str(row["user_id"] if table == "medication_schedules" else row["id"])
                payload = json.dumps(row, ensure_ascii=False, sort_keys=True)
                old = conn.execute("SELECT payload FROM legacy_records WHERE source=? AND source_key=?", (source, f"{table}:{key}")).fetchone()
                if old and old[0] != payload:
                    raise StoreError("Рядок джерела змінився після імпорту. Збережіть новий знімок з іншим полем source; старий архів не перезаписано.")
                result = conn.execute("INSERT OR IGNORE INTO legacy_records VALUES(?,?,?,?)", (source, f"{table}:{key}", payload, now))
                archived += result.rowcount
        if layout == "root":
            records = [(r["user_id"], r["user_id"], r["med_time"]) for r in tables["medication_schedules"]]
        else:
            owners = {u["id"]: u["telegram_id"] for u in tables["users"]}
            records = [(r["id"], owners[r["user_id"]], str(r["dispense_time"])[:5]) for r in tables["schedules"]]
        for legacy_id, owner, hhmm in records:
            device_id = mapping.get(str(owner))
            if not device_id:
                unmapped += 1
                continue
            store._device(conn, device_id, int(owner))
            # MySQL TIME may serialize 8:30:00, normalize without losing minutes.
            pieces = str(hhmm).split(":")
            hhmm = f"{int(pieces[0]):02}:{int(pieces[1]):02}"
            validate_time(hhmm)
            legacy_key = f"{source}:schedule:{legacy_id}"
            result = conn.execute("""INSERT OR IGNORE INTO schedules(device_id,time,label,enabled,created_at,legacy_key)
                VALUES(?,?,?,0,?,?)""", (device_id, hhmm, "Імпортований розклад — перевірте дозу", now, legacy_key))
            imported += result.rowcount
    return {"backup": backup, "archived": archived, "imported_disabled": imported, "unmapped_preserved": unmapped}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Явна міграція старої MySQL БД без зміни джерела")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--legacy-env", required=True)
    export.add_argument("--layout", choices=["root", "nested"], required=True)
    export.add_argument("--output", required=True)
    migrate = commands.add_parser("import")
    migrate.add_argument("--snapshot", required=True)
    migrate.add_argument("--mapping", required=True, help="JSON: Telegram ID -> device ID")
    migrate.add_argument("--database", required=True)
    args = parser.parse_args(argv)
    if args.command == "export":
        result = export_mysql(args.legacy_env, args.layout, args.output)
    else:
        snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8-sig"))
        mapping = json.loads(Path(args.mapping).read_text(encoding="utf-8-sig"))
        result = import_snapshot(Store(args.database), snapshot, mapping)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
