-- GAIA Service Coordinator Tables

CREATE TABLE IF NOT EXISTS gaia_services (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    command TEXT NOT NULL,
    args TEXT,
    work_dir TEXT,
    port INTEGER,
    status TEXT NOT NULL DEFAULT 'stopped',
    environment TEXT,
    health_check TEXT,
    auto_restart BOOLEAN DEFAULT 0,
    process_id INTEGER,
    restarts INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    stopped_at TIMESTAMP,
    last_health_check TIMESTAMP,
    error TEXT,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gaia_service_health_history (
    id TEXT PRIMARY KEY,
    service_id TEXT NOT NULL,
    is_healthy BOOLEAN NOT NULL,
    response_time_ms INTEGER,
    failure_count INTEGER DEFAULT 0,
    last_error TEXT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(service_id) REFERENCES gaia_services(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gaia_service_events (
    id TEXT PRIMARY KEY,
    service_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(service_id) REFERENCES gaia_services(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gaia_service_metrics (
    id TEXT PRIMARY KEY,
    service_id TEXT NOT NULL,
    cpu_percent REAL,
    memory_mb INTEGER,
    uptime_seconds INTEGER,
    health_checks_passed INTEGER DEFAULT 0,
    health_checks_failed INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(service_id) REFERENCES gaia_services(id) ON DELETE CASCADE
);

-- Indices for common queries
CREATE INDEX IF NOT EXISTS idx_gaia_services_status ON gaia_services(status);
CREATE INDEX IF NOT EXISTS idx_gaia_services_created_at ON gaia_services(created_at);
CREATE INDEX IF NOT EXISTS idx_gaia_service_health_service_id ON gaia_service_health_history(service_id);
CREATE INDEX IF NOT EXISTS idx_gaia_service_health_checked_at ON gaia_service_health_history(checked_at);
CREATE INDEX IF NOT EXISTS idx_gaia_service_events_service_id ON gaia_service_events(service_id);
CREATE INDEX IF NOT EXISTS idx_gaia_service_metrics_service_id ON gaia_service_metrics(service_id);
