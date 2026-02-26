-- Migration 032: LLM Provider Tests
-- Stores results from testing different LLM providers with standardized prompts

CREATE TABLE IF NOT EXISTS llm_test_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_name TEXT NOT NULL,
    description TEXT,
    prompt_template TEXT NOT NULL,
    max_lines INTEGER DEFAULT 1000,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT
);

CREATE TABLE IF NOT EXISTS llm_test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_run_id INTEGER NOT NULL,
    provider_name TEXT NOT NULL,
    session_name TEXT,
    status TEXT NOT NULL, -- 'pending', 'running', 'completed', 'failed', 'timeout'

    -- Timing
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,

    -- Output metrics
    files_created INTEGER DEFAULT 0,
    total_lines INTEGER DEFAULT 0,
    total_bytes INTEGER DEFAULT 0,
    output_path TEXT,

    -- Quality metrics
    test_passed BOOLEAN DEFAULT 0,
    error_message TEXT,

    -- Metadata
    metadata TEXT, -- JSON with additional info
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (test_run_id) REFERENCES llm_test_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_test_results_run ON llm_test_results(test_run_id);
CREATE INDEX IF NOT EXISTS idx_test_results_provider ON llm_test_results(provider_name);
CREATE INDEX IF NOT EXISTS idx_test_results_status ON llm_test_results(status);
CREATE INDEX IF NOT EXISTS idx_test_results_created ON llm_test_results(created_at);

-- Insert default calculator test
INSERT INTO llm_test_runs (test_name, description, prompt_template, max_lines, created_by)
VALUES (
    'Calculator Web App',
    'Generate a simple calculator web application with HTML, CSS, JS',
    'Create a simple Calculator web application in {output_dir} with:
1. calculator.html - Main HTML page with calculator interface
2. calculator.js - JavaScript for calculator logic
3. calculator.css - Styling
4. README.md - Brief description

Requirements:
- Basic arithmetic operations (add, subtract, multiply, divide)
- Display calculation history (last 5 calculations)
- Clear button to reset
- Responsive design
- Keep it simple and functional
- Total implementation under {max_lines} lines

Generate the files now.',
    1000,
    'system'
);
