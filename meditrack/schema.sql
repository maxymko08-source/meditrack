-- SQLite 3. Один авторитетний DDL; MySQL залишається джерелом явної міграції.
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    owner INTEGER NOT NULL CHECK(owner > 0),
    secret_hash TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'maintenance' CHECK(mode IN ('maintenance','awaiting_refill','ready','exhausted','locked')),
    position INTEGER NOT NULL DEFAULT 0 CHECK(position BETWEEN 0 AND 8),
    cycle_id TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL REFERENCES devices(id),
    time TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
    created_at INTEGER NOT NULL,
    legacy_key TEXT UNIQUE
);
CREATE UNIQUE INDEX IF NOT EXISTS active_device_time ON schedules(device_id,time) WHERE enabled=1;
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL REFERENCES devices(id),
    schedule_id INTEGER REFERENCES schedules(id),
    kind TEXT NOT NULL CHECK(kind IN ('dispense','home')),
    scheduled_local TEXT NOT NULL,
    scheduled_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    cycle_id TEXT NOT NULL,
    compartment INTEGER CHECK(compartment BETWEEN 1 AND 8),
    state TEXT NOT NULL CHECK(state IN ('pending','issued','command_completed','uncertain','not_started','homed','missed','cancelled')),
    label TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL,
    confirmed_at INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS one_live_occurrence ON events(schedule_id,scheduled_local) WHERE state!='cancelled';
CREATE UNIQUE INDEX IF NOT EXISTS one_issued_per_device ON events(device_id) WHERE state='issued';
CREATE UNIQUE INDEX IF NOT EXISTS one_slot_per_cycle ON events(device_id,cycle_id,compartment) WHERE compartment IS NOT NULL;
CREATE TABLE IF NOT EXISTS compartments (
    device_id TEXT NOT NULL REFERENCES devices(id),
    number INTEGER NOT NULL CHECK(number BETWEEN 1 AND 8),
    state TEXT NOT NULL CHECK(state IN ('empty','loaded','reserved','spent','uncertain')),
    event_id TEXT REFERENCES events(id),
    PRIMARY KEY(device_id,number)
);
CREATE TABLE IF NOT EXISTS refill_plans (
    id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL REFERENCES devices(id),
    cycle_id TEXT NOT NULL,
    slots_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('prepared','used','cancelled')),
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    event_id TEXT PRIMARY KEY REFERENCES events(id),
    owner INTEGER NOT NULL,
    text TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','sending','sent','failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt INTEGER NOT NULL,
    lease_until INTEGER,
    error TEXT,
    sent_at INTEGER
);
CREATE TABLE IF NOT EXISTS legacy_records (
    source TEXT NOT NULL,
    source_key TEXT NOT NULL,
    payload TEXT NOT NULL,
    imported_at INTEGER NOT NULL,
    PRIMARY KEY(source,source_key)
);
PRAGMA user_version = 1;
