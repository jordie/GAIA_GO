package cluster

import (
	"testing"
	"time"
)

// TestNodeCreation tests basic node creation
func TestNodeCreation(t *testing.T) {
	node := NewNode("node-1", "localhost", "127.0.0.1", 8151)

	if node.ID != "node-1" {
		t.Errorf("Expected ID 'node-1', got '%s'", node.ID)
	}

	if node.Status != NodeStatusOnline {
		t.Errorf("Expected status online, got %s", node.Status)
	}

	if node.Role != NodeRoleWorker {
		t.Errorf("Expected role worker, got %s", node.Role)
	}

	if !node.Healthy {
		t.Error("Expected node to be healthy")
	}
}

// TestNodeHeartbeat tests heartbeat updates
func TestNodeHeartbeat(t *testing.T) {
	node := NewNode("node-1", "localhost", "127.0.0.1", 8151)

	originalTime := node.LastSeen
	time.Sleep(10 * time.Millisecond)

	node.UpdateHeartbeat(50.0, 60.0, 70.0, 2.5)

	if node.CPUUsage != 50.0 {
		t.Errorf("Expected CPU 50.0, got %.1f", node.CPUUsage)
	}

	if node.MemoryUsage != 60.0 {
		t.Errorf("Expected memory 60.0, got %.1f", node.MemoryUsage)
	}

	if node.LastSeen.Equal(originalTime) {
		t.Error("Expected LastSeen to be updated")
	}
}

// TestNodeCapacity tests capacity calculation
func TestNodeCapacity(t *testing.T) {
	node := NewNode("node-1", "localhost", "127.0.0.1", 8151)
	node.MaxAgents = 10
	node.ActiveAgents = 3

	capacity := node.GetCapacity()
	expected := 0.7 // 7 available out of 10

	if capacity != expected {
		t.Errorf("Expected capacity %.1f, got %.1f", expected, capacity)
	}
}

// TestNodeLoadCalculation tests load score calculation
func TestNodeLoadCalculation(t *testing.T) {
	node := NewNode("node-1", "localhost", "127.0.0.1", 8151)
	node.MaxAgents = 10
	node.ActiveAgents = 5
	node.CPUUsage = 50.0
	node.MemoryUsage = 60.0

	load := node.GetLoad()

	// Expected: (50 * 0.4) + (60 * 0.3) + (50 * 0.3) = 20 + 18 + 15 = 53
	expected := 53.0

	if load != expected {
		t.Errorf("Expected load %.1f, got %.1f", expected, load)
	}
}

// TestNodeRegistry tests node registry operations
func TestNodeRegistry(t *testing.T) {
	registry := NewNodeRegistry(30*time.Second, 60*time.Second)

	// Register nodes
	node1 := NewNode("node-1", "host1", "10.0.0.1", 8151)
	node2 := NewNode("node-2", "host2", "10.0.0.2", 8151)

	if err := registry.Register(node1); err != nil {
		t.Fatalf("Failed to register node1: %v", err)
	}

	if err := registry.Register(node2); err != nil {
		t.Fatalf("Failed to register node2: %v", err)
	}

	// Test duplicate registration
	if err := registry.Register(node1); err != ErrNodeAlreadyExists {
		t.Error("Expected ErrNodeAlreadyExists for duplicate")
	}

	// Test GetAll
	nodes := registry.GetAll()
	if len(nodes) != 2 {
		t.Errorf("Expected 2 nodes, got %d", len(nodes))
	}

	// Test Get
	retrievedNode, err := registry.Get("node-1")
	if err != nil {
		t.Fatalf("Failed to get node: %v", err)
	}

	if retrievedNode.ID != "node-1" {
		t.Errorf("Expected node-1, got %s", retrievedNode.ID)
	}

	// Test Unregister
	if err := registry.Unregister("node-1"); err != nil {
		t.Fatalf("Failed to unregister: %v", err)
	}

	nodes = registry.GetAll()
	if len(nodes) != 1 {
		t.Errorf("Expected 1 node after unregister, got %d", len(nodes))
	}
}

