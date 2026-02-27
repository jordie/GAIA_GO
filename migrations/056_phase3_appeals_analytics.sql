-- Phase 3 Sprint 2: Appeal Management & Advanced Analytics

-- Appeals Table
CREATE TABLE IF NOT EXISTS appeals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    violation_id INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    priority VARCHAR(50) NOT NULL DEFAULT 'medium',
    reason VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    evidence TEXT, -- JSON array of file URLs
    reputation_lost DECIMAL(10,2) NOT NULL,
    requested_action VARCHAR(50) NOT NULL,
    reviewed_by VARCHAR(100),
    review_comment TEXT,
    resolution VARCHAR(100),
    approved_points DECIMAL(10,2),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- Appeal Reasons Reference Table
CREATE TABLE IF NOT EXISTS appeal_reasons (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    priority VARCHAR(50) NOT NULL DEFAULT 'medium',
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Appeals
CREATE INDEX idx_appeals_user_id ON appeals(user_id);
CREATE INDEX idx_appeals_violation_id ON appeals(violation_id);
CREATE INDEX idx_appeals_status ON appeals(status);
CREATE INDEX idx_appeals_priority ON appeals(priority);
CREATE INDEX idx_appeals_created_at ON appeals(created_at DESC);
CREATE INDEX idx_appeals_expires_at ON appeals(expires_at);
CREATE INDEX idx_appeals_user_status ON appeals(user_id, status);

-- Views for Appeal Analytics

-- View: Appeal Summary
CREATE VIEW appeal_summary AS
SELECT
    COUNT(*) as total_appeals,
    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_appeals,
    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved_appeals,
    SUM(CASE WHEN status = 'denied' THEN 1 ELSE 0 END) as denied_appeals,
    ROUND(
        SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END)::numeric /
        NULLIF(SUM(CASE WHEN status IN ('approved', 'denied') THEN 1 ELSE 0 END), 0) * 100,
        2
    ) as approval_rate,
    ROUND(AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600), 2) as avg_resolution_hours,
    COALESCE(SUM(CASE WHEN status = 'approved' THEN approved_points ELSE 0 END), 0) as total_points_restored
FROM appeals;

-- View: User Appeal History
CREATE VIEW user_appeal_history AS
SELECT
    user_id,
    COUNT(*) as total_appeals,
    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved_count,
    SUM(CASE WHEN status = 'denied' THEN 1 ELSE 0 END) as denied_count,
    SUM(CASE WHEN status IN ('pending', 'reviewing') THEN 1 ELSE 0 END) as pending_count,
    ROUND(
        SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END)::numeric /
        NULLIF(SUM(CASE WHEN status IN ('approved', 'denied') THEN 1 ELSE 0 END), 0) * 100,
        2
    ) as approval_rate,
    COALESCE(SUM(CASE WHEN status = 'approved' THEN approved_points ELSE 0 END), 0) as total_points_restored,
    MAX(created_at) as last_appeal_date
FROM appeals
GROUP BY user_id;

-- View: Appeal Trend Analysis
CREATE VIEW appeal_trend_analysis AS
SELECT
    DATE_TRUNC('week', created_at) as week,
    COUNT(*) as weekly_appeals,
    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved_this_week,
    SUM(CASE WHEN status = 'denied' THEN 1 ELSE 0 END) as denied_this_week,
    ROUND(
        SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END)::numeric /
        NULLIF(SUM(CASE WHEN status IN ('approved', 'denied') THEN 1 ELSE 0 END), 0) * 100,
        2
    ) as weekly_approval_rate
FROM appeals
WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '90 days'
GROUP BY DATE_TRUNC('week', created_at)
ORDER BY week DESC;

-- View: Pending Appeals Queue
CREATE VIEW pending_appeals_queue AS
SELECT
    id,
    user_id,
    violation_id,
    priority,
    reason,
    created_at,
    EXTRACT(DAY FROM (CURRENT_TIMESTAMP - created_at))::int as days_pending,
    CASE
        WHEN priority = 'critical' THEN 1
        WHEN priority = 'high' THEN 2
        WHEN priority = 'medium' THEN 3
        ELSE 4
    END as sort_order
FROM appeals
WHERE status IN ('pending', 'reviewing')
ORDER BY sort_order, created_at ASC;

-- Analytics Tables

-- Reputation Trends Table (aggregated daily)
CREATE TABLE IF NOT EXISTS reputation_trends (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    trend_date DATE NOT NULL,
    avg_score DECIMAL(10,2),
    max_score DECIMAL(10,2),
    min_score DECIMAL(10,2),
    tier VARCHAR(50),
    violation_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Behavior Patterns Log
CREATE TABLE IF NOT EXISTS behavior_patterns_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    pattern_type VARCHAR(100) NOT NULL,
    frequency INTEGER,
    last_detected TIMESTAMP WITH TIME ZONE,
    severity INTEGER,
    impact DECIMAL(10,2),
    month DATE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- User Analytics Summary
CREATE TABLE IF NOT EXISTS user_analytics_summary (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    trend_direction VARCHAR(50), -- improving, declining, stable
    volatility DECIMAL(10,2),
    avg_daily_score DECIMAL(10,2),
    peak_score DECIMAL(10,2),
    lowest_score DECIMAL(10,2),
    projected_30day_score DECIMAL(10,2),
    peak_usage_hour INTEGER,
    shift_pattern VARCHAR(50), -- day, night, mixed
    last_updated TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Analytics
CREATE INDEX idx_reputation_trends_user ON reputation_trends(user_id, trend_date DESC);
CREATE INDEX idx_behavior_patterns_user ON behavior_patterns_log(user_id, month DESC);
CREATE INDEX idx_user_analytics_summary_user ON user_analytics_summary(user_id);

-- Views for Trend Analysis

-- View: Improvement Candidates (users showing positive trends)
CREATE VIEW improvement_candidates AS
SELECT
    user_id,
    volatility,
    avg_daily_score,
    trend_direction,
    projected_30day_score,
    ROUND((projected_30day_score - avg_daily_score), 2) as expected_gain
FROM user_analytics_summary
WHERE trend_direction = 'improving'
AND projected_30day_score > avg_daily_score
ORDER BY expected_gain DESC;

-- View: At-Risk Users (declining trend or low score)
CREATE VIEW at_risk_users AS
SELECT
    user_id,
    avg_daily_score,
    trend_direction,
    volatility,
    projected_30day_score,
    CASE
        WHEN avg_daily_score < 20 THEN 'critical'
        WHEN avg_daily_score < 50 AND trend_direction = 'declining' THEN 'warning'
        WHEN trend_direction = 'declining' THEN 'watch'
        ELSE 'normal'
    END as risk_level
FROM user_analytics_summary
WHERE trend_direction IN ('declining', 'stable')
OR avg_daily_score < 50
ORDER BY risk_level, avg_daily_score ASC;

-- View: Usage Pattern Distribution
CREATE VIEW usage_pattern_distribution AS
SELECT
    shift_pattern,
    COUNT(*) as user_count,
    ROUND(AVG(avg_daily_score), 2) as avg_score_by_pattern,
    ROUND(AVG(volatility), 2) as avg_volatility
FROM user_analytics_summary
WHERE shift_pattern IS NOT NULL
GROUP BY shift_pattern;
