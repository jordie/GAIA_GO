package models

import "time"

// Presence represents user presence status
type Presence struct {
	ID        string                 `json:"id" db:"id"`
	UserID    string                 `json:"user_id" db:"user_id"`
	Status    string                 `json:"status" db:"status"`
	Metadata  map[string]interface{} `json:"metadata,omitempty" db:"metadata"`
	Timestamp time.Time              `json:"timestamp" db:"timestamp"`
	UpdatedAt time.Time              `json:"updated_at" db:"updated_at"`
}

// PresenceStatus represents the status of user presence
type PresenceStatus string

const (
	StatusOnline      PresenceStatus = "online"
	StatusOffline     PresenceStatus = "offline"
	StatusAway        PresenceStatus = "away"
	StatusDND         PresenceStatus = "dnd" // Do Not Disturb
	StatusIdle        PresenceStatus = "idle"
	StatusInMeeting   PresenceStatus = "in_meeting"
)

// PresenceFilter for querying presence records
type PresenceFilter struct {
	UserID    string
	Status    string
	StartDate time.Time
	EndDate   time.Time
	Limit     int
	Offset    int
}
