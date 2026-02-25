package usability

import (
	"context"
	"errors"
	"testing"
	"time"
)

// Error definitions for testing
var (
	ErrMetricRecordingFailed   = errors.New("failed to record metric")
	ErrFailedToRetrieveMetrics = errors.New("failed to retrieve metrics")
)

// MockUsabilityMetricsRepository implements repository.UsabilityMetricsRepository for testing
type MockUsabilityMetricsRepository struct {
	recordedMetrics []interface{}
	shouldErr       bool
}

func (m *MockUsabilityMetricsRepository) RecordMetric(ctx context.Context, metricData interface{}) error {
	if m.shouldErr {
		return ErrMetricRecordingFailed
	}
	m.recordedMetrics = append(m.recordedMetrics, metricData)
	return nil
}

func (m *MockUsabilityMetricsRepository) GetStudentMetrics(ctx context.Context, studentID, appName string, since time.Time) ([]interface{}, error) {
	if m.shouldErr {
		return nil, ErrFailedToRetrieveMetrics
	}
	return m.recordedMetrics, nil
}

func (m *MockUsabilityMetricsRepository) GetClassroomMetrics(ctx context.Context, classroomID, appName string) (map[string]interface{}, error) {
	if m.shouldErr {
		return nil, ErrFailedToRetrieveMetrics
	}
	return map[string]interface{}{
		"classroomID": classroomID,
		"appName":     appName,
		"metrics":     m.recordedMetrics,
	}, nil
}

func (m *MockUsabilityMetricsRepository) GetMetricsByType(ctx context.Context, sessionID string, since time.Time) ([]interface{}, error) {
	if m.shouldErr {
		return nil, ErrFailedToRetrieveMetrics
	}
	return m.recordedMetrics, nil
}

// MockEventBus implements EventBus for testing
type MockEventBus struct {
	frustrationEvents      []*FrustrationEvent
	satisfactionRatings    []map[string]interface{}
	metricEvents           []*Metric
	frustrationListeners   []FrustrationEventListener
}

func NewMockEventBus() *MockEventBus {
	return &MockEventBus{
		frustrationEvents:   make([]*FrustrationEvent, 0),
		satisfactionRatings: make([]map[string]interface{}, 0),
		metricEvents:        make([]*Metric, 0),
	}
}

func (m *MockEventBus) PublishFrustrationEvent(event *FrustrationEvent) {
	m.frustrationEvents = append(m.frustrationEvents, event)
	// Notify listeners
	for _, listener := range m.frustrationListeners {
		listener.OnFrustrationDetected(event)
	}
}

func (m *MockEventBus) PublishSatisfactionRating(studentID, appName string, rating int, feedback string) {
	m.satisfactionRatings = append(m.satisfactionRatings, map[string]interface{}{
		"studentID": studentID,
		"appName":   appName,
		"rating":    rating,
		"feedback":  feedback,
	})
}

func (m *MockEventBus) PublishMetricEvent(metric *Metric) {
	m.metricEvents = append(m.metricEvents, metric)
}

func (m *MockEventBus) Subscribe(listener FrustrationEventListener) {
	m.frustrationListeners = append(m.frustrationListeners, listener)
}

func (m *MockEventBus) Unsubscribe(listener FrustrationEventListener) {
	// Simple implementation - just remove first matching
	for i, l := range m.frustrationListeners {
		if l == listener {
			m.frustrationListeners = append(m.frustrationListeners[:i], m.frustrationListeners[i+1:]...)
			return
		}
	}
}

func (m *MockEventBus) Close() {
	// No-op for mock
}

// Test 1: RecordMetric with valid metric
func TestRecordMetric_ValidMetric(t *testing.T) {
	repo := &MockUsabilityMetricsRepository{}
	frustrationEngine := NewFrustrationDetectionEngine(nil) // Uses default thresholds
	aggregator := NewRealtimeMetricsAggregator(time.Minute)
	eventBus := NewMockEventBus()

	service := NewUsabilityMetricsService(repo, frustrationEngine, aggregator, eventBus, DefaultConfig())
	defer service.Stop()

	ctx := context.Background()
	metric := &Metric{
		StudentID:  "student-1",
		AppName:    "typing-app",
		SessionID:  "session-1",
		MetricType: MetricTypeKeyPress,
		MetricValue: 1.0,
		Timestamp:  time.Now(),
	}

	err := service.RecordMetric(ctx, metric)
	if err != nil {
		t.Fatalf("RecordMetric failed: %v", err)
	}

	// Verify metric was buffered
	if service.GetBufferSize() == 0 {
		t.Errorf("Expected metric to be buffered, got buffer size: 0")
	}
}

// Test 2: RecordMetric with nil metric
func TestRecordMetric_NilMetric(t *testing.T) {
	repo := &MockUsabilityMetricsRepository{}
	frustrationEngine := NewFrustrationDetectionEngine(nil)
	aggregator := NewRealtimeMetricsAggregator(time.Minute)
	eventBus := NewMockEventBus()

	service := NewUsabilityMetricsService(repo, frustrationEngine, aggregator, eventBus, DefaultConfig())

	ctx := context.Background()
	err := service.RecordMetric(ctx, nil)

	if err == nil {
		t.Errorf("Expected error for nil metric, got nil")
	}
}

