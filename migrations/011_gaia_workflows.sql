-- GAIA Workflow Orchestration Tables

CREATE TABLE IF NOT EXISTS gaia_workflows (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    version TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    variables TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error TEXT
);

CREATE TABLE IF NOT EXISTS gaia_workflow_tasks (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    agent TEXT NOT NULL,
    command TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    work_dir TEXT,
    timeout_seconds INTEGER DEFAULT 1800,
    max_retries INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    on_error TEXT DEFAULT 'fail',
    output TEXT,
    error TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(workflow_id) REFERENCES gaia_workflows(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gaia_workflow_task_dependencies (
    workflow_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    dependency_task_id TEXT NOT NULL,
    FOREIGN KEY(workflow_id) REFERENCES gaia_workflows(id) ON DELETE CASCADE,
    FOREIGN KEY(task_id) REFERENCES gaia_workflow_tasks(id) ON DELETE CASCADE,
    FOREIGN KEY(dependency_task_id) REFERENCES gaia_workflow_tasks(id) ON DELETE CASCADE,
    PRIMARY KEY(workflow_id, task_id, dependency_task_id)
);

CREATE TABLE IF NOT EXISTS gaia_workflow_executions (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    success_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(workflow_id) REFERENCES gaia_workflows(id) ON DELETE CASCADE
);

-- Indices for common queries
CREATE INDEX IF NOT EXISTS idx_gaia_workflows_status ON gaia_workflows(status);
CREATE INDEX IF NOT EXISTS idx_gaia_workflows_created_at ON gaia_workflows(created_at);
CREATE INDEX IF NOT EXISTS idx_gaia_workflow_tasks_workflow_id ON gaia_workflow_tasks(workflow_id);
CREATE INDEX IF NOT EXISTS idx_gaia_workflow_tasks_status ON gaia_workflow_tasks(status);
CREATE INDEX IF NOT EXISTS idx_gaia_workflow_task_deps_workflow_id ON gaia_workflow_task_dependencies(workflow_id);
CREATE INDEX IF NOT EXISTS idx_gaia_workflow_task_deps_task_id ON gaia_workflow_task_dependencies(task_id);
CREATE INDEX IF NOT EXISTS idx_gaia_workflow_executions_workflow_id ON gaia_workflow_executions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_gaia_workflow_executions_status ON gaia_workflow_executions(status);
