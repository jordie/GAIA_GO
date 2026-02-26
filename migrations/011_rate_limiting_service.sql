-- Phase 11: Rate Limiting & Resource Quotas - Shared Service
-- Created: 2026-02-26
-- Purpose: Database-backed rate limiting for GAIA_GO and Go GAIA MVP

-- Table 1: Rate Limit Rules
CREATE TABLE IF NOT EXISTS rate_limit_rules (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(255) UNIQUE NOT NULL,
    system_id VARCHAR(50) NOT NULL,  -- 'gaia_go', 'gaia_mvp', 'global'
    scope VARCHAR(50) NOT NULL,      -- 'ip', 'session', 'user', 'api_key'
    scope_value VARCHAR(255),        -- Specific value or NULL for default
    limit_type VARCHAR(50) NOT NULL, -- 'requests_per_second', 'requests_per_minute', 'daily_quota'
    limit_value INTEGER NOT NULL,
    resource_type VARCHAR(100),      -- 'confirm_request', 'pattern_crud', 'repl_command'
    enabled BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 100,    -- Lower = applied first
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rules_system ON rate_limit_rules(system_id);
CREATE INDEX IF NOT EXISTS idx_rules_scope ON rate_limit_rules(scope, scope_value);
CREATE INDEX IF NOT EXISTS idx_rules_enabled ON rate_limit_rules(enabled);

-- Table 2: Rate Limit Buckets (Sliding Window)
CREATE TABLE IF NOT EXISTS rate_limit_buckets (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER REFERENCES rate_limit_rules(id) ON DELETE CASCADE,
    system_id VARCHAR(50) NOT NULL,
    scope VARCHAR(50) NOT NULL,
    scope_value VARCHAR(255) NOT NULL,
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    request_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(rule_id, scope_value, window_start)
);

CREATE INDEX IF NOT EXISTS idx_buckets_scope_time ON rate_limit_buckets(system_id, scope, scope_value, window_start DESC);
CREATE INDEX IF NOT EXISTS idx_buckets_cleanup ON rate_limit_buckets(window_end) WHERE window_end < CURRENT_TIMESTAMP;

-- Table 3: Resource Quotas
CREATE TABLE IF NOT EXISTS resource_quotas (
    id SERIAL PRIMARY KEY,
    system_id VARCHAR(50) NOT NULL,
    scope VARCHAR(50) NOT NULL,
    scope_value VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    quota_period VARCHAR(20) NOT NULL,  -- 'daily', 'weekly', 'monthly'
    quota_limit INTEGER NOT NULL,
    quota_used INTEGER DEFAULT 0,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    last_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(system_id, scope, scope_value, resource_type, period_start)
);

CREATE INDEX IF NOT EXISTS idx_quotas_scope_period ON resource_quotas(system_id, scope, scope_value, period_start DESC);
CREATE INDEX IF NOT EXISTS idx_quotas_reset ON resource_quotas(period_end) WHERE quota_used < quota_limit;

-- Table 4: Rate Limit Violations
CREATE TABLE IF NOT EXISTS rate_limit_violations (
    id SERIAL PRIMARY KEY,
    system_id VARCHAR(50) NOT NULL,
    rule_id INTEGER REFERENCES rate_limit_rules(id) ON DELETE SET NULL,
    scope VARCHAR(50) NOT NULL,
    scope_value VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100),
    violated_limit INTEGER,
    actual_count INTEGER,
    violation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    request_path VARCHAR(500),
    request_method VARCHAR(10),
    user_agent VARCHAR(500),
    blocked BOOLEAN DEFAULT true,
    severity VARCHAR(20)  -- 'low', 'medium', 'high', 'critical'
);

CREATE INDEX IF NOT EXISTS idx_violations_system_time ON rate_limit_violations(system_id, violation_time DESC);
CREATE INDEX IF NOT EXISTS idx_violations_scope ON rate_limit_violations(scope, scope_value, violation_time DESC);
CREATE INDEX IF NOT EXISTS idx_violations_severity ON rate_limit_violations(severity, violation_time DESC);

