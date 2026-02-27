-- Phase 2 Sprint 2: Auto-Throttle System Migration

-- Throttle Events Table
CREATE TABLE IF NOT EXISTS throttle_events (
    id SERIAL PRIMARY KEY,
    level VARCHAR(20) NOT NULL,
    cpu_percent DECIMAL(5,2) NOT NULL,
    mem_percent DECIMAL(5,2) NOT NULL,
    goroutines INTEGER NOT NULL,
    multiplier DECIMAL(3,2) NOT NULL,
    reason TEXT NOT NULL,
    duration INTERVAL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for Performance
CREATE INDEX idx_throttle_events_level ON throttle_events(level);
CREATE INDEX idx_throttle_events_created_at ON throttle_events(created_at DESC);
CREATE INDEX idx_throttle_events_multiplier ON throttle_events(multiplier);

-- View for Current Throttle Status
CREATE VIEW throttle_status AS
SELECT
    (SELECT level FROM throttle_events ORDER BY created_at DESC LIMIT 1) as current_level,
    (SELECT multiplier FROM throttle_events ORDER BY created_at DESC LIMIT 1) as multiplier,
    (SELECT cpu_percent FROM throttle_events ORDER BY created_at DESC LIMIT 1) as last_cpu,
    (SELECT mem_percent FROM throttle_events ORDER BY created_at DESC LIMIT 1) as last_mem,
    (SELECT goroutines FROM throttle_events ORDER BY created_at DESC LIMIT 1) as last_goroutines,
    (SELECT created_at FROM throttle_events ORDER BY created_at DESC LIMIT 1) as last_changed;

-- View for Throttle Timeline (24 hours)
CREATE VIEW throttle_timeline_24h AS
SELECT
    level,
    COUNT(*) as event_count,
    AVG(cpu_percent) as avg_cpu,
    AVG(mem_percent) as avg_mem,
    MIN(created_at) as period_start,
    MAX(created_at) as period_end
FROM throttle_events
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY level
ORDER BY level;

-- View for Throttle Summary Statistics
CREATE VIEW throttle_summary AS
SELECT
    (SELECT COUNT(*) FROM throttle_events WHERE level = 'critical') as critical_events,
    (SELECT COUNT(*) FROM throttle_events WHERE level = 'high') as high_events,
    (SELECT COUNT(*) FROM throttle_events WHERE level = 'medium') as medium_events,
    (SELECT COUNT(*) FROM throttle_events WHERE level = 'low') as low_events,
    (SELECT COUNT(*) FROM throttle_events WHERE level = 'none') as none_events,
    (SELECT COUNT(*) FROM throttle_events) as total_events,
    (SELECT AVG(cpu_percent) FROM throttle_events) as avg_cpu,
    (SELECT AVG(mem_percent) FROM throttle_events) as avg_mem,
    (SELECT AVG(multiplier) FROM throttle_events WHERE multiplier < 1.0) as avg_throttle_multiplier;
