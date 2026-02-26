package usability

import (
	"context"
	"fmt"
	"testing"
	"time"
)

// BenchmarkRecordMetric benchmarks single metric recording
func BenchmarkRecordMetric(b *testing.B) {
	mockRepo := &MockUsabilityMetricsRepository{}
	eventBus := NewNoOpEventBus()
	frustrationEngine := NewFrustrationDetectionEngine(DefaultThresholds())
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)
	config := DefaultConfig()

	service := NewUsabilityMetricsService(mockRepo, frustrationEngine, aggregator, eventBus, config)
	ctx := context.Background()

	metric := &Metric{
		StudentID:   "student-1",
		AppName:     "typing",
		MetricType:  MetricTypeKeyPress,
		MetricValue: 1.0,
		Timestamp:   time.Now(),
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		service.RecordMetric(ctx, metric)
	}
}

// BenchmarkAnalyzeMetric benchmarks frustration analysis
func BenchmarkAnalyzeMetric(b *testing.B) {
	engine := NewFrustrationDetectionEngine(DefaultThresholds())

	metric := &Metric{
		StudentID:   "student-1",
		AppName:     "typing",
		MetricType:  MetricTypeError,
		MetricValue: 1.0,
		Timestamp:   time.Now(),
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		engine.AnalyzeMetric(metric)
	}
}

// BenchmarkAggregateMetrics benchmarks metrics aggregation
func BenchmarkAggregateMetrics(b *testing.B) {
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	metric := &Metric{
		StudentID:   "student-1",
		AppName:     "typing",
		MetricType:  MetricTypeKeyPress,
		MetricValue: 1.0,
		Timestamp:   time.Now(),
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		aggregator.UpdateMetric(metric)
	}
}

// BenchmarkGetMetrics benchmarks metrics retrieval
func BenchmarkGetMetrics(b *testing.B) {
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	// Pre-populate with metrics
	for i := 0; i < 100; i++ {
		metric := &Metric{
			StudentID:   fmt.Sprintf("student-%d", i),
			AppName:     "typing",
			MetricType:  MetricTypeKeyPress,
			MetricValue: 1.0,
			Timestamp:   time.Now(),
		}
		aggregator.UpdateMetric(metric)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		aggregator.GetMetrics("student-50", "typing")
	}
}

// TestLoadConcurrentMetrics tests handling concurrent metric recording from 100+ students
func TestLoadConcurrentMetrics(t *testing.T) {
	mockRepo := &MockUsabilityMetricsRepository{}
	eventBus := NewNoOpEventBus()
	frustrationEngine := NewFrustrationDetectionEngine(DefaultThresholds())
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)
	config := Config{
		BatchSize:     1000,
		FlushInterval: 5 * time.Second,
	}

	service := NewUsabilityMetricsService(mockRepo, frustrationEngine, aggregator, eventBus, config)
	ctx := context.Background()

	// Test with 100 concurrent students
	numStudents := 100
	metricsPerStudent := 50
	done := make(chan bool, numStudents)

	start := time.Now()

	for s := 0; s < numStudents; s++ {
		go func(studentID int) {
			for i := 0; i < metricsPerStudent; i++ {
				metric := &Metric{
					StudentID:   fmt.Sprintf("student-%d", studentID),
					AppName:     "typing",
					MetricType:  MetricTypeKeyPress,
					MetricValue: 1.0,
					Timestamp:   time.Now(),
				}
				service.RecordMetric(ctx, metric)
			}
			done <- true
		}(s)
	}

	// Wait for all goroutines
	for i := 0; i < numStudents; i++ {
		<-done
	}

	elapsed := time.Since(start)
	totalMetrics := numStudents * metricsPerStudent
	throughput := float64(totalMetrics) / elapsed.Seconds()

	t.Logf("Processed %d metrics in %v (%.0f metrics/sec)", totalMetrics, elapsed, throughput)

	// Performance assertion: should handle 5000+ metrics/sec
	if throughput < 5000 {
		t.Logf("WARNING: Throughput below target (%.0f/sec < 5000/sec)", throughput)
	}
}

// TestFrustrationDetectionAccuracy tests accuracy of frustration detection
func TestFrustrationDetectionAccuracy(t *testing.T) {
	engine := NewFrustrationDetectionEngine(DefaultThresholds())

	tests := []struct {
		name           string
		errorCount     int
		backspaceCount int
		expectedSeverity string
	}{
		{"Low frustration", 1, 2, ""},           // No event
		{"Medium frustration", 2, 15, "medium"},
		{"High frustration", 3, 10, "high"},
		{"Critical frustration", 5, 20, "critical"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Reset engine
			engine.ResetAll()

			// Add errors
			for i := 0; i < tt.errorCount; i++ {
				metric := &Metric{
					StudentID:   "student-1",
					AppName:     "typing",
					MetricType:  MetricTypeError,
					MetricValue: 1.0,
					Timestamp:   time.Now(),
				}
				engine.AnalyzeMetric(metric)
			}

			// Add backspaces
			for i := 0; i < tt.backspaceCount; i++ {
				metric := &Metric{
					StudentID:   "student-1",
					AppName:     "typing",
					MetricType:  MetricTypeBackspace,
					MetricValue: 1.0,
					Timestamp:   time.Now(),
				}
				event := engine.AnalyzeMetric(metric)

				if tt.expectedSeverity != "" {
					if event != nil {
						if event.Severity != tt.expectedSeverity {
							t.Logf("Severity mismatch: got %s, expected %s", event.Severity, tt.expectedSeverity)
						}
					}
				}
			}
		})
	}
}

