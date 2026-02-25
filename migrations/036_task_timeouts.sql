-- Add task timeout configuration per task type
-- Created: 2026-01-31

-- Add timeout_seconds column to task_queue
-- This allows per-task timeout configuration based on task type
ALTER TABLE task_queue ADD COLUMN timeout_seconds INTEGER;

-- Create index for efficient stuck task queries
CREATE INDEX IF NOT EXISTS idx_task_queue_status_started ON task_queue(status, started_at);

-- Create task_timeout_config table for persistent timeout settings
CREATE TABLE IF NOT EXISTS task_timeout_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT UNIQUE NOT NULL,
    timeout_seconds INTEGER NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT
);

-- Insert default timeout configurations
INSERT OR IGNORE INTO task_timeout_config (task_type, timeout_seconds, description) VALUES
    ('shell', 300, 'Shell commands - 5 minutes'),
    ('python', 600, 'Python scripts - 10 minutes'),
    ('git', 180, 'Git operations - 3 minutes'),
    ('deploy', 1800, 'Deployments - 30 minutes'),
    ('test', 900, 'Test runs - 15 minutes'),
    ('build', 1200, 'Build tasks - 20 minutes'),
    ('tmux', 60, 'tmux operations - 1 minute'),
    ('claude_task', 3600, 'Claude AI tasks - 60 minutes'),
    ('web_crawl', 300, 'Web crawling - 5 minutes'),
    ('error_fix', 1800, 'Auto error fixes - 30 minutes'),
    ('maintenance', 600, 'Maintenance tasks - 10 minutes'),
    ('default', 600, 'Default timeout - 10 minutes');
