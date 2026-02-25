-- Project Dependencies Migration
-- Adds table for tracking dependencies between projects

-- Table for project dependencies
CREATE TABLE IF NOT EXISTS project_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_project_id INTEGER NOT NULL,
    target_project_id INTEGER NOT NULL,
    dependency_type TEXT NOT NULL,  -- depends_on, blocks, related_to, extends, includes, etc.
    description TEXT,
    metadata TEXT,  -- JSON for additional data
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (target_project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE(source_project_id, target_project_id, dependency_type)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_project_deps_source ON project_dependencies(source_project_id);
CREATE INDEX IF NOT EXISTS idx_project_deps_target ON project_dependencies(target_project_id);
CREATE INDEX IF NOT EXISTS idx_project_deps_type ON project_dependencies(dependency_type);
