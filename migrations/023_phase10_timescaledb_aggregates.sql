-- Phase 10: TimescaleDB Continuous Aggregates for production analytics
-- These pre-aggregated views dramatically improve query performance

-- ==============================================================================
-- CONTINUOUS AGGREGATE: Hourly Metrics Summary
-- ==============================================================================

-- Drop existing materialized view if exists
DROP MATERIALIZED VIEW IF EXISTS metrics_1h_summary CASCADE;

-- Create continuous aggregate for hourly metrics
CREATE MATERIALIZED VIEW metrics_1h_summary
WITH (timescaledb.continuous, timescaledb.materialized_only = false)
AS
SELECT
    time_bucket('1 hour', timestamp) as hour,
    student_id,
    app_name,
    metric_type,
    COUNT(*) as metric_count,
    AVG(metric_value) as avg_value,
    MAX(metric_value) as max_value,
    MIN(metric_value) as min_value,
    STDDEV(metric_value) as stddev_value
FROM usability_metrics
GROUP BY hour, student_id, app_name, metric_type
WITH DATA;

-- Create index on continuous aggregate
CREATE INDEX ON metrics_1h_summary (hour DESC, student_id, app_name);

-- ==============================================================================
-- CONTINUOUS AGGREGATE: Daily Student Metrics
-- ==============================================================================

DROP MATERIALIZED VIEW IF EXISTS metrics_daily_student_summary CASCADE;

CREATE MATERIALIZED VIEW metrics_daily_student_summary
WITH (timescaledb.continuous, timescaledb.materialized_only = false)
AS
SELECT
    time_bucket('1 day', timestamp) as day,
    student_id,
    COUNT(DISTINCT app_name) as apps_used,
    COUNT(*) as total_metrics,
    COUNT(CASE WHEN metric_type = 'error' THEN 1 END) as error_count,
    COUNT(CASE WHEN metric_type = 'backspace' THEN 1 END) as backspace_count,
    COUNT(CASE WHEN metric_type = 'completion' THEN 1 END) as completion_count,
    AVG(metric_value) as avg_metric_value,
    MAX(metric_value) as max_metric_value
FROM usability_metrics
GROUP BY day, student_id
WITH DATA;

CREATE INDEX ON metrics_daily_student_summary (day DESC, student_id);

-- ==============================================================================
-- CONTINUOUS AGGREGATE: Frustration Event Hourly
-- ==============================================================================

DROP MATERIALIZED VIEW IF EXISTS frustration_1h_summary CASCADE;

CREATE MATERIALIZED VIEW frustration_1h_summary
WITH (timescaledb.continuous, timescaledb.materialized_only = false)
AS
SELECT
    time_bucket('1 hour', detected_at) as hour,
    student_id,
    app_name,
    severity,
    COUNT(*) as event_count,
    COUNT(CASE WHEN resolved_at IS NOT NULL THEN 1 END) as resolved_count
FROM frustration_events
GROUP BY hour, student_id, app_name, severity
WITH DATA;

CREATE INDEX ON frustration_1h_summary (hour DESC, student_id, severity);

-- ==============================================================================
-- CONTINUOUS AGGREGATE: Daily Frustration Summary
-- ==============================================================================

DROP MATERIALIZED VIEW IF EXISTS frustration_daily_summary CASCADE;

CREATE MATERIALIZED VIEW frustration_daily_summary
WITH (timescaledb.continuous, timescaledb.materialized_only = false)
AS
SELECT
    time_bucket('1 day', detected_at) as day,
    student_id,
    COUNT(*) as total_events,
    COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical_events,
    COUNT(CASE WHEN severity = 'high' THEN 1 END) as high_events,
    COUNT(CASE WHEN severity = 'medium' THEN 1 END) as medium_events,
    COUNT(CASE WHEN severity = 'low' THEN 1 END) as low_events,
    COUNT(CASE WHEN resolved_at IS NOT NULL THEN 1 END) as resolved_events
FROM frustration_events
GROUP BY day, student_id
WITH DATA;

CREATE INDEX ON frustration_daily_summary (day DESC, student_id);

-- ==============================================================================
-- CONTINUOUS AGGREGATE: Classroom Metrics Summary
-- ==============================================================================

DROP MATERIALIZED VIEW IF EXISTS classroom_metrics_hourly CASCADE;

CREATE MATERIALIZED VIEW classroom_metrics_hourly
WITH (timescaledb.continuous, timescaledb.materialized_only = false)
AS
SELECT
    time_bucket('1 hour', um.timestamp) as hour,
    cs.lesson_id,
    um.app_name,
    COUNT(DISTINCT um.student_id) as student_count,
    COUNT(*) as total_metrics,
    AVG(um.metric_value) as avg_metric_value,
    COUNT(CASE WHEN um.metric_type = 'error' THEN 1 END)::FLOAT /
        NULLIF(COUNT(*), 0) * 100 as error_rate_percent
