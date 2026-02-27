-- Phase 2 Sprint 4: Distributed Reputation System Migration

-- Reputation Events Table (for replication)
CREATE TABLE IF NOT EXISTS reputation_events (
    id SERIAL PRIMARY KEY,
    node_id VARCHAR(50) NOT NULL,
    user_id INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL, -- violation, clean_request, tier_change, vip_assigned
    score_delta DECIMAL(10,2) NOT NULL,
    reason_code VARCHAR(100),
    severity INTEGER,
    source_service VARCHAR(100) NOT NULL,
    event_hash VARCHAR(64) UNIQUE NOT NULL, -- SHA256 for deduplication
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    synced_at TIMESTAMP WITH TIME ZONE,
    local_only BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Reputation Sync Tracking
CREATE TABLE IF NOT EXISTS reputation_sync (
    id SERIAL PRIMARY KEY,
    node_id VARCHAR(50) NOT NULL,
    remote_node_id VARCHAR(50) NOT NULL,
    last_sync_time TIMESTAMP WITH TIME ZONE NOT NULL,
    last_event_id INTEGER,
    pending_events INTEGER DEFAULT 0,
    sync_errors INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'healthy', -- healthy, degraded, failed
    sync_frequency INTEGER DEFAULT 10, -- Seconds between syncs
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(node_id, remote_node_id)
);

-- Node Reputation (distributed reputation view)
CREATE TABLE IF NOT EXISTS node_reputation (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    node_id VARCHAR(50) NOT NULL,
    score DECIMAL(10,2) NOT NULL,
    tier VARCHAR(50) NOT NULL,
    last_updated TIMESTAMP WITH TIME ZONE NOT NULL,
    is_authoritative BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, node_id)
);

-- Indexes for Performance
CREATE INDEX idx_reputation_events_node_id ON reputation_events(node_id);
CREATE INDEX idx_reputation_events_user_id ON reputation_events(user_id);
CREATE INDEX idx_reputation_events_timestamp ON reputation_events(timestamp DESC);
CREATE INDEX idx_reputation_events_event_hash ON reputation_events(event_hash);
CREATE INDEX idx_reputation_events_synced ON reputation_events(synced_at);
CREATE INDEX idx_reputation_sync_node ON reputation_sync(node_id);
CREATE INDEX idx_reputation_sync_remote ON reputation_sync(remote_node_id);
CREATE INDEX idx_node_reputation_user ON node_reputation(user_id);
CREATE INDEX idx_node_reputation_node ON node_reputation(node_id);
CREATE INDEX idx_node_reputation_auth ON node_reputation(is_authoritative);

-- Views for Distributed Reputation

-- View: Recent Events (last 1 hour)
CREATE VIEW recent_reputation_events AS
SELECT
    re.id,
    re.node_id,
    re.user_id,
    re.event_type,
    re.score_delta,
    re.reason_code,
    re.severity,
    re.source_service,
    re.timestamp,
    re.synced_at,
    CASE WHEN re.synced_at IS NULL THEN true ELSE false END as pending,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - re.timestamp)) as age_seconds
FROM reputation_events re
WHERE re.timestamp > CURRENT_TIMESTAMP - INTERVAL '1 hour'
ORDER BY re.timestamp DESC;

-- View: Unsynced Events (needs replication)
CREATE VIEW unsynced_reputation_events AS
SELECT
    id,
    node_id,
    user_id,
    event_type,
    score_delta,
    source_service,
    timestamp,
    COUNT(*) OVER (PARTITION BY node_id) as node_pending_count
FROM reputation_events
WHERE synced_at IS NULL AND local_only = false
ORDER BY timestamp ASC;

-- View: Sync Network Health
CREATE VIEW reputation_sync_health AS
SELECT
    rs.node_id,
    rs.remote_node_id,
    rs.status,
    rs.last_sync_time,
    rs.pending_events,
    rs.sync_errors,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - rs.last_sync_time)) as seconds_since_sync,
    CASE
        WHEN rs.status = 'healthy' AND rs.sync_errors = 0 THEN 'optimal'
        WHEN rs.status = 'healthy' THEN 'good'
        WHEN rs.status = 'degraded' THEN 'warning'
        ELSE 'critical'
    END as health_status
FROM reputation_sync rs
ORDER BY rs.node_id, rs.remote_node_id;

-- View: Node Reputation Consensus
CREATE VIEW node_reputation_consensus AS
SELECT
    nr.user_id,
    COUNT(DISTINCT nr.node_id) as node_count,
    AVG(nr.score) as avg_score,
    MIN(nr.score) as min_score,
    MAX(nr.score) as max_score,
    STDDEV(nr.score) as score_stddev,
    (SELECT tier FROM node_reputation WHERE user_id = nr.user_id AND is_authoritative = true LIMIT 1) as authoritative_tier,
    MODE() WITHIN GROUP (ORDER BY tier) as consensus_tier,
    MAX(nr.last_updated) as latest_update
FROM node_reputation nr
GROUP BY nr.user_id;

-- View: Event Replication Summary
CREATE VIEW event_replication_summary AS
SELECT
    DATE_TRUNC('hour', re.timestamp) as hour,
    re.node_id,
    COUNT(*) as total_events,
    SUM(CASE WHEN re.synced_at IS NULL THEN 1 ELSE 0 END) as unsynced_events,
    SUM(CASE WHEN re.local_only = true THEN 1 ELSE 0 END) as local_only_events,
    COUNT(DISTINCT re.event_hash) as unique_events,
    COUNT(*) - COUNT(DISTINCT re.event_hash) as duplicate_events
FROM reputation_events re
GROUP BY DATE_TRUNC('hour', re.timestamp), re.node_id
ORDER BY hour DESC, re.node_id;

-- View: Network Latency (based on sync timing)
CREATE VIEW network_latency_stats AS
SELECT
    rs.node_id,
    rs.remote_node_id,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - rs.last_sync_time)) as last_sync_age_seconds,
    rs.sync_frequency as target_interval_seconds,
    CASE
        WHEN rs.sync_frequency = 0 THEN NULL
        ELSE EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - rs.last_sync_time)) / rs.sync_frequency
    END as latency_ratio,
    COUNT(ure.id) as pending_events
FROM reputation_sync rs
LEFT JOIN unsynced_reputation_events ure ON ure.node_id = rs.node_id
GROUP BY rs.id, rs.node_id, rs.remote_node_id, rs.last_sync_time, rs.sync_frequency;
