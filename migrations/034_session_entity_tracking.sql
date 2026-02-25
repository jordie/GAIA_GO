-- Migration: Add session-entity tracking
-- Sessions should be tied to environment, feature/bug, and milestone

-- Add environment tracking (dev, qa, prod, env1, env2, env3)
ALTER TABLE tmux_sessions ADD COLUMN environment TEXT;

-- Add milestone association
ALTER TABLE tmux_sessions ADD COLUMN milestone_id INTEGER REFERENCES autopilot_milestones(id);

-- Mark worker sessions (autoconfirm, deploy_worker, etc.)
ALTER TABLE tmux_sessions ADD COLUMN is_worker INTEGER DEFAULT 0;

-- Add run association for autopilot
ALTER TABLE tmux_sessions ADD COLUMN autopilot_run_id INTEGER REFERENCES autopilot_runs(id);

-- Update existing sessions with inferred environments
UPDATE tmux_sessions SET environment = 'dev' WHERE session_name LIKE '%dev%' OR session_name LIKE 'arch_dev%';
UPDATE tmux_sessions SET environment = 'qa' WHERE session_name LIKE '%qa%' OR session_name LIKE 'arch_qa%';
UPDATE tmux_sessions SET environment = 'prod' WHERE session_name LIKE '%prod%' OR session_name LIKE 'arch_prod%';
UPDATE tmux_sessions SET environment = 'env3' WHERE session_name LIKE '%env3%' OR session_name LIKE 'arch_env3%';

-- Mark known worker sessions
UPDATE tmux_sessions SET is_worker = 1 WHERE session_name IN ('autoconfirm', 'deploy_worker', 'task_worker', 'nodes_manager', 'audit_manager', 'command_runner');
