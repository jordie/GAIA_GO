-- Phase 9 Consolidation: Distributed Coordination Tables
-- Enables Raft consensus, Claude session coordination, and distributed task assignment

-- Claude sessions table - Track distributed Claude Code sessions
CREATE TABLE IF NOT EXISTS claude_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_name VARCHAR(255) NOT NULL UNIQUE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    tier VARCHAR(50) NOT NULL CHECK (tier IN ('high_level', 'manager', 'worker')),
    provider VARCHAR(50) NOT NULL CHECK (provider IN ('claude', 'codex', 'ollama', 'openai', 'gemini')),
    status VARCHAR(50) NOT NULL DEFAULT 'idle' CHECK (status IN ('idle', 'busy', 'paused', 'failed', 'offline')),

    -- Coordination
    lesson_id UUID REFERENCES lessons(id) ON DELETE SET NULL,
    time_window_start TIMESTAMP,
    time_window_end TIMESTAMP,

    -- Health tracking
    last_heartbeat TIMESTAMP NOT NULL DEFAULT NOW(),
    health_status VARCHAR(50) DEFAULT 'healthy' CHECK (health_status IN ('healthy', 'degraded', 'unhealthy')),
    consecutive_failures INT DEFAULT 0,

    -- Capacity
    max_concurrent_tasks INT DEFAULT 1,
    current_task_count INT DEFAULT 0,

    -- Metadata
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_claude_sessions_user ON claude_sessions(user_id);
CREATE INDEX idx_claude_sessions_tier ON claude_sessions(tier);
CREATE INDEX idx_claude_sessions_status ON claude_sessions(status);
CREATE INDEX idx_claude_sessions_lesson ON claude_sessions(lesson_id);
CREATE INDEX idx_claude_sessions_provider ON claude_sessions(provider);
CREATE INDEX idx_claude_sessions_last_heartbeat ON claude_sessions(last_heartbeat);

-- Lessons table - Task grouping by learning objective
CREATE TABLE IF NOT EXISTS lessons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'archived')),
    priority INT DEFAULT 0,
    tasks_total INT DEFAULT 0,
    tasks_completed INT DEFAULT 0,
    estimated_duration_minutes INT,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_lessons_project ON lessons(project_id);
CREATE INDEX idx_lessons_status ON lessons(status);
CREATE INDEX idx_lessons_priority ON lessons(priority);

-- Distributed task queue table - Enhanced task assignment
CREATE TABLE IF NOT EXISTS distributed_task_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key VARCHAR(255) UNIQUE NOT NULL,
    task_type VARCHAR(100) NOT NULL,
    task_data JSONB NOT NULL,
    priority INT NOT NULL DEFAULT 0,
    lesson_id UUID REFERENCES lessons(id) ON DELETE SET NULL,
    target_session_id UUID REFERENCES claude_sessions(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'assigned', 'in_progress', 'completed', 'failed', 'cancelled')),
    claimed_by UUID REFERENCES claude_sessions(id) ON DELETE SET NULL,
    claimed_at TIMESTAMP,
    claim_expires_at TIMESTAMP,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_distributed_task_queue_status ON distributed_task_queue(status);
CREATE INDEX idx_distributed_task_queue_priority ON distributed_task_queue(priority, status);
CREATE INDEX idx_distributed_task_queue_lesson ON distributed_task_queue(lesson_id);
CREATE INDEX idx_distributed_task_queue_claimed_by ON distributed_task_queue(claimed_by);
CREATE INDEX idx_distributed_task_queue_claim_expires ON distributed_task_queue(claim_expires_at);
CREATE INDEX idx_distributed_task_queue_idempotency ON distributed_task_queue(idempotency_key);
CREATE INDEX idx_distributed_task_queue_created ON distributed_task_queue(created_at DESC);

-- Distributed locks table - Prevent double-assignment
CREATE TABLE IF NOT EXISTS distributed_locks (
    lock_key VARCHAR(255) PRIMARY KEY,
    owner_id VARCHAR(255) NOT NULL,
    acquired_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    renewed_count INT DEFAULT 0,
    metadata JSONB
);

CREATE INDEX idx_distributed_locks_expires ON distributed_locks(expires_at);
CREATE INDEX idx_distributed_locks_owner ON distributed_locks(owner_id);

-- Session affinity table - Time-window and lesson-based scheduling
CREATE TABLE IF NOT EXISTS session_affinity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES claude_sessions(id) ON DELETE CASCADE,
    lesson_id UUID REFERENCES lessons(id) ON DELETE CASCADE,
    time_window_start TIMESTAMP,
    time_window_end TIMESTAMP,
    affinity_score FLOAT DEFAULT 1.0,
    last_used TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_session_affinity_session ON session_affinity(session_id);
CREATE INDEX idx_session_affinity_lesson ON session_affinity(lesson_id);
CREATE INDEX idx_session_affinity_time_window ON session_affinity(time_window_start, time_window_end);

-- Trigger to update claude_sessions.updated_at
CREATE OR REPLACE FUNCTION update_claude_sessions_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER claude_sessions_update_timestamp
BEFORE UPDATE ON claude_sessions
FOR EACH ROW
EXECUTE FUNCTION update_claude_sessions_timestamp();

-- Trigger to update lessons.updated_at
CREATE OR REPLACE FUNCTION update_lessons_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER lessons_update_timestamp
BEFORE UPDATE ON lessons
FOR EACH ROW
EXECUTE FUNCTION update_lessons_timestamp();

-- Trigger to update distributed_task_queue.updated_at
CREATE OR REPLACE FUNCTION update_distributed_task_queue_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER distributed_task_queue_update_timestamp
BEFORE UPDATE ON distributed_task_queue
FOR EACH ROW
EXECUTE FUNCTION update_distributed_task_queue_timestamp();