-- Table 5: Rate Limit Metrics
CREATE TABLE IF NOT EXISTS rate_limit_metrics (
    id SERIAL PRIMARY KEY,
    system_id VARCHAR(50) NOT NULL,
    scope VARCHAR(50),
    scope_value VARCHAR(255),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    requests_processed INTEGER DEFAULT 0,
    requests_allowed INTEGER DEFAULT 0,
    requests_blocked INTEGER DEFAULT 0,
    avg_response_time_ms FLOAT DEFAULT 0,
    cpu_usage_percent FLOAT DEFAULT 0,
    memory_usage_percent FLOAT DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_metrics_system_time ON rate_limit_metrics(system_id, timestamp DESC);

-- Insert default rate limit rules for GAIA_GO

-- GAIA_GO: Confirmation Requests
INSERT INTO rate_limit_rules (rule_name, system_id, scope, limit_type, limit_value, resource_type, priority)
VALUES ('gaia_go_confirm_per_session', 'gaia_go', 'session', 'requests_per_minute', 100, 'confirm_request', 10)
ON CONFLICT(rule_name) DO NOTHING;

INSERT INTO rate_limit_rules (rule_name, system_id, scope, limit_type, limit_value, resource_type, priority)
VALUES ('gaia_go_confirm_per_ip', 'gaia_go', 'ip', 'requests_per_minute', 1000, 'confirm_request', 20)
ON CONFLICT(rule_name) DO NOTHING;

-- GAIA_GO: Pattern Management
INSERT INTO rate_limit_rules (rule_name, system_id, scope, limit_type, limit_value, resource_type, priority)
VALUES ('gaia_go_pattern_create', 'gaia_go', 'session', 'daily_quota', 50, 'pattern_create', 10)
ON CONFLICT(rule_name) DO NOTHING;

INSERT INTO rate_limit_rules (rule_name, system_id, scope, limit_type, limit_value, resource_type, priority)
VALUES ('gaia_go_pattern_modify', 'gaia_go', 'session', 'requests_per_hour', 10, 'pattern_modify', 10)
ON CONFLICT(rule_name) DO NOTHING;

-- GAIA_GO: Statistics
INSERT INTO rate_limit_rules (rule_name, system_id, scope, limit_type, limit_value, resource_type, priority)
VALUES ('gaia_go_stats_per_ip', 'gaia_go', 'ip', 'requests_per_hour', 1000, 'stats', 20)
ON CONFLICT(rule_name) DO NOTHING;

-- Go GAIA MVP: REPL Commands
INSERT INTO rate_limit_rules (rule_name, system_id, scope, limit_type, limit_value, resource_type, priority)
VALUES ('gaia_mvp_query_per_session', 'gaia_mvp', 'session', 'requests_per_minute', 50, 'repl_query', 10)
ON CONFLICT(rule_name) DO NOTHING;

INSERT INTO rate_limit_rules (rule_name, system_id, scope, limit_type, limit_value, resource_type, priority)
VALUES ('gaia_mvp_query_per_ip', 'gaia_mvp', 'ip', 'requests_per_minute', 500, 'repl_query', 20)
ON CONFLICT(rule_name) DO NOTHING;

INSERT INTO rate_limit_rules (rule_name, system_id, scope, limit_type, limit_value, resource_type, priority)
VALUES ('gaia_mvp_execute_per_session', 'gaia_mvp', 'session', 'requests_per_hour', 10, 'repl_execute', 10)
ON CONFLICT(rule_name) DO NOTHING;

-- Global fallback rules
INSERT INTO rate_limit_rules (rule_name, system_id, scope, limit_type, limit_value, resource_type, priority)
VALUES ('global_ip_default', 'global', 'ip', 'requests_per_second', 100, NULL, 100)
ON CONFLICT(rule_name) DO NOTHING;
