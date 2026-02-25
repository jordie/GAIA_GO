package http

import (
	"net/http"

	"github.com/go-chi/chi"

<<<<<<< HEAD
	"architect-go/pkg/auth"
	"architect-go/pkg/cache"
	"architect-go/pkg/config"
	"architect-go/pkg/database"
=======
	"architect-go/pkg/cache"
>>>>>>> origin/feature/fix-db-connections-workers-distributed-0107
	"architect-go/pkg/errors"
	"architect-go/pkg/events"
	"architect-go/pkg/http/handlers"
	"architect-go/pkg/repository"
	"architect-go/pkg/services"
)

// Server represents the HTTP server
type Server struct {
<<<<<<< HEAD
	httpServer   *http.Server
	router       chi.Router
	dbManager    *database.Manager
	config       *config.Config
	startTime    time.Time
	wsHub        *websocket.Hub
	repos        *repository.Registry
	services     *services.Registry
	errHandler   *errors.Handler
	sessionMgr   *auth.SessionManager
	cache        *cache.CacheManager
	dispatcher   events.EventDispatcher
	handlers     *struct {
		project           *handlers.ProjectHandlers
		task              *handlers.TaskHandlers
		user              *handlers.UserHandlers
		auth              *handlers.AuthHandlers
		dashboard         *handlers.DashboardHandlers
		worker            *handlers.WorkerHandlers
		notification      *handlers.NotificationHandlers
		webhook           *handlers.WebhookHandlers
		eventLog          *handlers.EventLogHandlers
		auditLog          *handlers.AuditLogHandlers
		integration       *handlers.IntegrationHandlers
		integrationHealth *handlers.IntegrationHealthHandlers
		sessionTracking   *handlers.SessionTrackingHandlers
		realTimeEvent     *handlers.RealTimeEventHandlers
		errorLog          *handlers.ErrorLogHandlers
		analytics         *handlers.AnalyticsHandlers
		presence          *handlers.PresenceHandlers
		activity          *handlers.ActivityHandlers
	}
=======
	Router *chi.Mux
	Port   string

	// Service registry
	AnalyticsRegistry *services.AnalyticsRegistry

	// HTTP Handlers
	AnalyticsHandlers *handlers.AnalyticsHandlers
	OpenAPIHandler    *handlers.OpenAPIHandler
>>>>>>> origin/feature/fix-db-connections-workers-distributed-0107
}

