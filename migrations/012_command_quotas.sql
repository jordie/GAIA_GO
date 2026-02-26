-- Phase 11.3: Command Execution Quotas and Resource Tracking
--
-- Tables:
-- 1. command_quota_rules - Per-user and default command quotas
-- 2. command_executions - Track all command executions
-- 3. command_quota_usage - Rolling window quota usage tracking

-- Command execution quota configuration
CREATE TABLE IF NOT EXISTS command_quota_rules (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,                         -- NULL = global default
    command_type VARCHAR(50),               -- 'shell', 'code', 'test', 'review', 'refactor'
    daily_limit INT DEFAULT 500,
    weekly_limit INT DEFAULT 3000,
    monthly_limit INT DEFAULT 10000,
    estimated_cpu INT DEFAULT 5,            -- Estimated CPU % per command
    estimated_mem INT DEFAULT 50,           -- Estimated memory MB per command
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT unique_user_command UNIQUE(user_id, command_type)
);

-- Create index on user_id for quick lookups
CREATE INDEX IF NOT EXISTS idx_quota_rules_user ON command_quota_rules(user_id);
CREATE INDEX IF NOT EXISTS idx_quota_rules_command ON command_quota_rules(command_type);

-- Command execution tracking
CREATE TABLE IF NOT EXISTS command_executions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    session_id VARCHAR(36),
    command_type VARCHAR(50),               -- 'shell', 'code', 'test', 'review', 'refactor'
    command_hash VARCHAR(64),               -- SHA256 of command for deduplication
    duration_ms INT,                        -- Execution time in milliseconds
    cpu_usage_percent FLOAT,                -- Peak CPU usage during execution
    memory_usage_mb INT,                    -- Peak memory usage during execution
    exit_code INT,                          -- Process exit code (0 = success)
    error_message TEXT,                     -- Error message if failed
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_session FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_executions_user ON command_executions(user_id, executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_executions_session ON command_executions(session_id);
CREATE INDEX IF NOT EXISTS idx_executions_type ON command_executions(command_type, executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_executions_hash ON command_executions(command_hash);

-- Command quota usage tracking (rolling window)
CREATE TABLE IF NOT EXISTS command_quota_usage (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    command_type VARCHAR(50),
    usage_period VARCHAR(20),               -- 'daily', 'weekly', 'monthly'
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    commands_executed INT DEFAULT 0,        -- Number of commands executed
    total_cpu_usage INT DEFAULT 0,          -- Total CPU % * commands
    total_memory_usage INT DEFAULT 0,       -- Total memory MB used
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT unique_usage UNIQUE(user_id, command_type, usage_period, period_start)
);

-- Create indexes for quota lookups
CREATE INDEX IF NOT EXISTS idx_quota_usage_user ON command_quota_usage(user_id, usage_period, period_start DESC);
CREATE INDEX IF NOT EXISTS idx_quota_usage_period ON command_quota_usage(usage_period, period_start);

-- Insert default quotas for each command type
INSERT INTO command_quota_rules (user_id, command_type, daily_limit, weekly_limit, monthly_limit, estimated_cpu, estimated_mem)
VALUES
    (NULL, 'shell',    500,  3000,  10000,  10, 100),   -- Shell commands - higher cost
    (NULL, 'code',     300,  1500,   5000,  15, 200),   -- AI code generation - expensive
    (NULL, 'test',    1000,  5000,  20000,   5,  50),   -- Tests - lighter weight
    (NULL, 'review',   200,  1000,   3000,  20, 300),   -- Code review - expensive
    (NULL, 'refactor', 200,  1000,   3000,  20, 300)    -- Refactoring - expensive
ON CONFLICT (user_id, command_type) DO NOTHING;

-- Create view for easy quota status checking
CREATE OR REPLACE VIEW user_quota_status AS
SELECT
    cqu.user_id,
    cqu.command_type,
    cqu.usage_period,
    cqr.daily_limit,
    cqr.weekly_limit,
    cqr.monthly_limit,
    cqu.commands_executed,
    CASE
        WHEN cqu.usage_period = 'daily' THEN cqr.daily_limit - cqu.commands_executed
        WHEN cqu.usage_period = 'weekly' THEN cqr.weekly_limit - cqu.commands_executed
        WHEN cqu.usage_period = 'monthly' THEN cqr.monthly_limit - cqu.commands_executed
    END as remaining_quota,
    cqu.total_cpu_usage,
    cqu.total_memory_usage,
    cqu.period_start,
    cqu.period_end
FROM command_quota_usage cqu
JOIN command_quota_rules cqr ON (
    (cqu.user_id = cqr.user_id OR cqr.user_id IS NULL)
    AND cqu.command_type = cqr.command_type
);

-- Create view for command execution statistics
CREATE OR REPLACE VIEW command_execution_stats AS
SELECT
    ce.user_id,
    ce.command_type,
    COUNT(*) as total_commands,
    AVG(ce.duration_ms) as avg_duration_ms,
    MAX(ce.duration_ms) as max_duration_ms,
    AVG(ce.cpu_usage_percent) as avg_cpu,
    MAX(ce.cpu_usage_percent) as max_cpu,
    AVG(ce.memory_usage_mb) as avg_memory_mb,
    MAX(ce.memory_usage_mb) as max_memory_mb,
    SUM(CASE WHEN ce.exit_code = 0 THEN 1 ELSE 0 END) as successful_commands,
    SUM(CASE WHEN ce.exit_code != 0 THEN 1 ELSE 0 END) as failed_commands,
    MIN(ce.executed_at) as first_execution,
    MAX(ce.executed_at) as last_execution
FROM command_executions ce
WHERE ce.executed_at > NOW() - INTERVAL '30 days'
GROUP BY ce.user_id, ce.command_type;
