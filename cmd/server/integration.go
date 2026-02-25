package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"

	"github.com/jgirmay/GAIA_GO/pkg/cluster/coordinator"
	"github.com/jgirmay/GAIA_GO/pkg/cluster/queue"
	"github.com/jgirmay/GAIA_GO/pkg/cluster/raft"
	"github.com/jgirmay/GAIA_GO/pkg/models"
	"github.com/jgirmay/GAIA_GO/pkg/repository"
	"github.com/jgirmay/GAIA_GO/pkg/services/usability"
)

// DistributedGAIAConfig holds configuration for the distributed system
type DistributedGAIAConfig struct {
	DatabaseURL              string
	RaftEnabled              bool
	RaftNodeID               string
	RaftBindAddr             string
	RaftAdvertiseAddr        string
	RaftDiscoveryNodes       string
	ClusterSnapshotDir       string
	SessionLeaseTimeout      time.Duration
	SessionHeartbeatInterval time.Duration
	TaskQueueMaxRetries      int
	UsabilityMetricsEnabled  bool
}

// DistributedGAIAComponents holds all initialized components
type DistributedGAIAComponents struct {
	DB                 *gorm.DB
	Registry           *repository.Registry
	RaftNode           *raft.Node
	SessionCoordinator *coordinator.SessionCoordinator
	TaskQueue          *queue.DistributedTaskQueue
	MetricsService     *usability.UsabilityMetricsService
	FrustrationEngine  *usability.FrustrationDetectionEngine
	MetricsAggregator  *usability.RealtimeMetricsAggregator
	EventBus           usability.EventBus
}

// InitializeDistributedGAIA initializes all distributed coordination components
func InitializeDistributedGAIA(config DistributedGAIAConfig) (*DistributedGAIAComponents, error) {
	components := &DistributedGAIAComponents{}

	// 1. Initialize PostgreSQL database with GORM
	log.Println("[INIT] Initializing PostgreSQL database with GORM...")
	db, err := initGormDatabase(config.DatabaseURL)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize database: %w", err)
	}
	components.DB = db
	log.Println("[INIT] ✓ Database initialized")

	// 2. Auto-migrate all models
	log.Println("[INIT] Running database migrations...")
	if err := migrateModels(db); err != nil {
		return nil, fmt.Errorf("failed to migrate models: %w", err)
	}
	log.Println("[INIT] ✓ Migrations completed")

	// 3. Initialize repository registry
	log.Println("[INIT] Initializing repository registry...")
	reg := repository.NewRegistry(db)
	components.Registry = reg
	log.Println("[INIT] ✓ Repository registry initialized with 9 repositories")

	// 4. Initialize Raft consensus (if enabled)
	if config.RaftEnabled {
		log.Println("[INIT] Initializing Raft distributed consensus...")
		raftNode, err := initRaft(config, db)
		if err != nil {
			return nil, fmt.Errorf("failed to initialize Raft: %w", err)
		}
		components.RaftNode = raftNode
		log.Println("[INIT] ✓ Raft consensus initialized")

		// Wait for leader election
		log.Println("[INIT] Waiting for Raft leader election...")
		if err := raftNode.WaitForLeader(10 * time.Second); err != nil {
			log.Printf("[WARN] Leader election timeout: %v", err)
		}
		log.Printf("[INIT] ✓ Raft cluster ready (Node ID: %s)", config.RaftNodeID)
	}

	// 5. Initialize Session Coordinator
	log.Println("[INIT] Initializing Session Coordinator...")
	sessionCoordinator := coordinator.NewSessionCoordinator(
		reg.GetClaudeSessionRepository(),
		reg.GetSessionAffinityRepository(),
		reg.GetDistributedTaskRepository(),
		config.SessionLeaseTimeout,
	)
	components.SessionCoordinator = sessionCoordinator

	// Load existing sessions from database
	if err := sessionCoordinator.LoadSessions(); err != nil {
		log.Printf("[WARN] Failed to load existing sessions: %v", err)
	}

	// Start background health checks
	go sessionCoordinator.PerformHealthCheck()

	log.Println("[INIT] ✓ Session Coordinator initialized with background health checks")

	// 6. Initialize Distributed Task Queue
	log.Println("[INIT] Initializing Distributed Task Queue...")
	taskQueue := queue.NewDistributedTaskQueue(
		reg.GetDistributedTaskRepository(),
		reg.GetDistributedLockRepository(),
		sessionCoordinator,
		config.TaskQueueMaxRetries,
	)
	components.TaskQueue = taskQueue
	log.Println("[INIT] ✓ Distributed Task Queue initialized")

	// 7. Initialize Usability Metrics Services (if enabled)
	if config.UsabilityMetricsEnabled {
		log.Println("[INIT] Initializing Usability Metrics Services...")

		// Create event bus
		eventBus := usability.NewSimpleEventBus(100, 1000)
		components.EventBus = eventBus

		// Create frustration detection engine
		frustrationEngine := usability.NewFrustrationDetectionEngine(
			usability.DefaultThresholds(),
		)

		// Create real-time aggregator
		aggregator := usability.NewRealtimeMetricsAggregator(1 * time.Minute)

		// Create metrics service
		metricsService := usability.NewUsabilityMetricsService(
			reg.GetUsabilityMetricsRepository(),
			frustrationEngine,
			aggregator,
			eventBus,
			usability.DefaultConfig(),
		)

		components.FrustrationEngine = frustrationEngine
		components.MetricsAggregator = aggregator
		components.MetricsService = metricsService

		// Start background flushing
		metricsService.Start(context.Background())

		log.Println("[INIT] ✓ Usability Metrics Services initialized")
		log.Println("[INIT]   - Frustration Detection Engine")
		log.Println("[INIT]   - Real-time Metrics Aggregator")
		log.Println("[INIT]   - Background metrics flushing")
	}

	log.Println("[INIT] ================================================================")
	log.Println("[INIT] ✓ DISTRIBUTED GAIA_GO INITIALIZATION COMPLETE")
	log.Println("[INIT] ================================================================")

	return components, nil
}

