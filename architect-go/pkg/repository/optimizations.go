package repository

import (
	"fmt"
	"strings"
	"sync"
	"time"
)

// QueryMetrics tracks query performance and identifies N+1 patterns
type QueryMetrics struct {
	mu              sync.RWMutex
	queries         []QueryRecord
	maxSize         int
	n1Threshold     int
	lastCleanup     time.Time
	cleanupInterval time.Duration
}

// QueryRecord represents a single query execution
type QueryRecord struct {
	SQL       string
	Duration  time.Duration
	Timestamp time.Time
	RowsRead  int
}

// NewQueryMetrics creates a new query metrics tracker
func NewQueryMetrics(n1Threshold int) *QueryMetrics {
	qm := &QueryMetrics{
		queries:         make([]QueryRecord, 0, 1000),
		maxSize:         1000,
		n1Threshold:     n1Threshold,
		lastCleanup:     time.Now(),
		cleanupInterval: 5 * time.Minute,
	}

	return qm
}

// RecordQuery records a query execution
func (qm *QueryMetrics) RecordQuery(sql string, duration time.Duration, rowsRead int) {
	qm.mu.Lock()
	defer qm.mu.Unlock()

	qm.queries = append(qm.queries, QueryRecord{
		SQL:       sql,
		Duration:  duration,
		Timestamp: time.Now(),
		RowsRead:  rowsRead,
	})

	// Remove old entries if we exceed max size
	if len(qm.queries) > qm.maxSize {
		qm.queries = qm.queries[len(qm.queries)-qm.maxSize:]
	}

	// Periodic cleanup
	if time.Since(qm.lastCleanup) > qm.cleanupInterval {
		qm.cleanupOldRecords()
		qm.lastCleanup = time.Now()
	}
}

// cleanupOldRecords removes records older than 1 hour
func (qm *QueryMetrics) cleanupOldRecords() {
	cutoff := time.Now().Add(-1 * time.Hour)
	start := 0

	for i, record := range qm.queries {
		if record.Timestamp.After(cutoff) {
			start = i
			break
		}
	}

	qm.queries = qm.queries[start:]
}

// DetectN1Queries identifies potential N+1 query patterns
func (qm *QueryMetrics) DetectN1Queries() map[string]int {
	qm.mu.RLock()
	defer qm.mu.RUnlock()

	patterns := make(map[string]int)
	queryPatternCount := make(map[string]int)

	// Count occurrences of similar queries
	for _, record := range qm.queries {
		// Normalize query pattern
		pattern := normalizeQueryPattern(record.SQL)
		queryPatternCount[pattern]++
	}

	// Find patterns that exceed threshold (indicate N+1)
	for pattern, count := range queryPatternCount {
		if count > qm.n1Threshold {
			patterns[pattern] = count
		}
	}

	return patterns
}

// AverageQueryDuration returns average query duration
func (qm *QueryMetrics) AverageQueryDuration() time.Duration {
	qm.mu.RLock()
	defer qm.mu.RUnlock()

	if len(qm.queries) == 0 {
		return 0
	}

	var total time.Duration
	for _, record := range qm.queries {
		total += record.Duration
	}

	return total / time.Duration(len(qm.queries))
}

// SlowQueries returns queries slower than the threshold
func (qm *QueryMetrics) SlowQueries(threshold time.Duration) []QueryRecord {
	qm.mu.RLock()
	defer qm.mu.RUnlock()

	var slow []QueryRecord
	for _, record := range qm.queries {
		if record.Duration > threshold {
			slow = append(slow, record)
		}
	}

	return slow
}

// normalizeQueryPattern removes values from SQL to identify patterns
func normalizeQueryPattern(sql string) string {
	// Simple normalization: remove common values
	// In production, use a proper SQL parser
	pattern := sql

	// Replace numbers with ?
	for i := 0; i < 10; i++ {
		pattern = strings.ReplaceAll(pattern, fmt.Sprintf("%d", i), "?")
	}

	// Replace UUIDs/long strings with ?
	// This is a simplified version
	return pattern
}

// ConnectionPoolConfig defines database connection pool settings
type ConnectionPoolConfig struct {
	MaxConnections   int
	MinConnections   int
	MaxIdleTime      time.Duration
	ConnectionTimeout time.Duration
}

// DefaultConnectionPoolConfig returns optimized connection pool settings
func DefaultConnectionPoolConfig() ConnectionPoolConfig {
	return ConnectionPoolConfig{
		MaxConnections:    100,
		MinConnections:    20,
		MaxIdleTime:       10 * time.Second,
		ConnectionTimeout: 5 * time.Second,
	}
}

// QueryOptimizationTips provides recommendations for query optimization
type QueryOptimizationTips struct {
	// Identify missing indexes
	MissingIndexes []string

	// Identify N+1 patterns
	N1Patterns map[string]int

	// Identify slow queries
	SlowQueries []QueryRecord

	// Recommendations
	Recommendations []string
}

// AnalyzeQueryPerformance analyzes query performance and returns optimization tips
func AnalyzeQueryPerformance(metrics *QueryMetrics) QueryOptimizationTips {
	tips := QueryOptimizationTips{
		MissingIndexes:  []string{},
		N1Patterns:      metrics.DetectN1Queries(),
		SlowQueries:     metrics.SlowQueries(50 * time.Millisecond),
		Recommendations: []string{},
	}

	// Generate recommendations based on analysis
	if len(tips.N1Patterns) > 0 {
		tips.Recommendations = append(tips.Recommendations,
			"Consider using JOIN queries or eager loading to reduce N+1 patterns")
	}

	if len(tips.SlowQueries) > 0 {
		tips.Recommendations = append(tips.Recommendations,
			"Add indexes on frequently filtered columns")
		tips.Recommendations = append(tips.Recommendations,
			"Consider caching frequently accessed data")
	}

	if metrics.AverageQueryDuration() > 20*time.Millisecond {
		tips.Recommendations = append(tips.Recommendations,
			"Average query duration is high; review query execution plans")
	}

	return tips
}
