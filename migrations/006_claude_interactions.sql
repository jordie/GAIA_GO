-- Migration: Track Claude interactions for future processing
-- Store confirmation requests, response patterns, and new behaviors

CREATE TABLE IF NOT EXISTS claude_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_name TEXT NOT NULL,
    interaction_type TEXT NOT NULL,  -- 'confirmation', 'question', 'error', 'response', 'unknown'
    pattern TEXT,                     -- Detected pattern/template
    content TEXT,                     -- Full content captured
    context TEXT,                     -- Surrounding context
    run_id INTEGER,                   -- Associated autopilot run if any
    project_id INTEGER,               -- Associated project if any
    handled INTEGER DEFAULT 0,        -- Whether this was auto-handled
    handler_action TEXT,              -- What action was taken
    requires_review INTEGER DEFAULT 0, -- Flagged for human review
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES autopilot_runs(id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_claude_interactions_type ON claude_interactions(interaction_type);
CREATE INDEX IF NOT EXISTS idx_claude_interactions_pattern ON claude_interactions(pattern);
CREATE INDEX IF NOT EXISTS idx_claude_interactions_session ON claude_interactions(session_name);
CREATE INDEX IF NOT EXISTS idx_claude_interactions_review ON claude_interactions(requires_review);

-- Known patterns table for auto-handling
CREATE TABLE IF NOT EXISTS claude_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL,       -- 'confirmation', 'question', 'error'
    pattern_regex TEXT NOT NULL,      -- Regex to match
    auto_response TEXT,               -- Auto response if any
    action TEXT,                      -- 'approve', 'reject', 'escalate', 'ignore'
    priority INTEGER DEFAULT 0,       -- Higher = checked first
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert common known patterns
INSERT OR IGNORE INTO claude_patterns (pattern_type, pattern_regex, auto_response, action, priority) VALUES
    ('confirmation', 'Would you like me to.*\?', 'yes', 'approve', 10),
    ('confirmation', 'Do you want to proceed.*\?', 'yes', 'approve', 10),
    ('confirmation', 'Should I continue.*\?', 'yes', 'approve', 10),
    ('confirmation', 'Can I.*\?', 'yes', 'approve', 5),
    ('confirmation', 'Is it okay.*\?', 'yes', 'approve', 5),
    ('error', 'rate limit', NULL, 'escalate', 20),
    ('error', 'context.*exceeded', NULL, 'escalate', 20),
    ('error', 'permission denied', NULL, 'escalate', 15),
    ('question', 'Which option.*\?', NULL, 'escalate', 10),
    ('question', 'What.*prefer.*\?', NULL, 'escalate', 10);
