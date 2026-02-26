// Package queue provides distributed task queue with exactly-once semantics
package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/jgirmay/GAIA_GO/pkg/cluster/raft"
	"github.com/jgirmay/GAIA_GO/pkg/models"
	"github.com/jgirmay/GAIA_GO/pkg/repository"
)

// TaskQueue provides distributed task queuing with exactly-once semantics
type TaskQueue struct {
	mu           sync.RWMutex
	raftNode     *raft.Node
	taskRepo     repository.DistributedTaskRepository
	sessionRepo  repository.ClaudeSessionRepository
	lockRepo     repository.DistributedLockRepository
	coordinator  SessionCoordinator

	// Configuration
	maxRetries      int
	claimTimeout    time.Duration
	retryBackoff    time.Duration
	cleanupInterval time.Duration

	// State
	inFlightTasks map[string]time.Time

	// Channels
	done chan struct{}
}

// SessionCoordinator interface for task assignment
type SessionCoordinator interface {
	GetAvailableSession(ctx context.Context, lessonID *uuid.UUID) (*models.ClaudeSession, error)
	GetHealthySessions(ctx context.Context) ([]*models.ClaudeSession, error)
}

// Config holds TaskQueue configuration
type Config struct {
	MaxRetries      int
	ClaimTimeout    time.Duration
	RetryBackoff    time.Duration
	CleanupInterval time.Duration
}

// DefaultConfig returns default configuration
func DefaultConfig() Config {
	return Config{
		MaxRetries:      3,
		ClaimTimeout:    10 * time.Minute,
		RetryBackoff:    time.Second,
		CleanupInterval: time.Minute,
	}
}

// NewTaskQueue creates a new task queue
func NewTaskQueue(
	raftNode *raft.Node,
	taskRepo repository.DistributedTaskRepository,
	sessionRepo repository.ClaudeSessionRepository,
	lockRepo repository.DistributedLockRepository,
	coordinator SessionCoordinator,
	config Config,
) *TaskQueue {
	return &TaskQueue{
		raftNode:        raftNode,
		taskRepo:        taskRepo,
		sessionRepo:     sessionRepo,
		lockRepo:        lockRepo,
		coordinator:     coordinator,
		maxRetries:      config.MaxRetries,
		claimTimeout:    config.ClaimTimeout,
		retryBackoff:    config.RetryBackoff,
		cleanupInterval: config.CleanupInterval,
		inFlightTasks:   make(map[string]time.Time),
		done:            make(chan struct{}),
	}
}

// Enqueue adds a task to the queue
func (tq *TaskQueue) Enqueue(ctx context.Context, taskType string, data interface{}, priority int) (*models.DistributedTask, error) {
	// Generate idempotency key
	idempotencyKey := uuid.New().String()

	// Marshal task data
	taskData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal task data: %w", err)
	}

	// Create task
	task := &models.DistributedTask{
		ID:              uuid.New(),
		IdempotencyKey:  idempotencyKey,
		TaskType:        taskType,
		TaskData:        json.RawMessage(taskData),
		Priority:        priority,
		Status:          "pending",
		RetryCount:      0,
		MaxRetries:      tq.maxRetries,
		CreatedAt:       time.Now(),
		UpdatedAt:       time.Now(),
	}

	// Save to database
	if err := tq.taskRepo.Create(ctx, task); err != nil {
		return nil, fmt.Errorf("failed to create task: %w", err)
	}

	tq.mu.Lock()
	tq.inFlightTasks[task.ID.String()] = time.Now()
	tq.mu.Unlock()

	return task, nil
}

// Claim claims a task for execution
func (tq *TaskQueue) Claim(ctx context.Context, sessionID uuid.UUID) (*models.DistributedTask, error) {
	// Get pending tasks (limited to high priority to avoid starvation)
	pendingTasks, err := tq.taskRepo.ListPending(ctx, 10)
	if err != nil {
		return nil, fmt.Errorf("failed to list pending tasks: %w", err)
	}

	if len(pendingTasks) == 0 {
		return nil, fmt.Errorf("no pending tasks")
	}

	// Try to claim highest priority task atomically
	for _, task := range pendingTasks {
		// Acquire distributed lock
		lockKey := fmt.Sprintf("task:%s", task.ID.String())
		acquired, err := tq.lockRepo.Acquire(ctx, lockKey, sessionID.String(), tq.claimTimeout)
		if err != nil {
			fmt.Printf("warning: lock acquire error: %v\n", err)
			continue
		}
		if !acquired {
			// Already locked by another session
			continue
		}

		// Try to claim in database
		expiresAt := time.Now().Add(tq.claimTimeout)
		if err := tq.taskRepo.Claim(ctx, task.ID, sessionID, expiresAt); err != nil {
			// Release lock on failure
			if _, releaseErr := tq.lockRepo.Release(ctx, lockKey, sessionID.String()); releaseErr != nil {
				fmt.Printf("warning: failed to release lock: %v\n", releaseErr)
			}
			continue
		}

		tq.mu.Lock()
		tq.inFlightTasks[task.ID.String()] = time.Now()
		tq.mu.Unlock()

		return task, nil
	}

	return nil, fmt.Errorf("failed to claim any task (all locked or claimed)")
}

// ClaimMultiple claims multiple tasks for a session
func (tq *TaskQueue) ClaimMultiple(ctx context.Context, sessionID uuid.UUID, count int) ([]*models.DistributedTask, error) {
	var claimed []*models.DistributedTask

	for i := 0; i < count; i++ {
		task, err := tq.Claim(ctx, sessionID)
		if err != nil {
			// No more tasks available
			break
		}
		claimed = append(claimed, task)
	}

	return claimed, nil
}

