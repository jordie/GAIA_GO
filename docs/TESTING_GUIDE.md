# Testing Guide: Phase 3 Reputation System

Comprehensive testing guide for the GAIA_GO Phase 3 reputation management system. Covers integration tests, load testing, end-to-end scenarios, and performance benchmarking.

## Test Structure

The reputation system testing is organized into four main categories:

```
pkg/services/rate_limiting/
├── integration_test.go       # Multi-service workflow tests
├── load_test.go              # High-concurrency and sustained load tests
├── e2e_test.go               # Complete user journeys and scenarios
└── performance_bench_test.go # Latency and throughput benchmarks
```

## Running Tests

### All Tests

```bash
# Run all tests with verbose output
go test -v ./pkg/services/rate_limiting

# Run all tests with race detection
go test -race ./pkg/services/rate_limiting

# Run all tests with coverage
go test -cover ./pkg/services/rate_limiting

# Generate coverage report
go test -coverprofile=coverage.out ./pkg/services/rate_limiting
go tool cover -html=coverage.out
```

### Unit Tests Only

```bash
# Skip long-running tests
go test -short ./pkg/services/rate_limiting

# Run specific test
go test -run TestFullAppealLifecycle ./pkg/services/rate_limiting
```

### Integration Tests

Integration tests verify multiple services working together:

```bash
# Run all integration tests
go test -v -run Integration ./pkg/services/rate_limiting

# Run specific integration test
go test -v -run TestFullAppealLifecycle ./pkg/services/rate_limiting

# Run with verbose output and timing
go test -v -run Integration -timeout 60s ./pkg/services/rate_limiting
```

**Coverage:**
- Full appeal lifecycle (submit → negotiate → approve)
- Multiple concurrent appeals
- Appeal with negotiation messages
- ML predictions informing decisions
- Duplicate appeal prevention
- Notification delivery workflow
- Analytics across lifecycle

### Load Tests

Load tests verify performance under concurrent operations:

```bash
# Run all load tests (skipped by default with -short)
go test -v ./pkg/services/rate_limiting -run Load

# Run specific load test
go test -v -run TestHighConcurrencyAppealSubmission ./pkg/services/rate_limiting

# Run with timeout for long tests
go test -v -run Load -timeout 300s ./pkg/services/rate_limiting
```

**Coverage:**
- 1000 concurrent appeal submissions
- 50 concurrent negotiation users sending 20 messages each
- 10,000 message thread performance
- 30-second sustained load at target RPS
- Memory efficiency with 500 users × 100 messages

**Expected Results:**
- Error rate < 5%
- Throughput: > 50 req/sec
- Average latency: < 100ms
- Memory efficient with large datasets

### End-to-End Tests

E2E tests simulate realistic user scenarios:

```bash
# Run all E2E tests
go test -v -run E2E ./pkg/services/rate_limiting

# Run specific scenario
go test -v -run TestE2E_UserAppealJourney ./pkg/services/rate_limiting
```

**Test Scenarios:**

1. **User Appeal Journey** - Complete user experience
   - Submit appeal → Get prediction → Negotiate → Receive approval
   - Validates entire workflow from user perspective
   - Tests notifications at each stage

2. **Admin Bulk Review** - Administrative workflows
   - View pending appeals → Bulk approve/deny → Track results
   - Tests bulk operations and status tracking

3. **Peer Analytics Context** - Comparative metrics
   - User views peer comparison → Gets insights → Understands position
   - Tests analytics relative to other users

4. **Notification Channels** - Multi-channel notifications
   - Submission, approval, and denial notifications
   - Tests notification delivery across types

5. **Appeal Timeline Accuracy** - Audit trail verification
   - Tracks every status change
   - Measures resolution time
   - Verifies event ordering

6. **ML Prediction Accuracy** - Intelligence validation
   - Recovery timeline predictions
   - Approval probability scoring
   - Auto-appeal suggestions

7. **Appeal Window Validation** - Business rule enforcement
   - 30-day appeal window strictly enforced
   - Old violations cannot be appealed

### Performance Benchmarks

Performance benchmarks measure latency and throughput:

```bash
# Run all benchmarks
go test -bench=. -benchmem ./pkg/services/rate_limiting

# Run specific benchmark
go test -bench=BenchmarkAppealServiceSingleSubmission -benchmem ./pkg/services/rate_limiting

# Run with custom duration
go test -bench=. -benchtime=10s -benchmem ./pkg/services/rate_limiting

# Compare before/after changes
go test -bench=. -benchmem ./pkg/services/rate_limiting > before.txt
# Make changes...
go test -bench=. -benchmem ./pkg/services/rate_limiting > after.txt
benchstat before.txt after.txt
```

