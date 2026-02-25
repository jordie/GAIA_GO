package app

import (
	"fmt"
	"log"
	"sync"

	"github.com/gin-gonic/gin"
)

// Registry manages all registered GAIA apps
type Registry struct {
	apps      map[string]App
	metadata  map[string]Metadata
	mu        sync.RWMutex
}

// NewRegistry creates a new app registry
func NewRegistry() *Registry {
	return &Registry{
		apps:     make(map[string]App),
		metadata: make(map[string]Metadata),
	}
}

// Register registers a new app
func (r *Registry) Register(config AppConfig) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.apps[config.Name]; exists {
		return fmt.Errorf("app %s already registered", config.Name)
	}

	if config.Instance == nil {
		return fmt.Errorf("app %s has no instance", config.Name)
	}

	// Validate instance matches config
	if config.Instance.GetName() != config.Name {
		return fmt.Errorf("app name mismatch: config says %s, instance says %s",
			config.Name, config.Instance.GetName())
	}

	// Initialize database for app
	if err := config.Instance.InitDB(); err != nil {
		return fmt.Errorf("failed to initialize %s database: %v", config.Name, err)
	}

	// Store app and metadata
	r.apps[config.Name] = config.Instance
	r.metadata[config.Name] = Metadata{
		Name:        config.Name,
		DisplayName: config.Instance.GetDisplayName(),
		Description: config.Instance.GetDescription(),
		Version:     config.Instance.GetVersion(),
		Status:      "active",
	}

	log.Printf("[App Registry] Registered: %s (%s) v%s\n",
		config.Name, config.DisplayName, config.Instance.GetVersion())

	return nil
}

// GetApp retrieves a registered app
func (r *Registry) GetApp(name string) (App, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	app, exists := r.apps[name]
	if !exists {
		return nil, fmt.Errorf("app %s not found", name)
	}

	return app, nil
}

// GetMetadata retrieves app metadata
func (r *Registry) GetMetadata(name string) (Metadata, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	metadata, exists := r.metadata[name]
	if !exists {
		return Metadata{}, fmt.Errorf("metadata for %s not found", name)
	}

	return metadata, nil
}

// ListApps returns all registered apps
func (r *Registry) ListApps() map[string]Metadata {
	r.mu.RLock()
	defer r.mu.RUnlock()

	result := make(map[string]Metadata)
	for name, metadata := range r.metadata {
		result[name] = metadata
	}

	return result
}

// RegisterRoutes registers routes for all apps
// Assumes router is at /api, will create /api/<app_name> for each app
func (r *Registry) RegisterRoutes(apiRouter *gin.RouterGroup) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	for name, app := range r.apps {
		// Create app-specific router group
		appRouter := apiRouter.Group("/" + name)

		// Register app's routes
		app.RegisterRoutes(appRouter)

		log.Printf("[App Registry] Routes registered for %s at /api/%s\n", name, name)
	}
}

// GetAppCount returns number of registered apps
func (r *Registry) GetAppCount() int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return len(r.apps)
}

// AppsEndpoint returns all apps as JSON (for discovery)
func (r *Registry) AppsEndpoint() gin.HandlerFunc {
	return func(c *gin.Context) {
		apps := r.ListApps()
		c.JSON(200, gin.H{
			"apps":  apps,
			"count": len(apps),
		})
	}
}
