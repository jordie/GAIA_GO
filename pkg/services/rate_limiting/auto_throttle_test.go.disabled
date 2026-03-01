package rate_limiting

import (
	"context"
	"testing"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupThrottleTestDB creates test database for throttle tests
func setupThrottleTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to create test DB: %v", err)
	}

	db.AutoMigrate(&ThrottleEvent{})
	return db
}

// TestDefaultConfig tests default throttle configuration
func TestDefaultConfig(t *testing.T) {
	config := DefaultThrottleConfig()

	if !config.Enabled {
		t.Errorf("Auto-throttle should be enabled by default")
	}

	if config.CriticalCPUThreshold != 95.0 {
		t.Errorf("Expected critical CPU threshold 95.0, got %.1f", config.CriticalCPUThreshold)
	}

	if config.CriticalThrottleMultiplier != 0.2 {
		t.Errorf("Expected critical multiplier 0.2, got %.2f", config.CriticalThrottleMultiplier)
	}
}

// TestThrottleNone tests no throttle condition
func TestThrottleNone(t *testing.T) {
	db := setupThrottleTestDB(t)
	config := DefaultThrottleConfig()
	at := NewAutoThrottler(db, config)
	defer at.Close()

	metrics := &SystemMetrics{
		CPUPercent:     25.0,
		MemoryPercent:  30.0,
		GoroutineCount: 100,
		TimestampAt:    time.Now(),
	}

	level := at.determineThrottleLevel(metrics)
	if level != ThrottleNone {
		t.Errorf("Expected ThrottleNone, got %s", level)
	}
}

// TestThrottleLow tests low throttle condition
func TestThrottleLow(t *testing.T) {
	db := setupThrottleTestDB(t)
	config := DefaultThrottleConfig()
	at := NewAutoThrottler(db, config)
	defer at.Close()

	metrics := &SystemMetrics{
		CPUPercent:     55.0, // Above low threshold (50)
		MemoryPercent:  30.0,
		GoroutineCount: 100,
		TimestampAt:    time.Now(),
	}

	level := at.determineThrottleLevel(metrics)
	if level != ThrottleLow {
		t.Errorf("Expected ThrottleLow, got %s", level)
	}

	multiplier := at.getThrottleMultiplier(level)
	if multiplier != config.LowThrottleMultiplier {
		t.Errorf("Expected multiplier %.2f, got %.2f", config.LowThrottleMultiplier, multiplier)
	}
}

// TestThrottleMedium tests medium throttle condition
func TestThrottleMedium(t *testing.T) {
	db := setupThrottleTestDB(t)
	config := DefaultThrottleConfig()
	at := NewAutoThrottler(db, config)
	defer at.Close()

	metrics := &SystemMetrics{
		CPUPercent:     75.0, // Above medium threshold (70)
		MemoryPercent:  50.0,
		GoroutineCount: 100,
		TimestampAt:    time.Now(),
	}

	level := at.determineThrottleLevel(metrics)
	if level != ThrottleMedium {
		t.Errorf("Expected ThrottleMedium, got %s", level)
	}

	multiplier := at.getThrottleMultiplier(level)
	if multiplier != config.MediumThrottleMultiplier {
		t.Errorf("Expected multiplier %.2f, got %.2f", config.MediumThrottleMultiplier, multiplier)
	}
}

// TestThrottleHigh tests high throttle condition
func TestThrottleHigh(t *testing.T) {
	db := setupThrottleTestDB(t)
	config := DefaultThrottleConfig()
	at := NewAutoThrottler(db, config)
	defer at.Close()

	metrics := &SystemMetrics{
		CPUPercent:     88.0, // Above high threshold (85)
		MemoryPercent:  70.0,
		GoroutineCount: 100,
		TimestampAt:    time.Now(),
	}

	level := at.determineThrottleLevel(metrics)
	if level != ThrottleHigh {
		t.Errorf("Expected ThrottleHigh, got %s", level)
	}

	multiplier := at.getThrottleMultiplier(level)
	if multiplier != config.HighThrottleMultiplier {
		t.Errorf("Expected multiplier %.2f, got %.2f", config.HighThrottleMultiplier, multiplier)
	}
}

// TestThrottleCritical tests critical throttle condition
func TestThrottleCritical(t *testing.T) {
	db := setupThrottleTestDB(t)
	config := DefaultThrottleConfig()
	at := NewAutoThrottler(db, config)
	defer at.Close()

	metrics := &SystemMetrics{
		CPUPercent:     98.0, // Above critical threshold (95)
		MemoryPercent:  90.0,
		GoroutineCount: 100,
		TimestampAt:    time.Now(),
	}

	level := at.determineThrottleLevel(metrics)
	if level != ThrottleCritical {
		t.Errorf("Expected ThrottleCritical, got %s", level)
	}

	multiplier := at.getThrottleMultiplier(level)
	if multiplier != config.CriticalThrottleMultiplier {
		t.Errorf("Expected multiplier %.2f, got %.2f", config.CriticalThrottleMultiplier, multiplier)
	}
}

// TestGoroutineThrottling tests goroutine-based throttling
func TestGoroutineThrottling(t *testing.T) {
	db := setupThrottleTestDB(t)
	config := DefaultThrottleConfig()
	at := NewAutoThrottler(db, config)
	defer at.Close()

	metrics := &SystemMetrics{
		CPUPercent:     10.0,
		MemoryPercent:  10.0,
		GoroutineCount: 15000, // Above high threshold (10000)
		TimestampAt:    time.Now(),
	}

	level := at.determineThrottleLevel(metrics)
	if level != ThrottleHigh {
		t.Errorf("Expected ThrottleHigh due to goroutines, got %s", level)
	}
}

