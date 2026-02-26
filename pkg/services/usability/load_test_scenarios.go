package usability

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

// LoadTestScenario defines a load test configuration
type LoadTestScenario struct {
	Name                  string
	NumStudents           int
	NumApps               int
	MetricsPerStudentSec  int
	DurationSeconds       int
	NumConcurrentThreads  int
}

// LoadTestResult contains the results of a load test
type LoadTestResult struct {
	Scenario              LoadTestScenario
	TotalMetricsRecorded  int64
	TotalFrustrationEvents int64
	TotalErrors           int64
	DurationActual        time.Duration
	ThroughputMetricsSec  float64
	ThroughputEventsSec   float64
	AvgLatencyMs          float64
	P95LatencyMs          float64
	P99LatencyMs          float64
	MaxLatencyMs          float64
	MemoryPeakBytes       uint64
	Status                string
}

// StandardLoadTestScenarios returns predefined load test scenarios
func StandardLoadTestScenarios() []LoadTestScenario {
	return []LoadTestScenario{
		{
			Name:                 "Light Load - Baseline",
			NumStudents:          10,
			NumApps:              1,
			MetricsPerStudentSec: 5,
			DurationSeconds:      10,
			NumConcurrentThreads: 5,
		},
		{
			Name:                 "Medium Load - 50 Students",
			NumStudents:          50,
			NumApps:              3,
			MetricsPerStudentSec: 10,
			DurationSeconds:      30,
			NumConcurrentThreads: 10,
		},
		{
			Name:                 "Heavy Load - 200 Students",
			NumStudents:          200,
			NumApps:              5,
			MetricsPerStudentSec: 15,
			DurationSeconds:      60,
			NumConcurrentThreads: 20,
		},
		{
			Name:                 "Stress Test - 500+ Sessions",
			NumStudents:          500,
			NumApps:              10,
			MetricsPerStudentSec: 20,
			DurationSeconds:      120,
			NumConcurrentThreads: 50,
		},
		{
			Name:                 "Spike Test - Sudden Load Increase",
			NumStudents:          100,
			NumApps:              5,
			MetricsPerStudentSec: 50,
			DurationSeconds:      30,
			NumConcurrentThreads: 25,
		},
	}
}

// RunLoadTest executes a load test scenario
func RunLoadTest(
	scenario LoadTestScenario,
	metricsService *UsabilityMetricsService,
	perfMetrics *PerformanceMetrics,
) *LoadTestResult {
	result := &LoadTestResult{
		Scenario: scenario,
	}

	ctx := context.Background()
	start := time.Now()

	// Calculate total metrics to generate
	totalMetricsToGenerate := scenario.NumStudents *
		scenario.MetricsPerStudentSec *
		scenario.DurationSeconds

	// Distribution channels
	studentChan := make(chan int, scenario.NumConcurrentThreads)

	// Worker for generating metrics
	var metricsWg sync.WaitGroup

	// Start metric generator workers
	for w := 0; w < scenario.NumConcurrentThreads; w++ {
		metricsWg.Add(1)
		go func(workerID int) {
			defer metricsWg.Done()

			metricsGenerated := 0
			for studentID := range studentChan {
				for app := 0; app < scenario.NumApps; app++ {
					for m := 0; m < scenario.MetricsPerStudentSec; m++ {
						metric := &Metric{
							StudentID:   fmt.Sprintf("student-%d", studentID),
							AppName:     fmt.Sprintf("app-%d", app),
							MetricType:  MetricTypeKeyPress,
							MetricValue: 1.0,
							Timestamp:   time.Now(),
						}

						// Record start time for latency measurement
						latencyStart := time.Now()

						// Submit to service
						if err := metricsService.RecordMetric(ctx, metric); err == nil {
							latency := time.Since(latencyStart)
							perfMetrics.RecordMetricLatency(latency)
							metricsGenerated++
						} else {
							perfMetrics.RecordError()
						}
					}
				}

				// Check duration
				if time.Since(start) > time.Duration(scenario.DurationSeconds)*time.Second {
					break
				}
			}

			atomic.AddInt64(&result.TotalMetricsRecorded, int64(metricsGenerated))
		}(w)
	}

	// Main loop - feed students to workers
	go func() {
		deadline := time.Now().Add(time.Duration(scenario.DurationSeconds) * time.Second)
		for {
			if time.Now().After(deadline) {
				close(studentChan)
				break
			}

			for s := 0; s < scenario.NumStudents; s++ {
				select {
				case studentChan <- s:
				default:
					// Channel full, wait a bit
					time.Sleep(10 * time.Millisecond)
				}
			}

			time.Sleep(time.Second / time.Duration(scenario.MetricsPerStudentSec))
		}
	}()

	// Wait for all workers to finish
	metricsWg.Wait()

	result.DurationActual = time.Since(start)
	result.TotalErrors = atomic.LoadInt64(&perfMetrics.ErrorsEncountered)
	result.TotalFrustrationEvents = atomic.LoadInt64(&perfMetrics.FrustrationEvents)

	// Calculate throughput
	if result.DurationActual > 0 {
		result.ThroughputMetricsSec = float64(result.TotalMetricsRecorded) / result.DurationActual.Seconds()
		result.ThroughputEventsSec = float64(result.TotalFrustrationEvents) / result.DurationActual.Seconds()
	}

	// Determine status
	if result.TotalErrors == 0 && result.ThroughputMetricsSec > float64(totalMetricsToGenerate)/float64(scenario.DurationSeconds)*0.95 {
		result.Status = "PASS"
	} else if result.TotalErrors == 0 {
		result.Status = "PASS (Lower throughput)"
	} else {
		result.Status = "FAIL"
	}

	return result
}

