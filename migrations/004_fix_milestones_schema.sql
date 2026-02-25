-- Migration: Fix milestones table for orchestration compatibility
-- The original milestones table uses project_id, but orchestration needs app_id

-- Add app_id column to milestones (allows NULL since old records won't have it)
ALTER TABLE milestones ADD COLUMN app_id INTEGER REFERENCES apps(id);

-- Add run_id column for orchestration runs
ALTER TABLE milestones ADD COLUMN run_id INTEGER REFERENCES runs(id);

-- Add milestone_type for orchestration
ALTER TABLE milestones ADD COLUMN milestone_type TEXT CHECK(milestone_type IN ('feature', 'fix', 'improvement', 'deployment', 'investigation'));

-- Add risk assessment columns
ALTER TABLE milestones ADD COLUMN risk_score INTEGER DEFAULT 0;
ALTER TABLE milestones ADD COLUMN risk_factors TEXT;
ALTER TABLE milestones ADD COLUMN blast_radius TEXT;

-- Add rollback columns
ALTER TABLE milestones ADD COLUMN rollback_steps TEXT;
ALTER TABLE milestones ADD COLUMN rollback_available INTEGER DEFAULT 1;

-- Add review columns
ALTER TABLE milestones ADD COLUMN reviewer_notes TEXT;
ALTER TABLE milestones ADD COLUMN reviewed_by TEXT;
ALTER TABLE milestones ADD COLUMN reviewed_at TIMESTAMP;

-- Add ready_at timestamp
ALTER TABLE milestones ADD COLUMN ready_at TIMESTAMP;

-- Update status check (SQLite doesn't support modifying constraints, so we just use the column as-is)
-- The orchestration code will handle status values

-- Create indexes for the new columns
CREATE INDEX IF NOT EXISTS idx_milestones_app_id ON milestones(app_id);
CREATE INDEX IF NOT EXISTS idx_milestones_run_id ON milestones(run_id);
