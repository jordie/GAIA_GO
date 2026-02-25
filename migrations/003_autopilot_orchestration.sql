-- Migration: Autopilot Orchestration System
-- Adds tables for autonomous development loops, milestones, and review queue

-- =============================================================================
-- APPS: Primary object representing a managed application
-- =============================================================================
CREATE TABLE IF NOT EXISTS apps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    source_path TEXT,
    repo_url TEXT,

    -- Autopilot configuration
    autopilot_mode TEXT DEFAULT 'observe' CHECK(autopilot_mode IN ('observe', 'fix_forward', 'auto_staging', 'auto_prod')),
    autopilot_enabled INTEGER DEFAULT 0,
    risk_level TEXT DEFAULT 'medium' CHECK(risk_level IN ('low', 'medium', 'high', 'critical')),

    -- Goal / KPI
    goal TEXT,  -- "Reduce errors by 50%", "Add feature X"
    constraints TEXT,  -- JSON: budget, allowed deploy times, what's allowed to change

    -- Current state
    current_phase TEXT DEFAULT 'idle' CHECK(current_phase IN ('idle', 'planning', 'implementing', 'testing', 'deploying', 'monitoring', 'investigating')),
    current_run_id INTEGER,
    last_healthy_at TIMESTAMP,

    -- Environments
    dev_url TEXT,
    staging_url TEXT,
    prod_url TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (current_run_id) REFERENCES runs(id)
);

-- =============================================================================
-- RUNS: Each autonomous improvement cycle
-- =============================================================================
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER NOT NULL,
    run_number INTEGER NOT NULL,  -- Sequential per app

    -- Status
    status TEXT DEFAULT 'running' CHECK(status IN ('running', 'completed', 'failed', 'blocked', 'cancelled')),
    phase TEXT DEFAULT 'planning' CHECK(phase IN ('planning', 'implementing', 'testing', 'deploying', 'monitoring', 'investigating')),

    -- What triggered this run
    trigger_type TEXT CHECK(trigger_type IN ('scheduled', 'manual', 'incident', 'milestone_approved', 'regression')),
    trigger_details TEXT,  -- JSON with context

    -- Goal for this run
    goal TEXT,

    -- Progress tracking (step-based, not time-based)
    total_steps INTEGER DEFAULT 0,
    completed_steps INTEGER DEFAULT 0,
    current_step TEXT,

    -- tmux session used
    tmux_session TEXT,

    -- Timing
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    -- Outcome
    outcome_summary TEXT,

    FOREIGN KEY (app_id) REFERENCES apps(id)
);

-- =============================================================================
-- MILESTONES: Checkpoints requiring human verification
-- =============================================================================
CREATE TABLE IF NOT EXISTS milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER NOT NULL,
    run_id INTEGER,

    -- Milestone definition
    name TEXT NOT NULL,
    description TEXT,
    milestone_type TEXT CHECK(milestone_type IN ('feature', 'fix', 'improvement', 'deployment', 'investigation')),

    -- Status
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'ready_for_review', 'approved', 'rejected', 'changes_requested')),

    -- Risk assessment
    risk_score INTEGER DEFAULT 0,  -- 0-100
    risk_factors TEXT,  -- JSON: what contributes to risk
    blast_radius TEXT,  -- JSON: envs/services affected

    -- Rollback
    rollback_steps TEXT,  -- JSON: steps to undo
    rollback_available INTEGER DEFAULT 1,

    -- Review
    reviewer_notes TEXT,
    reviewed_by TEXT,
    reviewed_at TIMESTAMP,

    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ready_at TIMESTAMP,  -- When evidence packet was complete

    FOREIGN KEY (app_id) REFERENCES apps(id),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

-- =============================================================================
-- ARTIFACTS: Structured outputs from autonomous steps
-- =============================================================================
CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    milestone_id INTEGER,

    -- Artifact type
    artifact_type TEXT NOT NULL CHECK(artifact_type IN (
        'plan', 'task_list', 'pr', 'commit', 'test_report',
        'deploy_report', 'investigation_report', 'screenshot',
        'benchmark', 'diff_summary', 'decision_trail'
    )),

    -- Content
    title TEXT,
    content TEXT,  -- Markdown or JSON depending on type
    file_path TEXT,  -- If artifact is a file
    url TEXT,  -- If artifact has external link (PR, etc.)

    -- Metadata
    metadata TEXT,  -- JSON with type-specific data

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (run_id) REFERENCES runs(id),
    FOREIGN KEY (milestone_id) REFERENCES milestones(id)
);

