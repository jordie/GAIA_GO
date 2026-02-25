-- Notification Rules Migration
-- Adds tables for configurable notification rules

-- Table for notification rules
CREATE TABLE IF NOT EXISTS notification_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    channels TEXT NOT NULL,
    user_id TEXT,
    project_id INTEGER,
    conditions TEXT,
    frequency TEXT DEFAULT 'immediate',
    enabled BOOLEAN DEFAULT 1,
    quiet_hours_start TEXT,
    quiet_hours_end TEXT,
    description TEXT,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- Indexes for notification rules
CREATE INDEX IF NOT EXISTS idx_notif_rules_event ON notification_rules(event_type);
CREATE INDEX IF NOT EXISTS idx_notif_rules_user ON notification_rules(user_id);
CREATE INDEX IF NOT EXISTS idx_notif_rules_project ON notification_rules(project_id);
CREATE INDEX IF NOT EXISTS idx_notif_rules_enabled ON notification_rules(enabled);

-- Table for notification queue
CREATE TABLE IF NOT EXISTS notification_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER,
    event_type TEXT NOT NULL,
    event_data TEXT,
    channels TEXT NOT NULL,
    user_id TEXT,
    status TEXT DEFAULT 'pending',
    sent_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rule_id) REFERENCES notification_rules(id) ON DELETE SET NULL
);

-- Indexes for notification queue
CREATE INDEX IF NOT EXISTS idx_notif_queue_status ON notification_queue(status);
CREATE INDEX IF NOT EXISTS idx_notif_queue_user ON notification_queue(user_id);

-- Table for notification delivery log
CREATE TABLE IF NOT EXISTS notification_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_id INTEGER,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (notification_id) REFERENCES notification_queue(id) ON DELETE CASCADE
);

-- Indexes for notification log
CREATE INDEX IF NOT EXISTS idx_notif_log_notification ON notification_log(notification_id);
CREATE INDEX IF NOT EXISTS idx_notif_log_channel ON notification_log(channel);
