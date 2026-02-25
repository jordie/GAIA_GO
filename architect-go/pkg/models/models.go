package models

import (
	"encoding/json"
	"time"

	"gorm.io/gorm"
)

// Project represents a project in the system
type Project struct {
	ID          string                 `gorm:"primaryKey;column:id" json:"id"`
	Name        string                 `gorm:"column:name;type:varchar(255);not null" json:"name"`
	Description string                 `gorm:"column:description;type:text" json:"description"`
	Status      string                 `gorm:"column:status;type:varchar(50);default:active" json:"status"`
	Metadata    json.RawMessage     `gorm:"column:metadata;type:jsonb" json:"metadata"`
	CreatedAt   time.Time              `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	UpdatedAt   time.Time              `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
	DeletedAt   gorm.DeletedAt         `gorm:"column:deleted_at;index" json:"-"`
}

// Task represents a task within a project
type Task struct {
	ID          string                 `gorm:"primaryKey;column:id" json:"id"`
	ProjectID   string                 `gorm:"column:project_id;type:varchar(36);not null;index" json:"project_id"`
	Title       string                 `gorm:"column:title;type:varchar(255);not null" json:"title"`
	Description string                 `gorm:"column:description;type:text" json:"description"`
	Status      string                 `gorm:"column:status;type:varchar(50);default:pending" json:"status"`
	Priority    int                    `gorm:"column:priority;default:0" json:"priority"`
	AssignedTo  string                 `gorm:"column:assigned_to;type:varchar(36)" json:"assigned_to"`
	Metadata    json.RawMessage     `gorm:"column:metadata;type:jsonb" json:"metadata"`
	CreatedAt   time.Time              `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	UpdatedAt   time.Time              `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
	DeletedAt   gorm.DeletedAt         `gorm:"column:deleted_at;index" json:"-"`

	// Relationships
	Project *Project `gorm:"foreignKey:ProjectID;references:ID" json:"-"`
}

// Worker represents a background worker process
type Worker struct {
	ID            string                 `gorm:"primaryKey;column:id" json:"id"`
	Type          string                 `gorm:"column:type;type:varchar(100);not null;index" json:"type"`
	Status        string                 `gorm:"column:status;type:varchar(50);default:idle" json:"status"`
	LastHeartbeat *time.Time             `gorm:"column:last_heartbeat" json:"last_heartbeat"`
	Metadata      json.RawMessage     `gorm:"column:metadata;type:jsonb" json:"metadata"`
	CreatedAt     time.Time              `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	UpdatedAt     time.Time              `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
	DeletedAt     gorm.DeletedAt         `gorm:"column:deleted_at;index" json:"-"`
}

