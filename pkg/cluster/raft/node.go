// Package raft provides distributed consensus infrastructure for GAIA_GO
// using HashiCorp's Raft implementation.
package raft

import (
	"context"
	"fmt"
	"io"
	"net"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/hashicorp/raft"
	raftboltdb "github.com/hashicorp/raft-boltdb/v2"
)

// NodeConfig holds configuration for a Raft node
type NodeConfig struct {
	// NodeID is the unique identifier for this node in the cluster
	NodeID string

	// BindAddr is the address to bind the Raft server to (e.g., "0.0.0.0:8300")
	BindAddr string

	// AdvertiseAddr is the address other nodes should use to reach this node
	AdvertiseAddr string

	// DataDir is the directory to store Raft logs and snapshots
	DataDir string

	// Bootstrap indicates whether this node should bootstrap a new cluster
	Bootstrap bool

	// Peers are the initial cluster peers for bootstrap (NodeID:AdvertiseAddr)
	Peers []string

	// HeartbeatTimeout is the time before a follower considers the leader dead
	HeartbeatTimeout time.Duration

	// ElectionTimeout is the time before a candidate starts a new election
	ElectionTimeout time.Duration

	// SnapshotInterval is how often to take a snapshot
	SnapshotInterval time.Duration

	// SnapshotRetain is how many snapshots to keep
	SnapshotRetain int
}

// Node wraps a Raft node with convenience methods
type Node struct {
	raft *raft.Raft
	fsm  *FSM
	mu   sync.RWMutex

	// Configuration
	config NodeConfig

	// Leadership state
	isLeader bool
	leader   string

	// Cluster state
	peers map[string]raft.ServerAddress

	// Lifecycle
	done chan struct{}
}

// NewNode creates a new Raft node
func NewNode(config NodeConfig, fsm *FSM) (*Node, error) {
	if err := os.MkdirAll(config.DataDir, 0700); err != nil {
		return nil, fmt.Errorf("failed to create data directory: %w", err)
	}

	n := &Node{
		config: config,
		fsm:    fsm,
		peers:  make(map[string]raft.ServerAddress),
		done:   make(chan struct{}),
	}

	// Set defaults
	if config.HeartbeatTimeout == 0 {
		config.HeartbeatTimeout = 150 * time.Millisecond
	}
	if config.ElectionTimeout == 0 {
		config.ElectionTimeout = 300 * time.Millisecond
	}
	if config.SnapshotInterval == 0 {
		config.SnapshotInterval = 120 * time.Second
	}
	if config.SnapshotRetain == 0 {
		config.SnapshotRetain = 2
	}

	// Create Raft configuration
	raftConfig := raft.DefaultConfig()
	raftConfig.HeartbeatTimeout = config.HeartbeatTimeout
	raftConfig.ElectionTimeout = config.ElectionTimeout
	raftConfig.SnapshotInterval = config.SnapshotInterval
	raftConfig.SnapshotThreshold = 8192
	raftConfig.TrailingLogs = 10240
	raftConfig.LocalID = raft.ServerID(config.NodeID)

	// Create log store
	logStore, err := raftboltdb.NewBoltStore(filepath.Join(config.DataDir, "logs.db"))
	if err != nil {
		return nil, fmt.Errorf("failed to create log store: %w", err)
	}

	// Create stable store
	stableStore, err := raftboltdb.NewBoltStore(filepath.Join(config.DataDir, "stable.db"))
	if err != nil {
		return nil, fmt.Errorf("failed to create stable store: %w", err)
	}

	// Create snapshot store
	snapshots, err := raft.NewFileSnapshotStore(config.DataDir, config.SnapshotRetain, os.Stderr)
	if err != nil {
		return nil, fmt.Errorf("failed to create snapshot store: %w", err)
	}

	// Parse bind address
	tcpAddr, err := net.ResolveTCPAddr("tcp", config.BindAddr)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve bind address: %w", err)
	}

	// Create transport
	transport, err := raft.NewTCPTransport(config.BindAddr, (*net.TCPAddr)(tcpAddr), 3, 10*time.Second, os.Stderr)
	if err != nil {
		return nil, fmt.Errorf("failed to create transport: %w", err)
	}

	// Create Raft instance
	raftNode, err := raft.NewRaft(raftConfig, fsm, logStore, stableStore, snapshots, transport)
	if err != nil {
		return nil, fmt.Errorf("failed to create raft node: %w", err)
	}

	n.raft = raftNode

	// Bootstrap if needed
	if config.Bootstrap && len(config.Peers) > 0 {
		servers := make([]raft.Server, len(config.Peers))
		for i, peer := range config.Peers {
			// Parse "nodeID:address" format
			servers[i] = raft.Server{
				ID:       raft.ServerID(peer),
				Address:  raft.ServerAddress(config.AdvertiseAddr),
			}
		}

		future := raftNode.BootstrapCluster(raft.Configuration{
			Servers: servers,
		})
		if err := future.Error(); err != nil {
			// ErrClustersExist is not available in newer versions of hashicorp/raft
			if err.Error() != "cluster already bootstrapped" {
				return nil, fmt.Errorf("failed to bootstrap cluster: %w", err)
			}
		}
	}

	// Monitor leadership changes
	go n.monitorLeadership()

	return n, nil
}

