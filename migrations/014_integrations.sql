-- Migration: Add third-party integrations support
-- Manages external service connections (GitHub, Slack, Jira, etc.)

CREATE TABLE IF NOT EXISTS integrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    provider TEXT NOT NULL,
    config TEXT NOT NULL,
    credentials TEXT,
    enabled BOOLEAN DEFAULT 1,
    status TEXT DEFAULT 'pending',
    status_message TEXT,
    last_sync_at TIMESTAMP,
    last_error_at TIMESTAMP,
    last_error TEXT,
    sync_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name)
);

-- Integration events/webhooks received
CREATE TABLE IF NOT EXISTS integration_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    integration_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT,
    source_id TEXT,
    processed BOOLEAN DEFAULT 0,
    processed_at TIMESTAMP,
    result TEXT,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (integration_id) REFERENCES integrations(id) ON DELETE CASCADE
);

-- Integration sync log
CREATE TABLE IF NOT EXISTS integration_sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    integration_id INTEGER NOT NULL,
    sync_type TEXT NOT NULL,
    direction TEXT DEFAULT 'inbound',
    items_synced INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0,
    duration_ms INTEGER,
    details TEXT,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (integration_id) REFERENCES integrations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_integrations_type ON integrations(type);
CREATE INDEX IF NOT EXISTS idx_integrations_provider ON integrations(provider);
CREATE INDEX IF NOT EXISTS idx_integrations_enabled ON integrations(enabled);
CREATE INDEX IF NOT EXISTS idx_integration_events_integration ON integration_events(integration_id);
CREATE INDEX IF NOT EXISTS idx_integration_events_processed ON integration_events(processed);
CREATE INDEX IF NOT EXISTS idx_integration_sync_log_integration ON integration_sync_log(integration_id);
