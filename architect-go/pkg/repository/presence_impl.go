package repository

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"
	"gorm.io/gorm"

	"architect-go/pkg/models"
)

// presenceRepositoryImpl implements PresenceRepository
type presenceRepositoryImpl struct {
	db *gorm.DB
}

// NewPresenceRepository creates a new presence repository
func NewPresenceRepository(db *gorm.DB) PresenceRepository {
	return &presenceRepositoryImpl{db: db}
}

// CreateOrUpdatePresence creates or updates a user's presence record
func (r *presenceRepositoryImpl) CreateOrUpdatePresence(ctx context.Context, presence *models.Presence) error {
	if presence.ID == "" {
		presence.ID = uuid.New().String()
	}
	if presence.LastSeenAt.IsZero() {
		presence.LastSeenAt = time.Now()
	}

	result := r.db.WithContext(ctx).Save(presence)
	return result.Error
}

// GetPresence retrieves a user's current presence
func (r *presenceRepositoryImpl) GetPresence(ctx context.Context, userID string) (*models.Presence, error) {
	var presence models.Presence
	result := r.db.WithContext(ctx).Where("user_id = ?", userID).First(&presence)
	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, result.Error
	}
	return &presence, nil
}

// GetOnlineUsers retrieves all users with "online" status
func (r *presenceRepositoryImpl) GetOnlineUsers(ctx context.Context) ([]string, error) {
	var userIDs []string
	result := r.db.WithContext(ctx).Model(&models.Presence{}).Where("status = ?", "online").Pluck("user_id", &userIDs)
	return userIDs, result.Error
}

// GetPresenceByStatus retrieves all users with a specific status
func (r *presenceRepositoryImpl) GetPresenceByStatus(ctx context.Context, status string) ([]string, error) {
	var userIDs []string
	result := r.db.WithContext(ctx).Model(&models.Presence{}).Where("status = ?", status).Pluck("user_id", &userIDs)
	return userIDs, result.Error
}

// UpdatePresenceStatus updates a user's status
func (r *presenceRepositoryImpl) UpdatePresenceStatus(ctx context.Context, userID, status string) error {
	return r.db.WithContext(ctx).Model(&models.Presence{}).Where("user_id = ?", userID).Updates(map[string]interface{}{
		"status": status,
		"updated_at": time.Now(),
	}).Error
}

// UpdateLastSeen updates a user's last seen timestamp
func (r *presenceRepositoryImpl) UpdateLastSeen(ctx context.Context, userID string) error {
	return r.db.WithContext(ctx).Model(&models.Presence{}).Where("user_id = ?", userID).Update("last_seen_at", time.Now()).Error
}

// GetPresenceHistory retrieves a user's presence history with pagination
func (r *presenceRepositoryImpl) GetPresenceHistory(ctx context.Context, userID string, limit, offset int) ([]models.Presence, error) {
	var presences []models.Presence
	result := r.db.WithContext(ctx).
		Where("user_id = ?", userID).
		Order("created_at DESC").
		Limit(limit).
		Offset(offset).
		Find(&presences)
	return presences, result.Error
}

// GetPresenceHistoryCount returns the total count of presence records for a user
func (r *presenceRepositoryImpl) GetPresenceHistoryCount(ctx context.Context, userID string) (int64, error) {
	var count int64
	result := r.db.WithContext(ctx).Model(&models.Presence{}).Where("user_id = ?", userID).Count(&count)
	return count, result.Error
}

// SetOffline marks a user as offline
func (r *presenceRepositoryImpl) SetOffline(ctx context.Context, userID string) error {
	return r.db.WithContext(ctx).Model(&models.Presence{}).Where("user_id = ?", userID).Updates(map[string]interface{}{
		"status": "offline",
		"updated_at": time.Now(),
	}).Error
}

// DeletePresence soft-deletes a presence record
func (r *presenceRepositoryImpl) DeletePresence(ctx context.Context, userID string) error {
	return r.db.WithContext(ctx).Where("user_id = ?", userID).Delete(&models.Presence{}).Error
}

// GetStalePresences retrieves users who haven't been seen in a specified duration (for cleanup)
func (r *presenceRepositoryImpl) GetStalePresences(ctx context.Context, durationMinutes int) ([]string, error) {
	var userIDs []string
	staleBefore := time.Now().Add(-time.Duration(durationMinutes) * time.Minute)
	result := r.db.WithContext(ctx).
		Model(&models.Presence{}).
		Where("last_seen_at < ? AND status != ?", staleBefore, "offline").
		Pluck("user_id", &userIDs)
	if result.Error != nil {
		return nil, fmt.Errorf("failed to get stale presences: %w", result.Error)
	}
	return userIDs, nil
}
