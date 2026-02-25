package models

import "time"

// Activity represents a user activity in the system
type Activity struct {
	ID           string                 `json:"id" db:"id"`
	UserID       string                 `json:"user_id" db:"user_id"`
	Action       string                 `json:"action" db:"action"`
	ResourceType string                 `json:"resource_type" db:"resource_type"`
	ResourceID   string                 `json:"resource_id" db:"resource_id"`
	Details      map[string]interface{} `json:"details,omitempty" db:"details"`
	Timestamp    time.Time              `json:"timestamp" db:"timestamp"`
	CreatedAt    time.Time              `json:"created_at" db:"created_at"`
}

// ActivityAction represents the type of action performed
type ActivityAction string

const (
	ActionCreate ActivityAction = "create"
	ActionRead   ActivityAction = "read"
	ActionUpdate ActivityAction = "update"
	ActionDelete ActivityAction = "delete"
	ActionShare  ActivityAction = "share"
	ActionComment ActivityAction = "comment"
)

// ActivityFilter for querying activities
type ActivityFilter struct {
	UserID       string
	Action       string
	ResourceType string
	ResourceID   string
	StartDate    time.Time
	EndDate      time.Time
	Limit        int
	Offset       int
}
