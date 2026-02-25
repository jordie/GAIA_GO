-- Task Conversions Migration
-- Adds table for tracking task type conversions

-- Table for conversion history
CREATE TABLE IF NOT EXISTS task_conversions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    converted_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for conversion history
CREATE INDEX IF NOT EXISTS idx_conversions_source ON task_conversions(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_conversions_target ON task_conversions(target_type, target_id);
