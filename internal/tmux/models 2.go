package tmux

import "time"

// Project represents a project that contains tmux sessions
type Project struct {
	ID           int       `json:"id"`
	Slug         string    `json:"slug"`
	Name         string    `json:"name"`
	Icon         string    `json:"icon"`
	DisplayOrder int       `json:"display_order"`
	CreatedAt    time.Time `json:"created_at"`
}

// TmuxSession represents a single tmux session with its metadata
type TmuxSession struct {
	ID        string    `json:"id"`
	Name      string    `json:"name"`
	ProjectID *int      `json:"project_id"`
	Environment string   `json:"environment"`
	IsWorker  bool      `json:"is_worker"`
	Attached  bool      `json:"attached"`
	CreatedAt time.Time `json:"created_at"`
	LastActive time.Time `json:"last_active"`
}

// SessionGroup represents a grouped collection of sessions
type SessionGroup struct {
	ID            string         `json:"id"`
	Name          string         `json:"name"`
	Icon          string         `json:"icon"`
	Collapsed     bool           `json:"collapsed"`
	Sessions      []TmuxSession  `json:"sessions"`
	AttachedCount int            `json:"attached_count"`
	TotalCount    int            `json:"total_count"`
}

// GroupedSessions represents all sessions grouped by project, environment, and type
type GroupedSessions struct {
	Groups          []SessionGroup `json:"groups"`
	TotalSessions   int            `json:"total_sessions"`
	TotalAttached   int            `json:"total_attached"`
	UnassignedCount int            `json:"unassigned_count"`
}

// AutoAssignResult represents the result of an auto-assignment operation
type AutoAssignResult struct {
	Success  bool   `json:"success"`
	Assigned int    `json:"assigned"`
	Message  string `json:"message"`
}

// AssignSessionRequest represents a request to assign a session to a project
type AssignSessionRequest struct {
	SessionName string `json:"session_name"`
	ProjectID   int    `json:"project_id"`
}

// SetEnvironmentRequest represents a request to set session environment
type SetEnvironmentRequest struct {
	SessionName string `json:"session_name"`
	Environment string `json:"environment"`
}

// SetWorkerRequest represents a request to mark a session as a worker
type SetWorkerRequest struct {
	SessionName string `json:"session_name"`
	IsWorker    bool   `json:"is_worker"`
}

// ToggleCollapsedRequest represents a request to toggle group collapsed state
type ToggleCollapsedRequest struct {
	GroupID string `json:"group_id"`
}

// SessionGroupPreference represents user UI preferences for session groups
type SessionGroupPreference struct {
	ID      int       `json:"id"`
	UserID  int       `json:"user_id"`
	GroupID string    `json:"group_id"`
	Collapsed bool    `json:"collapsed"`
	UpdatedAt time.Time `json:"updated_at"`
}
