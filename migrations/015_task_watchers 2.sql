-- Migration: Add task watchers/subscribers support
-- Allows users to subscribe to tasks and receive notifications on updates

-- Task watchers table
CREATE TABLE IF NOT EXISTS task_watchers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    task_type TEXT NOT NULL,  -- 'task_queue', 'feature', 'bug', 'milestone', 'devops_task'
    user_id TEXT NOT NULL,
    watch_type TEXT DEFAULT 'all',  -- 'all', 'status', 'comments', 'assignment'
    notify_email BOOLEAN DEFAULT 0,
    notify_dashboard BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id, task_type, user_id)
);

-- Watch events log - tracks what notifications were sent
CREATE TABLE IF NOT EXISTS watch_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watcher_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    task_type TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- 'status_change', 'comment_added', 'assigned', 'updated', 'completed'
    event_data TEXT,  -- JSON with event details
    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP,
    FOREIGN KEY (watcher_id) REFERENCES task_watchers(id) ON DELETE CASCADE
);

-- User watch preferences
CREATE TABLE IF NOT EXISTS watch_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL UNIQUE,
    auto_watch_created BOOLEAN DEFAULT 1,  -- Auto-watch tasks you create
    auto_watch_assigned BOOLEAN DEFAULT 1,  -- Auto-watch tasks assigned to you
    auto_watch_commented BOOLEAN DEFAULT 0,  -- Auto-watch tasks you comment on
    quiet_hours_start TEXT,  -- e.g., '22:00'
    quiet_hours_end TEXT,    -- e.g., '08:00'
    digest_frequency TEXT DEFAULT 'instant',  -- 'instant', 'hourly', 'daily', 'weekly'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_task_watchers_task ON task_watchers(task_id, task_type);
CREATE INDEX IF NOT EXISTS idx_task_watchers_user ON task_watchers(user_id);
CREATE INDEX IF NOT EXISTS idx_watch_events_watcher ON watch_events(watcher_id);
CREATE INDEX IF NOT EXISTS idx_watch_events_unread ON watch_events(watcher_id, read_at);
CREATE INDEX IF NOT EXISTS idx_watch_events_task ON watch_events(task_id, task_type);
