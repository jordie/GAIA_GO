# Phase 5: Comprehensive Testing Plan

## Overview

Phase 5 focuses on comprehensive testing of the rate limiting and resource monitoring systems implemented in Phases 1-4. This plan outlines unit tests, integration tests, load tests, and end-to-end tests.

## Testing Scope

### 1. Unit Tests

Unit tests verify individual components in isolation using mocks and fixtures.

#### Rate Limiter Service Tests

Location: `pkg/services/rate_limiting/rate_limiter_test.go` (to be created)

**Test Categories:**

1. **Limit Checking**
   - `TestCheckLimitPerSecond()` - Verify per-second sliding window
   - `TestCheckLimitPerMinute()` - Verify per-minute sliding window
   - `TestCheckLimitPerHour()` - Verify per-hour sliding window
   - `TestCheckLimitPerDay()` - Verify daily quota
   - `TestCheckLimitPerWeek()` - Verify weekly quota
   - `TestCheckLimitPerMonth()` - Verify monthly quota

2. **Rule Management**
   - `TestCreateRule()` - Create rate limit rules
   - `TestUpdateRule()` - Update existing rules
   - `TestDeleteRule()` - Delete rules
   - `TestGetRule()` - Retrieve rule by ID
   - `TestListRules()` - List all rules with filtering
   - `TestRulePriority()` - Verify rules evaluated in priority order

3. **Quota Management**
   - `TestGetQuota()` - Retrieve quota usage
   - `TestIncrementQuota()` - Increment quota counters
   - `TestQuotaReset()` - Verify quotas reset at period boundaries
   - `TestQuotaExceeded()` - Test quota enforcement

4. **Violation Tracking**
   - `TestRecordViolation()` - Log rate limit violations
   - `TestGetViolations()` - Query violation history
   - `TestViolationStats()` - Analyze violation patterns

5. **Reputation Integration (Phase 2)**
   - `TestReputationBasedLimits()` - Trusted users get higher limits
   - `TestAdaptiveLimits()` - Limits adjust based on user score
   - `TestReputationScoring()` - Clean requests increase score

6. **Cache Management**
   - `TestRuleCache()` - Rules are cached in memory
   - `TestCacheInvalidation()` - Cache invalidates when rules change
   - `TestCacheTTL()` - Cache expires after configured TTL

#### Admin Routes Tests

Location: `pkg/routes/admin_rate_limiting_routes_test.go` (already exists, expand)

**Existing Tests:**
- TestGetRateLimitStats
- TestListRateLimitRules
- TestCreateRateLimitRule
- TestUpdateRateLimitRule
- TestDeleteRateLimitRule
- TestGetRateLimitRule
- TestGetViolations

**Tests to Add:**
- `TestGetMetricsSummary()` - Verify metrics aggregation
- `TestGetRateLimitUsage()` - Current usage stats
- `TestCleanupOldBuckets()` - Data retention
- `TestCleanupOldViolations()` - Data retention
- `TestCleanupOldMetrics()` - Data retention
- `TestRateLimitingHealth()` - Service health check
- `TestErrorHandling()` - Invalid inputs
- `TestContentType()` - Verify JSON responses

#### Alert Service Tests

Location: `pkg/services/rate_limiting/alert_service_test.go` (already exists, expand)

**Tests to Add:**
- `TestAlertRuleRegistration()` - Register alert rules
- `TestAlertEvaluation()` - Evaluate conditions
- `TestAlertTriggering()` - Create alerts when conditions met
- `TestAlertResolution()` - Mark alerts as resolved
- `TestAlertSilencing()` - Temporarily silence alerts
- `TestMultipleRules()` - Multiple rules in parallel
- `TestEdgeCases()` - Boundary conditions

### 2. Integration Tests

Integration tests verify components working together with real databases.

Location: `pkg/services/rate_limiting/integration_test.go` (already exists, expand)

**Test Scenarios:**

1. **End-to-End Rate Limiting**
   ```go
   TestFullRateLimitCycle()
   - Create rules
   - Make requests within limits (allowed)
   - Make requests exceeding limits (blocked)
   - Verify violation records
   - Verify metrics tracking
   - Cleanup data
   ```

2. **Quota Reset**
   ```go
   TestDailyQuotaReset()
   - Set daily quota
   - Consume quota
   - Verify at period boundary quota resets
   - New period allows fresh requests
   ```

3. **Reputation Integration**
   ```go
   TestReputationAffectsLimits()
   - Create low-reputation user
   - Verify strict limits applied
   - Improve reputation
   - Verify limits increased
   ```

4. **Multi-Scope Limits**
   ```go
   TestMultipleScopeLimits()
   - Apply IP-based limits
   - Apply user-based limits
   - Apply API key limits
   - Verify all limits enforced simultaneously
   ```

