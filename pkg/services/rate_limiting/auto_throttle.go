package rate_limiting

import (
	"context"
	"fmt"
	"runtime"
	"sync"
	"time"

	"gorm.io/gorm"
)

// ThrottleLevel defines the level of throttling applied
type ThrottleLevel string

const (
	ThrottleNone     ThrottleLevel = "none"
	ThrottleLow      ThrottleLevel = "low"
	ThrottleMedium   ThrottleLevel = "medium"
	ThrottleHigh     ThrottleLevel = "high"
	ThrottleCritical ThrottleLevel = "critical"
)

// SystemMetrics represents current system resource usage
type SystemMetrics struct {
	CPUPercent       float64       `json:"cpu_percent"`
	MemoryPercent    float64       `json:"memory_percent"`
	MemoryMB         float64       `json:"memory_mb"`
	GoroutineCount   int           `json:"goroutine_count"`
	AllocationMB     float64       `json:"allocation_mb"`
	SystemMB         float64       `json:"system_mb"`
	GCRuns           uint32        `json:"gc_runs"`
	LastGCTime       time.Time     `json:"last_gc_time"`
	TimestampAt      time.Time     `json:"timestamp"`
}

// ThrottleConfig defines throttling configuration
type ThrottleConfig struct {
	// Enable auto-throttling
	Enabled bool

	// CPU thresholds (%)
	LowCPUThreshold      float64
	MediumCPUThreshold   float64
	HighCPUThreshold     float64
	CriticalCPUThreshold float64

	// Memory thresholds (%)
	LowMemThreshold      float64
	MediumMemThreshold   float64
	HighMemThreshold     float64
	CriticalMemThreshold float64

	// Goroutine thresholds
	LowGoroutineThreshold      int
	MediumGoroutineThreshold   int
	HighGoroutineThreshold     int
	CriticalGoroutineThreshold int

	// Throttle multipliers (applied to rate limits)
	LowThrottleMultiplier      float64
	MediumThrottleMultiplier   float64
	HighThrottleMultiplier     float64
	CriticalThrottleMultiplier float64

	// Sampling interval
	SamplingInterval time.Duration

	// Cooldown before recovery
	RecoveryCooldown time.Duration
}

// DefaultThrottleConfig returns sensible defaults
func DefaultThrottleConfig() ThrottleConfig {
	return ThrottleConfig{
		Enabled: true,

		// CPU thresholds
		LowCPUThreshold:      50.0,
		MediumCPUThreshold:   70.0,
		HighCPUThreshold:     85.0,
		CriticalCPUThreshold: 95.0,

		// Memory thresholds
		LowMemThreshold:      60.0,
		MediumMemThreshold:   75.0,
		HighMemThreshold:     85.0,
		CriticalMemThreshold: 95.0,

		// Goroutine thresholds
		LowGoroutineThreshold:      1000,
		MediumGoroutineThreshold:   5000,
		HighGoroutineThreshold:     10000,
		CriticalGoroutineThreshold: 50000,

		// Throttle multipliers (0.5 = 50% of normal limit)
		LowThrottleMultiplier:      0.8,  // 80% of normal
		MediumThrottleMultiplier:   0.6,  // 60% of normal
		HighThrottleMultiplier:     0.4,  // 40% of normal
		CriticalThrottleMultiplier: 0.2,  // 20% of normal

		SamplingInterval: 10 * time.Second,
		RecoveryCooldown: 30 * time.Second,
	}
}

// AutoThrottler manages system load-based rate limiting
type AutoThrottler struct {
	db                  *gorm.DB
	config              ThrottleConfig
	mu                  sync.RWMutex
	currentLevel        ThrottleLevel
	lastLevelChange     time.Time
	metrics             *SystemMetrics
	throttleHistory     []ThrottleEvent
	active              bool
	stopChan            chan struct{}
}

// ThrottleEvent tracks throttling changes
type ThrottleEvent struct {
	ID           int           `json:"id" gorm:"primaryKey"`
	Level        ThrottleLevel `json:"level" gorm:"index"`
	CPUPercent   float64       `json:"cpu_percent"`
	MemPercent   float64       `json:"mem_percent"`
	Goroutines   int           `json:"goroutines"`
	Multiplier   float64       `json:"multiplier"`
	Reason       string        `json:"reason"`
	Duration     time.Duration `json:"duration"`
	CreatedAt    time.Time     `json:"created_at" gorm:"index"`
	ResolvedAt   *time.Time    `json:"resolved_at"`
}

// NewAutoThrottler creates a new auto-throttler
func NewAutoThrottler(db *gorm.DB, config ThrottleConfig) *AutoThrottler {
	at := &AutoThrottler{
		db:              db,
		config:          config,
		currentLevel:    ThrottleNone,
		lastLevelChange: time.Now(),
		stopChan:        make(chan struct{}),
		throttleHistory: make([]ThrottleEvent, 0),
	}

	if config.Enabled {
		go at.startMonitoring()
	}

	return at
}

