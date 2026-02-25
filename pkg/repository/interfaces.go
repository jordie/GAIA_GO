package repository

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/jgirmay/GAIA_GO/pkg/models"
)

// ClaudeSessionRepository defines operations for Claude sessions
type ClaudeSessionRepository interface {
	// Create creates a new session
	Create(ctx context.Context, session *models.ClaudeSession) error

	// GetByName retrieves a session by name
	GetByName(ctx context.Context, sessionName string) (*models.ClaudeSession, error)

	// GetByID retrieves a session by ID
	GetByID(ctx context.Context, id uuid.UUID) (*models.ClaudeSession, error)

	// List retrieves all sessions
	List(ctx context.Context) ([]*models.ClaudeSession, error)

	// ListByStatus retrieves sessions with a specific status
	ListByStatus(ctx context.Context, status string) ([]*models.ClaudeSession, error)

	// ListByTier retrieves sessions by tier
	ListByTier(ctx context.Context, tier string) ([]*models.ClaudeSession, error)

	// Update updates an existing session
	Update(ctx context.Context, session *models.ClaudeSession) error

	// Delete deletes a session
	Delete(ctx context.Context, id uuid.UUID) error

	// UpdateStatus updates session status
	UpdateStatus(ctx context.Context, id uuid.UUID, status string) error

	// UpdateHealthStatus updates health status and resets failures if healthy
	UpdateHealthStatus(ctx context.Context, id uuid.UUID, health string) error

	// RecordHeartbeat records a heartbeat
	RecordHeartbeat(ctx context.Context, id uuid.UUID) error

	// IncrementTaskCount increments current task count
	IncrementTaskCount(ctx context.Context, id uuid.UUID, count int) error

	// GetActiveSessions retrieves sessions active in the last 30 seconds
	GetActiveSessions(ctx context.Context) ([]*models.ClaudeSession, error)

	// GetHealthySessions retrieves sessions with healthy status
	GetHealthySessions(ctx context.Context) ([]*models.ClaudeSession, error)

	// GetAvailableSessions retrieves sessions that can take new tasks
	GetAvailableSessions(ctx context.Context) ([]*models.ClaudeSession, error)
}

// LessonRepository defines operations for lessons
type LessonRepository interface {
	// Create creates a new lesson
	Create(ctx context.Context, lesson *models.Lesson) error

	// GetByID retrieves a lesson by ID
	GetByID(ctx context.Context, id uuid.UUID) (*models.Lesson, error)

	// List retrieves all lessons
	List(ctx context.Context) ([]*models.Lesson, error)

	// ListByProject retrieves lessons for a project
	ListByProject(ctx context.Context, projectID uuid.UUID) ([]*models.Lesson, error)

	// ListByStatus retrieves lessons with a specific status
	ListByStatus(ctx context.Context, status string) ([]*models.Lesson, error)

	// Update updates an existing lesson
	Update(ctx context.Context, lesson *models.Lesson) error

	// Delete deletes a lesson
	Delete(ctx context.Context, id uuid.UUID) error

	// UpdateProgress updates task progress
	UpdateProgress(ctx context.Context, id uuid.UUID, completed int) error
}

// DistributedTaskRepository defines operations for distributed tasks
type DistributedTaskRepository interface {
	// Create creates a new task
	Create(ctx context.Context, task *models.DistributedTask) error

	// GetByID retrieves a task by ID
	GetByID(ctx context.Context, id uuid.UUID) (*models.DistributedTask, error)

	// List retrieves all tasks
	List(ctx context.Context) ([]*models.DistributedTask, error)

	// ListByStatus retrieves tasks with a specific status
	ListByStatus(ctx context.Context, status string) ([]*models.DistributedTask, error)

	// ListPending retrieves pending tasks ordered by priority
	ListPending(ctx context.Context, limit int) ([]*models.DistributedTask, error)

	// ListByLesson retrieves tasks for a lesson
	ListByLesson(ctx context.Context, lessonID uuid.UUID) ([]*models.DistributedTask, error)

	// ListBySession retrieves tasks assigned to a session
	ListBySession(ctx context.Context, sessionID uuid.UUID) ([]*models.DistributedTask, error)

	// Update updates an existing task
	Update(ctx context.Context, task *models.DistributedTask) error

	// Delete deletes a task
	Delete(ctx context.Context, id uuid.UUID) error

	// Claim claims a task for execution
	Claim(ctx context.Context, id uuid.UUID, sessionID uuid.UUID, expiresAt time.Time) error

	// Complete marks a task as completed
	Complete(ctx context.Context, id uuid.UUID, result interface{}) error

	// Fail marks a task as failed
	Fail(ctx context.Context, id uuid.UUID, errorMsg string) error

	// Retry increments retry count and resets status to pending
	Retry(ctx context.Context, id uuid.UUID) error

	// GetByIdempotencyKey retrieves a task by idempotency key
	GetByIdempotencyKey(ctx context.Context, key string) (*models.DistributedTask, error)

	// CleanupExpiredClaims resets expired claims
	CleanupExpiredClaims(ctx context.Context) error

	// ReassignFailedSessionTasks reassigns tasks from a failed session
	ReassignFailedSessionTasks(ctx context.Context, sessionID uuid.UUID) error
}

