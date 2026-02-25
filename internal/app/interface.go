package app

import (
	"database/sql"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/session"
)

// App is the interface all GAIA apps must implement
type App interface {
	// GetName returns the app's unique identifier (e.g., "typing", "math", "reading")
	GetName() string

	// GetDisplayName returns the human-readable name (e.g., "Typing Master")
	GetDisplayName() string

	// GetDescription returns a brief description of the app
	GetDescription() string

	// GetVersion returns the app version
	GetVersion() string

	// RegisterRoutes registers all HTTP endpoints for this app
	// The router is already scoped to /api/<app_name>, so handlers should be like:
	// router.GET("/text", handler)  →  /api/typing/text
	RegisterRoutes(router *gin.RouterGroup)

	// InitDB initializes app-specific database tables
	// Called once on startup
	InitDB() error

	// GetStats returns app-specific statistics for a user
	// Returns map[string]interface{} for flexibility
	GetUserStats(userID int64) (map[string]interface{}, error)

	// GetLeaderboard returns top players for the app
	// Returns []map[string]interface{} with user stats
	GetLeaderboard(limit int) ([]map[string]interface{}, error)
}

// AppConfig holds configuration for registering an app
type AppConfig struct {
	Name        string
	DisplayName string
	Description string
	Version     string
	Instance    App
	DB          *sql.DB
	SessionMgr  *session.Manager
}

// Metadata holds app information for discovery
type Metadata struct {
	Name        string `json:"name"`
	DisplayName string `json:"display_name"`
	Description string `json:"description"`
	Version     string `json:"version"`
	Path        string `json:"path"`
	Status      string `json:"status"`
}
