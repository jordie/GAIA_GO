-- Task Worklog Migration
-- Adds tables for tracking time and work entries on tasks

-- Table for worklog entries
CREATE TABLE IF NOT EXISTS task_worklog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    description TEXT,
    time_spent_minutes INTEGER NOT NULL,
    work_date DATE NOT NULL,
    work_type TEXT DEFAULT 'general',
    billable BOOLEAN DEFAULT 1,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES task_queue(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_worklog_task ON task_worklog(task_id);
CREATE INDEX IF NOT EXISTS idx_worklog_user ON task_worklog(user_id);
CREATE INDEX IF NOT EXISTS idx_worklog_date ON task_worklog(work_date);
CREATE INDEX IF NOT EXISTS idx_worklog_type ON task_worklog(work_type);

-- Table for active timers
CREATE TABLE IF NOT EXISTS task_timers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    description TEXT,
    work_type TEXT DEFAULT 'general',
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES task_queue(id) ON DELETE CASCADE
);

-- Indexes for timers
CREATE INDEX IF NOT EXISTS idx_timers_user ON task_timers(user_id);
CREATE INDEX IF NOT EXISTS idx_timers_active ON task_timers(user_id, end_time) WHERE end_time IS NULL;
