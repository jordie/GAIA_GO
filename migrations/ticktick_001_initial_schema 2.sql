-- TickTick Cache Database Schema
-- Hybrid design: indexed columns for frequent queries + JSON blobs for flexibility

-- Schema versioning
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (1, 'Initial TickTick cache schema with hybrid indexed + JSON design');

-- Folders/Projects table
CREATE TABLE IF NOT EXISTS folders (
    -- Core identity
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,

    -- Indexed metadata
    sort_order INTEGER,
    closed BOOLEAN DEFAULT 0,
    kind TEXT,

    -- Flexible JSON blob for all other fields
    raw_data TEXT,

    -- Sync metadata
    etag TEXT,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_folders_name ON folders(name);
CREATE INDEX IF NOT EXISTS idx_folders_kind ON folders(kind);
CREATE INDEX IF NOT EXISTS idx_folders_synced ON folders(synced_at DESC);

-- Tasks table
CREATE TABLE IF NOT EXISTS tasks (
    -- Core identity
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,

    -- Indexed fields for common queries
    title TEXT NOT NULL,
    status INTEGER DEFAULT 0,               -- 0=open, 1=completed
    priority INTEGER DEFAULT 0,             -- 0=none, 1-5=levels

    -- Date/time fields (frequently filtered)
    start_date TEXT,                        -- ISO8601
    due_date TEXT,                          -- ISO8601
    completed_date TEXT,                    -- ISO8601

    -- Hierarchy
    parent_id TEXT,                         -- Subtask parent

    -- Content (full-text searchable)
    content TEXT,

    -- Flexible JSON blob
    raw_data TEXT,

    -- Sync metadata
    etag TEXT,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,

    -- Foreign keys
    FOREIGN KEY (project_id) REFERENCES folders(id)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id);
CREATE INDEX IF NOT EXISTS idx_tasks_synced ON tasks(synced_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_modified ON tasks(modified_at DESC);

-- Compound indexes for common queries
CREATE INDEX IF NOT EXISTS idx_tasks_project_status ON tasks(project_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_status_priority ON tasks(status, priority DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_due_priority ON tasks(due_date, priority DESC) WHERE status = 0;

-- Full-text search table
CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(
    title,
    content,
    content=tasks,
    content_rowid=rowid
);

-- Triggers to keep FTS in sync with main tasks table
CREATE TRIGGER IF NOT EXISTS tasks_ai AFTER INSERT ON tasks BEGIN
    INSERT INTO tasks_fts(rowid, title, content)
    VALUES (new.rowid, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS tasks_ad AFTER DELETE ON tasks BEGIN
    DELETE FROM tasks_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER IF NOT EXISTS tasks_au AFTER UPDATE ON tasks BEGIN
    UPDATE tasks_fts SET title = new.title, content = new.content
    WHERE rowid = new.rowid;
END;

-- Tags table (many-to-many relationship)
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    tag TEXT NOT NULL,

    FOREIGN KEY (task_id) REFERENCES tasks(id),
    UNIQUE(task_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_tags_task ON tags(task_id);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);

-- Sync state table (ETag tracking per resource)
CREATE TABLE IF NOT EXISTS sync_state (
    resource_type TEXT NOT NULL,            -- 'folder', 'project_tasks'
    resource_id TEXT NOT NULL,              -- folder ID or 'all'
    etag TEXT,                              -- Last known ETag from API
    last_sync TIMESTAMP,                    -- Last successful sync time
    last_modified TIMESTAMP,                -- Last time data was modified
    sync_count INTEGER DEFAULT 0,           -- Total sync attempts
    error_count INTEGER DEFAULT 0,          -- Consecutive errors
    last_error TEXT,                        -- Last error message

    PRIMARY KEY (resource_type, resource_id)
);

CREATE INDEX IF NOT EXISTS idx_sync_last_sync ON sync_state(last_sync DESC);

-- Materialized view: Active tasks (most common query pattern)
CREATE VIEW IF NOT EXISTS active_tasks AS
SELECT
    t.id,
    t.project_id,
    f.name AS project_name,
    t.title,
    t.status,
    t.priority,
    t.due_date,
    t.parent_id,
    GROUP_CONCAT(tg.tag, ',') AS tags,
    t.modified_at
FROM tasks t
JOIN folders f ON t.project_id = f.id
LEFT JOIN tags tg ON t.id = tg.task_id
WHERE t.deleted_at IS NULL
  AND t.status = 0
GROUP BY t.id
ORDER BY t.priority DESC, t.due_date ASC;

-- Materialized view: Focus list (dedicated quick access)
CREATE VIEW IF NOT EXISTS focus_tasks AS
SELECT
    t.*,
    GROUP_CONCAT(tg.tag, ',') AS tags
FROM tasks t
JOIN folders f ON t.project_id = f.id
LEFT JOIN tags tg ON t.id = tg.task_id
WHERE f.name = 'Focus'
  AND t.deleted_at IS NULL
GROUP BY t.id
ORDER BY t.priority DESC, t.due_date ASC;

-- Materialized view: Overdue tasks
CREATE VIEW IF NOT EXISTS overdue_tasks AS
SELECT
    t.*,
    f.name AS project_name,
    GROUP_CONCAT(tg.tag, ',') AS tags
FROM tasks t
JOIN folders f ON t.project_id = f.id
LEFT JOIN tags tg ON t.id = tg.task_id
WHERE t.due_date < datetime('now')
  AND t.status = 0
  AND t.deleted_at IS NULL
GROUP BY t.id
ORDER BY t.due_date ASC;

-- Ensure foreign key constraints are enabled
PRAGMA foreign_keys = ON;
