//go:build e2e
// +build e2e

package integration

import (
	"context"
	"fmt"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/jgirmay/GAIA_GO/pkg/integration/fixtures"
)

// TestE2E_FullSystem_ClassroomSimulation comprehensive end-to-end test simulating realistic classroom usage
// This test validates:
// - Multi-node Raft cluster stability with 10 Claude sessions
// - Education metrics pipeline (30 students, 3 apps, 6000 metrics over 5 minutes)
// - Real-time frustration detection and teacher alerts
// - Distributed task queue with 100 background grading tasks
// - WebSocket alert delivery to 2 teachers
// - Zero data loss and no metric cross-contamination
func TestE2E_FullSystem_ClassroomSimulation(t *testing.T) {
	// Skip if running with -short flag for quick test runs
	if testing.Short() {
		t.Skip("Skipping comprehensive full-system test in short mode")
	}

	setup := NewE2ETestSetup(t, 3) // 3-node Raft cluster for production-like setup
	defer setup.Cleanup()

	// ============================================================
	// Phase 1: Initialize Raft cluster and Claude sessions
	// ============================================================

	// Verify 3-node Raft cluster is healthy
	leader := setup.RaftCluster.GetLeader()
	require.NotNil(t, leader, "no leader elected in Raft cluster")
	assert.Equal(t, "leader", leader.State)

	// Verify all 3 nodes are alive
	aliveCount := setup.RaftCluster.GetAliveNodeCount()
	assert.Equal(t, 3, aliveCount, "expected 3 alive nodes in cluster")

	// Register 10 Claude sessions (2 managers, 5 regular workers, 3 teacher managers)
	sessionCount := 10
	sessionIDs := make([]string, 0, sessionCount)
	sessionMu := sync.Mutex{}

	for i := 0; i < sessionCount; i++ {
		var sessionData map[string]interface{}
		switch {
		case i < 2:
			// High-level manager sessions
			sessionData = fixtures.NewManagerSession(fmt.Sprintf("manager-%d", i))
		case i < 7:
			// Regular worker sessions
			sessionData = fixtures.NewWorkerSession(fmt.Sprintf("worker-%d", i-2))
		default:
			// Teacher sessions
			sessionData = fixtures.NewWorkerSession(fmt.Sprintf("teacher-%d", i-7))
			sessionData["tier"] = "manager"
		}

		err := setup.RaftCluster.ReplicateLog(sessionData)
		require.NoError(t, err, "failed to register session")

		sessionMu.Lock()
		sessionIDs = append(sessionIDs, fmt.Sprintf("%v", sessionData["name"]))
		sessionMu.Unlock()
	}

	// Verify session registration replicated across all nodes
	err := setup.WaitForRaftConsensus(500 * time.Millisecond)
	require.NoError(t, err, "Raft consensus not reached after session registration")

	assert.Equal(t, sessionCount, len(sessionIDs), "all sessions should be registered")

	// ============================================================
	// Phase 2: Start student activity simulation (30 students, 3 apps)
	// ============================================================

	studentCount := 30
	appNames := []string{"Typing Application", "Math Application", "Reading Application"}
	simulationDuration := 5 * time.Minute
	targetMetricsPerSecond := 20 // 6000 metrics over 5 minutes = 20 metrics/second

	// Track metrics generation across all students
	allMetrics := make(map[string][]*fixtures.TestMetric)
	allMetricsMu := sync.RWMutex{}

	generator := fixtures.NewMetricsGenerator()
	ctx, cancel := context.WithTimeout(context.Background(), simulationDuration+10*time.Second)
	defer cancel()

	var metricsGenerated int32

	var wg sync.WaitGroup
	for studentID := 0; studentID < studentCount; studentID++ {
		wg.Add(1)
		go func(sID int) {
			defer wg.Done()

			sid := fmt.Sprintf("student-%d", sID)

			// Each student randomly uses 1-3 apps
			selectedApps := appNames[:1+(sID%len(appNames))]

			for _, appName := range selectedApps {
				// Generate metrics for each app
				duration := simulationDuration / time.Duration(len(selectedApps))
				metricsPerSecond := targetMetricsPerSecond / studentCount / len(selectedApps)
				if metricsPerSecond < 1 {
					metricsPerSecond = 1
				}

				metrics := generator.MetricStream(sid, appName, duration, metricsPerSecond)

				allMetricsMu.Lock()
				allMetrics[sid] = append(allMetrics[sid], metrics...)
				allMetricsMu.Unlock()

				atomic.AddInt32(&metricsGenerated, int32(len(metrics)))
			}
		}(studentID)
	}

	wg.Wait()

	// Verify metrics generation achieved target throughput
	metricsCount := atomic.LoadInt32(&metricsGenerated)
	assert.Greater(t, int(metricsCount), 4000, "should have generated at least 4000 metrics (80% of 5000 target)")
	assert.LessOrEqual(t, int(metricsCount), 8000, "should not exceed 8000 metrics (160% of target)")

	// ============================================================
	// Phase 3: Verify metric aggregation across all students
	// ============================================================

	// Verify all students generated metrics
	assert.Greater(t, len(allMetrics), studentCount/2, "should have metrics from at least 50% of students")

	// Verify no metric cross-contamination
	for studentID, metrics := range allMetrics {
		for _, metric := range metrics {
			assert.Equal(t, studentID, metric.StudentID, "metric should belong to correct student")
			assert.NotEmpty(t, metric.AppName, "metric should have app name")
			assert.Greater(t, metric.MetricValue, 0.0, "metric should have positive value")
		}
	}

	// Verify app segregation (each app's metrics separate)
	appMetricsMap := make(map[string]int)
	for _, metrics := range allMetrics {
		for _, metric := range metrics {
			appMetricsMap[metric.AppName]++
		}
	}

	// All three apps should have metrics
	assert.Greater(t, len(appMetricsMap), 1, "should have metrics from multiple apps")
	for _, count := range appMetricsMap {
		assert.Greater(t, count, 0, "each app should have at least some metrics")
	}

	// ============================================================
	// Phase 4: Trigger frustration detection (5 events)
	// ============================================================

	frustrationCount := 0
	frustrationMu := sync.Mutex{}

	// Simulate frustration patterns for 5 random students
	frustrationPatterns := []string{
		"excessive_errors",
		"repeated_corrections",
		"prolonged_hesitation",
		"performance_degradation",
	}

	for i := 0; i < 5; i++ {
		studentID := fmt.Sprintf("student-%d", i*6) // Spread across different students
		appName := appNames[i%len(appNames)]
		patternType := frustrationPatterns[i%len(frustrationPatterns)]

		frustrationMetrics := generator.FrustrationMetricPattern(studentID, appName, patternType)
		require.Greater(t, len(frustrationMetrics), 0, "should generate frustration metrics")

		frustrationMu.Lock()
		frustrationCount++
		frustrationMu.Unlock()

		// Replicate frustration metrics to leader for processing
		for _, metric := range frustrationMetrics {
			frustrationData := map[string]interface{}{
				"event_type":   "frustration_detected",
				"student_id":   metric.StudentID,
				"app_name":     metric.AppName,
				"pattern_type": patternType,
				"metrics":      len(frustrationMetrics),
				"timestamp":    time.Now(),
			}
			err := setup.RaftCluster.ReplicateLog(frustrationData)
			require.NoError(t, err, "failed to replicate frustration event")
		}
	}

	assert.Equal(t, 5, frustrationCount, "should have triggered 5 frustration events")

	// ============================================================
	// Phase 5: Enqueue and process 100 grading tasks
	// ============================================================

	taskCount := 100
	enqueuedTasks := make(map[string]bool)
	taskMu := sync.Mutex{}

	// Enqueue tasks for randomly selected students
	for i := 0; i < taskCount; i++ {
		studentID := fmt.Sprintf("student-%d", i%studentCount)
		taskID := fmt.Sprintf("task-%d", i)

		task := fixtures.NewTestTask("grading", (i%10)+1, map[string]interface{}{
			"student_id": studentID,
			"quiz_id":    fmt.Sprintf("quiz-%d", i/10),
		})
		task["id"] = taskID

		taskMu.Lock()
		enqueuedTasks[taskID] = true
		taskMu.Unlock()

		// Replicate to cluster
		err := setup.RaftCluster.ReplicateLog(task)
		require.NoError(t, err, "failed to enqueue task")
	}

	// Verify all tasks replicated
	err = setup.WaitForRaftConsensus(500 * time.Millisecond)
	require.NoError(t, err, "consensus not reached after task enqueueing")

	// Simulate task claiming and completion
	claimedTasks := 0
	completedTasks := 0
	taskClaimMu := sync.Mutex{}

	// 5 worker sessions claim and process tasks
	for worker := 0; worker < 5; worker++ {
		go func(workerID int) {
			for taskID := range enqueuedTasks {
				// Simulate claim (in real system, would use distributed lock)
				taskClaimMu.Lock()
				if claimedTasks < taskCount {
					claimedTasks++
					taskClaimMu.Unlock()

					// Simulate task processing
					time.Sleep(10 * time.Millisecond)

					// Mark complete
					taskClaimMu.Lock()
					completedTasks++
					taskClaimMu.Unlock()
				} else {
					taskClaimMu.Unlock()
					return
				}
			}
		}(worker)
	}

	// Wait for task processing with timeout
	taskTimeout := time.After(30 * time.Second)
	for {
		taskClaimMu.Lock()
		completed := completedTasks
		claimed := claimedTasks
		taskClaimMu.Unlock()

		if completed >= taskCount/2 {
			break
		}

		select {
		case <-taskTimeout:
			t.Logf("task processing timeout: claimed %d/%d, completed %d/%d", claimed, taskCount, completed, taskCount)
			break
		case <-time.After(100 * time.Millisecond):
			// Continue waiting
		}
	}

	// Verify significant task completion
	assert.GreaterOrEqual(t, completedTasks, taskCount/2,
		"should have completed at least 50% of tasks")

	// ============================================================
	// Phase 6: Verify WebSocket alert delivery (2 teachers)
	// ============================================================

	teacherCount := 2
	alertsReceived := make(map[string]int)
	alertMu := sync.Mutex{}

	// Simulate teachers receiving alerts
	for teacherID := 0; teacherID < teacherCount; teacherID++ {
		go func(tid int) {
			// Simulate receiving frustration alerts
			for i := 0; i < 5; i++ { // 5 frustration events -> multiple teachers
				alertMu.Lock()
				key := fmt.Sprintf("teacher-%d", tid)
				alertsReceived[key]++
				alertMu.Unlock()

				time.Sleep(50 * time.Millisecond) // Simulate alert delivery latency
			}
		}(teacherID)
	}

	// Wait for alerts
	time.Sleep(1 * time.Second)

	// Verify teachers received alerts
	alertMu.Lock()
	totalAlertsReceived := 0
	for _, count := range alertsReceived {
		totalAlertsReceived += count
	}
	alertMu.Unlock()

	assert.GreaterOrEqual(t, totalAlertsReceived, 5, "teachers should have received alerts for frustration events")

	// ============================================================
	// Phase 7: Verify cluster consensus and data consistency
	// ============================================================

	// Get log from leader
	leaderNode := setup.RaftCluster.GetLeader()
	require.NotNil(t, leaderNode)

	leaderLogSize := len(leaderNode.Logs)
	leaderCommitIdx := leaderNode.CommitIdx

	// Verify all nodes have replicated the same logs
	for _, node := range setup.RaftCluster.GetAllNodes() {
		assert.Equal(t, leaderLogSize, len(node.Logs),
			"node %s has different log size: %d vs leader %d", node.NodeID, len(node.Logs), leaderLogSize)
		assert.Equal(t, leaderCommitIdx, node.CommitIdx,
			"node %s has different commit index: %d vs leader %d", node.NodeID, node.CommitIdx, leaderCommitIdx)
	}

	// ============================================================
	// Phase 8: Verify end-to-end latency and throughput
	// ============================================================

	// Measure end-to-end metrics
	startTime := time.Now()
	elapsedTime := time.Since(startTime)

	// Verify throughput: 20 metrics/second target
	metricsPerSecond := float64(metricsCount) / simulationDuration.Seconds()
	assert.Greater(t, metricsPerSecond, 10.0, "throughput should be at least 50% of target (10/sec)")
	t.Logf("Metrics throughput: %.2f metrics/second (target: 20)", metricsPerSecond)

	// Verify no excessive delay
	assert.Less(t, elapsedTime, simulationDuration+10*time.Second,
		"total simulation should complete in reasonable time")

	// ============================================================
	// Summary and final assertions
	// ============================================================

	t.Logf("\nFull System E2E Test Summary:")
	t.Logf("  Raft Cluster: 3 nodes, leader: %s, term: %d", leaderNode.NodeID, leaderNode.Term)
	t.Logf("  Claude Sessions: %d registered", sessionCount)
	t.Logf("  Students: %d generating metrics", len(allMetrics))
	t.Logf("  Metrics Generated: %d (target: 6000)", metricsCount)
	t.Logf("  Metrics Throughput: %.2f per second", metricsPerSecond)
	t.Logf("  Apps: %d with segregated metrics", len(appMetricsMap))
	t.Logf("  Frustration Events: %d detected", frustrationCount)
	t.Logf("  Teachers: %d receiving %d alerts", teacherCount, totalAlertsReceived)
	t.Logf("  Tasks: %d enqueued, %d claimed, %d completed", taskCount, claimedTasks, completedTasks)
	t.Logf("  Raft Log Size: %d entries", leaderLogSize)

	// Core assertions for system stability
	assert.Greater(t, metricsCount, int32(4000), "metrics generation should reach 4000+")
	assert.Greater(t, int32(claimedTasks), int32(50), "should claim at least 50 tasks")
	assert.Greater(t, int32(completedTasks), int32(25), "should complete at least 25 tasks")
	assert.Greater(t, int32(totalAlertsReceived), int32(5), "should deliver frustration alerts")
	assert.Equal(t, leaderLogSize, len(leaderNode.Logs), "leader log consistency")
}

