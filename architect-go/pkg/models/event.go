package models

import "time"

// Event represents a tracked event in the system
type Event struct {
	ID        string                 `json:"id" db:"id"`
	Type      string                 `json:"type" db:"type"`
	UserID    string                 `json:"user_id" db:"user_id"`
	ProjectID string                 `json:"project_id,omitempty" db:"project_id"`
	Channel   string                 `json:"channel,omitempty" db:"channel"`
	Data      map[string]interface{} `json:"data,omitempty" db:"data"`
	Timestamp time.Time              `json:"timestamp" db:"timestamp"`
	CreatedAt time.Time              `json:"created_at" db:"created_at"`
}

// EventType represents the type of event
type EventType string

const (
	EventTypeLogin        EventType = "login"
	EventTypeLogout       EventType = "logout"
	EventTypeCreateEntity EventType = "create_entity"
	EventTypeUpdateEntity EventType = "update_entity"
	EventTypeDeleteEntity EventType = "delete_entity"
	EventTypeViewEntity   EventType = "view_entity"
	EventTypeShareEntity  EventType = "share_entity"
)

// EventFilter for querying events
type EventFilter struct {
	UserID    string
	Type      string
	ProjectID string
	StartDate time.Time
	EndDate   time.Time
	Limit     int
	Offset    int
}
