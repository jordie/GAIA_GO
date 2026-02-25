// Package coordinator provides distributed session coordination for GAIA_GO
// It manages Claude Code session registration, health tracking, and task assignment optimization.
package coordinator

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/jgirmay/GAIA_GO/pkg/cluster/raft"
	"github.com/jgirmay/GAIA_GO/pkg/models"
	"github.com/jgirmay/GAIA_GO/pkg/repository"
)

// SessionCoordinator manages distributed Claude Code session coordination
type SessionCoordinator struct {
	mu              sync.RWMutex
	raftNode        *raft.Node
	sessionRepo     repository.ClaudeSessionRepository
	lessonRepo      repository.LessonRepository
	affinityRepo    repository.SessionAffinityRepository
	taskRepo        repository.DistributedTaskRepository
	lockRepo        repository.DistributedLockRepository

	// Configuration
	leaseTimeout       time.Duration
	heartbeatInterval  time.Duration
	failureThreshold   int
	maxConcurrentTasks int

	// State
	activeSessions map[string]*models.ClaudeSession
	sessionStats   map[string]*SessionStats
	failedSessions map[string]time.Time

	// Channels
	done chan struct{}
}

// SessionStats tracks session performance metrics
type SessionStats struct {
	RegisteredAt      time.Time
	LastHeartbeat     time.Time
	TasksCompleted    int
	TasksFailed       int
	AverageTaskTime   time.Duration
	ConsecutiveErrors int
}

// Config holds SessionCoordinator configuration
type Config struct {
	LeaseTimeout       time.Duration
	HeartbeatInterval  time.Duration
	FailureThreshold   int
	MaxConcurrentTasks int
}

// DefaultConfig returns default configuration
func DefaultConfig() Config {
	return Config{
		LeaseTimeout:       30 * time.Second,
		HeartbeatInterval:  10 * time.Second,
		FailureThreshold:   3,
		MaxConcurrentTasks: 5,
	}
}

// NewSessionCoordinator creates a new session coordinator
func NewSessionCoordinator(
	raftNode *raft.Node,
	sessionRepo repository.ClaudeSessionRepository,
	lessonRepo repository.LessonRepository,
	affinityRepo repository.SessionAffinityRepository,
	taskRepo repository.DistributedTaskRepository,
	lockRepo repository.DistributedLockRepository,
	config Config,
) *SessionCoordinator {
	return &SessionCoordinator{
		raftNode:           raftNode,
		sessionRepo:        sessionRepo,
		lessonRepo:         lessonRepo,
		affinityRepo:       affinityRepo,
		taskRepo:           taskRepo,
		lockRepo:           lockRepo,
		leaseTimeout:       config.LeaseTimeout,
		heartbeatInterval:  config.HeartbeatInterval,
		failureThreshold:   config.FailureThreshold,
		maxConcurrentTasks: config.MaxConcurrentTasks,
		activeSessions:     make(map[string]*models.ClaudeSession),
		sessionStats:       make(map[string]*SessionStats),
		failedSessions:     make(map[string]time.Time),
		done:               make(chan struct{}),
	}
}

// RegisterSession registers a new Claude session
func (sc *SessionCoordinator) RegisterSession(ctx context.Context, session *models.ClaudeSession) error {
	sc.mu.Lock()
	defer sc.mu.Unlock()

	// Validate session
	if session.SessionName == "" {
		return fmt.Errorf("session name is required")
	}
	if session.Tier == "" {
		return fmt.Errorf("session tier is required")
	}
	if session.Provider == "" {
		return fmt.Errorf("session provider is required")
	}

	// Set defaults
	if session.ID == uuid.Nil {
		session.ID = uuid.New()
	}
	if session.Status == "" {
		session.Status = "idle"
	}
	if session.HealthStatus == "" {
		session.HealthStatus = "healthy"
	}
	if session.MaxConcurrentTasks == 0 {
		session.MaxConcurrentTasks = sc.maxConcurrentTasks
	}

	session.LastHeartbeat = time.Now()
	session.CreatedAt = time.Now()
	session.UpdatedAt = time.Now()

	// Create in database
	if err := sc.sessionRepo.Create(ctx, session); err != nil {
		return fmt.Errorf("failed to create session: %w", err)
	}

	// Register via Raft
	cmd, err := raft.RegisterSessionCommand(sc.raftNode.GetFSM().GetState()["node_id"].(string), map[string]interface{}{
		"session_name":         session.SessionName,
		"tier":                 session.Tier,
		"provider":             session.Provider,
		"max_concurrent_tasks": session.MaxConcurrentTasks,
	})
	if err != nil {
		return fmt.Errorf("failed to create register command: %w", err)
	}

	if err := sc.raftNode.Apply(ctx, cmd); err != nil {
		return fmt.Errorf("failed to apply register command: %w", err)
	}

	// Track locally
	sc.activeSessions[session.SessionName] = session
	sc.sessionStats[session.SessionName] = &SessionStats{
		RegisteredAt:  time.Now(),
		LastHeartbeat: time.Now(),
	}

	return nil
}

