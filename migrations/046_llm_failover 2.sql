-- Migration 030: LLM Provider Failover System
-- Created: 2026-01-31
-- Description: Add tables for LLM provider management, request tracking, and cost monitoring

-- =============================================================================
-- Provider Registration
-- =============================================================================

CREATE TABLE IF NOT EXISTS llm_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,              -- Provider name (claude, ollama, openai)
    provider_type TEXT NOT NULL,            -- Provider type enum
    enabled BOOLEAN NOT NULL DEFAULT 1,     -- Is provider enabled
    model TEXT NOT NULL,                     -- Default model for provider
    endpoint TEXT,                           -- API endpoint URL
    timeout INTEGER DEFAULT 120,             -- Request timeout in seconds
    max_retries INTEGER DEFAULT 3,           -- Max retry attempts

    -- Circuit breaker settings
    circuit_failure_threshold INTEGER DEFAULT 5,
    circuit_failure_window INTEGER DEFAULT 60,
    circuit_recovery_timeout INTEGER DEFAULT 30,
    circuit_success_threshold INTEGER DEFAULT 3,

    -- Cost tracking (per 1K tokens)
    cost_per_1k_prompt REAL DEFAULT 0.0,
    cost_per_1k_completion REAL DEFAULT 0.0,

    -- State
    circuit_state TEXT DEFAULT 'closed',     -- Circuit breaker state
    last_success TIMESTAMP,                  -- Last successful request
    last_failure TIMESTAMP,                  -- Last failed request
    consecutive_failures INTEGER DEFAULT 0,  -- Current failure streak

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    config_json TEXT                         -- Additional config as JSON
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_llm_providers_enabled ON llm_providers(enabled);
CREATE INDEX IF NOT EXISTS idx_llm_providers_circuit_state ON llm_providers(circuit_state);

-- Insert default providers
INSERT OR IGNORE INTO llm_providers (name, provider_type, enabled, model, endpoint, cost_per_1k_prompt, cost_per_1k_completion) VALUES
    ('claude', 'claude', 1, 'claude-sonnet-4-5-20250929', 'https://api.anthropic.com', 0.003, 0.015),
    ('ollama', 'ollama', 1, 'llama3.2', 'http://localhost:11434', 0.0, 0.0),
    ('openai', 'openai', 1, 'gpt-4-turbo', 'https://api.openai.com/v1', 0.01, 0.03);


-- =============================================================================
-- Request/Response Logging
-- =============================================================================

CREATE TABLE IF NOT EXISTS llm_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,                -- Unique request ID
    provider_name TEXT NOT NULL,             -- Provider that handled request

    -- Request details
    model TEXT NOT NULL,                     -- Model used
    use_case TEXT,                           -- Use case category
    prompt_hash TEXT,                        -- Hash of prompt for deduplication

    -- Token usage
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,

    -- Cost and performance
    cost REAL DEFAULT 0.0,                   -- Request cost in USD
    latency REAL DEFAULT 0.0,                -- Response time in seconds

    -- Failover tracking
    failover_attempt INTEGER DEFAULT 0,      -- Which attempt succeeded (0 = first)
    failed_providers TEXT,                   -- JSON array of failed providers

    -- Status
    status TEXT DEFAULT 'success',           -- success, failed, timeout, circuit_open
    error_message TEXT,                      -- Error details if failed

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_llm_requests_provider ON llm_requests(provider_name);
CREATE INDEX IF NOT EXISTS idx_llm_requests_status ON llm_requests(status);
CREATE INDEX IF NOT EXISTS idx_llm_requests_created ON llm_requests(created_at);
CREATE INDEX IF NOT EXISTS idx_llm_requests_use_case ON llm_requests(use_case);
CREATE INDEX IF NOT EXISTS idx_llm_requests_prompt_hash ON llm_requests(prompt_hash);


-- =============================================================================
-- Cost Tracking and Aggregation
-- =============================================================================