// TestNodeRegistryHealthy tests filtering healthy nodes
func TestNodeRegistryHealthy(t *testing.T) {
	registry := NewNodeRegistry(30*time.Second, 60*time.Second)

	node1 := NewNode("node-1", "host1", "10.0.0.1", 8151)
	node2 := NewNode("node-2", "host2", "10.0.0.2", 8151)
	node2.MarkUnhealthy("test failure")

	registry.Register(node1)
	registry.Register(node2)

	healthy := registry.GetHealthy()
	if len(healthy) != 1 {
		t.Errorf("Expected 1 healthy node, got %d", len(healthy))
	}

	if healthy[0].ID != "node-1" {
		t.Errorf("Expected node-1, got %s", healthy[0].ID)
	}
}

// TestNodeRegistryAvailable tests filtering available nodes
func TestNodeRegistryAvailable(t *testing.T) {
	registry := NewNodeRegistry(30*time.Second, 60*time.Second)

	node1 := NewNode("node-1", "host1", "10.0.0.1", 8151)
	node1.MaxAgents = 10
	node1.ActiveAgents = 5

	node2 := NewNode("node-2", "host2", "10.0.0.2", 8151)
	node2.MaxAgents = 10
	node2.ActiveAgents = 10 // Full

	registry.Register(node1)
	registry.Register(node2)

	available := registry.GetAvailable()
	if len(available) != 1 {
		t.Errorf("Expected 1 available node, got %d", len(available))
	}

	if available[0].ID != "node-1" {
		t.Errorf("Expected node-1, got %s", available[0].ID)
	}
}

// TestLoadBalancerLeastLoaded tests least loaded strategy
func TestLoadBalancerLeastLoaded(t *testing.T) {
	registry := NewNodeRegistry(30*time.Second, 60*time.Second)
	balancer := NewLoadBalancer(registry, StrategyLeastLoaded)

	node1 := NewNode("node-1", "host1", "10.0.0.1", 8151)
	node1.MaxAgents = 10
	node1.ActiveAgents = 5
	node1.CPUUsage = 50.0
	node1.MemoryUsage = 60.0

	node2 := NewNode("node-2", "host2", "10.0.0.2", 8151)
	node2.MaxAgents = 10
	node2.ActiveAgents = 2
	node2.CPUUsage = 20.0
	node2.MemoryUsage = 30.0

	registry.Register(node1)
	registry.Register(node2)

	selected, err := balancer.SelectNode()
	if err != nil {
		t.Fatalf("Failed to select node: %v", err)
	}

	// node2 has lower load
	if selected.ID != "node-2" {
		t.Errorf("Expected node-2 (lower load), got %s", selected.ID)
	}
}

// TestLoadBalancerRoundRobin tests round-robin strategy
func TestLoadBalancerRoundRobin(t *testing.T) {
	registry := NewNodeRegistry(30*time.Second, 60*time.Second)
	balancer := NewLoadBalancer(registry, StrategyRoundRobin)

	node1 := NewNode("node-1", "host1", "10.0.0.1", 8151)
	node1.MaxAgents = 10

	node2 := NewNode("node-2", "host2", "10.0.0.2", 8151)
	node2.MaxAgents = 10

	registry.Register(node1)
	registry.Register(node2)

	// Select twice to test round-robin
	first, _ := balancer.SelectNode()
	second, _ := balancer.SelectNode()

	// Should alternate between nodes
	if first.ID == second.ID {
		t.Error("Round-robin should alternate nodes")
	}

	third, _ := balancer.SelectNode()
	if third.ID != first.ID {
		t.Error("Third selection should match first (round-robin cycle)")
	}
}

