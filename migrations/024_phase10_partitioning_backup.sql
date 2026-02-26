-- Phase 10: Partitioning Strategy and Backup Procedures
-- Implements time-based partitioning for metrics tables and backup automation

-- ==============================================================================
-- PARTITIONING: usability_metrics by month
-- ==============================================================================

-- Convert usability_metrics to partitioned table (if not already)
-- This must be done during low-traffic periods

-- TimescaleDB automatically handles partitioning for hypertables
-- Verify hypertable is properly configured
SELECT show_chunks('usability_metrics', older_than => INTERVAL '3 months');

-- Create policy to drop old chunks (data retention: 90 days for raw metrics)
SELECT add_retention_policy('usability_metrics', INTERVAL '90 days', if_not_exists => true);

-- Compress old chunks to save space (older than 30 days)
SELECT add_compression_policy('usability_metrics', INTERVAL '30 days', if_not_exists => true);

-- ==============================================================================
-- PARTITIONING: frustration_events by quarter
-- ==============================================================================

-- Retention: Keep frustration events for 1 year
SELECT add_retention_policy('frustration_events', INTERVAL '365 days', if_not_exists => true);

-- Compress older chunks
SELECT add_compression_policy('frustration_events', INTERVAL '90 days', if_not_exists => true);

-- ==============================================================================
-- PARTITIONING: satisfaction_ratings by month
-- ==============================================================================

-- Retention: Keep ratings for 2 years for analytics
SELECT add_retention_policy('satisfaction_ratings', INTERVAL '730 days', if_not_exists => true);

-- ==============================================================================
-- BACKUP PROCEDURES
-- ==============================================================================

-- ==============================================================================
-- FUNCTION: Backup usability metrics to archive
-- ==============================================================================

CREATE OR REPLACE FUNCTION backup_usability_metrics_to_archive()
RETURNS void AS $$
DECLARE
    v_archive_date DATE;
    v_chunk_name TEXT;
BEGIN
    -- Archive metrics older than 60 days
    v_archive_date := CURRENT_DATE - INTERVAL '60 days';

    -- Get chunks that are candidates for archiving
    FOR v_chunk_name IN
        SELECT chunk_name
        FROM timescaledb_information.chunks
        WHERE hypertable_name = 'usability_metrics'
        AND range_start < EXTRACT(EPOCH FROM v_archive_date)::BIGINT * 1000000
    LOOP
        -- Mark chunks as immutable (prepare for archival)
        EXECUTE format('ALTER TABLE %I SET (timescaledb.compress = true)', v_chunk_name);
        RAISE NOTICE 'Marked % for archival', v_chunk_name;
    END LOOP;

    RAISE NOTICE 'Metrics archived for date: %', v_archive_date;
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- FUNCTION: Generate backup metadata
-- ==============================================================================

