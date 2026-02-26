# Phase 11: Rate Limiting & Resource Quotas - Shared Service Architecture

## Overview

Implement a **shared, database-backed rate limiting service** that protects both GAIA_GO (educational platform) and Go GAIA MVP (interactive REPL) systems from abuse while respecting user quotas and system resources.

## Architecture

### Multi-Tenant Rate Limiting Service

```
┌─────────────────────────────────────────────────────────┐
│         Shared Rate Limiting Service                     │
│  (Database-backed, stateless, horizontally scalable)     │
└──────────────────┬──────────────────────────────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
    ┌────────┐ ┌────────┐ ┌────────┐
    │GAIA_GO │ │REPL    │ │Future  │
    │API     │ │Commands│ │Systems │
    │        │ │        │ │        │
    └────────┘ └────────┘ └────────┘
        │          │          │
        └──────────┼──────────┘
                   │
        ┌──────────▼──────────┐
        │  PostgreSQL         │
        │ - Configs           │
        │ - Buckets           │
        │ - Violations        │
        │ - Quotas            │
        └─────────────────────┘
```

## Database Schema

### Tables to Create

**1. rate_limit_rules** - Define rate limit policies
```sql
CREATE TABLE rate_limit_rules (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(255) UNIQUE NOT NULL,
    system_id VARCHAR(50) NOT NULL,  -- 'gaia_go', 'gaia_mvp', 'global'
    scope VARCHAR(50) NOT NULL,      -- 'ip', 'session', 'user', 'api_key'
    scope_value VARCHAR(255),        -- Specific IP/session/user/key or NULL for default
    limit_type VARCHAR(50) NOT NULL, -- 'requests_per_second', 'requests_per_minute', 'daily_quota'
    limit_value INTEGER NOT NULL,
    resource_type VARCHAR(100),      -- 'confirm_request', 'pattern_crud', 'repl_command', etc
    enabled BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 100,    -- Lower = applied first
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rules_system ON rate_limit_rules(system_id);
CREATE INDEX idx_rules_scope ON rate_limit_rules(scope, scope_value);
```

**2. rate_limit_buckets** - Sliding window tracking
```sql
CREATE TABLE rate_limit_buckets (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER REFERENCES rate_limit_rules(id) ON DELETE CASCADE,
    system_id VARCHAR(50) NOT NULL,
    scope VARCHAR(50) NOT NULL,
    scope_value VARCHAR(255) NOT NULL,
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    request_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(rule_id, scope_value, window_start)
);

CREATE INDEX idx_buckets_scope_time ON rate_limit_buckets(system_id, scope, scope_value, window_start DESC);
```

**3. resource_quotas** - Daily/monthly quotas
```sql
CREATE TABLE resource_quotas (
    id SERIAL PRIMARY KEY,
    system_id VARCHAR(50) NOT NULL,
    scope VARCHAR(50) NOT NULL,
    scope_value VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    quota_period VARCHAR(20) NOT NULL,  -- 'daily', 'weekly', 'monthly'
    quota_limit INTEGER NOT NULL,
    quota_used INTEGER DEFAULT 0,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    last_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(system_id, scope, scope_value, resource_type, period_start)
);

CREATE INDEX idx_quotas_scope_period ON resource_quotas(system_id, scope, scope_value, period_start DESC);
```

**4. rate_limit_violations** - Security audit trail
```sql
CREATE TABLE rate_limit_violations (
    id SERIAL PRIMARY KEY,
    system_id VARCHAR(50) NOT NULL,
    rule_id INTEGER REFERENCES rate_limit_rules(id),
    scope VARCHAR(50) NOT NULL,
    scope_value VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100),
    violated_limit INTEGER,
    actual_count INTEGER,
    violation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    request_path VARCHAR(500),
    request_method VARCHAR(10),
    user_agent VARCHAR(500),
    blocked BOOLEAN DEFAULT true,
    severity VARCHAR(20)  -- 'low', 'medium', 'high', 'critical'
);

CREATE INDEX idx_violations_system_time ON rate_limit_violations(system_id, violation_time DESC);
CREATE INDEX idx_violations_scope ON rate_limit_violations(scope, scope_value, violation_time DESC);
```

**5. rate_limit_metrics** - Historical metrics for analytics
```sql
CREATE TABLE rate_limit_metrics (
    id SERIAL PRIMARY KEY,
    system_id VARCHAR(50) NOT NULL,
    scope VARCHAR(50),
    scope_value VARCHAR(255),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    requests_processed INTEGER DEFAULT 0,
    requests_allowed INTEGER DEFAULT 0,
    requests_blocked INTEGER DEFAULT 0,
    avg_response_time_ms FLOAT DEFAULT 0,
    cpu_usage_percent FLOAT DEFAULT 0,
    memory_usage_percent FLOAT DEFAULT 0
);

CREATE INDEX idx_metrics_system_time ON rate_limit_metrics(system_id, timestamp DESC);
```

## Service Implementation

### File Structure

```
pkg/services/rate_limiting/
├── rate_limiter.go        # Main service interface
├── rule_manager.go        # Rule CRUD and matching
├── bucket_manager.go      # Sliding window buckets
├── quota_manager.go       # Daily/monthly quotas
├── violation_tracker.go   # Security events
├── middleware.go          # HTTP middleware
├── config.go              # Configuration
└── models.go              # Data models
```

### Core Service Interface

