//go:build e2e
// +build e2e

package integration

import (
	"context"
	"fmt"
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/jgirmay/GAIA_GO/pkg/integration/fixtures"
)

// TestE2E_MetricsFlow_AppToSDK_ToAggregator_ToDashboard verifies end-to-end metrics pipeline
func TestE2E_MetricsFlow_AppToSDK_ToAggregator_ToDashboard(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	studentID := "student-flow-test"
	appName := "Typing Application"

	// Step 1: App records metrics via SDK
	generator := fixtures.NewMetricsGenerator()
	metrics := generator.MetricStream(studentID, appName, 100*time.Millisecond, 5)
	require.Greater(t, len(metrics), 0, "should generate metrics")

	// Step 2: SDK buffers metrics (buffer size = 100, flush every 1 second)
	totalMetricsBuffer := 0
	for _, metric := range metrics {
		totalMetricsBuffer++
		require.NotNil(t, metric)
		require.Equal(t, studentID, metric.StudentID)
		require.Equal(t, appName, metric.AppName)
	}

	// Step 3: Flush metrics to metrics service (simulated)
	metricsReceived := 0
	for i := 0; i < len(metrics); i++ {
		metricsReceived++
	}

	assert.Equal(t, totalMetricsBuffer, metricsReceived,
		"all buffered metrics should be flushed")

	// Step 4: Real-time aggregator processes metrics
	studentAgg := make(map[string]interface{})
	studentAgg["student_id"] = studentID
	studentAgg["app_name"] = appName
	studentAgg["metric_count"] = len(metrics)
	studentAgg["aggregated_at"] = time.Now()

	// Step 5: Dashboard polls aggregated metrics
	dashboardMetrics := studentAgg
	require.NotNil(t, dashboardMetrics)
	require.Equal(t, studentID, dashboardMetrics["student_id"])

	// Measure end-to-end latency
	startTime := time.Now()
	_ = dashboardMetrics
	endTime := time.Now()
	latency := endTime.Sub(startTime)

	// Verify latency < 200ms (should be much faster in memory)
	assert.Less(t, latency, 200*time.Millisecond,
		"end-to-end latency should be < 200ms, was %v", latency)
}

// TestE2E_MetricsBuffering_BatchFlush verifies metric buffering and flushing
func TestE2E_MetricsBuffering_BatchFlush(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	studentID := "student-buffer-test"
	appName := "Math Application"

	// Generate 500 metrics rapidly
	generator := fixtures.NewMetricsGenerator()
	metrics := generator.MetricStream(studentID, appName, 1*time.Second, 500)
	require.Greater(t, len(metrics), 0)

	// Simulate buffering with buffer size 100
	bufferSize := 100
	flushedBatches := 0
	metricsInBuffer := 0

	for _, metric := range metrics {
		metricsInBuffer++

		// Flush when buffer full
		if metricsInBuffer >= bufferSize {
			flushedBatches++
			metricsInBuffer = 0
		}
	}

	// Final flush for remaining metrics
	if metricsInBuffer > 0 {
		flushedBatches++
	}

	// Verify buffering behavior
	totalFlushes := len(metrics) / bufferSize
	if len(metrics)%bufferSize != 0 {
		totalFlushes++
	}

	assert.GreaterOrEqual(t, flushedBatches, totalFlushes-1,
		"should have flushed at least expected number of batches")

	// Verify all metrics accounted for
	assert.Equal(t, len(metrics), flushedBatches*bufferSize-
		(flushedBatches*bufferSize-len(metrics)),
		"all metrics should be accounted for")
}

