package health

import (
	"fmt"
	"runtime"
	"sync"
	"time"

	"gorm.io/gorm"
)

// HealthStatus represents the overall health of the application
type HealthStatus struct {
	Status    string            `json:"status"` // "healthy", "degraded", "unhealthy"
	Timestamp time.Time         `json:"timestamp"`
	Version   string            `json:"version"`
	Checks    map[string]interface{} `json:"checks"`
	Duration  int64             `json:"duration_ms"`
}

// ComponentHealth represents health of a single component
type ComponentHealth struct {
	Healthy bool        `json:"healthy"`
	Details interface{} `json:"details,omitempty"`
	Error   string      `json:"error,omitempty"`
}

// SystemMetrics captures current system metrics
type SystemMetrics struct {
	MemoryUsageMB       uint64 `json:"memory_usage_mb"`
	MemoryUsagePercent  float64 `json:"memory_usage_percent"`
	GoroutineCount      int    `json:"goroutine_count"`
	CPUNumCores         int    `json:"cpu_num_cores"`
	Uptime              int64  `json:"uptime_seconds"`
}

// HealthChecker provides health check functionality
type HealthChecker struct {
	db              *gorm.DB
	version         string
	startTime       time.Time
	mu              sync.RWMutex
	lastCheckTime   time.Time
	lastCheckStatus string
}

// NewHealthChecker creates a new health checker
func NewHealthChecker(db *gorm.DB, version string) *HealthChecker {
	return &HealthChecker{
		db:        db,
		version:   version,
		startTime: time.Now(),
	}
}

// Check performs a complete health check
func (hc *HealthChecker) Check() HealthStatus {
	start := time.Now()
	status := HealthStatus{
		Timestamp: start,
		Version:   hc.version,
		Checks:    make(map[string]interface{}),
	}

	// Check database
	dbCheck := hc.checkDatabase()
	status.Checks["database"] = dbCheck

	// Check memory
	memCheck := hc.checkMemory()
	status.Checks["memory"] = memCheck

	// Check goroutines
	goroutineCount := runtime.NumGoroutine()
	status.Checks["goroutines"] = map[string]interface{}{
		"count":    goroutineCount,
		"healthy": goroutineCount < 10000, // Alert if > 10k goroutines
	}

	// Check uptime
	uptime := time.Since(hc.startTime).Seconds()
	status.Checks["uptime_seconds"] = int64(uptime)

	// Determine overall status
	allHealthy := true
	if dbHealth, ok := dbCheck.(map[string]interface{}); ok {
		if !dbHealth["healthy"].(bool) {
			allHealthy = false
		}
	}

	if memHealth, ok := memCheck.(map[string]interface{}); ok {
		if !memHealth["healthy"].(bool) {
			allHealthy = false
		}
	}

	if goroutineCount >= 10000 {
		allHealthy = false
	}

	if allHealthy {
		status.Status = "healthy"
	} else {
		status.Status = "degraded"
	}

	status.Duration = time.Since(start).Milliseconds()

	hc.mu.Lock()
	hc.lastCheckTime = start
	hc.lastCheckStatus = status.Status
	hc.mu.Unlock()

	return status
}

// checkDatabase verifies database connectivity and latency
func (hc *HealthChecker) checkDatabase() interface{} {
	if hc.db == nil {
		return ComponentHealth{
			Healthy: false,
			Error:   "database not initialized",
		}
	}

	start := time.Now()

	// Ping database
	sqlDB, err := hc.db.DB()
	if err != nil {
		return ComponentHealth{
			Healthy: false,
			Error:   fmt.Sprintf("failed to get database connection: %v", err),
		}
	}

	if err := sqlDB.Ping(); err != nil {
		return ComponentHealth{
			Healthy: false,
			Error:   fmt.Sprintf("database ping failed: %v", err),
		}
	}

	latency := time.Since(start).Milliseconds()

	return map[string]interface{}{
		"healthy":       true,
		"latency_ms":    latency,
		"connection":    "connected",
		"latency_ok":    latency < 100, // Alert if latency > 100ms
	}
}

// checkMemory checks memory usage
func (hc *HealthChecker) checkMemory() interface{} {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	// Memory in MB
	memoryMB := m.Alloc / 1024 / 1024
	memoryPercent := float64(m.Alloc) / float64(m.TotalAlloc) * 100

	// Alert thresholds
	healthy := memoryMB < 500 // Less than 500MB

	return map[string]interface{}{
		"healthy":            healthy,
		"allocated_mb":       memoryMB,
		"allocated_percent":  memoryPercent,
		"total_alloc_mb":     m.TotalAlloc / 1024 / 1024,
		"sys_mb":             m.Sys / 1024 / 1024,
		"num_gc":             m.NumGC,
		"memory_ok":          memoryMB < 500,
	}
}

// IsHealthy returns true if system is healthy
func (hc *HealthChecker) IsHealthy() bool {
	hc.mu.RLock()
	status := hc.lastCheckStatus
	hc.mu.RUnlock()

	return status == "healthy"
}

// IsReady returns true if system is ready to serve traffic
func (hc *HealthChecker) IsReady() bool {
	if hc.db == nil {
		return false
	}

	sqlDB, err := hc.db.DB()
	if err != nil {
		return false
	}

	if err := sqlDB.Ping(); err != nil {
		return false
	}

	return true
}

// IsAlive returns true if system is running
func (hc *HealthChecker) IsAlive() bool {
	return true
}

// GetMetrics returns current system metrics
func (hc *HealthChecker) GetMetrics() SystemMetrics {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	return SystemMetrics{
		MemoryUsageMB:      m.Alloc / 1024 / 1024,
		MemoryUsagePercent: float64(m.Alloc) / float64(m.TotalAlloc) * 100,
		GoroutineCount:     runtime.NumGoroutine(),
		CPUNumCores:        runtime.NumCPU(),
		Uptime:             int64(time.Since(hc.startTime).Seconds()),
	}
}
