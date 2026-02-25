package cluster

import (
	"errors"
	"log"
	"math/rand"
	"sync"
	"time"
)

// LoadBalancingStrategy defines how work is distributed across nodes
type LoadBalancingStrategy string

const (
	StrategyRoundRobin   LoadBalancingStrategy = "round_robin"
	StrategyLeastLoaded  LoadBalancingStrategy = "least_loaded"
	StrategyLeastAgents  LoadBalancingStrategy = "least_agents"
	StrategyRandom       LoadBalancingStrategy = "random"
	StrategyWeighted     LoadBalancingStrategy = "weighted"
)

// LoadBalancer distributes work across cluster nodes
type LoadBalancer struct {
	registry  *NodeRegistry
	strategy  LoadBalancingStrategy
	rrIndex   int
	mu        sync.Mutex
}

// NewLoadBalancer creates a new load balancer
func NewLoadBalancer(registry *NodeRegistry, strategy LoadBalancingStrategy) *LoadBalancer {
	return &LoadBalancer{
		registry: registry,
		strategy: strategy,
		rrIndex:  0,
	}
}

// SelectNode selects the best node for new work
func (lb *LoadBalancer) SelectNode() (*Node, error) {
	switch lb.strategy {
	case StrategyRoundRobin:
		return lb.selectRoundRobin()
	case StrategyLeastLoaded:
		return lb.selectLeastLoaded()
	case StrategyLeastAgents:
		return lb.selectLeastAgents()
	case StrategyRandom:
		return lb.selectRandom()
	case StrategyWeighted:
		return lb.selectWeighted()
	default:
		return lb.selectLeastLoaded()
	}
}

// SelectNodes selects multiple nodes for distributed work
func (lb *LoadBalancer) SelectNodes(count int) ([]*Node, error) {
	nodes := make([]*Node, 0, count)

	for i := 0; i < count; i++ {
		node, err := lb.SelectNode()
		if err != nil {
			return nodes, err
		}
		nodes = append(nodes, node)
	}

	return nodes, nil
}

// SelectNodeWithService selects a node that provides a specific service
func (lb *LoadBalancer) SelectNodeWithService(service string) (*Node, error) {
	available := lb.registry.GetByService(service)

	if len(available) == 0 {
		return nil, errors.New("no nodes with service: " + service)
	}

	// Filter for availability
	filtered := make([]*Node, 0)
	for _, node := range available {
		if node.IsAvailable() {
			filtered = append(filtered, node)
		}
	}

	if len(filtered) == 0 {
		return nil, ErrNoAvailableNodes
	}

	// Use current strategy to pick from filtered list
	return lb.selectFromList(filtered)
}

// selectRoundRobin selects nodes in round-robin fashion
func (lb *LoadBalancer) selectRoundRobin() (*Node, error) {
	lb.mu.Lock()
	defer lb.mu.Unlock()

	available := lb.registry.GetAvailable()
	if len(available) == 0 {
		return nil, ErrNoAvailableNodes
	}

	node := available[lb.rrIndex % len(available)]
	lb.rrIndex++

	log.Printf("[LoadBalancer] Round-robin selected: %s (load: %.1f)", node.ID, node.GetLoad())
	return node, nil
}

// selectLeastLoaded selects the node with the lowest load
func (lb *LoadBalancer) selectLeastLoaded() (*Node, error) {
	available := lb.registry.GetAvailable()
	if len(available) == 0 {
		return nil, ErrNoAvailableNodes
	}

	bestNode := available[0]
	bestLoad := bestNode.GetLoad()

	for _, node := range available[1:] {
		load := node.GetLoad()
		if load < bestLoad {
			bestNode = node
			bestLoad = load
		}
	}

	log.Printf("[LoadBalancer] Least loaded selected: %s (load: %.1f)", bestNode.ID, bestLoad)
	return bestNode, nil
}

