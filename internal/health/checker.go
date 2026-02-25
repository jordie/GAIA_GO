package health

import (
	"database/sql"
	"fmt"
	"time"

	appmodule "github.com/jgirmay/GAIA_GO/internal/app"
)

// HealthStatus represents the overall system health
type HealthStatus struct {
	Status    string                       `json:"status"`
	Timestamp time.Time                    `json:"timestamp"`
	Message   string                       `json:"message"`
	Services  map[string]ServiceHealth     `json:"services"`
	Apps      map[string]AppHealth         `json:"apps"`
	Uptime    string                       `json:"uptime"`
}

// ServiceHealth represents health of a service
type ServiceHealth struct {
	Status  string `json:"status"`
	Message string `json:"message"`
	Latency string `json:"latency_ms"`
}

// AppHealth represents health of an app
type AppHealth struct {
	Name      string `json:"name"`
	Status    string `json:"status"`
	Version   string `json:"version"`
	Message   string `json:"message,omitempty"`
	Endpoints int    `json:"endpoints"`
}

// HealthChecker performs health checks on system components
type HealthChecker struct {
	db       *sql.DB
	apps     []appmodule.App
	metadata map[string]*appmodule.Metadata
	startTime time.Time
}

// NewHealthChecker creates a new health checker
func NewHealthChecker(db *sql.DB, apps []appmodule.App, metadata map[string]*appmodule.Metadata) *HealthChecker {
	return &HealthChecker{
		db:       db,
		apps:     apps,
		metadata: metadata,
		startTime: time.Now(),
	}
}

// Check performs a complete health check
func (hc *HealthChecker) Check() *HealthStatus {
	status := &HealthStatus{
		Status:    "healthy",
		Timestamp: time.Now(),
		Services:  make(map[string]ServiceHealth),
		Apps:      make(map[string]AppHealth),
		Uptime:    hc.calculateUptime(),
	}

	// Check database
	dbHealth := hc.checkDatabase()
	status.Services["database"] = dbHealth
	if dbHealth.Status != "healthy" {
		status.Status = "degraded"
	}

	// Check apps
	for _, app := range hc.apps {
		appMeta := hc.metadata[app.GetName()]
		if appMeta == nil {
			continue
		}

		appHealth := AppHealth{
			Name:    app.GetName(),
			Status:  "healthy",
			Version: appMeta.Version,
		}

		status.Apps[app.GetName()] = appHealth
	}

	// Determine overall status
	if len(status.Apps) == 0 {
		status.Status = "degraded"
		status.Message = "No apps registered"
	} else if dbHealth.Status != "healthy" {
		status.Status = "degraded"
		status.Message = "Database connectivity issue"
	} else {
		status.Message = fmt.Sprintf("System operating normally with %d apps", len(status.Apps))
	}

	return status
}

// checkDatabase verifies database connectivity
func (hc *HealthChecker) checkDatabase() ServiceHealth {
	start := time.Now()

	err := hc.db.Ping()
	latency := time.Since(start)

	if err != nil {
		return ServiceHealth{
			Status:  "unhealthy",
			Message: "Database connection failed: " + err.Error(),
			Latency: fmt.Sprintf("%d", latency.Milliseconds()),
		}
	}

	return ServiceHealth{
		Status:  "healthy",
		Message: "Database connection successful",
		Latency: fmt.Sprintf("%d", latency.Milliseconds()),
	}
}

// calculateUptime calculates system uptime as human-readable string
func (hc *HealthChecker) calculateUptime() string {
	elapsed := time.Since(hc.startTime)

	days := int(elapsed.Hours()) / 24
	hours := int(elapsed.Hours()) % 24
	minutes := int(elapsed.Minutes()) % 60
	seconds := int(elapsed.Seconds()) % 60

	if days > 0 {
		return fmt.Sprintf("%dd %dh %dm %ds", days, hours, minutes, seconds)
	} else if hours > 0 {
		return fmt.Sprintf("%dh %dm %ds", hours, minutes, seconds)
	} else if minutes > 0 {
		return fmt.Sprintf("%dm %ds", minutes, seconds)
	}
	return fmt.Sprintf("%ds", seconds)
}

// CheckApp performs health check on a specific app
func (hc *HealthChecker) CheckApp(appName string) *AppHealth {
	for _, app := range hc.apps {
		if app.GetName() == appName {
			appMeta := hc.metadata[appName]
			if appMeta == nil {
				return &AppHealth{
					Name:   appName,
					Status: "unknown",
				}
			}

			appHealth := AppHealth{
				Name:    appName,
				Status:  "healthy",
				Version: appMeta.Version,
			}

			return &appHealth
		}
	}

	return &AppHealth{
		Name:   appName,
		Status: "not_found",
	}
}
