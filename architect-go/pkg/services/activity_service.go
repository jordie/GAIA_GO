package services

import (
	"context"

	"architect-go/pkg/models"
	"architect-go/pkg/repository"
)

// ActivityService defines the interface for activity management
type ActivityService interface {
	// LogActivity logs a user's action
	LogActivity(ctx context.Context, userID, action, resourceType, resourceID string, metadata map[string]interface{}) error

	// GetUserActivity retrieves activities for a specific user with pagination
	GetUserActivity(ctx context.Context, userID string, limit, offset int) ([]models.Activity, int64, error)

	// GetProjectActivity retrieves activities for a specific project/resource with pagination
	GetProjectActivity(ctx context.Context, resourceType, resourceID string, limit, offset int) ([]models.Activity, int64, error)

	// FilterActivity retrieves activities matching filters with pagination
	FilterActivity(ctx context.Context, filters repository.ActivityFilters, limit, offset int) ([]models.Activity, int64, error)

	// GetActivityStats returns statistics of user's activities
	GetActivityStats(ctx context.Context, userID string) (map[string]int64, error)

	// GetRecentActivity retrieves the most recent system-wide activities
	GetRecentActivity(ctx context.Context, limit int) ([]models.Activity, error)

	// DeleteActivity soft-deletes an activity record
	DeleteActivity(ctx context.Context, activityID string) error

	// CleanupOldActivities removes activities older than specified days
	CleanupOldActivities(ctx context.Context, daysOld int) (int64, error)
}
