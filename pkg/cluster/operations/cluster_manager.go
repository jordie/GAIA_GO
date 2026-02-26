package operations

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/hashicorp/raft"
)

// ClusterManager manages the Raft cluster operations
type ClusterManager struct {
	raftNode  *raft.Raft
	mu        sync.RWMutex
	nodeID    string
	peers     map[string]*PeerInfo
	observers map[string]ClusterObserver
}

// PeerInfo represents information about a cluster peer
type PeerInfo struct {
	ID              string
	Address         string
	Port            int
	LastHeartbeat   time.Time
	IsLeader        bool
	State           PeerState
	LogIndex        uint64
	SnapshotIndex   uint64
	MatchIndex      uint64
	NextIndex       uint64
}

// PeerState represents the state of a peer
type PeerState string

const (
	PeerStateUnknown   PeerState = "unknown"
	PeerStateHealthy   PeerState = "healthy"
	PeerStateDegraded  PeerState = "degraded"
	PeerStateUnhealthy PeerState = "unhealthy"
)

// ClusterObserver is notified of cluster events
type ClusterObserver interface {
	OnLeaderChange(nodeID string, isLeader bool)
	OnPeerJoin(nodeID string)
	OnPeerLeave(nodeID string)
	OnClusterStateChange(state ClusterState)
}

// ClusterState represents the overall cluster state
type ClusterState struct {
	NodeID           string
	IsLeader         bool
	LeaderID         string
	Term             uint64
	LastLogIndex     uint64
	LastLogTerm      uint64
	LastSnapshotTime time.Time
	PeerCount        int
	HealthyPeers     int
	DegradedPeers    int
	UnhealthyPeers   int
}

// NewClusterManager creates a new cluster manager
func NewClusterManager(nodeID string, raftNode *raft.Raft) *ClusterManager {
	return &ClusterManager{
		raftNode:  raftNode,
		nodeID:    nodeID,
		peers:     make(map[string]*PeerInfo),
		observers: make(map[string]ClusterObserver),
	}
}

// GetClusterState returns the current cluster state
func (cm *ClusterManager) GetClusterState() ClusterState {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	state := ClusterState{
		NodeID:       cm.nodeID,
		IsLeader:     cm.raftNode.State() == raft.Leader,
		LeaderID:     cm.raftNode.Leader().String(),
		Term:         cm.raftNode.AppliedIndex(),
		PeerCount:    len(cm.peers),
	}

	for _, peer := range cm.peers {
		switch peer.State {
		case PeerStateHealthy:
			state.HealthyPeers++
		case PeerStateDegraded:
			state.DegradedPeers++
		case PeerStateUnhealthy:
			state.UnhealthyPeers++
		}
	}

	return state
}

// GetPeerInfo returns information about a specific peer
func (cm *ClusterManager) GetPeerInfo(nodeID string) *PeerInfo {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	if peer, ok := cm.peers[nodeID]; ok {
		return peer
	}
	return nil
}

// GetAllPeers returns information about all peers
func (cm *ClusterManager) GetAllPeers() map[string]*PeerInfo {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	peers := make(map[string]*PeerInfo)
	for id, peer := range cm.peers {
		peers[id] = peer
	}
	return peers
}

// AddPeer adds a new peer to the cluster
func (cm *ClusterManager) AddPeer(ctx context.Context, nodeID, address string) error {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	if cm.raftNode.State() != raft.Leader {
		return fmt.Errorf("only leader can add peers")
	}

	// Create peer info
	peer := &PeerInfo{
		ID:            nodeID,
		Address:       address,
		LastHeartbeat: time.Now(),
		State:         PeerStateUnknown,
	}

	cm.peers[nodeID] = peer

	// Add voter to Raft
	indexFuture := cm.raftNode.AddVoter(raft.ServerID(nodeID), raft.ServerAddress(address), 0, 0)
	if err := indexFuture.Error(); err != nil {
		delete(cm.peers, nodeID)
		return fmt.Errorf("failed to add voter: %w", err)
	}

	// Notify observers
	cm.notifyPeerJoin(nodeID)

	return nil
}

