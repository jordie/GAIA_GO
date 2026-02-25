package cluster

import (
	"context"
	"errors"
	"fmt"
	"log"
	"sync"
	"time"
)

// AgentAssignment represents an agent assigned to a node
type AgentAssignment struct {
	AgentName string
	NodeID    string
	AssignedAt time.Time
	Status    string // running, stopped, failed
}

// ClusterCoordinator manages the entire cluster
type ClusterCoordinator struct {
	// Core components
	registry     *NodeRegistry
	balancer     *LoadBalancer
	localNodeID  string
	isLeader     bool

	// Agent tracking
	assignments map[string]*AgentAssignment
	assignMu    sync.RWMutex

	// Configuration
	heartbeatInterval time.Duration
	healthCheckInterval time.Duration
	leaderElectionTimeout time.Duration

	// State
	ctx      context.Context
	cancel   context.CancelFunc
	wg       sync.WaitGroup
	started  bool
	mu       sync.RWMutex
}

// NewClusterCoordinator creates a new cluster coordinator
func NewClusterCoordinator(
	localNodeID string,
	heartbeatInterval time.Duration,
	healthCheckInterval time.Duration,
) *ClusterCoordinator {
	ctx, cancel := context.WithCancel(context.Background())

	registry := NewNodeRegistry(heartbeatInterval*3, healthCheckInterval)
	balancer := NewLoadBalancer(registry, StrategyLeastLoaded)

	return &ClusterCoordinator{
		registry:              registry,
		balancer:              balancer,
		localNodeID:           localNodeID,
		isLeader:              false,
		assignments:           make(map[string]*AgentAssignment),
		heartbeatInterval:     heartbeatInterval,
		healthCheckInterval:   healthCheckInterval,
		leaderElectionTimeout: heartbeatInterval * 5,
		ctx:                   ctx,
		cancel:                cancel,
		started:               false,
	}
}

// Start starts the cluster coordinator
func (cc *ClusterCoordinator) Start() error {
	cc.mu.Lock()
	defer cc.mu.Unlock()

	if cc.started {
		return errors.New("coordinator already started")
	}

	cc.started = true
	cc.registry.Start()

	// Start background goroutines
	cc.wg.Add(3)
	go cc.healthCheckLoop()
	go cc.leaderElectionLoop()
	go cc.coordinationLoop()

	log.Printf("[Coordinator] Started on node: %s", cc.localNodeID)
	return nil
}

// Stop stops the cluster coordinator
func (cc *ClusterCoordinator) Stop() error {
	cc.mu.Lock()
	defer cc.mu.Unlock()

	if !cc.started {
		return errors.New("coordinator not started")
	}

	cc.started = false
	cc.cancel()
	cc.registry.Stop()

	// Wait for goroutines to finish
	done := make(chan struct{})
	go func() {
		cc.wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		log.Printf("[Coordinator] Stopped gracefully")
	case <-time.After(10 * time.Second):
		log.Printf("[Coordinator] Stop timeout")
	}

	return nil
}

// RegisterNode registers a node with the cluster
func (cc *ClusterCoordinator) RegisterNode(node *Node) error {
	return cc.registry.Register(node)
}

// UnregisterNode removes a node from the cluster
func (cc *ClusterCoordinator) UnregisterNode(nodeID string) error {
	// Reassign agents from this node
	cc.assignMu.Lock()
	orphanedAgents := make([]string, 0)
	for agentName, assignment := range cc.assignments {
		if assignment.NodeID == nodeID {
			orphanedAgents = append(orphanedAgents, agentName)
			delete(cc.assignments, agentName)
		}
	}
	cc.assignMu.Unlock()

	// Log orphaned agents
	if len(orphanedAgents) > 0 {
		log.Printf("[Coordinator] Node %s had %d agents: %v", nodeID, len(orphanedAgents), orphanedAgents)
	}

	return cc.registry.Unregister(nodeID)
}