**Benchmark Suites:**

| Benchmark | Purpose | Expected |
|-----------|---------|----------|
| AppealServiceSingleSubmission | Single appeal submit latency | < 10ms |
| AppealServiceReview | Appeal review latency | < 15ms |
| NegotiationServiceSendMessage | Message send latency | < 5ms |
| NegotiationServiceGetThread | Thread retrieval (100 msgs) | < 50ms |
| MLPredictionServiceRecovery | Recovery prediction latency | < 30ms |
| MLPredictionServiceApprovalProbability | Approval probability latency | < 25ms |
| AnalyticsServiceTrends | Trend analysis latency | < 40ms |
| HistoryServiceRecordChange | Status change recording | < 5ms |
| HistoryServiceTimeline | Timeline retrieval (20 events) | < 30ms |
| PeerAnalyticsComparison | Peer comparison calculation | < 50ms |
| NotificationServiceSend | Notification send latency | < 10ms |
| CompleteWorkflowSequential | Full workflow latency | < 200ms |
| LargeThreadMessageRetrieval | 1000 message thread | < 150ms |
| ConcurrentPeerStatistics | 1000 user peer lookups | < 50ms |
| DatabaseQueryEfficiency | Query performance (10k records) | < 5ms |

## Test Reports

### Coverage Report

Generate detailed coverage analysis:

```bash
# Generate coverage
go test -coverprofile=coverage.out ./pkg/services/rate_limiting

# View in browser
go tool cover -html=coverage.out

# Show coverage by function
go tool cover -func=coverage.out
```

### Benchmark Report

Analyze benchmark results:

```bash
# Run benchmarks with statistics
go test -bench=. -benchstat -benchmem ./pkg/services/rate_limiting | tee bench_results.txt

# Compare versions
go test -bench=. -benchmem ./pkg/services/rate_limiting > v1.txt
# Make changes...
go test -bench=. -benchmem ./pkg/services/rate_limiting > v2.txt
benchstat v1.txt v2.txt
```

### Load Test Report

Detailed load test analysis:

```bash
# Run with detailed output
go test -v -run Load -timeout 300s ./pkg/services/rate_limiting 2>&1 | tee load_results.txt
```

Typical load test output shows:
- Throughput (requests/sec)
- Success/failure counts
- Latency statistics (min/avg/max)
- Error rates
- Duration

## Testing Best Practices

### Before Committing Code

```bash
# 1. Run all tests
go test -v ./pkg/services/rate_limiting

# 2. Check race conditions
go test -race ./pkg/services/rate_limiting

# 3. Verify coverage
go test -cover ./pkg/services/rate_limiting

# 4. Run benchmarks for key operations
go test -bench=BenchmarkCompleteWorkflowSequential ./pkg/services/rate_limiting
```

### During Development

```bash
# Run specific test in watch mode (with entr or similar)
ls pkg/services/rate_limiting/*.go | entr go test -v -run TestFullAppealLifecycle ./pkg/services/rate_limiting

# Run tests with specific filter
go test -v -run "Integration" ./pkg/services/rate_limiting

# Test specific service in isolation
go test -v -run "AppealService" ./pkg/services/rate_limiting
```

### Performance Regression Testing

```bash
# Create baseline
go test -bench=. -benchmem ./pkg/services/rate_limiting > baseline.txt

# After changes
go test -bench=. -benchmem ./pkg/services/rate_limiting > current.txt

# Compare
benchstat baseline.txt current.txt
```

If you see:
- **faster**: Good! Optimization successful
- **slower**: Investigate root cause before committing
- **~**: No change

## Test Data

### Test Database

All tests use in-memory SQLite for:
- Isolation: Each test gets fresh database
- Speed: No I/O overhead
- Safety: No production data touched

Database schema includes:
- reputation_scores
- user_analytics_summary
- violations
- appeals
- appeal_negotiation_messages
- appeal_notifications
- appeal_status_changes
- ml_predictions
- peer_reputation_stats

### Sample Data

Tests create realistic sample data:
- 100-10,000 users depending on test
- 1-1000 messages per conversation
- Varying appeal outcomes (approved/denied/pending)
- Different reputation tiers and trends

## Continuous Integration

### CI Pipeline

Recommended CI configuration:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-go@v2
        with:
          go-version: 1.21

      # Unit tests with coverage
      - run: go test -v -race -coverprofile=coverage.out ./pkg/services/rate_limiting
      - run: go tool cover -func=coverage.out | grep total | awk '{print $3}'

      # Benchmarks for regression detection
      - run: go test -bench=. -benchmem ./pkg/services/rate_limiting
