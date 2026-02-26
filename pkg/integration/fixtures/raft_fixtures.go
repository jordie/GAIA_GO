// Package fixtures provides test data factories for E2E integration tests
//go:build e2e
// +build e2e

package fixtures

import (
	"fmt"
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
)

// TestRaftCluster manages a test Raft cluster for multi-node testing
type TestRaftCluster struct {
	nodes       map[string]*TestRaftNode
	mu          sync.RWMutex
	leaderID    string
	t           *testing.T
	initialized bool
}

// TestRaftNode represents a single Raft node in a test cluster
type TestRaftNode struct {
	NodeID    string
	State     string // "leader", "follower", "candidate"
	Term      uint64
	CommitIdx uint64
	LastIdx   uint64
	Logs      []interface{}
	Peers     []string
	mu        sync.RWMutex
}

// NewTestRaftCluster creates a new test Raft cluster with specified number of nodes
func NewTestRaftCluster(t *testing.T, nodeCount int) *TestRaftCluster {
	require.Greater(t, nodeCount, 0, "nodeCount must be greater than 0")

	cluster := &TestRaftCluster{
		nodes:       make(map[string]*TestRaftNode),
		t:           t,
		initialized: false,
	}

	// Create nodes
	var peerList []string
	for i := 0; i < nodeCount; i++ {
		nodeID := fmt.Sprintf("node-%d", i+1)
		peerList = append(peerList, nodeID)
	}

	for i, nodeID := range peerList {
		node := &TestRaftNode{
			NodeID:    nodeID,
			State:     "follower",
			Term:      0,
			CommitIdx: 0,
			LastIdx:   0,
			Logs:      make([]interface{}, 0),
			Peers:     filterPeers(peerList, nodeID),
			mu:        sync.RWMutex{},
		}
		cluster.nodes[nodeID] = node

		// First node becomes leader
		if i == 0 {
			node.State = "leader"
			node.Term = 1
			cluster.leaderID = nodeID
		}
	}

	cluster.initialized = true
	return cluster
}

// GetLeader returns the current leader node
func (c *TestRaftCluster) GetLeader() *TestRaftNode {
	c.mu.RLock()
	defer c.mu.RUnlock()

	if c.leaderID != "" {
		return c.nodes[c.leaderID]
	}
	return nil
}

// GetNode returns a node by ID
func (c *TestRaftCluster) GetNode(nodeID string) *TestRaftNode {
	c.mu.RLock()
	defer c.mu.RUnlock()

	return c.nodes[nodeID]
}

// GetAllNodes returns all nodes in the cluster
func (c *TestRaftCluster) GetAllNodes() []*TestRaftNode {
	c.mu.RLock()
	defer c.mu.RUnlock()

	nodes := make([]*TestRaftNode, 0)
	for _, node := range c.nodes {
		nodes = append(nodes, node)
	}
	return nodes
}

// WaitForLeaderElection waits for cluster to elect a leader (or re-elect after failure)
func (c *TestRaftCluster) WaitForLeaderElection(timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	ticker := time.NewTicker(10 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			leader := c.GetLeader()
			if leader != nil && leader.State == "leader" {
				return nil
			}
			if time.Now().After(deadline) {
				return fmt.Errorf("leader election timeout after %v", timeout)
			}
		}
	}
}

// WaitForConsensus waits for all nodes to reach consensus on a value
func (c *TestRaftCluster) WaitForConsensus(timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	ticker := time.NewTicker(10 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			if c.HasConsensus() {
				return nil
			}
			if time.Now().After(deadline) {
				return fmt.Errorf("consensus timeout after %v", timeout)
			}
		}
	}
}

// HasConsensus checks if all nodes have reached consensus
func (c *TestRaftCluster) HasConsensus() bool {
	c.mu.RLock()
	defer c.mu.RUnlock()

	if len(c.nodes) == 0 {
		return false
	}

	// Check if majority of nodes agree on commit index
	commitIndices := make(map[uint64]int)
	for _, node := range c.nodes {
		commitIndices[node.CommitIdx]++
	}

	majority := (len(c.nodes) / 2) + 1
	for _, count := range commitIndices {
		if count >= majority {
			return true
		}
	}

	return false
}

// StopNode gracefully stops a node (simulates node failure)
func (c *TestRaftCluster) StopNode(nodeID string) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	node, exists := c.nodes[nodeID]
	if !exists {
		return fmt.Errorf("node %s not found", nodeID)
	}

	node.mu.Lock()
	node.State = "dead"
	node.mu.Unlock()

	// If this was the leader, clear it
	if c.leaderID == nodeID {
		c.leaderID = ""
	}

	return nil
}