// DistributedLockRepository defines operations for distributed locks
type DistributedLockRepository interface {
	// Acquire acquires a lock (or renews if already held)
	Acquire(ctx context.Context, lockKey string, ownerID string, ttl time.Duration) (bool, error)

	// Release releases a lock
	Release(ctx context.Context, lockKey string, ownerID string) (bool, error)

	// IsLocked checks if a lock is currently held
	IsLocked(ctx context.Context, lockKey string) (bool, error)

	// GetOwner gets the current lock owner
	GetOwner(ctx context.Context, lockKey string) (string, error)

	// CleanupExpired removes expired locks
	CleanupExpired(ctx context.Context) error

	// GetAll retrieves all locks
	GetAll(ctx context.Context) ([]*models.DistributedLock, error)
}

// SessionAffinityRepository defines operations for session affinity
type SessionAffinityRepository interface {
	// Create creates affinity record
	Create(ctx context.Context, affinity *models.SessionAffinity) error

	// GetForSession retrieves affinity records for a session
	GetForSession(ctx context.Context, sessionID uuid.UUID) ([]*models.SessionAffinity, error)

	// GetForLesson retrieves affinity records for a lesson
	GetForLesson(ctx context.Context, lessonID uuid.UUID) ([]*models.SessionAffinity, error)

	// Update updates affinity record
	Update(ctx context.Context, affinity *models.SessionAffinity) error

	// Delete deletes affinity record
	Delete(ctx context.Context, id uuid.UUID) error

	// GetBestSessionForLesson finds the best-matched session for a lesson
	GetBestSessionForLesson(ctx context.Context, lessonID uuid.UUID) (*models.SessionAffinity, error)

	// UpdateLastUsed updates last_used timestamp
	UpdateLastUsed(ctx context.Context, id uuid.UUID) error
}

// UsabilityMetricsRepository defines operations for usability metrics
type UsabilityMetricsRepository interface {
	// RecordMetric records a new metric
	RecordMetric(ctx context.Context, metric interface{}) error

	// GetStudentMetrics retrieves metrics for a student
	GetStudentMetrics(ctx context.Context, studentID string, appName string, since time.Time) ([]interface{}, error)

	// GetClassroomMetrics retrieves aggregated classroom metrics
	GetClassroomMetrics(ctx context.Context, classroomID string, appName string) (map[string]interface{}, error)

	// GetMetricsByType retrieves metrics by type
	GetMetricsByType(ctx context.Context, metricType string, since time.Time) ([]interface{}, error)
}

// FrustrationEventRepository defines operations for frustration events
type FrustrationEventRepository interface {
	// Create creates a frustration event
	Create(ctx context.Context, event interface{}) error

	// GetUnresolved retrieves unresolved frustration events
	GetUnresolved(ctx context.Context) ([]interface{}, error)

	// GetForStudent retrieves events for a student
	GetForStudent(ctx context.Context, studentID string) ([]interface{}, error)

	// GetBySeverity retrieves events by severity
	GetBySeverity(ctx context.Context, severity string) ([]interface{}, error)

	// Acknowledge marks an event as acknowledged
	Acknowledge(ctx context.Context, id int64) error

	// Resolve marks an event as resolved
	Resolve(ctx context.Context, id int64) error

	// DeleteOld deletes events older than duration
	DeleteOld(ctx context.Context, olderThan time.Duration) error
}

// SatisfactionRatingRepository defines operations for satisfaction ratings
type SatisfactionRatingRepository interface {
	// Create creates a satisfaction rating
	Create(ctx context.Context, rating interface{}) error

	// GetForStudent retrieves ratings for a student
	GetForStudent(ctx context.Context, studentID string) ([]interface{}, error)

	// GetAverageForApp retrieves average rating for an app
	GetAverageForApp(ctx context.Context, appName string) (float64, error)

	// GetRecentRatings retrieves recent ratings
	GetRecentRatings(ctx context.Context, limit int) ([]interface{}, error)

	// GetRecentAverageForStudent retrieves recent average for a student
	GetRecentAverageForStudent(ctx context.Context, studentID string, since time.Time) (float64, error)
}

// TeacherDashboardAlertRepository defines operations for teacher alerts
type TeacherDashboardAlertRepository interface {
	// Create creates a new alert
	Create(ctx context.Context, alert interface{}) error

	// GetForTeacher retrieves alerts for a teacher
	GetForTeacher(ctx context.Context, teacherID uuid.UUID) ([]interface{}, error)

	// GetUnacknowledged retrieves unacknowledged alerts
	GetUnacknowledged(ctx context.Context) ([]interface{}, error)

	// Acknowledge marks an alert as acknowledged
	Acknowledge(ctx context.Context, id uuid.UUID, note string) error

	// GetStrugglingSudents retrieves students with active alerts
	GetStrugglingStudents(ctx context.Context, appName string) ([]string, error)

	// DeleteOld deletes old alerts
	DeleteOld(ctx context.Context, olderThan time.Duration) error
}