5. **Cache Behavior**
   ```go
   TestCacheBehavior()
   - Rules cached on first load
   - Verify cache used for subsequent requests
   - Update rule
   - Verify cache invalidated
   - New rule version used
   ```

### 3. Load Tests

Load tests verify performance and scalability under concurrent load.

Location: `pkg/services/rate_limiting/load_test.go` (already exists, expand)

**Load Test Scenarios:**

1. **Concurrent Request Handling**
   ```go
   TestConcurrentRateLimitChecks()
   - 100 goroutines making concurrent requests
   - Verify correct limit enforcement
   - Measure latency (target: < 5ms p99)
   - Measure throughput (target: > 10,000 req/s)
   ```

2. **High Violation Rate**
   ```go
   TestHighViolationRate()
   - 1000 requests/sec exceeding limits
   - Verify violations recorded
   - Verify performance degradation < 20%
   ```

3. **Large Number of Rules**
   ```go
   TestManyRules()
   - Create 1000 rate limit rules
   - Verify rule evaluation time < 5ms
   - Verify memory usage reasonable
   ```

4. **Large Dataset**
   ```go
   TestLargeViolationHistory()
   - 100K+ violation records
   - Verify query performance
   - Verify cleanup operations efficient
   ```

5. **Sustained Load**
   ```go
   TestSustainedLoad()
   - Run for 1 hour at peak load
   - Verify stability
   - Verify no memory leaks
   - Verify no deadlocks
   ```

### 4. End-to-End Tests

E2E tests verify complete workflows through HTTP API.

Location: `pkg/routes/admin_rate_limiting_routes_integration_test.go` (to be created)

**E2E Scenarios:**

1. **Full Admin Workflow**
   ```
   POST /api/admin/rate-limiting/rules -> Create rule
   GET /api/admin/rate-limiting/rules/global -> List rules
   PUT /api/admin/rate-limiting/rules/1 -> Update rule
   GET /api/admin/rate-limiting/usage/global/ip/192.168.1.1 -> Check usage
   GET /api/admin/rate-limiting/violations/global -> List violations
   POST /api/admin/rate-limiting/cleanup/buckets -> Cleanup
   DELETE /api/admin/rate-limiting/rules/1 -> Delete rule
   GET /api/admin/rate-limiting/health -> Health check
   ```

2. **Multi-Tenant Isolation**
   ```
   - Create rules for system A
   - Create rules for system B
   - Verify rules isolated
   - Verify limits don't affect other systems
   ```

3. **Quota Management Workflow**
   ```
   GET /api/admin/rate-limiting/quotas/:system/:scope/:value
   POST /api/admin/rate-limiting/quotas/:system/:scope/:value/increment
   - Get current quota
   - Increment quota usage
   - Verify remaining quota calculated correctly
   - Verify quota period tracked
   ```

## Test Coverage Goals

| Component | Coverage Target | Priority |
|-----------|-----------------|----------|
| Rate Limiter (CheckLimit) | >95% | Critical |
| Rule Management | >90% | High |
| Quota Management | >90% | High |
| Violation Tracking | >85% | Medium |
| Alert Service | >80% | Medium |
| Routes/API | >85% | High |

## Performance Targets

| Operation | Latency (p99) | Throughput | Target |
|-----------|--------------|-----------|--------|
| CheckLimit | < 5ms | > 10,000 req/s | Critical |
| GetUsage | < 10ms | N/A | High |
| GetRules | < 1ms (cached) | N/A | High |
| CreateRule | < 50ms | N/A | Medium |
| Query Violations | < 100ms | N/A | Medium |
| Cleanup | < 1s per 1M records | N/A | Low |

## Test Data

### Fixtures

```go
// Standard test data sets
const (
    TestUserCount = 100
    TestRuleCount = 50
    TestViolationRecords = 10000
)

// Factory functions
createTestUser(id int) User
createTestRule(system, scope string) Rule
createTestViolation() Violation
```

### Database Setup

```go
// setupTestDB creates in-memory SQLite for tests
func setupTestDB(t *testing.T) *gorm.DB
func setupTestDBWithData(t *testing.T) *gorm.DB
func teardownTestDB(db *gorm.DB)
```

## Test Organization

### Directory Structure
```
pkg/services/rate_limiting/
├── rate_limiter_test.go           # Unit tests
├── models_test.go                 # Model tests
├── integration_test.go            # Integration tests (expand)
├── load_test.go                   # Load tests (expand)
└── testdata/
    ├── rules.json                 # Test fixtures
    ├── users.json                 # Test fixtures
    └── violations.json            # Test fixtures

pkg/routes/
├── admin_rate_limiting_routes_test.go  # Route unit tests (expand)
└── admin_rate_limiting_routes_integration_test.go  # E2E tests (create)
```

### Test Naming Convention

