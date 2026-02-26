package discovery

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"time"
)

// DiscoveryType defines the type of discovery mechanism
type DiscoveryType string

const (
	DiscoveryTypeStatic   DiscoveryType = "static"
	DiscoveryTypeDNS      DiscoveryType = "dns"
	DiscoveryTypeConsul   DiscoveryType = "consul"
	DiscoveryTypeKubernetes DiscoveryType = "kubernetes"
)

// NodeAddress represents a discovered node's address
type NodeAddress struct {
	ID       string
	Hostname string
	Port     int
	RaftPort int
}

// String returns the full address in "hostname:port" format
func (na *NodeAddress) String() string {
	return fmt.Sprintf("%s:%d", na.Hostname, na.RaftPort)
}

// Discovery interface for different discovery mechanisms
type Discovery interface {
	// Discover returns a list of known nodes
	Discover(ctx context.Context) ([]NodeAddress, error)

	// Watch returns a channel that receives updated node lists
	// Implementations should periodically check and send updates when nodes change
	Watch(ctx context.Context) (<-chan []NodeAddress, error)

	// Register registers this node in the discovery service
	Register(ctx context.Context, node NodeAddress) error

	// Deregister removes this node from the discovery service
	Deregister(ctx context.Context, nodeID string) error
}

// ==============================================================================
// StaticDiscovery - for static node lists (development/simple deployments)
// ==============================================================================

type StaticDiscovery struct {
	nodes []NodeAddress
	mu    sync.RWMutex
}

// NewStaticDiscovery creates a new static discovery with predefined nodes
func NewStaticDiscovery(nodes []NodeAddress) *StaticDiscovery {
	return &StaticDiscovery{
		nodes: nodes,
	}
}

// NewStaticDiscoveryFromString parses a comma-separated list of "hostname:port" addresses
func NewStaticDiscoveryFromString(nodeList string) (*StaticDiscovery, error) {
	if nodeList == "" {
		return &StaticDiscovery{nodes: []NodeAddress{}}, nil
	}

	var nodes []NodeAddress
	for i, nodeStr := range strings.Split(nodeList, ",") {
		parts := strings.Split(strings.TrimSpace(nodeStr), ":")
		if len(parts) != 2 {
			return nil, fmt.Errorf("invalid node format: %s (expected hostname:port)", nodeStr)
		}

		var port int
		fmt.Sscanf(parts[1], "%d", &port)

		nodes = append(nodes, NodeAddress{
			ID:       fmt.Sprintf("node-%d", i),
			Hostname: parts[0],
			RaftPort: port,
		})
	}

	return NewStaticDiscovery(nodes), nil
}

// Discover returns the static list of nodes
func (sd *StaticDiscovery) Discover(ctx context.Context) ([]NodeAddress, error) {
	sd.mu.RLock()
	defer sd.mu.RUnlock()

	result := make([]NodeAddress, len(sd.nodes))
	copy(result, sd.nodes)
	return result, nil
}

// Watch returns a channel that never updates (nodes are static)
func (sd *StaticDiscovery) Watch(ctx context.Context) (<-chan []NodeAddress, error) {
	ch := make(chan []NodeAddress)

	go func() {
		defer close(ch)
		// Send initial list
		nodes, _ := sd.Discover(ctx)
		select {
		case ch <- nodes:
		case <-ctx.Done():
			return
		}

		// Static discovery doesn't update, just wait for context cancellation
		<-ctx.Done()
	}()

	return ch, nil
}

// Register adds a node to the static list
func (sd *StaticDiscovery) Register(ctx context.Context, node NodeAddress) error {
	sd.mu.Lock()
	defer sd.mu.Unlock()

	// Check if already exists
	for _, n := range sd.nodes {
		if n.ID == node.ID {
			return fmt.Errorf("node already registered: %s", node.ID)
		}
	}

	sd.nodes = append(sd.nodes, node)
	return nil
}

// Deregister removes a node from the static list
func (sd *StaticDiscovery) Deregister(ctx context.Context, nodeID string) error {
	sd.mu.Lock()
	defer sd.mu.Unlock()

	for i, n := range sd.nodes {
		if n.ID == nodeID {
			sd.nodes = append(sd.nodes[:i], sd.nodes[i+1:]...)
			return nil
		}
	}

	return fmt.Errorf("node not found: %s", nodeID)
}

// ==============================================================================
// DNSDiscovery - for DNS-based discovery (cloud deployments)
// ==============================================================================

type DNSDiscovery struct {
	domain       string
	port         int
	refreshRate  time.Duration
	lastRefresh  time.Time
	cachedNodes  []NodeAddress
	mu           sync.RWMutex
}

// NewDNSDiscovery creates a new DNS-based discovery
func NewDNSDiscovery(domain string, port int, refreshRate time.Duration) *DNSDiscovery {
	return &DNSDiscovery{
		domain:      domain,
		port:        port,
		refreshRate: refreshRate,
	}
}

// Discover queries DNS for the current node list
func (dd *DNSDiscovery) Discover(ctx context.Context) ([]NodeAddress, error) {
	// In a real implementation, this would do DNS lookups
	// For now, return cached nodes
	dd.mu.RLock()
	defer dd.mu.RUnlock()

	result := make([]NodeAddress, len(dd.cachedNodes))
	copy(result, dd.cachedNodes)
	return result, nil
}

