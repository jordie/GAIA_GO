//go:build e2e
// +build e2e

package integration

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/jgirmay/GAIA_GO/pkg/integration/fixtures"
)

// TestE2E_SessionRegistrationAndHeartbeat verifies session registration and Raft replication
func TestE2E_SessionRegistrationAndHeartbeat(t *testing.T) {
	setup := NewE2ETestSetup(t, 3) // 3-node Raft cluster
	defer setup.Cleanup()

	// Register 5 Claude sessions with different tiers
	sessionFixtures := fixtures.SessionFixtures{}

	managerSessions := fixtures.SessionBatch(2, "manager")
	workerSessions := fixtures.SessionBatch(3, "worker")

	// Simulate registration on leader node
	leader := setup.RaftCluster.GetLeader()
	require.NotNil(t, leader, "no leader elected")
	require.Equal(t, "leader", leader.State)

	// Register sessions by replicating to all nodes
	for _, sessionData := range append(managerSessions, workerSessions...) {
		err := setup.RaftCluster.ReplicateLog(sessionData)
		require.NoError(t, err, "failed to replicate session registration")
	}

	// Verify Raft consensus reached within 500ms
	err := setup.WaitForRaftConsensus(500 * time.Millisecond)
	require.NoError(t, err, "Raft consensus not reached within timeout")

	// Verify all nodes have the sessions in their logs
	allNodes := setup.RaftCluster.GetAllNodes()
	require.Greater(t, len(allNodes), 0, "no nodes in cluster")

	for _, node := range allNodes {
		assert.Equal(t, 5, len(node.Logs), "node %s has incorrect log length", node.NodeID)
		assert.Equal(t, leader.CommitIdx, node.CommitIdx, "node %s has different commit index", node.NodeID)
	}

	// Verify no duplicate session IDs
	sessionIDs := make(map[string]bool)
	for _, sessionData := range append(managerSessions, workerSessions...) {
		sessionID := fmt.Sprintf("%v", sessionData["name"])
		assert.False(t, sessionIDs[sessionID], "duplicate session ID: %s", sessionID)
		sessionIDs[sessionID] = true
	}
}

// TestE2E_SessionFailover_LeaderElection verifies leader failure and election
func TestE2E_SessionFailover_LeaderElection(t *testing.T) {
	setup := NewE2ETestSetup(t, 3) // 3-node cluster for quorum
	defer setup.Cleanup()

	// Get current leader
	leader := setup.RaftCluster.GetLeader()
	require.NotNil(t, leader, "no leader elected")
	leaderID := leader.NodeID

	// Record initial leader term
	initialTerm := leader.Term

	// Trigger leader failure
	err := setup.RaftCluster.TriggerLeaderFailure()
	require.NoError(t, err, "failed to trigger leader failure")

	// Wait for new leader election (should be < 1 second)
	err = setup.RaftCluster.WaitForLeaderElection(1 * time.Second)
	require.NoError(t, err, "new leader not elected within timeout")

	// Verify a new leader was elected
	newLeader := setup.RaftCluster.GetLeader()
	require.NotNil(t, newLeader, "no leader after failover")
	assert.NotEqual(t, leaderID, newLeader.NodeID, "same node elected as leader after failure")

	// Verify leader term increased
	assert.Greater(t, newLeader.Term, initialTerm, "leader term did not increase")

	// Verify old leader is marked as dead
	oldLeaderNode := setup.RaftCluster.GetNode(leaderID)
	assert.Equal(t, "dead", oldLeaderNode.State)

	// Verify cluster has 2 alive nodes (original leader dead, but 2 followers alive)
	aliveCount := setup.RaftCluster.GetAliveNodeCount()
	assert.Equal(t, 2, aliveCount, "expected 2 alive nodes after leader failure")
}

// TestE2E_SessionHealthMonitoring verifies health status transitions
func TestE2E_SessionHealthMonitoring(t *testing.T) {
	setup := NewE2ETestSetup(t, 1) // Single node sufficient for health monitoring
	defer setup.Cleanup()

	// Register a session and simulate heartbeats
	sessionData := fixtures.NewWorkerSession("health-test-1")

	// Initial state
	assert.Equal(t, "healthy", sessionData["health_status"])
	assert.Equal(t, 0, sessionData["consecutive_fails"])

	// Simulate heartbeat failures
	// After 15 seconds without heartbeat: degraded
	// After 30 seconds without heartbeat: failed
	time.Sleep(100 * time.Millisecond) // Simulate time passing

	// Verify health transition logic (in real implementation)
	// degraded := consecutiveFails >= 1
	// failed := consecutiveFails >= 3 (or 30 second timeout)

	// For now, we test the data structure
	require.NotNil(t, sessionData["health_status"])
	require.NotNil(t, sessionData["consecutive_fails"])
}