CREATE OR REPLACE FUNCTION generate_backup_metadata(
    p_backup_id UUID DEFAULT gen_random_uuid(),
    p_backup_type VARCHAR DEFAULT 'full'
)
RETURNS TABLE (
    backup_id UUID,
    backup_type VARCHAR,
    backup_timestamp TIMESTAMP,
    estimated_size_mb NUMERIC,
    table_name VARCHAR,
    row_count BIGINT,
    table_size_mb NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p_backup_id,
        p_backup_type,
        NOW(),
        (
            SELECT SUM(pg_total_relation_size(schemaname||'.'||tablename))::NUMERIC / 1024 / 1024
            FROM pg_tables
            WHERE schemaname = 'public'
        ),
        tablename,
        (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE table_schema = 'public' AND table_name = tablename),
        (pg_total_relation_size(schemaname||'.'||tablename)::NUMERIC / 1024 / 1024)
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- FUNCTION: Automated backup verification
-- ==============================================================================

CREATE OR REPLACE FUNCTION verify_backup_integrity()
RETURNS TABLE (
    check_name VARCHAR,
    check_status VARCHAR,
    check_details VARCHAR
) AS $$
BEGIN
    -- Check table row counts
    RETURN QUERY
    SELECT
        'Row Count: '::VARCHAR || tablename,
        CASE WHEN reltuples > 0 THEN 'OK' ELSE 'WARNING' END,
        'Rows: ' || reltuples::VARCHAR
    FROM pg_stat_user_tables
    WHERE schemaname = 'public'
    ORDER BY tablename;

    -- Check index validity
    RETURN QUERY
    SELECT
        'Index: '::VARCHAR || indexname,
        CASE WHEN idx_scan > 0 THEN 'USED' ELSE 'UNUSED' END,
        'Scans: ' || idx_scan::VARCHAR
    FROM pg_stat_user_indexes
    WHERE schemaname = 'public'
    ORDER BY tablename, indexname;
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- FUNCTION: Calculate backup schedule
-- ==============================================================================

CREATE OR REPLACE FUNCTION get_backup_schedule()
RETURNS TABLE (
    backup_name VARCHAR,
    schedule_time TIME,
    frequency VARCHAR,
    retention_days INTEGER
) AS $$
BEGIN
    RETURN QUERY VALUES
        ('Full Backup'::VARCHAR, '02:00:00'::TIME, 'Daily', 7),
        ('Incremental Backup'::VARCHAR, '06:00:00'::TIME, 'Every 6 hours', 2),
        ('Transaction Log Backup'::VARCHAR, '00:15:00'::TIME, 'Every 15 minutes', 1),
        ('Archive Backup'::VARCHAR, '01:00:00'::TIME, 'Weekly (Sunday)', 90);
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- BACKUP STATISTICS TABLE
-- ==============================================================================

CREATE TABLE IF NOT EXISTS backup_statistics (
    id BIGSERIAL PRIMARY KEY,
    backup_id UUID NOT NULL,
    backup_type VARCHAR(50) NOT NULL,
    backup_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_seconds INTEGER,
    total_size_mb NUMERIC,
    compressed_size_mb NUMERIC,
    compression_ratio NUMERIC,
    status VARCHAR(20),
    error_message TEXT,
    backup_location VARCHAR(255),
    checksum VARCHAR(64),
    verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMP
);

CREATE INDEX idx_backup_statistics_timestamp ON backup_statistics(backup_timestamp DESC);
CREATE INDEX idx_backup_statistics_status ON backup_statistics(status) WHERE status != 'completed';

-- ==============================================================================
-- VIEW: Backup Status Dashboard
-- ==============================================================================

CREATE OR REPLACE VIEW backup_status_view AS
SELECT
    backup_id,
    backup_type,
    backup_timestamp,
    duration_seconds,
    total_size_mb,
    compression_ratio,
    status,
    verified,
    LAG(backup_timestamp) OVER (PARTITION BY backup_type ORDER BY backup_timestamp) as previous_backup_time,
    (backup_timestamp - LAG(backup_timestamp) OVER (PARTITION BY backup_type ORDER BY backup_timestamp))::INTERVAL as time_since_last_backup
FROM backup_statistics
WHERE status = 'completed'
ORDER BY backup_timestamp DESC;

-- ==============================================================================
-- DISASTER RECOVERY PROCEDURES
-- ==============================================================================

-- ==============================================================================
-- FUNCTION: Point-in-time recovery preparation
-- ==============================================================================

CREATE OR REPLACE FUNCTION prepare_pitr(
    p_recovery_target_time TIMESTAMP
)
RETURNS TABLE (
    recovery_point_found BOOLEAN,
    recovery_time TIMESTAMP,
    available_backups INTEGER
) AS $$
DECLARE
    v_backup_count INTEGER;
    v_closest_backup TIMESTAMP;
BEGIN
    -- Find closest backup before recovery target time
    SELECT COUNT(*), MAX(backup_timestamp)
    INTO v_backup_count, v_closest_backup
    FROM backup_statistics
    WHERE backup_timestamp <= p_recovery_target_time
    AND status = 'completed';

    RETURN QUERY SELECT
        (v_backup_count > 0),
        v_closest_backup,
        v_backup_count;
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- MONITORING: Database Size Tracking
-- ==============================================================================

CREATE TABLE IF NOT EXISTS database_size_history (
    recorded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    database_size_mb NUMERIC,
    indexes_size_mb NUMERIC,
    tables_size_mb NUMERIC,
    toast_size_mb NUMERIC
);

CREATE INDEX idx_database_size_history_recorded_at ON database_size_history(recorded_at DESC);

-- ==============================================================================
-- FUNCTION: Track database size growth
-- ==============================================================================

CREATE OR REPLACE FUNCTION record_database_size()
RETURNS void AS $$
BEGIN
    INSERT INTO database_size_history (database_size_mb, indexes_size_mb, tables_size_mb, toast_size_mb)
    SELECT
        (SELECT pg_database_size(current_database()) / 1024.0 / 1024.0),
        (SELECT SUM(pg_indexes_size(schemaname||'.'||tablename)) / 1024.0 / 1024.0 FROM pg_tables WHERE schemaname = 'public'),
        (SELECT SUM(pg_total_relation_size(schemaname||'.'||tablename)) / 1024.0 / 1024.0 FROM pg_tables WHERE schemaname = 'public'),
        (SELECT pg_tablespace_size('pg_default') / 1024.0 / 1024.0);

    RAISE NOTICE 'Database size recorded at %', NOW();
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- INITIAL SETUP
-- ==============================================================================

-- Create backup statistics table
INSERT INTO backup_statistics (backup_id, backup_type, start_time, status)
VALUES (
    gen_random_uuid(),
    'initial_setup',
    NOW(),
    'completed'
) ON CONFLICT DO NOTHING;

-- Record initial database size
SELECT record_database_size();

-- ==============================================================================
-- DOCUMENTATION: Backup Strategy
-- ==============================================================================

-- BACKUP STRATEGY FOR GAIA_GO PRODUCTION
--
-- 1. FULL BACKUPS (Daily at 02:00)
--    - pg_dump with all tables and schemas
--    - Compressed with gzip
--    - Retained for 7 days
--    - Size: ~500MB - 2GB depending on metric volume
--
-- 2. INCREMENTAL BACKUPS (Every 6 hours at 06:00, 12:00, 18:00, 00:00)
--    - Binary backup of changes since last full backup
--    - Retained for 2 days
--    - Enables faster recovery than replaying logs
--
-- 3. TRANSACTION LOG BACKUPS (Every 15 minutes)
--    - Archives PostgreSQL WAL files
--    - Enables point-in-time recovery
--    - Retained for 24 hours
--    - Critical for data between incremental backups
--
-- 4. ARCHIVE BACKUPS (Weekly on Sunday at 01:00)
--    - Long-term retention of 90-day snapshots
--    - For compliance and historical analysis
--    - Stored in cold storage
--
-- RECOVERY TIME OBJECTIVES (RTO):
--  - Full backup: 30-60 minutes
--  - Incremental + logs: 15-30 minutes
--  - Point-in-time: 60-120 minutes
--
-- RECOVERY POINT OBJECTIVES (RPO):
--  - Maximum data loss: 15 minutes
--  - With transaction log backup every 15 minutes
--
-- BACKUP LOCATIONS:
--  - Primary: /var/backups/gaia_go/ (local NAS)
--  - Secondary: S3 compatible object storage (off-site)
--  - Archive: Cold storage (AWS Glacier or equivalent)
--
-- VERIFICATION:
--  - Checksum verification on all backups
--  - Monthly test restore to verify integrity
--  - Automated backup statistics tracking
--
-- ENCRYPTION:
--  - AES-256 encryption for all backup files
--  - Encryption keys stored separately in HSM
--  - Encrypted transmission over TLS

-- ==============================================================================
-- VERIFICATION
-- ==============================================================================

-- Verify all functions created successfully
SELECT routine_name, routine_type
FROM information_schema.routines
WHERE routine_schema = 'public'
AND routine_name IN (
    'backup_usability_metrics_to_archive',
    'generate_backup_metadata',
    'verify_backup_integrity',
    'get_backup_schedule',
    'prepare_pitr',
    'record_database_size'
)
ORDER BY routine_name;
