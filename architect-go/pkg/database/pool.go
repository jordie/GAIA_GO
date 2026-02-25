package database

import (
	"context"
	"database/sql"
	"fmt"
	"sync"
	"time"

	"gorm.io/gorm"
)

// PoolConfig holds connection pool configuration
type PoolConfig struct {
	MinConnections      int           `yaml:"min_connections"`
	MaxConnections      int           `yaml:"max_connections"`
	MaxIdleTime         time.Duration `yaml:"max_idle_time"`
	MaxLifetime         time.Duration `yaml:"max_lifetime"`
	ConnectionTimeout   time.Duration `yaml:"connection_timeout"`
	HealthCheckInterval time.Duration `yaml:"health_check_interval"`
}

// ConnectionPool manages database connections with health monitoring
type ConnectionPool struct {
	db                *gorm.DB
	sqlDB             *sql.DB
	config            PoolConfig
	stats             *PoolStats
	healthCheckTicker *time.Ticker
	stopChan          chan struct{}
	mu                sync.RWMutex
}

// PoolStats tracks connection pool statistics
type PoolStats struct {
	mu                      sync.RWMutex
	OpenConnections         int
	InUseConnections        int
	IdleConnections         int
	TotalRequests           int64
	TotalWaits              int64
	TotalWaitDuration       time.Duration
	MaxIdleClosedCount      int64
	MaxLifetimeClosedCount  int64
	HealthCheckFailures     int
	LastHealthCheckTime     time.Time
}

// NewConnectionPool creates a new connection pool manager
func NewConnectionPool(db *gorm.DB, config PoolConfig) (*ConnectionPool, error) {
	sqlDB, err := db.DB()
	if err != nil {
		return nil, fmt.Errorf("failed to get SQL DB: %w", err)
	}

	pool := &ConnectionPool{
		db:       db,
		sqlDB:    sqlDB,
		config:   config,
		stats:    &PoolStats{},
		stopChan: make(chan struct{}),
	}

	// Configure connection pool
	pool.sqlDB.SetMaxIdleConns(config.MinConnections)
	pool.sqlDB.SetMaxOpenConns(config.MaxConnections)
	pool.sqlDB.SetConnMaxIdleTime(config.MaxIdleTime)
	pool.sqlDB.SetConnMaxLifetime(config.MaxLifetime)

	return pool, nil
}

// Start begins health checking routine
func (cp *ConnectionPool) Start() {
	cp.healthCheckTicker = time.NewTicker(cp.config.HealthCheckInterval)
	go cp.healthCheckRoutine()
}

// Stop stops the health checking routine
func (cp *ConnectionPool) Stop() {
	close(cp.stopChan)
	if cp.healthCheckTicker != nil {
		cp.healthCheckTicker.Stop()
	}
}

// healthCheckRoutine periodically checks connection pool health
func (cp *ConnectionPool) healthCheckRoutine() {
	for {
		select {
		case <-cp.stopChan:
			return
		case <-cp.healthCheckTicker.C:
			cp.performHealthCheck()
		}
	}
}

// performHealthCheck tests the connection pool
func (cp *ConnectionPool) performHealthCheck() {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	err := cp.sqlDB.PingContext(ctx)
	cp.updateHealthCheckStats(err)
}

// updateHealthCheckStats updates health check statistics
func (cp *ConnectionPool) updateHealthCheckStats(err error) {
	cp.stats.mu.Lock()
	defer cp.stats.mu.Unlock()

	cp.stats.LastHealthCheckTime = time.Now()

	if err != nil {
		cp.stats.HealthCheckFailures++
	} else {
		cp.stats.HealthCheckFailures = 0 // Reset on success
	}
}

// GetStats returns current pool statistics
func (cp *ConnectionPool) GetStats() map[string]interface{} {
	dbStats := cp.sqlDB.Stats()
	cp.stats.mu.RLock()
	defer cp.stats.mu.RUnlock()

	return map[string]interface{}{
		"open_connections":       dbStats.OpenConnections,
		"in_use":                 dbStats.InUse,
		"idle":                   dbStats.Idle,
		"wait_count":             dbStats.WaitCount,
		"wait_duration_ms":       dbStats.WaitDuration.Milliseconds(),
		"max_idle_closed":        dbStats.MaxIdleClosed,
		"max_lifetime_closed":    dbStats.MaxLifetimeClosed,
		"health_check_failures":  cp.stats.HealthCheckFailures,
		"last_health_check_time": cp.stats.LastHealthCheckTime,
		"config": map[string]interface{}{
			"min_connections":       cp.config.MinConnections,
			"max_connections":       cp.config.MaxConnections,
			"max_idle_time_ms":      cp.config.MaxIdleTime.Milliseconds(),
			"max_lifetime_ms":       cp.config.MaxLifetime.Milliseconds(),
			"health_check_interval": cp.config.HealthCheckInterval.String(),
		},
	}
}

