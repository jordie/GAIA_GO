//go:build e2e
// +build e2e

package fixtures

import (
	"context"
	"fmt"
	"math/rand"
	"time"
)

// TestMetric represents a single test metric
type TestMetric struct {
	StudentID   string
	AppName     string
	MetricType  string
	MetricValue float64
	Timestamp   time.Time
	Metadata    map[string]interface{}
}

// MetricsGenerator generates realistic metric streams for testing
type MetricsGenerator struct {
	rand *rand.Rand
}

// NewMetricsGenerator creates a new metrics generator
func NewMetricsGenerator() *MetricsGenerator {
	return &MetricsGenerator{
		rand: rand.New(rand.NewSource(time.Now().UnixNano())),
	}
}

// MetricStream generates a realistic stream of metrics over a duration
func (g *MetricsGenerator) MetricStream(studentID, appName string, duration time.Duration, metricsPerSecond int) []*TestMetric {
	metrics := make([]*TestMetric, 0)

	startTime := time.Now()
	endTime := startTime.Add(duration)
	interval := time.Second / time.Duration(metricsPerSecond)

	currentTime := startTime
	metricTypes := []string{"keypress", "backspace", "pause", "error", "response_time", "accuracy"}

	for currentTime.Before(endTime) {
		metricType := metricTypes[g.rand.Intn(len(metricTypes))]

		metric := &TestMetric{
			StudentID:   studentID,
			AppName:     appName,
			MetricType:  metricType,
			MetricValue: g.generateMetricValue(metricType),
			Timestamp:   currentTime,
			Metadata: map[string]interface{}{
				"focus_level": g.rand.Intn(10),
				"session_id":  fmt.Sprintf("session-%s", studentID),
			},
		}

		metrics = append(metrics, metric)
		currentTime = currentTime.Add(interval)
	}

	return metrics
}

// FrustrationMetricPattern generates metrics that trigger frustration detection
func (g *MetricsGenerator) FrustrationMetricPattern(studentID, appName, patternType string) []*TestMetric {
	metrics := make([]*TestMetric, 0)
	now := time.Now()

	switch patternType {
	case "excessive_errors":
		// 5+ errors within 1 minute → critical frustration
		for i := 0; i < 6; i++ {
			metric := &TestMetric{
				StudentID:   studentID,
				AppName:     appName,
				MetricType:  "error",
				MetricValue: 1.0,
				Timestamp:   now.Add(-time.Duration(i*10) * time.Second),
				Metadata: map[string]interface{}{
					"error_type": "incorrect_answer",
					"session_id": fmt.Sprintf("session-%s", studentID),
				},
			}
			metrics = append(metrics, metric)
		}

	case "repeated_corrections":
		// 20+ backspaces within 1 minute → high frustration
		for i := 0; i < 25; i++ {
			metric := &TestMetric{
				StudentID:   studentID,
				AppName:     appName,
				MetricType:  "backspace",
				MetricValue: 1.0,
				Timestamp:   now.Add(-time.Duration(i*2) * time.Second),
				Metadata: map[string]interface{}{
					"session_id": fmt.Sprintf("session-%s", studentID),
				},
			}
			metrics = append(metrics, metric)
		}

	case "prolonged_hesitation":
		// 30+ second pause → medium frustration
		metric := &TestMetric{
			StudentID:   studentID,
			AppName:     appName,
			MetricType:  "pause",
			MetricValue: 35.0,
			Timestamp:   now,
			Metadata: map[string]interface{}{
				"session_id": fmt.Sprintf("session-%s", studentID),
			},
		}
		metrics = append(metrics, metric)

	case "performance_degradation":
		// Accuracy declining over time
		accuracyValues := []float64{0.95, 0.90, 0.80, 0.70, 0.60, 0.50}
		for i, accuracy := range accuracyValues {
			metric := &TestMetric{
				StudentID:   studentID,
				AppName:     appName,
				MetricType:  "accuracy_percentage",
				MetricValue: accuracy * 100,
				Timestamp:   now.Add(-time.Duration((len(accuracyValues)-i-1)*5) * time.Second),
				Metadata: map[string]interface{}{
					"session_id": fmt.Sprintf("session-%s", studentID),
				},
			}
			metrics = append(metrics, metric)
		}
	}

	return metrics
}

