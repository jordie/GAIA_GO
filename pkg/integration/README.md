# GAIA_GO End-to-End Integration Test Suite

Comprehensive integration tests for GAIA_GO's Phase 10 distributed coordination and usability metrics features. This test suite validates the complete interaction between all system components including Raft consensus, distributed task queues, education app metrics, WebSocket alerts, and frustration detection.

## Overview

The integration test suite consists of **6 comprehensive test files** with **40+ test scenarios** covering:

1. **Claude Session Coordination** - Raft consensus, leader election, heartbeat management
2. **Distributed Task Queue** - Exactly-once semantics, priority ordering, retry logic
3. **Education App Metrics Flow** - End-to-end pipeline, buffering, real-time aggregation
4. **Teacher Dashboard WebSocket Alerts** - Alert delivery, subscriptions, reconnection
5. **Frustration Detection** - Pattern recognition, confidence scoring, false positive rates
6. **Full System Integration** - Comprehensive classroom simulation with all components

## Test Files

### 1. `coordination_e2e_test.go` (~300 lines)

**Purpose**: Validates Claude session coordination with Raft consensus protocol

**Test Scenarios**:
- `TestE2E_SessionRegistrationAndHeartbeat` - Register 5 sessions, verify Raft replication
- `TestE2E_SessionFailover_LeaderElection` - Kill leader, verify new election <1 second
- `TestE2E_SessionHealthMonitoring` - Health transitions (healthy → degraded → failed)
- `TestE2E_SessionAffinityScoring` - Task assignment by specialization (0.0-1.0 scoring)
- `TestE2E_MultiNodeCoordination` - 5-node cluster, 20 sessions, 100 concurrent tasks
- `TestE2E_SessionHeartbeatFrequency` - Verify 10-second heartbeat interval
- `BenchmarkE2E_SessionRegistration` - Session registration throughput

**Key Assertions**:
- Raft consensus within 500ms
- Leader election within 300-500ms
- No session double-registration
- Health transitions at expected timeouts
- Session affinity scores match expected values

**Running**:
```bash
go test -v -tags e2e -run TestE2E_SessionRegistrationAndHeartbeat ./pkg/integration/
```

### 2. `task_queue_e2e_test.go` (~450 lines)

**Purpose**: Validates distributed task queue with exactly-once semantics

**Test Scenarios**:
- `TestE2E_TaskEnqueueAndClaim` - 100 tasks, 5 workers, verify no double-claims
- `TestE2E_IdempotencyKeyEnforcement` - Same task twice returns same ID
- `TestE2E_ConcurrentClaims_NoDoubleAssignment` - 10 goroutines, 50 tasks, race-free
- `TestE2E_TaskRetry_ExponentialBackoff` - 3 retries with 1s→2s→4s backoff
- `TestE2E_ClaimExpiration_Timeout` - 10-minute timeout, auto-reassign
- `TestE2E_TaskPriorityOrdering` - High-priority tasks claimed first
- `TestE2E_TaskCompletion_UpdateStatus` - Status: pending→claimed→completed
- `TestE2E_DistributedLocking_PreventDoubleAssignment` - Lock-based safety
- `BenchmarkE2E_TaskClaimThroughput` - Single-threaded throughput
- `BenchmarkE2E_ConcurrentTaskClaims` - 10-worker concurrent claims

**Key Assertions**:
- Exactly-once semantics (max 1 claim per task)
- Idempotency keys prevent duplicates
- Priority ordering maintained
- Exponential backoff: task[retry_count] = N, delay = 2^(N-1) * baseBackoff
- Claim timeout auto-reassignment

**Running**:
```bash
go test -v -tags e2e -run TestE2E_TaskEnqueueAndClaim ./pkg/integration/
go test -v -tags e2e -bench=TaskClaimThroughput ./pkg/integration/
```

### 3. `metrics_flow_e2e_test.go` (~380 lines)

**Purpose**: Validates end-to-end metrics pipeline from education app to dashboard

**Test Scenarios**:
- `TestE2E_MetricsFlow_AppToSDK_ToAggregator_ToDashboard` - Full pipeline <200ms latency
- `TestE2E_MetricsBuffering_BatchFlush` - 500 metrics, buffer=100, flush on full or 1s
- `TestE2E_RealtimeAggregation_5MinuteWindow` - 10-minute stream, 5-min window aggregation
- `TestE2E_MetricsFlow_ConcurrentStudents` - 50 students, 100 metrics each, no cross-contamination
- `TestE2E_MetricsFlow_MultipleApps` - 3 apps, metrics segregated by app_name
- `TestE2E_MetricsAggregationAccuracy` - Correct average/sum calculations
- `TestE2E_MetricsFlush_PeriodicTimer` - Timer-based flush even without buffer overflow
- `BenchmarkE2E_MetricsIngestThroughput` - Metrics/second ingestion
- `BenchmarkE2E_MetricsAggregation` - Aggregation latency
- `BenchmarkE2E_ConcurrentMetricsIngestion` - Multi-student concurrent ingest

