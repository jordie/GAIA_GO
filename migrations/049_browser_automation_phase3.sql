-- Migration 049: Browser Automation Phase 3 - Execution Loop Database Schema
-- Created: 2026-02-17
-- Purpose: Adds tables for browser task orchestration, execution tracking, and performance monitoring

-- Track individual browser automation tasks
CREATE TABLE IF NOT EXISTS browser_tasks (
    id TEXT PRIMARY KEY,
    goal VARCHAR(500) NOT NULL,
    site_url VARCHAR(500) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    total_steps INTEGER DEFAULT 0,
    total_time_seconds FLOAT DEFAULT 0.0,
    total_cost DECIMAL(10, 4) DEFAULT 0.0,
    cached_path_used BOOLEAN DEFAULT FALSE,
    cache_time_saved_seconds FLOAT DEFAULT 0.0,
    final_result VARCHAR(1000),
    error_message TEXT,
    recovery_attempts INTEGER DEFAULT 0,
    recovery_succeeded BOOLEAN DEFAULT FALSE,
    metadata JSON,

    CONSTRAINT browser_tasks_status_check CHECK (
        status IN ('pending', 'in_progress', 'completed', 'failed', 'paused', 'recovered')
    )
);

-- Detailed execution log for each step in a task
CREATE TABLE IF NOT EXISTS browser_execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    step_number INTEGER NOT NULL,
    action VARCHAR(200) NOT NULL,
    ai_level INTEGER DEFAULT 1,
    ai_used VARCHAR(50),
    duration_ms INTEGER,
    cost DECIMAL(10, 4) DEFAULT 0.0,
    result VARCHAR(200),
    error_details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (task_id) REFERENCES browser_tasks(id) ON DELETE CASCADE,
    CONSTRAINT browser_execution_log_ai_level_check CHECK (ai_level IN (1, 2, 3, 4)),
    CONSTRAINT browser_execution_log_ai_provider_check CHECK (
        ai_used IN ('ollama', 'claude', 'codex', 'gemini', 'anythingllm', NULL)
    )
);

-- Cache for successful navigation paths
CREATE TABLE IF NOT EXISTS browser_navigation_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_url VARCHAR(500) NOT NULL,
    goal_pattern VARCHAR(500) NOT NULL,
    steps_json TEXT NOT NULL,
    success_count INTEGER DEFAULT 1,
    total_time_seconds FLOAT,
    cache_created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cache_last_used_at TIMESTAMP,
    cache_validity_expires_at TIMESTAMP,

    UNIQUE (site_url, goal_pattern)
);

-- Performance metrics aggregation
CREATE TABLE IF NOT EXISTS browser_task_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_date DATE DEFAULT CURRENT_DATE,
    total_tasks_completed INTEGER DEFAULT 0,
    total_tasks_failed INTEGER DEFAULT 0,
    avg_task_time_seconds FLOAT DEFAULT 0.0,
    avg_task_cost DECIMAL(10, 4) DEFAULT 0.0,
    cache_hit_count INTEGER DEFAULT 0,
    cache_hit_rate FLOAT DEFAULT 0.0,
    recovery_attempts INTEGER DEFAULT 0,
    recovery_success_rate FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Error recovery tracking
CREATE TABLE IF NOT EXISTS browser_recovery_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    error_type VARCHAR(100) NOT NULL,
    recovery_strategy VARCHAR(100) NOT NULL,
    attempt_number INTEGER NOT NULL,
    was_successful BOOLEAN,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (task_id) REFERENCES browser_tasks(id) ON DELETE CASCADE
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_browser_tasks_status ON browser_tasks(status);
CREATE INDEX IF NOT EXISTS idx_browser_tasks_site_url ON browser_tasks(site_url);
CREATE INDEX IF NOT EXISTS idx_browser_tasks_created_at ON browser_tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_browser_execution_task_id ON browser_execution_log(task_id);
CREATE INDEX IF NOT EXISTS idx_browser_execution_ai_level ON browser_execution_log(ai_level);
CREATE INDEX IF NOT EXISTS idx_browser_execution_created_at ON browser_execution_log(created_at);
CREATE INDEX IF NOT EXISTS idx_browser_navigation_site_url ON browser_navigation_cache(site_url);
CREATE INDEX IF NOT EXISTS idx_browser_navigation_goal ON browser_navigation_cache(goal_pattern);
CREATE INDEX IF NOT EXISTS idx_browser_recovery_task_id ON browser_recovery_attempts(task_id);
CREATE INDEX IF NOT EXISTS idx_browser_recovery_strategy ON browser_recovery_attempts(recovery_strategy);

-- Update schema_versions table
INSERT INTO schema_versions (version, description)
VALUES ('049', 'Browser Automation Phase 3 - Execution Loop Schema');
