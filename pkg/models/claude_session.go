package models

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// ClaudeSession represents a distributed Claude Code session
type ClaudeSession struct {
	ID                  uuid.UUID       `json:"id" gorm:"type:uuid;primary_key"`
	SessionName         string          `json:"session_name" gorm:"type:varchar(255);uniqueIndex"`
	UserID              *uuid.UUID      `json:"user_id" gorm:"type:uuid;index"`
	Tier                string          `json:"tier" gorm:"type:varchar(50);index"`                           // 'high_level', 'manager', 'worker'
	Provider            string          `json:"provider" gorm:"type:varchar(50);index"`                       // 'claude', 'codex', 'ollama', 'openai', 'gemini'
	Status              string          `json:"status" gorm:"type:varchar(50);index;default:'idle'"`         // 'idle', 'busy', 'paused', 'failed', 'offline'
	LessonID            *uuid.UUID      `json:"lesson_id" gorm:"type:uuid;index"`
	TimeWindowStart     *time.Time      `json:"time_window_start"`
	TimeWindowEnd       *time.Time      `json:"time_window_end"`
	LastHeartbeat       time.Time       `json:"last_heartbeat" gorm:"index"`
	HealthStatus        string          `json:"health_status" gorm:"type:varchar(50);default:'healthy'"`    // 'healthy', 'degraded', 'unhealthy'
	ConsecutiveFailures int             `json:"consecutive_failures" gorm:"default:0"`
	MaxConcurrentTasks  int             `json:"max_concurrent_tasks" gorm:"default:1"`
	CurrentTaskCount    int             `json:"current_task_count" gorm:"default:0"`
	Metadata            json.RawMessage `json:"metadata" gorm:"type:jsonb"`
	CreatedAt           time.Time       `json:"created_at" gorm:"index"`
	UpdatedAt           time.Time       `json:"updated_at"`
}

// TableName specifies the table name for GORM
func (ClaudeSession) TableName() string {
	return "claude_sessions"
}

// Lesson represents a task grouping by learning objective
type Lesson struct {
	ID                    uuid.UUID       `json:"id" gorm:"type:uuid;primary_key"`
	ProjectID             *uuid.UUID      `json:"project_id" gorm:"type:uuid;index"`
	Title                 string          `json:"title" gorm:"type:varchar(255)"`
	Description           string          `json:"description" gorm:"type:text"`
	Status                string          `json:"status" gorm:"type:varchar(50);index;default:'pending'"`    // 'pending', 'in_progress', 'completed', 'archived'
	Priority              int             `json:"priority" gorm:"index"`
	TasksTotal            int             `json:"tasks_total" gorm:"default:0"`
	TasksCompleted        int             `json:"tasks_completed" gorm:"default:0"`
	EstimatedDurationMins *int            `json:"estimated_duration_minutes"`
	Metadata              json.RawMessage `json:"metadata" gorm:"type:jsonb"`
	CreatedAt             time.Time       `json:"created_at"`
	UpdatedAt             time.Time       `json:"updated_at"`
}

// TableName specifies the table name for GORM
func (Lesson) TableName() string {
	return "lessons"
}

// DistributedTask represents a task in the distributed queue
type DistributedTask struct {
	ID              uuid.UUID       `json:"id" gorm:"type:uuid;primary_key"`
	IdempotencyKey  string          `json:"idempotency_key" gorm:"type:varchar(255);uniqueIndex"`
	TaskType        string          `json:"task_type" gorm:"type:varchar(100)"`
	TaskData        json.RawMessage `json:"task_data" gorm:"type:jsonb"`
	Priority        int             `json:"priority" gorm:"index"`
	LessonID        *uuid.UUID      `json:"lesson_id" gorm:"type:uuid;index"`
	TargetSessionID *uuid.UUID      `json:"target_session_id" gorm:"type:uuid;index"`
	Status          string          `json:"status" gorm:"type:varchar(50);index;default:'pending'"`        // 'pending', 'assigned', 'in_progress', 'completed', 'failed', 'cancelled'
	ClaimedBy       *uuid.UUID      `json:"claimed_by" gorm:"type:uuid;index"`
	ClaimedAt       *time.Time      `json:"claimed_at"`
	ClaimExpiresAt  *time.Time      `json:"claim_expires_at" gorm:"index"`
	RetryCount      int             `json:"retry_count" gorm:"default:0"`
	MaxRetries      int             `json:"max_retries" gorm:"default:3"`
	Result          json.RawMessage `json:"result" gorm:"type:jsonb"`
	ErrorMessage    string          `json:"error_message" gorm:"type:text"`
	CreatedAt       time.Time       `json:"created_at" gorm:"index"`
	UpdatedAt       time.Time       `json:"updated_at"`
}

