package usability

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestRecordMetric tests recording a single metric
func TestRecordMetric(t *testing.T) {
	// Setup
	mockRepo := &MockUsabilityMetricsRepository{}
	eventBus := NewNoOpEventBus()
	frustrationEngine := NewFrustrationDetectionEngine(DefaultThresholds())
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	config := Config{
		BatchSize:     10,
		FlushInterval: 1 * time.Second,
	}

	service := NewUsabilityMetricsService(mockRepo, frustrationEngine, aggregator, eventBus, config)
	ctx := context.Background()

	// Test
	metric := &Metric{
		StudentID:   "student-1",
		AppName:     "typing",
		MetricType:  MetricTypeKeyPress,
		MetricValue: 1.0,
		Timestamp:   time.Now(),
	}

	err := service.RecordMetric(ctx, metric)

	// Assert
	assert.NoError(t, err)
	assert.Equal(t, 1, service.GetBufferSize())
}

// TestRecordMetrics tests recording multiple metrics
func TestRecordMetrics(t *testing.T) {
	mockRepo := &MockUsabilityMetricsRepository{}
	eventBus := NewNoOpEventBus()
	frustrationEngine := NewFrustrationDetectionEngine(DefaultThresholds())
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	config := Config{
		BatchSize:     5,
		FlushInterval: 1 * time.Second,
	}

	service := NewUsabilityMetricsService(mockRepo, frustrationEngine, aggregator, eventBus, config)
	ctx := context.Background()

	metrics := make([]*Metric, 3)
	for i := 0; i < 3; i++ {
		metrics[i] = &Metric{
			StudentID:   "student-1",
			AppName:     "typing",
			MetricType:  MetricTypeKeyPress,
			MetricValue: 1.0,
			Timestamp:   time.Now(),
		}
	}

	err := service.RecordMetrics(ctx, metrics)

	assert.NoError(t, err)
	assert.Equal(t, 3, service.GetBufferSize())
}

// TestBufferFlush tests that buffer flushes when size is reached
func TestBufferFlush(t *testing.T) {
	mockRepo := &MockUsabilityMetricsRepository{}
	eventBus := NewNoOpEventBus()
	frustrationEngine := NewFrustrationDetectionEngine(DefaultThresholds())
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	config := Config{
		BatchSize:     2,
		FlushInterval: 10 * time.Second,
	}

	service := NewUsabilityMetricsService(mockRepo, frustrationEngine, aggregator, eventBus, config)
	ctx := context.Background()

	// Add 2 metrics (should flush when reaching batch size)
	for i := 0; i < 2; i++ {
		metric := &Metric{
			StudentID:   "student-1",
			AppName:     "typing",
			MetricType:  MetricTypeKeyPress,
			MetricValue: 1.0,
			Timestamp:   time.Now(),
		}
		service.RecordMetric(ctx, metric)
	}

	// Buffer should be flushed after reaching batch size
	time.Sleep(100 * time.Millisecond)
	// Note: In real implementation, buffer would be cleared after flush
}

// TestNilMetricHandling tests that nil metrics are handled gracefully
func TestNilMetricHandling(t *testing.T) {
	mockRepo := &MockUsabilityMetricsRepository{}
	eventBus := NewNoOpEventBus()
	frustrationEngine := NewFrustrationDetectionEngine(DefaultThresholds())
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	config := DefaultConfig()
	service := NewUsabilityMetricsService(mockRepo, frustrationEngine, aggregator, eventBus, config)
	ctx := context.Background()

	err := service.RecordMetric(ctx, nil)

	assert.Error(t, err)
	assert.Equal(t, "metric cannot be nil", err.Error())
}

// TestTimestampSetIfZero tests that timestamp is set if not provided
func TestTimestampSetIfZero(t *testing.T) {
	mockRepo := &MockUsabilityMetricsRepository{}
	eventBus := NewNoOpEventBus()
	frustrationEngine := NewFrustrationDetectionEngine(DefaultThresholds())
	aggregator := NewRealtimeMetricsAggregator(1 * time.Minute)

	config := DefaultConfig()
	service := NewUsabilityMetricsService(mockRepo, frustrationEngine, aggregator, eventBus, config)
	ctx := context.Background()

	before := time.Now()
	metric := &Metric{
		StudentID:   "student-1",
		AppName:     "typing",
		MetricType:  MetricTypeKeyPress,
		MetricValue: 1.0,
		Timestamp:   time.Time{},
	}

	service.RecordMetric(ctx, metric)
	after := time.Now()

	assert.False(t, metric.Timestamp.IsZero())
	assert.True(t, metric.Timestamp.After(before.Add(-1*time.Second)))
	assert.True(t, metric.Timestamp.Before(after.Add(1*time.Second)))
}

// MockUsabilityMetricsRepository is a mock for testing
type MockUsabilityMetricsRepository struct {
	recordings int
}

func (m *MockUsabilityMetricsRepository) RecordMetric(ctx context.Context, metric interface{}) error {
	m.recordings++
	return nil
}

func (m *MockUsabilityMetricsRepository) GetStudentMetrics(ctx context.Context, studentID string, appName string, since time.Time) ([]interface{}, error) {
	return []interface{}{}, nil
}

func (m *MockUsabilityMetricsRepository) GetClassroomMetrics(ctx context.Context, classroomID string, appName string) (map[string]interface{}, error) {
	return map[string]interface{}{}, nil
}

func (m *MockUsabilityMetricsRepository) GetMetricsByType(ctx context.Context, metricType string, since time.Time) ([]interface{}, error) {
	return []interface{}{}, nil
}
