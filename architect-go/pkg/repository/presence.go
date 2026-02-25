package repository

import (
	"context"

	"architect-go/pkg/models"
)

// PresenceRepository defines the interface for presence data access
type PresenceRepository interface {
	// CreateOrUpdatePresence creates or updates a user's presence record
	CreateOrUpdatePresence(ctx context.Context, presence *models.Presence) error

	// GetPresence retrieves a user's current presence
	GetPresence(ctx context.Context, userID string) (*models.Presence, error)

	// GetOnlineUsers retrieves all users with "online" status
	GetOnlineUsers(ctx context.Context) ([]string, error)

	// GetPresenceByStatus retrieves all users with a specific status
	GetPresenceByStatus(ctx context.Context, status string) ([]string, error)

	// UpdatePresenceStatus updates a user's status
	UpdatePresenceStatus(ctx context.Context, userID, status string) error

	// UpdateLastSeen updates a user's last seen timestamp
	UpdateLastSeen(ctx context.Context, userID string) error

	// GetPresenceHistory retrieves a user's presence history with pagination
	GetPresenceHistory(ctx context.Context, userID string, limit, offset int) ([]models.Presence, error)

	// GetPresenceHistoryCount returns the total count of presence records for a user
	GetPresenceHistoryCount(ctx context.Context, userID string) (int64, error)

	// SetOffline marks a user as offline
	SetOffline(ctx context.Context, userID string) error

	// DeletePresence soft-deletes a presence record
	DeletePresence(ctx context.Context, userID string) error

	// GetStalePresences retrieves users who haven't been seen in a specified duration (for cleanup)
	// durationMinutes: how old the last_seen_at must be
	GetStalePresences(ctx context.Context, durationMinutes int) ([]string, error)
}
