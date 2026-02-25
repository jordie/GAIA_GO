package session

import (
	"time"
)

// SessionStatus represents the state of a GAIA session
type SessionStatus string

const (
	SessionStatusCreating SessionStatus = "creating"
	SessionStatusActive   SessionStatus = "active"
	SessionStatusStopped  SessionStatus = "stopped"
	SessionStatusError    SessionStatus = "error"
)

// Session represents a GAIA development session (separate from user authentication sessions)
type Session struct {
	ID            string            `json:"id"`
	Name          string            `json:"name"`
	ProjectPath   string            `json:"project_path"`
	Status        SessionStatus     `json:"status"`
	Windows       map[string]*Window `json:"-"` // Internal tracking
	CreatedAt     time.Time         `json:"created_at"`
	LastActive    time.Time         `json:"last_active"`
	Metadata      map[string]string `json:"metadata"`
	Tags          []string          `json:"tags"`
}

// Window represents a tmux window within a GAIA session
type Window struct {
	ID            string          `json:"id"`
	SessionID     string          `json:"session_id"`
	Name          string          `json:"name"`
	Index         int             `json:"index"`
	Active        bool            `json:"active"`
	Panes         map[string]*Pane `json:"-"` // Internal tracking
	CreatedAt     time.Time       `json:"created_at"`
}

// Pane represents a tmux pane within a window
type Pane struct {
	ID          string    `json:"id"`
	WindowID    string    `json:"window_id"`
	SessionID   string    `json:"session_id"`
	Index       int       `json:"index"`
	Command     string    `json:"command"`
	Active      bool      `json:"active"`
	WorkDir     string    `json:"work_dir"`
	CreatedAt   time.Time `json:"created_at"`
}

// SessionConfig holds configuration for creating a new session
type SessionConfig struct {
	Name        string            `json:"name"`
	ProjectPath string            `json:"project_path"`
	Shell       string            `json:"shell"`
	Metadata    map[string]string `json:"metadata"`
	Tags        []string          `json:"tags"`
}

// WindowConfig holds configuration for creating a new window
type WindowConfig struct {
	Name string `json:"name"`
}

// PaneConfig holds configuration for creating a new pane
type PaneConfig struct {
	Command   string `json:"command"`
	WorkDir   string `json:"work_dir"`
	Reattach  bool   `json:"reattach"` // Reattach to existing session
	Vertical  bool   `json:"vertical"` // True for vertical split, false for horizontal
}
