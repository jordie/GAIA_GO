package repository

import (
	"context"
	"time"

	"architect-go/pkg/models"
)

// EventRepository interface
type EventRepository interface {
	GetEventsByDateRange(ctx context.Context, startDate, endDate time.Time) ([]models.Event, error)
	GetEventsByCohort(ctx context.Context, cohortDate time.Time) ([]models.Event, error)
	GetEventsByUserAndDateRange(ctx context.Context, userID string, startDate, endDate time.Time) ([]models.Event, error)
	CreateEvent(ctx context.Context, event *models.Event) error
	GetEvent(ctx context.Context, eventID string) (*models.Event, error)
	GetEvents(ctx context.Context, filters EventFilters, limit, offset int) ([]models.Event, int64, error)
}

// EventFilters represents filtering options for events
type EventFilters struct {
	UserID    string
	Type      string
	ProjectID string
	StartDate time.Time
	EndDate   time.Time
}

// PresenceRepository interface
type PresenceRepository interface {
	GetPresenceHistory(ctx context.Context, userID string, limit, offset int) ([]models.Presence, int64, error)
	UpdatePresence(ctx context.Context, userID, status string, metadata map[string]interface{}) error
	GetPresence(ctx context.Context, userID string) (*models.Presence, error)
}

// ActivityRepository interface
type ActivityRepository interface {
	GetActivities(ctx context.Context, filters ActivityFilters, limit, offset int) ([]models.Activity, int64, error)
	CreateActivity(ctx context.Context, activity *models.Activity) error
	DeleteActivity(ctx context.Context, activityID string) error
}

// ActivityFilters represents filtering options for activities
type ActivityFilters struct {
	UserID       string
	Action       string
	ResourceType string
	ResourceID   string
	StartDate    time.Time
	EndDate      time.Time
}

// UserRepository interface
type UserRepository interface {
	GetUser(ctx context.Context, userID string) (*models.User, error)
	GetUsers(ctx context.Context, limit, offset int) ([]models.User, int64, error)
	GetUserStats(ctx context.Context) (map[string]interface{}, error)
}

// ErrorRepository interface
type ErrorRepository interface {
	GetErrors(ctx context.Context, filters map[string]interface{}, limit, offset int) ([]map[string]interface{}, error)
	GetTopErrors(ctx context.Context, limit int) ([]map[string]interface{}, error)
	GetCriticalErrors(ctx context.Context) ([]map[string]interface{}, error)
}

// MetricsRepository interface
type MetricsRepository interface {
	GetRequestMetrics(ctx context.Context, granularity string) (map[string]interface{}, error)
	GetSystemMetrics(ctx context.Context) (map[string]interface{}, error)
	GetDatabaseMetrics(ctx context.Context) (map[string]interface{}, error)
	GetCacheMetrics(ctx context.Context) (map[string]interface{}, error)
}

// RealTimeRepository interface
type RealTimeRepository interface {
	PublishToChannel(ctx context.Context, channel string, data map[string]interface{}) error
	BroadcastEvent(ctx context.Context, eventType string, data map[string]interface{}) error
}

// Note: QueryBuilder is defined as a concrete type in query_builder.go
// It implements fluent API pattern for building SQL queries

// ProjectRepository interface (placeholder)
type ProjectRepository interface {
	GetProject(ctx context.Context, projectID string) (map[string]interface{}, error)
}

// TaskRepository interface (placeholder)
type TaskRepository interface {
	GetTask(ctx context.Context, taskID string) (map[string]interface{}, error)
}