**Key Assertions**:
- E2E latency <200ms
- Buffer size = 100
- Flush interval = 1 second
- Windowed aggregation = 5 minutes
- No metric cross-contamination across students
- Metric segregation by (student_id, app_name)
- Aggregation accuracy: average > 50 and < 100 for normal patterns

**Running**:
```bash
go test -v -tags e2e -run TestE2E_MetricsFlow ./pkg/integration/
go test -v -tags e2e -bench=MetricsIngestThroughput ./pkg/integration/
```

### 4. `dashboard_alerts_e2e_test.go` (Delegated to architect session)

**Purpose**: Validates WebSocket real-time alert delivery to teacher dashboards

**Expected Test Scenarios**:
- `TestE2E_WebSocket_FrustrationAlert` - <100ms delivery
- `TestE2E_WebSocket_MultipleTeacherSubscriptions` - Fan-out to N teachers
- `TestE2E_WebSocket_ClassroomMetricsUpdates` - Push every 5 seconds
- `TestE2E_WebSocket_InterventionTracking` - Teacher actions logged
- `TestE2E_WebSocket_Reconnection` - Buffered alerts on reconnect

**Key Assertions**:
- Alert latency <100ms
- All subscribed teachers receive alert
- Metrics refreshed every 5 seconds
- Reconnection preserves session and buffered alerts

### 5. `frustration_detection_e2e_test.go` (Delegated to architect session)

**Purpose**: Validates frustration detection pattern recognition and scoring

**Expected Test Scenarios**:
- `TestE2E_FrustrationDetection_ExcessiveErrors` - 5+ errors → 0.95 confidence
- `TestE2E_FrustrationDetection_RepeatedErrors` - 3+ errors → 0.85 confidence
- `TestE2E_FrustrationDetection_ExcessiveCorrections` - 20+ backspaces → 0.80 confidence
- `TestE2E_FrustrationDetection_RepeatedCorrections` - 10+ backspaces → 0.70 confidence
- `TestE2E_FrustrationDetection_ProlongedHesitation` - 30s+ pause → 0.65 confidence
- `TestE2E_FrustrationDetection_CombinedIndicators` - Multiple patterns → 0.99 confidence
- `TestE2E_FrustrationDetection_WeightedScoring` - Verify scoring formula
- `TestE2E_FrustrationDetection_FalsePositiveRate` - 1000 normal patterns, <5% FP

**Key Assertions**:
- 7 frustration patterns with correct confidence scores
- Weighted scoring matches expected formula
- False positive rate <5%

### 6. `full_system_e2e_test.go` (~500 lines)

**Purpose**: Comprehensive classroom simulation validating entire system working together

**Test Scenarios**:
- `TestE2E_FullSystem_ClassroomSimulation` - 8-phase comprehensive test:
  1. 3-node Raft cluster, 10 Claude sessions registration
  2. 30 students, 3 apps, 6000+ metrics over 5 minutes
  3. Metric aggregation and app segregation
  4. 5 frustration events triggered
  5. 100 grading tasks enqueued/claimed/completed
  6. 2 teachers receiving WebSocket alerts
  7. Multi-node consensus verification
  8. End-to-end latency and throughput measurement

- `TestE2E_FullSystem_FailoverRecovery` - System resilience during node failure
- `BenchmarkE2E_FullSystem` - Full system throughput measurement

**Key Assertions**:
- 4000+ metrics generated (80% of target)
- Metrics throughput >10/sec (50% of 20/sec target)
- Frustration events detected = 5
- Tasks claimed ≥50, completed ≥25
- Teachers receive alerts ≥5
- All 3 Raft nodes have consistent logs
- Leader election <3 seconds on failure
- Log consistency after failover

**Running**:
```bash
go test -v -tags e2e -run TestE2E_FullSystem ./pkg/integration/
go test -v -tags e2e -bench=BenchmarkE2E_FullSystem ./pkg/integration/
```

## Test Infrastructure

### E2ETestSetup

Extended test harness providing complete E2E test environment:

```go
type E2ETestSetup struct {
    *handlers.TestSetup           // Base test setup (DB, Router, etc.)

    // Distributed components
    RaftCluster     *TestRaftCluster
    Coordinator     *coordinator.SessionCoordinator
    TaskQueue       *queue.TaskQueue

    // Usability components
    MetricsService  *usability.UsabilityMetricsService
    Frustration     *usability.FrustrationDetectionEngine
    Aggregator      *usability.RealtimeMetricsAggregator

    // WebSocket components
    WebSocketHub    *websocket.Hub
    WebSocketServer *httptest.Server

    // Test helpers
    MetricsSimulator *MetricsSimulator
    AlertListener    *TestAlertListener
}
```

### Key Methods

```go
// Setup
setup := NewE2ETestSetup(t, nodeCount)
defer setup.Cleanup()

// Raft operations
leader := setup.RaftCluster.GetLeader()
setup.RaftCluster.ReplicateLog(data)
setup.RaftCluster.TriggerLeaderFailure()
setup.RaftCluster.WaitForLeaderElection(timeout)

// Consensus
setup.WaitForRaftConsensus(timeout)

// Metrics
setup.SimulateStudentActivity(ctx, studentID, appName, duration)
setup.AssertFrustrationEventDetected(pattern)
setup.AssertWebSocketAlertDelivered(teacherID, latency)
```

### Test Fixtures