// startMonitoring starts the background monitoring loop
func (at *AutoThrottler) startMonitoring() {
	at.mu.Lock()
	at.active = true
	at.mu.Unlock()

	ticker := time.NewTicker(at.config.SamplingInterval)
	defer ticker.Stop()

	for {
		select {
		case <-at.stopChan:
			return
		case <-ticker.C:
			at.checkAndUpdateThrottle()
		}
	}
}

// checkAndUpdateThrottle checks system load and updates throttle level
func (at *AutoThrottler) checkAndUpdateThrottle() {
	metrics := at.getSystemMetrics()
	at.mu.Lock()
	at.metrics = metrics
	at.mu.Unlock()

	newLevel := at.determineThrottleLevel(metrics)

	at.mu.Lock()
	oldLevel := at.currentLevel
	at.mu.Unlock()

	if newLevel != oldLevel {
		at.transitionThrottle(oldLevel, newLevel, metrics)
	}
}

// getSystemMetrics collects current system metrics
func (at *AutoThrottler) getSystemMetrics() *SystemMetrics {
	m := runtime.MemStats{}
	runtime.ReadMemStats(&m)

	// CPU percentage (simplified - would need actual sampling)
	// This is a placeholder that could be enhanced with psutil
	cpuPercent := 0.0

	memPercent := (float64(m.Alloc) / float64(m.Sys)) * 100

	return &SystemMetrics{
		CPUPercent:       cpuPercent,
		MemoryPercent:    memPercent,
		MemoryMB:         float64(m.Alloc) / (1024 * 1024),
		GoroutineCount:   runtime.NumGoroutine(),
		AllocationMB:     float64(m.Alloc) / (1024 * 1024),
		SystemMB:         float64(m.Sys) / (1024 * 1024),
		GCRuns:           m.NumGC,
		LastGCTime:       time.Unix(0, int64(m.LastGC)),
		TimestampAt:      time.Now(),
	}
}

// determineThrottleLevel determines appropriate throttle level
func (at *AutoThrottler) determineThrottleLevel(metrics *SystemMetrics) ThrottleLevel {
	// Check critical level first
	if metrics.CPUPercent >= at.config.CriticalCPUThreshold ||
		metrics.MemoryPercent >= at.config.CriticalMemThreshold ||
		metrics.GoroutineCount >= at.config.CriticalGoroutineThreshold {
		return ThrottleCritical
	}

	// Check high level
	if metrics.CPUPercent >= at.config.HighCPUThreshold ||
		metrics.MemoryPercent >= at.config.HighMemThreshold ||
		metrics.GoroutineCount >= at.config.HighGoroutineThreshold {
		return ThrottleHigh
	}

	// Check medium level
	if metrics.CPUPercent >= at.config.MediumCPUThreshold ||
		metrics.MemoryPercent >= at.config.MediumMemThreshold ||
		metrics.GoroutineCount >= at.config.MediumGoroutineThreshold {
		return ThrottleMedium
	}

	// Check low level
	if metrics.CPUPercent >= at.config.LowCPUThreshold ||
		metrics.MemoryPercent >= at.config.LowMemThreshold ||
		metrics.GoroutineCount >= at.config.LowGoroutineThreshold {
		return ThrottleLow
	}

	return ThrottleNone
}

// transitionThrottle handles throttle level transitions
func (at *AutoThrottler) transitionThrottle(oldLevel, newLevel ThrottleLevel, metrics *SystemMetrics) {
	reason := at.getThrottleReason(oldLevel, newLevel, metrics)

	event := ThrottleEvent{
		Level:      newLevel,
		CPUPercent: metrics.CPUPercent,
		MemPercent: metrics.MemoryPercent,
		Goroutines: metrics.GoroutineCount,
		Multiplier: at.getThrottleMultiplier(newLevel),
		Reason:     reason,
		CreatedAt:  time.Now(),
	}

	// Save event
	at.db.Table("throttle_events").Create(&event)

	at.mu.Lock()
	at.currentLevel = newLevel
	at.lastLevelChange = time.Now()
	at.mu.Unlock()

	// Log the transition
	fmt.Printf("[THROTTLE] Level: %s → %s | CPU: %.1f%% | Mem: %.1f%% | Goroutines: %d | Multiplier: %.2f\n",
		oldLevel, newLevel, metrics.CPUPercent, metrics.MemoryPercent,
		metrics.GoroutineCount, event.Multiplier)
}

