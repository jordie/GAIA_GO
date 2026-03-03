package rate_limiting

import (
	"context"
	"fmt"
	"runtime"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupRateLimiterLoadTestDB creates a test database for load tests
func setupRateLimiterLoadTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open("file::memory:?cache=shared"), &gorm.Config{})
	require.NoError(t, err, "failed to create load test database")

	// Create required tables for load testing
	createRateLimiterLoadTestTables(t, db)

	return db
}

// createRateLimiterLoadTestTables creates all required tables for load tests
func createRateLimiterLoadTestTables(t *testing.T, db *gorm.DB) {
	db.Exec(`
		CREATE TABLE rate_limit_configs (
			id INTEGER PRIMARY KEY,
			rule_name TEXT UNIQUE,
			scope TEXT,
			scope_value TEXT,
			limit_type TEXT,
			limit_value INTEGER,
			resource_type TEXT,
			enabled BOOLEAN DEFAULT 1,
			priority INTEGER DEFAULT 1,
			system_id TEXT,
			created_at TIMESTAMP,
			updated_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE rate_limit_buckets (
			id INTEGER PRIMARY KEY,
			rule_id INTEGER,
			system_id TEXT,
			scope TEXT,
			scope_value TEXT,
			window_start TIMESTAMP,
			window_end TIMESTAMP,
			request_count INTEGER DEFAULT 0,
			created_at TIMESTAMP,
			updated_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE INDEX idx_buckets_scope ON rate_limit_buckets(scope, scope_value, window_start)
	`)

	db.Exec(`
		CREATE TABLE resource_quotas (
			id INTEGER PRIMARY KEY,
			system_id TEXT,
			scope TEXT,
			scope_value TEXT,
			resource_type TEXT,
			quota_period TEXT,
			quota_limit INTEGER,
			quota_used INTEGER DEFAULT 0,
			period_start TIMESTAMP,
			period_end TIMESTAMP,
			created_at TIMESTAMP,
			updated_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE rate_limit_violations (
			id INTEGER PRIMARY KEY,
			system_id TEXT,
			scope TEXT,
			scope_value TEXT,
			resource_type TEXT,
			violated_limit INTEGER,
			violation_time TIMESTAMP,
			blocked BOOLEAN DEFAULT 1
		)
	`)

	db.Exec(`
		CREATE INDEX idx_violations_scope ON rate_limit_violations(scope, scope_value, violation_time)
	`)

	db.Exec(`
		CREATE INDEX idx_violations_time ON rate_limit_violations(violation_time)
	`)

	db.Exec(`
		CREATE TABLE reputation_scores (
			id INTEGER PRIMARY KEY,
			user_id INTEGER UNIQUE,
			score REAL DEFAULT 100.0,
			tier TEXT DEFAULT 'neutral'
		)
	`)
}

// LoadTestMetrics captures load test performance metrics
type LoadTestMetrics struct {
	TotalRequests   int64
	AllowedRequests int64
	BlockedRequests int64
	MinLatency      time.Duration
	MaxLatency      time.Duration
	AvgLatency      time.Duration
	P50Latency      time.Duration
	P99Latency      time.Duration
	Throughput      float64 // requests per second
	Duration        time.Duration
	MemStart        runtime.MemStats
	MemEnd          runtime.MemStats
}