// WorkerQueue represents tasks in the worker queue
type WorkerQueue struct {
	ID            string                 `gorm:"primaryKey;column:id" json:"id"`
	WorkerType    string                 `gorm:"column:worker_type;type:varchar(100);not null;index" json:"worker_type"`
	TaskData      json.RawMessage     `gorm:"column:task_data;type:jsonb;not null" json:"task_data"`
	Status        string                 `gorm:"column:status;type:varchar(50);default:pending;index" json:"status"`
	Priority      int                    `gorm:"column:priority;default:0" json:"priority"`
	RetryCount    int                    `gorm:"column:retry_count;default:0" json:"retry_count"`
	MaxRetries    int                    `gorm:"column:max_retries;default:3" json:"max_retries"`
	Error         string                 `gorm:"column:error;type:text" json:"error"`
	AssignedToID  string                 `gorm:"column:assigned_to_id;type:varchar(36)" json:"assigned_to_id"`
	ScheduledAt   *time.Time             `gorm:"column:scheduled_at;index" json:"scheduled_at"`
	StartedAt     *time.Time             `gorm:"column:started_at" json:"started_at"`
	CompletedAt   *time.Time             `gorm:"column:completed_at" json:"completed_at"`
	CreatedAt     time.Time              `gorm:"column:created_at;autoCreateTime;index" json:"created_at"`
	UpdatedAt     time.Time              `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
	DeletedAt     gorm.DeletedAt         `gorm:"column:deleted_at;index" json:"-"`
}

// User represents a user account
type User struct {
	ID            string                 `gorm:"primaryKey;column:id" json:"id"`
	Username      string                 `gorm:"column:username;type:varchar(100);unique;not null" json:"username"`
	Email         string                 `gorm:"column:email;type:varchar(255);unique;not null" json:"email"`
	PasswordHash  string                 `gorm:"column:password_hash;type:varchar(255);not null" json:"-"`
	FullName      string                 `gorm:"column:full_name;type:varchar(255)" json:"full_name"`
	Status        string                 `gorm:"column:status;type:varchar(50);default:active" json:"status"`
	LastLoginAt   *time.Time             `gorm:"column:last_login_at" json:"last_login_at"`
	Metadata      json.RawMessage     `gorm:"column:metadata;type:jsonb" json:"metadata"`
	CreatedAt     time.Time              `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	UpdatedAt     time.Time              `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
	DeletedAt     gorm.DeletedAt         `gorm:"column:deleted_at;index" json:"-"`
}

// Session represents a user session
type Session struct {
	ID        string        `gorm:"primaryKey;column:id" json:"id"`
	UserID    string        `gorm:"column:user_id;type:varchar(36);not null;index" json:"user_id"`
	Token     string        `gorm:"column:token;type:varchar(500);not null;uniqueIndex" json:"token"`
	ExpiresAt time.Time     `gorm:"column:expires_at;index" json:"expires_at"`
	CreatedAt time.Time     `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	UpdatedAt time.Time     `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
	DeletedAt gorm.DeletedAt `gorm:"column:deleted_at;index" json:"-"`

	// Relationships
	User *User `gorm:"foreignKey:UserID;references:ID" json:"-"`
}

// EventLog represents system events
type EventLog struct {
	ID        string                 `gorm:"primaryKey;column:id" json:"id"`
	EventType string                 `gorm:"column:event_type;type:varchar(100);not null;index" json:"event_type"`
	Source    string                 `gorm:"column:source;type:varchar(255);not null" json:"source"`
	UserID    string                 `gorm:"column:user_id;type:varchar(36);index" json:"user_id"`
	Data      json.RawMessage        `gorm:"column:data;type:jsonb" json:"data"`
	Message   string                 `gorm:"column:message;type:text" json:"message"`
	ProjectID string                 `gorm:"column:project_id;type:varchar(36);index" json:"project_id"`
	Metadata  json.RawMessage        `gorm:"column:metadata;type:jsonb" json:"metadata"`
	Tags      json.RawMessage        `gorm:"column:tags;type:jsonb" json:"tags"`
	Timestamp time.Time              `gorm:"column:timestamp;index" json:"timestamp"`
	CreatedAt time.Time              `gorm:"column:created_at;autoCreateTime;index" json:"created_at"`
	DeletedAt gorm.DeletedAt         `gorm:"column:deleted_at;index" json:"-"`
}

// ErrorLog represents errors in the system
type ErrorLog struct {
	ID         string                 `gorm:"primaryKey;column:id" json:"id"`
	ErrorType  string                 `gorm:"column:error_type;type:varchar(100);not null;index" json:"error_type"`
	Message    string                 `gorm:"column:message;type:text;not null" json:"message"`
	Source     string                 `gorm:"column:source;type:varchar(255);not null" json:"source"`
	StackTrace string                 `gorm:"column:stack_trace;type:text" json:"stack_trace"`
	Severity   string                 `gorm:"column:severity;type:varchar(50);default:error" json:"severity"`
	Count      int                    `gorm:"column:count;default:1" json:"count"`
	LastOccur  *time.Time             `gorm:"column:last_occur" json:"last_occur"`
	Data       json.RawMessage        `gorm:"column:data;type:jsonb" json:"data"`
	Timestamp  time.Time              `gorm:"column:timestamp;index" json:"timestamp"`
	Status     string                 `gorm:"column:status;type:varchar(50)" json:"status"`
	Metadata   json.RawMessage        `gorm:"column:metadata;type:jsonb" json:"metadata"`
	Tags       json.RawMessage        `gorm:"column:tags;type:jsonb" json:"tags"`
	CreatedAt  time.Time              `gorm:"column:created_at;autoCreateTime;index" json:"created_at"`
	UpdatedAt  time.Time              `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
	DeletedAt  gorm.DeletedAt         `gorm:"column:deleted_at;index" json:"-"`
}