// TestMemoryThrottling tests memory-based throttling
func TestMemoryThrottling(t *testing.T) {
	db := setupThrottleTestDB(t)
	config := DefaultThrottleConfig()
	at := NewAutoThrottler(db, config)
	defer at.Close()

	metrics := &SystemMetrics{
		CPUPercent:     10.0,
		MemoryPercent:  88.0, // Above high threshold (85)
		GoroutineCount: 100,
		TimestampAt:    time.Now(),
	}

	level := at.determineThrottleLevel(metrics)
	if level != ThrottleHigh {
		t.Errorf("Expected ThrottleHigh due to memory, got %s", level)
	}
}

// TestThrottleTransition tests throttle level transitions
func TestThrottleTransition(t *testing.T) {
	db := setupThrottleTestDB(t)
	config := DefaultThrottleConfig()
	at := NewAutoThrottler(db, config)
	defer at.Close()

	// Start with no throttle
	if at.GetCurrentLevel() != ThrottleNone {
		t.Errorf("Expected initial level ThrottleNone")
	}

	metrics := &SystemMetrics{
		CPUPercent:     75.0,
		MemoryPercent:  50.0,
		GoroutineCount: 100,
		TimestampAt:    time.Now(),
	}

	// Simulate transition
	at.transitionThrottle(ThrottleNone, ThrottleMedium, metrics)

	if at.GetCurrentLevel() != ThrottleMedium {
		t.Errorf("Expected level ThrottleMedium after transition")
	}
}

// TestManualThrottle tests manual throttle override
func TestManualThrottle(t *testing.T) {
	db := setupThrottleTestDB(t)
	config := DefaultThrottleConfig()
	at := NewAutoThrottler(db, config)
	defer at.Close()

	ctx := context.Background()
	err := at.ManuallySetThrottle(ctx, ThrottleHigh, "Emergency maintenance")
	if err != nil {
		t.Fatalf("Failed to set manual throttle: %v", err)
	}

	if at.GetCurrentLevel() != ThrottleHigh {
		t.Errorf("Expected ThrottleHigh after manual override")
	}

	// Check event was recorded
	events, err := at.GetThrottleHistory(ctx, 10)
	if err != nil {
		t.Fatalf("Failed to get history: %v", err)
	}

	if len(events) == 0 {
		t.Errorf("Expected throttle event to be recorded")
	}

	if !contains(events[0].Reason, "Emergency maintenance") {
		t.Errorf("Expected reason to contain override message")
	}
}

// TestGetThrottleMultiplier tests multiplier retrieval
func TestGetThrottleMultiplier(t *testing.T) {
	db := setupThrottleTestDB(t)
	config := DefaultThrottleConfig()

	tests := []struct {
		level    ThrottleLevel
		expected float64
	}{
		{ThrottleNone, 1.0},
		{ThrottleLow, config.LowThrottleMultiplier},
		{ThrottleMedium, config.MediumThrottleMultiplier},
		{ThrottleHigh, config.HighThrottleMultiplier},
		{ThrottleCritical, config.CriticalThrottleMultiplier},
	}

	at := NewAutoThrottler(db, config)
	defer at.Close()

	for _, test := range tests {
		multiplier := at.getThrottleMultiplier(test.level)
		if multiplier != test.expected {
			t.Errorf("Level %s: expected %.2f, got %.2f", test.level, test.expected, multiplier)
		}
	}
}

// TestThrottleStats tests statistics calculation
func TestThrottleStats(t *testing.T) {
	db := setupThrottleTestDB(t)
	config := DefaultThrottleConfig()
	at := NewAutoThrottler(db, config)
	defer at.Close()

	ctx := context.Background()

	// Create some events
	metrics := &SystemMetrics{
		CPUPercent:     75.0,
		MemoryPercent:  50.0,
		GoroutineCount: 100,
		TimestampAt:    time.Now(),
	}

	at.transitionThrottle(ThrottleNone, ThrottleMedium, metrics)
	time.Sleep(10 * time.Millisecond)
	at.transitionThrottle(ThrottleMedium, ThrottleNone, metrics)

	stats, err := at.GetThrottleStats(ctx, 24)
	if err != nil {
		t.Fatalf("Failed to get stats: %v", err)
	}

	if stats["current_level"].(ThrottleLevel) != ThrottleNone {
		t.Errorf("Expected current level ThrottleNone")
	}

	if stats["total_events"].(int) < 2 {
		t.Errorf("Expected at least 2 events recorded")
	}
}

// Helper function
func contains(s, substr string) bool {
	for i := 0; i < len(s)-len(substr)+1; i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

// BenchmarkThrottleLevel benchmarks throttle level determination
func BenchmarkThrottleLevel(b *testing.B) {
	db := setupThrottleTestDB(&testing.T{})
	config := DefaultThrottleConfig()
	at := NewAutoThrottler(db, config)
	defer at.Close()

	metrics := &SystemMetrics{
		CPUPercent:     75.0,
		MemoryPercent:  50.0,
		GoroutineCount: 5000,
		TimestampAt:    time.Now(),
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		at.determineThrottleLevel(metrics)
	}
}

// BenchmarkGetMultiplier benchmarks multiplier retrieval
func BenchmarkGetMultiplier(b *testing.B) {
	db := setupThrottleTestDB(&testing.T{})
	at := NewAutoThrottler(db, DefaultThrottleConfig())
	defer at.Close()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		at.GetThrottleMultiplier()
	}
}
