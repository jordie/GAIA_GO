package repository

import (
	"context"

	"architect-go/pkg/models"
)

// ActivityFilters represents filters for querying activities
type ActivityFilters struct {
	UserID       string
	Action       string
	ResourceType string
	ResourceID   string
	StartTime    interface{} // time.Time
	EndTime      interface{} // time.Time
}

// ActivityRepository defines the interface for activity data access
type ActivityRepository interface {
	// LogActivity creates a new activity record
	LogActivity(ctx context.Context, activity *models.Activity) error

	// GetUserActivity retrieves activities for a specific user with pagination
	GetUserActivity(ctx context.Context, userID string, limit, offset int) ([]models.Activity, error)

	// GetUserActivityCount returns the total count of activities for a user
	GetUserActivityCount(ctx context.Context, userID string) (int64, error)

	// GetProjectActivity retrieves activities for a specific project with pagination
	GetProjectActivity(ctx context.Context, resourceType, resourceID string, limit, offset int) ([]models.Activity, error)

	// GetProjectActivityCount returns the total count of activities for a project
	GetProjectActivityCount(ctx context.Context, resourceType, resourceID string) (int64, error)

	// FilterActivity retrieves activities matching the provided filters with pagination
	FilterActivity(ctx context.Context, filters ActivityFilters, limit, offset int) ([]models.Activity, error)

	// FilterActivityCount returns the total count of activities matching the filters
	FilterActivityCount(ctx context.Context, filters ActivityFilters) (int64, error)

	// GetActivityStats returns activity statistics for a user
	GetActivityStats(ctx context.Context, userID string) (map[string]int64, error)

	// GetRecentActivity retrieves the most recent activities system-wide
	GetRecentActivity(ctx context.Context, limit int) ([]models.Activity, error)

	// DeleteActivity soft-deletes an activity record
	DeleteActivity(ctx context.Context, activityID string) error

	// GetActivity retrieves a single activity by ID
	GetActivity(ctx context.Context, activityID string) (*models.Activity, error)

	// DeleteOldActivities soft-deletes activities older than the specified days
	DeleteOldActivities(ctx context.Context, daysOld int) (int64, error)
}