```go
// RateLimiter is the main rate limiting service
type RateLimiter interface {
    // Check if request is allowed
    CheckLimit(ctx context.Context, req LimitCheckRequest) (Decision, error)

    // Get current usage for a scope
    GetUsage(ctx context.Context, system, scope, value string) (Usage, error)

    // Get rules for a system
    GetRules(ctx context.Context, system string) ([]Rule, error)

    // Update rules (admin)
    UpdateRule(ctx context.Context, rule Rule) error
    CreateRule(ctx context.Context, rule Rule) error
    DeleteRule(ctx context.Context, ruleID int64) error
}

// LimitCheckRequest contains request metadata
type LimitCheckRequest struct {
    SystemID     string                 // 'gaia_go', 'gaia_mvp'
    Scope        string                 // 'ip', 'session', 'user', 'api_key'
    ScopeValue   string                 // Actual IP/session/user/key
    ResourceType string                 // Endpoint/command type
    RequestPath  string                 // /api/claude/confirm/request
    Method       string                 // GET, POST, etc
    Headers      map[string]string      // For user-agent, api-key extraction
    Metadata     map[string]interface{} // Custom data
}

// Decision is the rate limiting decision
type Decision struct {
    Allowed           bool
    RuleID            int64
    Reason            string
    RetryAfterSeconds int
    Limit             int
    Remaining         int
    ResetTime         time.Time
}
```

## Integration Points

### GAIA_GO Integration

```go
// In cmd/server/main.go
rateLimiter := rate_limiting.NewPostgresRateLimiter(db, "gaia_go")
router.Use(rate_limiting.Middleware(rateLimiter, rateLimitConfig))

// Applies to all endpoints:
// - POST /api/claude/confirm/request (limit: 100 req/min per session)
// - GET /api/claude/confirm/stats/{sessionID} (limit: 1000 req/hour per IP)
// - POST /api/claude/confirm/patterns (limit: 10 patterns/day per user)
```

### Go GAIA MVP Integration

```go
// In repl/repl.go
rateLimiter := rate_limiting.NewPostgresRateLimiter(db, "gaia_mvp")

// In command execution:
decision, err := rateLimiter.CheckLimit(ctx, rate_limiting.LimitCheckRequest{
    SystemID:     "gaia_mvp",
    Scope:        "session",
    ScopeValue:   sessionID,
    ResourceType: "repl_command",
    Metadata: map[string]interface{}{
        "command_type": "query",
        "tokens_used": 150,
    },
})

if !decision.Allowed {
    return fmt.Errorf("rate limit exceeded: %s (retry after %ds)",
        decision.Reason, decision.RetryAfterSeconds)
}
```

## Default Rate Limits

### GAIA_GO System

| Endpoint | Scope | Limit | Period |
|----------|-------|-------|--------|
| `/api/claude/confirm/request` | session | 100 | minute |
| `/api/claude/confirm/request` | ip | 1000 | minute |
| `/api/claude/confirm/patterns` (POST) | user | 10 | day |
| `/api/claude/confirm/patterns` (PUT/DELETE) | user | 5 | hour |
| `/api/claude/confirm/stats` | ip | 1000 | hour |

### Go GAIA MVP System

| Command | Scope | Limit | Period |
|---------|-------|-------|--------|
| `query` (REPL) | session | 50 | minute |
| `query` | ip | 500 | minute |
| `execute` (operations) | session | 10 | hour |
| `import` (data) | user | 100MB | day |

## Implementation Phases

### Phase 11.1: Database & Core Service (3-4 days)
- [ ] Create migrations for all tables
- [ ] Implement RateLimiter interface with PostgreSQL backend
- [ ] Implement Rule, Bucket, and Quota managers
- [ ] Write comprehensive unit tests

### Phase 11.2: Middleware & Integration (2-3 days)
- [ ] Implement HTTP middleware for Chi router
- [ ] Integrate with GAIA_GO endpoints
- [ ] Add response headers (X-RateLimit-*)
- [ ] Create error responses (429 Too Many Requests)

### Phase 11.3: Go GAIA MVP Integration (2-3 days)
- [ ] Integrate with REPL command execution
- [ ] Add usage feedback to REPL prompts
- [ ] Implement quota warnings

### Phase 11.4: Admin Dashboard (2-3 days)
- [ ] Create admin endpoints for rate limit management
- [ ] Build dashboard for viewing violations
- [ ] Implement rule configuration UI
- [ ] Add analytics and reporting

### Phase 11.5: Testing & Optimization (2 days)
- [ ] Load testing with concurrent requests
- [ ] Performance optimization of database queries
- [ ] Security audit
- [ ] Documentation

## Success Criteria

- ✅ All rate limit rules enforced correctly
- ✅ Zero false positives (legitimate requests blocked)
- ✅ Sub-millisecond rate limit check overhead
- ✅ Both systems protected simultaneously
- ✅ Complete audit trail of violations
- ✅ Admin interface for rule management
- ✅ Performance: <5ms per rate limit check (p99)
- ✅ Support for 1000+ concurrent users per system

## Timeline

**Total Duration**: 11-16 days
**Recommended Pace**: 3 days per phase

## Dependencies

- PostgreSQL 12+ (already available)
- GORM (already in use)
- Chi router (already in use)
- No new external dependencies

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Database bottleneck | Performance | Connection pooling, query optimization, caching |
| False positives | UX degradation | Conservative defaults, gradual rollout, override capability |
| Clock skew | Inaccurate limits | NTP synchronization, server-time based windows |
| Distributed state | Inconsistency | Centralized PostgreSQL, no client-side state |

## Future Enhancements

- **Phase 11.5**: Redis caching layer for ultra-low latency
- **Phase 12**: Distributed rate limiting across multiple servers
- **Phase 13**: Machine learning-based anomaly detection
- **Phase 14**: Adaptive rate limiting based on system load

---

**Status**: Ready for implementation
**Next Action**: Start Phase 11.1 - Database schema and core service