// AssignAgent assigns an agent to the best available node
func (cc *ClusterCoordinator) AssignAgent(agentName string) (*Node, error) {
	// Check if already assigned
	cc.assignMu.RLock()
	if existing, exists := cc.assignments[agentName]; exists {
		cc.assignMu.RUnlock()
		node, err := cc.registry.Get(existing.NodeID)
		if err == nil {
			return node, nil
		}
		// Assignment stale, remove it
		cc.assignMu.RUnlock()
		cc.assignMu.Lock()
		delete(cc.assignments, agentName)
		cc.assignMu.Unlock()
		cc.assignMu.RLock()
	}
	cc.assignMu.RUnlock()

	// Select best node
	node, err := cc.balancer.SelectNode()
	if err != nil {
		return nil, err
	}

	// Track assignment
	cc.assignMu.Lock()
	cc.assignments[agentName] = &AgentAssignment{
		AgentName:  agentName,
		NodeID:     node.ID,
		AssignedAt: time.Now(),
		Status:     "running",
	}
	cc.assignMu.Unlock()

	// Update node agent count
	node.IncrementAgents()

	log.Printf("[Coordinator] Assigned agent '%s' to node %s", agentName, node.ID)
	return node, nil
}

// UnassignAgent removes an agent assignment
func (cc *ClusterCoordinator) UnassignAgent(agentName string) error {
	cc.assignMu.Lock()
	defer cc.assignMu.Unlock()

	assignment, exists := cc.assignments[agentName]
	if !exists {
		return fmt.Errorf("agent not assigned: %s", agentName)
	}

	// Update node agent count
	node, err := cc.registry.Get(assignment.NodeID)
	if err == nil {
		node.DecrementAgents()
	}

	delete(cc.assignments, agentName)
	log.Printf("[Coordinator] Unassigned agent '%s' from node %s", agentName, assignment.NodeID)
	return nil
}

// GetAssignment returns the node assignment for an agent
func (cc *ClusterCoordinator) GetAssignment(agentName string) (*Node, error) {
	cc.assignMu.RLock()
	assignment, exists := cc.assignments[agentName]
	cc.assignMu.RUnlock()

	if !exists {
		return nil, fmt.Errorf("agent not assigned: %s", agentName)
	}

	return cc.registry.Get(assignment.NodeID)
}

// GetAllAssignments returns all current assignments
func (cc *ClusterCoordinator) GetAllAssignments() map[string]*AgentAssignment {
	cc.assignMu.RLock()
	defer cc.assignMu.RUnlock()

	assignments := make(map[string]*AgentAssignment, len(cc.assignments))
	for k, v := range cc.assignments {
		assignments[k] = v
	}

	return assignments
}

// GetClusterStats returns comprehensive cluster statistics
func (cc *ClusterCoordinator) GetClusterStats() map[string]interface{} {
	cc.assignMu.RLock()
	totalAssignments := len(cc.assignments)
	cc.assignMu.RUnlock()

	registryStats := cc.registry.GetStats()
	balancerStats := cc.balancer.GetStats()

	return map[string]interface{}{
		"local_node":        cc.localNodeID,
		"is_leader":         cc.isLeader,
		"total_assignments": totalAssignments,
		"registry":          registryStats,
		"balancer":          balancerStats,
	}
}

// IsLeader returns whether this node is the cluster leader
func (cc *ClusterCoordinator) IsLeader() bool {
	cc.mu.RLock()
	defer cc.mu.RUnlock()
	return cc.isLeader
}

// PromoteToLeader promotes this node to cluster leader
func (cc *ClusterCoordinator) PromoteToLeader() error {
	cc.mu.Lock()
	cc.isLeader = true
	cc.mu.Unlock()

	err := cc.registry.PromoteToLeader(cc.localNodeID)
	if err != nil {
		cc.mu.Lock()
		cc.isLeader = false
		cc.mu.Unlock()
		return err
	}

	log.Printf("[Coordinator] This node is now the cluster leader")
	return nil
}

