-- Task Effort Rollup Migration
-- Adds columns for storing rolled-up effort from subtasks

-- Add rollup columns to task_queue if they don't exist
ALTER TABLE task_queue ADD COLUMN rollup_estimated_hours REAL DEFAULT 0;
ALTER TABLE task_queue ADD COLUMN rollup_actual_hours REAL DEFAULT 0;
ALTER TABLE task_queue ADD COLUMN rollup_progress REAL DEFAULT 0;

-- Note: SQLite doesn't support IF NOT EXISTS for ALTER TABLE
-- These statements will fail silently if columns already exist
-- Run with appropriate error handling in migration script
