-- Migration 025: Task Hierarchy (Parent/Child Relationships)
-- Adds support for hierarchical task structures with subtasks

-- Add parent_id column to task_queue for parent-child relationships
ALTER TABLE task_queue ADD COLUMN parent_id INTEGER REFERENCES task_queue(id);

-- Add hierarchy level (depth from root, 0 = root task)
ALTER TABLE task_queue ADD COLUMN hierarchy_level INTEGER DEFAULT 0;

-- Add path for materialized path pattern (e.g., "/1/5/12/" for efficient ancestor queries)
ALTER TABLE task_queue ADD COLUMN hierarchy_path TEXT DEFAULT '/';

-- Add child count for quick access without subquery
ALTER TABLE task_queue ADD COLUMN child_count INTEGER DEFAULT 0;

-- Add completion requirements (all, any, percentage)
ALTER TABLE task_queue ADD COLUMN completion_requirement TEXT DEFAULT 'all';

-- Add same columns to task_archive for historical tracking
ALTER TABLE task_archive ADD COLUMN parent_id INTEGER;
ALTER TABLE task_archive ADD COLUMN hierarchy_level INTEGER DEFAULT 0;
ALTER TABLE task_archive ADD COLUMN hierarchy_path TEXT DEFAULT '/';

-- Create indexes for hierarchy queries
CREATE INDEX IF NOT EXISTS idx_task_queue_parent ON task_queue(parent_id);
CREATE INDEX IF NOT EXISTS idx_task_queue_hierarchy_path ON task_queue(hierarchy_path);
CREATE INDEX IF NOT EXISTS idx_task_queue_hierarchy_level ON task_queue(hierarchy_level);

-- Index for finding root tasks efficiently
CREATE INDEX IF NOT EXISTS idx_task_queue_root_tasks ON task_queue(parent_id) WHERE parent_id IS NULL;

-- Composite index for common hierarchy queries
CREATE INDEX IF NOT EXISTS idx_task_queue_parent_status ON task_queue(parent_id, status);

-- Task hierarchy settings table for configurable behavior
CREATE TABLE IF NOT EXISTS task_hierarchy_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_key TEXT NOT NULL UNIQUE,
    setting_value TEXT,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default settings
INSERT OR IGNORE INTO task_hierarchy_settings (setting_key, setting_value, description) VALUES
    ('max_depth', '10', 'Maximum hierarchy depth allowed'),
    ('cascade_status', 'true', 'Whether parent status changes cascade to children'),
    ('auto_complete_parent', 'true', 'Auto-complete parent when all children complete'),
    ('inherit_priority', 'false', 'Whether children inherit parent priority by default'),
    ('inherit_assignee', 'false', 'Whether children inherit parent assignee by default');

-- Task hierarchy templates for common subtask patterns
CREATE TABLE IF NOT EXISTS task_hierarchy_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    template_data TEXT NOT NULL,  -- JSON structure defining subtask hierarchy
    task_type TEXT,  -- Optional: restrict to specific task types
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_task_hierarchy_templates_name ON task_hierarchy_templates(name);
CREATE INDEX IF NOT EXISTS idx_task_hierarchy_templates_type ON task_hierarchy_templates(task_type);
