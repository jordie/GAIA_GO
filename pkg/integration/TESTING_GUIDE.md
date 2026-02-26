# GAIA_GO E2E Integration Testing Guide

Comprehensive guide for understanding, running, and developing integration tests for GAIA_GO's distributed coordination and metrics infrastructure.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Test Architecture](#test-architecture)
3. [Test Scenarios](#test-scenarios)
4. [Performance Targets](#performance-targets)
5. [Debugging Guide](#debugging-guide)
6. [Best Practices](#best-practices)
7. [Contributing Tests](#contributing-tests)

## Quick Start

### Prerequisites

```bash
# Go 1.21+
go version

# Dependencies
go mod download

# Build tags support
# Tests use //go:build e2e tag
```

### Run All Tests

```bash
# Basic run
go test -v -tags e2e ./pkg/integration/...

# With race detector
go test -v -tags e2e -race ./pkg/integration/...

# With coverage
go test -v -tags e2e -coverprofile=coverage.out ./pkg/integration/...
go tool cover -html=coverage.out
```

### Run Specific Category

```bash
# Coordination tests only
go test -v -tags e2e -run TestE2E_Session ./pkg/integration/

# Task queue tests only
go test -v -tags e2e -run TestE2E_Task ./pkg/integration/

# Metrics tests only
go test -v -tags e2e -run TestE2E_Metrics ./pkg/integration/

# Full system only
go test -v -tags e2e -run TestE2E_FullSystem ./pkg/integration/
```

### Run Benchmarks

```bash
# All benchmarks
go test -v -tags e2e -bench=. -run=^$ ./pkg/integration/

# Specific benchmark
go test -v -tags e2e -bench=BenchmarkE2E_MetricsIngestThroughput ./pkg/integration/

# With detailed stats
go test -v -tags e2e -bench=. -run=^$ -benchmem ./pkg/integration/
```

## Test Architecture

### Test Harness: E2ETestSetup

The `E2ETestSetup` provides a complete testing environment:

```
E2ETestSetup
├── RaftCluster (3-node simulation)
│   ├── Leader election & consensus
│   ├── Log replication
│   └── Failure injection
├── SessionCoordinator
│   ├── Session registration
│   ├── Heartbeat monitoring
│   └── Affinity scoring
├── TaskQueue
│   ├── Task enqueueing
│   ├── Claiming (exactly-once)
│   └── Retry management
├── MetricsService
│   ├── Metric buffering
│   ├── Windowed aggregation
│   └── Real-time computation
├── WebSocketHub
│   ├── Alert subscriptions
│   ├── Message broadcasting
│   └── Reconnection handling
└── Test Helpers
    ├── MetricsSimulator
    └── AlertListener
```

### Component Interactions

```
Student App
    ↓
Metrics SDK (buffer 100, flush 1s)
    ↓
Metrics Service (receives flushed batch)
    ↓
Real-time Aggregator (5-min window)
    ↓
Teacher Dashboard (WebSocket alert)
    ↓
Frustration Detection (confidence score)
```

### Concurrency Model

Tests use several concurrency patterns:

**sync.WaitGroup** - Coordinate goroutine completion
```go
var wg sync.WaitGroup
for i := 0; i < numWorkers; i++ {
    wg.Add(1)
    go func() {
        defer wg.Done()
        // work
    }()
}
wg.Wait()
```

**sync.Mutex** - Protect shared state
```go
mu := sync.Mutex{}
var count int

mu.Lock()
count++
mu.Unlock()
```

**atomic operations** - Lock-free counters
```go
var counter int32
atomic.AddInt32(&counter, 1)
value := atomic.LoadInt32(&counter)
```

**Context with timeouts** - Bounded execution
```go
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()
```

## Test Scenarios

### Category 1: Coordination Tests

**Purpose**: Validate Raft consensus and session management

#### Scenario: Session Registration & Replication
```
1. Create 3-node Raft cluster
2. Register 5 sessions (2 managers, 3 workers)
3. Verify each session replicated to all nodes
4. Assert: log.len ≥ 5, all nodes have same logs
```

**Key Code**:
```go
leader := setup.RaftCluster.GetLeader()
for i := 0; i < 5; i++ {
    session := fixtures.NewWorkerSession(fmt.Sprintf("session-%d", i))
    err := setup.RaftCluster.ReplicateLog(session)
    require.NoError(t, err)
}
err = setup.WaitForRaftConsensus(500 * time.Millisecond)
require.NoError(t, err)
```

#### Scenario: Leader Election
```
1. Get current leader (term = T)
2. Kill leader node
3. Wait for new election (<1 second)
4. Assert: new leader elected, term > T
```

**Key Timing**:
- Heartbeat interval: 150ms
- Election timeout: 300-500ms (random)
- Expected election time: <1 second

#### Scenario: Health Monitoring
```
1. Register session (health = healthy)
2. Stop heartbeats
3. Wait 15 seconds → health = degraded
4. Wait 30 seconds → health = failed
```

**Health State Machine**:
```
healthy -(15s no heartbeat)→ degraded -(15s more)→ failed
```

#### Scenario: Affinity Scoring
```
1. Create 3 sessions (math-specialist, reading-specialist, general)
2. Create 3 tasks (math, reading, general affinity)
3. Score each session for each task
4. Assert: perfect_match=1.0, partial=0.5, none=0.0
```

**Scoring Formula**:
```
score = 1.0 if session.specialty == task.affinity
score = 0.5 if session.specialty == "general" OR task.affinity == "general"
score = 0.0 otherwise
```

### Category 2: Task Queue Tests

**Purpose**: Validate exactly-once semantics and task processing

#### Scenario: Concurrent Claims (No Double-Assignment)
```
1. Enqueue 50 tasks
2. Launch 10 goroutines to claim tasks
3. Each goroutine claims max 1 task (check lock)
4. Assert: each task claimed 0 or 1 time (never 2+)
```

**Critical Section Pattern**:
```go
claimsMu.Lock()
if claimsPerTask[taskID] == 0 {  // Check before claim
    claimsPerTask[taskID]++       // Increment
    claimsMu.Unlock()
    // Claim successful
} else {
    claimsMu.Unlock()
    // Already claimed, skip
}
```

#### Scenario: Exponential Backoff
```
1. Task fails, retry_count = 0 → backoff = 1s
2. Task fails, retry_count = 1 → backoff = 2s
3. Task fails, retry_count = 2 → backoff = 4s
4. After 3 fails: status = failed
```

**Backoff Formula**:
```
backoff = 2^(retry_count - 1) * base_backoff_duration
baseBackoff = 1 second
retry_count = 1 → 1s
retry_count = 2 → 2s
retry_count = 3 → 4s
```

#### Scenario: Idempotency Key Enforcement
```
1. Enqueue task with idempotency_key = "job-123"
2. Enqueue same task again (same key)
3. Assert: Only 1 task in queue (deduped)
4. Both calls return same task_id
```

**Implementation**:
```go
task1 := fixtures.NewIdempotentTask("job-123", data)
task2 := fixtures.NewIdempotentTask("job-123", data)
// task1.id == task2.id after dedup
```

### Category 3: Metrics Flow Tests

**Purpose**: Validate end-to-end metrics pipeline

#### Scenario: Buffer + Flush
```
1. SDK buffer size = 100
2. Flush interval = 1 second
3. Send 150 metrics
4. Assert: First flush after 100 metrics (immediate)
5. Assert: Second flush after 1 second timer
```

**Flush Triggers**:
1. Buffer full (100 metrics)
2. Periodic timer (1 second)
3. Explicit flush call

#### Scenario: 5-Minute Windowed Aggregation
```
1. Generate metrics over 10 minutes
2. Aggregate in 5-min rolling window
3. Window 1: metrics from minutes 0-5
4. Window 2: metrics from minutes 5-10
5. Assert: No overlap, all metrics included
```

**Window Calculation**:
```
windowStart = now - 5 minutes
windowEnd = now
count = sum(metrics where windowStart < timestamp < windowEnd)
```

#### Scenario: Metric Isolation (Cross-Student)
```
1. Student 1 generates metrics
2. Student 2 generates metrics
3. Aggregate for each student
4. Assert: Student 1 metrics ≠ Student 2 metrics
5. Assert: No metrics from wrong student
```

**Validation**:
```go
for _, metric := range aggregatedMetrics {
    assert.Equal(t, studentID, metric.StudentID)
    // Prevent cross-contamination
}
```

#### Scenario: App Segregation
```
1. Student uses 3 apps: Typing, Math, Reading
2. Each app generates metrics
3. Aggregate per app
4. Assert: Typing metrics separate from Math
5. Assert: Each app's total consistent
```

**Metric Keys**:
```
Metrics keyed by: (student_id, app_name, metric_type)
Aggregated by: (student_id, app_name)
No mixing between apps for same student
```

### Category 4: Full System Integration

**Purpose**: Validate all components working together in realistic scenario

#### Scenario: Classroom Simulation
```
Phase 1: Initialize 3-node Raft + 10 Claude sessions
Phase 2: 30 students, 3 apps, generate 6000+ metrics (20/sec)
Phase 3: Verify metric aggregation + app segregation
Phase 4: Trigger 5 frustration detection events
Phase 5: Enqueue 100 grading tasks, process with 5 workers
Phase 6: 2 teachers receive WebSocket alerts
Phase 7: Verify Raft consensus across all 3 nodes
Phase 8: Measure throughput + latency
```

**Timeline**:
```
T=0s:    Cluster + sessions ready
T=0-5m:  Student activity (metrics generation)
T=0-5m:  Task processing (grading)
T=0.1s:  First frustration event detected
T=0.2s:  Alert delivered to teachers (<100ms)
T=5m:    All metrics aggregated
T=5m:    Verify data consistency
```

**Success Criteria**:
```
✓ 4000+ metrics generated (80% of 5000 target)
✓ Throughput ≥ 10/sec (50% of 20/sec target)
✓ 5 frustration events detected
✓ ≥50 tasks claimed, ≥25 completed
✓ 2 teachers receive ≥5 alerts each
✓ All 3 Raft nodes have consistent logs
✓ <200ms E2E latency
```

## Performance Targets

### Coordination Tests
| Operation | Target | Comment |
|-----------|--------|---------|
| Session registration | <100ms | Per session |
| Raft replication | <500ms | Consensus on 3 nodes |
| Leader election | <1s | After failure |
| Heartbeat interval | 10s | Session check-in |
| Health degradation | 15s | No heartbeat |
| Health failure | 30s | Confirmed dead |

### Task Queue Tests
| Operation | Target | Comment |
|-----------|--------|---------|
| Task enqueue | <10ms | Single task |
| Task claim | <5ms | With lock |
| Claim timeout | 10min | Auto-reassign |
| Retry backoff | 1s→2s→4s | Exponential |
| Max retries | 3 | Then mark failed |
| Throughput | 1000 tasks/sec | Single-threaded |

### Metrics Tests
| Operation | Target | Comment |
|-----------|--------|---------|
| Metric generation | 20/sec | Per student |
| Buffer flush | 1s | Periodic or on full |
| E2E latency | <200ms | App→Dashboard |
| Windowed agg | 5 min | Rolling window |
| Aggregation rate | 100 aggs/sec | Per window |
| Throughput | 20k metrics/sec | All students |

### Full System
| Metric | Target | Lower Bound |
|--------|--------|-------------|
| Metrics/second | 20 | 10 (50%) |
| Frustration detection | 100% | >90% |
| Task completion | 50% | 25% |
| Alert latency | <100ms | <500ms |
| Raft consensus | <500ms | <1s |
| Log consistency | 100% | 99% |

## Debugging Guide

### Test Failure: "No Leader Elected"

**Diagnosis**:
```bash
# Check Raft cluster state
go test -v -tags e2e -run TestE2E_SessionRegistrationAndHeartbeat -v

# Look for: "no leader elected"
```

**Causes**:
1. Cluster initialization failed
2. Consensus timeout too short
3. Node failure during election

**Fix**:
```go
// Increase timeout
err := setup.WaitForRaftConsensus(1 * time.Second)  // was 500ms

// Check node health
for _, node := range setup.RaftCluster.GetAllNodes() {
    t.Logf("Node %s: %s", node.NodeID, node.State)
}
```

### Test Failure: "Task Double-Claimed"

**Diagnosis**:
```bash
# Run with race detector
go test -v -tags e2e -race -run TestE2E_ConcurrentClaims

# Look for: "DATA RACE" warnings
```

**Causes**:
1. Distributed lock not acquired before claim
2. TOCTOU (time-of-check to time-of-use) bug
3. Missing mutex around claim check

**Fix**:
```go
// WRONG (TOCTOU bug):
if claimsPerTask[taskID] == 0 {  // Check
    mu.Unlock()                    // Release lock!
    claimsPerTask[taskID]++        // Race window here
}

// CORRECT:
mu.Lock()
if claimsPerTask[taskID] == 0 {
    claimsPerTask[taskID]++
    mu.Unlock()
    // Claim
} else {
    mu.Unlock()
}
```

### Test Failure: "Metric Cross-Contamination"

**Diagnosis**:
```bash
# Run with assertions enabled
go test -v -tags e2e -run TestE2E_MetricsFlow_ConcurrentStudents

# Look for: "student-X should belong to student-Y"
```

**Causes**:
1. Wrong student_id in metric
2. Aggregation includes wrong student
3. Buffer not keyed by student_id

**Fix**:
```go
// Verify metric generation
metric := &TestMetric{
    StudentID: studentID,  // Must match
    AppName: appName,
    ...
}

// Verify aggregation
for _, metric := range aggregated {
    assert.Equal(t, expectedStudentID, metric.StudentID)
}
```

### Test Hangs / Times Out

**Diagnosis**:
```bash
# Run with timeout
timeout 10 go test -v -tags e2e -run TestE2E_FullSystem

# Check for goroutine leaks
go test -v -tags e2e -run TestE2E_FullSystem 2>&1 | grep "goroutine"
```

**Causes**:
1. Deadlock (goroutines waiting for each other)
2. Goroutine leak (not cleaned up)
3. Context not cancelled

**Fix**:
```go
// Ensure cleanup
defer setup.Cleanup()  // Critical!
defer cancel()         // Cancel contexts

// Add logging for debugging
t.Logf("Starting goroutine %d", id)
defer t.Logf("Goroutine %d done", id)

// Use timeout
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()
```

### Test Data Mismatch

**Diagnosis**:
```bash
# Run with verbose logging
go test -v -tags e2e -run TestE2E_MetricsAggregationAccuracy -v

# Look for: actual vs expected values
```

**Causes**:
1. Random number generation too wide
2. Assertion bounds wrong
3. Data generation not matching spec

**Fix**:
```go
// Check random ranges
value := 75.0 + float64(rand.Intn(25))  // 75-100
assert.GreaterOrEqual(t, value, 75.0)
assert.LessOrEqual(t, value, 100.0)

// Seed for determinism (if needed)
rand.Seed(int64(time.Now().Unix()))
```

## Best Practices

### 1. Naming Conventions

**Test Names**:
```
TestE2E_<Component>_<Scenario>

Examples:
✓ TestE2E_SessionRegistrationAndHeartbeat
✓ TestE2E_ConcurrentClaims_NoDoubleAssignment
✓ TestE2E_MetricsFlow_MultipleApps
✗ TestSession  (too generic)
✗ Test1        (meaningless)
```

**Variable Names**:
```go
studentID, appName, taskID  // Clear purpose
nodeCount, timeoutMs        // Unit obvious

// Avoid
s, app, t  // Ambiguous (t = task or test?)
x, y       // Meaningless
```

### 2. Test Organization

**Structure**:
```go
func TestE2E_FeatureName_Scenario(t *testing.T) {
    // Setup phase
    setup := NewE2ETestSetup(t, 3)
    defer setup.Cleanup()

    // Verify setup assertions
    require.NotNil(t, setup.RaftCluster)

    // Execute test scenario
    result := doSomething()

    // Assert expectations
    assert.Equal(t, expected, result)
}
```

**Using Sub-tests**:
```go
tests := []struct {
    name     string
    input    interface{}
    expected interface{}
}{
    {"case 1", "input1", "expected1"},
    {"case 2", "input2", "expected2"},
}

for _, tt := range tests {
    t.Run(tt.name, func(t *testing.T) {
        // Test logic using tt.input, tt.expected
    })
}
```

### 3. Error Handling

**Use `require` for setup** (test fails immediately):
```go
setup := NewE2ETestSetup(t, 3)
defer setup.Cleanup()

leader := setup.RaftCluster.GetLeader()
require.NotNil(t, leader)  // Fail fast if setup fails
```

**Use `assert` for assertions** (test continues):
```go
assert.Equal(t, expectedValue, actualValue)
assert.Greater(t, count, 0)
assert.NoError(t, err)
```

### 4. Concurrent Testing Patterns

**WaitGroup for coordination**:
```go
var wg sync.WaitGroup
for i := 0; i < numWorkers; i++ {
    wg.Add(1)
    go func(id int) {
        defer wg.Done()
        // Work
    }(i)  // Pass i as parameter, don't capture
}
wg.Wait()
```

**Atomic operations for lock-free counting**:
```go
var counter int32
atomic.AddInt32(&counter, 1)
value := atomic.LoadInt32(&counter)
```

**Context timeouts for bounded execution**:
```go
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()

select {
case result := <-ch:
    // Got result
case <-ctx.Done():
    t.Fatal("timeout")
}
```

### 5. Fixture Usage

**Don't repeat data creation**:
```go
// Good: use fixtures
session := fixtures.NewWorkerSession("session-1")
metrics := generator.MetricStream(studentID, appName, 1*time.Minute, 10)

// Avoid: hardcoded test data
session := map[string]interface{}{
    "name": "worker-1",
    "tier": "worker",
    "health_status": "healthy",
    ...
}
```

### 6. Test Isolation

**Each test is independent**:
```go
// Each test creates its own setup
func TestE2E_Feature1(t *testing.T) {
    setup := NewE2ETestSetup(t, 1)
    defer setup.Cleanup()
    // ...
}

func TestE2E_Feature2(t *testing.T) {
    setup := NewE2ETestSetup(t, 1)
    defer setup.Cleanup()
    // ...
}

// Not: shared global state
var globalSetup E2ETestSetup  // BAD: shared state
```

## Contributing Tests

### Adding a New Test

1. **Choose category**:
   - Coordination: `coordination_e2e_test.go`
   - Task Queue: `task_queue_e2e_test.go`
   - Metrics: `metrics_flow_e2e_test.go`
   - Full System: `full_system_e2e_test.go`

2. **Create test function**:
```go
func TestE2E_YourComponent_YourScenario(t *testing.T) {
    if testing.Short() {
        t.Skip("skipping comprehensive test")
    }

    setup := NewE2ETestSetup(t, nodeCount)
    defer setup.Cleanup()

    // Your test logic
}
```

3. **Document**:
```go
// TestE2E_YourComponent_YourScenario validates:
// - Aspect 1
// - Aspect 2
// - Aspect 3
func TestE2E_YourComponent_YourScenario(t *testing.T) {
```

4. **Test locally**:
```bash
# Run your test
go test -v -tags e2e -run TestE2E_YourComponent_YourScenario ./pkg/integration/

# With race detector
go test -v -tags e2e -race -run TestE2E_YourComponent_YourScenario ./pkg/integration/
```

5. **Submit PR** with test added

### Approval Checklist

- [ ] Test follows naming convention `TestE2E_*_*`
- [ ] Test has clear documentation comment
- [ ] Uses `require` for setup, `assert` for assertions
- [ ] Proper cleanup in `defer setup.Cleanup()`
- [ ] Passes with `-race` flag
- [ ] Runs in <5 minutes
- [ ] Coverage report shows >80%
- [ ] No flaky failures (passes 10x consistently)

---

**Last Updated**: Phase 10 Sprint 5
**Coverage**: 82%+ across all component layers
