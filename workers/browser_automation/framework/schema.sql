-- Browser Automation Framework Database Schema
-- Stores sources, actions, prompt trees in database instead of files

-- Sources: Websites/apps we can automate
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,  -- 'browser', 'api', 'applescript'
    base_url TEXT,
    app_name TEXT,  -- For AppleScript (Comet, Safari, etc.)
    description TEXT,
    config JSON,  -- Additional configuration
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Elements: UI elements within sources
CREATE TABLE IF NOT EXISTS elements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    selector TEXT NOT NULL,  -- CSS selector, XPath, or key combo
    selector_type TEXT DEFAULT 'key',  -- 'key', 'css', 'xpath', 'id'
    description TEXT,
    wait_after REAL DEFAULT 0.5,
    FOREIGN KEY (source_id) REFERENCES sources(id),
    UNIQUE(source_id, name)
);

-- Actions: Reusable automation actions
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,  -- 'click', 'type', 'wait', 'script', 'api_call'
    description TEXT,
    implementation TEXT,  -- Python code, AppleScript, or API call
    parameters JSON,  -- Parameter definitions
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Prompt Trees: Navigation flows
CREATE TABLE IF NOT EXISTS prompt_trees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    source_id INTEGER,
    description TEXT,
    steps JSON NOT NULL,  -- Array of steps
    variables JSON,  -- Template variables
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

-- Tree Steps: Individual steps in a prompt tree
CREATE TABLE IF NOT EXISTS tree_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tree_id INTEGER NOT NULL,
    step_number INTEGER NOT NULL,
    action_id INTEGER,
    element_id INTEGER,
    params JSON,
    condition TEXT,  -- Optional conditional logic
    on_success INTEGER,  -- Next step if success
    on_failure INTEGER,  -- Next step if failure
    FOREIGN KEY (tree_id) REFERENCES prompt_trees(id),
    FOREIGN KEY (action_id) REFERENCES actions(id),
    FOREIGN KEY (element_id) REFERENCES elements(id),
    UNIQUE(tree_id, step_number)
);

-- Executions: Log of automation runs
CREATE TABLE IF NOT EXISTS executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tree_id INTEGER NOT NULL,
    data JSON,  -- Runtime data
    status TEXT,  -- 'running', 'success', 'failed'
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error TEXT,
    result JSON,
    FOREIGN KEY (tree_id) REFERENCES prompt_trees(id)
);

-- Execution Steps: Individual step results
CREATE TABLE IF NOT EXISTS execution_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id INTEGER NOT NULL,
    step_id INTEGER NOT NULL,
    status TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error TEXT,
    result JSON,
    FOREIGN KEY (execution_id) REFERENCES executions(id),
    FOREIGN KEY (step_id) REFERENCES tree_steps(id)
);

-- Pauses: Timing configurations per source
CREATE TABLE IF NOT EXISTS pauses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    duration REAL NOT NULL,  -- Seconds
    description TEXT,
    FOREIGN KEY (source_id) REFERENCES sources(id),
    UNIQUE(source_id, name)
);

-- URL Patterns: For validation and detection
CREATE TABLE IF NOT EXISTS url_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    pattern TEXT NOT NULL,  -- Regex pattern
    description TEXT,
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_elements_source ON elements(source_id);
CREATE INDEX IF NOT EXISTS idx_tree_steps_tree ON tree_steps(tree_id);
CREATE INDEX IF NOT EXISTS idx_executions_tree ON executions(tree_id);
CREATE INDEX IF NOT EXISTS idx_executions_status ON executions(status);
CREATE INDEX IF NOT EXISTS idx_execution_steps_execution ON execution_steps(execution_id);