// Notification represents a notification to send
type Notification struct {
	ID        string                 `gorm:"primaryKey;column:id" json:"id"`
	UserID    string                 `gorm:"column:user_id;type:varchar(36);not null;index" json:"user_id"`
	Type      string                 `gorm:"column:type;type:varchar(100);not null" json:"type"`
	Title     string                 `gorm:"column:title;type:varchar(255)" json:"title"`
	Message   string                 `gorm:"column:message;type:text" json:"message"`
	Data      json.RawMessage     `gorm:"column:data;type:jsonb" json:"data"`
	Status    string                 `gorm:"column:status;type:varchar(50);default:pending" json:"status"`
	ReadAt    *time.Time             `gorm:"column:read_at" json:"read_at"`
	CreatedAt time.Time              `gorm:"column:created_at;autoCreateTime;index" json:"created_at"`
	UpdatedAt time.Time              `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
	DeletedAt gorm.DeletedAt         `gorm:"column:deleted_at;index" json:"-"`
}

// Integration represents a third-party integration configuration
type Integration struct {
	ID          string                 `gorm:"primaryKey;column:id" json:"id"`
	Name        string                 `gorm:"column:name;type:varchar(100);not null" json:"name"`
	Type        string                 `gorm:"column:type;type:varchar(100);not null;index" json:"type"`
	Provider    string                 `gorm:"column:provider;type:varchar(100)" json:"provider"`
	Config      json.RawMessage        `gorm:"column:config;type:jsonb" json:"config"`
	Enabled     bool                   `gorm:"column:enabled;default:true" json:"enabled"`
	Status      string                 `gorm:"column:status;type:varchar(50);default:inactive" json:"status"`
	LastSyncAt  *time.Time             `gorm:"column:last_sync_at" json:"last_sync_at"`
	CreatedAt   time.Time              `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	UpdatedAt   time.Time              `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
	DeletedAt   gorm.DeletedAt         `gorm:"column:deleted_at;index" json:"-"`
}

// AuditLog represents an audit trail entry (append-only, immutable)
type AuditLog struct {
	ID         string                 `gorm:"primaryKey;column:id" json:"id"`
	UserID     string                 `gorm:"column:user_id;type:varchar(36);index" json:"user_id"`
	Action     string                 `gorm:"column:action;type:varchar(100);index" json:"action"`
	Resource   string                 `gorm:"column:resource;type:varchar(100)" json:"resource"`
	ResourceID string                 `gorm:"column:resource_id;type:varchar(100);index" json:"resource_id"`
	Changes    json.RawMessage        `gorm:"column:changes;type:jsonb" json:"changes"`
	Details    json.RawMessage        `gorm:"column:details;type:jsonb" json:"details"`
	Timestamp  time.Time              `gorm:"column:timestamp;index" json:"timestamp"`
	Status     string                 `gorm:"column:status;type:varchar(50)" json:"status"`
	CreatedAt  time.Time              `gorm:"column:created_at;autoCreateTime" json:"created_at"`
}

// Bug represents a bug report
type Bug struct {
	ID          string                 `gorm:"primaryKey;column:id" json:"id"`
	ProjectID   string                 `gorm:"column:project_id;type:varchar(36);index" json:"project_id"`
	Title       string                 `gorm:"column:title;type:varchar(255);not null" json:"title"`
	Description string                 `gorm:"column:description;type:text" json:"description"`
	Status      string                 `gorm:"column:status;type:varchar(50);default:open" json:"status"`
	Severity    string                 `gorm:"column:severity;type:varchar(50)" json:"severity"`
	Metadata    json.RawMessage     `gorm:"column:metadata;type:jsonb" json:"metadata"`
	CreatedAt   time.Time              `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	UpdatedAt   time.Time              `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
	DeletedAt   gorm.DeletedAt         `gorm:"column:deleted_at;index" json:"-"`
}

// NotificationTemplate represents a notification template
type NotificationTemplate struct {
	ID        string                 `gorm:"primaryKey;column:id" json:"id"`
	Name      string                 `gorm:"column:name;type:varchar(255);not null;unique" json:"name"`
	Subject   string                 `gorm:"column:subject;type:varchar(255)" json:"subject"`
	Body      string                 `gorm:"column:body;type:text" json:"body"`
	Type      string                 `gorm:"column:type;type:varchar(50)" json:"type"`
	Metadata  json.RawMessage     `gorm:"column:metadata;type:jsonb" json:"metadata"`
	CreatedAt time.Time              `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	UpdatedAt time.Time              `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
	DeletedAt gorm.DeletedAt         `gorm:"column:deleted_at;index" json:"-"`
}

// Webhook represents a webhook configuration
type Webhook struct {
	ID        string                 `gorm:"primaryKey;column:id" json:"id"`
	ProjectID string                 `gorm:"column:project_id;type:varchar(36);index" json:"project_id"`
	URL       string                 `gorm:"column:url;type:varchar(1000);not null" json:"url"`
	Events    json.RawMessage     `gorm:"column:events;type:jsonb" json:"events"`
	Active    bool                   `gorm:"column:active;default:true" json:"active"`
	Metadata  json.RawMessage     `gorm:"column:metadata;type:jsonb" json:"metadata"`
	CreatedAt time.Time              `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	UpdatedAt time.Time              `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
	DeletedAt gorm.DeletedAt         `gorm:"column:deleted_at;index" json:"-"`
}

// TableName specifies the table name for each model
func (Project) TableName() string {
	return "projects"
}

func (Task) TableName() string {
	return "tasks"
}

func (Worker) TableName() string {
	return "workers"
}

func (WorkerQueue) TableName() string {
	return "worker_queue"
}

func (User) TableName() string {
	return "users"
}

func (Session) TableName() string {
	return "sessions"
}

func (EventLog) TableName() string {
	return "event_logs"
}

func (ErrorLog) TableName() string {
	return "error_logs"
}

func (Notification) TableName() string {
	return "notifications"
}

func (Integration) TableName() string {
	return "integrations"
}

func (AuditLog) TableName() string {
	return "audit_logs"
}

func (Bug) TableName() string {
	return "bugs"
}

func (NotificationTemplate) TableName() string {
	return "notification_templates"
}

func (Webhook) TableName() string {
	return "webhooks"
}

func (Presence) TableName() string {
	return "presences"
}

func (Activity) TableName() string {
	return "activities"
}

// Presence represents a user's current online status and activity
type Presence struct {
	ID        string          `gorm:"primaryKey;column:id" json:"id"`
	UserID    string          `gorm:"column:user_id;type:varchar(36);not null;uniqueIndex" json:"user_id"`
	Status    string          `gorm:"column:status;type:varchar(50);default:offline;index" json:"status"`
	LastSeenAt time.Time      `gorm:"column:last_seen_at;not null;index" json:"last_seen_at"`
	DeviceInfo json.RawMessage `gorm:"column:device_info;type:jsonb" json:"device_info"`
	Metadata  json.RawMessage `gorm:"column:metadata;type:jsonb" json:"metadata"`
	CreatedAt time.Time       `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	UpdatedAt time.Time       `gorm:"column:updated_at;autoUpdateTime" json:"updated_at"`
	DeletedAt gorm.DeletedAt  `gorm:"column:deleted_at;index" json:"-"`

	// Relationships
	User *User `gorm:"foreignKey:UserID;references:ID" json:"-"`
}

// Activity represents a user's action or event in the system
type Activity struct {
	ID           string          `gorm:"primaryKey;column:id" json:"id"`
	UserID       string          `gorm:"column:user_id;type:varchar(36);not null;index" json:"user_id"`
	Action       string          `gorm:"column:action;type:varchar(100);not null;index" json:"action"`
	ResourceType string          `gorm:"column:resource_type;type:varchar(100);index" json:"resource_type"`
	ResourceID   string          `gorm:"column:resource_id;type:varchar(36);index" json:"resource_id"`
	Metadata     json.RawMessage `gorm:"column:metadata;type:jsonb" json:"metadata"`
	Timestamp    time.Time       `gorm:"column:timestamp;not null;index" json:"timestamp"`
	CreatedAt    time.Time       `gorm:"column:created_at;autoCreateTime" json:"created_at"`
	DeletedAt    gorm.DeletedAt  `gorm:"column:deleted_at;index" json:"-"`

	// Relationships
	User *User `gorm:"foreignKey:UserID;references:ID" json:"-"`
}