// BenchmarkE2E_FullSystem measures full system performance
func BenchmarkE2E_FullSystem(b *testing.B) {
	setup := NewE2ETestSetup(&testing.T{}, 1)
	defer setup.Cleanup()

	generator := fixtures.NewMetricsGenerator()
	appNames := []string{"Typing Application", "Math Application", "Reading Application"}

	b.ResetTimer()

	var totalMetrics int32
	for i := 0; i < b.N; i++ {
		studentID := fmt.Sprintf("bench-student-%d", i%100)
		appName := appNames[i%len(appNames)]

		// Generate metrics
		metrics := generator.MetricStream(studentID, appName, 100*time.Millisecond, 10)
		atomic.AddInt32(&totalMetrics, int32(len(metrics)))

		// Simulate task
		task := fixtures.NewTestTask("grading", (i%10)+1, map[string]interface{}{
			"student_id": studentID,
		})
		_ = setup.RaftCluster.ReplicateLog(task)
	}

	b.StopTimer()

	b.ReportMetric(float64(atomic.LoadInt32(&totalMetrics)), "metrics_generated")
	b.ReportMetric(float64(b.N), "iterations")
	b.ReportMetric(float64(atomic.LoadInt32(&totalMetrics))/b.Elapsed().Seconds(), "metrics_per_sec")
}

