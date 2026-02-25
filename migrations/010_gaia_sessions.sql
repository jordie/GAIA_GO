-- GAIA Session Management Tables
-- Separate from user authentication sessions (internal/session/)

CREATE TABLE IF NOT EXISTS gaia_sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    project_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'active',
    metadata TEXT,
    tags TEXT
);

CREATE TABLE IF NOT EXISTS gaia_session_windows (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    name TEXT NOT NULL,
    window_index INTEGER NOT NULL,
    active BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES gaia_sessions(id) ON DELETE CASCADE,
    UNIQUE(session_id, window_index)
);

CREATE TABLE IF NOT EXISTS gaia_session_panes (
    id TEXT PRIMARY KEY,
    window_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    pane_index INTEGER NOT NULL,
    command TEXT,
    work_dir TEXT,
    active BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(window_id) REFERENCES gaia_session_windows(id) ON DELETE CASCADE,
    FOREIGN KEY(session_id) REFERENCES gaia_sessions(id) ON DELETE CASCADE,
    UNIQUE(window_id, pane_index)
);

-- Indices for common queries
CREATE INDEX IF NOT EXISTS idx_gaia_sessions_created_at ON gaia_sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_gaia_sessions_last_active ON gaia_sessions(last_active);
CREATE INDEX IF NOT EXISTS idx_gaia_sessions_status ON gaia_sessions(status);
CREATE INDEX IF NOT EXISTS idx_gaia_session_windows_session_id ON gaia_session_windows(session_id);
CREATE INDEX IF NOT EXISTS idx_gaia_session_panes_session_id ON gaia_session_panes(session_id);
CREATE INDEX IF NOT EXISTS idx_gaia_session_panes_window_id ON gaia_session_panes(window_id);