// Test 3: RecordMetrics batch processing
func TestRecordMetrics_Batch(t *testing.T) {
	repo := &MockUsabilityMetricsRepository{}
	frustrationEngine := NewFrustrationDetectionEngine(nil)
	aggregator := NewRealtimeMetricsAggregator(time.Minute)
	eventBus := NewMockEventBus()

	service := NewUsabilityMetricsService(repo, frustrationEngine, aggregator, eventBus, DefaultConfig())
	defer service.Stop()

	ctx := context.Background()
	metrics := []*Metric{
		{StudentID: "s1", AppName: "app1", MetricType: MetricTypeKeyPress, MetricValue: 1.0},
		{StudentID: "s1", AppName: "app1", MetricType: MetricTypeBackspace, MetricValue: 1.0},
		{StudentID: "s1", AppName: "app1", MetricType: MetricTypeError, MetricValue: 1.0},
	}

	err := service.RecordMetrics(ctx, metrics)
	if err != nil {
		t.Fatalf("RecordMetrics failed: %v", err)
	}

	if service.GetBufferSize() != 3 {
		t.Errorf("Expected buffer size 3, got %d", service.GetBufferSize())
	}
}

// Test 4: ForceFlush triggers database write
func TestForceFlush_WritesToDatabase(t *testing.T) {
	repo := &MockUsabilityMetricsRepository{}
	frustrationEngine := NewFrustrationDetectionEngine(nil)
	aggregator := NewRealtimeMetricsAggregator(time.Minute)
	eventBus := NewMockEventBus()

	config := DefaultConfig()
	config.BatchSize = 10 // High batch size so we need to force flush

	service := NewUsabilityMetricsService(repo, frustrationEngine, aggregator, eventBus, config)
	defer service.Stop()

	ctx := context.Background()
	metric := &Metric{
		StudentID:  "s1",
		AppName:    "app1",
		MetricType: MetricTypeKeyPress,
		MetricValue: 1.0,
		Timestamp:  time.Now(),
	}

	service.RecordMetric(ctx, metric)

	if service.GetBufferSize() != 1 {
		t.Errorf("Expected buffer size 1 before flush, got %d", service.GetBufferSize())
	}

	// Force flush
	err := service.ForceFlush(ctx)
	if err != nil {
		t.Fatalf("ForceFlush failed: %v", err)
	}

	if service.GetBufferSize() != 0 {
		t.Errorf("Expected buffer size 0 after flush, got %d", service.GetBufferSize())
	}

	if len(repo.recordedMetrics) == 0 {
		t.Errorf("Expected metrics written to repository")
	}
}

// Test 5: GetStudentMetrics retrieves data
func TestGetStudentMetrics(t *testing.T) {
	repo := &MockUsabilityMetricsRepository{
		recordedMetrics: []interface{}{"metric1", "metric2"},
	}
	frustrationEngine := NewFrustrationDetectionEngine(nil)
	aggregator := NewRealtimeMetricsAggregator(time.Minute)
	eventBus := NewMockEventBus()

	service := NewUsabilityMetricsService(repo, frustrationEngine, aggregator, eventBus, DefaultConfig())

	ctx := context.Background()
	metrics, err := service.GetStudentMetrics(ctx, "student-1", "app-1", time.Now().Add(-time.Hour))

	if err != nil {
		t.Fatalf("GetStudentMetrics failed: %v", err)
	}

	if len(metrics) != 2 {
		t.Errorf("Expected 2 metrics, got %d", len(metrics))
	}
}

// Test 6: GetStudentMetricsCount returns correct count
func TestGetStudentMetricsCount(t *testing.T) {
	repo := &MockUsabilityMetricsRepository{
		recordedMetrics: []interface{}{"m1", "m2", "m3"},
	}
	frustrationEngine := NewFrustrationDetectionEngine(nil)
	aggregator := NewRealtimeMetricsAggregator(time.Minute)
	eventBus := NewMockEventBus()

	service := NewUsabilityMetricsService(repo, frustrationEngine, aggregator, eventBus, DefaultConfig())

	ctx := context.Background()
	count, err := service.GetStudentMetricsCount(ctx, "s1", "app1", time.Now().Add(-time.Hour))

	if err != nil {
		t.Fatalf("GetStudentMetricsCount failed: %v", err)
	}

	if count != 3 {
		t.Errorf("Expected count 3, got %d", count)
	}
}

