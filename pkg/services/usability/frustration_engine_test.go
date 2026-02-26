package usability

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

// TestAnalyzeMetricKeyPress tests analyzing keypress metrics
func TestAnalyzeMetricKeyPress(t *testing.T) {
	engine := NewFrustrationDetectionEngine(DefaultThresholds())

	metric := &Metric{
		StudentID:   "student-1",
		AppName:     "typing",
		MetricType:  MetricTypeKeyPress,
		MetricValue: 1.0,
		Timestamp:   time.Now(),
	}

	event := engine.AnalyzeMetric(metric)

	// Low frustration should not trigger event
	assert.Nil(t, event)
}

// TestAnalyzeMetricErrors tests analyzing error metrics
func TestAnalyzeMetricErrors(t *testing.T) {
	engine := NewFrustrationDetectionEngine(DefaultThresholds())

	// Add errors to trigger high frustration
	for i := 0; i < 4; i++ {
		metric := &Metric{
			StudentID:   "student-1",
			AppName:     "typing",
			MetricType:  MetricTypeError,
			MetricValue: 1.0,
			Timestamp:   time.Now(),
		}
		event := engine.AnalyzeMetric(metric)

		// Should trigger event after 3rd error
		if i >= 2 {
			assert.NotNil(t, event)
			if event != nil {
				assert.Equal(t, "high", event.Severity)
			}
		}
	}
}

// TestAnalyzeMetricCriticalErrors tests critical error threshold
func TestAnalyzeMetricCriticalErrors(t *testing.T) {
	engine := NewFrustrationDetectionEngine(DefaultThresholds())

	// Add 5 errors to trigger critical frustration
	for i := 0; i < 5; i++ {
		metric := &Metric{
			StudentID:   "student-1",
			AppName:     "typing",
			MetricType:  MetricTypeError,
			MetricValue: 1.0,
			Timestamp:   time.Now(),
		}
		event := engine.AnalyzeMetric(metric)

		// Should trigger critical event at 5th error
		if i == 4 {
			assert.NotNil(t, event)
			assert.Equal(t, "critical", event.Severity)
			assert.Greater(t, event.ConfidenceScore, 0.9)
		}
	}
}

// TestAnalyzeMetricBackspaces tests backspace metrics
func TestAnalyzeMetricBackspaces(t *testing.T) {
	engine := NewFrustrationDetectionEngine(DefaultThresholds())

	// Add backspaces to trigger frustration
	for i := 0; i < 11; i++ {
		metric := &Metric{
			StudentID:   "student-1",
			AppName:     "typing",
			MetricType:  MetricTypeBackspace,
			MetricValue: 1.0,
			Timestamp:   time.Now(),
		}
		event := engine.AnalyzeMetric(metric)

		// Should trigger event after 10th backspace
		if i >= 9 {
			assert.NotNil(t, event)
		}
	}
}

// TestAnalyzeMetricHesitation tests hesitation metrics
func TestAnalyzeMetricHesitation(t *testing.T) {
	engine := NewFrustrationDetectionEngine(DefaultThresholds())

	metric := &Metric{
		StudentID:   "student-1",
		AppName:     "typing",
		MetricType:  MetricTypeHesitation,
		MetricValue: 45.0, // 45 seconds in milliseconds / 1000
		Timestamp:   time.Now(),
	}

	event := engine.AnalyzeMetric(metric)

	// Should trigger event for long hesitation
	assert.NotNil(t, event)
	if event != nil {
		assert.Equal(t, "prolonged_hesitation", event.EventType)
	}
}

// TestGetPatternStats tests retrieving pattern statistics
func TestGetPatternStats(t *testing.T) {
	engine := NewFrustrationDetectionEngine(DefaultThresholds())

	studentID := "student-1"
	appName := "typing"

	// Record some metrics
	for i := 0; i < 3; i++ {
		metric := &Metric{
			StudentID:   studentID,
			AppName:     appName,
			MetricType:  MetricTypeKeyPress,
			MetricValue: 1.0,
			Timestamp:   time.Now(),
		}
		engine.AnalyzeMetric(metric)
	}

	stats := engine.GetPatternStats(studentID, appName)

	assert.NotNil(t, stats)
	assert.Equal(t, studentID, stats["student_id"])
	assert.Equal(t, appName, stats["app_name"])
	assert.Equal(t, 3, stats["key_press_count"])
}

// TestResetPattern tests resetting frustration patterns
func TestResetPattern(t *testing.T) {
	engine := NewFrustrationDetectionEngine(DefaultThresholds())

	studentID := "student-1"
	appName := "typing"

	// Record metric
	metric := &Metric{
		StudentID:   studentID,
		AppName:     appName,
		MetricType:  MetricTypeKeyPress,
		MetricValue: 1.0,
		Timestamp:   time.Now(),
	}
	engine.AnalyzeMetric(metric)

	// Verify pattern exists
	stats := engine.GetPatternStats(studentID, appName)
	assert.NotNil(t, stats)

	// Reset
	engine.Reset(studentID, appName)

	// Verify pattern is gone
	stats = engine.GetPatternStats(studentID, appName)
	assert.Nil(t, stats)
}

// TestOnFrustrationDetected tests event handler registration
func TestOnFrustrationDetected(t *testing.T) {
	engine := NewFrustrationDetectionEngine(DefaultThresholds())

	handlerCalled := false
	handler := func(event *FrustrationEvent) {
		handlerCalled = true
	}

	engine.OnFrustrationDetected(handler)

	// Trigger frustration
	for i := 0; i < 5; i++ {
		metric := &Metric{
			StudentID:   "student-1",
			AppName:     "typing",
			MetricType:  MetricTypeError,
			MetricValue: 1.0,
			Timestamp:   time.Now(),
		}
		engine.AnalyzeMetric(metric)
	}

	// Handler should have been called
	time.Sleep(100 * time.Millisecond) // Allow goroutine to execute
	assert.True(t, handlerCalled)
}

// TestConfidenceScoreRange tests that confidence scores stay within 0-1
func TestConfidenceScoreRange(t *testing.T) {
	engine := NewFrustrationDetectionEngine(DefaultThresholds())

	// Create a frustration event
	for i := 0; i < 5; i++ {
		metric := &Metric{
			StudentID:   "student-1",
			AppName:     "typing",
			MetricType:  MetricTypeError,
			MetricValue: 1.0,
			Timestamp:   time.Now(),
		}
		event := engine.AnalyzeMetric(metric)

		if event != nil {
			assert.GreaterOrEqual(t, event.ConfidenceScore, 0.0)
			assert.LessOrEqual(t, event.ConfidenceScore, 1.0)
		}
	}
}
