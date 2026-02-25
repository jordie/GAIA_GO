-- Migration 050: Rate Limiting and Resource Monitoring Enhancement
-- Adds database-backed rate limiting with persistence and auto-throttling

-- Rate Limit Configurations
CREATE TABLE IF NOT EXISTS rate_limit_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT NOT NULL UNIQUE,
    scope TEXT NOT NULL,  -- 'ip', 'user', 'api_key', 'resource'
    scope_value TEXT,     -- Specific IP/user/key, or NULL for default
    limit_type TEXT NOT NULL,  -- 'requests_per_minute', 'requests_per_hour', 'daily_quota'
    limit_value INTEGER NOT NULL,
    resource_type TEXT,   -- 'login', 'create', 'upload', 'api_call', NULL for all
    enabled BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rate_configs_scope ON rate_limit_configs(scope, scope_value);
CREATE INDEX IF NOT EXISTS idx_rate_configs_resource ON rate_limit_configs(resource_type);
CREATE INDEX IF NOT EXISTS idx_rate_configs_enabled ON rate_limit_configs(enabled);

-- Rate Limit Buckets (sliding window)
CREATE TABLE IF NOT EXISTS rate_limit_buckets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    scope_value TEXT NOT NULL,
    resource_type TEXT,
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    request_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_buckets_scope ON rate_limit_buckets(scope, scope_value, window_start);
CREATE INDEX IF NOT EXISTS idx_buckets_resource ON rate_limit_buckets(resource_type, window_start);
CREATE INDEX IF NOT EXISTS idx_buckets_time ON rate_limit_buckets(window_end);

-- Rate Limit Violations
CREATE TABLE IF NOT EXISTS rate_limit_violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    scope_value TEXT NOT NULL,
    resource_type TEXT,
    exceeded_limit INTEGER,
    actual_count INTEGER,
    violation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    request_path TEXT,
    user_agent TEXT,
    blocked BOOLEAN DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_violations_scope ON rate_limit_violations(scope, scope_value, violation_time);
CREATE INDEX IF NOT EXISTS idx_violations_time ON rate_limit_violations(violation_time);
CREATE INDEX IF NOT EXISTS idx_violations_blocked ON rate_limit_violations(blocked);

-- Resource Quotas (daily/monthly limits)
CREATE TABLE IF NOT EXISTS resource_quotas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    api_key TEXT,
    resource_type TEXT NOT NULL,
    quota_period TEXT NOT NULL,  -- 'daily', 'weekly', 'monthly'
    quota_limit INTEGER NOT NULL,
    quota_used INTEGER DEFAULT 0,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_quotas_user ON resource_quotas(user_id, resource_type, period_start);
CREATE INDEX IF NOT EXISTS idx_quotas_apikey ON resource_quotas(api_key, resource_type, period_start);
CREATE INDEX IF NOT EXISTS idx_quotas_period ON resource_quotas(period_start, period_end);

-- Resource Consumption Tracking
CREATE TABLE IF NOT EXISTS resource_consumption (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cpu_percent REAL,
    memory_percent REAL,
    memory_mb REAL,
    disk_io_read_mb REAL,
    disk_io_write_mb REAL,
    network_sent_mb REAL,
    network_recv_mb REAL,
    active_connections INTEGER,
    request_rate REAL,  -- requests per second
    avg_response_time_ms REAL
);

CREATE INDEX IF NOT EXISTS idx_consumption_time ON resource_consumption(timestamp);
CREATE INDEX IF NOT EXISTS idx_consumption_date ON resource_consumption(DATE(timestamp));

-- System Load History (for trend analysis)
CREATE TABLE IF NOT EXISTS system_load_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cpu_percent REAL,
    memory_percent REAL,
    disk_percent REAL,
    throttle_active BOOLEAN DEFAULT 0,
    throttle_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_load_time ON system_load_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_load_throttle ON system_load_history(throttle_active, timestamp);

-- Rate Limit Statistics (summary)
CREATE TABLE IF NOT EXISTS rate_limit_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE DEFAULT CURRENT_DATE,
    scope TEXT NOT NULL,
    total_requests INTEGER DEFAULT 0,
    total_violations INTEGER DEFAULT 0,
    avg_response_time_ms REAL,
    peak_requests_per_minute INTEGER,
    unique_clients INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stats_date ON rate_limit_stats(date);
CREATE INDEX IF NOT EXISTS idx_stats_scope ON rate_limit_stats(scope, date);
