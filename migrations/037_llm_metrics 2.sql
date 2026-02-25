-- Migration: LLM Provider Metrics and Cost Tracking
-- Date: 2026-02-07
-- Description: Tables for tracking LLM provider usage, metrics, and costs

-- LLM Providers registry
CREATE TABLE IF NOT EXISTS llm_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,  -- ollama, localai, claude, openai
    display_name TEXT NOT NULL,
    provider_type TEXT NOT NULL,  -- local, remote
    base_url TEXT,
    is_enabled INTEGER DEFAULT 1,
    priority INTEGER DEFAULT 0,  -- lower = higher priority
    timeout_seconds INTEGER DEFAULT 60,
    circuit_breaker_threshold INTEGER DEFAULT 5,
    circuit_breaker_timeout INTEGER DEFAULT 300,
    metadata TEXT,  -- JSON for additional config
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- LLM Request metrics
CREATE TABLE IF NOT EXISTS llm_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL,
    session_id TEXT,  -- Claude session, workflow ID, etc.
    model TEXT,  -- llama3.2, claude-sonnet-4-5, gpt-4, etc.
    endpoint TEXT,  -- generate, chat/completions, etc.
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    duration_seconds REAL,
    status TEXT NOT NULL,  -- success, failed, timeout
    error_message TEXT,
    cost_usd REAL DEFAULT 0.0,  -- calculated cost
    is_fallback INTEGER DEFAULT 0,  -- 1 if this was a fallback attempt
    original_provider_id INTEGER,  -- if fallback, which provider failed
    user_id TEXT,
    request_metadata TEXT,  -- JSON for prompt, response, context
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES llm_providers(id)
);

-- LLM Provider health/circuit breaker state
CREATE TABLE IF NOT EXISTS llm_provider_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL,
    is_available INTEGER DEFAULT 1,
    failure_count INTEGER DEFAULT 0,
    last_failure_at TIMESTAMP,
    last_success_at TIMESTAMP,
    circuit_state TEXT DEFAULT 'closed',  -- closed, open, half_open
    total_requests INTEGER DEFAULT 0,
    successful_requests INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    avg_response_time_ms REAL DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES llm_providers(id),
    UNIQUE(provider_id)
);

-- LLM Cost tracking (aggregated by day/provider)
CREATE TABLE IF NOT EXISTS llm_costs_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL,
    date TEXT NOT NULL,  -- YYYY-MM-DD
    total_requests INTEGER DEFAULT 0,
    successful_requests INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0.0,
    estimated_savings_usd REAL DEFAULT 0.0,  -- vs remote providers
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES llm_providers(id),
    UNIQUE(provider_id, date)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_llm_requests_provider ON llm_requests(provider_id);
CREATE INDEX IF NOT EXISTS idx_llm_requests_created ON llm_requests(created_at);
CREATE INDEX IF NOT EXISTS idx_llm_requests_status ON llm_requests(status);
CREATE INDEX IF NOT EXISTS idx_llm_costs_date ON llm_costs_daily(date);
CREATE INDEX IF NOT EXISTS idx_llm_costs_provider ON llm_costs_daily(provider_id);

-- Insert default providers
INSERT OR IGNORE INTO llm_providers (name, display_name, provider_type, base_url, priority, is_enabled) VALUES
    ('ollama', 'Ollama (Local)', 'local', 'http://localhost:11434', 1, 1),
    ('localai', 'LocalAI', 'local', 'http://localhost:8080', 2, 1),
    ('claude', 'Claude (Anthropic)', 'remote', 'https://api.anthropic.com', 3, 1),
    ('openai', 'OpenAI GPT-4', 'remote', 'https://api.openai.com', 4, 1);

-- Initialize health records for each provider
INSERT OR IGNORE INTO llm_provider_health (provider_id, is_available, circuit_state)
SELECT id, 1, 'closed' FROM llm_providers;
