-- Phase 9 Consolidation: Usability Metrics Tables
-- Real-time monitoring and frustration detection for education apps

-- Enable TimescaleDB extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Usability metrics table - Time-series metrics (TimescaleDB hypertable)
CREATE TABLE IF NOT EXISTS usability_metrics (
    id BIGSERIAL PRIMARY KEY,
    student_id VARCHAR(50) NOT NULL,
    app_name VARCHAR(50) NOT NULL,
    metric_type VARCHAR(100) NOT NULL,
    metric_value NUMERIC NOT NULL,
    metadata JSONB,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Convert to hypertable if not already
SELECT create_hypertable('usability_metrics', 'timestamp', if_not_exists => TRUE);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_usability_metrics_student_timestamp
ON usability_metrics (student_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_usability_metrics_app_timestamp
ON usability_metrics (app_name, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_usability_metrics_metric_type
ON usability_metrics (metric_type, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_usability_metrics_session
ON usability_metrics (session_id, timestamp DESC);

-- Frustration events table - Real-time alerts
CREATE TABLE IF NOT EXISTS frustration_events (
    id BIGSERIAL PRIMARY KEY,
    student_id VARCHAR(50) NOT NULL,
    app_name VARCHAR(50) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    details JSONB NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_frustration_events_student ON frustration_events(student_id);
CREATE INDEX IF NOT EXISTS idx_frustration_events_app ON frustration_events(app_name);
CREATE INDEX IF NOT EXISTS idx_frustration_events_severity ON frustration_events(severity);
CREATE INDEX IF NOT EXISTS idx_frustration_events_detected_at ON frustration_events(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_frustration_events_unresolved
ON frustration_events(resolved_at) WHERE resolved_at IS NULL;

-- Satisfaction ratings table - User feedback
CREATE TABLE IF NOT EXISTS satisfaction_ratings (
    id BIGSERIAL PRIMARY KEY,
    student_id VARCHAR(50) NOT NULL,
    app_name VARCHAR(50) NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    session_id VARCHAR(100) NOT NULL,
    feedback_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_satisfaction_ratings_student ON satisfaction_ratings(student_id);
CREATE INDEX IF NOT EXISTS idx_satisfaction_ratings_app ON satisfaction_ratings(app_name);
CREATE INDEX IF NOT EXISTS idx_satisfaction_ratings_created ON satisfaction_ratings(created_at DESC);

-- Teacher dashboard alerts table - Intervention tracking
CREATE TABLE IF NOT EXISTS teacher_dashboard_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID REFERENCES users(id) ON DELETE CASCADE,
    student_id VARCHAR(50) NOT NULL,
    app_name VARCHAR(50) NOT NULL,
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    details JSONB NOT NULL,
    acknowledged_at TIMESTAMP,
    intervention_note TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_teacher_dashboard_alerts_teacher ON teacher_dashboard_alerts(teacher_id);
CREATE INDEX IF NOT EXISTS idx_teacher_dashboard_alerts_student ON teacher_dashboard_alerts(student_id);
CREATE INDEX IF NOT EXISTS idx_teacher_dashboard_alerts_app ON teacher_dashboard_alerts(app_name);
CREATE INDEX IF NOT EXISTS idx_teacher_dashboard_alerts_severity ON teacher_dashboard_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_teacher_dashboard_alerts_created ON teacher_dashboard_alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_teacher_dashboard_alerts_acknowledged
ON teacher_dashboard_alerts(acknowledged_at) WHERE acknowledged_at IS NULL;

-- Classroom metrics snapshot table - Aggregated metrics for dashboard
CREATE TABLE IF NOT EXISTS classroom_metrics_snapshot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    classroom_id VARCHAR(100) NOT NULL,
    app_name VARCHAR(50) NOT NULL,
    student_count INT,
    struggling_student_count INT,
    average_frustration_level FLOAT,
    average_satisfaction_rating FLOAT,
    snapshot_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_classroom_metrics_snapshot_classroom ON classroom_metrics_snapshot(classroom_id);
CREATE INDEX IF NOT EXISTS idx_classroom_metrics_snapshot_created ON classroom_metrics_snapshot(created_at DESC);

-- Function to calculate frustration level from metrics
CREATE OR REPLACE FUNCTION calculate_frustration_level(
    error_count INT,
    backspace_count INT,
    hesitation_duration_seconds INT
) RETURNS VARCHAR AS $$
BEGIN
    -- Weighted scoring
    IF error_count > 5 OR backspace_count > 20 OR hesitation_duration_seconds > 60 THEN
        RETURN 'critical';
    ELSIF error_count > 3 OR backspace_count > 10 OR hesitation_duration_seconds > 30 THEN
        RETURN 'high';
    ELSIF error_count > 1 OR backspace_count > 5 OR hesitation_duration_seconds > 10 THEN
        RETURN 'medium';
    ELSE
        RETURN 'low';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- View for classroom struggle analysis
CREATE OR REPLACE VIEW classroom_struggle_analysis AS
SELECT
    fe.student_id,
    fe.app_name,
    COUNT(*) FILTER (WHERE fe.severity = 'critical') as critical_events,
    COUNT(*) FILTER (WHERE fe.severity = 'high') as high_severity_events,
    MAX(fe.detected_at) as last_frustration_event,
    AVG(CASE WHEN sr.rating IS NOT NULL THEN sr.rating ELSE NULL END) as avg_satisfaction
FROM frustration_events fe
LEFT JOIN satisfaction_ratings sr ON fe.student_id = sr.student_id AND fe.app_name = sr.app_name
WHERE fe.resolved_at IS NULL
GROUP BY fe.student_id, fe.app_name;

-- Trigger to update teacher_dashboard_alerts.updated_at
CREATE OR REPLACE FUNCTION update_teacher_dashboard_alerts_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER teacher_dashboard_alerts_update_timestamp
BEFORE UPDATE ON teacher_dashboard_alerts
FOR EACH ROW
EXECUTE FUNCTION update_teacher_dashboard_alerts_timestamp();
