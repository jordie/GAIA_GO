-- Team recognition kudos

CREATE TABLE IF NOT EXISTS kudos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_user_id INTEGER NOT NULL,
    recipient_user_id INTEGER NOT NULL,
    project_id INTEGER,
    category TEXT DEFAULT 'general',
    message TEXT NOT NULL,
    points INTEGER DEFAULT 1,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_user_id) REFERENCES users(id),
    FOREIGN KEY (recipient_user_id) REFERENCES users(id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE INDEX IF NOT EXISTS idx_kudos_sender ON kudos(sender_user_id);
CREATE INDEX IF NOT EXISTS idx_kudos_recipient ON kudos(recipient_user_id);
CREATE INDEX IF NOT EXISTS idx_kudos_project ON kudos(project_id);
CREATE INDEX IF NOT EXISTS idx_kudos_created_at ON kudos(created_at);