// Watch periodically discovers and returns updated node lists
func (dd *DNSDiscovery) Watch(ctx context.Context) (<-chan []NodeAddress, error) {
	ch := make(chan []NodeAddress)

	go func() {
		defer close(ch)
		ticker := time.NewTicker(dd.refreshRate)
		defer ticker.Stop()

		var lastNodes []NodeAddress

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				nodes, err := dd.Discover(ctx)
				if err != nil {
					continue
				}

				// Only send if changed
				if !nodesEqual(nodes, lastNodes) {
					lastNodes = nodes
					select {
					case ch <- nodes:
					case <-ctx.Done():
						return
					}
				}
			}
		}
	}()

	return ch, nil
}

// Register is a no-op for DNS discovery
func (dd *DNSDiscovery) Register(ctx context.Context, node NodeAddress) error {
	return fmt.Errorf("cannot register nodes with DNS discovery")
}

// Deregister is a no-op for DNS discovery
func (dd *DNSDiscovery) Deregister(ctx context.Context, nodeID string) error {
	return fmt.Errorf("cannot deregister nodes with DNS discovery")
}

// ==============================================================================
// DiscoveryManager - Coordinates discovery and handles node tracking
// ==============================================================================

type DiscoveryManager struct {
	discovery     Discovery
	nodeID        string
	mu            sync.RWMutex
	knownNodes    map[string]NodeAddress
	lastUpdate    time.Time
	updateChannel <-chan []NodeAddress
	observers     map[string]DiscoveryObserver
}

// DiscoveryObserver is notified of discovery changes
type DiscoveryObserver interface {
	OnNodesDiscovered(nodes []NodeAddress)
	OnNodeJoined(node NodeAddress)
	OnNodeLeft(nodeID string)
}

// NewDiscoveryManager creates a new discovery manager
func NewDiscoveryManager(discovery Discovery, nodeID string) *DiscoveryManager {
	return &DiscoveryManager{
		discovery:  discovery,
		nodeID:     nodeID,
		knownNodes: make(map[string]NodeAddress),
		observers:  make(map[string]DiscoveryObserver),
	}
}

// Start begins watching for discovery updates
func (dm *DiscoveryManager) Start(ctx context.Context) error {
	// Initial discovery
	nodes, err := dm.discovery.Discover(ctx)
	if err != nil {
		return fmt.Errorf("initial discovery failed: %w", err)
	}

	dm.updateKnownNodes(nodes)

	// Start watching for updates
	updateCh, err := dm.discovery.Watch(ctx)
	if err != nil {
		return fmt.Errorf("failed to start watching: %w", err)
	}

	go dm.watchUpdates(ctx, updateCh)

	return nil
}

// watchUpdates listens for discovery updates
func (dm *DiscoveryManager) watchUpdates(ctx context.Context, updateCh <-chan []NodeAddress) {
	for {
		select {
		case <-ctx.Done():
			return
		case nodes := <-updateCh:
			if nodes != nil {
				dm.updateKnownNodes(nodes)
			}
		}
	}
}

// updateKnownNodes updates the list of known nodes and notifies observers
func (dm *DiscoveryManager) updateKnownNodes(newNodes []NodeAddress) {
	dm.mu.Lock()
	defer dm.mu.Unlock()

	// Track which nodes are new and which have left
	newNodeMap := make(map[string]NodeAddress)
	for _, node := range newNodes {
		newNodeMap[node.ID] = node
	}

	// Find removed nodes
	for id := range dm.knownNodes {
		if _, exists := newNodeMap[id]; !exists {
			dm.notifyNodeLeft(id)
		}
	}

	// Find new nodes
	for _, node := range newNodes {
		if _, exists := dm.knownNodes[node.ID]; !exists && node.ID != dm.nodeID {
			dm.notifyNodeJoined(node)
		}
	}

	dm.knownNodes = newNodeMap
	dm.lastUpdate = time.Now()
	dm.notifyNodesDiscovered(newNodes)
}

// GetNodes returns the current list of discovered nodes
func (dm *DiscoveryManager) GetNodes() []NodeAddress {
	dm.mu.RLock()
	defer dm.mu.RUnlock()

	nodes := make([]NodeAddress, 0, len(dm.knownNodes))
	for _, node := range dm.knownNodes {
		if node.ID != dm.nodeID { // Exclude self
			nodes = append(nodes, node)
		}
	}
	return nodes
}

// RegisterObserver registers a discovery observer
func (dm *DiscoveryManager) RegisterObserver(name string, observer DiscoveryObserver) {
	dm.mu.Lock()
	defer dm.mu.Unlock()

	dm.observers[name] = observer
}

// Private helpers
func (dm *DiscoveryManager) notifyNodesDiscovered(nodes []NodeAddress) {
	for _, observer := range dm.observers {
		go observer.OnNodesDiscovered(nodes)
	}
}

func (dm *DiscoveryManager) notifyNodeJoined(node NodeAddress) {
	for _, observer := range dm.observers {
		go observer.OnNodeJoined(node)
	}
}

func (dm *DiscoveryManager) notifyNodeLeft(nodeID string) {
	for _, observer := range dm.observers {
		go observer.OnNodeLeft(nodeID)
	}
}

// Helper function to compare node lists
func nodesEqual(a, b []NodeAddress) bool {
	if len(a) != len(b) {
		return false
	}

	aMap := make(map[string]NodeAddress)
	for _, node := range a {
		aMap[node.ID] = node
	}

	for _, node := range b {
		if _, exists := aMap[node.ID]; !exists {
			return false
		}
	}

	return true
}
