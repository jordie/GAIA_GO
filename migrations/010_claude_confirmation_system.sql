-- Migration: Claude Confirmation System with Pattern Matching and AI Agent Fallback
-- Phase 10: Auto-confirm patterns with AI fallback

-- Confirmation requests
CREATE TABLE IF NOT EXISTS claude_confirmations (
    id UUID PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    permission_type VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_path TEXT NOT NULL,
    context TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decision VARCHAR(20),
    decision_reason TEXT,
    approved_at TIMESTAMP,
    approved_by VARCHAR(50),
    pattern_id UUID REFERENCES approval_patterns(id) ON DELETE SET NULL,
    INDEX idx_session (session_id),
    INDEX idx_timestamp (timestamp),
    INDEX idx_decision (decision),
    INDEX idx_pattern_id (pattern_id)
);

-- Approval patterns
CREATE TABLE IF NOT EXISTS approval_patterns (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    permission_type VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    path_pattern VARCHAR(255),
    context_keywords JSON,
    enabled BOOLEAN DEFAULT true,
    decision_type VARCHAR(20) NOT NULL,
    confidence FLOAT DEFAULT 0.8,
    success_count INT DEFAULT 0,
    failure_count INT DEFAULT 0,
    last_used TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_enabled (enabled),
    INDEX idx_decision_type (decision_type),
    INDEX idx_success_count (success_count DESC)
);

-- AI agent decisions
CREATE TABLE IF NOT EXISTS ai_agent_decisions (
    id UUID PRIMARY KEY,
    confirmation_id UUID NOT NULL REFERENCES claude_confirmations(id) ON DELETE CASCADE,
    decision VARCHAR(20) NOT NULL,
    confidence FLOAT NOT NULL,
    reasoning TEXT,
    matched_patterns JSON,
    tokens_used INT,
    cost_usd DECIMAL(10, 6),
    response_time_ms INT,
    model VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_confirmation_id (confirmation_id),
    INDEX idx_decision (decision),
    INDEX idx_created_at (created_at)
);

-- Session approval preferences
CREATE TABLE IF NOT EXISTS session_approval_preferences (
    id UUID PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL UNIQUE,
    session_name VARCHAR(255),
    allow_all BOOLEAN DEFAULT false,
    pattern_ids JSON,
    use_ai_fallback BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_id (session_id)
);

-- Add some default patterns for common scenarios
INSERT INTO approval_patterns (
    id, name, description, permission_type, resource_type,
    path_pattern, context_keywords, enabled, decision_type,
    confidence, created_at, updated_at
) VALUES
    -- Read operations on project files are generally safe
    (UUID(),
     'Read Project Files',
     'Allow reading project source code and documentation',
     'read', 'file',
     '/data/*,~/projects/*,~/gitrepos/*',
     '["read", "project", "source", "code"]',
     true, 'approve', 0.95, NOW(), NOW()),

    -- Write to project directories
    (UUID(),
     'Write Project Files',
     'Allow writing to project directories for code generation',
     'write', 'file',
     '/data/*,~/projects/*',
     '["write", "project", "generate"]',
     true, 'approve', 0.85, NOW(), NOW()),

    -- Deny system file writes
    (UUID(),
     'Deny System File Writes',
     'Deny writing to system directories',
     'write', 'directory',
     '/etc/*,/sys/*,/var/*',
     '["system", "config"]',
     true, 'deny', 0.95, NOW(), NOW()),

    -- Allow read from home directory
    (UUID(),
     'Read Home Directory',
     'Allow reading user home directory',
     'read', 'directory',
     '~/*',
     '["home", "directory"]',
     true, 'approve', 0.85, NOW(), NOW()),

    -- Test and build operations
    (UUID(),
     'Execute Build Commands',
     'Allow executing build and test commands',
     'execute', 'command',
     '*/test*,*/build*,*/run*',
     '["test", "build", "run"]',
     true, 'approve', 0.80, NOW(), NOW());

-- Create default session preferences for known educational sessions
INSERT INTO session_approval_preferences (
    id, session_id, session_name, allow_all, use_ai_fallback, created_at, updated_at
) VALUES
    (UUID(), 'basic_edu', 'basic_edu', false, true, NOW(), NOW()),
    (UUID(), 'rando_inspector', 'rando_inspector', false, true, NOW(), NOW()),
    (UUID(), 'edu_worker1', 'edu_worker1', false, true, NOW(), NOW());
