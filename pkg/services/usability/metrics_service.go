// Package usability provides services for real-time usability monitoring
// and frustration detection for education applications.
package usability

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/jgirmay/GAIA_GO/pkg/repository"
)

// MetricType defines the type of metric being recorded
type MetricType string

const (
	MetricTypeKeyPress      MetricType = "keypress"
	MetricTypeBackspace     MetricType = "backspace"
	MetricTypeError         MetricType = "error"
	MetricTypeHesitation    MetricType = "hesitation"
	MetricTypeCompletion    MetricType = "completion"
	MetricTypeFocus         MetricType = "focus"
	MetricTypeBlur          MetricType = "blur"
	MetricTypeScrolling     MetricType = "scrolling"
	MetricTypeMouseMovement MetricType = "mouse_movement"
)

// Metric represents a single usability metric
type Metric struct {
	StudentID    string                 `json:"student_id"`
	AppName      string                 `json:"app_name"`
	SessionID    string                 `json:"session_id"`
	MetricType   MetricType             `json:"metric_type"`
	MetricValue  float64                `json:"metric_value"`
	Metadata     map[string]interface{} `json:"metadata,omitempty"`
	Timestamp    time.Time              `json:"timestamp"`
}

// UsabilityMetricsService provides metrics collection and storage
type UsabilityMetricsService struct {
	mu                 sync.RWMutex
	metricsRepo        repository.UsabilityMetricsRepository
	frustrationEngine  *FrustrationDetectionEngine
	aggregator         *RealtimeMetricsAggregator
	eventBus           EventBus

	// Buffer for batch writes
	metricBuffer []*Metric
	bufferSize   int
	flushTicker  *time.Ticker

	// Configuration
	batchSize     int
	flushInterval time.Duration

	// State
	done chan struct{}
}

// Config holds service configuration
type Config struct {
	BatchSize     int
	FlushInterval time.Duration
}

// DefaultConfig returns default configuration
func DefaultConfig() Config {
	return Config{
		BatchSize:     100,
		FlushInterval: time.Second,
	}
}

// NewUsabilityMetricsService creates a new metrics service
func NewUsabilityMetricsService(
	metricsRepo repository.UsabilityMetricsRepository,
	frustrationEngine *FrustrationDetectionEngine,
	aggregator *RealtimeMetricsAggregator,
	eventBus EventBus,
	config Config,
) *UsabilityMetricsService {
	return &UsabilityMetricsService{
		metricsRepo:       metricsRepo,
		frustrationEngine: frustrationEngine,
		aggregator:        aggregator,
		eventBus:          eventBus,
		metricBuffer:      make([]*Metric, 0, config.BatchSize),
		bufferSize:        config.BatchSize,
		batchSize:         config.BatchSize,
		flushInterval:     config.FlushInterval,
		done:              make(chan struct{}),
	}
}

// RecordMetric records a single metric
func (s *UsabilityMetricsService) RecordMetric(ctx context.Context, metric *Metric) error {
	if metric == nil {
		return fmt.Errorf("metric cannot be nil")
	}

	if metric.Timestamp.IsZero() {
		metric.Timestamp = time.Now()
	}

	// Add to buffer
	s.mu.Lock()
	s.metricBuffer = append(s.metricBuffer, metric)
	shouldFlush := len(s.metricBuffer) >= s.bufferSize
	s.mu.Unlock()

	// Flush if buffer is full
	if shouldFlush {
		if err := s.flushBuffer(ctx); err != nil {
			fmt.Printf("error flushing buffer: %v\n", err)
		}
	}

	// Analyze metric for frustration
	frustrationEvent := s.frustrationEngine.AnalyzeMetric(metric)
	if frustrationEvent != nil {
		s.eventBus.PublishFrustrationEvent(frustrationEvent)
	}

	// Update real-time aggregations
	s.aggregator.UpdateMetric(metric)

	return nil
}

