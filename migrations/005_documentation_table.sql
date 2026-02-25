-- Migration: Add documentation table for versioned docs
-- Stores generated documentation that can be updated before deployments

-- Documentation versions table
CREATE TABLE IF NOT EXISTS documentation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL,
    content TEXT NOT NULL,
    html_content TEXT,
    generated_by TEXT DEFAULT 'system',
    environment TEXT,
    stats_snapshot TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for quick version lookups
CREATE INDEX IF NOT EXISTS idx_documentation_version ON documentation(version);
CREATE INDEX IF NOT EXISTS idx_documentation_updated ON documentation(updated_at DESC);

-- Documentation update log (tracks when docs were regenerated)
CREATE TABLE IF NOT EXISTS documentation_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger_type TEXT NOT NULL CHECK(trigger_type IN ('manual', 'pre_deploy', 'scheduled', 'api')),
    triggered_by TEXT,
    environment TEXT,
    old_version TEXT,
    new_version TEXT,
    changes_summary TEXT,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'running', 'completed', 'failed')),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_doc_updates_status ON documentation_updates(status);
