-- Migration: Add task attachments support
-- Allows uploading and previewing files attached to tasks

-- Task attachments table
CREATE TABLE IF NOT EXISTS task_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    task_type TEXT NOT NULL,  -- 'feature', 'bug', 'task_queue', 'milestone', 'devops_task'

    -- File info
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    mime_type TEXT,
    file_hash TEXT,  -- SHA-256 for deduplication

    -- Metadata
    description TEXT,
    uploaded_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Preview info
    has_preview BOOLEAN DEFAULT 0,
    preview_path TEXT,
    thumbnail_path TEXT
);

-- Attachment comments/annotations
CREATE TABLE IF NOT EXISTS attachment_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attachment_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    comment TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attachment_id) REFERENCES task_attachments(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_task_attachments_task ON task_attachments(task_id, task_type);
CREATE INDEX IF NOT EXISTS idx_task_attachments_hash ON task_attachments(file_hash);
CREATE INDEX IF NOT EXISTS idx_task_attachments_user ON task_attachments(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_attachment_comments_attachment ON attachment_comments(attachment_id);
