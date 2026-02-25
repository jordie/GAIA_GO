-- Migration: Add notification system for service failures
-- Supports logging and optional webhook notifications

-- Notification settings table (webhook URLs, channels, etc.)
CREATE TABLE IF NOT EXISTS notification_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,           -- Setting name (e.g., 'slack_webhook', 'discord_webhook')
    category TEXT NOT NULL,              -- 'webhook', 'email', 'log', 'socket'
    config TEXT NOT NULL,                -- JSON config (url, headers, template, etc.)
    enabled INTEGER DEFAULT 1,
    notify_on TEXT DEFAULT 'all',        -- 'all', 'critical', 'error', 'warning'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Notification log table (history of sent notifications)
CREATE TABLE IF NOT EXISTS notification_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_type TEXT NOT NULL,     -- 'service_failure', 'worker_down', 'health_alert', 'error'
    severity TEXT DEFAULT 'error',       -- 'critical', 'error', 'warning', 'info'
    title TEXT NOT NULL,
    message TEXT,
    source TEXT,                         -- Service/worker that generated the notification
    metadata TEXT,                       -- JSON with additional context
    channels_notified TEXT,              -- JSON array of channels that were notified
    webhook_responses TEXT,              -- JSON with webhook response data
    acknowledged INTEGER DEFAULT 0,
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_notification_log_type ON notification_log(notification_type);
CREATE INDEX IF NOT EXISTS idx_notification_log_severity ON notification_log(severity);
CREATE INDEX IF NOT EXISTS idx_notification_log_source ON notification_log(source);
CREATE INDEX IF NOT EXISTS idx_notification_log_acknowledged ON notification_log(acknowledged);
CREATE INDEX IF NOT EXISTS idx_notification_log_created ON notification_log(created_at);
CREATE INDEX IF NOT EXISTS idx_notification_settings_category ON notification_settings(category);
CREATE INDEX IF NOT EXISTS idx_notification_settings_enabled ON notification_settings(enabled);

-- Insert default settings
INSERT OR IGNORE INTO notification_settings (name, category, config, enabled, notify_on) VALUES
    ('file_log', 'log', '{"path": "/tmp/architect_notifications.log", "format": "json"}', 1, 'all'),
    ('database_log', 'log', '{"table": "notification_log"}', 1, 'all'),
    ('websocket_broadcast', 'socket', '{"room": "notifications", "event": "service_alert"}', 1, 'all');
