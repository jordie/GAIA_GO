package cluster

import (
	"fmt"
	"sync"
	"time"
)

// NodeStatus represents the current state of a cluster node
type NodeStatus string

const (
	NodeStatusOnline  NodeStatus = "online"
	NodeStatusOffline NodeStatus = "offline"
	NodeStatusDraining NodeStatus = "draining" // Not accepting new work
	NodeStatusUnknown NodeStatus = "unknown"
)

// NodeRole defines the role of a node in the cluster
type NodeRole string

const (
	NodeRoleLeader   NodeRole = "leader"   // Cluster coordinator
	NodeRoleWorker   NodeRole = "worker"   // Standard worker node
	NodeRoleReplica  NodeRole = "replica"  // Read-only replica
	NodeRoleStandby  NodeRole = "standby"  // Hot standby for failover
)

// Node represents a single node in the cluster
type Node struct {
	// Identity
	ID       string   `json:"id"`
	Hostname string   `json:"hostname"`
	IPAddress string  `json:"ip_address"`
	Port     int      `json:"port"`
	Role     NodeRole `json:"role"`

	// Status
	Status       NodeStatus `json:"status"`
	LastSeen     time.Time  `json:"last_seen"`
	StartedAt    time.Time  `json:"started_at"`
	Version      string     `json:"version"`

	// Capabilities
	MaxAgents    int      `json:"max_agents"`
	ActiveAgents int      `json:"active_agents"`
	Services     []string `json:"services"` // e.g., ["wrapper", "database", "streaming"]

	// Resources
	CPUUsage    float64 `json:"cpu_usage"`
	MemoryUsage float64 `json:"memory_usage"`
	DiskUsage   float64 `json:"disk_usage"`
	LoadAverage float64 `json:"load_average"`

	// Health
	Healthy       bool   `json:"healthy"`
	HealthMessage string `json:"health_message,omitempty"`
	FailureCount  int    `json:"failure_count"`

	// Metadata
	Tags     map[string]string `json:"tags,omitempty"`
	Metadata map[string]interface{} `json:"metadata,omitempty"`

	mu sync.RWMutex
}

// NewNode creates a new cluster node
func NewNode(id, hostname, ipAddress string, port int) *Node {
	return &Node{
		ID:        id,
		Hostname:  hostname,
		IPAddress: ipAddress,
		Port:      port,
		Role:      NodeRoleWorker,
		Status:    NodeStatusOnline,
		StartedAt: time.Now(),
		LastSeen:  time.Now(),
		Healthy:   true,
		Services:  []string{},
		Tags:      make(map[string]string),
		Metadata:  make(map[string]interface{}),
	}
}

// UpdateHeartbeat updates the last seen timestamp and metrics
func (n *Node) UpdateHeartbeat(cpu, memory, disk, load float64) {
	n.mu.Lock()
	defer n.mu.Unlock()

	n.LastSeen = time.Now()
	n.CPUUsage = cpu
	n.MemoryUsage = memory
	n.DiskUsage = disk
	n.LoadAverage = load

	// Auto-heal if node was unhealthy
	if !n.Healthy && n.FailureCount > 0 {
		n.FailureCount--
		if n.FailureCount == 0 {
			n.Healthy = true
			n.HealthMessage = ""
		}
	}
}

// MarkUnhealthy marks the node as unhealthy with a reason
func (n *Node) MarkUnhealthy(reason string) {
	n.mu.Lock()
	defer n.mu.Unlock()

	n.Healthy = false
	n.HealthMessage = reason
	n.FailureCount++
}

// IsAvailable checks if the node can accept new work
func (n *Node) IsAvailable() bool {
	n.mu.RLock()
	defer n.mu.RUnlock()

	return n.Status == NodeStatusOnline &&
	       n.Healthy &&
	       n.ActiveAgents < n.MaxAgents
}

// GetCapacity returns the remaining capacity (0.0 to 1.0)
func (n *Node) GetCapacity() float64 {
	n.mu.RLock()
	defer n.mu.RUnlock()

	if n.MaxAgents == 0 {
		return 0.0
	}

	return float64(n.MaxAgents - n.ActiveAgents) / float64(n.MaxAgents)
}

// GetLoad returns the current load score (lower is better)
func (n *Node) GetLoad() float64 {
	n.mu.RLock()
	defer n.mu.RUnlock()

	// Weighted load: CPU (40%) + Memory (30%) + Agents (30%)
	agentLoad := 0.0
	if n.MaxAgents > 0 {
		agentLoad = float64(n.ActiveAgents) / float64(n.MaxAgents) * 100.0
	}

	return (n.CPUUsage * 0.4) + (n.MemoryUsage * 0.3) + (agentLoad * 0.3)
}

// IncrementAgents increments the active agent count
func (n *Node) IncrementAgents() {
	n.mu.Lock()
	defer n.mu.Unlock()
	n.ActiveAgents++
}

// DecrementAgents decrements the active agent count
func (n *Node) DecrementAgents() {
	n.mu.Lock()
	defer n.mu.Unlock()
	if n.ActiveAgents > 0 {
		n.ActiveAgents--
	}
}

// SetRole changes the node's role
func (n *Node) SetRole(role NodeRole) {
	n.mu.Lock()
	defer n.mu.Unlock()
	n.Role = role
}

// SetStatus changes the node's status
func (n *Node) SetStatus(status NodeStatus) {
	n.mu.Lock()
	defer n.mu.Unlock()
	n.Status = status
}

// IsStale checks if the node hasn't sent a heartbeat recently
func (n *Node) IsStale(timeout time.Duration) bool {
	n.mu.RLock()
	defer n.mu.RUnlock()

	return time.Since(n.LastSeen) > timeout
}

// GetAddress returns the node's network address
func (n *Node) GetAddress() string {
	n.mu.RLock()
	defer n.mu.RUnlock()

	return fmt.Sprintf("%s:%d", n.IPAddress, n.Port)
}

// HasService checks if the node provides a specific service
func (n *Node) HasService(service string) bool {
	n.mu.RLock()
	defer n.mu.RUnlock()

	for _, s := range n.Services {
		if s == service {
			return true
		}
	}
	return false
}

// AddService adds a service to the node
func (n *Node) AddService(service string) {
	n.mu.Lock()
	defer n.mu.Unlock()

	// Check if already exists
	for _, s := range n.Services {
		if s == service {
			return
		}
	}

	n.Services = append(n.Services, service)
}

// GetInfo returns a summary of node information
func (n *Node) GetInfo() map[string]interface{} {
	n.mu.RLock()
	defer n.mu.RUnlock()

	return map[string]interface{}{
		"id":            n.ID,
		"hostname":      n.Hostname,
		"address":       fmt.Sprintf("%s:%d", n.IPAddress, n.Port),
		"role":          string(n.Role),
		"status":        string(n.Status),
		"healthy":       n.Healthy,
		"active_agents": n.ActiveAgents,
		"max_agents":    n.MaxAgents,
		"capacity":      n.GetCapacity(),
		"load":          n.GetLoad(),
		"cpu_usage":     n.CPUUsage,
		"memory_usage":  n.MemoryUsage,
		"uptime":        time.Since(n.StartedAt).String(),
		"last_seen":     n.LastSeen.Format(time.RFC3339),
	}
}
