package guessing

import (
	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/metrics"
	"github.com/jgirmay/GAIA_GO/internal/session"
)

// RegisterHandlers registers all guessing app routes
func RegisterHandlers(router *gin.RouterGroup, app *GuessingApp, sessionMgr *session.Manager, businessMetrics *metrics.BusinessMetricsRegistry) {
	// Register all routes from the app
	app.RegisterRoutes(router)
}
