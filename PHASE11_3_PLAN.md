# Phase 11.3: Command Execution Rate Limiting & Resource Quotas

## Overview

Phase 11.3 extends the Phase 11 rate limiting infrastructure to cover **command execution** operations, adding per-user quotas, resource tracking, and intelligent auto-throttling based on system load. This protects GAIA_GO and Go GAIA MVP from resource exhaustion while providing visibility into command execution patterns.

## Current State Analysis

### Command Execution Systems

**System 1: Workflow Executor** (`internal/orchestration/workflow/executor.go`)
- Executes task types: Shell, Code, Test, Review, Refactor
- Used by autonomous improvement loops
- Direct shell command execution via `exec.CommandContext`
- No current rate limiting or quota enforcement

**System 2: Command Handler** (`go_wrapper/stream/command_handler.go`)
- Handles process control: pause, resume, kill, send_input, get_state, send_signal
- Direct process interaction
- No current quotas
- Command logging but no enforcement

**System 3: HTTP Handlers** (`pkg/apps/*/handlers.go`)
- Individual app endpoints (typing, reading, math, piano, guessing)
- Uses existing Phase 11.2 HTTP middleware rate limiting
- No command-specific quotas

### Gaps to Address

1. **No per-user command execution quotas** - Anyone can spawn unlimited subprocesses
2. **No resource tracking per command** - Can't see which users consume most resources
3. **No auto-throttling based on system load** - Won't back off when system is under stress
4. **No quota warnings** - Users don't know approaching limits
5. **No command categorization** - All commands treated equally regardless of cost

## Architecture Design

### Component 1: Command Quota Service

**File:** `pkg/services/rate_limiting/command_quotas.go` (NEW)

```go
type CommandQuotaService struct {
    db        *gorm.DB
    rateLimiter RateLimiter
    resourceMonitor ResourceMonitor
}

type CommandQuotaRequest struct {
    UserID       int64
    SessionID    string
    CommandType  string  // "shell", "code", "test", etc
    CommandSize  int     // Approx command string length
    Estimated CPU int    // Estimated CPU cost %
    EstimatedMem int     // Estimated memory cost MB
}

type CommandQuotaDecision struct {
    Allowed              bool
    RemainingQuotaToday  int
    RemainingQuotaWeek   int
    EstimatedExecuteTime time.Duration
    ThrottleFactor       float64  // 1.0 = no throttle, 0.5 = half speed
    WarningMessage       string
}
```

**Key Methods:**
- `CheckCommandQuota(ctx, req)` → CommandQuotaDecision
- `RecordCommandExecution(ctx, userID, cmdType, duration, cpuUsage, memUsage)`
- `GetUserQuotaStatus(ctx, userID)` → Daily/Weekly/Monthly usage
- `AdjustQuotasForSystemLoad(ctx)` → Reduce quotas if system over-utilized

### Component 2: Resource Monitor Enhancement

**File:** `pkg/services/rate_limiting/resource_monitor.go` (EXISTING - ENHANCE)

Add methods to existing ResourceMonitor:
- `GetSystemLoad()` → Current CPU/memory/disk %
- `ShouldThrottleCommands()` → bool based on load
- `GetThrottleMultiplier()` → float64 (0.0 = blocked, 1.0 = full speed)

**Load-based Throttling:**
```
CPU Usage:  <70% = multiplier 1.0 (full)
            70-80% = multiplier 0.8 (80% speed)
            80-90% = multiplier 0.6 (60% speed)
            90-95% = multiplier 0.3 (30% speed)
            >95% = multiplier 0.0 (blocked)

Memory:     <75% = multiplier 1.0
            75-85% = multiplier 0.8
            85-95% = multiplier 0.6
            >95% = multiplier 0.0
```

### Component 3: Executor Integration

**File:** `internal/orchestration/workflow/executor.go` (MODIFY)

Add quota checking before command execution:

```go
func (e *Executor) Execute(ctx context.Context, workflow *Workflow, task *Task) (string, error) {
    // NEW: Check quota before execution
    userID := ctx.Value("user_id").(int64)
    sessionID := ctx.Value("session_id").(string)

    quota, err := e.quotaService.CheckCommandQuota(ctx, CommandQuotaRequest{
        UserID:      userID,
        SessionID:   sessionID,
        CommandType: task.Type,
        CommandSize: len(task.Command),
    })

    if !quota.Allowed {
        return "", fmt.Errorf("rate limit: %s (reset in %s)",
            quota.WarningMessage, quota.RemainingQuotaToday)
    }

    // Apply throttle factor if needed
    if quota.ThrottleFactor < 1.0 {
        log.Printf("Throttling command to %.0f%% speed", quota.ThrottleFactor*100)
        ctx = context.WithValue(ctx, "throttle_factor", quota.ThrottleFactor)
    }

    // Execute with tracking
    start := time.Now()
    output, err := e.executeTask(ctx, workflow, task)
    duration := time.Since(start)

    // Record execution
    if userID != nil {
        e.quotaService.RecordCommandExecution(ctx, userID, task.Type, duration, 0, 0)
    }

    return output, err
}
```

