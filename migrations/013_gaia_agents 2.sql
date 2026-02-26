-- GAIA AI Agent Bridge Tables

CREATE TABLE IF NOT EXISTS gaia_agents (
    id TEXT PRIMARY KEY,
    agent_type TEXT NOT NULL,
    capabilities TEXT,
    status TEXT NOT NULL DEFAULT 'available',
    binary_path TEXT,
    max_concurrent INTEGER DEFAULT 1,
    total_tasks INTEGER DEFAULT 0,
    successful_tasks INTEGER DEFAULT 0,
    failed_tasks INTEGER DEFAULT 0,
    last_used TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gaia_agent_tasks (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    instruction TEXT NOT NULL,
    context TEXT,
    work_dir TEXT,
    files TEXT,
    timeout_seconds INTEGER DEFAULT 1800,
    priority INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY(agent_id) REFERENCES gaia_agents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gaia_agent_results (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    success BOOLEAN NOT NULL,
    output TEXT,
    modified_files TEXT,
    error TEXT,
    duration_seconds INTEGER,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id),
    FOREIGN KEY(task_id) REFERENCES gaia_agent_tasks(id) ON DELETE CASCADE,
    FOREIGN KEY(agent_id) REFERENCES gaia_agents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gaia_agent_executions (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(agent_id) REFERENCES gaia_agents(id) ON DELETE CASCADE,
    FOREIGN KEY(task_id) REFERENCES gaia_agent_tasks(id) ON DELETE CASCADE
);

-- Indices for common queries
CREATE INDEX IF NOT EXISTS idx_gaia_agents_type ON gaia_agents(agent_type);
CREATE INDEX IF NOT EXISTS idx_gaia_agents_status ON gaia_agents(status);
CREATE INDEX IF NOT EXISTS idx_gaia_agent_tasks_agent_id ON gaia_agent_tasks(agent_id);
CREATE INDEX IF NOT EXISTS idx_gaia_agent_tasks_status ON gaia_agent_tasks(status);
CREATE INDEX IF NOT EXISTS idx_gaia_agent_results_task_id ON gaia_agent_results(task_id);
CREATE INDEX IF NOT EXISTS idx_gaia_agent_results_agent_id ON gaia_agent_results(agent_id);
CREATE INDEX IF NOT EXISTS idx_gaia_agent_executions_agent_id ON gaia_agent_executions(agent_id);
