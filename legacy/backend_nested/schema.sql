-- ============================================================
--  MediTrack — DDL-скрипт для MySQL
--  Опис: Схема бази даних для розумного диспенсера таблеток
-- ============================================================

CREATE DATABASE IF NOT EXISTS meditrack
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE meditrack;

-- ------------------------------------------------------------
-- Таблиця: users
-- Зберігає зареєстрованих через Telegram-бот користувачів
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id          INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    telegram_id BIGINT          NOT NULL UNIQUE COMMENT 'Унікальний Telegram user_id',
    name        VARCHAR(255)    NOT NULL            COMMENT 'Ім\'я або username користувача',
    created_at  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_telegram_id (telegram_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Таблиця: schedules
-- Зберігає розклад прийому ліків для кожного користувача
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schedules (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    user_id         INT UNSIGNED    NOT NULL COMMENT 'Зовнішній ключ на users.id',
    dispense_time   TIME            NOT NULL COMMENT 'Час видачі у форматі HH:MM:SS',
    status          ENUM('pending', 'dispensed')
                                    NOT NULL DEFAULT 'pending'
                                    COMMENT 'pending = очікує, dispensed = видано',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_user_id   (user_id),
    INDEX idx_status    (status),
    INDEX idx_dispense_time (dispense_time),
    CONSTRAINT fk_schedules_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
