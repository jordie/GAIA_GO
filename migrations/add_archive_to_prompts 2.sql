-- Add archive functionality to prompts table
-- Allows hiding completed/failed prompts without deleting them

-- Add archived column
ALTER TABLE prompts ADD COLUMN archived INTEGER DEFAULT 0;

-- Add archived_at timestamp
ALTER TABLE prompts ADD COLUMN archived_at TIMESTAMP;

-- Create index for fast filtering
CREATE INDEX IF NOT EXISTS idx_prompts_archived ON prompts(archived);
CREATE INDEX IF NOT EXISTS idx_prompts_status_archived ON prompts(status, archived);
