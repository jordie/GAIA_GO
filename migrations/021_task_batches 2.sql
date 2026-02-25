-- Task Batches Migration
-- Adds table for tracking batch-created tasks

-- Table for task batches
CREATE TABLE IF NOT EXISTS task_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL UNIQUE,
    name TEXT,
    description TEXT,
    template_id INTEGER,
    total_tasks INTEGER DEFAULT 0,
    created_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',  -- pending, created, partial, failed, cancelled, completed
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (template_id) REFERENCES task_templates(id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_task_batches_batch_id ON task_batches(batch_id);
CREATE INDEX IF NOT EXISTS idx_task_batches_template ON task_batches(template_id);
CREATE INDEX IF NOT EXISTS idx_task_batches_status ON task_batches(status);
CREATE INDEX IF NOT EXISTS idx_task_batches_created_by ON task_batches(created_by);
