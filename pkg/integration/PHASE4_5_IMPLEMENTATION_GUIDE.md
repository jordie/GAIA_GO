# Phase 4-5 Implementation Guide for Architect Session

## Overview

This guide provides instructions for completing **Phase 4-5** of the end-to-end integration test suite. Draft implementations have been provided as templates that require connection to actual service implementations.

**Phase 4**: WebSocket Dashboard Alerts (5 test scenarios)
**Phase 5**: Frustration Detection (8 test scenarios)

## What's Already Done

✅ **Foundation Infrastructure** (Phase 1) - Complete
- E2ETestSetup with all components
- Test fixtures for Raft, metrics, WebSocket
- Base patterns and conventions established

✅ **Task Queue & Metrics Tests** (Phases 2-3) - Complete
- 10 task queue test scenarios
- 8 metrics flow test scenarios
- Working examples of all testing patterns

✅ **Full System Integration** (Phase 6) - Complete
- Comprehensive classroom simulation
- Failover recovery testing
- Benchmarking infrastructure

✅ **Documentation & CI/CD** (Phase 7) - Complete
- README.md with instructions
- TESTING_GUIDE.md with patterns
- GitHub Actions workflow configured

## Phase 4: WebSocket Dashboard Alerts

**File**: `pkg/integration/dashboard_alerts_e2e_test.go`
**Status**: Draft created with 5 test scenarios

### Test Scenarios to Complete

#### 1. TestE2E_WebSocket_FrustrationAlert
**Purpose**: Verify frustration alerts delivered to teachers via WebSocket <100ms

**What needs implementation**:
```go
// Connect TestWebSocketClient to actual WebSocket server
teacherClient.Connect(ctx)  // ← Already implemented

// Subscribe to classroom (actual subscription handling)
teacherClient.SubscribeToClassroom("classroom-1")  // ← Already implemented

// Generate frustration metrics
generator.FrustrationMetricPattern(...)  // ← Already implemented

// Trigger actual frustration detection in service
// → Need to call: setup.Frustration.DetectFrustration(metrics)

// Verify alert received via WebSocket
// → Currently using mock alert, need to verify real alerts

// Measure latency
alertLatency := alertReceiveTime.Sub(alertSendTime)
assert.Less(t, alertLatency, 100*time.Millisecond)  // ← Already done
```

**Integration Points**:
- `setup.Frustration` - FrustrationDetectionEngine service
- `setup.WebSocketHub` - WebSocket hub for broadcasting
- Alert event routing through `setup.EventBus`

**Template Changes Needed**:
1. Call actual frustration detection engine instead of mocking event
2. Wait for alert through real WebSocket message (already setup)
3. Verify alert content matches detection result

#### 2. TestE2E_WebSocket_MultipleTeacherSubscriptions
**Purpose**: Verify fan-out to all subscribed teachers

**What needs implementation**:
```go
// Create multiple teacher clients (already done)
for i := 0; i < teacherCount; i++ {
    client.Connect(ctx)  // ← Already implemented
    client.SubscribeToClassroom("classroom-1")  // ← Already implemented
}

// Dispatch frustration event (currently mocked)
// → Need to call: setup.Frustration.DetectFrustration(metrics)
// → This should broadcast to all subscribed teachers via WebSocketHub

// Verify all teachers received alert (already done)
alert, err := teacherClient.WaitForAlert(2 * time.Second)
```

**Integration Points**:
- WebSocket subscription management (pub/sub)
- Fan-out broadcasting logic
- Event bus message routing

**Template Changes Needed**:
1. Trigger real frustration detection (not mocked event)
2. Verify WebSocket Hub broadcasts to all subscribers
3. Validate message content on each teacher client

#### 3. TestE2E_WebSocket_ClassroomMetricsUpdates
**Purpose**: Verify classroom metrics pushed every 5 seconds

**What needs implementation**:
```go
// Generate metrics (already done)
metrics := generator.MetricStream(...)

// Dispatch metrics update event (currently mocked)
// → Need to integrate with: setup.Aggregator.UpdateAggregates(metrics)
// → This should push updates to subscribed teachers

// Wait for metrics update alert (already done)
alert, err := teacherClient.WaitForAlert(pushInterval + 2*time.Second)
```

**Integration Points**:
- Real-time metrics aggregator (`setup.Aggregator`)
- Periodic push scheduling (5-second interval)
- WebSocket message broadcasting

**Template Changes Needed**:
1. Wire real metrics aggregator instead of mock events
2. Verify periodic push at 5-second intervals
3. Validate aggregated metrics content in alert