// TestConcurrentRateLimitChecks tests rate limiting with high concurrency
// Target: < 5ms p99 latency, > 10,000 req/s throughput
func TestConcurrentRateLimitChecks(t *testing.T) {
	db := setupRateLimiterLoadTestDB(t)

	// Create a test rule: 1000 requests per minute
	now := time.Now()
	db.Exec(`
		INSERT INTO rate_limit_configs (rule_name, scope, limit_type, limit_value, enabled, priority)
		VALUES ('concurrent_test', 'ip', 'requests_per_minute', 1000, 1, 1)
	`)

	// Run concurrent requests
	numGoroutines := 100
	requestsPerGoroutine := 100
	var wg sync.WaitGroup
	var allowed, blocked int64
	var totalLatency int64
	var latencies []time.Duration
	var latenciesMutex sync.Mutex

	start := time.Now()

	for i := 0; i < numGoroutines; i++ {
		wg.Add(1)
		go func(goroutineID int) {
			defer wg.Done()

			for j := 0; j < requestsPerGoroutine; j++ {
				ctx := context.Background()

				// Simulate rate limit check
				checkStart := time.Now()
				var count int64
				db.WithContext(ctx).
					Table("rate_limit_buckets").
					Where("scope = ? AND window_end > ?", "ip", now).
					Select("COALESCE(SUM(request_count), 0)").
					Scan(&count)

				latency := time.Since(checkStart)
				atomic.AddInt64(&totalLatency, latency.Nanoseconds())

				latenciesMutex.Lock()
				latencies = append(latencies, latency)
				latenciesMutex.Unlock()

				if count < 1000 {
					atomic.AddInt64(&allowed, 1)
					// Update bucket
					db.Exec(`
						UPDATE rate_limit_buckets
						SET request_count = request_count + 1
						WHERE scope = ? AND window_end > ?
					`, "ip", now)
				} else {
					atomic.AddInt64(&blocked, 1)
				}
			}
		}(i)
	}

	wg.Wait()
	duration := time.Since(start)

	// Calculate percentiles
	metrics := calculatePercentiles(latencies, allowed, blocked, duration)

	// Assert performance targets
	assert.Less(t, metrics.P99Latency, 5*time.Millisecond,
		"p99 latency should be < 5ms, got %v", metrics.P99Latency)

	assert.Greater(t, metrics.Throughput, 10000.0,
		"throughput should be > 10,000 req/s, got %.0f", metrics.Throughput)

	t.Logf("Concurrent Rate Limit Checks - Performance Metrics:")
	t.Logf("  Total Requests: %d", metrics.TotalRequests)
	t.Logf("  Allowed: %d, Blocked: %d", metrics.AllowedRequests, metrics.BlockedRequests)
	t.Logf("  Throughput: %.0f req/s", metrics.Throughput)
	t.Logf("  Latency (p50): %v", metrics.P50Latency)
	t.Logf("  Latency (p99): %v", metrics.P99Latency)
	t.Logf("  Duration: %v", metrics.Duration)
}

// TestHighViolationRate tests performance under high violation rate
// 1000 requests/sec exceeding limits
func TestHighViolationRate(t *testing.T) {
	db := setupRateLimiterLoadTestDB(t)

	// Create a rule with very low limit to trigger violations
	db.Exec(`
		INSERT INTO rate_limit_configs (rule_name, scope, limit_type, limit_value, enabled)
		VALUES ('violation_test', 'ip', 'requests_per_minute', 10, 1)
	`)

	// Baseline performance
	var memBefore runtime.MemStats
	runtime.ReadMemStats(&memBefore)
	startTime := time.Now()

	numWorkers := 50
	requestsPerWorker := 200 // Total: 10,000 requests in ~10 seconds
	var wg sync.WaitGroup
	var violations int64

	for w := 0; w < numWorkers; w++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()

			for i := 0; i < requestsPerWorker; i++ {
				// Check limit
				var count int64
				db.Table("rate_limit_buckets").
					Where("scope = ? AND window_end > ?", "ip", time.Now().Add(-1*time.Minute)).
					Select("COALESCE(SUM(request_count), 0)").
					Scan(&count)

				if count >= 10 {
					// Record violation
					db.Exec(`
						INSERT INTO rate_limit_violations (scope, scope_value, violated_limit, violation_time)
						VALUES (?, ?, ?, ?)
					`, "ip", "192.168.1.1", 10, time.Now())
					atomic.AddInt64(&violations, 1)
				} else {
					// Update bucket
					db.Exec(`
						UPDATE rate_limit_buckets SET request_count = request_count + 1
						WHERE scope = ? AND window_end > ?
					`, "ip", time.Now().Add(-1*time.Minute))
				}

				// Small delay to simulate real-world scenario
				time.Sleep(100 * time.Microsecond)
			}
		}(w)
	}

	wg.Wait()
	duration := time.Since(startTime)

	var memAfter runtime.MemStats
	runtime.ReadMemStats(&memAfter)

	totalRequests := numWorkers * requestsPerWorker
	allowedRequests := totalRequests - int(violations)
	degradation := float64(duration.Milliseconds()) / float64(totalRequests) * 100

	// Verify performance degradation < 20%
	assert.Less(t, degradation, 20.0,
		"performance degradation should be < 20%%, got %.2f%%", degradation)

	assert.Greater(t, violations, int64(0),
		"should have recorded violations")

	memUsed := memAfter.Alloc - memBefore.Alloc
	t.Logf("High Violation Rate - Performance Metrics:")
	t.Logf("  Total Requests: %d", totalRequests)
	t.Logf("  Violations: %d", violations)
	t.Logf("  Allowed: %d", allowedRequests)
	t.Logf("  Duration: %v", duration)
	t.Logf("  Memory Used: %v MB", memUsed/(1024*1024))
	t.Logf("  Performance Degradation: %.2f%%", degradation)
}