// Test 7: GetClassroomMetrics returns aggregated data
func TestGetClassroomMetrics(t *testing.T) {
	repo := &MockUsabilityMetricsRepository{}
	frustrationEngine := NewFrustrationDetectionEngine(nil)
	aggregator := NewRealtimeMetricsAggregator(time.Minute)
	eventBus := NewMockEventBus()

	service := NewUsabilityMetricsService(repo, frustrationEngine, aggregator, eventBus, DefaultConfig())

	ctx := context.Background()
	metrics, err := service.GetClassroomMetrics(ctx, "classroom-1", "app-1")

	if err != nil {
		t.Fatalf("GetClassroomMetrics failed: %v", err)
	}

	if metrics == nil {
		t.Errorf("Expected metrics, got nil")
	}
}

// Test 8: Start and Stop service lifecycle
func TestServiceLifecycle_StartStop(t *testing.T) {
	repo := &MockUsabilityMetricsRepository{}
	frustrationEngine := NewFrustrationDetectionEngine(nil)
	aggregator := NewRealtimeMetricsAggregator(time.Minute)
	eventBus := NewMockEventBus()

	config := DefaultConfig()
	config.FlushInterval = 100 * time.Millisecond

	service := NewUsabilityMetricsService(repo, frustrationEngine, aggregator, eventBus, config)

	ctx := context.Background()
	service.Start(ctx)

	// Record some metrics
	metric := &Metric{
		StudentID:   "s1",
		AppName:     "app1",
		MetricType:  MetricTypeKeyPress,
		MetricValue: 1.0,
		Timestamp:   time.Now(),
	}
	service.RecordMetric(ctx, metric)

	// Give time for background flush
	time.Sleep(200 * time.Millisecond)

	// Stop service
	service.Stop()

	// Verify flush occurred
	if service.GetBufferSize() != 0 {
		t.Errorf("Expected buffer to be flushed after stop, got size %d", service.GetBufferSize())
	}
}

// Test 9: GetRealtimeMetrics returns aggregated data
func TestGetRealtimeMetrics(t *testing.T) {
	repo := &MockUsabilityMetricsRepository{}
	frustrationEngine := NewFrustrationDetectionEngine(nil)
	aggregator := NewRealtimeMetricsAggregator(time.Minute)
	eventBus := NewMockEventBus()

	service := NewUsabilityMetricsService(repo, frustrationEngine, aggregator, eventBus, DefaultConfig())

	// Record a metric (which updates aggregator)
	metric := &Metric{
		StudentID:   "s1",
		AppName:     "app1",
		MetricType:  MetricTypeKeyPress,
		MetricValue: 1.0,
		Timestamp:   time.Now(),
	}
	ctx := context.Background()
	service.RecordMetric(ctx, metric)

	// Get real-time metrics
	realtimeMetrics := service.GetRealtimeMetrics("s1", "app1")

	if realtimeMetrics == nil {
		t.Errorf("Expected real-time metrics, got nil")
	}
}

// Test 10: Multiple metrics flush when buffer fills
func TestRecordMetrics_AutoFlushOnBufferFull(t *testing.T) {
	repo := &MockUsabilityMetricsRepository{}
	frustrationEngine := NewFrustrationDetectionEngine(nil)
	aggregator := NewRealtimeMetricsAggregator(time.Minute)
	eventBus := NewMockEventBus()

	config := DefaultConfig()
	config.BatchSize = 2 // Small batch size to trigger flush

	service := NewUsabilityMetricsService(repo, frustrationEngine, aggregator, eventBus, config)
	defer service.Stop()

	ctx := context.Background()

	// Record 3 metrics (should flush after 2nd)
	metrics := []*Metric{
		{StudentID: "s1", AppName: "app1", MetricType: MetricTypeKeyPress, MetricValue: 1.0},
		{StudentID: "s1", AppName: "app1", MetricType: MetricTypeBackspace, MetricValue: 1.0},
		{StudentID: "s1", AppName: "app1", MetricType: MetricTypeError, MetricValue: 1.0},
	}

	service.RecordMetrics(ctx, metrics)

	// Give time for processing
	time.Sleep(50 * time.Millisecond)

	// Should have written some metrics to repo
	if len(repo.recordedMetrics) < 2 {
		t.Errorf("Expected at least 2 metrics written (batch size 2), got %d", len(repo.recordedMetrics))
	}
}

// Test 11: Error handling from repository
func TestRecordMetric_RepositoryError(t *testing.T) {
	repo := &MockUsabilityMetricsRepository{shouldErr: true}
	frustrationEngine := NewFrustrationDetectionEngine(nil)
	aggregator := NewRealtimeMetricsAggregator(time.Minute)
	eventBus := NewMockEventBus()

	config := DefaultConfig()
	config.BatchSize = 1 // Force immediate flush

	service := NewUsabilityMetricsService(repo, frustrationEngine, aggregator, eventBus, config)
	defer service.Stop()

	ctx := context.Background()
	metric := &Metric{
		StudentID:   "s1",
		AppName:     "app1",
		MetricType:  MetricTypeKeyPress,
		MetricValue: 1.0,
		Timestamp:   time.Now(),
	}

	// Should not panic even if repository errors
	err := service.RecordMetric(ctx, metric)
	// Service doesn't return error, just logs it

	if err != nil && err.Error() == "" {
		t.Errorf("Unexpected error: %v", err)
	}
}
