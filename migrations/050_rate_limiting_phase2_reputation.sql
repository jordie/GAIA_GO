-- Phase 2: Advanced Rate Limiting Features - Reputation System
-- Status: Sprint 1 Foundation
-- Created: 2026-02-25

-- User Reputation Scores
CREATE TABLE IF NOT EXISTS user_reputation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    reputation_score REAL DEFAULT 50.0,
    tier TEXT DEFAULT 'standard',
    last_violation TIMESTAMP,
    total_violations INTEGER DEFAULT 0,
    total_clean_requests INTEGER DEFAULT 0,
    decay_last_applied TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_reputation_score ON user_reputation(reputation_score);
CREATE INDEX idx_reputation_user ON user_reputation(user_id);
CREATE INDEX idx_reputation_tier ON user_reputation(tier);

-- Reputation Events (audit trail)
CREATE TABLE IF NOT EXISTS reputation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    severity INTEGER DEFAULT 1,
    description TEXT,
    score_delta REAL DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_reputation(user_id)
);

CREATE INDEX idx_reputation_events_user ON reputation_events(user_id, timestamp);
CREATE INDEX idx_reputation_events_type ON reputation_events(event_type, timestamp);

-- VIP User Tiers (manual override)
CREATE TABLE IF NOT EXISTS vip_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    tier TEXT NOT NULL,
    limit_multiplier REAL DEFAULT 1.0,
    notes TEXT,
    approved_by INTEGER,
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_reputation(user_id)
);

CREATE INDEX idx_vip_tier ON vip_users(tier);
CREATE INDEX idx_vip_multiplier ON vip_users(limit_multiplier);

-- Reputation Configuration
CREATE TABLE IF NOT EXISTS reputation_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key TEXT NOT NULL UNIQUE,
    config_value TEXT NOT NULL,
    description TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO reputation_config (config_key, config_value, description) VALUES
    ('initial_score', '50', 'Initial reputation score for new users'),
    ('min_score', '0', 'Minimum possible reputation score'),
    ('max_score', '100', 'Maximum possible reputation score'),
    ('violation_penalty', '5', 'Points deducted per violation'),
    ('attack_penalty', '10', 'Points deducted for suspected attacks'),
    ('clean_request_reward', '0.5', 'Points added per 100 clean requests'),
    ('daily_decay_rate', '0.99', 'Decay multiplier per day (forgiveness factor)'),
    ('tier_excellent', '90', 'Reputation score for excellent tier (1.5x limits)'),
    ('tier_good', '75', 'Reputation score for good tier (1.2x limits)'),
    ('tier_neutral', '50', 'Reputation score for neutral tier (1.0x limits)'),
    ('tier_caution', '25', 'Reputation score for caution tier (0.8x limits)'),
    ('tier_restricted', '0', 'Reputation score for restricted tier (0.5x limits)');

-- Limits by Reputation Tier
CREATE TABLE IF NOT EXISTS reputation_limit_tiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tier_name TEXT NOT NULL UNIQUE,
    min_score REAL NOT NULL,
    max_score REAL NOT NULL,
    limit_multiplier REAL NOT NULL,
    description TEXT,
    color_code TEXT
);

INSERT OR IGNORE INTO reputation_limit_tiers (tier_name, min_score, max_score, limit_multiplier, description, color_code) VALUES
    ('excellent', 90, 100, 2.0, 'Highly trusted users, 2x request limits', '#4CAF50'),
    ('good', 75, 89, 1.5, 'Trusted users, 1.5x request limits', '#8BC34A'),
    ('neutral', 50, 74, 1.0, 'Normal users, standard request limits', '#2196F3'),
    ('caution', 25, 49, 0.8, 'Cautious users, 0.8x request limits', '#FF9800'),
    ('restricted', 0, 24, 0.5, 'Restricted users, 0.5x request limits', '#F44336');

-- Feature Flag for Reputation System
CREATE TABLE IF NOT EXISTS feature_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_name TEXT NOT NULL UNIQUE,
    enabled BOOLEAN DEFAULT 0,
    rollout_percentage INTEGER DEFAULT 0,
    config JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO feature_flags (feature_name, enabled, rollout_percentage, config) VALUES
    ('reputation_system', 0, 0, '{"auto_adjust_limits": false, "decay_enabled": true, "min_events_for_calculation": 10}'),
    ('adaptive_limiting', 0, 0, '{"vip_tiers_enabled": false, "behavioral_learning": false, "load_adjustment": false}'),
    ('anomaly_detection', 0, 0, '{"enabled": false, "confidence_threshold": 0.8, "min_baseline_days": 7}');

-- Rate Limit Configuration
CREATE TABLE IF NOT EXISTS rate_limit_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT NOT NULL UNIQUE,
    scope TEXT NOT NULL,
    scope_value TEXT,
    limit_type TEXT NOT NULL,
    limit_value INTEGER NOT NULL,
    resource_type TEXT,
    enabled BOOLEAN DEFAULT 1,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Default rate limit rules
INSERT OR IGNORE INTO rate_limit_rules (rule_name, scope, limit_type, limit_value, description) VALUES
    ('global_default', 'global', 'requests_per_minute', 1000, 'Default global limit'),
    ('login_limit', 'resource', 'requests_per_minute', 100, 'Login endpoint rate limit'),
    ('create_limit', 'resource', 'requests_per_minute', 500, 'Create endpoint rate limit'),
    ('upload_limit', 'resource', 'requests_per_minute', 200, 'Upload endpoint rate limit');
