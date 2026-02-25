-- GAIA_GO Tmux Session Grouping
-- Organizes tmux sessions into project groups for better development workflow management

-- Projects table: Core project definitions
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    icon TEXT,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tmux Sessions table: Track all tmux sessions with project association
CREATE TABLE IF NOT EXISTS tmux_sessions (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    project_id INTEGER,
    environment TEXT DEFAULT 'dev',
    is_worker BOOLEAN DEFAULT 0,
    attached BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

-- Session Group Preferences: Store user UI state for collapsed/expanded groups
CREATE TABLE IF NOT EXISTS session_group_prefs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    group_id TEXT NOT NULL,
    collapsed BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    UNIQUE(user_id, group_id)
);

-- Indices for common queries
CREATE INDEX IF NOT EXISTS idx_tmux_sessions_project_id ON tmux_sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_tmux_sessions_environment ON tmux_sessions(environment);
CREATE INDEX IF NOT EXISTS idx_tmux_sessions_is_worker ON tmux_sessions(is_worker);
CREATE INDEX IF NOT EXISTS idx_tmux_sessions_name ON tmux_sessions(name);
CREATE INDEX IF NOT EXISTS idx_session_group_prefs_user_id ON session_group_prefs(user_id);

-- Seed data: Four core projects
INSERT OR IGNORE INTO projects (slug, name, icon, display_order) VALUES
    ('basic_edu', 'Basic Education Apps', '🎓', 1),
    ('rando', 'Rando Project', '🎲', 2),
    ('architect', 'Architect System', '🏗️', 3),
    ('gaia_improvements', 'GAIA Improvements', '⚡', 4);