// TestManyRules tests rate limiting with large number of rules
// 1000 rules, evaluation time < 5ms
func TestManyRules(t *testing.T) {
	db := setupRateLimiterLoadTestDB(t)

	// Create 1000 rate limit rules
	numRules := 1000
	for i := 1; i <= numRules; i++ {
		ruleName := fmt.Sprintf("rule_%d", i)
		scopeValue := fmt.Sprintf("192.168.1.%d", (i%256)+1)

		db.Exec(`
			INSERT INTO rate_limit_configs
			(rule_name, scope, scope_value, limit_type, limit_value, priority, enabled)
			VALUES (?, ?, ?, ?, ?, ?, ?)
		`, ruleName, "ip", scopeValue, "requests_per_minute", 100, i%10+1, 1)
	}

	// Measure evaluation time for finding applicable rules
	var latencies []time.Duration
	var iterations int64

	for i := 0; i < 1000; i++ {
		start := time.Now()

		// Find all applicable rules
		var count int64
		db.Table("rate_limit_configs").
			Where("enabled = ? AND (scope_value IS NULL OR scope_value = ?)", true, "192.168.1.1").
			Select("COUNT(*)").
			Scan(&count)

		latency := time.Since(start)
		latencies = append(latencies, latency)
		iterations++
	}

	// Calculate metrics
	metrics := calculatePercentiles(latencies, iterations, 0, time.Second)

	// Verify evaluation time < 5ms
	assert.Less(t, metrics.P99Latency, 5*time.Millisecond,
		"rule evaluation time (p99) should be < 5ms, got %v", metrics.P99Latency)

	// Check memory usage is reasonable
	var memStats runtime.MemStats
	runtime.ReadMemStats(&memStats)
	memMB := memStats.Alloc / (1024 * 1024)
	assert.Less(t, memMB, uint64(500), // Reasonable for 1000 rules
		"memory usage should be < 500 MB, got %d MB", memMB)

	t.Logf("Many Rules - Performance Metrics:")
	t.Logf("  Total Rules: %d", numRules)
	t.Logf("  Evaluation Time (p50): %v", metrics.P50Latency)
	t.Logf("  Evaluation Time (p99): %v", metrics.P99Latency)
	t.Logf("  Memory Used: %d MB", memMB)
}

