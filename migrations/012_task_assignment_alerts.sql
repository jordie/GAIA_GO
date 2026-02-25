-- Migration: Add task assignment alerts
-- Enables real-time notifications when tasks are assigned to users/workers

-- Task assignment alerts table
CREATE TABLE IF NOT EXISTS task_assignment_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    task_type TEXT NOT NULL,
    task_title TEXT,
    assigned_to TEXT NOT NULL,
    assigned_by TEXT,
    priority TEXT DEFAULT 'normal',
    message TEXT,
    read_at TIMESTAMP,
    dismissed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES task_queue(id) ON DELETE CASCADE
);

-- User alert preferences
CREATE TABLE IF NOT EXISTS user_alert_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL UNIQUE,
    notify_on_assignment BOOLEAN DEFAULT 1,
    notify_on_completion BOOLEAN DEFAULT 1,
    notify_on_error BOOLEAN DEFAULT 1,
    sound_enabled BOOLEAN DEFAULT 1,
    desktop_notifications BOOLEAN DEFAULT 1,
    email_notifications BOOLEAN DEFAULT 0,
    quiet_hours_start TEXT,
    quiet_hours_end TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_task_assignment_alerts_to ON task_assignment_alerts(assigned_to);
CREATE INDEX IF NOT EXISTS idx_task_assignment_alerts_read ON task_assignment_alerts(read_at);
CREATE INDEX IF NOT EXISTS idx_task_assignment_alerts_task ON task_assignment_alerts(task_id);
CREATE INDEX IF NOT EXISTS idx_user_alert_preferences_user ON user_alert_preferences(user_id);