#### 4. TestE2E_WebSocket_InterventionTracking
**Purpose**: Verify teacher interventions are logged

**What needs implementation**:
```go
// Teacher sends intervention (already implemented)
teacherClient.SendIntervention(studentID, action)

// Log intervention to system (currently mocked)
// → Need to call: setup.TaskQueue.EnqueueTask(...) or
//    setup.InterventionLogger.LogIntervention(teacherID, studentID, action)

// The implementation should:
// 1. Accept WebSocket intervention message
// 2. Route to appropriate service
// 3. Log/persist the intervention
// 4. Update teacher dashboard state
```

**Integration Points**:
- WebSocket message parsing
- Intervention service/task queue
- Logging/persistence layer
- Dashboard state updates

**Template Changes Needed**:
1. Parse incoming WebSocket intervention message
2. Call actual intervention handling service
3. Verify intervention was logged/persisted
4. Validate task creation if needed

#### 5. TestE2E_WebSocket_Reconnection
**Purpose**: Verify buffered alerts delivered on reconnect

**What needs implementation**:
```go
// Disconnect (already done)
teacherClient.Close()

// Generate buffered alerts while disconnected (currently mocked)
// → Need to implement message buffering in WebSocket server
// → When teacher reconnects, retrieve buffered messages

// Reconnect (already done)
teacherClient.Connect(ctx)

// Verify buffered alerts delivered (already done, but test mock data)
receivedAlerts := teacherClient.GetReceivedAlerts()
assert.Greater(t, len(receivedAlerts), 0)
```

**Integration Points**:
- WebSocket session management
- Message buffering on disconnect
- Message replay on reconnect
- Session state tracking

**Template Changes Needed**:
1. Implement message buffering for disconnected sessions
2. Store alerts/updates while session offline
3. Deliver buffered messages on reconnection
4. Verify all buffered messages received

### Completing Phase 4

**Step-by-step**:

1. **Review existing patterns**:
   ```bash
   # Look at how metrics tests interact with services
   cat pkg/integration/metrics_flow_e2e_test.go | grep setup.
   ```

2. **Identify service interfaces** in `pkg/services/usability/`:
   - `UsabilityMetricsService`
   - `FrustrationDetectionEngine`
   - `RealtimeMetricsAggregator`
   - `WebSocket Hub`
   - `EventBus`

3. **Update each test**:
   - Replace mocked events with real service calls
   - Remove comments marked with `// → Need to`
   - Add assertions for actual service behavior

4. **Run and verify**:
   ```bash
   go test -v -tags e2e -run TestE2E_WebSocket ./pkg/integration/
   go test -v -tags e2e -race -run TestE2E_WebSocket ./pkg/integration/
   ```

---

## Phase 5: Frustration Detection

**File**: `pkg/integration/frustration_detection_e2e_test.go`
**Status**: Draft created with 8 test scenarios

### Test Scenarios to Complete

#### 1-5. Pattern Detection Tests

**These tests verify each frustration pattern**:

1. `TestE2E_FrustrationDetection_ExcessiveErrors` - 5+ errors → 0.95 confidence
2. `TestE2E_FrustrationDetection_RepeatedErrors` - 3+ errors → 0.85 confidence
3. `TestE2E_FrustrationDetection_ExcessiveCorrections` - 20+ backspaces → 0.80 confidence
4. `TestE2E_FrustrationDetection_RepeatedCorrections` - 10+ backspaces → 0.70 confidence
5. `TestE2E_FrustrationDetection_ProlongedHesitation` - 30+ sec pause → 0.65 confidence

**What needs implementation** (same pattern for all 5):

```go
// Generate pattern metrics (already done)
frustrationMetrics := generator.FrustrationMetricPattern(...)

// Verify pattern characteristics (already done)
assert.GreaterOrEqual(t, errorCount, 5)

// Call actual frustration detection (needs implementation)
// → Need to call: result := setup.Frustration.Detect(frustrationMetrics)
// → Then verify: assert.Equal(t, result.Confidence, 0.95)

// Currently just hardcoding expected confidence, need to call real engine
```

**Integration Points**:
- `setup.Frustration.Detect(metrics)` - FrustrationDetectionEngine
- Return type with `.Confidence` field
- Pattern matching logic

**Template Changes Needed**:
1. Call actual `setup.Frustration.Detect()` method
2. Assert returned confidence matches expected value
3. Remove hardcoded confidence assignments

#### 6. TestE2E_FrustrationDetection_CombinedIndicators
**Purpose**: Verify multiple patterns combined → confidence 0.99