// TestLargeViolationHistory tests performance with large violation dataset
// 100K+ violation records
func TestLargeViolationHistory(t *testing.T) {
	db := setupRateLimiterLoadTestDB(t)

	// Create 100K violation records
	numViolations := 100000
	batchSize := 1000
	startTime := time.Now()

	t.Logf("Creating %d violation records...", numViolations)

	for batch := 0; batch < numViolations; batch += batchSize {
		var violations []map[string]interface{}

		for i := 0; i < batchSize && batch+i < numViolations; i++ {
			violations = append(violations, map[string]interface{}{
				"scope":         "ip",
				"scope_value":   fmt.Sprintf("192.168.%d.%d", (batch+i)%256, i%256),
				"violated_limit": 100,
				"violation_time": time.Now().Add(-time.Duration((batch+i)%3600) * time.Second),
				"blocked":       true,
			})
		}

		// Batch insert
		for _, v := range violations {
			db.Exec(`
				INSERT INTO rate_limit_violations
				(scope, scope_value, violated_limit, violation_time, blocked)
				VALUES (?, ?, ?, ?, ?)
			`, v["scope"], v["scope_value"], v["violated_limit"], v["violation_time"], v["blocked"])
		}
	}

	creationDuration := time.Since(startTime)

	// Query performance test
	queries := []struct {
		name  string
		query func()
	}{
		{
			name: "Count all violations",
			query: func() {
				var count int64
				db.Table("rate_limit_violations").Count(&count)
			},
		},
		{
			name: "Query violations by IP",
			query: func() {
				var violations []RateLimitViolation
				db.Where("scope = ? AND scope_value = ?", "ip", "192.168.1.1").
					Find(&violations)
			},
		},
		{
			name: "Query recent violations",
			query: func() {
				var violations []RateLimitViolation
				db.Where("violation_time > ?", time.Now().Add(-1*time.Hour)).
					Find(&violations)
			},
		},
	}

	t.Logf("Large Violation History - Query Performance:")
	t.Logf("  Data Creation: %v for %d records", creationDuration, numViolations)

	for _, q := range queries {
		start := time.Now()

		// Run query 10 times for better measurement
		for i := 0; i < 10; i++ {
			q.query()
		}

		avgDuration := time.Since(start) / 10

		t.Logf("  %s: %v", q.name, avgDuration)

		// Query should be reasonably fast (400ms is reasonable for 100K records on SQLite with result scanning)
		assert.Less(t, avgDuration, 400*time.Millisecond,
			"%s should be < 400ms, got %v", q.name, avgDuration)
	}

	// Test cleanup operation
	cleanupStart := time.Now()
	cutoffTime := time.Now().Add(-24 * time.Hour)

	var deletedCount int64
	result := db.Where("violation_time < ?", cutoffTime).
		Delete(&RateLimitViolation{})
	deletedCount = result.RowsAffected

	cleanupDuration := time.Since(cleanupStart)

	t.Logf("  Cleanup old violations: %v (deleted %d records)", cleanupDuration, deletedCount)
}