```
Test{Component}{Scenario}{Condition}
Examples:
- TestCheckLimitPerSecond
- TestCreateRuleWithInvalidData
- TestConcurrentRateLimitChecks
- TestQuotaResetAtMidnight
```

## Execution Strategy

### Phase 5a: Unit Tests (Week 1)
- [ ] Write rate limiter unit tests
- [ ] Write rule management tests
- [ ] Write quota management tests
- [ ] Target: 90%+ code coverage

### Phase 5b: Integration Tests (Week 2)
- [ ] Expand existing integration tests
- [ ] Test multi-component workflows
- [ ] Test database persistence
- [ ] Test cache invalidation

### Phase 5c: Load & Performance Tests (Week 2-3)
- [ ] Write load tests
- [ ] Measure latency benchmarks
- [ ] Verify throughput targets
- [ ] Profile memory usage

### Phase 5d: E2E Tests (Week 3)
- [ ] Create HTTP API tests
- [ ] Test complete workflows
- [ ] Test error scenarios
- [ ] Test multi-tenant isolation

### Phase 5e: Documentation & Cleanup (Week 4)
- [ ] Document test results
- [ ] Update README with test instructions
- [ ] Create CI/CD test pipeline
- [ ] Archive test coverage reports

## Running Tests

### Run All Tests
```bash
go test ./pkg/services/rate_limiting ./pkg/routes -v
```

### Run Specific Test Suite
```bash
go test ./pkg/services/rate_limiting -run TestRateLimiter -v
go test ./pkg/routes -run TestAdmin -v
```

### Run with Coverage
```bash
go test -cover ./pkg/services/rate_limiting ./pkg/routes
go test -coverprofile=coverage.out ./pkg/services/rate_limiting
go tool cover -html=coverage.out
```

### Run Load Tests
```bash
go test -bench=. -benchmem ./pkg/services/rate_limiting -run BenchmarkRateLimit
```

### Run Specific Test with Timeout
```bash
go test -timeout 30s -run TestConcurrentRateLimitChecks ./pkg/services/rate_limiting -v
```

## Known Issues & Blockers

### Current Compilation Issues
The following files have compilation errors preventing full test suite execution:
- `appeal_negotiation_service.go` - Invalid GORM method `From`
- `appeal_notification_service.go` - Undefined constant `AppealNotificationApproved`
- `admin_bulk_operations_service_test.go` - Missing test fixtures

**Resolution Path:**
1. Fix missing imports in appeal services
2. Add missing constant definitions
3. Update test fixtures for appeal services
4. Re-run full test suite

## Success Criteria

- [ ] 90%+ code coverage on rate_limiter.go
- [ ] 85%+ code coverage on admin routes
- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] Load tests meet performance targets
- [ ] E2E tests validating complete workflows
- [ ] Documentation updated with test coverage report
- [ ] CI/CD pipeline configured to run tests

## Related Documentation

- [Rate Limiting Guide](./RATE_LIMITING_GUIDE.md)
- [API Routes](../pkg/routes/admin_rate_limiting_routes.go)
- [Rate Limiter Implementation](../pkg/services/rate_limiting/rate_limiter.go)

## Appendix: Test Templates

### Unit Test Template
```go
func TestCheckLimitPerSecond(t *testing.T) {
    db := setupTestDB(t)
    defer teardownTestDB(db)

    limiter := NewPostgresRateLimiter(db, defaultConfig())

    // Create rule
    rule := createTestRule("global", "ip")
    ruleID, err := limiter.CreateRule(context.Background(), rule)
    require.NoError(t, err)

    // Test within limit
    req := LimitCheckRequest{
        SystemID: "global",
        Scope: "ip",
        ScopeValue: "192.168.1.1",
    }

    decision, err := limiter.CheckLimit(context.Background(), req)
    assert.NoError(t, err)
    assert.True(t, decision.Allowed)

    // Test exceeding limit
    // ... make requests to exceed
    decision, err = limiter.CheckLimit(context.Background(), req)
    assert.NoError(t, err)
    assert.False(t, decision.Allowed)
}
```

### Integration Test Template
```go
func TestFullRateLimitCycle(t *testing.T) {
    // Setup
    db := setupTestDBWithData(t)
    defer teardownTestDB(db)

    // Execute workflow
    // Verify results at each step

    // Cleanup verification
    cleanup, err := limiter.CleanupOldBuckets(context.Background(), time.Now())
    assert.NoError(t, err)
    assert.Greater(t, cleanup, int64(0))
}
```

### Load Test Template
```go
func BenchmarkRateLimitCheck(b *testing.B) {
    db := setupTestDB(&testing.T{})
    limiter := NewPostgresRateLimiter(db, defaultConfig())
    req := createTestRequest()

    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        limiter.CheckLimit(context.Background(), req)
    }
}
```