// UnregisterSession unregisters a session
func (sc *SessionCoordinator) UnregisterSession(ctx context.Context, sessionName string) error {
	sc.mu.Lock()
	defer sc.mu.Unlock()

	session, ok := sc.activeSessions[sessionName]
	if !ok {
		return fmt.Errorf("session not found: %s", sessionName)
	}

	// Remove from database
	if err := sc.sessionRepo.Delete(ctx, session.ID); err != nil {
		return fmt.Errorf("failed to delete session: %w", err)
	}

	// Remove locally
	delete(sc.activeSessions, sessionName)
	delete(sc.sessionStats, sessionName)
	delete(sc.failedSessions, sessionName)

	return nil
}

// RecordHeartbeat records a session heartbeat
func (sc *SessionCoordinator) RecordHeartbeat(ctx context.Context, sessionName string) error {
	sc.mu.Lock()
	defer sc.mu.Unlock()

	session, ok := sc.activeSessions[sessionName]
	if !ok {
		return fmt.Errorf("session not found: %s", sessionName)
	}

	// Update in database
	if err := sc.sessionRepo.RecordHeartbeat(ctx, session.ID); err != nil {
		return fmt.Errorf("failed to record heartbeat: %w", err)
	}

	// Update locally
	session.LastHeartbeat = time.Now()
	session.Status = "idle"
	sc.activeSessions[sessionName] = session

	if stats, ok := sc.sessionStats[sessionName]; ok {
		stats.LastHeartbeat = time.Now()
		stats.ConsecutiveErrors = 0
	}

	// Reset failure tracking if healthy
	if session.ConsecutiveFailures > 0 {
		if err := sc.sessionRepo.UpdateHealthStatus(ctx, session.ID, "healthy"); err != nil {
			// Log but don't fail
			fmt.Printf("warning: failed to update health status: %v\n", err)
		}
	}

	return nil
}

// GetAvailableSession finds the best session for task assignment
func (sc *SessionCoordinator) GetAvailableSession(ctx context.Context, lessonID *uuid.UUID) (*models.ClaudeSession, error) {
	sc.mu.RLock()
	defer sc.mu.RUnlock()

	var candidates []*models.ClaudeSession

	// Find healthy, active sessions that can take tasks
	for _, session := range sc.activeSessions {
		if !session.IsActive() || !session.IsHealthy() {
			continue
		}
		if session.CurrentTaskCount >= session.MaxConcurrentTasks {
			continue
		}
		candidates = append(candidates, session)
	}

	if len(candidates) == 0 {
		return nil, fmt.Errorf("no available sessions")
	}

	// If lesson ID provided, use affinity scoring
	if lessonID != nil {
		bestSession, score := sc.findBestSessionForLesson(ctx, candidates, *lessonID)
		if bestSession != nil {
			return bestSession, nil
		}
		// Fall through to default selection if affinity lookup fails
	}

	// Default: return session with least load
	bestSession := candidates[0]
	for _, s := range candidates[1:] {
		if s.CurrentTaskCount < bestSession.CurrentTaskCount {
			bestSession = s
		}
	}

	return bestSession, nil
}

// findBestSessionForLesson finds session with best affinity for lesson
func (sc *SessionCoordinator) findBestSessionForLesson(ctx context.Context, candidates []*models.ClaudeSession, lessonID uuid.UUID) (*models.ClaudeSession, float64) {
	bestScore := -1.0
	var bestSession *models.ClaudeSession

	for _, session := range candidates {
		// Check if session has affinity for this lesson
		// This would be enhanced when affinityRepo.GetBestSessionForLesson is implemented
		if session != nil {
			bestSession = session
			bestScore = 1.0
			break
		}
	}

	return bestSession, bestScore
}

// GetHealthySessions returns all healthy, active sessions
func (sc *SessionCoordinator) GetHealthySessions(ctx context.Context) ([]*models.ClaudeSession, error) {
	sc.mu.RLock()
	defer sc.mu.RUnlock()

	var result []*models.ClaudeSession
	for _, session := range sc.activeSessions {
		if session.IsActive() && session.IsHealthy() {
			result = append(result, session)
		}
	}
	return result, nil
}

