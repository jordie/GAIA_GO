-- Phase 3 Sprint 1: User Reputation Portal Migration

-- User Reputation Views (derived data for portal)
-- These views provide the data needed for the user-facing portal

-- View: User Dashboard Summary
CREATE VIEW user_reputation_summary AS
SELECT
    rs.user_id,
    rs.score,
    rs.tier,
    CASE
        WHEN rs.score < 20 THEN 0.5
        WHEN rs.score < 80 THEN 1.0
        WHEN rs.score < 100 THEN 1.5
        ELSE 2.0
    END as multiplier,
    CASE
        WHEN rs.tier = 'flagged' THEN 20
        WHEN rs.tier = 'standard' THEN 80
        ELSE 100
    END as next_tier_score,
    rs.last_updated,
    COUNT(DISTINCT CASE WHEN re.event_type = 'violation' THEN re.id END) as violation_count,
    COUNT(DISTINCT CASE WHEN re.event_type IN ('clean_request', 'success') THEN re.id END) as clean_count,
    MAX(re.created_at) as last_activity
FROM reputation_scores rs
LEFT JOIN reputation_events re ON rs.user_id = re.user_id AND re.created_at > CURRENT_TIMESTAMP - INTERVAL '30 days'
GROUP BY rs.user_id, rs.score, rs.tier, rs.last_updated;

-- View: User Violations Summary (last 30 days)
CREATE VIEW user_violations_30day AS
SELECT
    re.user_id,
    re.id,
    re.event_type,
    re.reason_code,
    re.severity,
    CASE
        WHEN re.severity = 3 THEN 'severe'
        WHEN re.severity = 2 THEN 'moderate'
        ELSE 'minor'
    END as severity_label,
    re.score_delta,
    re.timestamp,
    re.created_at,
    (CURRENT_TIMESTAMP - re.timestamp < INTERVAL '30 days') as can_appeal
FROM reputation_events re
WHERE re.event_type = 'violation'
AND re.timestamp > CURRENT_TIMESTAMP - INTERVAL '30 days'
ORDER BY re.timestamp DESC;

-- View: User Tier Progression
CREATE VIEW user_tier_progression AS
SELECT
    rs.user_id,
    rs.score,
    rs.tier,
    CASE
        WHEN rs.tier = 'flagged' THEN 'standard'
        WHEN rs.tier = 'standard' THEN 'trusted'
        WHEN rs.tier = 'trusted' THEN 'premium_vip'
        ELSE rs.tier
    END as next_tier,
    CASE
        WHEN rs.tier = 'flagged' THEN 20.0
        WHEN rs.tier = 'standard' THEN 80.0
        WHEN rs.tier = 'trusted' THEN 100.0
        ELSE 100.0
    END as next_tier_score,
    CASE
        WHEN rs.tier = 'flagged' THEN ROUND(rs.score / 20.0 * 100, 1)
        WHEN rs.tier = 'standard' THEN ROUND(rs.score / 80.0 * 100, 1)
        WHEN rs.tier = 'trusted' THEN ROUND(rs.score / 100.0 * 100, 1)
        ELSE 100.0
    END as progress_percent,
    CASE
        WHEN rs.tier = 'flagged' THEN (20.0 - rs.score)
        WHEN rs.tier = 'standard' THEN (80.0 - rs.score)
        WHEN rs.tier = 'trusted' THEN (100.0 - rs.score)
        ELSE 0.0
    END as distance_to_next
FROM reputation_scores rs;

-- View: User Rate Limit Calculation
CREATE VIEW user_rate_limit_calc AS
SELECT
    rs.user_id,
    1000 as base_limit,
    CASE
        WHEN rs.score < 20 THEN 0.5
        WHEN rs.score < 80 THEN 1.0
        WHEN rs.score < 100 THEN 1.5
        ELSE 2.0
    END as reputation_multiplier,
    0.8 as throttle_multiplier, -- Would be dynamic from throttle_events
    CAST(1000 *
        CASE
            WHEN rs.score < 20 THEN 0.5
            WHEN rs.score < 80 THEN 1.0
            WHEN rs.score < 100 THEN 1.5
            ELSE 2.0
        END * 0.8 AS INTEGER) as final_limit
FROM reputation_scores rs;

-- View: User VIP Status
CREATE VIEW user_vip_status AS
SELECT
    COALESCE(va.user_id, rs.user_id) as user_id,
    COALESCE(va.tier, 'none') as vip_tier,
    CASE
        WHEN va.expires_at IS NULL THEN false
        WHEN va.expires_at > CURRENT_TIMESTAMP THEN true
        ELSE false
    END as active,
    va.expires_at,
    CASE
        WHEN va.expires_at IS NULL THEN NULL
        ELSE EXTRACT(DAY FROM (va.expires_at - CURRENT_TIMESTAMP))
    END as days_remaining,
    CASE
        WHEN va.tier = 'premium' THEN 2.0
        ELSE 1.5
    END as vip_multiplier
FROM reputation_scores rs
LEFT JOIN vip_assignments va ON rs.user_id = va.user_id AND va.expires_at > CURRENT_TIMESTAMP;

-- View: User Activity Heatmap
CREATE VIEW user_activity_heatmap AS
SELECT
    user_id,
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) as event_count,
    SUM(CASE WHEN event_type = 'violation' THEN 1 ELSE 0 END) as violation_count,
    SUM(CASE WHEN event_type IN ('clean_request', 'success') THEN 1 ELSE 0 END) as success_count,
    AVG(CASE WHEN event_type = 'violation' THEN score_delta ELSE NULL END) as avg_violation_impact
FROM reputation_events
WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '90 days'
GROUP BY user_id, DATE_TRUNC('hour', created_at)
ORDER BY hour DESC;

-- View: User Decay Schedule
CREATE VIEW user_decay_schedule AS
SELECT
    user_id,
    score,
    tier,
    -- Calculate days until next Monday (decay day)
    CASE
        WHEN EXTRACT(DOW FROM CURRENT_DATE) = 1 THEN 7
        ELSE (8 - EXTRACT(DOW FROM CURRENT_DATE))
    END as days_until_decay,
    -- Estimated score after decay
    CASE
        WHEN score < 20 THEN MAX(0, score - 5) -- Flagged users decay faster
        WHEN score > 50 THEN score - 2
        ELSE score -- Neutral users don't decay
    END as estimated_score_after_decay
FROM reputation_scores;

-- Indexes for performance
CREATE INDEX idx_user_reputation_summary_user ON user_reputation_summary(user_id);
CREATE INDEX idx_user_violations_30day_user ON user_violations_30day(user_id, timestamp DESC);
CREATE INDEX idx_user_tier_progression_user ON user_tier_progression(user_id);
CREATE INDEX idx_user_vip_status_user ON user_vip_status(user_id);
CREATE INDEX idx_user_activity_heatmap_user ON user_activity_heatmap(user_id, hour DESC);
CREATE INDEX idx_user_decay_schedule_user ON user_decay_schedule(user_id);

-- Portal access logging table (optional, for analytics)
CREATE TABLE IF NOT EXISTS portal_access_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    accessed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tab_viewed VARCHAR(50), -- dashboard, violations, tiers, faq
    action VARCHAR(100), -- viewed, appealed, etc
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_portal_access_user ON portal_access_log(user_id, accessed_at DESC);
CREATE INDEX idx_portal_access_tab ON portal_access_log(tab_viewed);
