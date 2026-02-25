package router

import (
	"database/sql"
	"fmt"
	"log"

	appmodule "github.com/jgirmay/GAIA_GO/internal/app"
	"github.com/jgirmay/GAIA_GO/internal/docs"
	"github.com/jgirmay/GAIA_GO/internal/metrics"
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

	// Initialize metrics registries (Phase 6)
	httpMetrics := metrics.NewHTTPMetricsRegistry()
	r.metricsRegistry = httpMetrics
	log.Printf("✓ Initialized HTTP metrics registry\n")

	// Initialize business metrics (Phase 2)
	businessMetrics := metrics.NewBusinessMetricsRegistry()
	r.businessMetrics = businessMetrics
	log.Printf("✓ Initialized business metrics registry\n")

	// Register handlers for each app in dependency order
	for _, appName := range discovered.LoadOrder {
		if err := r.registerAppHandlers(appName, db, sessionManager, businessMetrics); err != nil {
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

	// Register SDK generation endpoints (Phase 4)
	openAPISpec := discoveredOpenAPISpec(discovered.Apps, discovered.Metadata)
	r.RegisterSDKGeneration(openAPISpec)
	log.Printf("Registered SDK generation endpoints\n")

	// Register metrics endpoint (Phase 6)
	r.RegisterMetricsEndpoint(httpMetrics)
	log.Printf("✓ Registered metrics endpoint at /metrics\n")

	return nil
}

// discoveredOpenAPISpec generates OpenAPI spec from discovered apps
func discoveredOpenAPISpec(apps []appmodule.App, metadata map[string]*appmodule.Metadata) *docs.OpenAPISpec {
	return docs.GenerateOpenAPISpec(apps, metadata)
}

// registerAppHandlers registers all handlers for a specific app
func (r *AppRouter) registerAppHandlers(appName string, db *sql.DB, sm *session.Manager, businessMetrics *metrics.BusinessMetricsRegistry) error {
	group := r.RegisterAppRoutes(appName)

	switch appName {
	case "math":
		mathApp := mathhandlers.NewMathApp(db)
		mathhandlers.RegisterHandlers(group, mathApp, sm, businessMetrics)
		log.Printf("Registered math app handlers\n")
	case "typing":
		typingApp := typinghandlers.NewTypingApp(db)
		typinghandlers.RegisterHandlers(group, typingApp, sm, businessMetrics)
		log.Printf("Registered typing app handlers\n")
	case "reading":
		readingApp := readinghandlers.NewReadingApp(db)
		readinghandlers.RegisterHandlers(group, readingApp, sm, businessMetrics)
		log.Printf("Registered reading app handlers\n")
	case "piano":
		pianoApp := pianohandlers.NewPianoApp(db)
		pianohandlers.RegisterHandlers(group, pianoApp, sm, businessMetrics)
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
			"status":      appMeta.Status,
		}
	}

	return metadata, nil
}
