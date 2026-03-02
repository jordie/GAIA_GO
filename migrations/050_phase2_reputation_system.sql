-- Phase 2 Sprint 1: Reputation System Migration

-- Reputation Scores Table
CREATE TABLE IF NOT EXISTS reputation_scores (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    score INTEGER NOT NULL DEFAULT 50,
    tier VARCHAR(20) NOT NULL DEFAULT 'standard',
    multiplier DECIMAL(3,2) NOT NULL DEFAULT 1.0,
    vip_tier VARCHAR(20),
    vip_expires_at TIMESTAMP WITH TIME ZONE,
    violation_count INTEGER NOT NULL DEFAULT 0,
    clean_requests INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Reputation Events Table (audit trail)
CREATE TABLE IF NOT EXISTS reputation_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    event_type VARCHAR(20) NOT NULL, -- violation, clean, decay, manual
    severity INTEGER DEFAULT 0,
    description TEXT,
    score_delta INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES reputation_scores(user_id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_reputation_scores_user_id ON reputation_scores(user_id);
CREATE INDEX idx_reputation_scores_tier ON reputation_scores(tier);
CREATE INDEX idx_reputation_scores_score ON reputation_scores(score);
CREATE INDEX idx_reputation_events_user_id ON reputation_events(user_id);
CREATE INDEX idx_reputation_events_event_type ON reputation_events(event_type);
CREATE INDEX idx_reputation_events_created_at ON reputation_events(created_at DESC);
CREATE INDEX idx_reputation_events_user_created ON reputation_events(user_id, created_at DESC);

-- View for reputation statistics
CREATE VIEW reputation_stats AS
SELECT
    COUNT(*) as total_users,
    SUM(CASE WHEN tier = 'flagged' THEN 1 ELSE 0 END) as flagged_count,
    SUM(CASE WHEN tier = 'standard' THEN 1 ELSE 0 END) as standard_count,
    SUM(CASE WHEN tier = 'trusted' THEN 1 ELSE 0 END) as trusted_count,
    SUM(CASE WHEN tier = 'premium' OR vip_tier = 'premium' THEN 1 ELSE 0 END) as premium_count,
    ROUND(AVG(score)::numeric, 2) as avg_score,
    MAX(score) as max_score,
    MIN(score) as min_score,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY score) as median_score,
    SUM(violation_count) as total_violations,
    SUM(clean_requests) as total_clean_requests
FROM reputation_scores;

-- View for active VIP users
CREATE VIEW vip_users AS
SELECT
    user_id,
    vip_tier,
    vip_expires_at,
    score,
    multiplier,
    CASE WHEN vip_expires_at IS NOT NULL AND vip_expires_at > CURRENT_TIMESTAMP THEN true ELSE false END as is_active
FROM reputation_scores
WHERE vip_tier IS NOT NULL;
