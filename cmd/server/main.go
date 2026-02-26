package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"

	"github.com/jgirmay/GAIA_GO/pkg/http/handlers"
	"github.com/jgirmay/GAIA_GO/pkg/repository"
	"github.com/jgirmay/GAIA_GO/pkg/services/claude_confirm"
	"github.com/jgirmay/GAIA_GO/pkg/services/rate_limiting"
	"github.com/jgirmay/GAIA_GO/pkg/services/websocket"
	"github.com/jgirmay/GAIA_GO/pkg/services/usability"
)

func main() {
	// Load environment configuration
	port := getEnv("PORT", "8080")
	dbURL := getEnv("DATABASE_URL", "postgres://jgirmay@localhost:5432/gaia_go?sslmode=disable")

	// Initialize database with GORM
	log.Println("[INIT] Initializing PostgreSQL database...")
	db, err := gorm.Open(postgres.Open(dbURL), &gorm.Config{})
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	log.Println("[INIT] ✓ Database connection established")

	// Initialize repository registry
	log.Println("[INIT] Initializing repository registry...")
	registry := repository.NewRegistry(db)
	if err := registry.Initialize(); err != nil {
		log.Fatalf("Failed to initialize repository registry: %v", err)
	}
	log.Println("[INIT] ✓ Repository registry initialized")

	// Auto-migrate Claude confirmation tables
	log.Println("[INIT] Migrating Claude confirmation schema...")
	if err := db.AutoMigrate(
		&claude_confirm.ConfirmationRequest{},
		&claude_confirm.ApprovalPattern{},
		&claude_confirm.AIAgentDecision{},
		&claude_confirm.SessionApprovalPreference{},
	); err != nil {
		log.Fatalf("Failed to migrate Claude confirmation tables: %v", err)
	}
	log.Println("[INIT] ✓ Claude confirmation schema migrated")

	// Initialize usability metrics services
	log.Println("[INIT] Initializing Usability Metrics Services...")

	// Create event bus
	eventBus := usability.NewSimpleEventBus(100, 1000)

	// Create frustration detection engine
	frustrationEngine := usability.NewFrustrationDetectionEngine(
		usability.DefaultThresholds(),
	)

	// Create real-time metrics aggregator
	aggregator := usability.NewRealtimeMetricsAggregator(1 * time.Minute)

	// Create metrics service
	metricsService := usability.NewUsabilityMetricsService(
		registry.UsabilityMetricsRepository,
		frustrationEngine,
		aggregator,
		eventBus,
		usability.DefaultConfig(),
	)

	// Start background metrics flushing
	ctx := context.Background()
	metricsService.Start(ctx)
	log.Println("[INIT] ✓ Usability Metrics Services initialized")
	log.Println("[INIT]   - Frustration Detection Engine")
	log.Println("[INIT]   - Real-time Metrics Aggregator")
	log.Println("[INIT]   - Background metrics flushing started")

	// Create Chi router
	router := chi.NewRouter()

	// Register middleware
	router.Use(middleware.Logger)
	router.Use(middleware.Recoverer)
	router.Use(middleware.RequestID)

	// Initialize Rate Limiting Service (Phase 11)
	log.Println("[INIT] Initializing Rate Limiting Service...")
	rlConfig := rate_limiting.DefaultConfig()
	rateLimiter := rate_limiting.NewPostgresRateLimiter(db, rlConfig)

	// Apply rate limiting middleware to all routes
	router.Use(rate_limiting.WithSessionScope(rateLimiter, rate_limiting.SystemGAIAGO))
	log.Println("[INIT] ✓ Rate Limiting Service initialized")
	log.Println("[INIT]   - Sliding window rate limiting (per-second/minute/hour)")
	log.Println("[INIT]   - Quota-based limits (daily/weekly/monthly)")
	log.Println("[INIT]   - Automatic cleanup and metrics collection")

	// Teacher Dashboard routes are disabled for Phase 11 focus
	// (Teacher dashboard handlers temporarily renamed to avoid build errors)

	// Initialize Claude confirmation system (Phase 10)
	log.Println("[INIT] Initializing Claude Auto-Confirm Patterns System...")

	// Create AI agent for fallback decisions
	aiConfig := claude_confirm.AIAgentConfig{
		Model:           "claude-opus-4.5",
		MaxTokens:       2000,
		DecisionTimeout: 10 * time.Second,
		Enabled:         getEnvBool("CLAUDE_CONFIRM_AI_ENABLED", true),
	}
	aiAgent := claude_confirm.NewAIAgent(db, aiConfig)

	// Create confirmation service
	confirmationService := claude_confirm.NewConfirmationService(db, aiAgent)

	// Register confirmation handlers
	confirmHandlers := handlers.NewClaudeConfirmHandlers(confirmationService)
	confirmHandlers.RegisterRoutes(router)

	log.Println("[INIT] ✓ Claude Auto-Confirm Patterns System initialized")
	if aiConfig.Enabled {
		log.Println("[INIT]   - Pattern Matching Engine")
		log.Println("[INIT]   - AI Agent Fallback (enabled)")
	} else {
		log.Println("[INIT]   - Pattern Matching Engine")
		log.Println("[INIT]   - AI Agent Fallback (disabled)")
	}

	// Initialize Quota Admin Dashboard (Phase 11.4.4)
	log.Println("[INIT] Initializing Admin Dashboard...")
	// Create resource monitor
	resourceMonitor := rate_limiting.NewResourceMonitor()
	// Create quota service with command quotas
	commandQuotaService := rate_limiting.NewCommandQuotaService(db, rateLimiter, resourceMonitor)
	quotaAdminHandlers := handlers.NewQuotaAdminHandlers(commandQuotaService, db)
	quotaAdminHandlers.RegisterRoutes(router)
	log.Println("[INIT] ✓ Admin Dashboard initialized")
	log.Println("[INIT]   - API endpoints: /api/admin/quotas/*")
	log.Println("[INIT]   - Dashboard UI: /admin/quotas")

	// Initialize WebSocket Real-time Updates (Phase 11.4.5)
	log.Println("[INIT] Initializing WebSocket Real-time Updates...")
	broadcaster := websocket.NewQuotaBroadcaster(
		db,
		quotaAdminHandlers.AnalyticsService,
		quotaAdminHandlers.AlertEngine,
		commandQuotaService,
	)
	broadcaster.Start(ctx)
	wsHandlers := handlers.NewQuotaWebSocketHandlers(broadcaster)

	// Register WebSocket routes
	router.Get("/ws/admin/quotas", wsHandlers.HandleQuotaWebSocket)
	router.Get("/api/ws/health", wsHandlers.HandleHealthCheck)
	router.Post("/api/ws/test-broadcast", wsHandlers.BroadcastTestMessage)
	router.Post("/api/ws/test-violation", wsHandlers.BroadcastViolation)
	router.Post("/api/ws/test-alert", wsHandlers.BroadcastAlert)

	log.Println("[INIT] ✓ WebSocket Real-time Updates initialized")
	log.Println("[INIT]   - WebSocket endpoint: /ws/admin/quotas")
	log.Println("[INIT]   - Health check: /api/ws/health")
	log.Println("[INIT]   - Broadcast interval: 5 seconds")
	log.Println("[INIT]   - Heartbeat interval: 10 seconds")

	// Serve static files (CSS, JavaScript)
	router.Handle("/static/*", http.StripPrefix("/static/", http.FileServer(http.Dir("./static"))))

	// Serve template files
	router.Handle("/templates/*", http.StripPrefix("/templates/", http.FileServer(http.Dir("./templates"))))

	// Root redirect to dashboard
	router.Get("/", func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "/admin/quotas", http.StatusMovedPermanently)
	})

	// Health check endpoint
	router.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"healthy"}`))
	})

	// Print available routes
	log.Println("\n===============================================================")
	log.Println("GAIA_GO Phase 9+10 - Teacher Monitoring & Claude Auto-Confirm")
	log.Println("===============================================================\n")
	log.Println("Available Endpoints:\n")
	log.Println("Health & Status:")
	log.Println("  GET    /health                           - System health check\n")
	log.Println("Teacher Dashboard (Phase 9):")
	log.Println("  GET    /api/dashboard/classroom/{classroomID}/metrics  - Classroom metrics")
	log.Println("  GET    /api/dashboard/student/frustration - Student frustration metrics")
	log.Println("  POST   /api/dashboard/interventions      - Record intervention")
	log.Println("  GET    /api/dashboard/struggling-students - Struggling students list")
	log.Println("  GET    /api/dashboard/health             - Dashboard health status\n")
	log.Println("Claude Auto-Confirm Patterns (Phase 10):")
	log.Println("  POST   /api/claude/confirm/request               - Process confirmation request")
	log.Println("  GET    /api/claude/confirm/history/{sessionID}   - Request history")
	log.Println("  GET    /api/claude/confirm/stats/{sessionID}     - Session statistics")
	log.Println("  GET    /api/claude/confirm/patterns              - List patterns")
	log.Println("  POST   /api/claude/confirm/patterns              - Create pattern")
	log.Println("  PUT    /api/claude/confirm/patterns/{patternID}  - Update pattern")
	log.Println("  DELETE /api/claude/confirm/patterns/{patternID}  - Delete pattern")
	log.Println("  GET    /api/claude/confirm/preferences/{sessionID} - Get preferences")
	log.Println("  POST   /api/claude/confirm/preferences/{sessionID} - Set preferences")
	log.Println("  GET    /api/claude/confirm/stats                 - Global statistics\n")
	log.Println("Alternative Routes (RESTful):")
	log.Println("  GET    /api/classrooms/{classroomID}/metrics          - Classroom metrics")
	log.Println("  GET    /api/classrooms/{classroomID}/struggling-students - Struggling students")
	log.Println("  GET    /api/students/{studentID}/frustration          - Student frustration")
	log.Println("  POST   /api/interventions/                            - Record intervention\n")
	log.Println("===============================================================\n")

	// Create HTTP server
	addr := ":" + port
	server := &http.Server{
		Addr:         addr,
		Handler:      router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Graceful shutdown handling
	go func() {
		sigChan := make(chan os.Signal, 1)
		signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
		sig := <-sigChan

		log.Printf("\n[SHUTDOWN] Received signal: %v", sig)
		log.Println("[SHUTDOWN] Initiating graceful shutdown...")

		// Give requests 10 seconds to complete
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		if err := server.Shutdown(shutdownCtx); err != nil {
			log.Printf("[SHUTDOWN] Server shutdown error: %v", err)
		}

		// Stop broadcaster
		log.Println("[SHUTDOWN] Stopping WebSocket broadcaster...")
		broadcaster.Stop()

		// Stop metrics service
		log.Println("[SHUTDOWN] Stopping metrics service...")
		metricsService.Stop()

		// Close event bus
		log.Println("[SHUTDOWN] Closing event bus...")
		eventBus.Close()

		// Close database
		log.Println("[SHUTDOWN] Closing database connection...")
		if sqlDB, err := db.DB(); err == nil {
			sqlDB.Close()
		}

		log.Println("[SHUTDOWN] ✓ Graceful shutdown complete")
		os.Exit(0)
	}()

	// Start server
	log.Printf("[INFO] Starting HTTP server on %s\n", addr)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Server startup error: %v", err)
	}
}

// getEnv gets an environment variable with a default value
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// getEnvBool gets a boolean environment variable with a default value
func getEnvBool(key string, defaultValue bool) bool {
	value := os.Getenv(key)
	if value == "" {
		return defaultValue
	}
	return value == "true" || value == "1" || value == "yes"
}
