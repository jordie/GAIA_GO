package raft

import (
	"bytes"
	"encoding/gob"
	"encoding/json"
	"fmt"
	"io"
	"sync"

	"github.com/hashicorp/raft"
)

// CommandType defines the type of command being applied
type CommandType string

const (
	CommandSessionRegister   CommandType = "session_register"
	CommandSessionHeartbeat  CommandType = "session_heartbeat"
	CommandTaskAssign        CommandType = "task_assign"
	CommandTaskComplete      CommandType = "task_complete"
	CommandSessionFailure    CommandType = "session_failure"
	CommandLockAcquire       CommandType = "lock_acquire"
	CommandLockRelease       CommandType = "lock_release"
)

// Command represents a command to be applied to the state machine
type Command struct {
	Type      CommandType `json:"type"`
	NodeID    string      `json:"node_id"`
	Data      interface{} `json:"data"`
	Timestamp int64       `json:"timestamp"`
}

// SessionData holds Claude session information
type SessionData struct {
	SessionName       string      `json:"session_name"`
	Tier              string      `json:"tier"`
	Provider          string      `json:"provider"`
	Status            string      `json:"status"`
	MaxConcurrentTasks int        `json:"max_concurrent_tasks"`
	Metadata          interface{} `json:"metadata,omitempty"`
}

// TaskData holds distributed task information
type TaskData struct {
	TaskID    string      `json:"task_id"`
	SessionID string      `json:"session_id"`
	Priority  int         `json:"priority"`
	Data      interface{} `json:"data"`
}

// LockData holds distributed lock information
type LockData struct {
	LockKey string `json:"lock_key"`
	OwnerID string `json:"owner_id"`
	TTL     int64  `json:"ttl_seconds"`
}

// FSM is the finite state machine for Raft
type FSM struct {
	mu sync.RWMutex

	// Session state
	sessions map[string]*SessionData

	// Task assignment state
	taskAssignments map[string]string // taskID -> sessionID

	// Lock state
	locks map[string]*LockData

	// Operation log
	operationLog []Command
}

// NewFSM creates a new finite state machine
func NewFSM() *FSM {
	return &FSM{
		sessions:        make(map[string]*SessionData),
		taskAssignments: make(map[string]string),
		locks:           make(map[string]*LockData),
		operationLog:    make([]Command, 0),
	}
}

// Apply applies a command to the FSM
func (f *FSM) Apply(log *raft.Log) interface{} {
	f.mu.Lock()
	defer f.mu.Unlock()

	var cmd Command
	if err := json.Unmarshal(log.Data, &cmd); err != nil {
		return fmt.Errorf("failed to unmarshal command: %w", err)
	}

	// Log the operation
	f.operationLog = append(f.operationLog, cmd)
	if len(f.operationLog) > 10000 {
		// Keep only recent operations
		f.operationLog = f.operationLog[1000:]
	}

	switch cmd.Type {
	case CommandSessionRegister:
		return f.applySessionRegister(&cmd)
	case CommandSessionHeartbeat:
		return f.applySessionHeartbeat(&cmd)
	case CommandTaskAssign:
		return f.applyTaskAssign(&cmd)
	case CommandTaskComplete:
		return f.applyTaskComplete(&cmd)
	case CommandSessionFailure:
		return f.applySessionFailure(&cmd)
	case CommandLockAcquire:
		return f.applyLockAcquire(&cmd)
	case CommandLockRelease:
		return f.applyLockRelease(&cmd)
	default:
		return fmt.Errorf("unknown command type: %s", cmd.Type)
	}
}

// applySessionRegister registers a new Claude session
func (f *FSM) applySessionRegister(cmd *Command) interface{} {
	data, ok := cmd.Data.(map[string]interface{})
	if !ok {
		return fmt.Errorf("invalid session data")
	}

	sessionData := &SessionData{
		SessionName:        data["session_name"].(string),
		Tier:               data["tier"].(string),
		Provider:           data["provider"].(string),
		Status:             "idle",
		MaxConcurrentTasks: int(data["max_concurrent_tasks"].(float64)),
		Metadata:           data["metadata"],
	}

	f.sessions[sessionData.SessionName] = sessionData
	return nil
}

// applySessionHeartbeat updates session heartbeat
func (f *FSM) applySessionHeartbeat(cmd *Command) interface{} {
	data, ok := cmd.Data.(map[string]interface{})
	if !ok {
		return fmt.Errorf("invalid heartbeat data")
	}

	sessionName := data["session_name"].(string)
	if session, ok := f.sessions[sessionName]; ok {
		session.Status = "idle"
		return nil
	}
	return fmt.Errorf("session not found: %s", sessionName)
}

// applyTaskAssign assigns a task to a session
func (f *FSM) applyTaskAssign(cmd *Command) interface{} {
	data, ok := cmd.Data.(map[string]interface{})
	if !ok {
		return fmt.Errorf("invalid task data")
	}

	taskID := data["task_id"].(string)
	sessionID := data["session_id"].(string)

	// Check if session exists
	if _, ok := f.sessions[sessionID]; !ok {
		return fmt.Errorf("session not found: %s", sessionID)
	}

	f.taskAssignments[taskID] = sessionID
	return nil
}