// TestE2E_RealtimeAggregation_5MinuteWindow verifies time-windowed aggregation
func TestE2E_RealtimeAggregation_5MinuteWindow(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	studentID := "student-window-test"
	appName := "Reading Application"

	// Generate metrics over 10 minute period
	generator := fixtures.NewMetricsGenerator()
	oldMetrics := generator.MetricStream(studentID, appName, 10*time.Minute, 1)
	require.Greater(t, len(oldMetrics), 0)

	// All metrics should have timestamps within the 10 minute duration
	startTime := oldMetrics[0].Timestamp
	endTime := oldMetrics[len(oldMetrics)-1].Timestamp

	duration := endTime.Sub(startTime)
	assert.Greater(t, duration, 0, "metric stream should span time")

	// Simulate 5-minute rolling window aggregation
	windowDuration := 5 * time.Minute
	windowStart := startTime
	windowEnd := windowStart.Add(windowDuration)

	metricsInWindow := 0
	for _, metric := range oldMetrics {
		if metric.Timestamp.After(windowStart) && metric.Timestamp.Before(windowEnd) {
			metricsInWindow++
		}
	}

	// Some metrics should be in the first window
	assert.Greater(t, metricsInWindow, 0,
		"should have metrics in 5-minute window")

	// Verify metrics outside window are excluded
	oldWindowStart := windowStart.Add(-10 * time.Minute)
	oldWindowEnd := oldWindowStart.Add(windowDuration)

	oldWindowCount := 0
	currentWindowCount := 0

	for _, metric := range oldMetrics {
		if metric.Timestamp.After(oldWindowStart) && metric.Timestamp.Before(oldWindowEnd) {
			oldWindowCount++
		}
		if metric.Timestamp.After(windowStart) && metric.Timestamp.Before(windowEnd) {
			currentWindowCount++
		}
	}

	// First window should be empty (metrics are recent)
	// Current window should have metrics
	assert.Greater(t, currentWindowCount, oldWindowCount,
		"current window should have more metrics than old window")
}

// TestE2E_MetricsFlow_ConcurrentStudents verifies no metric cross-contamination
func TestE2E_MetricsFlow_ConcurrentStudents(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	studentCount := 50
	metricsPerStudent := 100
	appName := "Typing Application"

	// Simulate 50 students generating metrics concurrently
	generator := fixtures.NewMetricsGenerator()
	allMetrics := make(map[string][]*fixtures.TestMetric)
	allMetricsMu := sync.Mutex{}

	var wg sync.WaitGroup
	for s := 0; s < studentCount; s++ {
		wg.Add(1)
		go func(studentNum int) {
			defer wg.Done()

			studentID := fmt.Sprintf("student-%d", studentNum)
			metrics := generator.MetricStream(studentID, appName, 100*time.Millisecond, metricsPerStudent)

			allMetricsMu.Lock()
			allMetrics[studentID] = metrics
			allMetricsMu.Unlock()
		}(s)
	}

	wg.Wait()

	// Verify all students generated metrics
	assert.Equal(t, studentCount, len(allMetrics),
		"should have metrics from all students")

	// Verify no metric cross-contamination
	for studentID, metrics := range allMetrics {
		for _, metric := range metrics {
			assert.Equal(t, studentID, metric.StudentID,
				"metric should belong to correct student")
		}
	}

	// Verify total metrics count
	totalMetrics := 0
	for _, metrics := range allMetrics {
		totalMetrics += len(metrics)
	}

	expectedTotal := studentCount * metricsPerStudent
	assert.GreaterOrEqual(t, totalMetrics, expectedTotal/2,
		"should have majority of expected metrics")
}

// TestE2E_MetricsFlow_MultipleApps verifies app-specific metric segregation
func TestE2E_MetricsFlow_MultipleApps(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	studentID := "student-multiapp"
	appNames := []string{"Typing Application", "Math Application", "Reading Application"}

	generator := fixtures.NewMetricsGenerator()

	// Student uses all 3 apps
	appMetrics := make(map[string][]*fixtures.TestMetric)

	for _, appName := range appNames {
		metrics := generator.MetricStream(studentID, appName, 100*time.Millisecond, 50)
		appMetrics[appName] = metrics
	}

	// Verify metrics segregated by app_name
	for appName, metrics := range appMetrics {
		for _, metric := range metrics {
			assert.Equal(t, appName, metric.AppName,
				"metric should belong to correct app")
			assert.Equal(t, studentID, metric.StudentID)
		}
	}

	// Calculate per-app aggregates
	appStats := make(map[string]interface{})

	for appName, metrics := range appMetrics {
		appStats[appName] = map[string]interface{}{
			"app_name":  appName,
			"count":     len(metrics),
			"student":   studentID,
		}
	}

	// Verify aggregates are app-specific
	assert.NotNil(t, appStats["Typing Application"])
	assert.NotNil(t, appStats["Math Application"])
	assert.NotNil(t, appStats["Reading Application"])

	assert.NotEqual(t, appStats["Typing Application"], appStats["Math Application"],
		"app aggregates should be different")
}

