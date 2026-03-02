-- Phase 3 Sprint 4: Advanced Appeal Features & UI Components

-- Appeal Negotiation Messages
CREATE TABLE IF NOT EXISTS appeal_negotiation_messages (
    id SERIAL PRIMARY KEY,
    appeal_id INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,                      -- User or admin ID
    sender_type VARCHAR(50) NOT NULL,               -- 'user' or 'admin'
    message TEXT NOT NULL,
    message_type VARCHAR(50) DEFAULT 'message',     -- message, question, clarification, proposal
    metadata JSONB,                                 -- Additional context (proposals, etc.)
    attachment_urls TEXT[],                         -- Array of file URLs
    sentiment_score DECIMAL(3,2),                   -- AI-calculated sentiment (-1 to 1)
    language_score DECIMAL(3,2),                    -- Quality score (0 to 1)
    is_pinned BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appeal_id) REFERENCES appeals(id)
);

-- Appeal Mediation Records
CREATE TABLE IF NOT EXISTS appeal_mediations (
    id SERIAL PRIMARY KEY,
    appeal_id INTEGER NOT NULL UNIQUE,
    initiator_id INTEGER,                           -- Who requested mediation
    mediator_id INTEGER,                            -- Admin mediator assigned
    mediation_status VARCHAR(50) DEFAULT 'proposed', -- proposed, accepted, in_progress, resolved, failed
    dispute_reason TEXT,
    mediator_notes TEXT,
    resolution_recommendation VARCHAR(500),         -- Mediator's suggested resolution
    final_resolution VARCHAR(100),                  -- Final outcome: approved, denied, compromise
    final_approved_points DECIMAL(10,2),
    compromise_details JSONB,                       -- Details of any compromise
    started_at TIMESTAMP WITH TIME ZONE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appeal_id) REFERENCES appeals(id)
);

-- ML Predictions Cache
CREATE TABLE IF NOT EXISTS ml_predictions (
    id SERIAL PRIMARY KEY,
    appeal_id INTEGER,                              -- NULL for user-wide predictions
    user_id INTEGER,                                -- Required for user-wide predictions
    prediction_type VARCHAR(50) NOT NULL,          -- recovery_timeline, approval_probability, language_quality
    prediction_value DECIMAL(10,4),
    confidence DECIMAL(3,2),                        -- 0.0-1.0
    supporting_factors JSONB,                       -- Features used in prediction
    model_version VARCHAR(20),                      -- e.g., "v1.0", "v2.1"
    predicted_at TIMESTAMP WITH TIME ZONE,
    actual_value DECIMAL(10,4),                     -- Ground truth after resolved
    accuracy_checked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Enhanced Appeal Classifications (extended from Sprint 3)
CREATE TABLE IF NOT EXISTS appeal_classifications_extended (
    id SERIAL PRIMARY KEY,
    appeal_id INTEGER NOT NULL UNIQUE,
    primary_classification VARCHAR(100),             -- false_positive, policy_edge_case, system_error, user_error
    secondary_classifications TEXT[],                -- Additional tags
    confidence DECIMAL(3,2),                         -- 0.0-1.0
    is_auto_approvable BOOLEAN DEFAULT false,       -- Auto-approve candidate?
    auto_approve_confidence DECIMAL(3,2),
    classification_reason TEXT,
    classified_by VARCHAR(100),                      -- 'ml_model_v1.0' or admin username
    classification_features JSONB,                   -- Features used
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appeal_id) REFERENCES appeals(id)
);

