-- Add task archive table for old completed/failed tasks
-- Created: 2026-01-31

-- Task archive table - stores archived tasks from task_queue
CREATE TABLE IF NOT EXISTS task_archive (
    id INTEGER PRIMARY KEY,
    original_id INTEGER NOT NULL,
    task_type TEXT NOT NULL,
    task_data TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    assigned_node TEXT,
    assigned_worker TEXT,
    retries INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    timeout_seconds INTEGER,
    error_message TEXT,
    created_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_task_archive_type ON task_archive(task_type);
CREATE INDEX IF NOT EXISTS idx_task_archive_status ON task_archive(status);
CREATE INDEX IF NOT EXISTS idx_task_archive_completed ON task_archive(completed_at);
CREATE INDEX IF NOT EXISTS idx_task_archive_archived ON task_archive(archived_at);
CREATE INDEX IF NOT EXISTS idx_task_archive_original ON task_archive(original_id);
