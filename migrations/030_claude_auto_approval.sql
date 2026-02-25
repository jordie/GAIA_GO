-- Claude Auto-Approval Patterns
-- Allows Claude Code sessions to work autonomously by auto-approving common operations

CREATE TABLE IF NOT EXISTS claude_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    pattern_type TEXT NOT NULL, -- 'file_edit', 'file_create', 'file_read', 'command', 'tool_use'
    pattern TEXT NOT NULL, -- Regex or glob pattern to match prompts
    action TEXT NOT NULL DEFAULT 'approve', -- 'approve' or 'deny'
    scope TEXT, -- 'global', 'session:<name>', 'project:<path>'
    priority INTEGER DEFAULT 0, -- Higher priority patterns checked first
    conditions TEXT, -- JSON conditions for when to apply
    enabled BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS claude_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_name TEXT NOT NULL,
    prompt_type TEXT NOT NULL, -- 'file_permission', 'edit_confirmation', 'command', etc.
    prompt_text TEXT,
    file_path TEXT,
    action_requested TEXT, -- 'read', 'write', 'edit', 'delete', 'execute'
    response TEXT, -- 'approved', 'denied', 'pending'
    matched_pattern_id INTEGER,
    auto_approved BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP,
    FOREIGN KEY (matched_pattern_id) REFERENCES claude_patterns(id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_claude_patterns_type ON claude_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_claude_patterns_enabled ON claude_patterns(enabled);
CREATE INDEX IF NOT EXISTS idx_claude_interactions_session ON claude_interactions(session_name);
CREATE INDEX IF NOT EXISTS idx_claude_interactions_response ON claude_interactions(response);

-- Insert default auto-approval patterns
INSERT INTO claude_patterns (name, description, pattern_type, pattern, action, scope, priority) VALUES
-- File editing patterns
('auto_approve_code_edits', 'Auto-approve edits to code files', 'file_edit', '.*\.(py|js|jsx|ts|tsx|java|go|rs|rb|php|c|cpp|h|hpp|cs)$', 'approve', 'global', 10),
('auto_approve_config_edits', 'Auto-approve edits to config files', 'file_edit', '.*\.(yaml|yml|json|toml|ini|conf|cfg)$', 'approve', 'global', 8),
('auto_approve_doc_edits', 'Auto-approve edits to documentation', 'file_edit', '.*\.(md|txt|rst|adoc)$', 'approve', 'global', 5),
('auto_approve_test_files', 'Auto-approve edits to test files', 'file_edit', '.*/test.*\.(py|js|ts|go|rb)$', 'approve', 'global', 9),

-- File creation patterns
('auto_approve_temp_files', 'Auto-approve temp file creation', 'file_create', '.*/tmp/.*', 'approve', 'global', 10),
('auto_approve_test_output', 'Auto-approve test output files', 'file_create', '.*/(test_output|__pycache__|node_modules|build|dist)/.*', 'approve', 'global', 9),
('auto_approve_new_code', 'Auto-approve new code files in project', 'file_create', '.*/architect/.*\.(py|js|jsx|ts|tsx|sql|sh)$', 'approve', 'global', 8),

-- File reading patterns
('auto_approve_read_code', 'Auto-approve reading code files', 'file_read', '.*\.(py|js|jsx|ts|tsx|java|go|rs|rb|php|yaml|json|md)$', 'approve', 'global', 10),

-- Command execution patterns
('auto_approve_safe_commands', 'Auto-approve safe shell commands', 'command', '^(ls|cat|grep|find|echo|pwd|which|python3|node|npm|git status|git diff).*', 'approve', 'global', 7),
('auto_approve_git_read', 'Auto-approve git read commands', 'command', '^git (log|show|diff|status|branch).*', 'approve', 'global', 9),
('auto_approve_package_info', 'Auto-approve package managers (read-only)', 'command', '^(pip list|npm list|cargo --version|go version).*', 'approve', 'global', 8),

-- Tool use patterns
('auto_approve_read_tools', 'Auto-approve Read tool usage', 'tool_use', 'Read', 'approve', 'global', 10),
('auto_approve_grep_glob', 'Auto-approve Grep and Glob tools', 'tool_use', '(Grep|Glob)', 'approve', 'global', 10),
('auto_approve_edit_tool', 'Auto-approve Edit tool for code files', 'tool_use', 'Edit', 'approve', 'global', 9),
('auto_approve_write_temp', 'Auto-approve Write tool to temp directories', 'tool_use', 'Write.*(/tmp/|/var/tmp/)', 'approve', 'global', 8);

-- Session-specific patterns for autonomous workers
INSERT INTO claude_patterns (name, description, pattern_type, pattern, action, scope, priority) VALUES
('codex_full_autonomy', 'Codex session - full autonomy for code generation', 'file_edit', '.*', 'approve', 'session:codex', 100),
('codex_full_autonomy_create', 'Codex session - full autonomy for file creation', 'file_create', '.*', 'approve', 'session:codex', 100),
('comet_full_autonomy', 'Comet session - full autonomy', 'file_edit', '.*', 'approve', 'session:comet', 100),
('comet_full_autonomy_create', 'Comet session - full autonomy for file creation', 'file_create', '.*', 'approve', 'session:comet', 100),
('concurrent_worker_autonomy', 'Concurrent worker - full autonomy', 'file_edit', '.*', 'approve', 'session:concurrent_worker1', 100),
('concurrent_worker_create', 'Concurrent worker - file creation autonomy', 'file_create', '.*', 'approve', 'session:concurrent_worker1', 100),
('task_worker_autonomy', 'Task worker - full autonomy', 'file_edit', '.*', 'approve', 'session:task_worker1', 100),
('task_worker_create', 'Task worker - file creation autonomy', 'file_create', '.*', 'approve', 'session:task_worker1', 100);
