-- Secure Vault for Login Credentials
-- Migration 031: Create secrets table for encrypted credential storage

CREATE TABLE IF NOT EXISTS secrets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    encrypted_value BLOB NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    description TEXT,
    project_id INTEGER,
    service TEXT,  -- Service name (gmail, chatgpt, grok, claude, etc.)
    username TEXT,  -- Associated username/email
    url TEXT,  -- Login URL
    expires_at TIMESTAMP,
    last_accessed TIMESTAMP,
    access_count INTEGER DEFAULT 0,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_secrets_category ON secrets(category);
CREATE INDEX IF NOT EXISTS idx_secrets_service ON secrets(service);
CREATE INDEX IF NOT EXISTS idx_secrets_project ON secrets(project_id);

-- Secret categories for organization
-- Supported categories:
--   'api_key' - API keys and access tokens
--   'password' - User passwords and passphrases
--   'login' - Website login credentials
--   'token' - OAuth tokens, JWT tokens
--   'certificate' - SSL/TLS certificates
--   'ssh_key' - SSH private keys
--   'env_var' - Environment variables
--   'general' - Other sensitive data

-- Audit log for secret access
CREATE TABLE IF NOT EXISTS secret_access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    secret_id INTEGER NOT NULL,
    accessed_by TEXT,
    action TEXT NOT NULL,  -- 'view', 'create', 'update', 'delete'
    ip_address TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (secret_id) REFERENCES secrets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_secret_access_secret ON secret_access_log(secret_id);
CREATE INDEX IF NOT EXISTS idx_secret_access_timestamp ON secret_access_log(timestamp DESC);

-- Insert default login credentials placeholders (encrypted values to be added via API)
INSERT OR IGNORE INTO secrets (name, category, service, description, username, url, encrypted_value)
VALUES
    ('gmail_login', 'login', 'gmail', 'Gmail account for automation', 'jgirmay@gmail.com', 'https://mail.google.com', ''),
    ('chatgpt_login', 'login', 'chatgpt', 'ChatGPT account for automation', NULL, 'https://chat.openai.com', ''),
    ('grok_login', 'login', 'grok', 'Grok (X.AI) account for automation', NULL, 'https://grok.x.ai', ''),
    ('claude_login', 'login', 'claude', 'Claude account for automation', NULL, 'https://claude.ai', '');