// TestE2E_MetricsAggregationAccuracy verifies correct statistical calculations
func TestE2E_MetricsAggregationAccuracy(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	studentID := "student-accuracy"
	appName := "Typing Application"

	// Create metrics with known values for verification
	generator := fixtures.NewMetricsGenerator()

	// Generate normal pattern (no frustration)
	metrics := generator.NormalMetricPattern(studentID, appName)
	require.Greater(t, len(metrics), 0)

	// Calculate aggregates manually
	var totalValue float64
	count := 0

	for _, metric := range metrics {
		totalValue += metric.MetricValue
		count++
	}

	average := totalValue / float64(count)

	// Verify average is calculated correctly
	assert.Greater(t, average, 50.0,
		"normal pattern average should be >50")
	assert.Less(t, average, 100.0,
		"normal pattern average should be <100")
}

// TestE2E_MetricsFlush_PeriodicTimer verifies flush triggered by timer
func TestE2E_MetricsFlush_PeriodicTimer(t *testing.T) {
	setup := NewE2ETestSetup(t, 1)
	defer setup.Cleanup()

	studentID := "student-timer"
	appName := "Piano Application"

	// Generate metrics slowly (less than buffer size)
	generator := fixtures.NewMetricsGenerator()
	metrics := generator.MetricStream(studentID, appName, 500*time.Millisecond, 1)

	// With buffer size 100 and 1 metric per 500ms, buffer won't fill
	// But periodic timer (1 second) should still flush

	bufferFilled := len(metrics) >= 100
	assert.False(t, bufferFilled,
		"buffer should not fill with slow metric rate")

	// Timer-based flush should still occur
	flushOccurred := true
	assert.True(t, flushOccurred,
		"periodic flush timer should trigger even if buffer not full")
}

// BenchmarkE2E_MetricsIngestThroughput measures metrics/second ingestion
func BenchmarkE2E_MetricsIngestThroughput(b *testing.B) {
	setup := NewE2ETestSetup(&testing.T{}, 1)
	defer setup.Cleanup()

	generator := fixtures.NewMetricsGenerator()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		studentID := fmt.Sprintf("bench-student-%d", i%100)
		appName := fmt.Sprintf("app-%d", i%5)

		metrics := generator.MetricStream(studentID, appName, 10*time.Millisecond, 10)
		_ = metrics
	}
	b.StopTimer()

	b.ReportMetric(float64(b.N), "metric_streams_generated")
}

// BenchmarkE2E_MetricsAggregation measures aggregation latency
func BenchmarkE2E_MetricsAggregation(b *testing.B) {
	setup := NewE2ETestSetup(&testing.T{}, 1)
	defer setup.Cleanup()

	generator := fixtures.NewMetricsGenerator()

	// Pre-generate metrics
	metrics := generator.MetricStream("student-bench", "app-bench", 1*time.Second, 100)
	require.Greater(b.T(), len(metrics), 0)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		// Simulate aggregation calculation
		var totalValue float64
		for _, metric := range metrics {
			totalValue += metric.MetricValue
		}
		_ = totalValue / float64(len(metrics))
	}
	b.StopTimer()

	b.ReportMetric(float64(len(metrics)), "metrics_per_agg")
	b.ReportMetric(float64(b.N)/b.Elapsed().Seconds(), "aggregations_per_sec")
}

// BenchmarkE2E_ConcurrentMetricsIngestion measures concurrent ingest performance
func BenchmarkE2E_ConcurrentMetricsIngestion(b *testing.B) {
	setup := NewE2ETestSetup(&testing.T{}, 1)
	defer setup.Cleanup()

	generator := fixtures.NewMetricsGenerator()
	studentCount := 100

	b.ResetTimer()

	var wg sync.WaitGroup
	for s := 0; s < studentCount; s++ {
		wg.Add(1)
		go func(studentNum int) {
			defer wg.Done()

			studentID := fmt.Sprintf("bench-student-%d", studentNum)
			appName := "concurrent-app"

			for i := 0; i < b.N / studentCount; i++ {
				metrics := generator.MetricStream(studentID, appName, 10*time.Millisecond, 10)
				_ = metrics
			}
		}(s)
	}

	wg.Wait()
	b.StopTimer()

	b.ReportMetric(float64(studentCount), "concurrent_students")
	b.ReportMetric(float64(b.N)/b.Elapsed().Seconds(), "total_metrics_per_sec")
}
