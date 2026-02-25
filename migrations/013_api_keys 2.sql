-- Migration: Add API key authentication
-- Enables programmatic API access without session-based login

CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_id TEXT UNIQUE NOT NULL,
    key_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    user_id TEXT NOT NULL,
    scopes TEXT DEFAULT 'read',
    rate_limit INTEGER DEFAULT 1000,
    expires_at TIMESTAMP,
    last_used_at TIMESTAMP,
    last_used_ip TEXT,
    use_count INTEGER DEFAULT 0,
    enabled BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- API key usage log for auditing
CREATE TABLE IF NOT EXISTS api_key_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER,
    ip_address TEXT,
    user_agent TEXT,
    response_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (key_id) REFERENCES api_keys(key_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_api_keys_key_id ON api_keys(key_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_enabled ON api_keys(enabled);
CREATE INDEX IF NOT EXISTS idx_api_key_usage_key ON api_key_usage(key_id);
CREATE INDEX IF NOT EXISTS idx_api_key_usage_created ON api_key_usage(created_at);