CREATE TABLE IF NOT EXISTS llm_cost_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_name TEXT NOT NULL,             -- Provider name
    time_bucket TEXT NOT NULL,               -- Time bucket (YYYY-MM-DD HH:00:00 for hourly)
    bucket_type TEXT DEFAULT 'hourly',       -- hourly, daily, monthly

    -- Aggregated metrics
    request_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    total_cost REAL DEFAULT 0.0,

    -- Success/failure tracking
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    timeout_count INTEGER DEFAULT 0,

    -- Performance
    avg_latency REAL DEFAULT 0.0,
    max_latency REAL DEFAULT 0.0,
    min_latency REAL DEFAULT 0.0,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(provider_name, time_bucket, bucket_type)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_llm_cost_tracking_provider ON llm_cost_tracking(provider_name);
CREATE INDEX IF NOT EXISTS idx_llm_cost_tracking_time_bucket ON llm_cost_tracking(time_bucket);
CREATE INDEX IF NOT EXISTS idx_llm_cost_tracking_bucket_type ON llm_cost_tracking(bucket_type);


-- =============================================================================
-- Budget Management and Alerts
-- =============================================================================

CREATE TABLE IF NOT EXISTS llm_budget_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL,                -- daily_limit, monthly_limit, threshold
    threshold_type TEXT NOT NULL,            -- requests, cost
    threshold_value REAL NOT NULL,           -- Threshold value
    current_value REAL DEFAULT 0.0,          -- Current value
    period_start TIMESTAMP NOT NULL,         -- Period start time
    period_end TIMESTAMP NOT NULL,           -- Period end time

    -- Alert status
    triggered BOOLEAN DEFAULT 0,
    triggered_at TIMESTAMP,
    acknowledged BOOLEAN DEFAULT 0,
    acknowledged_at TIMESTAMP,
    acknowledged_by TEXT,

    -- Actions taken
    action_taken TEXT,                       -- block_provider, send_alert, etc.

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details_json TEXT                        -- Additional details as JSON
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_llm_budget_alerts_triggered ON llm_budget_alerts(triggered);
CREATE INDEX IF NOT EXISTS idx_llm_budget_alerts_period ON llm_budget_alerts(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_llm_budget_alerts_type ON llm_budget_alerts(alert_type);


-- =============================================================================
-- Failover Events Log
-- =============================================================================

CREATE TABLE IF NOT EXISTS llm_failover_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,                -- Associated request ID
    from_provider TEXT NOT NULL,             -- Provider that failed
    to_provider TEXT,                        -- Provider that succeeded (NULL if all failed)

    -- Failure details
    failure_reason TEXT NOT NULL,            -- Error message or reason
    failure_type TEXT,                       -- timeout, circuit_open, api_error, etc.

    -- Circuit breaker state
    circuit_opened BOOLEAN DEFAULT 0,        -- Did this event open a circuit
    circuit_state_before TEXT,
    circuit_state_after TEXT,

    -- Timing
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Metadata
    details_json TEXT                        -- Additional details as JSON
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_llm_failover_events_from_provider ON llm_failover_events(from_provider);
CREATE INDEX IF NOT EXISTS idx_llm_failover_events_occurred ON llm_failover_events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_llm_failover_events_circuit_opened ON llm_failover_events(circuit_opened);


-- =============================================================================
-- Response Quality Tracking (for adaptive routing)
-- =============================================================================

CREATE TABLE IF NOT EXISTS llm_response_quality (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,                -- Associated request ID
    provider_name TEXT NOT NULL,             -- Provider that generated response

    -- Quality metrics (user feedback or automated)
    quality_score REAL,                      -- 0.0 to 1.0 quality rating
    user_rating INTEGER,                     -- 1-5 star rating (optional)
    automated_score REAL,                    -- Automated quality check

    -- Feedback
    feedback_type TEXT,                      -- positive, negative, neutral
    feedback_text TEXT,                      -- User feedback comments

    -- Context
    use_case TEXT,                           -- Use case for this request
    task_type TEXT,                          -- Type of task

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT                          -- User who provided feedback
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_llm_response_quality_provider ON llm_response_quality(provider_name);
CREATE INDEX IF NOT EXISTS idx_llm_response_quality_use_case ON llm_response_quality(use_case);
CREATE INDEX IF NOT EXISTS idx_llm_response_quality_score ON llm_response_quality(quality_score);


-- =============================================================================
-- Provider Health Metrics
-- =============================================================================

CREATE TABLE IF NOT EXISTS llm_provider_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_name TEXT NOT NULL,             -- Provider name
    check_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Health check results
    is_healthy BOOLEAN DEFAULT 1,            -- Overall health status
    response_time REAL,                      -- Health check response time
    error_message TEXT,                      -- Error if unhealthy

    -- Circuit breaker state at check time
    circuit_state TEXT,
    consecutive_failures INTEGER DEFAULT 0,
    current_recovery_timeout INTEGER,

    -- Metrics snapshot
    success_rate REAL,                       -- Success rate (0.0 to 1.0)
    avg_latency REAL,                        -- Average latency in seconds
    requests_last_hour INTEGER,              -- Request count in last hour
    cost_last_hour REAL                      -- Cost in last hour
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_llm_provider_health_provider ON llm_provider_health(provider_name);
CREATE INDEX IF NOT EXISTS idx_llm_provider_health_check_time ON llm_provider_health(check_time);
CREATE INDEX IF NOT EXISTS idx_llm_provider_health_healthy ON llm_provider_health(is_healthy);


-- =============================================================================
-- Views for Reporting
-- =============================================================================

-- Daily cost summary by provider
CREATE VIEW IF NOT EXISTS v_llm_daily_costs AS
SELECT
    provider_name,
    DATE(time_bucket) as date,
    SUM(request_count) as total_requests,
    SUM(total_tokens) as total_tokens,
    SUM(total_cost) as total_cost,
    ROUND(SUM(total_cost) / NULLIF(SUM(request_count), 0), 4) as avg_cost_per_request,
    ROUND(SUM(success_count) * 100.0 / NULLIF(SUM(request_count), 0), 2) as success_rate
FROM llm_cost_tracking
WHERE bucket_type = 'hourly'
GROUP BY provider_name, DATE(time_bucket)
ORDER BY date DESC, provider_name;

-- Recent failover events
CREATE VIEW IF NOT EXISTS v_recent_failovers AS
SELECT
    lfe.id,
    lfe.from_provider,
    lfe.to_provider,
    lfe.failure_reason,
    lfe.failure_type,
    lfe.circuit_opened,
    lfe.occurred_at,
    lr.use_case,
    lr.model
FROM llm_failover_events lfe
LEFT JOIN llm_requests lr ON lfe.request_id = lr.request_id
ORDER BY lfe.occurred_at DESC
LIMIT 100;

-- Provider performance summary
CREATE VIEW IF NOT EXISTS v_provider_performance AS
SELECT
    p.name,
    p.enabled,
    p.circuit_state,
    COUNT(r.id) as total_requests,
    SUM(CASE WHEN r.status = 'success' THEN 1 ELSE 0 END) as successful_requests,
    ROUND(SUM(CASE WHEN r.status = 'success' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(r.id), 0), 2) as success_rate,
    ROUND(AVG(r.latency), 2) as avg_latency,
    ROUND(SUM(r.cost), 4) as total_cost,
    MAX(r.created_at) as last_request_at
FROM llm_providers p
LEFT JOIN llm_requests r ON p.name = r.provider_name
    AND r.created_at > datetime('now', '-24 hours')
GROUP BY p.name
ORDER BY p.name;


-- =============================================================================
-- Triggers for Automatic Updates
-- =============================================================================

-- Update llm_providers.updated_at on changes
CREATE TRIGGER IF NOT EXISTS llm_providers_update_timestamp
AFTER UPDATE ON llm_providers
FOR EACH ROW
BEGIN
    UPDATE llm_providers SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Update llm_cost_tracking.updated_at on changes
CREATE TRIGGER IF NOT EXISTS llm_cost_tracking_update_timestamp
AFTER UPDATE ON llm_cost_tracking
FOR EACH ROW
BEGIN
    UPDATE llm_cost_tracking SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Update llm_budget_alerts.updated_at on changes
CREATE TRIGGER IF NOT EXISTS llm_budget_alerts_update_timestamp
AFTER UPDATE ON llm_budget_alerts
FOR EACH ROW
BEGIN
    UPDATE llm_budget_alerts SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;


-- =============================================================================
-- Sample Data for Testing
-- =============================================================================

-- Add sample health check
INSERT INTO llm_provider_health (provider_name, is_healthy, circuit_state, success_rate)
SELECT name, 1, circuit_state, 1.0
FROM llm_providers
WHERE enabled = 1;
