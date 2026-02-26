-- Sprints Migration
-- Adds table for agile sprint planning

-- Table for sprints
CREATE TABLE IF NOT EXISTS sprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    project_id INTEGER NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    goal TEXT,
    capacity_hours REAL,
    status TEXT DEFAULT 'planning',
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- Indexes for sprints
CREATE INDEX IF NOT EXISTS idx_sprints_project ON sprints(project_id);
CREATE INDEX IF NOT EXISTS idx_sprints_status ON sprints(status);
CREATE INDEX IF NOT EXISTS idx_sprints_dates ON sprints(start_date, end_date);

-- Add sprint_id column to task_queue if not exists
ALTER TABLE task_queue ADD COLUMN sprint_id INTEGER REFERENCES sprints(id);
CREATE INDEX IF NOT EXISTS idx_tasks_sprint ON task_queue(sprint_id);