// applyTaskComplete marks a task as completed
func (f *FSM) applyTaskComplete(cmd *Command) interface{} {
	data, ok := cmd.Data.(map[string]interface{})
	if !ok {
		return fmt.Errorf("invalid task completion data")
	}

	taskID := data["task_id"].(string)
	delete(f.taskAssignments, taskID)
	return nil
}

// applySessionFailure marks a session as failed
func (f *FSM) applySessionFailure(cmd *Command) interface{} {
	data, ok := cmd.Data.(map[string]interface{})
	if !ok {
		return fmt.Errorf("invalid failure data")
	}

	sessionName := data["session_name"].(string)
	if session, ok := f.sessions[sessionName]; ok {
		session.Status = "failed"

		// Reassign tasks from failed session
		tasksToReassign := make([]string, 0)
		for taskID, assignedSession := range f.taskAssignments {
			if assignedSession == sessionName {
				tasksToReassign = append(tasksToReassign, taskID)
			}
		}

		// Clear assignments
		for _, taskID := range tasksToReassign {
			delete(f.taskAssignments, taskID)
		}

		return nil
	}
	return fmt.Errorf("session not found: %s", sessionName)
}

// applyLockAcquire acquires a distributed lock
func (f *FSM) applyLockAcquire(cmd *Command) interface{} {
	data, ok := cmd.Data.(map[string]interface{})
	if !ok {
		return fmt.Errorf("invalid lock data")
	}

	lockKey := data["lock_key"].(string)
	ownerID := data["owner_id"].(string)
	ttl := int64(data["ttl_seconds"].(float64))

	// Check if lock is already held by different owner
	if existing, ok := f.locks[lockKey]; ok && existing.OwnerID != ownerID {
		return fmt.Errorf("lock already held by: %s", existing.OwnerID)
	}

	f.locks[lockKey] = &LockData{
		LockKey: lockKey,
		OwnerID: ownerID,
		TTL:     ttl,
	}
	return nil
}

// applyLockRelease releases a distributed lock
func (f *FSM) applyLockRelease(cmd *Command) interface{} {
	data, ok := cmd.Data.(map[string]interface{})
	if !ok {
		return fmt.Errorf("invalid lock release data")
	}

	lockKey := data["lock_key"].(string)
	ownerID := data["owner_id"].(string)

	// Verify ownership
	if lock, ok := f.locks[lockKey]; ok && lock.OwnerID == ownerID {
		delete(f.locks, lockKey)
		return nil
	}
	return fmt.Errorf("lock not owned by: %s", ownerID)
}

// Snapshot returns a snapshot of the FSM state
func (f *FSM) Snapshot() (raft.FSMSnapshot, error) {
	f.mu.RLock()
	defer f.mu.RUnlock()

	return &snapshot{
		sessions:        f.sessions,
		taskAssignments: f.taskAssignments,
		locks:           f.locks,
	}, nil
}

// Restore restores the FSM from a snapshot
func (f *FSM) Restore(rc io.ReadCloser) error {
	f.mu.Lock()
	defer f.mu.Unlock()

	var snap snapshot
	dec := gob.NewDecoder(rc)
	if err := dec.Decode(&snap); err != nil {
		return fmt.Errorf("failed to decode snapshot: %w", err)
	}

	f.sessions = snap.sessions
	f.taskAssignments = snap.taskAssignments
	f.locks = snap.locks

	return rc.Close()
}

// GetState returns the current state
func (f *FSM) GetState() map[string]interface{} {
	f.mu.RLock()
	defer f.mu.RUnlock()

	return map[string]interface{}{
		"sessions":         len(f.sessions),
		"task_assignments": len(f.taskAssignments),
		"locks":            len(f.locks),
	}
}

// GetSessions returns all registered sessions
func (f *FSM) GetSessions() map[string]*SessionData {
	f.mu.RLock()
	defer f.mu.RUnlock()

	sessions := make(map[string]*SessionData)
	for k, v := range f.sessions {
		sessions[k] = v
	}
	return sessions
}

// GetTaskAssignments returns all task assignments
func (f *FSM) GetTaskAssignments() map[string]string {
	f.mu.RLock()
	defer f.mu.RUnlock()

	assignments := make(map[string]string)
	for k, v := range f.taskAssignments {
		assignments[k] = v
	}
	return assignments
}

// GetLocks returns all distributed locks
func (f *FSM) GetLocks() map[string]*LockData {
	f.mu.RLock()
	defer f.mu.RUnlock()

	locks := make(map[string]*LockData)
	for k, v := range f.locks {
		locks[k] = v
	}
	return locks
}

// snapshot represents a snapshot of the FSM
type snapshot struct {
	sessions        map[string]*SessionData
	taskAssignments map[string]string
	locks           map[string]*LockData
}

// Persist writes the snapshot to a WriteCloser
func (s *snapshot) Persist(sink raft.SnapshotSink) error {
	enc := gob.NewEncoder(sink)
	if err := enc.Encode(s); err != nil {
		sink.Cancel()
		return fmt.Errorf("failed to encode snapshot: %w", err)
	}
	return sink.Close()
}

// Release is called when we're done with the snapshot
func (s *snapshot) Release() {
	// Nothing to clean up
}
