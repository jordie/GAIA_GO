package cluster

import (
	"errors"
	"fmt"
	"log"
	"sync"
	"time"
)

var (
	ErrNodeNotFound      = errors.New("node not found")
	ErrNodeAlreadyExists = errors.New("node already exists")
	ErrNoAvailableNodes  = errors.New("no available nodes")
)

// NodeRegistry manages the cluster's node membership
type NodeRegistry struct {
	nodes            map[string]*Node
	mu               sync.RWMutex
	heartbeatTimeout time.Duration
	cleanupInterval  time.Duration
	stopChan         chan struct{}
}

// NewNodeRegistry creates a new node registry
func NewNodeRegistry(heartbeatTimeout, cleanupInterval time.Duration) *NodeRegistry {
	return &NodeRegistry{
		nodes:            make(map[string]*Node),
		heartbeatTimeout: heartbeatTimeout,
		cleanupInterval:  cleanupInterval,
		stopChan:         make(chan struct{}),
	}
}

// Start begins the background cleanup goroutine
func (r *NodeRegistry) Start() {
	go r.cleanupLoop()
}

// Stop stops the background cleanup goroutine
func (r *NodeRegistry) Stop() {
	close(r.stopChan)
}

// Register adds a new node to the registry
func (r *NodeRegistry) Register(node *Node) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.nodes[node.ID]; exists {
		return ErrNodeAlreadyExists
	}

	r.nodes[node.ID] = node
	log.Printf("[Registry] Node registered: %s (%s)", node.ID, node.GetAddress())
	return nil
}

// Unregister removes a node from the registry
func (r *NodeRegistry) Unregister(nodeID string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	node, exists := r.nodes[nodeID]
	if !exists {
		return ErrNodeNotFound
	}

	delete(r.nodes, nodeID)
	log.Printf("[Registry] Node unregistered: %s (%s)", node.ID, node.GetAddress())
	return nil
}

// Get retrieves a node by ID
func (r *NodeRegistry) Get(nodeID string) (*Node, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	node, exists := r.nodes[nodeID]
	if !exists {
		return nil, ErrNodeNotFound
	}

	return node, nil
}

// GetAll returns all registered nodes
func (r *NodeRegistry) GetAll() []*Node {
	r.mu.RLock()
	defer r.mu.RUnlock()

	nodes := make([]*Node, 0, len(r.nodes))
	for _, node := range r.nodes {
		nodes = append(nodes, node)
	}

	return nodes
}

// GetHealthy returns all healthy nodes
func (r *NodeRegistry) GetHealthy() []*Node {
	r.mu.RLock()
	defer r.mu.RUnlock()

	nodes := make([]*Node, 0)
	for _, node := range r.nodes {
		if node.Healthy && node.Status == NodeStatusOnline {
			nodes = append(nodes, node)
		}
	}

	return nodes
}

// GetAvailable returns all nodes that can accept new work
func (r *NodeRegistry) GetAvailable() []*Node {
	r.mu.RLock()
	defer r.mu.RUnlock()

	nodes := make([]*Node, 0)
	for _, node := range r.nodes {
		if node.IsAvailable() {
			nodes = append(nodes, node)
		}
	}

	return nodes
}

// GetByRole returns all nodes with a specific role
func (r *NodeRegistry) GetByRole(role NodeRole) []*Node {
	r.mu.RLock()
	defer r.mu.RUnlock()

	nodes := make([]*Node, 0)
	for _, node := range r.nodes {
		if node.Role == role {
			nodes = append(nodes, node)
		}
	}

	return nodes
}

// GetByService returns all nodes that provide a specific service
func (r *NodeRegistry) GetByService(service string) []*Node {
	r.mu.RLock()
	defer r.mu.RUnlock()

	nodes := make([]*Node, 0)
	for _, node := range r.nodes {
		if node.HasService(service) {
			nodes = append(nodes, node)
		}
	}

	return nodes
}

// GetLeader returns the current leader node (if any)
func (r *NodeRegistry) GetLeader() (*Node, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	for _, node := range r.nodes {
		if node.Role == NodeRoleLeader && node.Healthy {
			return node, nil
		}
	}

	return nil, errors.New("no leader node found")
}

// PromoteToLeader promotes a node to leader role
func (r *NodeRegistry) PromoteToLeader(nodeID string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	// Demote current leader
	for _, node := range r.nodes {
		if node.Role == NodeRoleLeader {
			node.SetRole(NodeRoleWorker)
			log.Printf("[Registry] Node demoted from leader: %s", node.ID)
		}
	}

	// Promote new leader
	node, exists := r.nodes[nodeID]
	if !exists {
		return ErrNodeNotFound
	}

	node.SetRole(NodeRoleLeader)
	log.Printf("[Registry] Node promoted to leader: %s", nodeID)
	return nil
}

