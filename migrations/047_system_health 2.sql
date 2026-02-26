-- System Health Monitoring
-- Track system resources (CPU, memory, disk) and service status over time

CREATE TABLE IF NOT EXISTS system_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- System resources
    cpu_percent REAL,
    memory_percent REAL,
    memory_used_mb INTEGER,
    memory_total_mb INTEGER,
    disk_percent REAL,
    disk_used_gb INTEGER,
    disk_total_gb INTEGER,

    -- Network
    network_sent_mb REAL,
    network_recv_mb REAL,

    -- Load average (1, 5, 15 min)
    load_avg_1 REAL,
    load_avg_5 REAL,
    load_avg_15 REAL,

    -- Service counts
    services_running INTEGER,
    services_total INTEGER,
    workers_active INTEGER,
    workers_total INTEGER,

    -- Additional metrics
    uptime_seconds INTEGER,
    process_count INTEGER,
    thread_count INTEGER,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_system_health_timestamp ON system_health(timestamp);
CREATE INDEX IF NOT EXISTS idx_system_health_created_at ON system_health(created_at);

-- Service health tracking
CREATE TABLE IF NOT EXISTS service_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    service_name TEXT NOT NULL,
    service_type TEXT CHECK(service_type IN ('web', 'worker', 'llm', 'database', 'other')),
    port INTEGER,
    pid INTEGER,
    status TEXT CHECK(status IN ('running', 'stopped', 'error', 'unknown')),

    -- Resource usage
    cpu_percent REAL,
    memory_mb REAL,
    memory_percent REAL,

    -- Response time (for web services)
    response_time_ms INTEGER,

    -- Error info (if status = 'error')
    error_message TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_service_health_timestamp ON service_health(timestamp);
CREATE INDEX IF NOT EXISTS idx_service_health_service ON service_health(service_name, timestamp);

-- Keep only last 30 days of metrics (cleanup trigger)
CREATE TRIGGER IF NOT EXISTS cleanup_old_system_health
AFTER INSERT ON system_health
BEGIN
    DELETE FROM system_health
    WHERE timestamp < datetime('now', '-30 days');
END;

CREATE TRIGGER IF NOT EXISTS cleanup_old_service_health
AFTER INSERT ON service_health
BEGIN
    DELETE FROM service_health
    WHERE timestamp < datetime('now', '-30 days');
END;
