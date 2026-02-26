-- Migration 020: Task Due Dates and Reminders
-- Adds due date tracking and reminder functionality for tasks

-- Add due_date column to task_queue if not exists
ALTER TABLE task_queue ADD COLUMN due_date TIMESTAMP;
ALTER TABLE task_queue ADD COLUMN reminder_sent INTEGER DEFAULT 0;

-- Add due_date to task_archive for historical tracking
ALTER TABLE task_archive ADD COLUMN due_date TIMESTAMP;

-- Create index for due date queries
CREATE INDEX IF NOT EXISTS idx_task_queue_due_date ON task_queue(due_date);
CREATE INDEX IF NOT EXISTS idx_task_queue_due_pending ON task_queue(due_date, status) WHERE status IN ('pending', 'in_progress');

-- Task reminder settings table
CREATE TABLE IF NOT EXISTS task_reminder_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    reminder_enabled INTEGER DEFAULT 1,
    remind_days_before INTEGER DEFAULT 1,
    remind_hours_before INTEGER DEFAULT 24,
    remind_on_due_day INTEGER DEFAULT 1,
    remind_when_overdue INTEGER DEFAULT 1,
    email_notifications INTEGER DEFAULT 0,
    in_app_notifications INTEGER DEFAULT 1,
    slack_notifications INTEGER DEFAULT 0,
    quiet_hours_start TEXT,
    quiet_hours_end TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id)
);

-- Task reminders log table
CREATE TABLE IF NOT EXISTS task_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    user_id TEXT,
    reminder_type TEXT NOT NULL,  -- 'due_soon', 'due_today', 'overdue'
    reminder_method TEXT NOT NULL,  -- 'in_app', 'email', 'slack', 'webhook'
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES task_queue(id)
);

CREATE INDEX IF NOT EXISTS idx_task_reminders_task ON task_reminders(task_id);
CREATE INDEX IF NOT EXISTS idx_task_reminders_user ON task_reminders(user_id);
CREATE INDEX IF NOT EXISTS idx_task_reminders_type ON task_reminders(reminder_type);