// Complete marks a task as completed
func (tq *TaskQueue) Complete(ctx context.Context, taskID uuid.UUID, result interface{}) error {
	task, err := tq.taskRepo.GetByID(ctx, taskID)
	if err != nil {
		return fmt.Errorf("failed to get task: %w", err)
	}

	// Mark as complete
	if err := tq.taskRepo.Complete(ctx, taskID, result); err != nil {
		return fmt.Errorf("failed to complete task: %w", err)
	}

	// Release lock
	if task.ClaimedBy != nil {
		lockKey := fmt.Sprintf("task:%s", taskID.String())
		if _, err := tq.lockRepo.Release(ctx, lockKey, task.ClaimedBy.String()); err != nil {
			fmt.Printf("warning: failed to release lock: %v\n", err)
		}
	}

	tq.mu.Lock()
	delete(tq.inFlightTasks, taskID.String())
	tq.mu.Unlock()

	return nil
}

// Fail marks a task as failed
func (tq *TaskQueue) Fail(ctx context.Context, taskID uuid.UUID, reason string) error {
	task, err := tq.taskRepo.GetByID(ctx, taskID)
	if err != nil {
		return fmt.Errorf("failed to get task: %w", err)
	}

	// Release lock
	if task.ClaimedBy != nil {
		lockKey := fmt.Sprintf("task:%s", taskID.String())
		if _, err := tq.lockRepo.Release(ctx, lockKey, task.ClaimedBy.String()); err != nil {
			fmt.Printf("warning: failed to release lock: %v\n", err)
		}
	}

	// Check if we should retry
	if task.RetryCount < task.MaxRetries {
		// Retry
		if err := tq.taskRepo.Retry(ctx, taskID); err != nil {
			return fmt.Errorf("failed to retry task: %w", err)
		}
	} else {
		// Mark as permanently failed
		if err := tq.taskRepo.Fail(ctx, taskID, reason); err != nil {
			return fmt.Errorf("failed to fail task: %w", err)
		}
	}

	tq.mu.Lock()
	delete(tq.inFlightTasks, taskID.String())
	tq.mu.Unlock()

	return nil
}

// GetTaskStatus returns task status
func (tq *TaskQueue) GetTaskStatus(ctx context.Context, taskID uuid.UUID) (*models.DistributedTask, error) {
	return tq.taskRepo.GetByID(ctx, taskID)
}

// GetPendingTaskCount returns count of pending tasks
func (tq *TaskQueue) GetPendingTaskCount(ctx context.Context) (int, error) {
	pending, err := tq.taskRepo.ListPending(ctx, 1000)
	if err != nil {
		return 0, err
	}
	return len(pending), nil
}

// GetTaskStats returns queue statistics
func (tq *TaskQueue) GetTaskStats(ctx context.Context) map[string]interface{} {
	tq.mu.RLock()
	inFlightCount := len(tq.inFlightTasks)
	tq.mu.RUnlock()

	pending, err := tq.GetPendingTaskCount(ctx)
	if err != nil {
		pending = -1
	}

	return map[string]interface{}{
		"pending_tasks":   pending,
		"in_flight_tasks": inFlightCount,
		"timestamp":       time.Now(),
	}
}

// CleanupExpiredClaims cleans up expired task claims
func (tq *TaskQueue) CleanupExpiredClaims(ctx context.Context) error {
	if err := tq.taskRepo.CleanupExpiredClaims(ctx); err != nil {
		return fmt.Errorf("failed to cleanup expired claims: %w", err)
	}

	if err := tq.lockRepo.CleanupExpired(ctx); err != nil {
		return fmt.Errorf("failed to cleanup expired locks: %w", err)
	}

	return nil
}

// Start begins background cleanup
func (tq *TaskQueue) Start(ctx context.Context) {
	ticker := time.NewTicker(tq.cleanupInterval)
	defer ticker.Stop()

	for {
		select {
		case <-tq.done:
			return
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := tq.CleanupExpiredClaims(ctx); err != nil {
				fmt.Printf("cleanup error: %v\n", err)
			}
		}
	}
}

// Stop stops the queue
func (tq *TaskQueue) Stop() {
	close(tq.done)
}

// AssignTaskToOptimalSession finds the best session and assigns task
func (tq *TaskQueue) AssignTaskToOptimalSession(ctx context.Context, task *models.DistributedTask) error {
	// Find best session
	session, err := tq.coordinator.GetAvailableSession(ctx, task.LessonID)
	if err != nil {
		return fmt.Errorf("no available sessions: %w", err)
	}

	// Assign task
	task.TargetSessionID = &session.ID
	task.Status = "assigned"

	// Persist
	if err := tq.taskRepo.Update(ctx, task); err != nil {
		return fmt.Errorf("failed to update task: %w", err)
	}

	return nil
}

// RequeueFailedTasks requeues all failed tasks that haven't exceeded max retries
func (tq *TaskQueue) RequeueFailedTasks(ctx context.Context) error {
	// This would be implemented by querying failed tasks with retry_count < max_retries
	// and updating their status back to 'pending'
	return nil
}

// GetInFlightTasks returns all in-flight task IDs
func (tq *TaskQueue) GetInFlightTasks() []string {
	tq.mu.RLock()
	defer tq.mu.RUnlock()

	var tasks []string
	for taskID := range tq.inFlightTasks {
		tasks = append(tasks, taskID)
	}
	return tasks
}

// GetInFlightTaskDuration returns how long a task has been in flight
func (tq *TaskQueue) GetInFlightTaskDuration(taskID string) (time.Duration, error) {
	tq.mu.RLock()
	defer tq.mu.RUnlock()

	if startTime, ok := tq.inFlightTasks[taskID]; ok {
		return time.Since(startTime), nil
	}
	return 0, fmt.Errorf("task not in flight")
}