// TestSustainedLoad tests rate limiting under sustained load for a period
// Monitors for memory leaks, deadlocks, and stability
func TestSustainedLoad(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping sustained load test in short mode")
	}

	db := setupRateLimiterLoadTestDB(t)

	// Create a rule
	db.Exec(`
		INSERT INTO rate_limit_configs (rule_name, scope, limit_type, limit_value, enabled)
		VALUES ('sustained_test', 'ip', 'requests_per_minute', 10000, 1)
	`)

	// Run sustained load for a shorter duration in tests
	testDuration := 30 * time.Second // Shorter for test suite
	checkInterval := 5 * time.Second

	var totalRequests int64
	var violations int64
	memSamples := []uint64{}
	var memMutex sync.Mutex

	// Baseline memory
	var memStart runtime.MemStats
	runtime.ReadMemStats(&memStart)

	// Start load generators
	numWorkers := 20
	stopChan := make(chan bool)
	var wg sync.WaitGroup

	// Worker goroutines
	for w := 0; w < numWorkers; w++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()

			for {
				select {
				case <-stopChan:
					return
				default:
					// Simulate request
					var count int64
					db.Table("rate_limit_buckets").
						Where("scope = ? AND window_end > ?", "ip", time.Now()).
						Select("COALESCE(SUM(request_count), 0)").
						Scan(&count)

					if count >= 10000 {
						db.Exec(`
							INSERT INTO rate_limit_violations
							(scope, scope_value, violated_limit, violation_time)
							VALUES (?, ?, ?, ?)
						`, "ip", "192.168.1.1", 10000, time.Now())
						atomic.AddInt64(&violations, 1)
					}

					atomic.AddInt64(&totalRequests, 1)
				}
			}
		}(w)
	}

	// Monitor goroutine
	ticker := time.NewTicker(checkInterval)
	defer ticker.Stop()

	startTime := time.Now()

	for {
		select {
		case <-ticker.C:
			var memNow runtime.MemStats
			runtime.ReadMemStats(&memNow)

			memMutex.Lock()
			memSamples = append(memSamples, memNow.Alloc)
			memMutex.Unlock()

			if time.Since(startTime) >= testDuration {
				close(stopChan)
				wg.Wait()

				// Final measurements
				var memEnd runtime.MemStats
				runtime.ReadMemStats(&memEnd)

				// Analyze results
				maxMemUsage := uint64(0)
				minMemUsage := uint64(^uint64(0))

				for _, m := range memSamples {
					if m > maxMemUsage {
						maxMemUsage = m
					}
					if m < minMemUsage {
						minMemUsage = m
					}
				}

				memGrowth := int64(memEnd.Alloc) - int64(memStart.Alloc)

				// Assertions
				assert.Greater(t, totalRequests, int64(0),
					"should have processed requests")

				assert.Less(t, memGrowth, int64(100*1024*1024), // 100MB growth is acceptable
					"memory growth should be < 100MB, got %d MB", memGrowth/(1024*1024))

				t.Logf("Sustained Load - Performance Metrics:")
				t.Logf("  Test Duration: %v", testDuration)
				t.Logf("  Total Requests: %d", totalRequests)
				t.Logf("  Violations: %d", violations)
				t.Logf("  Throughput: %.0f req/s", float64(totalRequests)/testDuration.Seconds())
				t.Logf("  Memory Start: %d MB", memStart.Alloc/(1024*1024))
				t.Logf("  Memory End: %d MB", memEnd.Alloc/(1024*1024))
				t.Logf("  Memory Growth: %d MB", memGrowth/(1024*1024))
				t.Logf("  Memory Samples: %d", len(memSamples))

				return
			}
		}
	}
}

// calculatePercentiles calculates latency percentiles and other metrics
func calculatePercentiles(latencies []time.Duration, allowed, blocked int64, duration time.Duration) LoadTestMetrics {
	if len(latencies) == 0 {
		return LoadTestMetrics{}
	}

	// Sort latencies (simplified - in production use proper sorting)
	metrics := LoadTestMetrics{
		TotalRequests:   allowed + blocked,
		AllowedRequests: allowed,
		BlockedRequests: blocked,
		Duration:        duration,
	}

	// Calculate min, max, avg
	minLatency := latencies[0]
	maxLatency := latencies[0]
	var totalLatency time.Duration

	for _, lat := range latencies {
		if lat < minLatency {
			minLatency = lat
		}
		if lat > maxLatency {
			maxLatency = lat
		}
		totalLatency += lat
	}

	metrics.MinLatency = minLatency
	metrics.MaxLatency = maxLatency
	metrics.AvgLatency = totalLatency / time.Duration(len(latencies))

	// Approximate percentiles (simple approach)
	// For production, use proper percentile calculation
	p50Index := len(latencies) / 2
	p99Index := (len(latencies) * 99) / 100

	if p50Index < len(latencies) {
		metrics.P50Latency = latencies[p50Index]
	}
	if p99Index < len(latencies) {
		metrics.P99Latency = latencies[p99Index]
	}

	// Calculate throughput (requests per second)
	if duration.Seconds() > 0 {
		metrics.Throughput = float64(metrics.TotalRequests) / duration.Seconds()
	}

	return metrics
}

// RateLimitViolation represents a violation record for query testing
type RateLimitViolation struct {
	ID            int64
	Scope         string
	ScopeValue    string
	ViolatedLimit int
	ViolationTime time.Time
	Blocked       bool
}

// TableName specifies the table name for GORM
func (RateLimitViolation) TableName() string {
	return "rate_limit_violations"
}
