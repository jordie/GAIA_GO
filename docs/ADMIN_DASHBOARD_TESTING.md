# Admin Dashboard Testing Guide

Comprehensive testing guide for the GAIA_GO Admin Dashboard including load tests, stress tests, integration tests, and performance benchmarks.

## Table of Contents

1. [Overview](#overview)
2. [Test Types](#test-types)
3. [Running Tests](#running-tests)
4. [Performance Targets](#performance-targets)
5. [Load Testing](#load-testing)
6. [Stress Testing](#stress-testing)
7. [Integration Testing](#integration-testing)
8. [Benchmarking](#benchmarking)
9. [Interpreting Results](#interpreting-results)
10. [Troubleshooting](#troubleshooting)

## Overview

The admin dashboard has comprehensive test coverage including:

- **Unit Tests** (16): Individual endpoint functionality
- **Load Tests** (12): Concurrent request handling
- **Integration Tests** (9): Complete workflows
- **Benchmarks** (2): Performance measurements
- **Edge Cases** (5): Boundary conditions and error scenarios

**Total: 44 test cases**

## Test Types

### Unit Tests

Test individual endpoints in isolation.

```bash
go test -v -run '^TestGet' ./pkg/routes
```

**Examples:**
- TestGetDashboardOverview
- TestListAppeals
- TestGetAnalyticsTrends

### Load Tests

Test system behavior under concurrent load.

```bash
go test -v -run '^TestLoad' ./pkg/routes
```

**Examples:**
- TestLoadDashboardOverview: 10 concurrent users × 100 requests
- TestLoadListAppeals: 20 concurrent users × 50 requests
- TestLoadFilterAppeals: 15 concurrent users × 75 requests

### Stress Tests

Test system behavior at the breaking point.

```bash
go test -v -run '^TestStress' ./pkg/routes
```

**Examples:**
- TestStressAnalyticsTrends: 50 concurrent users
- TestStressSystemHealth: 100 concurrent users

### Integration Tests

Test complete user workflows end-to-end.

```bash
go test -v -run '^TestIntegration' ./pkg/routes
```

**Examples:**
- TestIntegrationDashboardWorkflow: 7-step user journey
- TestIntegrationMultipleUsersSimultaneous: 10 concurrent users
- TestIntegrationFullDashboard: All endpoints together

### Edge Cases

Test boundary conditions and error scenarios.

```bash
go test -v -run '^TestEdgeCase' ./pkg/routes
```

**Examples:**
- TestEdgeCaseEmptyDatabase: No data
- TestEdgeCaseInvalidParameters: Invalid inputs
- TestEdgeCaseLargeDatasets: 10,000 appeals

### Benchmarks

Measure performance under various conditions.

```bash
go test -bench=. ./pkg/routes
```

**Examples:**
- BenchmarkDashboardOverview
- BenchmarkConcurrentRequests
- BenchmarkPaginationPerformance

## Running Tests

### Run All Tests

```bash
# Verbose output
go test -v ./pkg/routes

# With coverage
go test -v -coverprofile=coverage.out ./pkg/routes
go tool cover -html=coverage.out
```

### Run Specific Test Categories

```bash
# Unit tests only
go test -v -run '^Test[^L^I^E^S]' ./pkg/routes

# Load tests only
go test -v -run '^TestLoad' ./pkg/routes

# Integration tests only
go test -v -run '^TestIntegration' ./pkg/routes

# Edge cases only
go test -v -run '^TestEdgeCase' ./pkg/routes
```

### Run in Short Mode (Skip Large Dataset Tests)

```bash
# Excludes long-running tests with 5000+ appeals
go test -short -v ./pkg/routes
```

### Run with Race Condition Detection

```bash
# Detects data races in concurrent tests
go test -race ./pkg/routes
```

### Run Specific Test

```bash
go test -v -run TestLoadDashboardOverview ./pkg/routes
```

### Run Benchmarks

```bash
# All benchmarks
go test -bench=. ./pkg/routes

# Specific benchmark
go test -bench=BenchmarkDashboardOverview ./pkg/routes

# With timing information
go test -bench=. -benchtime=10s ./pkg/routes

# Memory allocations
go test -bench=. -benchmem ./pkg/routes
```

## Performance Targets

### Dashboard Endpoints

| Endpoint | Metric | Target | Alert |
|----------|--------|--------|-------|
| Overview | Avg Latency | < 200ms | > 500ms |
| Overview | P99 Latency | < 500ms | > 1000ms |
| Overview | Success Rate | > 99% | < 95% |
| Appeals | Avg Latency | < 200ms | > 500ms |
| Appeals | Throughput | > 100 req/s | < 50 req/s |
| Filters | P95 Latency | < 300ms | > 500ms |
| Analytics | P99 Latency | < 1000ms | > 2000ms |

### Concurrent Load

| Scenario | Users | Requests | Target Success |
|----------|-------|----------|-----------------|
| Normal | 10-20 | 50-100 ea | 99%+ |
| High | 50 | 100 ea | 95%+ |
| Stress | 100+ | 50 ea | 85%+ |

### Database Operations

| Operation | Latency | Throughput |
|-----------|---------|-----------|
| Single Query | < 10ms | N/A |
| Aggregate | < 100ms | N/A |
| Pagination | < 50ms | N/A |

## Load Testing

### TestLoadDashboardOverview

Tests dashboard metrics endpoint under load.

**Configuration:**
- Concurrency: 10 users
- Requests per user: 100
- Total requests: 1,000
- Dataset: 1,000 appeals

**Expected Results:**
```
Success Rate: ~99%
Avg Latency: 100-200ms
P99 Latency: 300-500ms
Throughput: 50-100 req/s
```

**Command:**
```bash
go test -v -run TestLoadDashboardOverview ./pkg/routes
```

### TestLoadListAppeals

Tests appeal pagination under load.

**Configuration:**
- Concurrency: 20 users
- Requests per user: 50
- Total requests: 1,000
- Dataset: 2,000 appeals

**Expected Results:**
```
Success Rate: ~99%
Avg Latency: 80-150ms
P99 Latency: 250-400ms
Throughput: 100-150 req/s
```

### TestConcurrentPagination

Tests pagination with concurrent page requests.

**Configuration:**
- Pages: 1-20
- Concurrent requests: 20
- Total requests: 20

**Expected Results:**
```
All requests successful
No duplicate records
Consistent ordering
```

## Stress Testing

### TestStressAnalyticsTrends

Tests analytics under high concurrency.

**Configuration:**
- Concurrency: 50 users
- Requests per user: 100
- Total requests: 5,000
- Dataset: 5,000 appeals

**Expected Results:**
```
Success Rate: ~90%+ (acceptable degradation)
P99 Latency: < 2 seconds
Max Latency: < 3 seconds
System remains responsive
```

### TestStressSystemHealth

Tests health check under maximum load.

**Configuration:**
- Concurrency: 100 users
- Requests per user: 50
- Total requests: 5,000

**Expected Results:**
```
Success Rate: 95%+
Avg Latency: < 100ms
P99 Latency: < 300ms (health checks are fast)
No timeouts
```

## Integration Testing

### TestIntegrationDashboardWorkflow

Tests complete 7-step user journey.

**Steps:**
1. View dashboard overview
2. View appeals list
3. Filter by status
4. View analytics
5. Check predictions
6. Generate report
7. Check system health

**Expected:**
```
All steps complete successfully
Data consistency maintained
Response times acceptable
```

**Run:**
```bash
go test -v -run TestIntegrationDashboardWorkflow ./pkg/routes
```

### TestIntegrationMultipleUsersSimultaneous

Tests 10 users accessing dashboard concurrently.

**Each user:**
- Views overview
- Views appeals
- Filters results

**Expected:**
```
All requests succeed
No data corruption
Consistent results
```

### TestIntegrationPaginationConsistency

Tests pagination for duplicate prevention.

**Verification:**
- Fetches all pages
- Checks for duplicate IDs
- Verifies no appeals missing

**Expected:**
```
No duplicate appeal IDs
Consistent ordering
All appeals covered
```

### TestIntegrationAnalyticsEndToEnd

Tests all analytics endpoints together.

**Endpoints tested:**
- /analytics/trends
- /analytics/patterns
- /analytics/approval-rate
- /analytics/user-statistics

**Expected:**
```
All endpoints respond with 200 OK
Data correlates between endpoints
Consistent metric calculations
```

## Benchmarking

### Run All Benchmarks

```bash
go test -bench=. ./pkg/routes
```

**Example Output:**
```
BenchmarkDashboardOverview-8        5000     246813 ns/op
BenchmarkListAppeals-8              3000     412556 ns/op
BenchmarkConcurrentRequests-8     10000     143521 ns/op
```

### Interpret Benchmark Output

- **-8**: Number of CPU cores used
- **5000**: How many times the test ran
- **246813 ns/op**: Nanoseconds per operation (246.8 µs or 0.247 ms)

### Benchmark with Memory

```bash
go test -bench=. -benchmem ./pkg/routes
```

**Example Output:**
```
BenchmarkDashboardOverview-8  5000  246813 ns/op  15234 B/op  42 allocs/op
```

- **15234 B/op**: Bytes allocated per operation
- **42 allocs/op**: Number of memory allocations per operation

### Compare Benchmarks

```bash
# Run benchmark and save results
go test -bench=. ./pkg/routes > new.txt

# Compare with previous results
benchstat old.txt new.txt
```

## Interpreting Results

### Success Metrics

**Latency (Milliseconds):**
```
< 50ms   : Excellent
50-200ms : Good
200-500ms: Acceptable
500-1000ms: Slow
> 1000ms : Critical
```

**Throughput (Requests/Second):**
```
> 1000 req/s : Excellent
500-1000 req/s: Good
100-500 req/s: Acceptable
< 100 req/s   : Needs optimization
```

**Success Rate:**
```
99.9%+ : Production-ready
99%+   : Good
95%+   : Acceptable under load
< 95%  : Needs work
```

### Red Flags

⚠️ **High Error Rate**
- Check server logs
- Verify database connectivity
- Check for resource exhaustion

⚠️ **Increasing Latency**
- Check database query performance
- Monitor memory usage
- Look for goroutine leaks

⚠️ **Memory Leaks**
- Run: `go test -memprofile=mem.out ./pkg/routes`
- Analyze: `go tool pprof mem.out`

⚠️ **Race Conditions**
- Run: `go test -race ./pkg/routes`
- Fix concurrent access issues

## Edge Cases

### TestEdgeCaseEmptyDatabase

Tests endpoints with no data.

**Expected:** Endpoints return valid (empty) responses

**Run:**
```bash
go test -v -run TestEdgeCaseEmptyDatabase ./pkg/routes
```

### TestEdgeCaseInvalidParameters

Tests invalid input handling.

**Test cases:**
- `range=invalid` (invalid time range)
- `page=999` (non-existent page)
- `page=-1` (negative page)
- `limit=99999` (excessive limit)

**Expected:**
- Status 200 OK with default behavior, or
- Status 400 Bad Request with error message

### TestEdgeCaseLargeDatasets

Tests performance with 10,000 appeals.

**Expected:**
- Completes in < 2 seconds
- Doesn't cause OOM errors
- Returns correct results

**Run:**
```bash
go test -v TestEdgeCaseLargeDatasets ./pkg/routes
```

### TestMemoryLeaks

Runs same endpoint 1,000 times.

**Expected:**
- All requests succeed
- Memory usage remains stable
- No goroutine buildup

**Profile memory:**
```bash
go test -memprofile=mem.out -run TestMemoryLeaks ./pkg/routes
go tool pprof mem.out
```

## Troubleshooting

### Tests Failing with Database Error

**Error:** `database is locked`

**Solution:**
```bash
# Use :memory: database (already done)
# Or close other connections
# Or increase timeout
```

### Timeout Errors

**Error:** `context deadline exceeded`

**Solution:**
```bash
# Increase test timeout
go test -timeout 10m ./pkg/routes

# Or reduce load
go test -run TestStress -short ./pkg/routes
```

### Memory Issues

**Error:** `fatal error: heap overflow`

**Solution:**
```bash
# Run tests individually
go test -v -run TestEdgeCaseLargeDatasets ./pkg/routes

# Reduce dataset size
# Check for memory leaks
go test -memprofile=mem.out ./pkg/routes
go tool pprof mem.out
```

### Flaky Tests

**Problem:** Test passes sometimes, fails other times

**Solution:**
```bash
# Run with race detector
go test -race ./pkg/routes

# Increase test iterations
go test -count=10 -run TestConcurrentPagination ./pkg/routes

# Check for timing issues
# Increase sleep durations
```

### Cannot Find Tests

**Error:** `no test files`

**Solution:**
```bash
# Verify test files exist
ls -la pkg/routes/*test.go

# Use correct package
cd /path/to/GAIA_GO
go test -v ./pkg/routes
```

## Continuous Testing

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

go test -short ./pkg/routes
if [ $? -ne 0 ]; then
  echo "Tests failed, commit aborted"
  exit 1
fi
```

### CI/CD Pipeline

```yaml
test:
  script:
    - go test -v -race ./pkg/routes
    - go test -bench=. ./pkg/routes
    - go tool cover -func=coverage.out
```

## Performance Optimization

### Identify Bottlenecks

```bash
# CPU profiling
go test -cpuprofile=cpu.out -bench=. ./pkg/routes
go tool pprof cpu.out

# Memory profiling
go test -memprofile=mem.out ./pkg/routes
go tool pprof mem.out
```

### Optimization Techniques

1. **Query Optimization**
   - Add indexes
   - Use prepared statements
   - Batch queries

2. **Caching**
   - Cache aggregation results
   - Use in-memory cache
   - Set appropriate TTL

3. **Pagination**
   - Reduce default page size
   - Use cursor pagination
   - Implement offset optimization

4. **Concurrency**
   - Use goroutine pools
   - Limit concurrent database connections
   - Implement rate limiting

## Test Maintenance

### Update Tests

When adding new endpoints:
1. Add unit test
2. Add integration test
3. Run full test suite
4. Update this documentation

### Review Test Results

Regularly review:
- Test execution time
- Coverage percentage
- Performance trends
- Error patterns

### Archive Results

```bash
# Save baseline
go test -bench=. ./pkg/routes > baseline.txt

# Compare monthly
go test -bench=. ./pkg/routes > current.txt
benchstat baseline.txt current.txt
```

## Related Documentation

- [Admin Dashboard Guide](ADMIN_DASHBOARD_GUIDE.md)
- [Testing Guide](TESTING_GUIDE.md)
- [Development Setup](../README.md)

## Support

For test failures or issues:
1. Run test with `-v` for verbose output
2. Check error message
3. Review relevant test code
4. Check troubleshooting section
5. Contact development team

## Changelog

### v1.0.0 (2024-02-27)

**Test Suite:**
- 16 unit tests
- 12 load tests
- 9 integration tests
- 5 edge case tests
- 2 comprehensive benchmarks
- 44 total test cases

**Test Data:**
- In-memory SQLite database
- 100-10,000 appeal fixtures
- Realistic data generation
- Concurrent load simulation

**Coverage:**
- All 35 API endpoints
- Happy path scenarios
- Error conditions
- Concurrency scenarios
- Large dataset handling