### Component 4: Database Schema Extension

**File:** `migrations/012_command_quotas.sql` (NEW)

```sql
-- Command execution quota configuration
CREATE TABLE command_quota_rules (
    id SERIAL PRIMARY KEY,
    user_id INT,                  -- NULL = global default
    command_type VARCHAR(50),     -- 'shell', 'code', 'test', 'review', 'refactor'
    daily_limit INT DEFAULT 500,
    weekly_limit INT DEFAULT 3000,
    monthly_limit INT DEFAULT 10000,
    estimated_cpu INT DEFAULT 5,  -- Estimated CPU % per command
    estimated_mem INT DEFAULT 50, -- Estimated memory MB per command
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, command_type)
);

-- Command execution tracking
CREATE TABLE command_executions (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    session_id VARCHAR(36),
    command_type VARCHAR(50),
    command_hash VARCHAR(64),     -- SHA256 of command for dedup
    duration_ms INT,
    cpu_usage_percent FLOAT,
    memory_usage_mb INT,
    exit_code INT,
    error_message TEXT,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
);

-- Command quota tracking (rolling window)
CREATE TABLE command_quota_usage (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    command_type VARCHAR(50),
    usage_period VARCHAR(20),     -- 'daily', 'weekly', 'monthly'
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    commands_executed INT DEFAULT 0,
    total_cpu_usage INT DEFAULT 0,
    total_memory_usage INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, command_type, usage_period, period_start)
);

-- Default quotas per command type (for cost accounting)
INSERT INTO command_quota_rules (command_type, daily_limit, weekly_limit, monthly_limit, estimated_cpu, estimated_mem) VALUES
('shell',    500,  3000,  10000,  10, 100),   -- Shell commands - higher cost
('code',     300,  1500,   5000,  15, 200),   -- AI code generation - expensive
('test',     1000, 5000,  20000,   5,  50),   -- Tests - lighter weight
('review',   200,  1000,   3000,  20, 300),   -- Code review - expensive
('refactor', 200,  1000,   3000,  20, 300);   -- Refactoring - expensive

CREATE INDEX idx_executions_user ON command_executions(user_id, executed_at DESC);
CREATE INDEX idx_executions_session ON command_executions(session_id);
CREATE INDEX idx_quota_usage_user ON command_quota_usage(user_id, usage_period, period_start);
```

### Component 5: Quota Status API

**File:** `pkg/http/handlers/quota_handlers.go` (NEW)

```go
// GET /api/quotas/user/{userID}
func GetUserQuotaStatus(c *gin.Context) {
    userID := c.Param("userID")

    usage, err := quotaService.GetUserQuotaStatus(ctx, userID)
    if err != nil {
        c.JSON(500, gin.H{"error": err.Error()})
        return
    }

    c.JSON(200, gin.H{
        "daily": usage.Daily,
        "weekly": usage.Weekly,
        "monthly": usage.Monthly,
        "throttle_factor": usage.ThrottleFactor,
        "system_load": usage.SystemLoad,
    })
}

// GET /api/quotas/commands
func GetCommandQuotaLimits(c *gin.Context) {
    limits, err := quotaService.GetCommandLimits(ctx)
    if err != nil {
        c.JSON(500, gin.H{"error": err.Error()})
        return
    }

    c.JSON(200, limits)
}

// GET /api/quotas/executions?user_id=123&since=2026-02-20
func GetCommandExecutionHistory(c *gin.Context) {
    userID := c.Query("user_id")
    since := c.Query("since")

    executions, err := quotaService.GetExecutionHistory(ctx, userID, since)
    if err != nil {
        c.JSON(500, gin.H{"error": err.Error()})
        return
    }

    c.JSON(200, executions)
}
```

### Component 6: REPL/Command Prompt Warnings

**File:** `pkg/services/rate_limiting/prompt_service.go` (NEW)

Provides user-friendly quota warning messages:

```go
func (qs *CommandQuotaService) GetQuotaWarning(ctx context.Context, userID int64) string {
    status := qs.GetUserQuotaStatus(ctx, userID)

    if status.Daily.Remaining < 10 {
        return "⚠️  WARNING: You have only 10 commands remaining today"
    }

    if status.ThrottleFactor < 1.0 {
        percent := int(status.ThrottleFactor * 100)
        return fmt.Sprintf("⚠️  THROTTLED: System load high. Running at %d%% speed", percent)
    }

    return ""
}
```

## Implementation Phases

### Phase 11.3.1: Database & Service Layer (Week 1)
1. Create migration `012_command_quotas.sql`
2. Implement `CommandQuotaService` in `rate_limiting` package
3. Enhance `ResourceMonitor` with load-based throttling
4. Write unit tests for quota checking and throttling logic

