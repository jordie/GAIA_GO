package handlers

import (
	"context"
	"encoding/json"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"gorm.io/gorm"

	"architect-go/pkg/cache"
	"architect-go/pkg/errors"
)

// HealthHandler handles health check endpoints
type HealthHandler struct {
	db           *gorm.DB
	cacheManager *cache.CacheManager
	errHandler   *errors.Handler
}

// NewHealthHandler creates a new health handler
func NewHealthHandler(db *gorm.DB, cacheManager *cache.CacheManager, errHandler *errors.Handler) *HealthHandler {
	return &HealthHandler{
		db:           db,
		cacheManager: cacheManager,
		errHandler:   errHandler,
	}
}

// RegisterRoutes registers health check routes
func (h *HealthHandler) RegisterRoutes(router chi.Router) {
	router.Get("/health", h.Health)
	router.Get("/health/liveness", h.Liveness)
	router.Get("/health/readiness", h.Readiness)
	router.Get("/health/detailed", h.Detailed)
}

// HealthResponse is the response structure for health checks
type HealthResponse struct {
	Status    string                 `json:"status"`
	Timestamp time.Time              `json:"timestamp"`
	Uptime    string                 `json:"uptime,omitempty"`
	Version   string                 `json:"version,omitempty"`
	Details   map[string]interface{} `json:"details,omitempty"`
}

// LivenessResponse is the response structure for liveness checks
type LivenessResponse struct {
	Alive     bool      `json:"alive"`
	Timestamp time.Time `json:"timestamp"`
}

// ReadinessResponse is the response structure for readiness checks
type ReadinessResponse struct {
	Ready     bool                   `json:"ready"`
	Timestamp time.Time              `json:"timestamp"`
	Components map[string]bool       `json:"components"`
}

// DetailedHealthResponse is the response structure for detailed health checks
type DetailedHealthResponse struct {
	Status     string                 `json:"status"`
	Timestamp  time.Time              `json:"timestamp"`
	Components map[string]interface{} `json:"components"`
	Metrics    map[string]interface{} `json:"metrics,omitempty"`
}

// Health returns basic health check (200 OK)
func (h *HealthHandler) Health(w http.ResponseWriter, r *http.Request) {
	response := HealthResponse{
		Status:    "healthy",
		Timestamp: time.Now(),
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}

// Liveness returns liveness probe response
// Used by Kubernetes liveness probe to determine if pod is alive
func (h *HealthHandler) Liveness(w http.ResponseWriter, r *http.Request) {
	response := LivenessResponse{
		Alive:     true,
		Timestamp: time.Now(),
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}

// Readiness returns readiness probe response
// Used by Kubernetes readiness probe to determine if pod can receive traffic
func (h *HealthHandler) Readiness(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	components := map[string]bool{
		"database": false,
		"cache":    false,
	}

	// Check database connectivity
	if err := h.db.WithContext(ctx).Exec("SELECT 1").Error; err == nil {
		components["database"] = true
	}

	// Check cache connectivity
	if h.cacheManager != nil {
		// Cache is in-memory, so it's always ready if manager exists
		components["cache"] = true
	}

	// Determine overall readiness
	ready := components["database"] && components["cache"]

	response := ReadinessResponse{
		Ready:      ready,
		Timestamp:  time.Now(),
		Components: components,
	}

	statusCode := http.StatusOK
	if !ready {
		statusCode = http.StatusServiceUnavailable
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	json.NewEncoder(w).Encode(response)
}

// Detailed returns detailed health check information
// Includes metrics about system performance and component health
func (h *HealthHandler) Detailed(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	components := map[string]interface{}{
		"database": map[string]interface{}{
			"status": "unknown",
			"error":  nil,
		},
		"cache": map[string]interface{}{
			"status": "unknown",
			"size":   0,
		},
	}

	// Check database connectivity and get connection pool stats
	if err := h.db.WithContext(ctx).Exec("SELECT 1").Error; err != nil {
		components["database"] = map[string]interface{}{
			"status": "unhealthy",
			"error":  err.Error(),
		}
	} else {
		sqlDB, _ := h.db.DB()
		stats := sqlDB.Stats()
		components["database"] = map[string]interface{}{
			"status":           "healthy",
			"open_connections": stats.OpenConnections,
			"in_use":           stats.InUse,
			"idle":             stats.Idle,
			"wait_count":       stats.WaitCount,
			"wait_duration":    stats.WaitDuration.String(),
			"max_idle_closed":  stats.MaxIdleClosed,
		}
	}

	// Check cache health and metrics
	if h.cacheManager != nil {
		cacheStats := h.cacheManager.Stats()
		components["cache"] = map[string]interface{}{
			"status":   "healthy",
			"size":     h.cacheManager.Size(),
			"hits":     cacheStats.Hits,
			"misses":   cacheStats.Misses,
			"hit_rate": cacheStats.HitRate(),
		}
	} else {
		components["cache"] = map[string]interface{}{
			"status": "not_configured",
		}
	}

	// Determine overall status
	status := "healthy"
	if dbStatus, ok := components["database"].(map[string]interface{}); ok {
		if dbStatus["status"] != "healthy" {
			status = "degraded"
		}
	}

	response := DetailedHealthResponse{
		Status:     status,
		Timestamp:  time.Now(),
		Components: components,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}
