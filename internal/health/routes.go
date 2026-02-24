package health

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/api"
)

// HealthHandler provides health check endpoints
type HealthHandler struct {
	checker *HealthChecker
}

// NewHealthHandler creates a new health handler
func NewHealthHandler(checker *HealthChecker) *HealthHandler {
	return &HealthHandler{
		checker: checker,
	}
}

// RegisterRoutes registers health check endpoints
func (h *HealthHandler) RegisterRoutes(engine *gin.Engine) {
	health := engine.Group("/api/health")
	{
		health.GET("", h.handleHealthStatus)
		health.GET("/live", h.handleLiveness)
		health.GET("/ready", h.handleReadiness)
		health.GET("/apps/:appName", h.handleAppHealth)
	}
}

// handleHealthStatus returns complete health status
func (h *HealthHandler) handleHealthStatus(c *gin.Context) {
	status := h.checker.Check()

	// Return appropriate HTTP status based on health
	httpStatus := http.StatusOK
	if status.Status != "healthy" {
		httpStatus = http.StatusServiceUnavailable
	}

	api.RespondWith(c, httpStatus, status)
}

// handleLiveness checks if the service is running
func (h *HealthHandler) handleLiveness(c *gin.Context) {
	// Simple liveness check - just return ok
	api.RespondWith(c, http.StatusOK, gin.H{
		"status": "alive",
		"message": "Service is running",
	})
}

// handleReadiness checks if the service is ready to serve requests
func (h *HealthHandler) handleReadiness(c *gin.Context) {
	status := h.checker.Check()

	if status.Status == "healthy" {
		api.RespondWith(c, http.StatusOK, gin.H{
			"status": "ready",
			"message": "Service is ready to serve requests",
		})
	} else {
		api.RespondWithError(c, api.NewError(
			api.ErrCodeInternalServer,
			"Service is not ready: "+status.Message,
			http.StatusServiceUnavailable,
		))
	}
}

// handleAppHealth returns health status for a specific app
func (h *HealthHandler) handleAppHealth(c *gin.Context) {
	appName := c.Param("appName")
	appHealth := h.checker.CheckApp(appName)

	if appHealth.Status == "not_found" {
		api.RespondWithError(c, api.NewError(
			api.ErrCodeNotFound,
			"App not found: "+appName,
			http.StatusNotFound,
		))
		return
	}

	api.RespondWith(c, http.StatusOK, appHealth)
}
