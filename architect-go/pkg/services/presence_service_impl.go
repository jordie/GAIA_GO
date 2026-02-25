package services

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"architect-go/pkg/cache"
	"architect-go/pkg/events"
	"architect-go/pkg/repository"
	"architect-go/pkg/models"
)

// PresenceServiceImpl implements PresenceService
type PresenceServiceImpl struct {
	repo       repository.PresenceRepository
	activityRepo repository.ActivityRepository
	cache      *cache.CacheManager
	dispatcher events.EventDispatcher
}

// NewPresenceService creates a new presence service
func NewPresenceService(presenceRepo repository.PresenceRepository, activityRepo repository.ActivityRepository) PresenceService {
	return &PresenceServiceImpl{
		repo:       presenceRepo,
		activityRepo: activityRepo,
		cache:      nil,
		dispatcher: nil,
	}
}

// NewPresenceServiceWithCache creates a new presence service with caching
func NewPresenceServiceWithCache(presenceRepo repository.PresenceRepository, activityRepo repository.ActivityRepository, cm *cache.CacheManager, dispatcher events.EventDispatcher) PresenceService {
	return &PresenceServiceImpl{
		repo:       presenceRepo,
		activityRepo: activityRepo,
		cache:      cm,
		dispatcher: dispatcher,
	}
}

// UpdatePresence updates a user's presence status
func (s *PresenceServiceImpl) UpdatePresence(ctx context.Context, userID, status string, metadata map[string]interface{}) error {
	// Get old presence if exists
	oldPresence, err := s.GetPresence(ctx, userID)
	var oldStatus string
	if err == nil && oldPresence != nil {
		oldStatus = oldPresence.Status
	} else {
		oldStatus = "offline"
	}

	// Create or update presence
	now := time.Now()
	presence := &models.Presence{
		UserID:     userID,
		Status:     status,
		LastSeenAt: now,
	}

	if metadata != nil {
		if data, err := json.Marshal(metadata); err == nil {
			presence.Metadata = data
		}
	}

	if err := s.repo.CreateOrUpdatePresence(ctx, presence); err != nil {
		return fmt.Errorf("failed to update presence: %w", err)
	}

	// Invalidate cache
	if s.cache != nil {
		s.cache.Delete("presence:" + userID)
	}

	// Broadcast presence change event if dispatcher is available and status changed
	if s.dispatcher != nil && oldStatus != status {
		_ = s.BroadcastPresenceChange(ctx, userID, oldStatus, status)
	}

	return nil
}

// GetPresence retrieves a user's current presence
func (s *PresenceServiceImpl) GetPresence(ctx context.Context, userID string) (*models.Presence, error) {
	// Try cache first
	if s.cache != nil {
		cacheKey := "presence:" + userID
		if cached, ok := s.cache.Get(cacheKey); ok {
			if presence, ok := cached.(*models.Presence); ok {
				return presence, nil
			}
		}
	}

	// Get from repository
	presence, err := s.repo.GetPresence(ctx, userID)
	if err != nil {
		return nil, fmt.Errorf("failed to get presence: %w", err)
	}

	// Cache the result (5 minute TTL)
	if s.cache != nil && presence != nil {
		cacheKey := "presence:" + userID
		s.cache.Set(cacheKey, presence, 5*time.Minute)
	}

	return presence, nil
}

// GetOnlineUsers retrieves all online users
func (s *PresenceServiceImpl) GetOnlineUsers(ctx context.Context) ([]string, error) {
	// Try cache first
	if s.cache != nil {
		cacheKey := "presence:online_users"
		if cached, ok := s.cache.Get(cacheKey); ok {
			if users, ok := cached.([]string); ok {
				return users, nil
			}
		}
	}

	// Get from repository
	users, err := s.repo.GetOnlineUsers(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to get online users: %w", err)
	}

	// Cache the result (1 minute TTL)
	if s.cache != nil {
		cacheKey := "presence:online_users"
		s.cache.Set(cacheKey, users, 1*time.Minute)
	}

	return users, nil
}

// GetPresenceByStatus retrieves users with a specific status
func (s *PresenceServiceImpl) GetPresenceByStatus(ctx context.Context, status string) ([]string, error) {
	users, err := s.repo.GetPresenceByStatus(ctx, status)
	if err != nil {
		return nil, fmt.Errorf("failed to get users by status: %w", err)
	}
	return users, nil
}

// GetPresenceHistory retrieves a user's presence history with pagination
func (s *PresenceServiceImpl) GetPresenceHistory(ctx context.Context, userID string, limit, offset int) ([]models.Presence, int64, error) {
	// Get history from repository
	history, err := s.repo.GetPresenceHistory(ctx, userID, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get presence history: %w", err)
	}

	// Get count
	count, err := s.repo.GetPresenceHistoryCount(ctx, userID)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get presence history count: %w", err)
	}

	return history, count, nil
}

// SetOffline marks a user as offline
func (s *PresenceServiceImpl) SetOffline(ctx context.Context, userID string) error {
	// Get current presence
	presence, err := s.GetPresence(ctx, userID)
	oldStatus := "offline"
	if err == nil && presence != nil {
		oldStatus = presence.Status
	}

	// Set offline
	if err := s.repo.SetOffline(ctx, userID); err != nil {
		return fmt.Errorf("failed to set offline: %w", err)
	}

	// Invalidate cache
	if s.cache != nil {
		s.cache.Delete("presence:" + userID)
		s.cache.Delete("presence:online_users")
	}

	// Broadcast presence change event
	if s.dispatcher != nil && oldStatus != "offline" {
		_ = s.BroadcastPresenceChange(ctx, userID, oldStatus, "offline")
	}

	return nil
}

// BroadcastPresenceChange broadcasts a presence change event
func (s *PresenceServiceImpl) BroadcastPresenceChange(ctx context.Context, userID, oldStatus, newStatus string) error {
	if s.dispatcher == nil {
		return nil
	}

	event := events.Event{
		Type: "presence.changed",
		Channel: "presence:" + userID,
		Data: map[string]interface{}{
			"user_id":    userID,
			"old_status": oldStatus,
			"new_status": newStatus,
			"timestamp":  time.Now(),
		},
		Timestamp: time.Now(),
	}

	s.dispatcher.Dispatch(event)
	return nil
}

// HandleUserLogout sets user to offline and logs activity
func (s *PresenceServiceImpl) HandleUserLogout(ctx context.Context, userID string) error {
	// Set offline
	if err := s.SetOffline(ctx, userID); err != nil {
		return err
	}

	// Log activity
	if s.activityRepo != nil {
		activity := &models.Activity{
			UserID:    userID,
			Action:    "user_logout",
			Timestamp: time.Now(),
		}
		_ = s.activityRepo.LogActivity(ctx, activity)
	}

	return nil
}

// CleanupStalePresences marks users as offline if they haven't been seen recently
func (s *PresenceServiceImpl) CleanupStalePresences(ctx context.Context, durationMinutes int) (int64, error) {
	staleUsers, err := s.repo.GetStalePresences(ctx, durationMinutes)
	if err != nil {
		return 0, fmt.Errorf("failed to get stale presences: %w", err)
	}

	var count int64
	for _, userID := range staleUsers {
		if err := s.SetOffline(ctx, userID); err != nil {
			// Log but continue
			fmt.Printf("failed to set offline for stale user %s: %v\n", userID, err)
		} else {
			count++
		}
	}

	return count, nil
}
