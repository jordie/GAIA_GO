package services

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"architect-go/pkg/models"
	"architect-go/pkg/repository"
)

// ActivityServiceImpl implements ActivityService
type ActivityServiceImpl struct {
	repo repository.ActivityRepository
}

// NewActivityService creates a new activity service
func NewActivityService(repo repository.ActivityRepository) ActivityService {
	return &ActivityServiceImpl{
		repo: repo,
	}
}

// LogActivity logs a user's action
func (s *ActivityServiceImpl) LogActivity(ctx context.Context, userID, action, resourceType, resourceID string, metadata map[string]interface{}) error {
	activity := &models.Activity{
		UserID:       userID,
		Action:       action,
		ResourceType: resourceType,
		ResourceID:   resourceID,
		Timestamp:    time.Now(),
	}

	if metadata != nil {
		if data, err := json.Marshal(metadata); err == nil {
			activity.Metadata = data
		}
	}

	if err := s.repo.LogActivity(ctx, activity); err != nil {
		return fmt.Errorf("failed to log activity: %w", err)
	}

	return nil
}

// GetUserActivity retrieves activities for a specific user with pagination
func (s *ActivityServiceImpl) GetUserActivity(ctx context.Context, userID string, limit, offset int) ([]models.Activity, int64, error) {
	activities, err := s.repo.GetUserActivity(ctx, userID, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get user activities: %w", err)
	}

	count, err := s.repo.GetUserActivityCount(ctx, userID)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get user activity count: %w", err)
	}

	return activities, count, nil
}

// GetProjectActivity retrieves activities for a specific project/resource with pagination
func (s *ActivityServiceImpl) GetProjectActivity(ctx context.Context, resourceType, resourceID string, limit, offset int) ([]models.Activity, int64, error) {
	activities, err := s.repo.GetProjectActivity(ctx, resourceType, resourceID, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get project activities: %w", err)
	}

	count, err := s.repo.GetProjectActivityCount(ctx, resourceType, resourceID)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get project activity count: %w", err)
	}

	return activities, count, nil
}

// FilterActivity retrieves activities matching filters with pagination
func (s *ActivityServiceImpl) FilterActivity(ctx context.Context, filters repository.ActivityFilters, limit, offset int) ([]models.Activity, int64, error) {
	activities, err := s.repo.FilterActivity(ctx, filters, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to filter activities: %w", err)
	}

	count, err := s.repo.FilterActivityCount(ctx, filters)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get filter activity count: %w", err)
	}

	return activities, count, nil
}

// GetActivityStats returns statistics of user's activities
func (s *ActivityServiceImpl) GetActivityStats(ctx context.Context, userID string) (map[string]int64, error) {
	stats, err := s.repo.GetActivityStats(ctx, userID)
	if err != nil {
		return nil, fmt.Errorf("failed to get activity stats: %w", err)
	}

	return stats, nil
}

// GetRecentActivity retrieves the most recent system-wide activities
func (s *ActivityServiceImpl) GetRecentActivity(ctx context.Context, limit int) ([]models.Activity, error) {
	activities, err := s.repo.GetRecentActivity(ctx, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to get recent activities: %w", err)
	}

	return activities, nil
}

// DeleteActivity soft-deletes an activity record
func (s *ActivityServiceImpl) DeleteActivity(ctx context.Context, activityID string) error {
	if err := s.repo.DeleteActivity(ctx, activityID); err != nil {
		return fmt.Errorf("failed to delete activity: %w", err)
	}

	return nil
}

// CleanupOldActivities removes activities older than specified days
func (s *ActivityServiceImpl) CleanupOldActivities(ctx context.Context, daysOld int) (int64, error) {
	count, err := s.repo.DeleteOldActivities(ctx, daysOld)
	if err != nil {
		return 0, fmt.Errorf("failed to cleanup old activities: %w", err)
	}

	return count, nil
}
