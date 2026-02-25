package http

import (
	"fmt"
	"net/http"
	"time"

	"github.com/go-chi/chi"

	"architect-go/pkg/cache"
	"architect-go/pkg/errors"
	"architect-go/pkg/events"
	"architect-go/pkg/http/handlers"
	"architect-go/pkg/repository"
	"architect-go/pkg/services"
)

// Server represents the HTTP server
type Server struct {
	Router            *chi.Mux
	Port              string
	AnalyticsRegistry *services.AnalyticsRegistry
	AnalyticsHandlers *handlers.AnalyticsHandlers
	OpenAPIHandler    *handlers.OpenAPIHandler
}

// NewServer creates a new HTTP server with analytics services
func NewServer(port string, repos *repository.Registry) *Server {
	router := chi.NewRouter()
	cacheManager := cache.NewCacheManager()

	// Create analytics registry
	analyticsRegistry := services.NewAnalyticsRegistryWithCache(repos, cacheManager)

	// Create handlers
	errorHandler := &errors.ErrorHandler{Debug: false, Verbose: true}
	analyticsHandlers := handlers.NewAnalyticsHandlers(
		analyticsRegistry.EventAnalyticsService,
		analyticsRegistry.PresenceAnalyticsService,
		analyticsRegistry.ActivityAnalyticsService,
		analyticsRegistry.PerformanceAnalyticsService,
		analyticsRegistry.UserAnalyticsService,
		analyticsRegistry.ErrorAnalyticsService,
		errorHandler,
	)

	openAPIHandler := &handlers.OpenAPIHandler{}

	server := &Server{
		Router:            router,
		Port:              port,
		AnalyticsRegistry: analyticsRegistry,
		AnalyticsHandlers: analyticsHandlers,
		OpenAPIHandler:    openAPIHandler,
	}

	// Setup routes
	server.setupRoutes()

	return server
}

// setupRoutes configures all HTTP routes
func (s *Server) setupRoutes() {
	// Health check
	s.Router.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"healthy"}`))
	})

	// OpenAPI documentation
	s.Router.Get("/api/openapi.json", s.OpenAPIHandler.ServeOpenAPI)
	s.Router.Get("/api/docs", s.OpenAPIHandler.ServeSwaggerUI)

	// Analytics API routes
	s.Router.Route("/api/analytics", func(r chi.Router) {
		// Event analytics
		r.Route("/events", func(r chi.Router) {
			r.Get("/timeline", s.AnalyticsHandlers.GetEventTimeline)
			r.Get("/trends", s.AnalyticsHandlers.GetEventTrends)
			r.Get("/by-type", s.AnalyticsHandlers.GetEventsByType)
			r.Get("/funnel", s.AnalyticsHandlers.GetFunnelAnalysis)
		})

		// Presence analytics
		r.Route("/presence", func(r chi.Router) {
			r.Get("/trends", s.AnalyticsHandlers.GetPresenceTrends)
			r.Get("/engagement", s.AnalyticsHandlers.GetUserEngagementMetrics)
			r.Get("/heatmap", s.AnalyticsHandlers.GetPresenceHeatmap)
		})

		// Activity analytics
		r.Route("/activity", func(r chi.Router) {
			r.Get("/trends", s.AnalyticsHandlers.GetActivityTrends)
			r.Get("/top-users", s.AnalyticsHandlers.GetTopActiveUsers)
		})

		// Performance analytics
		r.Route("/performance", func(r chi.Router) {
			r.Get("/requests", s.AnalyticsHandlers.GetRequestMetrics)
			r.Get("/system", s.AnalyticsHandlers.GetSystemMetrics)
			r.Get("/database", s.AnalyticsHandlers.GetDatabaseMetrics)
			r.Get("/cache", s.AnalyticsHandlers.GetCacheMetrics)
		})

		// User analytics
		r.Route("/users", func(r chi.Router) {
			r.Get("/growth", s.AnalyticsHandlers.GetUserGrowth)
			r.Get("/retention", s.AnalyticsHandlers.GetUserRetention)
		})

		// Error analytics
		r.Route("/errors", func(r chi.Router) {
			r.Get("/metrics", s.AnalyticsHandlers.GetErrorMetrics)
			r.Get("/top", s.AnalyticsHandlers.GetTopErrors)
			r.Get("/critical", s.AnalyticsHandlers.GetCriticalErrors)
		})
	})
}

// ListenAndServe starts the HTTP server
func (s *Server) ListenAndServe() error {
	return http.ListenAndServe(s.Port, s.Router)
}