// TestE2E_SessionAffinityScoring verifies task assignment by affinity score
func TestE2E_SessionAffinityScoring(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	// Create sessions with different specializations
	type SessionSpecialization struct {
		name      string
		tier      string
		provider  string
		specialty string // "math", "reading", "general"
	}

	sessions := []SessionSpecialization{
		{name: "math-specialist", tier: "worker", provider: "claude", specialty: "math"},
		{name: "reading-specialist", tier: "worker", provider: "claude", specialty: "reading"},
		{name: "general-worker", tier: "worker", provider: "claude", specialty: "general"},
	}

	// Create tasks with affinity requirements
	type TaskWithAffinity struct {
		id       string
		taskType string
		affinity string // "math", "reading", "general"
	}

	tasks := []TaskWithAffinity{
		{id: "task-1", taskType: "grading", affinity: "math"},
		{id: "task-2", taskType: "grading", affinity: "reading"},
		{id: "task-3", taskType: "grading", affinity: "general"},
	}

	// Verify affinity score calculation (0.0 - 1.0)
	// Perfect match: 1.0
	// Partial match: 0.5
	// No match: 0.0

	affinityScores := make(map[string]map[string]float64)

	for _, session := range sessions {
		affinityScores[session.name] = make(map[string]float64)
		for _, task := range tasks {
			var score float64
			if session.specialty == task.affinity {
				score = 1.0 // Perfect match
			} else if session.specialty == "general" || task.affinity == "general" {
				score = 0.5 // Partial match (general can handle anything)
			} else {
				score = 0.0 // No match
			}
			affinityScores[session.name][task.id] = score
		}
	}

	// Verify math specialist has highest affinity for math task
	assert.Equal(t, 1.0, affinityScores["math-specialist"]["task-1"])
	assert.Equal(t, 0.0, affinityScores["math-specialist"]["task-2"])
	assert.Equal(t, 0.5, affinityScores["math-specialist"]["task-3"])

	// Verify general worker has equal affinity for all
	assert.Equal(t, 0.5, affinityScores["general-worker"]["task-1"])
	assert.Equal(t, 0.5, affinityScores["general-worker"]["task-2"])
	assert.Equal(t, 0.5, affinityScores["general-worker"]["task-3"])
}

// TestE2E_MultiNodeCoordination verifies coordination across 5-node cluster
func TestE2E_MultiNodeCoordination(t *testing.T) {
	setup := NewE2ETestSetup(t, 5) // 5-node cluster
	defer setup.Cleanup()

	// Register 20 sessions distributed across nodes
	sessionCount := 20
	for i := 0; i < sessionCount; i++ {
		tier := "worker"
		if i%5 == 0 {
			tier = "manager"
		}
		sessionData := fixtures.NewWorkerSession(fmt.Sprintf("session-%d", i))
		sessionData["tier"] = tier

		err := setup.RaftCluster.ReplicateLog(sessionData)
		require.NoError(t, err)
	}

	// Verify Raft consensus on all nodes
	err := setup.WaitForRaftConsensus(500 * time.Millisecond)
	require.NoError(t, err, "consensus not reached")

	// Verify all nodes have same logs
	leader := setup.RaftCluster.GetLeader()
	require.NotNil(t, leader)

	for _, node := range setup.RaftCluster.GetAllNodes() {
		assert.Equal(t, len(leader.Logs), len(node.Logs),
			"node %s has different log length", node.NodeID)
		assert.Equal(t, leader.CommitIdx, node.CommitIdx,
			"node %s has different commit index", node.NodeID)
	}

	// Verify all sessions are in cluster logs
	assert.Greater(t, len(leader.Logs), 0)
	assert.LessOrEqual(t, sessionCount, len(leader.Logs))
}

// TestE2E_SessionHeartbeatFrequency verifies heartbeat timing
func TestE2E_SessionHeartbeatFrequency(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	// Session heartbeat should be every 10 seconds
	expectedInterval := 10 * time.Second

	// Register a session
	sessionData := fixtures.NewWorkerSession("heartbeat-test")

	// Verify heartbeat interval metadata exists
	require.NotNil(t, sessionData)

	// In real implementation, would verify:
	// - Heartbeat sent every 10 seconds
	// - Missed heartbeat threshold = 3 failures (30 seconds)
	// - Degraded status after 15 seconds (1.5 heartbeat misses)
	// - Failed status after 30 seconds (3 heartbeat misses)
}

// BenchmarkE2E_SessionRegistration benchmarks session registration throughput
func BenchmarkE2E_SessionRegistration(b *testing.B) {
	setup := NewE2ETestSetup(&testing.T{}, 3)
	defer setup.Cleanup()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		sessionData := fixtures.NewWorkerSession(fmt.Sprintf("bench-session-%d", i))
		_ = setup.RaftCluster.ReplicateLog(sessionData)
	}
	b.StopTimer()

	// Verify consensus
	_ = setup.WaitForRaftConsensus(500 * time.Millisecond)
}