// TestClusterCoordinator tests basic coordinator operations
func TestClusterCoordinator(t *testing.T) {
	coordinator := NewClusterCoordinator(
		"local-node",
		30*time.Second,
		60*time.Second,
	)

	// Register nodes
	node1 := NewNode("node-1", "host1", "10.0.0.1", 8151)
	node1.MaxAgents = 10

	node2 := NewNode("node-2", "host2", "10.0.0.2", 8151)
	node2.MaxAgents = 10

	coordinator.RegisterNode(node1)
	coordinator.RegisterNode(node2)

	// Assign agent
	assignedNode, err := coordinator.AssignAgent("test-agent")
	if err != nil {
		t.Fatalf("Failed to assign agent: %v", err)
	}

	if assignedNode == nil {
		t.Fatal("Expected assigned node")
	}

	// Verify assignment
	assignment, err := coordinator.GetAssignment("test-agent")
	if err != nil {
		t.Fatalf("Failed to get assignment: %v", err)
	}

	if assignment.ID != assignedNode.ID {
		t.Errorf("Expected assignment to %s, got %s", assignedNode.ID, assignment.ID)
	}

	// Verify agent count
	if assignedNode.ActiveAgents != 1 {
		t.Errorf("Expected 1 active agent, got %d", assignedNode.ActiveAgents)
	}

	// Unassign agent
	if err := coordinator.UnassignAgent("test-agent"); err != nil {
		t.Fatalf("Failed to unassign: %v", err)
	}

	// Verify agent count decreased
	if assignedNode.ActiveAgents != 0 {
		t.Errorf("Expected 0 active agents after unassign, got %d", assignedNode.ActiveAgents)
	}
}

// TestClusterStats tests cluster statistics
func TestClusterStats(t *testing.T) {
	registry := NewNodeRegistry(30*time.Second, 60*time.Second)

	node1 := NewNode("node-1", "host1", "10.0.0.1", 8151)
	node1.MaxAgents = 10
	node1.ActiveAgents = 5

	node2 := NewNode("node-2", "host2", "10.0.0.2", 8151)
	node2.MaxAgents = 10
	node2.ActiveAgents = 3
	node2.SetStatus(NodeStatusOffline)

	registry.Register(node1)
	registry.Register(node2)

	stats := registry.GetStats()

	totalNodes := stats["total_nodes"].(int)
	if totalNodes != 2 {
		t.Errorf("Expected 2 total nodes, got %d", totalNodes)
	}

	onlineNodes := stats["online_nodes"].(int)
	if onlineNodes != 1 {
		t.Errorf("Expected 1 online node, got %d", onlineNodes)
	}

	totalAgents := stats["total_agents"].(int)
	if totalAgents != 8 {
		t.Errorf("Expected 8 total agents, got %d", totalAgents)
	}
}

// TestLeaderElection tests leader promotion
func TestLeaderElection(t *testing.T) {
	registry := NewNodeRegistry(30*time.Second, 60*time.Second)

	node1 := NewNode("node-1", "host1", "10.0.0.1", 8151)
	node2 := NewNode("node-2", "host2", "10.0.0.2", 8151)

	registry.Register(node1)
	registry.Register(node2)

	// Promote node1 to leader
	if err := registry.PromoteToLeader("node-1"); err != nil {
		t.Fatalf("Failed to promote leader: %v", err)
	}

	leader, err := registry.GetLeader()
	if err != nil {
		t.Fatalf("Failed to get leader: %v", err)
	}

	if leader.ID != "node-1" {
		t.Errorf("Expected leader node-1, got %s", leader.ID)
	}

	// Promote node2 (should demote node1)
	if err := registry.PromoteToLeader("node-2"); err != nil {
		t.Fatalf("Failed to promote new leader: %v", err)
	}

	leader, err = registry.GetLeader()
	if err != nil {
		t.Fatalf("Failed to get new leader: %v", err)
	}

	if leader.ID != "node-2" {
		t.Errorf("Expected new leader node-2, got %s", leader.ID)
	}

	if node1.Role != NodeRoleWorker {
		t.Error("Expected old leader to be demoted to worker")
	}
}
