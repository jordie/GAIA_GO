package usability

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

// TestUpdateMetricKeyPress tests updating metrics with keypresses
func TestUpdateMetricKeyPress(t *testing.T) {
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	metric := &Metric{
		StudentID:   "student-1",
		AppName:     "typing",
		MetricType:  MetricTypeKeyPress,
		MetricValue: 1.0,
		Timestamp:   time.Now(),
	}

	aggregator.UpdateMetric(metric)

	metrics := aggregator.GetMetrics("student-1", "typing")
	assert.NotNil(t, metrics)
	assert.Equal(t, "student-1", metrics["student_id"])
	assert.Equal(t, 1, metrics["key_press_count"])
}

// TestUpdateMetricErrorRate tests error rate calculation
func TestUpdateMetricErrorRate(t *testing.T) {
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	// Add 10 keypresses
	for i := 0; i < 10; i++ {
		metric := &Metric{
			StudentID:   "student-1",
			AppName:     "typing",
			MetricType:  MetricTypeKeyPress,
			MetricValue: 1.0,
			Timestamp:   time.Now(),
		}
		aggregator.UpdateMetric(metric)
	}

	// Add 2 errors
	for i := 0; i < 2; i++ {
		metric := &Metric{
			StudentID:   "student-1",
			AppName:     "typing",
			MetricType:  MetricTypeError,
			MetricValue: 1.0,
			Timestamp:   time.Now(),
		}
		aggregator.UpdateMetric(metric)
	}

	metrics := aggregator.GetMetrics("student-1", "typing")
	errorRate := metrics["error_rate"].(float64)

	// 2 errors / 10 keypresses = 20%
	assert.InDelta(t, 20.0, errorRate, 0.1)
}

// TestUpdateMetricBackspaceRate tests backspace rate calculation
func TestUpdateMetricBackspaceRate(t *testing.T) {
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	// Add 10 keypresses
	for i := 0; i < 10; i++ {
		metric := &Metric{
			StudentID:   "student-1",
			AppName:     "typing",
			MetricType:  MetricTypeKeyPress,
			MetricValue: 1.0,
			Timestamp:   time.Now(),
		}
		aggregator.UpdateMetric(metric)
	}

	// Add 3 backspaces
	for i := 0; i < 3; i++ {
		metric := &Metric{
			StudentID:   "student-1",
			AppName:     "typing",
			MetricType:  MetricTypeBackspace,
			MetricValue: 1.0,
			Timestamp:   time.Now(),
		}
		aggregator.UpdateMetric(metric)
	}

	metrics := aggregator.GetMetrics("student-1", "typing")
	backspaceRate := metrics["backspace_rate"].(float64)

	// 3 backspaces / 10 keypresses = 30%
	assert.InDelta(t, 30.0, backspaceRate, 0.1)
}

// TestUpdateMetricHesitation tests hesitation duration tracking
func TestUpdateMetricHesitation(t *testing.T) {
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	metric := &Metric{
		StudentID:   "student-1",
		AppName:     "typing",
		MetricType:  MetricTypeHesitation,
		MetricValue: 45.0, // 45 seconds
		Timestamp:   time.Now(),
	}

	aggregator.UpdateMetric(metric)

	metrics := aggregator.GetMetrics("student-1", "typing")
	hesitation := metrics["current_hesitation_ms"].(int64)

	// Should be approximately 45000 milliseconds
	assert.InDelta(t, 45000, hesitation, 5000)
}

// TestGetStudentMetrics tests retrieving all metrics for a student
func TestGetStudentMetrics(t *testing.T) {
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	// Add metrics for different apps
	for _, app := range []string{"typing", "math"} {
		for i := 0; i < 5; i++ {
			metric := &Metric{
				StudentID:   "student-1",
				AppName:     app,
				MetricType:  MetricTypeKeyPress,
				MetricValue: 1.0,
				Timestamp:   time.Now(),
			}
			aggregator.UpdateMetric(metric)
		}
	}

	metrics := aggregator.GetStudentMetrics("student-1")
	assert.NotNil(t, metrics)
	assert.Equal(t, "student-1", metrics["student_id"])
	assert.NotNil(t, metrics["apps"])
}