-- =============================================================================
-- APPROVAL_GATES: User-defined checkpoints requiring approval
-- =============================================================================
CREATE TABLE IF NOT EXISTS approval_gates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER,  -- NULL means global gate

    -- Gate definition
    name TEXT NOT NULL,
    description TEXT,

    -- Trigger conditions (JSON)
    -- e.g., {"type": "deploy", "env": "prod"} or {"risk_score_gt": 70}
    conditions TEXT NOT NULL,

    -- What happens when triggered
    action TEXT DEFAULT 'require_approval' CHECK(action IN ('require_approval', 'notify', 'block')),

    -- Notification
    notify_channels TEXT,  -- JSON: slack, email, dashboard

    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (app_id) REFERENCES apps(id)
);

-- =============================================================================
-- REVIEW_QUEUE: Items awaiting user action
-- =============================================================================
CREATE TABLE IF NOT EXISTS review_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- What needs review
    item_type TEXT NOT NULL CHECK(item_type IN ('milestone', 'incident', 'blocked', 'input_needed')),
    item_id INTEGER NOT NULL,  -- References milestones, incidents, etc.

    app_id INTEGER NOT NULL,
    run_id INTEGER,

    -- Priority/urgency
    priority TEXT DEFAULT 'normal' CHECK(priority IN ('low', 'normal', 'high', 'critical')),

    -- Status
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'in_review', 'resolved', 'dismissed')),

    -- Summary for queue display
    title TEXT NOT NULL,
    summary TEXT,

    -- Actions available (JSON array)
    available_actions TEXT,  -- e.g., ["approve", "reject", "request_changes"]

    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolved_by TEXT,
    resolution TEXT,

    FOREIGN KEY (app_id) REFERENCES apps(id),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

-- =============================================================================
-- AGENT_STEPS: Individual steps executed by Claude agents
-- =============================================================================
CREATE TABLE IF NOT EXISTS agent_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,

    -- Step info
    step_number INTEGER NOT NULL,
    step_type TEXT CHECK(step_type IN ('think', 'plan', 'execute', 'verify', 'report')),
    description TEXT,

    -- Execution
    tmux_session TEXT,
    command TEXT,
    output TEXT,

    -- Status
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'running', 'completed', 'failed', 'skipped')),
    error_message TEXT,

    -- Timing
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds REAL,

    FOREIGN KEY (run_id) REFERENCES runs(id)
);

-- =============================================================================
-- INCIDENTS: Detected issues requiring attention
-- =============================================================================
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER NOT NULL,
    run_id INTEGER,  -- Run that detected or caused the incident

    -- Incident details
    severity TEXT DEFAULT 'warning' CHECK(severity IN ('info', 'warning', 'error', 'critical')),
    title TEXT NOT NULL,
    description TEXT,

    -- Source
    source TEXT,  -- 'monitoring', 'test_failure', 'deploy_failure', 'user_report'
    source_details TEXT,  -- JSON with specifics

    -- Related commits/PRs
    suspected_commit TEXT,
    suspected_pr TEXT,

    -- Status
    status TEXT DEFAULT 'open' CHECK(status IN ('open', 'investigating', 'mitigated', 'resolved', 'dismissed')),

    -- Resolution
    resolution TEXT,
    resolved_by TEXT,
    resolved_at TIMESTAMP,

    -- Proposed fix
    proposed_fix TEXT,
    fix_confidence INTEGER,  -- 0-100

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (app_id) REFERENCES apps(id),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

-- =============================================================================
-- INDEXES for performance
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_runs_app_id ON runs(app_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_milestones_app_id ON milestones(app_id);
CREATE INDEX IF NOT EXISTS idx_milestones_status ON milestones(status);
CREATE INDEX IF NOT EXISTS idx_artifacts_run_id ON artifacts(run_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_milestone_id ON artifacts(milestone_id);
CREATE INDEX IF NOT EXISTS idx_review_queue_status ON review_queue(status);
CREATE INDEX IF NOT EXISTS idx_review_queue_priority ON review_queue(priority);
CREATE INDEX IF NOT EXISTS idx_agent_steps_run_id ON agent_steps(run_id);
CREATE INDEX IF NOT EXISTS idx_incidents_app_id ON incidents(app_id);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);

-- =============================================================================
-- DEFAULT APPROVAL GATES
-- =============================================================================
INSERT OR IGNORE INTO approval_gates (name, description, conditions, action) VALUES
    ('Prod Deploy', 'Production deployments require approval', '{"type": "deploy", "env": "prod"}', 'require_approval'),
    ('Schema Changes', 'Database schema changes require approval', '{"files_match": "**/migrations/*.sql"}', 'require_approval'),
    ('High Risk', 'High risk changes require approval', '{"risk_score_gt": 70}', 'require_approval'),
    ('Auth/Billing', 'Security-sensitive changes require approval', '{"paths_match": ["**/auth/**", "**/billing/**"]}', 'require_approval');
