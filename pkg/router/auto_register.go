package router

import (
	"database/sql"
	"fmt"
	"log"

	"github.com/jgirmay/GAIA_GO/internal/session"
	mathhandlers "github.com/jgirmay/GAIA_GO/pkg/apps/math"
	pianohandlers "github.com/jgirmay/GAIA_GO/pkg/apps/piano"
	readinghandlers "github.com/jgirmay/GAIA_GO/pkg/apps/reading"
	typinghandlers "github.com/jgirmay/GAIA_GO/pkg/apps/typing"
)

// RegisterAllApps discovers and registers all GAIA applications with documentation and health checks
func (r *AppRouter) RegisterAllApps(db *sql.DB, sessionManager *session.Manager) error {
	// Discover all apps
	discovered, err := DiscoverApps(db, sessionManager)
	if err != nil {
		return fmt.Errorf("app discovery failed: %w", err)
	}

	log.Printf("Registering %d apps in load order: %v\n", len(discovered.Apps), discovered.LoadOrder)

	// Register handlers for each app in dependency order
	for _, appName := range discovered.LoadOrder {
		if err := r.registerAppHandlers(appName, db, sessionManager); err != nil {
			log.Printf("Error registering handlers for %s: %v\n", appName, err)
			// Continue with other apps instead of failing completely
		}
	}

	// Register API documentation (Phase 3)
	r.RegisterDocumentation(discovered.Apps, discovered.Metadata)
	log.Printf("Registered API documentation endpoints\n")

	// Register health check endpoints (Phase 3)
	r.RegisterHealthCheck(db, discovered.Apps, discovered.Metadata)
	log.Printf("Registered health check endpoints\n")

	return nil
}

// registerAppHandlers registers all handlers for a specific app
func (r *AppRouter) registerAppHandlers(appName string, db *sql.DB, sm *session.Manager) error {
	group := r.RegisterAppRoutes(appName)

	switch appName {
	case "math":
		mathApp := mathhandlers.NewMathApp(db)
		mathhandlers.RegisterHandlers(group, mathApp, sm)
		log.Printf("Registered math app handlers\n")
	case "typing":
		typingApp := typinghandlers.NewTypingApp(db)
		typinghandlers.RegisterHandlers(group, typingApp, sm)
		log.Printf("Registered typing app handlers\n")
	case "reading":
		readingApp := readinghandlers.NewReadingApp(db)
		readinghandlers.RegisterHandlers(group, readingApp, sm)
		log.Printf("Registered reading app handlers\n")
	case "piano":
		pianoApp := pianohandlers.NewPianoApp(db)
		pianohandlers.RegisterHandlers(group, pianoApp, sm)
		log.Printf("Registered piano app handlers\n")
	default:
		return fmt.Errorf("unknown app: %s", appName)
	}

	return nil
}


// GetDiscoveredAppsMetadata returns metadata for all discovered apps
// This is useful for documentation and debugging
func GetAppMetadata(db *sql.DB, sessionManager *session.Manager) (map[string]interface{}, error) {
	discovered, err := DiscoverApps(db, sessionManager)
	if err != nil {
		return nil, err
	}

	metadata := make(map[string]interface{})
	for appName, appMeta := range discovered.Metadata {
		metadata[appName] = map[string]interface{}{
			"name":        appMeta.Name,
			"description": appMeta.Description,
			"version":     appMeta.Version,
			"base_path":   appMeta.BasePath,
			"status":      appMeta.Status,
			"routes":      appMeta.Routes,
		}
	}

	return metadata, nil
}