// RemovePeer removes a peer from the cluster
func (cm *ClusterManager) RemovePeer(ctx context.Context, nodeID string) error {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	if cm.raftNode.State() != raft.Leader {
		return fmt.Errorf("only leader can remove peers")
	}

	if _, ok := cm.peers[nodeID]; !ok {
		return fmt.Errorf("peer not found: %s", nodeID)
	}

	// Remove voter from Raft
	indexFuture := cm.raftNode.RemoveServer(raft.ServerID(nodeID), 0, 0)
	if err := indexFuture.Error(); err != nil {
		return fmt.Errorf("failed to remove server: %w", err)
	}

	delete(cm.peers, nodeID)

	// Notify observers
	cm.notifyPeerLeave(nodeID)

	return nil
}

// UpdatePeerHeartbeat updates the last heartbeat time for a peer
func (cm *ClusterManager) UpdatePeerHeartbeat(nodeID string) {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	if peer, ok := cm.peers[nodeID]; ok {
		peer.LastHeartbeat = time.Now()
	}
}

// UpdatePeerState updates the state of a peer
func (cm *ClusterManager) UpdatePeerState(nodeID string, state PeerState) {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	if peer, ok := cm.peers[nodeID]; ok {
		peer.State = state
	}
}

// CheckPeerHealth checks the health of all peers
func (cm *ClusterManager) CheckPeerHealth(ctx context.Context, heartbeatTimeout time.Duration) {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	now := time.Now()
	for _, peer := range cm.peers {
		if peer.ID == cm.nodeID {
			continue // Skip self
		}

		timeSinceHeartbeat := now.Sub(peer.LastHeartbeat)

		switch {
		case timeSinceHeartbeat > heartbeatTimeout*2:
			peer.State = PeerStateUnhealthy
		case timeSinceHeartbeat > heartbeatTimeout:
			peer.State = PeerStateDegraded
		case peer.LastHeartbeat.IsZero():
			peer.State = PeerStateUnknown
		default:
			peer.State = PeerStateHealthy
		}
	}

	// Notify observers of state change
	cm.notifyClusterStateChange(cm.GetClusterState())
}

// ForceLeaderElection forces a new leader election
func (cm *ClusterManager) ForceLeaderElection(ctx context.Context) error {
	// This is done at the Raft level by calling raft.Barrier() then raft.VerifyLeader()
	// Or by stepping down as leader to trigger new election
	if cm.raftNode.State() == raft.Leader {
		// Step down and let other nodes elect a new leader
		return cm.raftNode.LeadershipTransfer().Error()
	}

	return nil
}

// RegisterObserver registers a cluster observer
func (cm *ClusterManager) RegisterObserver(name string, observer ClusterObserver) {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	cm.observers[name] = observer
}

// UnregisterObserver unregisters a cluster observer
func (cm *ClusterManager) UnregisterObserver(name string) {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	delete(cm.observers, name)
}

// Private helper methods for notifications

func (cm *ClusterManager) notifyPeerJoin(nodeID string) {
	for _, observer := range cm.observers {
		go observer.OnPeerJoin(nodeID)
	}
}

func (cm *ClusterManager) notifyPeerLeave(nodeID string) {
	for _, observer := range cm.observers {
		go observer.OnPeerLeave(nodeID)
	}
}

func (cm *ClusterManager) notifyClusterStateChange(state ClusterState) {
	for _, observer := range cm.observers {
		go observer.OnClusterStateChange(state)
	}
}

// GetMetrics returns cluster metrics
func (cm *ClusterManager) GetMetrics() map[string]interface{} {
	state := cm.GetClusterState()

	return map[string]interface{}{
		"node_id":          state.NodeID,
		"is_leader":        state.IsLeader,
		"leader_id":        state.LeaderID,
		"peer_count":       state.PeerCount,
		"healthy_peers":    state.HealthyPeers,
		"degraded_peers":   state.DegradedPeers,
		"unhealthy_peers":  state.UnhealthyPeers,
		"term":             state.Term,
	}
}
