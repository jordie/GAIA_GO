package monitoring

import (
	"context"
	"database/sql"
	"fmt"
	"sync"
	"time"
)

// HealthStatus represents the health status of a component
type HealthStatus string

const (
	HealthStatusHealthy   HealthStatus = "healthy"
	HealthStatusDegraded  HealthStatus = "degraded"
	HealthStatusUnhealthy HealthStatus = "unhealthy"
)

// ComponentHealth represents the health of a single component
type ComponentHealth struct {
	Name        string        `json:"name"`
	Status      HealthStatus  `json:"status"`
	Message     string        `json:"message"`
	LastCheck   time.Time     `json:"last_check"`
	ResponseMs  int64         `json:"response_ms"`
}

// ClusterHealth represents the overall health of the cluster
type ClusterHealth struct {
	Status      HealthStatus      `json:"status"`
	Timestamp   time.Time         `json:"timestamp"`
	NodeID      string            `json:"node_id"`
	IsLeader    bool              `json:"is_leader"`
	Components  []ComponentHealth `json:"components"`
	Uptime      int64             `json:"uptime_seconds"`
	Version     string            `json:"version"`
	Metrics     map[string]interface{} `json:"metrics"`
}

// HealthChecker provides health check capabilities
type HealthChecker struct {
	mu              sync.RWMutex
	db              *sql.DB
	nodeID          string
	version         string
	startTime       time.Time
	lastCheckTime   time.Time
	cachedHealth    *ClusterHealth
	cacheDuration   time.Duration
}

// NewHealthChecker creates a new health checker
func NewHealthChecker(db *sql.DB, nodeID, version string) *HealthChecker {
	return &HealthChecker{
		db:            db,
		nodeID:        nodeID,
		version:       version,
		startTime:     time.Now(),
		cacheDuration: 5 * time.Second,
	}
}

// Check performs a comprehensive health check
func (hc *HealthChecker) Check(ctx context.Context, isLeader bool) *ClusterHealth {
	hc.mu.Lock()
	defer hc.mu.Unlock()

	// Return cached result if still fresh
	if hc.cachedHealth != nil && time.Since(hc.lastCheckTime) < hc.cacheDuration {
		return hc.cachedHealth
	}

	health := &ClusterHealth{
		Timestamp:  time.Now(),
		NodeID:     hc.nodeID,
		IsLeader:   isLeader,
		Components: make([]ComponentHealth, 0),
		Uptime:     int64(time.Since(hc.startTime).Seconds()),
		Version:    hc.version,
		Metrics:    make(map[string]interface{}),
	}

	// Check database
	dbHealth := hc.checkDatabase(ctx)
	health.Components = append(health.Components, dbHealth)

	// Determine overall status based on components
	health.Status = HealthStatusHealthy
	for _, comp := range health.Components {
		if comp.Status == HealthStatusUnhealthy {
			health.Status = HealthStatusUnhealthy
		} else if comp.Status == HealthStatusDegraded && health.Status != HealthStatusUnhealthy {
			health.Status = HealthStatusDegraded
		}
	}

	// Cache the result
	hc.cachedHealth = health
	hc.lastCheckTime = time.Now()

	return health
}

// checkDatabase performs a health check on the database
func (hc *HealthChecker) checkDatabase(ctx context.Context) ComponentHealth {
	start := time.Now()
	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	health := ComponentHealth{
		Name:      "database",
		Status:    HealthStatusHealthy,
		LastCheck: time.Now(),
	}

	// Ping database
	if err := hc.db.PingContext(ctx); err != nil {
		health.Status = HealthStatusUnhealthy
		health.Message = fmt.Sprintf("ping failed: %v", err)
		health.ResponseMs = time.Since(start).Milliseconds()
		return health
	}

	// Check connection pool
	sqlDB := hc.db.Stats()
	health.Metrics = map[string]interface{}{
		"open_connections": sqlDB.OpenConnections,
		"in_use":           sqlDB.InUse,
		"idle":             sqlDB.Idle,
	}

	// Check if connection pool is saturated
	if sqlDB.InUse > int32(float64(sqlDB.OpenConnections)*0.9) {
		health.Status = HealthStatusDegraded
		health.Message = fmt.Sprintf("connection pool near capacity: %d/%d", sqlDB.InUse, sqlDB.OpenConnections)
	}

	// Query a simple table to ensure queries work
	var timestamp time.Time
	err := hc.db.QueryRowContext(ctx, "SELECT CURRENT_TIMESTAMP").Scan(&timestamp)
	if err != nil {
		health.Status = HealthStatusUnhealthy
		health.Message = fmt.Sprintf("query test failed: %v", err)
		health.ResponseMs = time.Since(start).Milliseconds()
		return health
	}

	health.Message = "database healthy"
	health.ResponseMs = time.Since(start).Milliseconds()

	// Warn if response time is high
	if health.ResponseMs > 100 {
		health.Status = HealthStatusDegraded
		health.Message = fmt.Sprintf("database response slow: %dms", health.ResponseMs)
	}

	return health
}

// CheckReadiness performs a quick readiness check (for container orchestration)
func (hc *HealthChecker) CheckReadiness(ctx context.Context) bool {
	ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()

	// Simple database ping
	if err := hc.db.PingContext(ctx); err != nil {
		return false
	}

	return true
}

// CheckLiveness performs a basic liveness check (service is running)
func (hc *HealthChecker) CheckLiveness(ctx context.Context) bool {
	// Very quick check - just verify we can take a lock
	// In a real implementation, check that goroutines haven't all panicked
	hc.mu.RLock()
	defer hc.mu.RUnlock()
	return true
}

// GetMetrics returns current system metrics
func (hc *HealthChecker) GetMetrics() map[string]interface{} {
	if hc.db == nil {
		return nil
	}

	stats := hc.db.Stats()
	return map[string]interface{}{
		"database_connections": map[string]interface{}{
			"open": stats.OpenConnections,
			"in_use": stats.InUse,
			"idle": stats.Idle,
			"wait_count": stats.WaitCount,
			"wait_duration_ms": stats.WaitDuration.Milliseconds(),
			"max_idle_closed": stats.MaxIdleClosed,
			"max_lifetime_closed": stats.MaxLifetimeClosed,
		},
	}
}

// Ready checks if the service is ready to receive traffic
func (hc *HealthChecker) Ready(ctx context.Context) bool {
	return hc.CheckReadiness(ctx)
}

// Live checks if the service is still running
func (hc *HealthChecker) Live(ctx context.Context) bool {
	return hc.CheckLiveness(ctx)
}