// selectLeastAgents selects the node with the fewest active agents
func (lb *LoadBalancer) selectLeastAgents() (*Node, error) {
	available := lb.registry.GetAvailable()
	if len(available) == 0 {
		return nil, ErrNoAvailableNodes
	}

	bestNode := available[0]
	bestCount := bestNode.ActiveAgents

	for _, node := range available[1:] {
		if node.ActiveAgents < bestCount {
			bestNode = node
			bestCount = node.ActiveAgents
		}
	}

	log.Printf("[LoadBalancer] Least agents selected: %s (agents: %d/%d)",
		bestNode.ID, bestNode.ActiveAgents, bestNode.MaxAgents)
	return bestNode, nil
}

// selectRandom selects a random available node
func (lb *LoadBalancer) selectRandom() (*Node, error) {
	available := lb.registry.GetAvailable()
	if len(available) == 0 {
		return nil, ErrNoAvailableNodes
	}

	rand.Seed(time.Now().UnixNano())
	node := available[rand.Intn(len(available))]

	log.Printf("[LoadBalancer] Random selected: %s", node.ID)
	return node, nil
}

// selectWeighted selects based on available capacity (weighted random)
func (lb *LoadBalancer) selectWeighted() (*Node, error) {
	available := lb.registry.GetAvailable()
	if len(available) == 0 {
		return nil, ErrNoAvailableNodes
	}

	// Calculate total weight (based on capacity)
	totalWeight := 0.0
	weights := make([]float64, len(available))

	for i, node := range available {
		weight := node.GetCapacity() * 100.0 // Scale to percentage
		weights[i] = weight
		totalWeight += weight
	}

	if totalWeight == 0 {
		// Fallback to round-robin if all weights are zero
		return lb.selectRoundRobin()
	}

	// Select based on weighted probability
	rand.Seed(time.Now().UnixNano())
	r := rand.Float64() * totalWeight
	cumulative := 0.0

	for i, weight := range weights {
		cumulative += weight
		if r <= cumulative {
			node := available[i]
			log.Printf("[LoadBalancer] Weighted selected: %s (capacity: %.1f%%)",
				node.ID, node.GetCapacity()*100)
			return node, nil
		}
	}

	// Fallback (shouldn't reach here)
	return available[len(available)-1], nil
}

// selectFromList selects from a pre-filtered list using current strategy
func (lb *LoadBalancer) selectFromList(nodes []*Node) (*Node, error) {
	if len(nodes) == 0 {
		return nil, ErrNoAvailableNodes
	}

	switch lb.strategy {
	case StrategyLeastLoaded:
		bestNode := nodes[0]
		bestLoad := bestNode.GetLoad()
		for _, node := range nodes[1:] {
			load := node.GetLoad()
			if load < bestLoad {
				bestNode = node
				bestLoad = load
			}
		}
		return bestNode, nil

	case StrategyLeastAgents:
		bestNode := nodes[0]
		bestCount := bestNode.ActiveAgents
		for _, node := range nodes[1:] {
			if node.ActiveAgents < bestCount {
				bestNode = node
				bestCount = node.ActiveAgents
			}
		}
		return bestNode, nil

	case StrategyRandom:
		rand.Seed(time.Now().UnixNano())
		return nodes[rand.Intn(len(nodes))], nil

	default:
		// Round-robin for filtered list
		lb.mu.Lock()
		node := nodes[lb.rrIndex % len(nodes)]
		lb.rrIndex++
		lb.mu.Unlock()
		return node, nil
	}
}

// SetStrategy changes the load balancing strategy
func (lb *LoadBalancer) SetStrategy(strategy LoadBalancingStrategy) {
	lb.mu.Lock()
	defer lb.mu.Unlock()

	lb.strategy = strategy
	log.Printf("[LoadBalancer] Strategy changed to: %s", strategy)
}

// GetStats returns load balancer statistics
func (lb *LoadBalancer) GetStats() map[string]interface{} {
	return map[string]interface{}{
		"strategy":          string(lb.strategy),
		"round_robin_index": lb.rrIndex,
		"registry_stats":    lb.registry.GetStats(),
	}
}

// Rebalance redistributes agents across nodes (future enhancement)
func (lb *LoadBalancer) Rebalance() error {
	// TODO: Implement agent migration for rebalancing
	// This would move agents from overloaded nodes to underutilized ones
	log.Printf("[LoadBalancer] Rebalancing not yet implemented")
	return errors.New("rebalancing not implemented")
}