// NewServer creates a new HTTP server with analytics services
func NewServer(port string, repos *repository.Registry) *Server {
	router := chi.NewRouter()
	cacheManager := cache.NewCacheManager()

	// Create analytics registry
	analyticsRegistry := services.NewAnalyticsRegistryWithCache(repos, cacheManager)

<<<<<<< HEAD
	// Initialize cache manager
	cm := cache.NewCacheManager()

	// Initialize services with cache support and hub-aware real-time service
	svc := services.NewRegistryWithCacheAndHub(repos, cm, wsHub)

	// Initialize dispatcher
	dispatcher := events.NewHubEventDispatcher(wsHub)
=======
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
>>>>>>> origin/feature/fix-db-connections-workers-distributed-0107

	openAPIHandler := &handlers.OpenAPIHandler{}

<<<<<<< HEAD
	// Initialize session manager
	passwordMgr := auth.NewPasswordManager()
	tokenMgr := auth.NewTokenManager(config.Auth.SecretKey, config.Auth.TokenExpiry, config.Auth.Issuer)
	sessionMgr := auth.NewSessionManager(repos.UserRepository, repos.SessionRepository, passwordMgr, tokenMgr, config.Auth.SessionExpiry)

	// Initialize handlers with dispatcher support for core handlers
	handlerRegistry := &struct {
		project           *handlers.ProjectHandlers
		task              *handlers.TaskHandlers
		user              *handlers.UserHandlers
		auth              *handlers.AuthHandlers
		dashboard         *handlers.DashboardHandlers
		worker            *handlers.WorkerHandlers
		notification      *handlers.NotificationHandlers
		webhook           *handlers.WebhookHandlers
		eventLog          *handlers.EventLogHandlers
		auditLog          *handlers.AuditLogHandlers
		integration       *handlers.IntegrationHandlers
		integrationHealth *handlers.IntegrationHealthHandlers
		sessionTracking   *handlers.SessionTrackingHandlers
		realTimeEvent     *handlers.RealTimeEventHandlers
		errorLog          *handlers.ErrorLogHandlers
		analytics         *handlers.AnalyticsHandlers
		presence          *handlers.PresenceHandlers
		activity          *handlers.ActivityHandlers
	}{
		project:           handlers.NewProjectHandlersWithDispatcher(svc.ProjectService, errHandler, dispatcher),
		task:              handlers.NewTaskHandlersWithDispatcher(svc.TaskService, errHandler, dispatcher),
		user:              handlers.NewUserHandlers(svc.UserService, errHandler),
		auth:              handlers.NewAuthHandlers(sessionMgr, svc.UserService, errHandler),
		dashboard:         handlers.NewDashboardHandlers(svc.DashboardService, errHandler),
		worker:            handlers.NewWorkerHandlers(svc.WorkerService, errHandler),
		notification:      handlers.NewNotificationHandlers(svc.NotificationService, errHandler),
		webhook:           handlers.NewWebhookHandlers(svc.WebhookService, errHandler),
		eventLog:          handlers.NewEventLogHandlers(svc.EventLogService, errHandler),
		auditLog:          handlers.NewAuditLogHandlers(svc.AuditLogService, errHandler),
		integration:       handlers.NewIntegrationHandlers(svc.IntegrationService, errHandler),
		integrationHealth: handlers.NewIntegrationHealthHandlers(svc.IntegrationHealthService, errHandler),
		sessionTracking:   handlers.NewSessionTrackingHandlers(svc.SessionTrackingService, errHandler),
		realTimeEvent:     handlers.NewRealTimeEventHandlersWithDispatcher(svc.RealTimeEventService, errHandler, dispatcher),
		errorLog:          handlers.NewErrorLogHandlers(svc.ErrorLogService, errHandler),
		analytics:         handlers.NewAnalyticsHandlers(svc.EventAnalyticsService, svc.ErrorAnalyticsService, svc.PerformanceAnalyticsService, svc.UserAnalyticsService),
		presence:          handlers.NewPresenceHandlersWithDispatcher(svc.PresenceService, errHandler, dispatcher),
		activity:          handlers.NewActivityHandlersWithDispatcher(svc.ActivityService, errHandler, dispatcher),
	}

	srv := &Server{
		router:      router,
		dbManager:   dbManager,
		config:      config,
		startTime:   time.Now(),
		wsHub:       wsHub,
		repos:       repos,
		services:    svc,
		errHandler:  errHandler,
		sessionMgr:  sessionMgr,
		cache:       cm,
		dispatcher:  dispatcher,
		handlers:    handlerRegistry,
		httpServer: &http.Server{
			Addr:         fmt.Sprintf("%s:%d", config.Server.Host, config.Server.Port),
			Handler:      router,
			ReadTimeout:  config.Server.ReadTimeout,
			WriteTimeout: config.Server.WriteTimeout,
			IdleTimeout:  15 * time.Second,
		},
	}

	// Setup middleware
	srv.setupMiddleware()

=======
	server := &Server{
		Router:            router,
		Port:              port,
		AnalyticsRegistry: analyticsRegistry,
		AnalyticsHandlers: analyticsHandlers,
		OpenAPIHandler:    openAPIHandler,
	}

>>>>>>> origin/feature/fix-db-connections-workers-distributed-0107
	// Setup routes
	server.setupRoutes()

	return server
}