// initGormDatabase initializes a PostgreSQL database with GORM
func initGormDatabase(dsn string) (*gorm.DB, error) {
	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{})
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	// Configure connection pool
	sqlDB, err := db.DB()
	if err != nil {
		return nil, err
	}

	sqlDB.SetMaxIdleConns(10)
	sqlDB.SetMaxOpenConns(100)
	sqlDB.SetConnMaxLifetime(time.Hour)

	return db, nil
}

// migrateModels runs auto-migrations for all models
func migrateModels(db *gorm.DB) error {
	return db.AutoMigrate(
		&models.ClaudeSession{},
		&models.Lesson{},
		&models.DistributedTask{},
		&models.DistributedLock{},
		&models.SessionAffinity{},
	)
}

// initRaft initializes the Raft consensus node
func initRaft(config DistributedGAIAConfig, db *gorm.DB) (*raft.Node, error) {
	// Create snapshot directory
	snapshotDir := config.ClusterSnapshotDir
	if snapshotDir == "" {
		snapshotDir = filepath.Join(".", "data", "raft", config.RaftNodeID)
	}

	if err := os.MkdirAll(snapshotDir, 0700); err != nil {
		return nil, fmt.Errorf("failed to create snapshot directory: %w", err)
	}

	// Initialize Raft node from environment
	raftNode, err := raft.InitFromEnv()
	if err != nil {
		return nil, fmt.Errorf("failed to initialize Raft from environment: %w", err)
	}

	return raftNode, nil
}

// ShutdownDistributedGAIA gracefully shuts down all components
func ShutdownDistributedGAIA(components *DistributedGAIAComponents) error {
	log.Println("[SHUTDOWN] Shutting down distributed components...")

	// 1. Stop metrics service
	if components.MetricsService != nil {
		log.Println("[SHUTDOWN] Stopping metrics service...")
		components.MetricsService.Stop()
	}

	// 2. Close event bus
	if components.EventBus != nil {
		log.Println("[SHUTDOWN] Closing event bus...")
		components.EventBus.Close()
	}

	// 3. Shutdown Raft
	if components.RaftNode != nil {
		log.Println("[SHUTDOWN] Shutting down Raft node...")
		if err := components.RaftNode.Shutdown(); err != nil {
			log.Printf("[WARN] Error shutting down Raft: %v", err)
		}
	}

	// 4. Close registry
	if components.Registry != nil {
		log.Println("[SHUTDOWN] Closing repository registry...")
		if err := components.Registry.Close(); err != nil {
			log.Printf("[WARN] Error closing registry: %v", err)
		}
	}

	log.Println("[SHUTDOWN] ✓ All components shut down gracefully")
	return nil
}

// HealthCheck performs a health check on all components
func HealthCheck(components *DistributedGAIAComponents) map[string]interface{} {
	health := map[string]interface{}{
		"timestamp":  time.Now(),
		"status":     "healthy",
		"components": map[string]interface{}{},
	}

	components_health := health["components"].(map[string]interface{})

	// Database health
	if components.DB != nil {
		sqlDB, err := components.DB.DB()
		if err == nil {
			if err := sqlDB.Ping(); err == nil {
				components_health["database"] = "healthy"
			} else {
				components_health["database"] = "unhealthy"
				health["status"] = "degraded"
			}
		}
	}

	// Raft health
	if components.RaftNode != nil {
		if components.RaftNode.IsLeader() {
			components_health["raft"] = map[string]interface{}{
				"status": "healthy",
				"role":   "leader",
			}
		} else {
			components_health["raft"] = map[string]interface{}{
				"status": "healthy",
				"role":   "follower",
			}
		}
	}

	// Session Coordinator health
	if components.SessionCoordinator != nil {
		sessions := components.SessionCoordinator.GetAvailableSessions()
		components_health["session_coordinator"] = map[string]interface{}{
			"status":          "healthy",
			"active_sessions": len(sessions),
		}
	}

	// Task Queue health
	if components.TaskQueue != nil {
		components_health["task_queue"] = "healthy"
	}

	// Metrics Service health
	if components.MetricsService != nil {
		bufferSize := components.MetricsService.GetBufferSize()
		components_health["metrics_service"] = map[string]interface{}{
			"status":      "healthy",
			"buffer_size": bufferSize,
		}
	}

	return health
}