### Phase 11.3.2: Executor Integration (Week 1-2)
1. Modify `workflow/executor.go` to check quotas before execution
2. Modify `command_handler.go` to check quotas before process control
3. Add quota context to HTTP handlers
4. Implement throttle factor application to command execution

### Phase 11.3.3: API Endpoints (Week 2)
1. Create `quota_handlers.go` with status and history endpoints
2. Add quota display to HTTP responses (headers + body)
3. Implement prompt warning messages
4. Add quota info to command execution logs

### Phase 11.3.4: Monitoring & Dashboard (Week 2-3)
1. Create Prometheus metrics for command execution
2. Build admin dashboard for quota management
3. Implement quota adjustment endpoints (admin only)
4. Create quota alerts for system admin

### Phase 11.3.5: Testing & Optimization (Week 3-4)
1. Load test command execution under quota limits
2. Stress test auto-throttling behavior
3. Benchmark quota check latency (<5ms requirement)
4. Optimize database queries for quota checks

## Default Quota Tiers

### Free Tier (Default)
- Shell: 500 commands/day, 3,000/week
- Code: 300 commands/day, 1,500/week
- Test: 1,000 commands/day, 5,000/week
- Review: 200 commands/day, 1,000/week
- Refactor: 200 commands/day, 1,000/week

### Premium Tier (10x quotas)
- Shell: 5,000 commands/day, 30,000/week
- Code: 3,000 commands/day, 15,000/week
- Test: 10,000 commands/day, 50,000/week
- Review: 2,000 commands/day, 10,000/week
- Refactor: 2,000 commands/day, 10,000/week

### Enterprise Tier (Unlimited with throttling)
- No hard limits
- Auto-throttle based on system load
- Priority execution
- Dedicated resource pool

## Monitoring & Alerts

### Metrics to Track
- Commands executed per user per day/week/month
- Average execution time per command type
- CPU/memory usage per command
- Quota utilization % per user
- Throttle events and frequency
- System load at time of execution

### Alerts
- High quota utilization (>80% of daily limit)
- Sustained throttling (>50% of commands throttled)
- Unusual command patterns (spike detection)
- Long-running commands (>5 minutes)
- Failed commands (exit code != 0)

## Integration Points

### 1. Architect Dashboard
- New "Command Quotas" panel showing user/system-wide usage
- Admin interface for quota management
- Historical usage graphs
- Alert configuration

### 2. Go GAIA MVP REPL
- Quota warnings before/after command execution
- Throttle notifications if system under load
- Estimated wait time if throttled
- Quota reset timer display

### 3. Session Manager
- Track quota usage per session
- Inherit user quotas or apply session-specific limits
- Multi-user scenarios (shared sessions)

### 4. Orchestration System
- Quota-aware task scheduling
- Backoff and retry logic for throttled commands
- Task prioritization based on cost

## Success Criteria

- ✓ All commands pass quota checks before execution
- ✓ Quota checks add <5ms latency per request
- ✓ Users receive clear warnings when approaching limits
- ✓ System auto-throttles during high load (>80% CPU)
- ✓ Quotas can be adjusted by admins without redeployment
- ✓ Historical execution data available for 90 days
- ✓ No false positives (legitimate commands blocked)
- ✓ Supports 1,000+ concurrent users with accurate tracking

## Migration Path

### Day 1: Deploy with Monitoring
- Deploy Phase 11.3 code with quotas in "monitor" mode
- Set very high initial limits (won't actually block anything)
- Collect baseline usage metrics for 24-48 hours

### Day 2-3: Adjust Limits
- Analyze actual usage patterns
- Set realistic limits based on P95 usage
- Distribute quotas fairly across user tiers

### Day 4-7: Full Enforcement
- Enable quota enforcement for new sessions
- Grandfather existing sessions with higher limits
- Monitor for complaints/issues

### Week 2: Optimization
- Tune throttle thresholds based on system stability
- Adjust command cost estimates based on actual performance
- Fine-tune auto-throttling algorithm

## Rollback Plan

If issues arise:
1. Disable quota enforcement via feature flag
2. Keep quota tracking active for monitoring
3. Revert to HTTP-only rate limiting
4. Maintain quota data for analysis

## Performance Targets

- Quota check latency: <5ms (p99)
- Memory overhead: <50MB for 10,000 users
- Database queries per check: 1 (with caching)
- Throughput: 10,000+ quota checks/sec

## Future Enhancements

1. **Machine Learning**: Detect command patterns and predict resource usage
2. **Billing Integration**: Charge users based on actual resource consumption
3. **Priority Queuing**: Queue commands during high load instead of rejecting
4. **Fair-Share Scheduling**: Ensure no single user monopolizes resources
5. **Command Caching**: Cache results of expensive operations
6. **Distributed Execution**: Farm out expensive commands to worker pool

---

**Status:** Ready for implementation
**Estimated Duration:** 3-4 weeks
**Complexity:** Medium (extends existing rate limiting framework)
**Risk:** Low (quota checks are non-blocking in monitor mode)