// RecordMetrics records multiple metrics in batch
func (s *UsabilityMetricsService) RecordMetrics(ctx context.Context, metrics []*Metric) error {
	if len(metrics) == 0 {
		return nil
	}

	s.mu.Lock()
	for _, metric := range metrics {
		if metric.Timestamp.IsZero() {
			metric.Timestamp = time.Now()
		}
		s.metricBuffer = append(s.metricBuffer, metric)
	}
	shouldFlush := len(s.metricBuffer) >= s.bufferSize
	s.mu.Unlock()

	// Analyze each metric
	for _, metric := range metrics {
		frustrationEvent := s.frustrationEngine.AnalyzeMetric(metric)
		if frustrationEvent != nil {
			s.eventBus.PublishFrustrationEvent(frustrationEvent)
		}
		s.aggregator.UpdateMetric(metric)
	}

	// Flush if needed
	if shouldFlush {
		if err := s.flushBuffer(ctx); err != nil {
			fmt.Printf("error flushing buffer: %v\n", err)
		}
	}

	return nil
}

// flushBuffer writes buffered metrics to database
func (s *UsabilityMetricsService) flushBuffer(ctx context.Context) error {
	s.mu.Lock()
	if len(s.metricBuffer) == 0 {
		s.mu.Unlock()
		return nil
	}

	// Copy buffer for writing
	toWrite := make([]*Metric, len(s.metricBuffer))
	copy(toWrite, s.metricBuffer)
	s.metricBuffer = s.metricBuffer[:0] // Clear buffer
	s.mu.Unlock()

	// Write to database
	for _, metric := range toWrite {
		// Convert to interface{} for repository
		data, err := json.Marshal(metric)
		if err != nil {
			fmt.Printf("error marshaling metric: %v\n", err)
			continue
		}

		// Record in repository
		if err := s.metricsRepo.RecordMetric(ctx, data); err != nil {
			fmt.Printf("error recording metric: %v\n", err)
		}
	}

	return nil
}

// GetStudentMetrics retrieves metrics for a student
func (s *UsabilityMetricsService) GetStudentMetrics(
	ctx context.Context,
	studentID string,
	appName string,
	since time.Time,
) ([]interface{}, error) {
	return s.metricsRepo.GetStudentMetrics(ctx, studentID, appName, since)
}

// GetStudentMetricsCount returns count of metrics for a student
func (s *UsabilityMetricsService) GetStudentMetricsCount(
	ctx context.Context,
	studentID string,
	appName string,
	since time.Time,
) (int, error) {
	metrics, err := s.metricsRepo.GetStudentMetrics(ctx, studentID, appName, since)
	if err != nil {
		return 0, err
	}
	return len(metrics), nil
}

// GetClassroomMetrics retrieves aggregated classroom metrics
func (s *UsabilityMetricsService) GetClassroomMetrics(
	ctx context.Context,
	classroomID string,
	appName string,
) (map[string]interface{}, error) {
	return s.metricsRepo.GetClassroomMetrics(ctx, classroomID, appName)
}

// GetRealtimeMetrics returns real-time aggregated metrics
func (s *UsabilityMetricsService) GetRealtimeMetrics(studentID string, appName string) map[string]interface{} {
	return s.aggregator.GetMetrics(studentID, appName)
}

// GetSessionMetrics returns metrics for a session
func (s *UsabilityMetricsService) GetSessionMetrics(
	ctx context.Context,
	sessionID string,
) ([]interface{}, error) {
	return s.metricsRepo.GetMetricsByType(ctx, sessionID, time.Now().Add(-1*time.Hour))
}

// Start begins background flushing
func (s *UsabilityMetricsService) Start(ctx context.Context) {
	s.flushTicker = time.NewTicker(s.flushInterval)
	go func() {
		for {
			select {
			case <-s.done:
				s.flushTicker.Stop()
				// Final flush
				if err := s.flushBuffer(ctx); err != nil {
					fmt.Printf("error during final flush: %v\n", err)
				}
				return
			case <-ctx.Done():
				s.flushTicker.Stop()
				// Final flush
				if err := s.flushBuffer(ctx); err != nil {
					fmt.Printf("error during final flush: %v\n", err)
				}
				return
			case <-s.flushTicker.C:
				if err := s.flushBuffer(ctx); err != nil {
					fmt.Printf("error during periodic flush: %v\n", err)
				}
			}
		}
	}()
}

// Stop stops the service and flushes remaining metrics
func (s *UsabilityMetricsService) Stop() {
	close(s.done)
}

// GetBufferSize returns current buffer size
func (s *UsabilityMetricsService) GetBufferSize() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return len(s.metricBuffer)
}

// ForceFlush forces an immediate flush of buffered metrics
func (s *UsabilityMetricsService) ForceFlush(ctx context.Context) error {
	return s.flushBuffer(ctx)
}