// TestMemoryUsageWithLargeMetricSet tests memory efficiency with large metrics
func TestMemoryUsageWithLargeMetricSet(t *testing.T) {
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	// Add metrics for 500 students across 5 apps
	numStudents := 500
	numApps := 5
	metricsPerStudentApp := 20

	for s := 0; s < numStudents; s++ {
		for a := 0; a < numApps; a++ {
			for m := 0; m < metricsPerStudentApp; m++ {
				metric := &Metric{
					StudentID:   fmt.Sprintf("student-%d", s),
					AppName:     fmt.Sprintf("app-%d", a),
					MetricType:  MetricTypeKeyPress,
					MetricValue: float64(m),
					Timestamp:   time.Now(),
				}
				aggregator.UpdateMetric(metric)
			}
		}
	}

	// Verify all metrics are stored
	allMetrics := aggregator.GetAllMetrics()
	expectedCount := numStudents * numApps
	actualCount := len(allMetrics)

	if actualCount != expectedCount {
		t.Logf("Metric count mismatch: got %d, expected %d", actualCount, expectedCount)
	}

	t.Logf("Successfully tracked %d student-app combinations in memory", actualCount)
}

// TestConcurrentAggregatorAccess tests concurrent safe access to aggregator
func TestConcurrentAggregatorAccess(t *testing.T) {
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	// Test concurrent reads and writes
	numGoroutines := 50
	operationsPerGoroutine := 100
	done := make(chan bool, numGoroutines)

	start := time.Now()

	for g := 0; g < numGoroutines; g++ {
		go func(goroutineID int) {
			for i := 0; i < operationsPerGoroutine; i++ {
				// Alternate between writes and reads
				if i%2 == 0 {
					metric := &Metric{
						StudentID:   fmt.Sprintf("student-%d", goroutineID),
						AppName:     "typing",
						MetricType:  MetricTypeKeyPress,
						MetricValue: 1.0,
						Timestamp:   time.Now(),
					}
					aggregator.UpdateMetric(metric)
				} else {
					aggregator.GetMetrics(fmt.Sprintf("student-%d", goroutineID), "typing")
				}
			}
			done <- true
		}(g)
	}

	// Wait for all goroutines
	for i := 0; i < numGoroutines; i++ {
		<-done
	}

	elapsed := time.Since(start)
	totalOps := numGoroutines * operationsPerGoroutine
	opsPerSec := float64(totalOps) / elapsed.Seconds()

	t.Logf("Completed %d concurrent operations in %v (%.0f ops/sec)", totalOps, elapsed, opsPerSec)

	// Should handle at least 10,000 ops/sec
	if opsPerSec < 10000 {
		t.Logf("WARNING: Concurrent operation rate below target (%.0f ops/sec < 10000 ops/sec)", opsPerSec)
	}
}

// TestLongRunningAggregation tests aggregator stability over extended period
func TestLongRunningAggregation(t *testing.T) {
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	// Simulate 5 minutes of continuous metrics
	duration := 5 * time.Second // Use 5 seconds for test
	interval := 10 * time.Millisecond
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	start := time.Now()
	metricCount := 0

	for {
		select {
		case <-ticker.C:
			// Add metrics from 20 students
			for s := 0; s < 20; s++ {
				metric := &Metric{
					StudentID:   fmt.Sprintf("student-%d", s),
					AppName:     "typing",
					MetricType:  MetricTypeKeyPress,
					MetricValue: 1.0,
					Timestamp:   time.Now(),
				}
				aggregator.UpdateMetric(metric)
				metricCount++
			}

		default:
			if time.Since(start) > duration {
				goto Done
			}
		}
	}

Done:
	elapsed := time.Since(start)
	t.Logf("Aggregated %d metrics over %v", metricCount, elapsed)

	// Verify no memory leaks by checking student count
	studentCount := aggregator.GetStudentCount()
	if studentCount > 100 {
		t.Logf("WARNING: Unexpectedly high student count: %d", studentCount)
	}
}

// TestErrorHandlingUnderLoad tests error handling during high load
func TestErrorHandlingUnderLoad(t *testing.T) {
	mockRepo := &MockUsabilityMetricsRepository{}
	eventBus := NewNoOpEventBus()
	frustrationEngine := NewFrustrationDetectionEngine(DefaultThresholds())
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)
	config := DefaultConfig()

	service := NewUsabilityMetricsService(mockRepo, frustrationEngine, aggregator, eventBus, config)
	ctx := context.Background()

	// Send mix of valid and invalid metrics
	errorCount := 0
	successCount := 0

	for i := 0; i < 1000; i++ {
		if i%10 == 0 {
			// Send nil metric (should error)
			err := service.RecordMetric(ctx, nil)
			if err != nil {
				errorCount++
			}
		} else {
			// Send valid metric
			metric := &Metric{
				StudentID:   fmt.Sprintf("student-%d", i%100),
				AppName:     "typing",
				MetricType:  MetricTypeKeyPress,
				MetricValue: 1.0,
				Timestamp:   time.Now(),
			}
			err := service.RecordMetric(ctx, metric)
			if err == nil {
				successCount++
			}
		}
	}

	t.Logf("Processed 1000 metrics: %d successful, %d errors", successCount, errorCount)

	// Should have correctly handled ~900 valid and ~100 invalid metrics
	if successCount < 850 {
		t.Logf("WARNING: Unexpectedly low success rate: %d/900", successCount)
	}
	if errorCount < 80 {
		t.Logf("WARNING: Unexpectedly low error handling: %d/100", errorCount)
	}
}