// NormalMetricPattern generates normal student interaction metrics (no frustration)
func (g *MetricsGenerator) NormalMetricPattern(studentID, appName string) []*TestMetric {
	metrics := make([]*TestMetric, 0)
	now := time.Now()

	// Normal typing pattern: mix of keypresses, occasional backspaces, good accuracy
	metricTypes := []struct {
		mType string
		count int
	}{
		{"keypress", 20},
		{"backspace", 2},
		{"accuracy_percentage", 1},
		{"response_time", 1},
	}

	for _, mt := range metricTypes {
		for i := 0; i < mt.count; i++ {
			metric := &TestMetric{
				StudentID:   studentID,
				AppName:     appName,
				MetricType:  mt.mType,
				MetricValue: g.generateNormalMetricValue(mt.mType),
				Timestamp:   now.Add(-time.Duration(i*100) * time.Millisecond),
				Metadata: map[string]interface{}{
					"focus_level": 8 + g.rand.Intn(2), // 8-9 out of 10
					"session_id":  fmt.Sprintf("session-%s", studentID),
				},
			}
			metrics = append(metrics, metric)
		}
	}

	return metrics
}

// SimulateStudentActivity simulates a student using an app over time (blocking)
func (g *MetricsGenerator) SimulateStudentActivity(ctx context.Context, studentID, appName string, duration time.Duration) <-chan *TestMetric {
	metricsChan := make(chan *TestMetric, 100)

	go func() {
		defer close(metricsChan)

		startTime := time.Now()
		endTime := startTime.Add(duration)

		metricsPerSecond := 5 + g.rand.Intn(10) // 5-14 metrics per second

		for {
			select {
			case <-ctx.Done():
				return
			default:
				if time.Now().After(endTime) {
					return
				}

				// Generate random metric
				metric := &TestMetric{
					StudentID:   studentID,
					AppName:     appName,
					MetricType:  []string{"keypress", "backspace", "pause", "accuracy_percentage"}[g.rand.Intn(4)],
					MetricValue: g.generateNormalMetricValue("mixed"),
					Timestamp:   time.Now(),
					Metadata: map[string]interface{}{
						"focus_level": g.rand.Intn(10),
						"session_id":  fmt.Sprintf("session-%s", studentID),
					},
				}

				select {
				case metricsChan <- metric:
				case <-ctx.Done():
					return
				}

				// Sleep based on metrics per second
				time.Sleep(time.Second / time.Duration(metricsPerSecond))
			}
		}
	}()

	return metricsChan
}

// Helper function to generate realistic metric values
func (g *MetricsGenerator) generateMetricValue(metricType string) float64 {
	switch metricType {
	case "keypress":
		return 1.0 // Count

	case "backspace":
		return 1.0 // Count

	case "pause":
		return float64(g.rand.Intn(30)) // 0-30 seconds

	case "error":
		return 1.0 // Binary

	case "response_time":
		return float64(500 + g.rand.Intn(1500)) // 500-2000 ms

	case "accuracy":
		return 50.0 + float64(g.rand.Intn(50)) // 50-100%

	default:
		return float64(g.rand.Intn(100))
	}
}

// Helper function to generate normal metric values (no frustration)
func (g *MetricsGenerator) generateNormalMetricValue(metricType string) float64 {
	switch metricType {
	case "keypress":
		return 1.0

	case "backspace":
		return float64(g.rand.Intn(3)) // 0-2 backspaces

	case "accuracy_percentage":
		return 85.0 + float64(g.rand.Intn(15)) // 85-100%

	case "response_time":
		return float64(800 + g.rand.Intn(400)) // 800-1200 ms

	default:
		return 75.0 + float64(g.rand.Intn(25)) // 75-100%
	}
}

// TaskFixtures provides factory methods for distributed task test data
type TaskFixtures struct{}

// NewTestTask creates a single test task
func NewTestTask(taskType string, priority int, data map[string]interface{}) map[string]interface{} {
	return map[string]interface{}{
		"task_type":      taskType,
		"priority":       priority,
		"task_data":      data,
		"status":         "pending",
		"retry_count":    0,
		"max_retries":    3,
		"created_at":     time.Now(),
	}
}

// TaskBatch creates multiple tasks with varying priorities
func TaskBatch(count int) []map[string]interface{} {
	tasks := make([]map[string]interface{}, 0)
	priorities := []int{1, 1, 1, 5, 5, 10}

	for i := 0; i < count; i++ {
		priority := priorities[i%len(priorities)]
		task := NewTestTask(
			"grading",
			priority,
			map[string]interface{}{
				"student_id": fmt.Sprintf("student-%d", i),
				"quiz_id":    fmt.Sprintf("quiz-%d", i/10),
			},
		)
		tasks = append(tasks, task)
	}

	return tasks
}

// NewIdempotentTask creates a task with a specific idempotency key
func NewIdempotentTask(idempotencyKey string, data map[string]interface{}) map[string]interface{} {
	return map[string]interface{}{
		"idempotency_key": idempotencyKey,
		"task_type":       "analytics",
		"priority":        5,
		"task_data":       data,
		"status":          "pending",
		"retry_count":     0,
		"max_retries":     3,
		"created_at":      time.Now(),
	}
}