// UpdateHeartbeat updates a node's heartbeat
func (r *NodeRegistry) UpdateHeartbeat(nodeID string, cpu, memory, disk, load float64) error {
	r.mu.RLock()
	node, exists := r.nodes[nodeID]
	r.mu.RUnlock()

	if !exists {
		return ErrNodeNotFound
	}

	node.UpdateHeartbeat(cpu, memory, disk, load)
	return nil
}

// MarkUnhealthy marks a node as unhealthy
func (r *NodeRegistry) MarkUnhealthy(nodeID string, reason string) error {
	r.mu.RLock()
	node, exists := r.nodes[nodeID]
	r.mu.RUnlock()

	if !exists {
		return ErrNodeNotFound
	}

	node.MarkUnhealthy(reason)
	log.Printf("[Registry] Node marked unhealthy: %s - %s", nodeID, reason)
	return nil
}

// GetStats returns cluster-wide statistics
func (r *NodeRegistry) GetStats() map[string]interface{} {
	r.mu.RLock()
	defer r.mu.RUnlock()

	totalNodes := len(r.nodes)
	healthyNodes := 0
	onlineNodes := 0
	totalAgents := 0
	maxAgents := 0

	nodesByRole := make(map[string]int)
	nodesByStatus := make(map[string]int)

	for _, node := range r.nodes {
		if node.Healthy {
			healthyNodes++
		}
		if node.Status == NodeStatusOnline {
			onlineNodes++
		}

		totalAgents += node.ActiveAgents
		maxAgents += node.MaxAgents

		nodesByRole[string(node.Role)]++
		nodesByStatus[string(node.Status)]++
	}

	utilizationPct := 0.0
	if maxAgents > 0 {
		utilizationPct = float64(totalAgents) / float64(maxAgents) * 100.0
	}

	return map[string]interface{}{
		"total_nodes":      totalNodes,
		"healthy_nodes":    healthyNodes,
		"online_nodes":     onlineNodes,
		"total_agents":     totalAgents,
		"max_agents":       maxAgents,
		"utilization_pct":  utilizationPct,
		"nodes_by_role":    nodesByRole,
		"nodes_by_status":  nodesByStatus,
	}
}

// cleanupLoop periodically checks for stale nodes
func (r *NodeRegistry) cleanupLoop() {
	ticker := time.NewTicker(r.cleanupInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			r.cleanupStaleNodes()
		case <-r.stopChan:
			return
		}
	}
}

// cleanupStaleNodes marks stale nodes as unhealthy or offline
func (r *NodeRegistry) cleanupStaleNodes() {
	r.mu.RLock()
	staleNodes := make([]*Node, 0)

	for _, node := range r.nodes {
		if node.IsStale(r.heartbeatTimeout) {
			staleNodes = append(staleNodes, node)
		}
	}
	r.mu.RUnlock()

	for _, node := range staleNodes {
		staleDuration := time.Since(node.LastSeen)

		// If stale for 2x timeout, mark offline
		if staleDuration > r.heartbeatTimeout*2 {
			node.SetStatus(NodeStatusOffline)
			log.Printf("[Registry] Node marked offline (stale %s): %s", staleDuration, node.ID)
		} else {
			// If stale for 1x timeout, mark unhealthy
			node.MarkUnhealthy(fmt.Sprintf("No heartbeat for %s", staleDuration))
		}
	}
}

// FindBestNode finds the best available node based on load
func (r *NodeRegistry) FindBestNode() (*Node, error) {
	available := r.GetAvailable()

	if len(available) == 0 {
		return nil, ErrNoAvailableNodes
	}

	// Find node with lowest load
	bestNode := available[0]
	bestLoad := bestNode.GetLoad()

	for _, node := range available[1:] {
		load := node.GetLoad()
		if load < bestLoad {
			bestNode = node
			bestLoad = load
		}
	}

	return bestNode, nil
}

// FindNodeWithCapacity finds a node with at least the specified capacity
func (r *NodeRegistry) FindNodeWithCapacity(minCapacity float64) (*Node, error) {
	available := r.GetAvailable()

	for _, node := range available {
		if node.GetCapacity() >= minCapacity {
			return node, nil
		}
	}

	return nil, ErrNoAvailableNodes
}

// DistributeWork distributes work across available nodes (round-robin)
func (r *NodeRegistry) DistributeWork(count int) ([]*Node, error) {
	available := r.GetAvailable()

	if len(available) == 0 {
		return nil, ErrNoAvailableNodes
	}

	nodes := make([]*Node, 0, count)
	for i := 0; i < count; i++ {
		node := available[i % len(available)]
		nodes = append(nodes, node)
	}

	return nodes, nil
}