// setupRoutes configures all HTTP routes
func (s *Server) setupRoutes() {
<<<<<<< HEAD
	// Health check route
	s.router.Get("/health", s.healthHandler)

	// Metrics route
	s.router.Get("/metrics", s.metricsHandler)

	// WebSocket route with authentication
	wsHandler := websocket.NewClientHandlerWithAuth(s.wsHub, s.sessionMgr)
	s.router.Handle("/ws", wsHandler)

	// API routes
	s.router.Route("/api", func(r chi.Router) {
		// Projects routes
		r.Route("/projects", func(pr chi.Router) {
			handlers.RegisterProjectRoutes(pr, s.handlers.project)
		})

		// Tasks routes
		r.Route("/tasks", func(tr chi.Router) {
			handlers.RegisterTaskRoutes(tr, s.handlers.task)
		})

		// Users routes
		r.Route("/users", func(ur chi.Router) {
			handlers.RegisterUserRoutes(ur, s.handlers.user)
		})

		// Auth routes
		r.Route("/auth", func(ar chi.Router) {
			handlers.RegisterAuthRoutes(ar, s.handlers.auth)
		})

		// Dashboard routes
		r.Route("/dashboard", func(dr chi.Router) {
			handlers.RegisterDashboardRoutes(dr, s.handlers.dashboard)
		})

		// Workers routes
		r.Route("/workers", func(wr chi.Router) {
			handlers.RegisterWorkerRoutes(wr, s.handlers.worker)
		})

		// Notifications routes (Phase 3.2 Track A)
		r.Route("/notifications", func(nr chi.Router) {
			handlers.RegisterNotificationRoutes(nr, s.handlers.notification)
		})

		// Webhooks routes (Phase 3.2 Track A)
		r.Route("/webhooks", func(wr chi.Router) {
			handlers.RegisterWebhookRoutes(wr, s.handlers.webhook)
		})

		// Event Log routes (Phase 3.2 Track A)
		r.Route("/event-logs", func(elr chi.Router) {
			handlers.RegisterEventLogRoutes(elr, s.handlers.eventLog)
		})

		// Audit Log routes (Phase 3.2 Track A)
		r.Route("/audit-logs", func(alr chi.Router) {
			handlers.RegisterAuditLogRoutes(alr, s.handlers.auditLog)
		})

		// Integration routes (Phase 3.2 Track B)
		r.Route("/integrations", func(ir chi.Router) {
			handlers.RegisterIntegrationRoutes(ir, s.handlers.integration)
		})

		// Integration Health routes (Phase 3.2 Track C)
		r.Route("/integrations/health", func(ihr chi.Router) {
			handlers.RegisterIntegrationHealthRoutes(ihr, s.handlers.integrationHealth)
		})

		// Session Tracking routes (Phase 3.2 Track D)
		r.Route("/sessions", func(str chi.Router) {
			handlers.RegisterSessionTrackingRoutes(str, s.handlers.sessionTracking)
		})

		// RealTime Event routes (Phase 3.2 Track D)
		r.Route("/realtime", func(rer chi.Router) {
			handlers.RegisterRealTimeEventRoutes(rer, s.handlers.realTimeEvent)
		})

		// Error Log routes (Phase 3.2 Track D)
		r.Route("/errors", func(elr chi.Router) {
			handlers.RegisterErrorLogRoutes(elr, s.handlers.errorLog)
		})

		// Analytics routes (Phase 3.3.1)
		r.Route("/analytics", func(ar chi.Router) {
			handlers.RegisterAnalyticsRoutes(ar, s.handlers.analytics)
		})

		// Presence routes (Phase 4.4)
		r.Route("/presence", func(pr chi.Router) {
			handlers.RegisterPresenceRoutes(pr, s.handlers.presence)
		})

		// Activity routes (Phase 4.4)
		r.Route("/activity", func(ar chi.Router) {
			handlers.RegisterActivityRoutes(ar, s.handlers.activity)
		})

		// System routes
		r.Get("/system/stats", s.systemStatsHandler)
		r.Get("/system/database/health", s.databaseHealthHandler)
=======
	// Health check
	s.Router.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"healthy"}`))
>>>>>>> origin/feature/fix-db-connections-workers-distributed-0107
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