// RestartNode restarts a previously stopped node
func (c *TestRaftCluster) RestartNode(nodeID string) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	node, exists := c.nodes[nodeID]
	if !exists {
		return fmt.Errorf("node %s not found", nodeID)
	}

	node.mu.Lock()
	node.State = "follower"
	node.mu.Unlock()

	return nil
}

// ReplicateLog simulates log replication to all nodes
func (c *TestRaftCluster) ReplicateLog(entry interface{}) error {
	leader := c.GetLeader()
	if leader == nil {
		return fmt.Errorf("no leader elected")
	}

	leader.mu.Lock()
	leader.LastIdx++
	leader.Logs = append(leader.Logs, entry)
	leader.mu.Unlock()

	// Replicate to all followers
	for _, node := range c.GetAllNodes() {
		if node.NodeID == leader.NodeID {
			continue // Skip leader itself
		}

		node.mu.Lock()
		node.Logs = append(node.Logs, entry)
		node.LastIdx++
		node.mu.Unlock()
	}

	// Update commit index on leader
	leader.mu.Lock()
	leader.CommitIdx = leader.LastIdx
	leader.mu.Unlock()

	// Update commit index on followers
	for _, node := range c.GetAllNodes() {
		if node.NodeID == leader.NodeID {
			continue
		}
		node.mu.Lock()
		node.CommitIdx = node.LastIdx
		node.mu.Unlock()
	}

	return nil
}

// TriggerLeaderFailure simulates current leader failure and new election
func (c *TestRaftCluster) TriggerLeaderFailure() error {
	leader := c.GetLeader()
	if leader == nil {
		return fmt.Errorf("no leader to fail")
	}

	if err := c.StopNode(leader.NodeID); err != nil {
		return err
	}

	// New leader election: choose first alive follower
	for _, node := range c.GetAllNodes() {
		if node.NodeID != leader.NodeID {
			node.mu.Lock()
			node.State = "leader"
			node.Term++
			node.mu.Unlock()

			c.mu.Lock()
			c.leaderID = node.NodeID
			c.mu.Unlock()

			return nil
		}
	}

	return fmt.Errorf("no nodes available for new leader election")
}

// GetNodeCount returns the number of nodes in the cluster
func (c *TestRaftCluster) GetNodeCount() int {
	c.mu.RLock()
	defer c.mu.RUnlock()

	return len(c.nodes)
}

// GetAliveNodeCount returns the number of alive (not dead) nodes
func (c *TestRaftCluster) GetAliveNodeCount() int {
	c.mu.RLock()
	defer c.mu.RUnlock()

	count := 0
	for _, node := range c.nodes {
		node.mu.RLock()
		if node.State != "dead" {
			count++
		}
		node.mu.RUnlock()
	}
	return count
}

// Shutdown shuts down the entire cluster
func (c *TestRaftCluster) Shutdown() error {
	c.mu.Lock()
	defer c.mu.Unlock()

	for _, node := range c.nodes {
		node.mu.Lock()
		node.State = "dead"
		node.mu.Unlock()
	}

	return nil
}

// Helper function to filter peers (exclude self)
func filterPeers(peers []string, self string) []string {
	filtered := make([]string, 0)
	for _, peer := range peers {
		if peer != self {
			filtered = append(filtered, peer)
		}
	}
	return filtered
}

// SessionFixtures contains factory methods for Claude session test data
type SessionFixtures struct{}

// NewManagerSession creates a manager-tier Claude session
func NewManagerSession(name string) map[string]interface{} {
	return map[string]interface{}{
		"name":              name,
		"tier":              "manager",
		"provider":          "claude",
		"status":            "idle",
		"max_concurrent":    5,
		"current_tasks":     0,
		"health_status":     "healthy",
		"consecutive_fails": 0,
	}
}

// NewWorkerSession creates a worker-tier Claude session
func NewWorkerSession(name string) map[string]interface{} {
	return map[string]interface{}{
		"name":              name,
		"tier":              "worker",
		"provider":          "claude",
		"status":            "idle",
		"max_concurrent":    1,
		"current_tasks":     0,
		"health_status":     "healthy",
		"consecutive_fails": 0,
	}
}

// SessionBatch creates multiple sessions with the specified tier
func SessionBatch(count int, tier string) []map[string]interface{} {
	sessions := make([]map[string]interface{}, 0)
	for i := 0; i < count; i++ {
		name := fmt.Sprintf("%s-session-%d", tier, i+1)
		session := map[string]interface{}{
			"name":              name,
			"tier":              tier,
			"provider":          "claude",
			"status":            "idle",
			"max_concurrent":    1,
			"current_tasks":     0,
			"health_status":     "healthy",
			"consecutive_fails": 0,
		}
		sessions = append(sessions, session)
	}
	return sessions
}