// TableName specifies the table name for GORM
func (DistributedTask) TableName() string {
	return "distributed_task_queue"
}

// DistributedLock represents a distributed lock
type DistributedLock struct {
	LockKey    string          `json:"lock_key" gorm:"type:varchar(255);primary_key"`
	OwnerID    string          `json:"owner_id" gorm:"type:varchar(255);index"`
	AcquiredAt time.Time       `json:"acquired_at"`
	ExpiresAt  time.Time       `json:"expires_at" gorm:"index"`
	RenewedCount int           `json:"renewed_count" gorm:"default:0"`
	Metadata   json.RawMessage `json:"metadata" gorm:"type:jsonb"`
}

// TableName specifies the table name for GORM
func (DistributedLock) TableName() string {
	return "distributed_locks"
}

// SessionAffinity represents time-window and lesson-based scheduling
type SessionAffinity struct {
	ID              uuid.UUID  `json:"id" gorm:"type:uuid;primary_key"`
	SessionID       uuid.UUID  `json:"session_id" gorm:"type:uuid;index"`
	LessonID        *uuid.UUID `json:"lesson_id" gorm:"type:uuid;index"`
	TimeWindowStart *time.Time `json:"time_window_start"`
	TimeWindowEnd   *time.Time `json:"time_window_end"`
	AffinityScore   float64    `json:"affinity_score" gorm:"default:1.0"`
	LastUsed        *time.Time `json:"last_used"`
	CreatedAt       time.Time  `json:"created_at"`
}

// TableName specifies the table name for GORM
func (SessionAffinity) TableName() string {
	return "session_affinity"
}

// IsActive checks if the session is currently active
func (cs *ClaudeSession) IsActive() bool {
	return time.Since(cs.LastHeartbeat) < 30*time.Second && cs.Status != "offline" && cs.Status != "failed"
}

// IsHealthy checks if the session is in a healthy state
func (cs *ClaudeSession) IsHealthy() bool {
	return cs.HealthStatus == "healthy" && cs.ConsecutiveFailures == 0
}

// CanTakeTask checks if the session can take on more work
func (cs *ClaudeSession) CanTakeTask() bool {
	return cs.IsActive() && cs.IsHealthy() && cs.CurrentTaskCount < cs.MaxConcurrentTasks
}

// MarshalJSON implements json.Marshaler
func (cs *ClaudeSession) MarshalJSON() ([]byte, error) {
	type Alias ClaudeSession
	return json.Marshal(&struct {
		*Alias
		IsActive bool `json:"is_active"`
		IsHealthy bool `json:"is_healthy"`
		CanTakeTask bool `json:"can_take_task"`
	}{
		Alias:      (*Alias)(cs),
		IsActive:   cs.IsActive(),
		IsHealthy:  cs.IsHealthy(),
		CanTakeTask: cs.CanTakeTask(),
	})
}

// String implements fmt.Stringer
func (cs *ClaudeSession) String() string {
	return "ClaudeSession{name:" + cs.SessionName + ", tier:" + cs.Tier + ", status:" + cs.Status + "}"
}

// IsExpired checks if a distributed lock has expired
func (dl *DistributedLock) IsExpired() bool {
	return time.Now().After(dl.ExpiresAt)
}

// ProgressPercentage returns the progress percentage for a lesson
func (l *Lesson) ProgressPercentage() float64 {
	if l.TasksTotal == 0 {
		return 0
	}
	return float64(l.TasksCompleted) / float64(l.TasksTotal) * 100
}

// Note: json.RawMessage already implements sql.Scanner and driver.Valuer
// via GORM's builtin support for JSON types, so no custom methods needed