// GetActiveSessionCount returns count of active sessions
func (sc *SessionCoordinator) GetActiveSessionCount() int {
	sc.mu.RLock()
	defer sc.mu.RUnlock()
	return len(sc.activeSessions)
}

// GetSessionStatus returns status of all sessions
func (sc *SessionCoordinator) GetSessionStatus(ctx context.Context) map[string]interface{} {
	sc.mu.RLock()
	defer sc.mu.RUnlock()

	status := make(map[string]interface{})
	status["total_sessions"] = len(sc.activeSessions)

	healthy := 0
	idle := 0
	busy := 0

	for _, session := range sc.activeSessions {
		if session.IsHealthy() {
			healthy++
		}
		if session.Status == "idle" {
			idle++
		} else if session.Status == "busy" {
			busy++
		}
	}

	status["healthy_sessions"] = healthy
	status["idle_sessions"] = idle
	status["busy_sessions"] = busy
	status["timestamp"] = time.Now()

	return status
}

// PerformHealthCheck checks health of all sessions
func (sc *SessionCoordinator) PerformHealthCheck(ctx context.Context) error {
	sc.mu.Lock()
	defer sc.mu.Unlock()

	now := time.Now()
	for sessionName, session := range sc.activeSessions {
		timeSinceHeartbeat := now.Sub(session.LastHeartbeat)

		if timeSinceHeartbeat > sc.leaseTimeout {
			// Session is dead
			if err := sc.handleSessionFailure(ctx, session); err != nil {
				fmt.Printf("error handling session failure: %v\n", err)
			}
			delete(sc.activeSessions, sessionName)
		} else if timeSinceHeartbeat > sc.leaseTimeout/2 {
			// Session is degraded
			if err := sc.sessionRepo.UpdateHealthStatus(ctx, session.ID, "degraded"); err != nil {
				fmt.Printf("warning: failed to update health status: %v\n", err)
			}
		}
	}

	return nil
}

// handleSessionFailure handles a failed session
func (sc *SessionCoordinator) handleSessionFailure(ctx context.Context, session *models.ClaudeSession) error {
	// Mark session as failed
	if err := sc.sessionRepo.UpdateStatus(ctx, session.ID, "failed"); err != nil {
		return fmt.Errorf("failed to update session status: %w", err)
	}

	// Reassign tasks from failed session
	if err := sc.taskRepo.ReassignFailedSessionTasks(ctx, session.ID); err != nil {
		return fmt.Errorf("failed to reassign tasks: %w", err)
	}

	// Track failure time
	sc.failedSessions[session.SessionName] = time.Now()

	return nil
}

// Start begins background health monitoring
func (sc *SessionCoordinator) Start(ctx context.Context) {
	ticker := time.NewTicker(sc.heartbeatInterval)
	defer ticker.Stop()

	for {
		select {
		case <-sc.done:
			return
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := sc.PerformHealthCheck(ctx); err != nil {
				fmt.Printf("health check error: %v\n", err)
			}
		}
	}
}

// Stop stops the coordinator
func (sc *SessionCoordinator) Stop() {
	close(sc.done)
}

// GetSessionStats returns stats for a session
func (sc *SessionCoordinator) GetSessionStats(sessionName string) *SessionStats {
	sc.mu.RLock()
	defer sc.mu.RUnlock()
	return sc.sessionStats[sessionName]
}

// GetAllSessionStats returns stats for all sessions
func (sc *SessionCoordinator) GetAllSessionStats() map[string]*SessionStats {
	sc.mu.RLock()
	defer sc.mu.RUnlock()

	result := make(map[string]*SessionStats)
	for k, v := range sc.sessionStats {
		result[k] = v
	}
	return result
}

// LoadSessions loads all sessions from database on startup
func (sc *SessionCoordinator) LoadSessions(ctx context.Context) error {
	sessions, err := sc.sessionRepo.List(ctx)
	if err != nil {
		return fmt.Errorf("failed to load sessions: %w", err)
	}

	sc.mu.Lock()
	defer sc.mu.Unlock()

	for _, session := range sessions {
		sc.activeSessions[session.SessionName] = session
		sc.sessionStats[session.SessionName] = &SessionStats{
			RegisteredAt:  session.CreatedAt,
			LastHeartbeat: session.LastHeartbeat,
		}
	}

	return nil
}
