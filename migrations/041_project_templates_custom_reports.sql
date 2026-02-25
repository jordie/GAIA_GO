-- Migration 019: Project Templates and Custom Reports
-- Adds tables for project templates and custom report builder

-- Project Templates table
CREATE TABLE IF NOT EXISTS project_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    template_data TEXT,  -- JSON: default_milestones, default_features, settings
    is_active INTEGER DEFAULT 1,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_project_templates_name ON project_templates(name);
CREATE INDEX IF NOT EXISTS idx_project_templates_active ON project_templates(is_active);

-- Custom Reports table
CREATE TABLE IF NOT EXISTS custom_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    report_type TEXT DEFAULT 'table',  -- table, chart, summary
    report_config TEXT,  -- JSON: data_source, filters, columns, grouping, sorting, aggregations
    is_shared INTEGER DEFAULT 0,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_run_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_custom_reports_name ON custom_reports(name);
CREATE INDEX IF NOT EXISTS idx_custom_reports_created_by ON custom_reports(created_by);
CREATE INDEX IF NOT EXISTS idx_custom_reports_shared ON custom_reports(is_shared);
