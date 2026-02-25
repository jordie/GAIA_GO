package api

import (
	"context"
	"sync"
	"time"
)

// ReplayState represents the current state of a replay session
type ReplayState string

const (
	ReplayStatePlaying ReplayState = "playing"
	ReplayStatePaused  ReplayState = "paused"
	ReplayStateStopped ReplayState = "stopped"
)

// ReplaySession tracks an active replay session
type ReplaySession struct {
	SessionID    string
	State        ReplayState
	Speed        float64
	CurrentIndex int
	TotalEvents  int
	StartedAt    time.Time
	PausedAt     *time.Time
	ctx          context.Context
	cancel       context.CancelFunc
	pauseChan    chan bool
	resumeChan   chan bool
	seekChan     chan int
	mu           sync.RWMutex
}

// ReplayManager manages all active replay sessions
type ReplayManager struct {
	sessions map[string]*ReplaySession
	mu       sync.RWMutex
}

// NewReplayManager creates a new replay manager
func NewReplayManager() *ReplayManager {
	return &ReplayManager{
		sessions: make(map[string]*ReplaySession),
	}
}

// CreateSession creates a new replay session
func (rm *ReplayManager) CreateSession(sessionID string, totalEvents int, speed float64) *ReplaySession {
	rm.mu.Lock()
	defer rm.mu.Unlock()

	// Cancel existing session if present
	if existing, ok := rm.sessions[sessionID]; ok {
		existing.Stop()
	}

	ctx, cancel := context.WithCancel(context.Background())
	session := &ReplaySession{
		SessionID:    sessionID,
		State:        ReplayStatePlaying,
		Speed:        speed,
		CurrentIndex: 0,
		TotalEvents:  totalEvents,
		StartedAt:    time.Now(),
		ctx:          ctx,
		cancel:       cancel,
		pauseChan:    make(chan bool, 1),
		resumeChan:   make(chan bool, 1),
		seekChan:     make(chan int, 1),
	}

	rm.sessions[sessionID] = session
	return session
}

// GetSession retrieves a replay session
func (rm *ReplayManager) GetSession(sessionID string) (*ReplaySession, bool) {
	rm.mu.RLock()
	defer rm.mu.RUnlock()
	session, ok := rm.sessions[sessionID]
	return session, ok
}

// RemoveSession removes a replay session
func (rm *ReplayManager) RemoveSession(sessionID string) {
	rm.mu.Lock()
	defer rm.mu.Unlock()
	if session, ok := rm.sessions[sessionID]; ok {
		session.Stop()
		delete(rm.sessions, sessionID)
	}
}

// ListSessions returns all active sessions
func (rm *ReplayManager) ListSessions() []string {
	rm.mu.RLock()
	defer rm.mu.RUnlock()

	sessions := make([]string, 0, len(rm.sessions))
	for id := range rm.sessions {
		sessions = append(sessions, id)
	}
	return sessions
}

// Pause pauses the replay session
func (rs *ReplaySession) Pause() bool {
	rs.mu.Lock()
	defer rs.mu.Unlock()

	if rs.State != ReplayStatePlaying {
		return false
	}

	rs.State = ReplayStatePaused
	now := time.Now()
	rs.PausedAt = &now

	// Non-blocking send
	select {
	case rs.pauseChan <- true:
	default:
	}

	return true
}

// Resume resumes the replay session
func (rs *ReplaySession) Resume() bool {
	rs.mu.Lock()
	defer rs.mu.Unlock()

	if rs.State != ReplayStatePaused {
		return false
	}

	rs.State = ReplayStatePlaying
	rs.PausedAt = nil

	// Non-blocking send
	select {
	case rs.resumeChan <- true:
	default:
	}

	return true
}

// Stop stops the replay session
func (rs *ReplaySession) Stop() {
	rs.mu.Lock()
	defer rs.mu.Unlock()

	if rs.State == ReplayStateStopped {
		return
	}

	rs.State = ReplayStateStopped
	rs.cancel()
}

// Seek seeks to a specific event index
func (rs *ReplaySession) Seek(index int) bool {
	rs.mu.Lock()
	defer rs.mu.Unlock()

	if index < 0 || index >= rs.TotalEvents {
		return false
	}

	// Non-blocking send
	select {
	case rs.seekChan <- index:
		return true
	default:
		return false
	}
}

// SetSpeed changes the playback speed
func (rs *ReplaySession) SetSpeed(speed float64) {
	rs.mu.Lock()
	defer rs.mu.Unlock()

	if speed > 0 && speed <= 10.0 {
		rs.Speed = speed
	}
}

// GetState returns the current state
func (rs *ReplaySession) GetState() ReplayState {
	rs.mu.RLock()
	defer rs.mu.RUnlock()
	return rs.State
}

// GetProgress returns current playback progress
func (rs *ReplaySession) GetProgress() (current int, total int, percent float64) {
	rs.mu.RLock()
	defer rs.mu.RUnlock()

	current = rs.CurrentIndex
	total = rs.TotalEvents
	if total > 0 {
		percent = float64(current) / float64(total) * 100.0
	}
	return
}

// UpdateProgress updates the current index
func (rs *ReplaySession) UpdateProgress(index int) {
	rs.mu.Lock()
	defer rs.mu.Unlock()
	rs.CurrentIndex = index
}

// Context returns the session context
func (rs *ReplaySession) Context() context.Context {
	return rs.ctx
}

// WaitForResume waits until the session is resumed or stopped
func (rs *ReplaySession) WaitForResume() bool {
	select {
	case <-rs.resumeChan:
		return true
	case <-rs.ctx.Done():
		return false
	}
}

// CheckPause checks if pause was requested
func (rs *ReplaySession) CheckPause() bool {
	select {
	case <-rs.pauseChan:
		return true
	default:
		return false
	}
}

// CheckSeek checks if seek was requested
func (rs *ReplaySession) CheckSeek() (int, bool) {
	select {
	case index := <-rs.seekChan:
		return index, true
	default:
		return 0, false
	}
}

// GetStatus returns a status summary
func (rs *ReplaySession) GetStatus() map[string]interface{} {
	rs.mu.RLock()
	defer rs.mu.RUnlock()

	status := map[string]interface{}{
		"session_id":    rs.SessionID,
		"state":         string(rs.State),
		"speed":         rs.Speed,
		"current_index": rs.CurrentIndex,
		"total_events":  rs.TotalEvents,
		"started_at":    rs.StartedAt.Format(time.RFC3339),
	}

	if rs.PausedAt != nil {
		status["paused_at"] = rs.PausedAt.Format(time.RFC3339)
	}

	current, total, percent := rs.GetProgress()
	status["progress"] = map[string]interface{}{
		"current": current,
		"total":   total,
		"percent": percent,
	}

	return status
}
