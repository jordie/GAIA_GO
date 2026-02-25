package router

import (
	"database/sql"
	"log"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/app"
	"github.com/jgirmay/GAIA_GO/internal/session"
)

// DiscoveredApps holds all discovered applications and their metadata
type DiscoveredApps struct {
	Apps     []app.App
	Metadata map[string]*app.Metadata
	LoadOrder []string
}

// DiscoverApps returns the list of known GAIA apps
func DiscoverApps(db *sql.DB, sessionManager *session.Manager) (*DiscoveredApps, error) {
	discovered := &DiscoveredApps{
		Apps:      make([]app.App, 0),
		Metadata:  make(map[string]*app.Metadata),
		LoadOrder: []string{"math", "typing", "reading", "piano"},
	}

	// Build metadata and stubs for known apps
	appNames := discovered.LoadOrder
	for _, appName := range appNames {
		meta := &app.Metadata{
			Name: appName,
			Status: "active",
		}

		var stub *AppStub

		switch appName {
		case "math":
			meta.DisplayName = "Math Master"
			meta.Description = "Practice mental math and arithmetic"
			meta.Version = "1.0.0"
			stub = &AppStub{name: "math", displayName: "Math Master", description: "Practice mental math and arithmetic", version: "1.0.0"}
		case "typing":
			meta.DisplayName = "Typing Master"
			meta.Description = "Test and improve your typing speed and accuracy"
			meta.Version = "2.0.0"
			stub = &AppStub{name: "typing", displayName: "Typing Master", description: "Test and improve your typing speed and accuracy", version: "2.0.0"}
		case "reading":
			meta.DisplayName = "Reading Comprehension"
			meta.Description = "Improve reading speed and comprehension"
			meta.Version = "1.0.0"
			stub = &AppStub{name: "reading", displayName: "Reading Comprehension", description: "Improve reading speed and comprehension", version: "1.0.0"}
		case "piano":
			meta.DisplayName = "Piano Master"
			meta.Description = "Learn to play piano songs"
			meta.Version = "1.0.0"
			stub = &AppStub{name: "piano", displayName: "Piano Master", description: "Learn to play piano songs", version: "1.0.0"}
		}

		discovered.Apps = append(discovered.Apps, stub)
		discovered.Metadata[appName] = meta
		log.Printf("[App Discovery] Discovered: %s (%s) v%s\n",
			appName, meta.DisplayName, meta.Version)
	}

	return discovered, nil
}

// GetAppMetadata returns metadata for a specific app
func (d *DiscoveredApps) GetAppMetadata(name string) *app.Metadata {
	return d.Metadata[name]
}

// GetApp returns a specific app by name (returns nil, apps are created by handlers)
func (d *DiscoveredApps) GetApp(name string) app.App {
	return nil
}

// AppStub implements app.App interface for documentation/health check purposes
type AppStub struct {
	name        string
	displayName string
	description string
	version     string
}

func (s *AppStub) GetName() string {
	return s.name
}

func (s *AppStub) GetDisplayName() string {
	return s.displayName
}

func (s *AppStub) GetDescription() string {
	return s.description
}

func (s *AppStub) GetVersion() string {
	return s.version
}

func (s *AppStub) RegisterRoutes(router *gin.RouterGroup) {
	// Stub implementation - actual routes registered by handlers
}

func (s *AppStub) InitDB() error {
	return nil
}

func (s *AppStub) GetUserStats(userID int64) (map[string]interface{}, error) {
	return nil, nil
}

func (s *AppStub) GetLeaderboard(limit int) ([]map[string]interface{}, error) {
	return nil, nil
}
