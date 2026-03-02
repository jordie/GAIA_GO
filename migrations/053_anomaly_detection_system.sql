-- Phase 2 Sprint 3: Anomaly Detection System Migration

-- Anomaly Patterns Table
CREATE TABLE IF NOT EXISTS anomaly_patterns (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    pattern_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    score DECIMAL(5,2) NOT NULL,
    confidence DECIMAL(3,2) NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    resolved BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- User Behavior Profiles Table
CREATE TABLE IF NOT EXISTS user_behavior_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    avg_requests_per_hour DECIMAL(10,2) NOT NULL,
    std_dev_requests DECIMAL(10,2) NOT NULL,
    peak_hour INTEGER NOT NULL,
    peak_day_of_week INTEGER NOT NULL,
    avg_response_time DECIMAL(10,2) NOT NULL,
    common_resources TEXT,
    violation_rate DECIMAL(5,2) NOT NULL,
    last_analyzed TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Performance
CREATE INDEX idx_anomaly_patterns_user_id ON anomaly_patterns(user_id);
CREATE INDEX idx_anomaly_patterns_pattern_type ON anomaly_patterns(pattern_type);
CREATE INDEX idx_anomaly_patterns_resolved ON anomaly_patterns(resolved);
CREATE INDEX idx_anomaly_patterns_created_at ON anomaly_patterns(created_at DESC);
CREATE INDEX idx_anomaly_patterns_score ON anomaly_patterns(score DESC);
CREATE INDEX idx_behavior_profiles_user_id ON user_behavior_profiles(user_id);

-- View for Current Anomalies
CREATE VIEW current_anomalies AS
SELECT
    ap.id,
    ap.user_id,
    ap.pattern_type,
    ap.description,
    ap.score,
    ap.confidence,
    ap.start_time,
    CURRENT_TIMESTAMP - ap.start_time as duration,
    CASE
        WHEN ap.score >= 80 THEN 'critical'
        WHEN ap.score >= 60 THEN 'high'
        WHEN ap.score >= 40 THEN 'medium'
        ELSE 'low'
    END as severity
FROM anomaly_patterns ap
WHERE ap.resolved = false
ORDER BY ap.score DESC, ap.created_at DESC;

-- View for Anomaly Summary
CREATE VIEW anomaly_summary AS
SELECT
    COUNT(*) as total_anomalies,
    SUM(CASE WHEN pattern_type = 'critical' THEN 1 ELSE 0 END) as critical_count,
    SUM(CASE WHEN pattern_type = 'high' THEN 1 ELSE 0 END) as high_count,
    SUM(CASE WHEN pattern_type = 'medium' THEN 1 ELSE 0 END) as medium_count,
    SUM(CASE WHEN pattern_type = 'low' THEN 1 ELSE 0 END) as low_count,
    SUM(CASE WHEN resolved = false THEN 1 ELSE 0 END) as unresolved_count,
    ROUND(AVG(score), 2) as average_score,
    ROUND(AVG(confidence), 2) as average_confidence
FROM anomaly_patterns;

-- View for User Anomaly Risk
CREATE VIEW user_anomaly_risk AS
SELECT
    ap.user_id,
    COUNT(*) as total_patterns,
    SUM(CASE WHEN ap.resolved = false THEN 1 ELSE 0 END) as active_patterns,
    MAX(ap.score) as max_anomaly_score,
    ROUND(AVG(ap.score), 2) as avg_anomaly_score,
    MAX(ap.created_at) as last_anomaly
FROM anomaly_patterns ap
GROUP BY ap.user_id
ORDER BY max_anomaly_score DESC;
