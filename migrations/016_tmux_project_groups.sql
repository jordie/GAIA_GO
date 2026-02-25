-- Migration: Add project grouping support for tmux sessions
-- Enables grouping sessions by project with collapsible sections

-- Add project_id to tmux_sessions
ALTER TABLE tmux_sessions ADD COLUMN project_id INTEGER REFERENCES projects(id);

-- Add environment field for better categorization
ALTER TABLE tmux_sessions ADD COLUMN environment TEXT;

-- Add is_worker flag
ALTER TABLE tmux_sessions ADD COLUMN is_worker BOOLEAN DEFAULT 0;

-- Add display_order for custom ordering within groups
ALTER TABLE tmux_sessions ADD COLUMN display_order INTEGER DEFAULT 0;

-- Add tags for flexible categorization
ALTER TABLE tmux_sessions ADD COLUMN tags TEXT;

-- Create index for project grouping queries
CREATE INDEX IF NOT EXISTS idx_tmux_sessions_project ON tmux_sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_tmux_sessions_environment ON tmux_sessions(environment);

-- Session group preferences (collapsed state, etc.)
CREATE TABLE IF NOT EXISTS session_group_prefs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    collapsed BOOLEAN DEFAULT 0,
    display_order INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, group_id)
);

CREATE INDEX IF NOT EXISTS idx_session_group_prefs_user ON session_group_prefs(user_id);
