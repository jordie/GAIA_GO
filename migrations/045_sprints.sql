-- Migration 026: Sprint Management
-- Adds tables for managing sprints in Agile/Scrum workflows

-- Sprints table
CREATE TABLE IF NOT EXISTS sprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    goal TEXT,
    project_id INTEGER,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status TEXT DEFAULT 'planning',  -- planning, active, completed, cancelled
    velocity_planned INTEGER DEFAULT 0,
    velocity_actual INTEGER DEFAULT 0,
    capacity_hours REAL DEFAULT 0,
    notes TEXT,
    retrospective TEXT,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Indexes for sprint queries
CREATE INDEX IF NOT EXISTS idx_sprints_project ON sprints(project_id);
CREATE INDEX IF NOT EXISTS idx_sprints_status ON sprints(status);
CREATE INDEX IF NOT EXISTS idx_sprints_dates ON sprints(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_sprints_active ON sprints(status, start_date) WHERE status = 'active';

-- Sprint tasks association (tasks assigned to sprints)
CREATE TABLE IF NOT EXISTS sprint_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sprint_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    story_points INTEGER DEFAULT 0,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by TEXT,
    removed_at TIMESTAMP,
    removed_by TEXT,
    FOREIGN KEY (sprint_id) REFERENCES sprints(id),
    FOREIGN KEY (task_id) REFERENCES task_queue(id),
    UNIQUE(sprint_id, task_id)
);

CREATE INDEX IF NOT EXISTS idx_sprint_tasks_sprint ON sprint_tasks(sprint_id);
CREATE INDEX IF NOT EXISTS idx_sprint_tasks_task ON sprint_tasks(task_id);

-- Sprint features association (features assigned to sprints)
CREATE TABLE IF NOT EXISTS sprint_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sprint_id INTEGER NOT NULL,
    feature_id INTEGER NOT NULL,
    story_points INTEGER DEFAULT 0,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by TEXT,
    FOREIGN KEY (sprint_id) REFERENCES sprints(id),
    FOREIGN KEY (feature_id) REFERENCES features(id),
    UNIQUE(sprint_id, feature_id)
);

CREATE INDEX IF NOT EXISTS idx_sprint_features_sprint ON sprint_features(sprint_id);
CREATE INDEX IF NOT EXISTS idx_sprint_features_feature ON sprint_features(feature_id);

-- Sprint bugs association (bugs assigned to sprints)
CREATE TABLE IF NOT EXISTS sprint_bugs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sprint_id INTEGER NOT NULL,
    bug_id INTEGER NOT NULL,
    story_points INTEGER DEFAULT 0,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by TEXT,
    FOREIGN KEY (sprint_id) REFERENCES sprints(id),
    FOREIGN KEY (bug_id) REFERENCES bugs(id),
    UNIQUE(sprint_id, bug_id)
);

CREATE INDEX IF NOT EXISTS idx_sprint_bugs_sprint ON sprint_bugs(sprint_id);
CREATE INDEX IF NOT EXISTS idx_sprint_bugs_bug ON sprint_bugs(bug_id);

-- Sprint daily standups/burndown snapshots
CREATE TABLE IF NOT EXISTS sprint_daily_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sprint_id INTEGER NOT NULL,
    snapshot_date DATE NOT NULL,
    total_points INTEGER DEFAULT 0,
    completed_points INTEGER DEFAULT 0,
    remaining_points INTEGER DEFAULT 0,
    tasks_total INTEGER DEFAULT 0,
    tasks_completed INTEGER DEFAULT 0,
    tasks_in_progress INTEGER DEFAULT 0,
    blockers_count INTEGER DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sprint_id) REFERENCES sprints(id),
    UNIQUE(sprint_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_sprint_snapshots_sprint ON sprint_daily_snapshots(sprint_id);
CREATE INDEX IF NOT EXISTS idx_sprint_snapshots_date ON sprint_daily_snapshots(snapshot_date);

-- Sprint settings
CREATE TABLE IF NOT EXISTS sprint_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    setting_key TEXT NOT NULL,
    setting_value TEXT,
    UNIQUE(project_id, setting_key)
);

-- Insert default settings
INSERT OR IGNORE INTO sprint_settings (project_id, setting_key, setting_value) VALUES
    (NULL, 'default_sprint_length', '14'),
    (NULL, 'default_capacity_per_day', '6'),
    (NULL, 'auto_close_completed_sprints', 'false'),
    (NULL, 'require_retrospective', 'true'),
    (NULL, 'velocity_calculation_method', 'average'),  -- average, weighted, median
    (NULL, 'sprints_for_velocity', '3');