// monitorLeadership watches for leadership changes
func (n *Node) monitorLeadership() {
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-n.done:
			return
		case <-ticker.C:
			n.mu.Lock()
			if n.raft.State() == raft.Leader {
				n.isLeader = true
				n.leader = n.config.NodeID
			} else {
				n.isLeader = false
				if leader := n.raft.Leader(); leader != "" {
					n.leader = string(leader)
				}
			}
			n.mu.Unlock()
		}
	}
}

// Apply applies a command to the state machine
func (n *Node) Apply(ctx context.Context, command []byte) error {
	future := n.raft.Apply(command, 5*time.Second)

	if err := future.Error(); err != nil {
		if err == raft.ErrNotLeader {
			return fmt.Errorf("node is not the leader")
		}
		return fmt.Errorf("failed to apply command: %w", err)
	}

	return nil
}

// AddPeer adds a peer to the cluster
func (n *Node) AddPeer(id, addr string) error {
	future := n.raft.AddNonvoter(raft.ServerID(id), raft.ServerAddress(addr), 0, 5*time.Second)
	return future.Error()
}

// AddVoter adds a voting member to the cluster
func (n *Node) AddVoter(id, addr string) error {
	future := n.raft.AddVoter(raft.ServerID(id), raft.ServerAddress(addr), 0, 5*time.Second)
	return future.Error()
}

// RemovePeer removes a peer from the cluster
func (n *Node) RemovePeer(id string) error {
	future := n.raft.RemoveServer(raft.ServerID(id), 0, 5*time.Second)
	return future.Error()
}

// IsLeader returns whether this node is the current leader
func (n *Node) IsLeader() bool {
	n.mu.RLock()
	defer n.mu.RUnlock()
	return n.isLeader
}

// Leader returns the current leader's node ID
func (n *Node) Leader() string {
	n.mu.RLock()
	defer n.mu.RUnlock()
	return n.leader
}

// GetFSM returns the finite state machine
func (n *Node) GetFSM() *FSM {
	return n.fsm
}

// GetState returns the current state
func (n *Node) GetState() map[string]interface{} {
	return n.fsm.GetState()
}

// GetStats returns Raft statistics
func (n *Node) GetStats() map[string]string {
	return n.raft.Stats()
}

// GetRaftStats returns detailed Raft statistics
func (n *Node) GetRaftStats() map[string]string {
	return n.raft.Stats()
}

// Peers returns the current cluster peers
func (n *Node) Peers() []raft.Server {
	future := n.raft.GetConfiguration()
	return future.Configuration().Servers
}

// Shutdown gracefully shuts down the Raft node
func (n *Node) Shutdown() error {
	close(n.done)

	// Wait for leadership monitor to stop
	time.Sleep(100 * time.Millisecond)

	future := n.raft.Shutdown()
	return future.Error()
}

// Restore is used by Raft to restore a snapshot
func (n *Node) Restore(rc io.ReadCloser) error {
	return n.fsm.Restore(rc)
}

// Snapshot is used by Raft to take a snapshot
func (n *Node) Snapshot() (io.ReadCloser, error) {
	// FSMSnapshot doesn't implement ReadCloser, so we return nil
	// Raft will need to be updated to properly support snapshots
	return nil, fmt.Errorf("snapshots not implemented")
}

// WaitForLeader waits up to timeout for a leader to be elected
func (n *Node) WaitForLeader(timeout time.Duration) bool {
	deadline := time.Now().Add(timeout)
	ticker := time.NewTicker(100 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-time.After(time.Until(deadline)):
			return false
		case <-ticker.C:
			n.mu.RLock()
			leader := n.leader
			n.mu.RUnlock()

			if leader != "" {
				return true
			}
		}
	}
}

// GetLeadershipTransferProgress returns progress of a leadership transfer
func (n *Node) GetLeadershipTransferProgress() (status string, progress float64) {
	if n.raft.State() == raft.Leader {
		return "leader", 1.0
	}
	if n.raft.State() == raft.Candidate {
		return "candidate", 0.5
	}
	return "follower", 0.0
}