FROM usability_metrics um
LEFT JOIN claude_sessions cs ON um.session_id = cs.id
GROUP BY hour, cs.lesson_id, um.app_name
WITH DATA;

CREATE INDEX ON classroom_metrics_hourly (hour DESC, lesson_id);

-- ==============================================================================
-- CONTINUOUS AGGREGATE: Session Health Summary
-- ==============================================================================

DROP MATERIALIZED VIEW IF EXISTS session_health_hourly CASCADE;

CREATE MATERIALIZED VIEW session_health_hourly
WITH (timescaledb.continuous, timescaledb.materialized_only = false)
AS
SELECT
    time_bucket('1 hour', updated_at) as hour,
    COUNT(*) as total_sessions,
    COUNT(CASE WHEN health_status = 'healthy' THEN 1 END) as healthy_count,
    COUNT(CASE WHEN health_status = 'degraded' THEN 1 END) as degraded_count,
    COUNT(CASE WHEN health_status = 'unhealthy' THEN 1 END) as unhealthy_count,
    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_sessions,
    AVG(EXTRACT(EPOCH FROM (last_heartbeat - created_at))) as avg_session_duration_sec
FROM claude_sessions
GROUP BY hour
WITH DATA;

CREATE INDEX ON session_health_hourly (hour DESC);

-- ==============================================================================
-- VIEW: Student Performance Dashboard
-- ==============================================================================

-- Query-friendly view combining multiple metrics
DROP VIEW IF EXISTS student_performance_view CASCADE;

CREATE VIEW student_performance_view AS
SELECT
    ds.day,
    ds.student_id,
    ds.apps_used,
    ds.total_metrics,
    ds.error_count,
    ds.backspace_count,
    ds.completion_count,
    CASE WHEN ds.total_metrics > 0 THEN (ds.error_count::FLOAT / ds.total_metrics * 100) ELSE 0 END as error_rate,
    CASE WHEN ds.error_count > 0 THEN (ds.backspace_count::FLOAT / ds.error_count) ELSE 0 END as backspace_per_error,
    CASE WHEN ds.total_metrics > 0 THEN (ds.completion_count::FLOAT / ds.total_metrics * 100) ELSE 0 END as completion_rate,
    fs.total_events as frustration_events,
    fs.critical_events,
    fs.high_events
FROM metrics_daily_student_summary ds
LEFT JOIN frustration_daily_summary fs ON ds.day = fs.day AND ds.student_id = fs.student_id
ORDER BY ds.day DESC, ds.student_id;

-- ==============================================================================
-- VIEW: Classroom Health Dashboard
-- ==============================================================================

DROP VIEW IF EXISTS classroom_health_view CASCADE;

CREATE VIEW classroom_health_view AS
SELECT
    ch.hour,
    ch.lesson_id,
    ch.app_name,
    ch.student_count,
    ch.total_metrics,
    ch.error_rate_percent,
    CASE
        WHEN ch.error_rate_percent > 10 THEN 'critical'
        WHEN ch.error_rate_percent > 5 THEN 'high'
        WHEN ch.error_rate_percent > 2 THEN 'medium'
        ELSE 'low'
    END as health_status,
    sh.healthy_count,
    sh.degraded_count,
    sh.unhealthy_count
FROM classroom_metrics_hourly ch
LEFT JOIN session_health_hourly sh ON ch.hour = sh.hour
ORDER BY ch.hour DESC;

-- ==============================================================================
-- POLICY: Retention for Raw Metrics (30 days)
-- ==============================================================================

-- Keep only recent metrics in raw table for performance
-- Older data is available in aggregated views
SELECT add_retention_policy('usability_metrics', INTERVAL '30 days', if_not_exists => true);

-- ==============================================================================
-- POLICY: Continuous Aggregate Refresh
-- ==============================================================================

-- Auto-refresh aggregates every hour
SELECT add_continuous_aggregate_policy('metrics_1h_summary',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '1 hour',
    if_not_exists => true);

SELECT add_continuous_aggregate_policy('frustration_1h_summary',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '1 hour',
    if_not_exists => true);

SELECT add_continuous_aggregate_policy('session_health_hourly',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '1 hour',
    if_not_exists => true);

-- ==============================================================================
-- STATISTICS
-- ==============================================================================

-- Refresh stats for optimizer
ANALYZE usability_metrics;
ANALYZE metrics_1h_summary;
ANALYZE frustration_events;
ANALYZE frustration_1h_summary;
ANALYZE claude_sessions;

-- ==============================================================================
-- VERIFICATION
-- ==============================================================================

-- Show created continuous aggregates
SELECT
    view_schema,
    view_name,
    view_type,
    materialized
FROM timescaledb_information.continuous_aggregates
WHERE view_schema = 'public'
ORDER BY view_name;
