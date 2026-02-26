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
	"github.com/jgirmay/GAIA_GO/pkg/services/usability"
)

func main() {
	// Load environment configuration
	port := getEnv("PORT", "8080")
	dbURL := getEnv("DATABASE_URL", "postgres://user:password@localhost:5432/gaia_go")

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

	// Register teacher dashboard routes
	log.Println("[INIT] Registering Teacher Dashboard routes...")
	handlers.RegisterTeacherDashboardRoutes(
		router,
		metricsService,
		frustrationEngine,
		aggregator,
		registry.TeacherDashboardAlertRepository,
	)
	log.Println("[INIT] ✓ Teacher Dashboard routes registered")

	// Health check endpoint
	router.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"healthy"}`))
	})

	// Print available routes
	log.Println("\n===============================================================")
	log.Println("GAIA_GO Phase 9 - Teacher Usability Monitoring")
	log.Println("===============================================================\n")
	log.Println("Available Endpoints:\n")
	log.Println("Health & Status:")
	log.Println("  GET    /health                           - System health check\n")
	log.Println("Teacher Dashboard:")
	log.Println("  GET    /api/dashboard/classroom/{classroomID}/metrics  - Classroom metrics")
	log.Println("  GET    /api/dashboard/student/frustration - Student frustration metrics")
	log.Println("  POST   /api/dashboard/interventions      - Record intervention")
	log.Println("  GET    /api/dashboard/struggling-students - Struggling students list")
	log.Println("  GET    /api/dashboard/health             - Dashboard health status\n")
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
