package services

import (
	"context"

	"architect-go/pkg/models"
)

// PresenceService defines the interface for presence management
type PresenceService interface {
	// UpdatePresence updates a user's presence status
	UpdatePresence(ctx context.Context, userID, status string, metadata map[string]interface{}) error

	// GetPresence retrieves a user's current presence
	GetPresence(ctx context.Context, userID string) (*models.Presence, error)

	// GetOnlineUsers retrieves all online users
	GetOnlineUsers(ctx context.Context) ([]string, error)

	// GetPresenceByStatus retrieves users with a specific status
	GetPresenceByStatus(ctx context.Context, status string) ([]string, error)

	// GetPresenceHistory retrieves a user's presence history with pagination
	GetPresenceHistory(ctx context.Context, userID string, limit, offset int) ([]models.Presence, int64, error)

	// SetOffline marks a user as offline
	SetOffline(ctx context.Context, userID string) error

	// BroadcastPresenceChange broadcasts a presence change event
	BroadcastPresenceChange(ctx context.Context, userID, oldStatus, newStatus string) error

	// HandleUserLogout sets user to offline and logs activity
	HandleUserLogout(ctx context.Context, userID string) error

	// CleanupStalePresences marks users as offline if they haven't been seen recently
	CleanupStalePresences(ctx context.Context, durationMinutes int) (int64, error)
}
