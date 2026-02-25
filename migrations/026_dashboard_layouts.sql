-- Dashboard Layouts Migration
-- Adds table for saving custom dashboard layouts

-- Table for dashboard layouts
CREATE TABLE IF NOT EXISTS dashboard_layouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    layout_config TEXT NOT NULL,
    is_default BOOLEAN DEFAULT 0,
    is_public BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for dashboard layouts
CREATE INDEX IF NOT EXISTS idx_layouts_user ON dashboard_layouts(user_id);
CREATE INDEX IF NOT EXISTS idx_layouts_default ON dashboard_layouts(user_id, is_default);
CREATE INDEX IF NOT EXISTS idx_layouts_public ON dashboard_layouts(is_public);
