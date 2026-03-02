-- Phase 3 Sprint 3: Appeal Workflow Enhancements & Advanced Analytics

-- Rejection Reasons Reference Table
CREATE TABLE IF NOT EXISTS appeal_rejection_reasons (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    category VARCHAR(50),           -- policy_violation, insufficient_evidence, appeals_limit, other
    requires_explanation BOOLEAN DEFAULT true,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Appeal Status Changes Audit Log
CREATE TABLE IF NOT EXISTS appeal_status_changes (
    id SERIAL PRIMARY KEY,
    appeal_id INTEGER NOT NULL,
    user_id INTEGER,                -- User who made the change (NULL for system)
    old_status VARCHAR(50) NOT NULL,
    new_status VARCHAR(50) NOT NULL,
    changed_by VARCHAR(100),        -- Username or system identifier
    reason TEXT,                    -- Why the status changed
    metadata JSONB,                 -- Additional context (e.g., approval points)
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appeal_id) REFERENCES appeals(id)
);

-- Appeal Notifications Tracking
CREATE TABLE IF NOT EXISTS appeal_notifications (
    id SERIAL PRIMARY KEY,
    appeal_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    notification_type VARCHAR(50) NOT NULL,  -- submitted, approved, denied, expired, status_update
    channel VARCHAR(50) NOT NULL,            -- email, in_app, sms
    recipient VARCHAR(255) NOT NULL,        -- Email or phone
    subject TEXT,
    body TEXT,
    status VARCHAR(50) DEFAULT 'pending',    -- pending, sent, failed, bounced
    error_message TEXT,
    sent_at TIMESTAMP WITH TIME ZONE,
    opened_at TIMESTAMP WITH TIME ZONE,
    clicked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appeal_id) REFERENCES appeals(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Peer Reputation Statistics (aggregated daily)
CREATE TABLE IF NOT EXISTS peer_reputation_stats (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL,
    tier VARCHAR(50) NOT NULL,      -- flagged, standard, trusted, vip
    total_users INTEGER,
    avg_score DECIMAL(10,2),
    median_score DECIMAL(10,2),
    min_score DECIMAL(10,2),
    max_score DECIMAL(10,2),
    stddev_score DECIMAL(10,2),
    percentile_10 DECIMAL(10,2),
    percentile_25 DECIMAL(10,2),
    percentile_75 DECIMAL(10,2),
    percentile_90 DECIMAL(10,2),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- User Peer Comparison Cache
CREATE TABLE IF NOT EXISTS user_peer_comparison (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    tier VARCHAR(50),
    score DECIMAL(10,2),
    peer_avg_score DECIMAL(10,2),
    peer_percentile DECIMAL(10,2),  -- 0-100, user's position in tier
    rank_in_tier INTEGER,            -- Rank among users in same tier
    total_in_tier INTEGER,           -- Total users in this tier
    better_than_percent DECIMAL(5,2), -- % of users with lower score in tier
    trend_vs_peers VARCHAR(50),      -- improving, declining, stable vs peers
    last_updated TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Appeal Classification
CREATE TABLE IF NOT EXISTS appeal_classifications (
    id SERIAL PRIMARY KEY,
    appeal_id INTEGER NOT NULL UNIQUE,
    classification_type VARCHAR(50),   -- false_positive, policy_edge_case, system_error, user_error
    confidence DECIMAL(3,2),           -- 0.0-1.0
    classification_reason TEXT,
    classified_by VARCHAR(100),        -- admin or system
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appeal_id) REFERENCES appeals(id)
);

-- Reputation Recovery Predictions
CREATE TABLE IF NOT EXISTS reputation_recovery_predictions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    current_score DECIMAL(10,2),
    target_score DECIMAL(10,2),        -- User's desired score
    days_to_target INTEGER,            -- Estimated days at current trajectory
    weekly_change_rate DECIMAL(10,2),  -- Points per week
    required_actions TEXT,             -- JSON array of required actions
    confidence_level DECIMAL(3,2),     -- 0.0-1.0
    last_calculated TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Bulk Appeal Operation Logs
CREATE TABLE IF NOT EXISTS bulk_appeal_operations (
    id SERIAL PRIMARY KEY,
    operation_id VARCHAR(100) UNIQUE NOT NULL,
    admin_id INTEGER NOT NULL,
    operation_type VARCHAR(50),        -- bulk_approve, bulk_deny, bulk_priority_assign
    filter_criteria JSONB,             -- Criteria used to select appeals
    total_selected INTEGER,
    total_processed INTEGER,
    total_succeeded INTEGER,
    total_failed INTEGER,
    status VARCHAR(50) DEFAULT 'in_progress',  -- in_progress, completed, failed
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast querying
CREATE INDEX idx_appeal_status_changes_appeal ON appeal_status_changes(appeal_id);
CREATE INDEX idx_appeal_status_changes_created ON appeal_status_changes(created_at DESC);
CREATE INDEX idx_appeal_notifications_appeal ON appeal_notifications(appeal_id);
CREATE INDEX idx_appeal_notifications_user ON appeal_notifications(user_id);
CREATE INDEX idx_appeal_notifications_status ON appeal_notifications(status);
CREATE INDEX idx_peer_reputation_stats_date ON peer_reputation_stats(stat_date DESC, tier);
CREATE INDEX idx_appeal_classifications_appeal ON appeal_classifications(appeal_id);
CREATE INDEX idx_reputation_recovery_user ON reputation_recovery_predictions(user_id);
CREATE INDEX idx_bulk_operations_admin ON bulk_appeal_operations(admin_id, started_at DESC);
CREATE INDEX idx_bulk_operations_status ON bulk_appeal_operations(status);

-- Views for Appeal Timeline
CREATE VIEW appeal_timeline AS
SELECT
    a.id as appeal_id,
    a.user_id,
    a.status as current_status,
    a.created_at as submitted_at,
    sc.new_status,
    sc.changed_by,
    sc.reason as status_reason,
    sc.created_at as status_changed_at,
    sc.metadata,
    ROW_NUMBER() OVER (PARTITION BY a.id ORDER BY sc.created_at) as timeline_order
FROM appeals a
LEFT JOIN appeal_status_changes sc ON a.id = sc.appeal_id
ORDER BY a.id, sc.created_at;

-- View for Rejection Reasons Distribution
CREATE VIEW rejection_reason_distribution AS
SELECT
    arr.code,
    arr.name,
    COUNT(asc.id) as usage_count,
    COUNT(CASE WHEN asc.created_at > CURRENT_TIMESTAMP - INTERVAL '30 days' THEN 1 END) as usage_30d
FROM appeal_rejection_reasons arr
LEFT JOIN appeal_status_changes asc ON asc.metadata->>'rejection_reason' = arr.code
WHERE arr.enabled = true
GROUP BY arr.id, arr.code, arr.name;

-- View for Peer Analytics
CREATE VIEW peer_analytics_summary AS
SELECT
    user_id,
    tier,
    score,
    peer_avg_score,
    peer_percentile,
    CASE
        WHEN peer_percentile >= 90 THEN 'top_10_percent'
        WHEN peer_percentile >= 75 THEN 'top_quartile'
        WHEN peer_percentile >= 25 THEN 'middle_half'
        ELSE 'bottom_quartile'
    END as peer_rank_category,
    ROUND((score - peer_avg_score), 2) as score_vs_peer_avg,
    better_than_percent,
    trend_vs_peers,
    last_updated
FROM user_peer_comparison
WHERE last_updated > CURRENT_TIMESTAMP - INTERVAL '24 hours';
