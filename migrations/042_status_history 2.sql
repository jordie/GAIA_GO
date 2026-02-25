-- Migration: Add task status change history
-- Tracks all status changes across features, bugs, and tasks

-- Status history table
CREATE TABLE IF NOT EXISTS status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Entity reference
    entity_type TEXT NOT NULL,  -- 'feature', 'bug', 'task', 'milestone', 'devops_task'
    entity_id INTEGER NOT NULL,

    -- Status change details
    old_status TEXT,            -- Previous status (NULL for initial creation)
    new_status TEXT NOT NULL,   -- New status

    -- Context
    changed_by TEXT,            -- User who made the change
    change_reason TEXT,         -- Optional reason/comment
    change_source TEXT,         -- 'manual', 'api', 'auto', 'webhook', 'worker'

    -- Metadata
    metadata TEXT,              -- JSON for additional context
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_status_history_entity
    ON status_history(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_status_history_created
    ON status_history(created_at);
CREATE INDEX IF NOT EXISTS idx_status_history_user
    ON status_history(changed_by);
CREATE INDEX IF NOT EXISTS idx_status_history_status
    ON status_history(new_status);

-- Status transition rules (optional enforcement)
CREATE TABLE IF NOT EXISTS status_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    from_status TEXT NOT NULL,
    to_status TEXT NOT NULL,
    is_allowed BOOLEAN DEFAULT 1,
    requires_reason BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_type, from_status, to_status)
);

-- Seed common valid transitions
INSERT OR IGNORE INTO status_transitions (entity_type, from_status, to_status) VALUES
    -- Feature transitions
    ('feature', 'draft', 'planned'),
    ('feature', 'planned', 'in_progress'),
    ('feature', 'in_progress', 'review'),
    ('feature', 'review', 'testing'),
    ('feature', 'testing', 'completed'),
    ('feature', 'in_progress', 'blocked'),
    ('feature', 'blocked', 'in_progress'),
    ('feature', 'review', 'in_progress'),
    ('feature', 'testing', 'in_progress'),

    -- Bug transitions
    ('bug', 'open', 'in_progress'),
    ('bug', 'in_progress', 'resolved'),
    ('bug', 'resolved', 'closed'),
    ('bug', 'resolved', 'open'),
    ('bug', 'in_progress', 'open'),
    ('bug', 'open', 'wontfix'),

    -- Task transitions
    ('task', 'pending', 'running'),
    ('task', 'running', 'completed'),
    ('task', 'running', 'failed'),
    ('task', 'pending', 'cancelled'),
    ('task', 'failed', 'pending'),

    -- Milestone transitions
    ('milestone', 'open', 'in_progress'),
    ('milestone', 'in_progress', 'completed'),
    ('milestone', 'in_progress', 'on_hold'),
    ('milestone', 'on_hold', 'in_progress');