```

### Quality Gates

Recommended quality standards:

| Metric | Target | Action |
|--------|--------|--------|
| Coverage | > 80% | Fail if below |
| Test Pass Rate | 100% | Fail if any fail |
| Performance Regression | < 5% | Warn if slower |
| Race Detection | 0 | Fail if detected |

## Troubleshooting

### Test Failures

**Appeal status mismatch**
- Check test isolation - ensure previous test cleanup
- Verify database state assumptions

**Timeout errors**
- Increase `-timeout` flag: `go test -timeout 60s ...`
- Check for deadlocks in concurrent code

**Memory issues**
- Reduce test data size for load tests
- Check for goroutine leaks: `go test -run TestXXX -race`

**Race conditions detected**

```
# Run with race detector
go test -race ./pkg/services/rate_limiting

# If race detected:
# 1. Verify synchronization (channels, mutexes)
# 2. Check for shared state mutations
# 3. Use atomic operations for counters
```

### Performance Regression

If benchmarks show slowdown:

```bash
# 1. Run baseline
go test -bench=. -benchmem ./pkg/services/rate_limiting > before.txt

# 2. Identify slow benchmark
benchstat before.txt after.txt | grep slower

# 3. Profile the operation
go test -cpuprofile=cpu.prof -bench=SlowBench ./pkg/services/rate_limiting
go tool pprof cpu.prof

# 4. Check:
# - Database queries (indexing)
# - Algorithm complexity (loops)
# - Memory allocations (GC pressure)
# - Concurrency issues (lock contention)
```

## Test Maintenance

### Regular Tasks

- **Weekly**: Run full test suite with coverage
- **After schema changes**: Update database setup
- **Before release**: Run all tests + load tests
- **Monthly**: Review and optimize slow tests

### Adding New Tests

When adding new functionality:

1. **Write integration test first** - Define behavior
2. **Add E2E scenario** - Test user journey
3. **Add performance benchmark** - Establish baseline
4. **Update this guide** - Document the test

Example:

```go
// TestNewFeature verifies new functionality
func TestNewFeature(t *testing.T) {
    db := setupIntegrationTestDB(t)
    ctx := context.Background()

    svc := NewService(db)

    // Test implementation
    result, err := svc.NewMethod(ctx)

    // Verify behavior
    if err != nil {
        t.Errorf("Unexpected error: %v", err)
    }
}

// BenchmarkNewFeature measures performance
func BenchmarkNewFeature(b *testing.B) {
    // ... setup ...
    for i := 0; i < b.N; i++ {
        svc.NewMethod(ctx)
    }
}
```

## Performance Targets

### Service-Level Targets

| Operation | Target | Current |
|-----------|--------|---------|
| Appeal Submit | < 10ms | - |
| Appeal Review | < 15ms | - |
| Message Send | < 5ms | - |
| Thread Retrieval | < 50ms (100 msgs) | - |
| Prediction (Recovery) | < 30ms | - |
| Prediction (Approval) | < 25ms | - |
| Analytics (Trends) | < 40ms | - |

### System-Level Targets

| Metric | Target | Current |
|--------|--------|---------|
| Throughput | > 50 req/sec | - |
| P99 Latency | < 100ms | - |
| Error Rate | < 1% | - |
| Memory (100 appeals) | < 50MB | - |

## Resources

- **Go Testing**: https://golang.org/pkg/testing/
- **Table-Driven Tests**: https://github.com/golang/go/wiki/TableDrivenTests
- **Benchmarking**: https://golang.org/pkg/testing/#B
- **Race Detector**: https://golang.org/doc/articles/race_detector
- **Profiling**: https://golang.org/blog/pprof

## Test Execution Summary

Quick reference for common test commands:

```bash
# Quick validation (30 seconds)
go test -short ./pkg/services/rate_limiting

# Full test suite (2-5 minutes)
go test -v ./pkg/services/rate_limiting

# With coverage (3-6 minutes)
go test -v -cover ./pkg/services/rate_limiting

# Race detection (2x slower)
go test -race ./pkg/services/rate_limiting

# Load tests (5-10 minutes)
go test -v -run Load ./pkg/services/rate_limiting

# Benchmarks (varies by machine)
go test -bench=. ./pkg/services/rate_limiting

# CI pipeline (all checks)
go test -v -race -cover ./pkg/services/rate_limiting && \
go test -v -run Load -timeout 300s ./pkg/services/rate_limiting && \
go test -bench=. ./pkg/services/rate_limiting
```

## Next Steps

1. Run test suite to establish baseline
2. Review coverage report
3. Run load tests to verify scalability
4. Run benchmarks for performance baseline
5. Monitor tests during development
6. Optimize any slow operations
7. Maintain tests as features evolve
