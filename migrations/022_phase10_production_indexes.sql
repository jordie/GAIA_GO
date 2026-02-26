-- Phase 10: Production-grade indexes for high-cardinality columns
-- This migration optimizes query performance for production workloads

-- ==============================================================================
-- USABILITY_METRICS TABLE INDEXES
-- ==============================================================================

-- High-cardinality composite index: student_id + timestamp + app_name
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_usability_metrics_student_timestamp_app
ON usability_metrics (student_id, timestamp DESC, app_name)
INCLUDE (metric_type, metric_value);

-- Index for searching by app and timestamp
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_usability_metrics_app_timestamp
ON usability_metrics (app_name, timestamp DESC);

-- Index for time-range queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_usability_metrics_timestamp
ON usability_metrics (timestamp DESC)
WHERE created_at > NOW() - INTERVAL '30 days';

-- Index for metric_type searches
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_usability_metrics_metric_type
ON usability_metrics (metric_type, student_id, timestamp DESC);

-- Index for session tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_usability_metrics_session
ON usability_metrics (session_id, timestamp DESC)
WHERE session_id IS NOT NULL;

-- ==============================================================================
-- FRUSTRATION_EVENTS TABLE INDEXES
-- ==============================================================================

-- High-cardinality: student_id + severity + detected_at
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_frustration_events_student_severity_detected
ON frustration_events (student_id, severity, detected_at DESC);

-- Search by detection time
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_frustration_events_detected_at
ON frustration_events (detected_at DESC);

-- Search by app
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_frustration_events_app_detected
ON frustration_events (app_name, detected_at DESC);

-- Find unresolved events
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_frustration_events_unresolved
ON frustration_events (student_id, detected_at DESC)
WHERE resolved_at IS NULL;

-- ==============================================================================
-- CLAUDE_SESSIONS TABLE INDEXES
-- ==============================================================================

-- Active sessions lookup
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_claude_sessions_active
ON claude_sessions (status, last_heartbeat DESC)
WHERE status != 'terminated';

-- Session by lesson
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_claude_sessions_lesson
ON claude_sessions (lesson_id, status);

-- Health status tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_claude_sessions_health
ON claude_sessions (health_status, last_heartbeat DESC);

-- ==============================================================================
-- DISTRIBUTED_TASK_QUEUE TABLE INDEXES
-- ==============================================================================

-- Pending task lookup by priority
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_distributed_task_queue_pending
ON distributed_task_queue (priority DESC, created_at ASC)
WHERE status = 'pending';

-- Claimed task tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_distributed_task_queue_claimed
ON distributed_task_queue (claimed_by, claimed_at DESC)
WHERE claimed_by IS NOT NULL AND status = 'in_progress';

-- Task by type
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_distributed_task_queue_type
ON distributed_task_queue (task_type, status, priority DESC);

-- Idempotency key lookup
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_distributed_task_queue_idempotency
ON distributed_task_queue (idempotency_key);

-- ==============================================================================
-- SATISFACTION_RATINGS TABLE INDEXES
-- ==============================================================================

-- Rating lookup by student and app
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_satisfaction_ratings_student_app
ON satisfaction_ratings (student_id, app_name, created_at DESC);

-- Time-based queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_satisfaction_ratings_created_at
ON satisfaction_ratings (created_at DESC);

-- ==============================================================================
-- PERFORMANCE ANALYSIS INDEXES
-- ==============================================================================

-- Analyze patterns in metrics
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_usability_metrics_pattern
ON usability_metrics (student_id, app_name, metric_type, timestamp DESC);

-- Quick aggregation queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_usability_metrics_aggregate
ON usability_metrics (student_id, timestamp DESC NULLS LAST);

-- ==============================================================================
-- VACUUM AND ANALYZE
-- ==============================================================================

ANALYZE usability_metrics;
ANALYZE frustration_events;
ANALYZE claude_sessions;
ANALYZE distributed_task_queue;
ANALYZE satisfaction_ratings;

-- ==============================================================================
-- INDEX STATISTICS
-- ==============================================================================

-- Verify indexes were created
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
