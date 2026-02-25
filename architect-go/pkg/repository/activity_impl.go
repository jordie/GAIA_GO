package repository

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"
	"gorm.io/gorm"

	"architect-go/pkg/models"
)

// activityRepositoryImpl implements ActivityRepository
type activityRepositoryImpl struct {
	db *gorm.DB
}

// NewActivityRepository creates a new activity repository
func NewActivityRepository(db *gorm.DB) ActivityRepository {
	return &activityRepositoryImpl{db: db}
}

// LogActivity creates a new activity record
func (r *activityRepositoryImpl) LogActivity(ctx context.Context, activity *models.Activity) error {
	if activity.ID == "" {
		activity.ID = uuid.New().String()
	}
	if activity.Timestamp.IsZero() {
		activity.Timestamp = time.Now()
	}

	result := r.db.WithContext(ctx).Create(activity)
	return result.Error
}

// GetUserActivity retrieves activities for a specific user with pagination
func (r *activityRepositoryImpl) GetUserActivity(ctx context.Context, userID string, limit, offset int) ([]models.Activity, error) {
	var activities []models.Activity
	result := r.db.WithContext(ctx).
		Where("user_id = ?", userID).
		Order("timestamp DESC").
		Limit(limit).
		Offset(offset).
		Find(&activities)
	return activities, result.Error
}

// GetUserActivityCount returns the total count of activities for a user
func (r *activityRepositoryImpl) GetUserActivityCount(ctx context.Context, userID string) (int64, error) {
	var count int64
	result := r.db.WithContext(ctx).Model(&models.Activity{}).Where("user_id = ?", userID).Count(&count)
	return count, result.Error
}

// GetProjectActivity retrieves activities for a specific project with pagination
func (r *activityRepositoryImpl) GetProjectActivity(ctx context.Context, resourceType, resourceID string, limit, offset int) ([]models.Activity, error) {
	var activities []models.Activity
	result := r.db.WithContext(ctx).
		Where("resource_type = ? AND resource_id = ?", resourceType, resourceID).
		Order("timestamp DESC").
		Limit(limit).
		Offset(offset).
		Find(&activities)
	return activities, result.Error
}

// GetProjectActivityCount returns the total count of activities for a project
func (r *activityRepositoryImpl) GetProjectActivityCount(ctx context.Context, resourceType, resourceID string) (int64, error) {
	var count int64
	result := r.db.WithContext(ctx).
		Model(&models.Activity{}).
		Where("resource_type = ? AND resource_id = ?", resourceType, resourceID).
		Count(&count)
	return count, result.Error
}

// FilterActivity retrieves activities matching the provided filters with pagination
func (r *activityRepositoryImpl) FilterActivity(ctx context.Context, filters ActivityFilters, limit, offset int) ([]models.Activity, error) {
	query := r.db.WithContext(ctx)

	if filters.UserID != "" {
		query = query.Where("user_id = ?", filters.UserID)
	}
	if filters.Action != "" {
		query = query.Where("action = ?", filters.Action)
	}
	if filters.ResourceType != "" {
		query = query.Where("resource_type = ?", filters.ResourceType)
	}
	if filters.ResourceID != "" {
		query = query.Where("resource_id = ?", filters.ResourceID)
	}
	if filters.StartTime != nil {
		query = query.Where("timestamp >= ?", filters.StartTime)
	}
	if filters.EndTime != nil {
		query = query.Where("timestamp <= ?", filters.EndTime)
	}

	var activities []models.Activity
	result := query.Order("timestamp DESC").Limit(limit).Offset(offset).Find(&activities)
	return activities, result.Error
}

// FilterActivityCount returns the total count of activities matching the filters
func (r *activityRepositoryImpl) FilterActivityCount(ctx context.Context, filters ActivityFilters) (int64, error) {
	query := r.db.WithContext(ctx)

	if filters.UserID != "" {
		query = query.Where("user_id = ?", filters.UserID)
	}
	if filters.Action != "" {
		query = query.Where("action = ?", filters.Action)
	}
	if filters.ResourceType != "" {
		query = query.Where("resource_type = ?", filters.ResourceType)
	}
	if filters.ResourceID != "" {
		query = query.Where("resource_id = ?", filters.ResourceID)
	}
	if filters.StartTime != nil {
		query = query.Where("timestamp >= ?", filters.StartTime)
	}
	if filters.EndTime != nil {
		query = query.Where("timestamp <= ?", filters.EndTime)
	}

	var count int64
	result := query.Model(&models.Activity{}).Count(&count)
	return count, result.Error
}

// GetActivityStats returns activity statistics for a user
func (r *activityRepositoryImpl) GetActivityStats(ctx context.Context, userID string) (map[string]int64, error) {
	var results []map[string]interface{}
	query := r.db.WithContext(ctx).
		Model(&models.Activity{}).
		Where("user_id = ?", userID).
		Group("action").
		Select("action, COUNT(*) as count")

	if err := query.Scan(&results).Error; err != nil {
		return nil, fmt.Errorf("failed to get activity stats: %w", err)
	}

	stats := make(map[string]int64)
	for _, result := range results {
		if action, ok := result["action"].(string); ok {
			if count, ok := result["count"].(int64); ok {
				stats[action] = count
			}
		}
	}

	return stats, nil
}

// GetRecentActivity retrieves the most recent activities system-wide
func (r *activityRepositoryImpl) GetRecentActivity(ctx context.Context, limit int) ([]models.Activity, error) {
	var activities []models.Activity
	result := r.db.WithContext(ctx).
		Order("timestamp DESC").
		Limit(limit).
		Find(&activities)
	return activities, result.Error
}

// DeleteActivity soft-deletes an activity record
func (r *activityRepositoryImpl) DeleteActivity(ctx context.Context, activityID string) error {
	return r.db.WithContext(ctx).Where("id = ?", activityID).Delete(&models.Activity{}).Error
}

// GetActivity retrieves a single activity by ID
func (r *activityRepositoryImpl) GetActivity(ctx context.Context, activityID string) (*models.Activity, error) {
	var activity models.Activity
	result := r.db.WithContext(ctx).Where("id = ?", activityID).First(&activity)
	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, result.Error
	}
	return &activity, nil
}

// DeleteOldActivities soft-deletes activities older than the specified days
func (r *activityRepositoryImpl) DeleteOldActivities(ctx context.Context, daysOld int) (int64, error) {
	cutoffTime := time.Now().AddDate(0, 0, -daysOld)
	result := r.db.WithContext(ctx).Where("timestamp < ?", cutoffTime).Delete(&models.Activity{})
	return result.RowsAffected, result.Error
}