// healthCheckLoop periodically checks node health
func (cc *ClusterCoordinator) healthCheckLoop() {
	defer cc.wg.Done()

	ticker := time.NewTicker(cc.healthCheckInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			cc.performHealthChecks()
		case <-cc.ctx.Done():
			return
		}
	}
}

// performHealthChecks checks all nodes for health issues
func (cc *ClusterCoordinator) performHealthChecks() {
	nodes := cc.registry.GetAll()

	for _, node := range nodes {
		// Check if stale
		if node.IsStale(cc.heartbeatInterval * 3) {
			log.Printf("[Coordinator] Node %s is stale (last seen: %s)",
				node.ID, node.LastSeen.Format(time.RFC3339))
		}

		// Check resource usage
		if node.CPUUsage > 90.0 {
			log.Printf("[Coordinator] WARNING: Node %s CPU usage: %.1f%%", node.ID, node.CPUUsage)
		}
		if node.MemoryUsage > 90.0 {
			log.Printf("[Coordinator] WARNING: Node %s memory usage: %.1f%%", node.ID, node.MemoryUsage)
		}
	}
}

// leaderElectionLoop handles leader election
func (cc *ClusterCoordinator) leaderElectionLoop() {
	defer cc.wg.Done()

	ticker := time.NewTicker(cc.leaderElectionTimeout)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			cc.checkLeaderStatus()
		case <-cc.ctx.Done():
			return
		}
	}
}

// checkLeaderStatus checks if there's a leader and elects one if needed
func (cc *ClusterCoordinator) checkLeaderStatus() {
	_, err := cc.registry.GetLeader()

	if err != nil {
		// No leader found, try to become leader
		healthyNodes := cc.registry.GetHealthy()

		if len(healthyNodes) == 0 {
			return
		}

		// Simple election: lowest ID wins
		lowestID := healthyNodes[0].ID
		for _, node := range healthyNodes[1:] {
			if node.ID < lowestID {
				lowestID = node.ID
			}
		}

		if lowestID == cc.localNodeID {
			cc.PromoteToLeader()
		}
	}
}

// coordinationLoop handles cluster coordination tasks (leader only)
func (cc *ClusterCoordinator) coordinationLoop() {
	defer cc.wg.Done()

	ticker := time.NewTicker(cc.heartbeatInterval * 2)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			if cc.IsLeader() {
				cc.coordinateCluster()
			}
		case <-cc.ctx.Done():
			return
		}
	}
}

// coordinateCluster performs leader-only coordination tasks
func (cc *ClusterCoordinator) coordinateCluster() {
	// Check for orphaned agents
	cc.checkOrphanedAgents()

	// Log cluster status
	stats := cc.GetClusterStats()
	log.Printf("[Coordinator] Cluster: %d nodes, %d agents",
		stats["registry"].(map[string]interface{})["total_nodes"],
		stats["total_assignments"])
}

// checkOrphanedAgents finds assignments to offline nodes
func (cc *ClusterCoordinator) checkOrphanedAgents() {
	cc.assignMu.Lock()
	defer cc.assignMu.Unlock()

	orphaned := make([]string, 0)

	for agentName, assignment := range cc.assignments {
		node, err := cc.registry.Get(assignment.NodeID)
		if err != nil || node.Status == NodeStatusOffline {
			orphaned = append(orphaned, agentName)
		}
	}

	if len(orphaned) > 0 {
		log.Printf("[Coordinator] Found %d orphaned agents: %v", len(orphaned), orphaned)
		// TODO: Reassign orphaned agents
	}
}

// GetRegistry returns the node registry
func (cc *ClusterCoordinator) GetRegistry() *NodeRegistry {
	return cc.registry
}

// GetBalancer returns the load balancer
func (cc *ClusterCoordinator) GetBalancer() *LoadBalancer {
	return cc.balancer
}
