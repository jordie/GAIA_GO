-- TARGET: main
-- Migration: Add session pool management tables

-- Session Pool table for managing Claude agent sessions
CREATE TABLE IF NOT EXISTS session_pool (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    tmux_name TEXT NOT NULL,
    role TEXT DEFAULT 'worker',
    restart_count INTEGER DEFAULT 0,
    health TEXT DEFAULT 'unknown',
    status TEXT DEFAULT 'stopped',
    last_heartbeat TIMESTAMP,
    last_restart TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT
);

-- Pool Events table for tracking session lifecycle events
CREATE TABLE IF NOT EXISTS pool_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_name) REFERENCES session_pool(name)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_pool_events_session ON pool_events(session_name);
CREATE INDEX IF NOT EXISTS idx_pool_events_timestamp ON pool_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_session_pool_health ON session_pool(health);
CREATE INDEX IF NOT EXISTS idx_session_pool_status ON session_pool(status);
