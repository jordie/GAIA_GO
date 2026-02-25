package models

import "time"

// User represents a system user
type User struct {
	ID        string    `json:"id" db:"id"`
	Email     string    `json:"email" db:"email"`
	Name      string    `json:"name" db:"name"`
	Role      string    `json:"role" db:"role"`
	Status    string    `json:"status" db:"status"`
	CreatedAt time.Time `json:"created_at" db:"created_at"`
	UpdatedAt time.Time `json:"updated_at" db:"updated_at"`
	LastLogin time.Time `json:"last_login,omitempty" db:"last_login"`
}

// UserRole represents user roles
type UserRole string

const (
	RoleAdmin  UserRole = "admin"
	RoleEditor UserRole = "editor"
	RoleViewer UserRole = "viewer"
	RoleGuest  UserRole = "guest"
)

// UserStatus represents user account status
type UserStatus string

const (
	StatusActive   UserStatus = "active"
	StatusInactive UserStatus = "inactive"
	StatusSuspended UserStatus = "suspended"
)

// UserFilter for querying users
type UserFilter struct {
	Role      string
	Status    string
	CreatedAfter time.Time
	CreatedBefore time.Time
	Limit     int
	Offset    int
}
