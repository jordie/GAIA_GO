-- Custom Reports Migration
-- Adds tables for the custom report builder feature

-- Table for custom report definitions
CREATE TABLE IF NOT EXISTS custom_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    data_source TEXT NOT NULL,
    columns TEXT,  -- JSON array of column definitions
    filters TEXT,  -- JSON array of filter conditions
    config TEXT,   -- JSON object with additional config (group_by, order_by, limit)
    schedule TEXT, -- JSON object with schedule configuration
    owner_id INTEGER,
    is_public INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Table for report run history
CREATE TABLE IF NOT EXISTS report_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    row_count INTEGER DEFAULT 0,
    duration_seconds REAL,
    status TEXT DEFAULT 'pending',
    error TEXT,
    run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (report_id) REFERENCES custom_reports(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_custom_reports_owner ON custom_reports(owner_id);
CREATE INDEX IF NOT EXISTS idx_custom_reports_public ON custom_reports(is_public);
CREATE INDEX IF NOT EXISTS idx_custom_reports_source ON custom_reports(data_source);
CREATE INDEX IF NOT EXISTS idx_report_runs_report ON report_runs(report_id);
CREATE INDEX IF NOT EXISTS idx_report_runs_status ON report_runs(status);
CREATE INDEX IF NOT EXISTS idx_report_runs_time ON report_runs(run_at);
