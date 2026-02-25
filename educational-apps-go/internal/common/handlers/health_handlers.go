package handlers

import (
	"net/http"

	"github.com/architect/educational-apps/internal/common/health"
	"github.com/gin-gonic/gin"
)

// HealthHandler manages health check endpoints
type HealthHandler struct {
	checker *health.HealthChecker
}

// NewHealthHandler creates a new health handler
func NewHealthHandler(checker *health.HealthChecker) *HealthHandler {
	return &HealthHandler{
		checker: checker,
	}
}

// Health returns comprehensive health status
// GET /health
func (h *HealthHandler) Health(c *gin.Context) {
	status := h.checker.Check()
	c.JSON(http.StatusOK, status)
}

// Readiness returns readiness status
// GET /health/readiness
func (h *HealthHandler) Readiness(c *gin.Context) {
	if h.checker.IsReady() {
		c.JSON(http.StatusOK, gin.H{"ready": true})
		return
	}

	c.JSON(http.StatusServiceUnavailable, gin.H{"ready": false})
}

// Liveness returns liveness status
// GET /health/liveness
func (h *HealthHandler) Liveness(c *gin.Context) {
	if h.checker.IsAlive() {
		c.JSON(http.StatusOK, gin.H{"alive": true})
		return
	}

	c.JSON(http.StatusServiceUnavailable, gin.H{"alive": false})
}

// Metrics returns current system metrics
// GET /health/metrics
func (h *HealthHandler) Metrics(c *gin.Context) {
	metrics := h.checker.GetMetrics()
	c.JSON(http.StatusOK, metrics)
}

// Detailed returns detailed health information
// GET /health/detailed
func (h *HealthHandler) Detailed(c *gin.Context) {
	status := h.checker.Check()

	// Add additional details
	detailed := gin.H{
		"status":    status.Status,
		"timestamp": status.Timestamp,
		"version":   status.Version,
		"checks":    status.Checks,
		"metrics":   h.checker.GetMetrics(),
		"duration_ms": status.Duration,
	}

	c.JSON(http.StatusOK, detailed)
}