// getThrottleReason returns human-readable reason for throttle transition
func (at *AutoThrottler) getThrottleReason(oldLevel, newLevel ThrottleLevel, metrics *SystemMetrics) string {
	var reasons []string

	if metrics.CPUPercent >= at.config.CriticalCPUThreshold {
		reasons = append(reasons, fmt.Sprintf("CPU critical (%.1f%%)", metrics.CPUPercent))
	} else if metrics.CPUPercent >= at.config.HighCPUThreshold {
		reasons = append(reasons, fmt.Sprintf("CPU high (%.1f%%)", metrics.CPUPercent))
	}

	if metrics.MemoryPercent >= at.config.CriticalMemThreshold {
		reasons = append(reasons, fmt.Sprintf("Memory critical (%.1f%%)", metrics.MemoryPercent))
	} else if metrics.MemoryPercent >= at.config.HighMemThreshold {
		reasons = append(reasons, fmt.Sprintf("Memory high (%.1f%%)", metrics.MemoryPercent))
	}

	if metrics.GoroutineCount >= at.config.CriticalGoroutineThreshold {
		reasons = append(reasons, fmt.Sprintf("Goroutines critical (%d)", metrics.GoroutineCount))
	} else if metrics.GoroutineCount >= at.config.HighGoroutineThreshold {
		reasons = append(reasons, fmt.Sprintf("Goroutines high (%d)", metrics.GoroutineCount))
	}

	if len(reasons) == 0 {
		reasons = append(reasons, "System load normalized")
	}

	result := ""
	for i, r := range reasons {
		if i > 0 {
			result += " | "
		}
		result += r
	}

	return result
}

// GetThrottleMultiplier returns the multiplier for current throttle level
func (at *AutoThrottler) GetThrottleMultiplier() float64 {
	at.mu.RLock()
	level := at.currentLevel
	at.mu.RUnlock()

	return at.getThrottleMultiplier(level)
}

// getThrottleMultiplier returns multiplier for a specific level
func (at *AutoThrottler) getThrottleMultiplier(level ThrottleLevel) float64 {
	switch level {
	case ThrottleNone:
		return 1.0
	case ThrottleLow:
		return at.config.LowThrottleMultiplier
	case ThrottleMedium:
		return at.config.MediumThrottleMultiplier
	case ThrottleHigh:
		return at.config.HighThrottleMultiplier
	case ThrottleCritical:
		return at.config.CriticalThrottleMultiplier
	default:
		return 1.0
	}
}

// GetCurrentLevel returns the current throttle level
func (at *AutoThrottler) GetCurrentLevel() ThrottleLevel {
	at.mu.RLock()
	defer at.mu.RUnlock()
	return at.currentLevel
}

// GetSystemMetrics returns current system metrics
func (at *AutoThrottler) GetSystemMetrics() *SystemMetrics {
	at.mu.RLock()
	defer at.mu.RUnlock()
	return at.metrics
}

// GetThrottleStats returns throttle statistics
func (at *AutoThrottler) GetThrottleStats(ctx context.Context, hours int) (map[string]interface{}, error) {
	cutoff := time.Now().AddDate(0, 0, -1*hours/24)

	var events []ThrottleEvent
	at.db.WithContext(ctx).
		Where("created_at > ?", cutoff).
		Order("created_at DESC").
		Find(&events)

	// Calculate statistics
	levelCounts := make(map[ThrottleLevel]int)
	totalDuration := time.Duration(0)
	var lastEvent *ThrottleEvent

	for i, event := range events {
		levelCounts[event.Level]++

		if i > 0 && lastEvent != nil {
			duration := lastEvent.CreatedAt.Sub(event.CreatedAt)
			totalDuration += duration
		}

		lastEvent = &event
	}

	return map[string]interface{}{
		"current_level":     at.GetCurrentLevel(),
		"total_events":      len(events),
		"level_distribution": levelCounts,
		"average_duration":  totalDuration / time.Duration(len(events)+1),
		"last_change":       at.lastLevelChange,
		"hours_reviewed":    hours,
	}, nil
}

// GetThrottleHistory returns throttle event history
func (at *AutoThrottler) GetThrottleHistory(ctx context.Context, limit int) ([]ThrottleEvent, error) {
	var events []ThrottleEvent
	err := at.db.WithContext(ctx).
		Order("created_at DESC").
		Limit(limit).
		Find(&events).Error
	return events, err
}

// ManuallySetThrottle allows manual throttle override (admin)
func (at *AutoThrottler) ManuallySetThrottle(ctx context.Context, level ThrottleLevel, reason string) error {
	at.mu.Lock()
	oldLevel := at.currentLevel
	at.currentLevel = level
	at.lastLevelChange = time.Now()
	at.mu.Unlock()

	metrics := at.GetSystemMetrics()
	if metrics == nil {
		metrics = &SystemMetrics{TimestampAt: time.Now()}
	}

	event := ThrottleEvent{
		Level:      level,
		CPUPercent: metrics.CPUPercent,
		MemPercent: metrics.MemoryPercent,
		Goroutines: metrics.GoroutineCount,
		Multiplier: at.getThrottleMultiplier(level),
		Reason:     fmt.Sprintf("Manual override (was %s): %s", oldLevel, reason),
		CreatedAt:  time.Now(),
	}

	return at.db.WithContext(ctx).Table("throttle_events").Create(&event).Error
}

// Close stops the auto-throttler
func (at *AutoThrottler) Close() error {
	at.mu.Lock()
	defer at.mu.Unlock()

	if at.active {
		close(at.stopChan)
		at.active = false
	}

	return nil
}