// TestGetClassroomMetrics tests retrieving classroom-wide metrics
func TestGetClassroomMetrics(t *testing.T) {
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	// Add metrics for multiple students
	for i := 1; i <= 3; i++ {
		studentID := "student-" + string(rune(48+i))
		for j := 0; j < 5; j++ {
			metric := &Metric{
				StudentID:   studentID,
				AppName:     "typing",
				MetricType:  MetricTypeKeyPress,
				MetricValue: 1.0,
				Timestamp:   time.Now(),
			}
			aggregator.UpdateMetric(metric)
		}
	}

	metrics := aggregator.GetClassroomMetrics("classroom-1", "typing")
	assert.NotNil(t, metrics)
	assert.Equal(t, "classroom-1", metrics["classroom_id"])
	assert.Equal(t, "typing", metrics["app_name"])
}

// TestResetMetrics tests resetting metrics for a student
func TestResetMetrics(t *testing.T) {
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	metric := &Metric{
		StudentID:   "student-1",
		AppName:     "typing",
		MetricType:  MetricTypeKeyPress,
		MetricValue: 1.0,
		Timestamp:   time.Now(),
	}

	aggregator.UpdateMetric(metric)

	// Verify metric exists
	metrics := aggregator.GetMetrics("student-1", "typing")
	assert.NotNil(t, metrics)
	assert.Equal(t, 1, metrics["key_press_count"])

	// Reset
	aggregator.Reset("student-1", "typing")

	// Verify metric is gone - should return no_data response
	metrics = aggregator.GetMetrics("student-1", "typing")
	assert.NotNil(t, metrics)
	noData, ok := metrics["no_data"].(bool)
	assert.True(t, ok && noData)
}

// TestResetAll tests resetting all metrics
func TestResetAll(t *testing.T) {
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	// Add multiple metrics
	for i := 0; i < 5; i++ {
		metric := &Metric{
			StudentID:   "student-1",
			AppName:     "typing",
			MetricType:  MetricTypeKeyPress,
			MetricValue: 1.0,
			Timestamp:   time.Now(),
		}
		aggregator.UpdateMetric(metric)
	}

	assert.Equal(t, 1, aggregator.GetStudentCount())

	aggregator.ResetAll()

	assert.Equal(t, 0, aggregator.GetStudentCount())
}

// TestGetAllMetrics tests retrieving all metrics
func TestGetAllMetrics(t *testing.T) {
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	// Add metrics for multiple students
	for i := 1; i <= 3; i++ {
		studentID := "student-" + string(rune(48+i))
		metric := &Metric{
			StudentID:   studentID,
			AppName:     "typing",
			MetricType:  MetricTypeKeyPress,
			MetricValue: 1.0,
			Timestamp:   time.Now(),
		}
		aggregator.UpdateMetric(metric)
	}

	allMetrics := aggregator.GetAllMetrics()
	assert.Equal(t, 3, len(allMetrics))
}

// TestCompletionRate tests completion rate calculation
func TestCompletionRate(t *testing.T) {
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	// Add 10 keypresses
	for i := 0; i < 10; i++ {
		metric := &Metric{
			StudentID:   "student-1",
			AppName:     "typing",
			MetricType:  MetricTypeKeyPress,
			MetricValue: 1.0,
			Timestamp:   time.Now(),
		}
		aggregator.UpdateMetric(metric)
	}

	// Add 2 completions
	for i := 0; i < 2; i++ {
		metric := &Metric{
			StudentID:   "student-1",
			AppName:     "typing",
			MetricType:  MetricTypeCompletion,
			MetricValue: 1.0,
			Timestamp:   time.Now(),
		}
		aggregator.UpdateMetric(metric)
	}

	metrics := aggregator.GetMetrics("student-1", "typing")
	completionRate := metrics["completion_rate"].(float64)

	// 2 completions / 10 keypresses = 0.2
	assert.InDelta(t, 0.2, completionRate, 0.01)
}