**What needs implementation**:
```go
// Combine multiple patterns
combinedMetrics = append(combinedMetrics, errorMetrics...)
combinedMetrics = append(combinedMetrics, correctionMetrics...)

// Call detection with combined metrics
// → Need: result := setup.Frustration.Detect(combinedMetrics)
// → Expect: result.Confidence ≈ 0.99 (highest when all indicators present)
```

**Integration Points**:
- Weighted scoring across multiple indicators
- Confidence aggregation logic

**Template Changes Needed**:
1. Call `setup.Frustration.Detect()` with combined metrics
2. Verify confidence is near maximum (0.99)
3. Validate scoring formula combines indicators

#### 7. TestE2E_FrustrationDetection_WeightedScoring
**Purpose**: Verify correct scoring formula

**What needs implementation**:
```go
// Current: hardcoded scoring formula in test
calculatedScore := (tt.errorRate * 0.25) + ...

// Needed: call actual frustration detection engine scoring
// → Need to understand the actual weights:
//    - Error rate: 25%?
//    - Response time: 10%?
//    - Hesitation: 20%?
//    - Corrections: 20%?
//    - Other: 25%?

// For each test case:
// frustrationMetrics := createMetricsWithKnownValues(...)
// result := setup.Frustration.Detect(frustrationMetrics)
// assert.InDelta(t, result.Confidence, tt.expectedScore, 0.05)
```

**Integration Points**:
- Actual frustration detection scoring algorithm
- Weight configuration
- Test data generation

**Template Changes Needed**:
1. Determine actual scoring weights from implementation
2. Update test cases to reflect actual weights
3. Call real detection engine
4. Assert against real calculated scores

#### 8. TestE2E_FrustrationDetection_FalsePositiveRate
**Purpose**: Verify <5% false positive rate on 1000 normal patterns

**What needs implementation**:
```go
// Generate 1000 normal patterns (already done)
normalMetrics := generator.NormalMetricPattern(...)

// Check if detection triggers (currently hardcoded)
// → Need: result := setup.Frustration.Detect(normalMetrics)
// → Check: if result.Confidence > 0.5 { falsePositives++ }

// Verify FP rate < 5% (already done)
assert.Less(t, fpRate, 5.0)
```

**Integration Points**:
- Actual frustration detection thresholds
- Confidence threshold for triggering alert
- False positive measurement

**Template Changes Needed**:
1. Call actual detection engine
2. Check if confidence exceeds alert threshold
3. Count false positives when normal pattern triggers
4. Validate <5% FP rate on realistic data

### Completing Phase 5

**Step-by-step**:

1. **Understand the frustration detection engine**:
   ```bash
   cat pkg/services/usability/frustration_engine.go
   # Look for:
   # - Detect() or DetectFrustration() method signature
   # - Return type structure (Confidence, Pattern, etc.)
   # - Supported patterns and their detection logic
   # - Scoring weights
   ```

2. **Understand metric generator patterns**:
   ```bash
   # Verify each pattern generates expected metric characteristics
   go test -v -tags e2e -run TestE2E_Metrics ./pkg/integration/
   ```

3. **Update each test**:
   - Call actual `setup.Frustration.Detect()` method
   - Remove hardcoded confidence assignments
   - Update expected scores based on actual weights
   - Add assertions for returned confidence

4. **Validate scoring formula**:
   - Extract actual weights from implementation
   - Update test cases to match
   - Test with known input/output pairs

5. **Run and verify**:
   ```bash
   go test -v -tags e2e -run TestE2E_FrustrationDetection ./pkg/integration/
   go test -v -tags e2e -race -run TestE2E_FrustrationDetection ./pkg/integration/
   ```

---

## Common Implementation Tasks

### Task 1: Access Service Implementations

All services are available through `setup`:

```go
setup.RaftCluster              // Raft cluster (use ReplicateLog)
setup.Coordinator              // Session coordinator
setup.TaskQueue                // Distributed task queue
setup.MetricsService           // Metrics recording
setup.Frustration              // FrustrationDetectionEngine
setup.Aggregator               // Real-time metrics aggregator
setup.WebSocketHub             // WebSocket hub for subscriptions
setup.EventBus                 // Event routing
```

### Task 2: Connect to WebSocket Messages

WebSocket communication is pre-built in fixtures:

```go
// Client side (teacher)
client := helper.CreateClient(t, "teacher-1", setup.WebSocketServer.URL)
client.Connect(ctx)
client.SubscribeToClassroom("classroom-1")
alert, err := client.WaitForAlert(timeout)

// Server side (service)
// → WebSocket Hub should broadcast alerts to all subscribed clients
// → Use setup.WebSocketHub.Broadcast(alert) or similar
```

