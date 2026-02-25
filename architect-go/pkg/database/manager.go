package database

import (
	"context"
	"fmt"
	"log"
	"time"

	"gorm.io/gorm"

	"architect-go/pkg/config"
)

// Manager manages database lifecycle and connection pool
type Manager struct {
	db   *gorm.DB
	pool *ConnectionPool
}

// NewManager creates a new database manager
func NewManager(db *gorm.DB, config *config.Config) (*Manager, error) {
	poolConfig := PoolConfig{
		MinConnections:      config.Database.MinConnections,
		MaxConnections:      config.Database.MaxConnections,
		MaxIdleTime:         15 * time.Second,
		MaxLifetime:         time.Hour,
		ConnectionTimeout:   10 * time.Second,
		HealthCheckInterval: 30 * time.Second,
	}

	pool, err := NewConnectionPool(db, poolConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create connection pool: %w", err)
	}

	return &Manager{
		db:   db,
		pool: pool,
	}, nil
}

// Start initializes the manager and begins monitoring
func (m *Manager) Start(ctx context.Context) error {
	log.Println("Starting database manager...")

	// Wait for database to be healthy
	healthCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	if err := m.pool.WaitForHealthy(healthCtx); err != nil {
		return fmt.Errorf("database not healthy: %w", err)
	}

	// Warm up connection pool
	if err := m.pool.WarmUp(ctx); err != nil {
		log.Printf("Warning: Failed to warm up connection pool: %v", err)
	}

	// Start health checks
	m.pool.Start()

	log.Println("Database manager started successfully")
	return nil
}

// Stop gracefully stops the manager
func (m *Manager) Stop() error {
	log.Println("Stopping database manager...")
	m.pool.Stop()

	sqlDB, err := m.db.DB()
	if err != nil {
		return fmt.Errorf("failed to get SQL DB: %w", err)
	}

	if err := sqlDB.Close(); err != nil {
		return fmt.Errorf("failed to close database: %w", err)
	}

	log.Println("Database manager stopped")
	return nil
}

// GetDB returns the GORM DB instance
func (m *Manager) GetDB() *gorm.DB {
	return m.db
}

// GetPool returns the connection pool
func (m *Manager) GetPool() *ConnectionPool {
	return m.pool
}

// Health checks the database health
func (m *Manager) Health() error {
	return m.db.WithContext(context.Background()).Raw("SELECT 1").Error
}

// Stats returns pool statistics
func (m *Manager) Stats() map[string]interface{} {
	return m.pool.GetStats()
}

// Metrics returns detailed metrics
func (m *Manager) Metrics() PoolMetrics {
	return m.pool.GetMetrics()
}

// Reset resets the connection pool
func (m *Manager) Reset(newConfig PoolConfig) error {
	return m.pool.Reset(newConfig)
}

// Drain drains idle connections
func (m *Manager) Drain() error {
	return m.pool.Drain()
}

// MigrationResults holds the results of running migrations
type MigrationResults struct {
	Success  bool
	Message  string
	Duration time.Duration
	Error    error
}

// RunMigrations runs all database migrations
func (m *Manager) RunMigrations() MigrationResults {
	start := time.Now()

	log.Println("Running database migrations...")

	// Get all models from models package
	models := getAllModels()

	// Run migrations
	if err := m.db.AutoMigrate(models...); err != nil {
		return MigrationResults{
			Success:  false,
			Message:  "Migration failed",
			Duration: time.Since(start),
			Error:    err,
		}
	}

	duration := time.Since(start)
	log.Printf("Migrations completed successfully in %v", duration)

	return MigrationResults{
		Success:  true,
		Message:  "All migrations completed successfully",
		Duration: duration,
	}
}

// getAllModels returns all domain models for migration
func getAllModels() []interface{} {
	return []interface{}{
		// Import from models package - these are used by GORM
		// This is a placeholder - actual models are in pkg/models/models.go
	}
}

// Health check constants
const (
	HealthCheckSuccess = "healthy"
	HealthCheckFailure = "unhealthy"
)

// HealthCheckResult represents the result of a health check
type HealthCheckResult struct {
	Status               string
	Database             bool
	ConnectionPool       bool
	OpenConnections      int
	InUseConnections     int
	IdleConnections      int
	HealthCheckFailures  int
	LastHealthCheckTime  time.Time
	ResponseTimeMs       int64
}

// PerformHealthCheck performs a comprehensive health check
func (m *Manager) PerformHealthCheck(ctx context.Context) HealthCheckResult {
	start := time.Now()

	result := HealthCheckResult{
		Status: HealthCheckSuccess,
	}

	// Check database connectivity
	err := m.Health()
	result.Database = err == nil

	// Get pool metrics
	metrics := m.Metrics()
	result.ConnectionPool = metrics.IsHealthy
	result.OpenConnections = metrics.OpenConnections
	result.InUseConnections = metrics.InUseConnections
	result.IdleConnections = metrics.IdleConnections
	result.HealthCheckFailures = metrics.HealthCheckFailures
	result.LastHealthCheckTime = metrics.LastHealthCheckTime

	// Set overall status
	if !result.Database || !result.ConnectionPool {
		result.Status = HealthCheckFailure
	}

	result.ResponseTimeMs = time.Since(start).Milliseconds()
	return result
}