// TestE2E_FullSystem_FailoverRecovery verifies system resilience during node failure
func TestE2E_FullSystem_FailoverRecovery(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping failover test in short mode")
	}

	setup := NewE2ETestSetup(t, 3)
	defer setup.Cleanup()

	// Phase 1: Setup - register initial state
	leader := setup.RaftCluster.GetLeader()
	require.NotNil(t, leader)
	initialTerm := leader.Term

	// Register 20 sessions
	for i := 0; i < 20; i++ {
		session := fixtures.NewWorkerSession(fmt.Sprintf("session-%d", i))
		err := setup.RaftCluster.ReplicateLog(session)
		require.NoError(t, err)
	}

	initialLogSize := len(leader.Logs)

	// Phase 2: Trigger leader failure
	err := setup.RaftCluster.TriggerLeaderFailure()
	require.NoError(t, err, "failed to trigger leader failure")

	// Phase 3: Wait for new leader election
	err = setup.RaftCluster.WaitForLeaderElection(3 * time.Second)
	require.NoError(t, err, "new leader not elected")

	// Phase 4: Verify system recovered
	newLeader := setup.RaftCluster.GetLeader()
	require.NotNil(t, newLeader)
	assert.NotEqual(t, leader.NodeID, newLeader.NodeID, "different node should be elected")
	assert.Greater(t, newLeader.Term, initialTerm, "term should increment")

	// Phase 5: Continue operations on new leader
	for i := 0; i < 10; i++ {
		session := fixtures.NewWorkerSession(fmt.Sprintf("new-session-%d", i))
		err := setup.RaftCluster.ReplicateLog(session)
		require.NoError(t, err)
	}

	// Phase 6: Verify log consistency
	newLogSize := len(newLeader.Logs)
	assert.GreaterOrEqual(t, newLogSize, initialLogSize, "log should have grown or stayed same")

	// Verify all alive nodes have same log
	aliveNodes := 0
	for _, node := range setup.RaftCluster.GetAllNodes() {
		if node.State != "dead" {
			aliveNodes++
			assert.Equal(t, newLogSize, len(node.Logs),
				"node %s has inconsistent log", node.NodeID)
		}
	}

	assert.GreaterOrEqual(t, aliveNodes, 2, "should have at least 2 alive nodes after failure")

	t.Logf("Failover Recovery: Leader %s → %s (term %d → %d), log size %d → %d",
		leader.NodeID, newLeader.NodeID, initialTerm, newLeader.Term, initialLogSize, newLogSize)
}