### Task 3: Trigger Service Operations

Example pattern from Phase 2-3:

```go
// Generate test data
metrics := generator.MetricStream(studentID, appName, duration, rate)

// Call service
err := setup.MetricsService.RecordMetrics(metrics)
require.NoError(t, err)

// Verify results
aggregated := setup.Aggregator.GetAggregates(studentID)
assert.Equal(t, len(metrics), aggregated.MetricCount)
```

Apply same pattern for Phase 4-5:

```go
// Phase 4: Frustration detection → WebSocket alert
frustrationMetrics := generator.FrustrationMetricPattern(...)
result := setup.Frustration.Detect(frustrationMetrics)
if result.Confidence > threshold {
    alert := NewFrustrationAlert(result)
    setup.WebSocketHub.Broadcast(alert)
}

// Phase 5: Weighted scoring validation
result := setup.Frustration.Detect(testMetrics)
assert.InDelta(t, result.Confidence, expectedConfidence, tolerance)
```

### Task 4: Verify Behavior

Use same assertion patterns as Phase 2-3:

```go
// Functional assertions
require.NoError(t, err)
assert.Equal(t, expected, actual)
assert.Greater(t, value, threshold)

// Concurrency assertions
go test -v -tags e2e -race -run TestName ./pkg/integration/

// Performance assertions
assert.Less(t, latency, 100*time.Millisecond)
assert.Greater(t, throughput, 1000*float64(itemsPerSecond))
```

---

## Testing Checklist

Before submitting Phase 4-5:

### Code Quality
- [ ] All TODO comments replaced with actual implementation
- [ ] No hardcoded mock values (use real service calls)
- [ ] Assertions match actual service behavior
- [ ] Proper error handling with require/assert

### Testing
- [ ] All tests pass: `go test -v -tags e2e ./pkg/integration/`
- [ ] Race detector clean: `go test -v -tags e2e -race ./pkg/integration/`
- [ ] Coverage analyzed: `go test -v -tags e2e -coverprofile=coverage.out ./pkg/integration/`
- [ ] Benchmarks working: `go test -v -tags e2e -bench=. ./pkg/integration/`

### Documentation
- [ ] Test comments document purpose and assertions
- [ ] Service method calls are clear and documented
- [ ] Expected values documented with rationale

### Integration
- [ ] Uses existing E2ETestSetup patterns
- [ ] Reuses test fixtures (don't create new ones)
- [ ] Follows naming convention `TestE2E_*_*`
- [ ] Proper resource cleanup with `defer setup.Cleanup()`

---

## Resources

### Related Files
- `pkg/integration/README.md` - Test suite overview
- `pkg/integration/TESTING_GUIDE.md` - Patterns and best practices
- `pkg/integration/task_queue_e2e_test.go` - Service integration examples
- `pkg/integration/metrics_flow_e2e_test.go` - Fixture usage examples
- `pkg/integration/fixtures/*.go` - Available test data factories

### Service Interfaces
- `pkg/services/usability/frustration_engine.go` - Frustration detection
- `pkg/services/usability/metrics_service.go` - Metrics recording
- `pkg/services/usability/realtime_aggregator.go` - Metrics aggregation
- `pkg/websocket/hub.go` - WebSocket broadcasting
- `pkg/cluster/queue/task_queue.go` - Task queue

### Testing Patterns
```go
// Setup phase
setup := NewE2ETestSetup(t, nodeCount)
defer setup.Cleanup()

// Service calls
result := setup.SomeService.DoSomething(data)
require.NoError(t, err)

// Assertions
assert.Equal(t, expected, result)
assert.Greater(t, value, threshold)
assert.Less(t, latency, maxLatency)

// Concurrency
var wg sync.WaitGroup
wg.Add(1)
go func() {
    defer wg.Done()
    // concurrent work
}()
wg.Wait()
```

---

## Getting Help

If implementation gets stuck:

1. **Review working examples**: Look at `task_queue_e2e_test.go` for service integration patterns
2. **Check fixtures**: Use metrics_fixtures and websocket_fixtures for data generation
3. **Read documentation**: TESTING_GUIDE.md has detailed walkthroughs
4. **Verify service API**: Check actual service method signatures
5. **Run tests incrementally**: Complete one test at a time

---

**Status**: Draft templates created, ready for implementation
**Expected Effort**: 2-3 hours for complete Phase 4-5 implementation
**Current Blocker**: Service implementations must be available in `setup.*` components

Good luck! 🚀
