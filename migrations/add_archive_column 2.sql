-- Add archive column to tasks and errors tables
-- This allows hiding completed/resolved items without deleting them

-- Add archived column to task_queue
ALTER TABLE task_queue ADD COLUMN archived INTEGER DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_task_queue_archived ON task_queue(archived);

-- Add archived column to errors
ALTER TABLE errors ADD COLUMN archived INTEGER DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_errors_archived ON errors(archived);

-- Add archived_at timestamp
ALTER TABLE task_queue ADD COLUMN archived_at TIMESTAMP;
ALTER TABLE errors ADD COLUMN archived_at TIMESTAMP;