// WaitForHealthy waits for the pool to become healthy
func (cp *ConnectionPool) WaitForHealthy(ctx context.Context) error {
	ticker := time.NewTicker(500 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return fmt.Errorf("context cancelled while waiting for healthy pool")
		case <-ticker.C:
			err := cp.sqlDB.PingContext(ctx)
			if err == nil {
				return nil
			}
		}
	}
}

// IsHealthy returns true if the pool is healthy
func (cp *ConnectionPool) IsHealthy() bool {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	return cp.sqlDB.PingContext(ctx) == nil
}

// Drain closes all idle connections
func (cp *ConnectionPool) Drain() error {
	// Set min connections to 0 to drain
	cp.sqlDB.SetMaxIdleConns(0)

	// Wait a bit for idle connections to close
	time.Sleep(100 * time.Millisecond)

	// Restore min connections
	cp.sqlDB.SetMaxIdleConns(cp.config.MinConnections)

	return nil
}

// Reset resets the connection pool with new config
func (cp *ConnectionPool) Reset(config PoolConfig) error {
	cp.mu.Lock()
	defer cp.mu.Unlock()

	cp.config = config
	cp.sqlDB.SetMaxIdleConns(config.MinConnections)
	cp.sqlDB.SetMaxOpenConns(config.MaxConnections)
	cp.sqlDB.SetConnMaxIdleTime(config.MaxIdleTime)
	cp.sqlDB.SetConnMaxLifetime(config.MaxLifetime)

	return nil
}

// WarmUp pre-allocates minimum connections
func (cp *ConnectionPool) WarmUp(ctx context.Context) error {
	for i := 0; i < cp.config.MinConnections; i++ {
		err := cp.sqlDB.PingContext(ctx)
		if err != nil {
			return fmt.Errorf("failed to warm up connection %d: %w", i, err)
		}
	}
	return nil
}

// GetMetrics returns detailed pool metrics
func (cp *ConnectionPool) GetMetrics() PoolMetrics {
	dbStats := cp.sqlDB.Stats()
	cp.stats.mu.RLock()
	defer cp.stats.mu.RUnlock()

	avgWaitTime := time.Duration(0)
	if dbStats.WaitCount > 0 {
		avgWaitTime = dbStats.WaitDuration / time.Duration(dbStats.WaitCount)
	}

	utilizationPercent := 0.0
	if cp.config.MaxConnections > 0 {
		utilizationPercent = float64(dbStats.InUse) / float64(cp.config.MaxConnections) * 100
	}

	return PoolMetrics{
		OpenConnections:       dbStats.OpenConnections,
		InUseConnections:      dbStats.InUse,
		IdleConnections:       dbStats.Idle,
		WaitCount:             dbStats.WaitCount,
		TotalWaitDuration:     dbStats.WaitDuration,
		AverageWaitTime:       avgWaitTime,
		MaxIdleClosedCount:    dbStats.MaxIdleClosed,
		MaxLifetimeClosedCount: dbStats.MaxLifetimeClosed,
		UtilizationPercent:    utilizationPercent,
		HealthCheckFailures:   cp.stats.HealthCheckFailures,
		IsHealthy:             cp.IsHealthy(),
		LastHealthCheckTime:   cp.stats.LastHealthCheckTime,
	}
}

// PoolMetrics represents detailed pool metrics
type PoolMetrics struct {
	OpenConnections        int
	InUseConnections       int
	IdleConnections        int
	WaitCount              int64
	TotalWaitDuration      time.Duration
	AverageWaitTime        time.Duration
	MaxIdleClosedCount     int64
	MaxLifetimeClosedCount int64
	UtilizationPercent     float64
	HealthCheckFailures    int
	IsHealthy              bool
	LastHealthCheckTime    time.Time
}
