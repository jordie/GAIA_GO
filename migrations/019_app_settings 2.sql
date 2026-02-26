-- App Settings Migration
-- Adds tables for managing application-wide settings

-- Table for app-wide settings
CREATE TABLE IF NOT EXISTS app_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT,
    type TEXT DEFAULT 'string',  -- string, integer, boolean, float, json
    category TEXT DEFAULT 'general',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_app_settings_key ON app_settings(key);
CREATE INDEX IF NOT EXISTS idx_app_settings_category ON app_settings(category);

-- Table for settings change history (audit trail)
CREATE TABLE IF NOT EXISTS settings_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_by TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for history queries
CREATE INDEX IF NOT EXISTS idx_settings_history_key ON settings_history(key);
CREATE INDEX IF NOT EXISTS idx_settings_history_time ON settings_history(changed_at);

-- Trigger to automatically log settings changes
CREATE TRIGGER IF NOT EXISTS log_settings_change
AFTER UPDATE ON app_settings
BEGIN
    INSERT INTO settings_history (key, old_value, new_value, changed_by)
    VALUES (OLD.key, OLD.value, NEW.value, NEW.updated_by);
END;
