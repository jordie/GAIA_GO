package raft

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"
)

// InitFromEnv creates a Raft node from environment variables
func InitFromEnv() (*Node, error) {
	enabled := os.Getenv("CLUSTER_ENABLED")
	if enabled != "true" {
		return nil, fmt.Errorf("clustering disabled")
	}

	config := NodeConfig{
		NodeID:            os.Getenv("CLUSTER_NODE_ID"),
		BindAddr:          os.Getenv("CLUSTER_BIND_ADDR"),
		AdvertiseAddr:     os.Getenv("CLUSTER_ADVERTISE_ADDR"),
		DataDir:           os.Getenv("CLUSTER_DATA_DIR"),
		Bootstrap:         os.Getenv("CLUSTER_BOOTSTRAP") == "true",
		HeartbeatTimeout:  parseDuration(os.Getenv("RAFT_HEARTBEAT_TIMEOUT"), 150*time.Millisecond),
		ElectionTimeout:   parseTimeout(os.Getenv("RAFT_ELECTION_TIMEOUT"), 300*time.Millisecond),
		SnapshotInterval:  parseDuration(os.Getenv("RAFT_SNAPSHOT_INTERVAL"), 120*time.Second),
		SnapshotRetain:    parseInt(os.Getenv("RAFT_SNAPSHOT_RETAIN"), 2),
	}

	// Parse peers
	peersStr := os.Getenv("CLUSTER_DISCOVERY_NODES")
	if peersStr != "" {
		config.Peers = strings.Split(peersStr, ",")
	}

	// Validate required fields
	if config.NodeID == "" {
		return nil, fmt.Errorf("CLUSTER_NODE_ID is required")
	}
	if config.BindAddr == "" {
		return nil, fmt.Errorf("CLUSTER_BIND_ADDR is required")
	}
	if config.AdvertiseAddr == "" {
		return nil, fmt.Errorf("CLUSTER_ADVERTISE_ADDR is required")
	}
	if config.DataDir == "" {
		config.DataDir = "./data/raft"
	}

	// Create FSM
	fsm := NewFSM()

	// Create and return node
	return NewNode(config, fsm)
}

// InitWithConfig creates a Raft node with explicit configuration
func InitWithConfig(config NodeConfig) (*Node, error) {
	fsm := NewFSM()
	return NewNode(config, fsm)
}

// parseTimeout parses a timeout string (e.g., "150ms", "2s")
func parseTimeout(s string, defaultVal time.Duration) time.Duration {
	return parseDuration(s, defaultVal)
}

// parseDuration parses a duration string (e.g., "150ms", "2s")
func parseDuration(s string, defaultVal time.Duration) time.Duration {
	if s == "" {
		return defaultVal
	}
	d, err := time.ParseDuration(s)
	if err != nil {
		return defaultVal
	}
	return d
}

// parseInt parses an integer string
func parseInt(s string, defaultVal int) int {
	if s == "" {
		return defaultVal
	}
	var i int
	if _, err := fmt.Sscanf(s, "%d", &i); err != nil {
		return defaultVal
	}
	return i
}

// RegisterSessionCommand creates a session registration command
func RegisterSessionCommand(nodeID string, session map[string]interface{}) ([]byte, error) {
	cmd := Command{
		Type:      CommandSessionRegister,
		NodeID:    nodeID,
		Data:      session,
		Timestamp: time.Now().Unix(),
	}
	return json.Marshal(cmd)
}

// HeartbeatCommand creates a heartbeat command
func HeartbeatCommand(nodeID string, sessionName string) ([]byte, error) {
	cmd := Command{
		Type:   CommandSessionHeartbeat,
		NodeID: nodeID,
		Data: map[string]interface{}{
			"session_name": sessionName,
		},
		Timestamp: time.Now().Unix(),
	}
	return json.Marshal(cmd)
}

// TaskAssignCommand creates a task assignment command
func TaskAssignCommand(nodeID string, taskID string, sessionID string, priority int) ([]byte, error) {
	cmd := Command{
		Type:   CommandTaskAssign,
		NodeID: nodeID,
		Data: map[string]interface{}{
			"task_id":    taskID,
			"session_id": sessionID,
			"priority":   priority,
		},
		Timestamp: time.Now().Unix(),
	}
	return json.Marshal(cmd)
}

// TaskCompleteCommand creates a task completion command
func TaskCompleteCommand(nodeID string, taskID string) ([]byte, error) {
	cmd := Command{
		Type:   CommandTaskComplete,
		NodeID: nodeID,
		Data: map[string]interface{}{
			"task_id": taskID,
		},
		Timestamp: time.Now().Unix(),
	}
	return json.Marshal(cmd)
}

// SessionFailureCommand creates a session failure command
func SessionFailureCommand(nodeID string, sessionName string, reason string) ([]byte, error) {
	cmd := Command{
		Type:   CommandSessionFailure,
		NodeID: nodeID,
		Data: map[string]interface{}{
			"session_name": sessionName,
			"reason":       reason,
		},
		Timestamp: time.Now().Unix(),
	}
	return json.Marshal(cmd)
}

// LockAcquireCommand creates a lock acquisition command
func LockAcquireCommand(nodeID string, lockKey string, ownerID string, ttlSeconds int64) ([]byte, error) {
	cmd := Command{
		Type:   CommandLockAcquire,
		NodeID: nodeID,
		Data: map[string]interface{}{
			"lock_key":     lockKey,
			"owner_id":     ownerID,
			"ttl_seconds":  ttlSeconds,
		},
		Timestamp: time.Now().Unix(),
	}
	return json.Marshal(cmd)
}

// LockReleaseCommand creates a lock release command
func LockReleaseCommand(nodeID string, lockKey string, ownerID string) ([]byte, error) {
	cmd := Command{
		Type:   CommandLockRelease,
		NodeID: nodeID,
		Data: map[string]interface{}{
			"lock_key": lockKey,
			"owner_id": ownerID,
		},
		Timestamp: time.Now().Unix(),
	}
	return json.Marshal(cmd)
}