// LoadTestSuite runs multiple load test scenarios
func LoadTestSuite(
	scenarios []LoadTestScenario,
	metricsService *UsabilityMetricsService,
	perfMetrics *PerformanceMetrics,
) []*LoadTestResult {
	results := make([]*LoadTestResult, len(scenarios))

	for i, scenario := range scenarios {
		// Reset metrics between tests
		perfMetrics.Reset()

		results[i] = RunLoadTest(scenario, metricsService, perfMetrics)

		// Cool-down period
		time.Sleep(2 * time.Second)
	}

	return results
}

// PrintLoadTestResults prints load test results in a formatted table
func PrintLoadTestResults(results []*LoadTestResult) {
	fmt.Println("\n" + strings.Repeat("=", 120))
	fmt.Println("LOAD TEST RESULTS SUMMARY")
	fmt.Println(strings.Repeat("=", 120))
	fmt.Printf("%-35s | %10s | %12s | %12s | %10s | %10s | %10s\n",
		"Scenario", "Status", "Metrics/sec", "Events/sec", "Duration", "Errors", "Throughput")
	fmt.Println("-" + strings.Repeat("-", 118))

	for _, result := range results {
		status := result.Status
		if len(status) < 10 {
			status = status + " "[len(status):]
		}

		fmt.Printf("%-35s | %10s | %12.0f | %12.2f | %9.1fs | %10d | ",
			result.Scenario.Name[:35],
			status,
			result.ThroughputMetricsSec,
			result.ThroughputEventsSec,
			result.DurationActual.Seconds(),
			result.TotalErrors,
		)

		// Throughput indicator
		targetThroughput := float64(result.Scenario.NumStudents) *
			float64(result.Scenario.MetricsPerStudentSec) *
			float64(result.Scenario.NumApps)

		percentOfTarget := (result.ThroughputMetricsSec * float64(result.Scenario.DurationSeconds) / targetThroughput) * 100
		fmt.Printf("%6.1f%%", percentOfTarget)

		fmt.Println()
	}

	fmt.Println(strings.Repeat("=", 120) + "\n")
}

// PerformanceAnalysis analyzes load test performance
func PerformanceAnalysis(results []*LoadTestResult) map[string]interface{} {
	analysis := map[string]interface{}{
		"total_scenarios": len(results),
		"passed":          0,
		"failed":          0,
		"avg_throughput":  0.0,
		"max_throughput":  0.0,
		"min_throughput":  0.0,
	}

	var totalThroughput float64
	var maxThroughput float64
	var minThroughput float64 = 999999999.0

	for _, result := range results {
		if result.Status == "PASS" {
			analysis["passed"] = analysis["passed"].(int) + 1
		} else {
			analysis["failed"] = analysis["failed"].(int) + 1
		}

		if result.ThroughputMetricsSec > maxThroughput {
			maxThroughput = result.ThroughputMetricsSec
		}
		if result.ThroughputMetricsSec < minThroughput {
			minThroughput = result.ThroughputMetricsSec
		}

		totalThroughput += result.ThroughputMetricsSec
	}

	if len(results) > 0 {
		analysis["avg_throughput"] = totalThroughput / float64(len(results))
		analysis["max_throughput"] = maxThroughput
		analysis["min_throughput"] = minThroughput
	}

	return analysis
}