**pkg/integration/fixtures/**

#### `raft_fixtures.go`
- `NewTestRaftCluster(nodeCount)` - Create simulated Raft cluster
- `TestRaftCluster.GetLeader()` - Get current leader
- `TestRaftCluster.WaitForLeaderElection(timeout)` - Wait for new leader
- `TestRaftCluster.ReplicateLog(entry)` - Replicate entry to all nodes
- `TestRaftCluster.TriggerLeaderFailure()` - Kill leader for failover testing

#### `metrics_fixtures.go`
- `NewMetricsGenerator()` - Create metrics generator
- `MetricStream(studentID, appName, duration, metricsPerSecond)` - Generate metric stream
- `FrustrationMetricPattern(studentID, patternType)` - Generate frustration pattern
- `NormalMetricPattern(studentID)` - Generate normal baseline
- `NewTestTask(taskType, priority, data)` - Create task
- `TaskBatch(count)` - Create multiple tasks with varied priorities
- `NewIdempotentTask(key, data)` - Create task with idempotency key

#### `websocket_fixtures.go`
- `NewTestWebSocketClient(t, url)` - Create test client
- `Client.Connect(ctx)` - Establish connection
- `Client.SubscribeToClassroom(classroomID)` - Subscribe to alerts
- `Client.WaitForAlert(timeout)` - Block wait for alert
- `Client.SendIntervention(studentID, action)` - Send teacher action
- `Client.GetReceivedAlerts()` - Get all alerts received

## Running the Tests

### All E2E Tests
```bash
go test -v -tags e2e ./pkg/integration/...
```

### Specific Test File
```bash
go test -v -tags e2e ./pkg/integration/coordination_e2e_test.go
```

### Specific Test
```bash
go test -v -tags e2e -run TestE2E_SessionRegistrationAndHeartbeat ./pkg/integration/
```

### With Race Detector
```bash
go test -v -tags e2e -race ./pkg/integration/...
```

### With Coverage
```bash
go test -v -tags e2e -coverprofile=coverage.out ./pkg/integration/...
go tool cover -html=coverage.out
```

### Benchmarks Only
```bash
go test -v -tags e2e -bench=. -run=^$ ./pkg/integration/
```

### Specific Benchmark
```bash
go test -v -tags e2e -bench=BenchmarkE2E_MetricsIngestThroughput ./pkg/integration/
```

## Test Metrics and Targets

### Coordination Tests
| Metric | Target | Assertion |
|--------|--------|-----------|
| Session Registration | <500ms | Raft consensus within timeout |
| Leader Election | <1s | New leader elected after failure |
| Health Monitoring | 15s/30s | Degraded at 15s, failed at 30s |
| Affinity Scoring | 0.0-1.0 | Perfect=1.0, Partial=0.5, None=0.0 |

### Task Queue Tests
| Metric | Target | Assertion |
|--------|--------|-----------|
| Double-Claim Prevention | 0% | Max 1 claim per task |
| Idempotency | 100% | Duplicate tasks deduplicated |
| Retry Backoff | 1s→2s→4s | Exponential delay formula |
| Claim Timeout | 10min | Auto-reassignment after timeout |
| Priority Ordering | FIFO | High priority claimed first |

### Metrics Flow Tests
| Metric | Target | Assertion |
|--------|--------|-----------|
| E2E Latency | <200ms | Full pipeline <200ms |
| Buffer Size | 100 | Flush when full |
| Flush Interval | 1s | Timer-based flush |
| Windowed Agg | 5min | Rolling window size |
| Metric Isolation | 100% | No cross-contamination |
| Cross-Student | 100% | Each student separate |
| Cross-App | 100% | Each app segregated |

### Full System Simulation
| Metric | Target | Assertion |
|--------|--------|-----------|
| Metrics Generated | 6000 | ≥4000 (80% of target) |
| Throughput | 20/sec | ≥10/sec (50% of target) |
| Frustration Events | 5 | All detected and alerted |
| Tasks Processed | 100 | ≥50 claimed, ≥25 completed |
| Alert Delivery | <100ms | Teachers receive within timeout |
| Log Consistency | 100% | All nodes same logs |

## CI/CD Integration

### GitHub Actions Workflow

See `.github/workflows/integration-tests.yml`:

```yaml
name: E2E Integration Tests
on: [push, pull_request]

jobs:
  integration-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-go@v4
        with:
          go-version: 1.21

      - name: Run E2E Tests
        run: go test -v -tags e2e -race ./pkg/integration/...

      - name: Generate Coverage
        run: go test -v -tags e2e -coverprofile=coverage.out ./pkg/integration/...

      - name: Upload Coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.out
```

## Coverage Goals

| Component | Target |
|-----------|--------|
| Coordination Layer | >80% |
| Task Queue Layer | >85% |
| Metrics Layer | >85% |
| Critical Paths | 100% |
| **Overall** | **>82%** |

Current coverage: Run tests with `-coverprofile=coverage.out` flag to generate report.

## Development Guide

### Adding a New Test

1. Create test function following naming convention `TestE2E_*Component*_*Scenario*`
2. Use `require` for setup assertions (test fails if setup fails)
3. Use `assert` for functionality assertions
4. Always call `defer setup.Cleanup()` to prevent resource leaks
5. Document test purpose and key assertions in comment

Example:
```go
func TestE2E_NewFeature_Scenario(t *testing.T) {
    // Setup
    setup := NewE2ETestSetup(t, 1)
    defer setup.Cleanup()

    // Verify setup
    require.NotNil(t, setup.RaftCluster)

    // Execute
    result := doSomething()

    // Assert
    assert.Equal(t, expected, result)
}
```

### Common Patterns

**Table-Driven Tests with Fixtures**:
```go
tests := []struct {
    name     string
    input    *fixtures.TestData
    expected interface{}
}{
    {"case 1", fixtures.NewWorkerSession("test"), expectedValue},
    {"case 2", fixtures.NewManagerSession("test"), expectedValue},
}

for _, tt := range tests {
    t.Run(tt.name, func(t *testing.T) {
        // Test logic
    })
}
```

**Concurrent Testing**:
```go
var wg sync.WaitGroup
for i := 0; i < concurrency; i++ {
    wg.Add(1)
    go func(id int) {
        defer wg.Done()
        // Concurrent work
    }(i)
}
wg.Wait()
```

**Timeout Testing**:
```go
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()

// Use ctx for operations
```

## Troubleshooting

### Test Fails: "no leader elected"
- **Cause**: Raft cluster not reaching consensus
- **Fix**: Increase timeout in `WaitForLeaderElection()`, check node health

### Test Fails: "metric cross-contamination"
- **Cause**: Metrics from different students mixed
- **Fix**: Verify `StudentID` is properly set in metric generation, check aggregation logic

### Test Fails: "claim count exceeds task count"
- **Cause**: Task claimed multiple times
- **Fix**: Ensure distributed lock is acquired before claim, check race detector

### Test Times Out
- **Cause**: Deadlock in concurrent test
- **Fix**: Check for proper mutex unlock, verify goroutine cleanup, use context timeouts

### Build Fails: "missing package"
- **Cause**: Required service packages not imported
- **Fix**: Ensure all `pkg/services/`, `pkg/cluster/`, `pkg/websocket/` packages exist

## Future Enhancements

- [ ] Add chaos engineering tests (random failures, latency injection)
- [ ] Add performance profiling tests (CPU, memory, goroutine count)
- [ ] Add property-based testing for metrics consistency
- [ ] Add load testing with configurable student/task/metric counts
- [ ] Add failure mode analysis (Byzantine fault tolerance)
- [ ] Add cross-region cluster testing
- [ ] Add data migration and versioning tests

## Contact & Support

For questions or issues with the integration test suite, contact the GAIA_GO team.

Test suite created as part of Phase 10 Sprint 5: End-to-End Integration Tests.
# Workflow trigger - Thu Feb 26 08:08:41 PST 2026