-- Appeal Language Analysis
CREATE TABLE IF NOT EXISTS appeal_language_analysis (
    id SERIAL PRIMARY KEY,
    appeal_id INTEGER NOT NULL UNIQUE,
    overall_quality_score DECIMAL(3,2),             -- 0.0-1.0
    clarity_score DECIMAL(3,2),
    evidence_quality_score DECIMAL(3,2),
    tone_score DECIMAL(3,2),                        -- 0=negative, 0.5=neutral, 1=positive
    persuasiveness_score DECIMAL(3,2),
    readability_grade INTEGER,                      -- Flesch-Kincaid grade level
    word_count INTEGER,
    sentiment_classification VARCHAR(50),           -- positive, neutral, negative
    tone_analysis TEXT,                             -- Professional, emotional, defensive, etc.
    suggestions TEXT[],                             -- Improvement suggestions
    analyzed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Auto-Appeal Suggestions
CREATE TABLE IF NOT EXISTS auto_appeal_suggestions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    violation_id INTEGER NOT NULL,
    suggestion_reason VARCHAR(100),                 -- high_confidence_fp, pattern_match, similar_success
    confidence DECIMAL(3,2),                        -- 0.0-1.0
    predicted_success_rate DECIMAL(3,2),            -- 0.0-1.0
    suggested_strategy TEXT,
    supporting_evidence TEXT[],
    similar_success_count INTEGER,                  -- Similar appeals that succeeded
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_accepted BOOLEAN,
    appeal_created_from_suggestion BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- User Appeal Statistics (aggregated)
CREATE TABLE IF NOT EXISTS user_appeal_statistics (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    total_appeals INTEGER DEFAULT 0,
    successful_appeals INTEGER DEFAULT 0,
    appeal_success_rate DECIMAL(5,2),               -- 0.0-100.0
    avg_appeal_resolution_days DECIMAL(8,2),
    avg_message_count_per_appeal INTEGER,
    negotiation_count INTEGER DEFAULT 0,
    mediation_count INTEGER DEFAULT 0,
    auto_appeal_count INTEGER DEFAULT 0,
    estimated_next_appeal_success DECIMAL(3,2),    -- Predicted based on history
    last_updated TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast querying
CREATE INDEX idx_appeal_negotiation_messages_appeal ON appeal_negotiation_messages(appeal_id, created_at DESC);
CREATE INDEX idx_appeal_negotiation_messages_sender ON appeal_negotiation_messages(sender_id, created_at DESC);
CREATE INDEX idx_appeal_mediations_appeal ON appeal_mediations(appeal_id);
CREATE INDEX idx_appeal_mediations_status ON appeal_mediations(mediation_status);
CREATE INDEX idx_ml_predictions_appeal ON ml_predictions(appeal_id);
CREATE INDEX idx_ml_predictions_user ON ml_predictions(user_id, prediction_type);
CREATE INDEX idx_ml_predictions_type ON ml_predictions(prediction_type, created_at DESC);
CREATE INDEX idx_appeal_classifications_ext_appeal ON appeal_classifications_extended(appeal_id);
CREATE INDEX idx_auto_appeal_suggestions_user ON auto_appeal_suggestions(user_id, generated_at DESC);
CREATE INDEX idx_auto_appeal_suggestions_confidence ON auto_appeal_suggestions(confidence DESC);
CREATE INDEX idx_user_appeal_statistics_user ON user_appeal_statistics(user_id);

-- Views for Analysis

-- View: Negotiation Activity
CREATE VIEW negotiation_activity AS
SELECT
    a.id as appeal_id,
    a.user_id,
    COUNT(anm.id) as message_count,
    COUNT(CASE WHEN anm.sender_type = 'user' THEN 1 END) as user_messages,
    COUNT(CASE WHEN anm.sender_type = 'admin' THEN 1 END) as admin_messages,
    AVG(anm.sentiment_score) as avg_sentiment,
    AVG(anm.language_score) as avg_language_quality,
    MIN(anm.created_at) as first_message,
    MAX(anm.created_at) as last_message
FROM appeals a
LEFT JOIN appeal_negotiation_messages anm ON a.id = anm.appeal_id
WHERE a.status IN ('reviewing', 'pending')
GROUP BY a.id, a.user_id;

-- View: Mediation Queue
CREATE VIEW mediation_queue AS
SELECT
    am.id as mediation_id,
    a.id as appeal_id,
    a.user_id,
    a.status as appeal_status,
    am.mediation_status,
    am.dispute_reason,
    EXTRACT(DAY FROM (CURRENT_TIMESTAMP - am.created_at)) as days_pending,
    CASE
        WHEN am.mediation_status = 'proposed' THEN 1
        WHEN am.mediation_status = 'accepted' THEN 2
        WHEN am.mediation_status = 'in_progress' THEN 3
        ELSE 4
    END as priority_order
FROM appeal_mediations am
JOIN appeals a ON am.appeal_id = a.id
WHERE am.mediation_status IN ('proposed', 'accepted', 'in_progress')
ORDER BY priority_order, am.created_at ASC;

-- View: ML Model Performance
CREATE VIEW ml_model_performance AS
SELECT
    prediction_type,
    model_version,
    COUNT(*) as total_predictions,
    COUNT(CASE WHEN accuracy_checked_at IS NOT NULL THEN 1 END) as verified_predictions,
    AVG(confidence) as avg_confidence,
    ROUND(
        COUNT(CASE
            WHEN actual_value IS NOT NULL
            AND ROUND(ABS(prediction_value - actual_value), 2) < 0.1
            THEN 1
        END)::numeric / NULLIF(COUNT(CASE WHEN actual_value IS NOT NULL THEN 1 END), 0) * 100,
        2
    ) as accuracy_percent
FROM ml_predictions
WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '90 days'
GROUP BY prediction_type, model_version;

-- View: Auto-Appeal Recommendation Effectiveness
CREATE VIEW auto_appeal_effectiveness AS
SELECT
    suggestion_reason,
    COUNT(*) as total_suggestions,
    COUNT(CASE WHEN user_accepted THEN 1 END) as accepted_suggestions,
    COUNT(CASE WHEN appeal_created_from_suggestion THEN 1 END) as appeals_created,
    ROUND(
        COUNT(CASE WHEN user_accepted THEN 1 END)::numeric / COUNT(*) * 100,
        2
    ) as acceptance_rate
FROM auto_appeal_suggestions
WHERE generated_at > CURRENT_TIMESTAMP - INTERVAL '30 days'
GROUP BY suggestion_reason;

-- View: User Appeal Analytics
CREATE VIEW user_appeal_analytics AS
SELECT
    uas.user_id,
    uas.total_appeals,
    uas.successful_appeals,
    uas.appeal_success_rate,
    uas.negotiation_count,
    uas.mediation_count,
    uas.auto_appeal_count,
    COUNT(DISTINCT CASE WHEN anm.sender_type = 'user' THEN anm.appeal_id END) as appeals_with_negotiation,
    COUNT(DISTINCT am.appeal_id) as appeals_with_mediation,
    ROUND(AVG(aca.overall_quality_score), 2) as avg_language_quality
FROM user_appeal_statistics uas
LEFT JOIN appeal_negotiation_messages anm ON uas.user_id = anm.sender_id AND anm.sender_type = 'user'
LEFT JOIN appeal_mediations am ON uas.user_id = (SELECT user_id FROM appeals WHERE id = am.appeal_id)
LEFT JOIN appeal_language_analysis aca ON aca.appeal_id IN (SELECT id FROM appeals WHERE user_id = uas.user_id)
GROUP BY uas.user_id, uas.total_appeals, uas.successful_appeals, uas.appeal_success_rate,
         uas.negotiation_count, uas.mediation_count, uas.auto_appeal_count;
