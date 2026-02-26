package services

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
)

// EducationAppSDK provides metrics collection for education applications
type EducationAppSDK struct {
	mu                   sync.RWMutex
	appID                string
	appName              string
	metricsService       *RealtimeMetricsAggregator
	sessionID            string
	studentID            string
	bufferedMetrics      []*AppMetric
	bufferSize           int
	flushInterval        time.Duration
	lastFlushTime        time.Time
	isInitialized        bool
	eventHandlers        map[string][]EventHandler
	performanceThresholds map[string]PerformanceThreshold
}

// PerformanceThreshold defines acceptable performance limits
type PerformanceThreshold struct {
	Name           string
	WarningValue   float64
	CriticalValue  float64
	Unit           string
	CheckFrequency time.Duration
}

// EventHandler is called when specific events occur
type EventHandler func(event *AppEvent) error

// AppMetric represents a single metric from education app
type AppMetric struct {
	ID            string                 `json:"id"`
	AppName       string                 `json:"app_name"`
	MetricType    string                 `json:"metric_type"`
	MetricValue   float64                `json:"metric_value"`
	Unit          string                 `json:"unit"`
	StudentID     string                 `json:"student_id"`
	SessionID     string                 `json:"session_id"`
	Timestamp     time.Time              `json:"timestamp"`
	Metadata      map[string]interface{} `json:"metadata"`
	IsAnomaly     bool                   `json:"is_anomaly"`
	AnomalyScore  float64                `json:"anomaly_score"`
}

// AppEvent represents an event from education app
type AppEvent struct {
	ID        string                 `json:"id"`
	AppName   string                 `json:"app_name"`
	EventType string                 `json:"event_type"`
	StudentID string                 `json:"student_id"`
	SessionID string                 `json:"session_id"`
	Details   map[string]interface{} `json:"details"`
	Severity  string                 `json:"severity"` // 'low', 'medium', 'high', 'critical'
	Timestamp time.Time              `json:"timestamp"`
}

// NewEducationAppSDK creates a new education app SDK instance
func NewEducationAppSDK(
	appID string,
	appName string,
	metricsService *RealtimeMetricsAggregator,
) *EducationAppSDK {
	return &EducationAppSDK{
		appID:              appID,
		appName:            appName,
		metricsService:     metricsService,
		bufferedMetrics:    make([]*AppMetric, 0),
		bufferSize:         100,
		flushInterval:      5 * time.Second,
		isInitialized:      false,
		eventHandlers:      make(map[string][]EventHandler),
		performanceThresholds: make(map[string]PerformanceThreshold),
	}
}

// Initialize initializes the SDK for a student session
func (sdk *EducationAppSDK) Initialize(ctx context.Context, studentID, sessionID string) error {
	sdk.mu.Lock()
	defer sdk.mu.Unlock()

	if sdk.isInitialized {
		return fmt.Errorf("SDK already initialized for student %s", studentID)
	}

	sdk.studentID = studentID
	sdk.sessionID = sessionID
	sdk.isInitialized = true

	// Start buffer flush goroutine
	go sdk.startBufferFlusher(ctx)

	return nil
}

// RecordMetric records a single metric from the education app
func (sdk *EducationAppSDK) RecordMetric(ctx context.Context, metricType string, value float64, unit string) error {
	sdk.mu.Lock()
	defer sdk.mu.Unlock()

	if !sdk.isInitialized {
		return fmt.Errorf("SDK not initialized")
	}

	metric := &AppMetric{
		ID:          uuid.New().String(),
		AppName:     sdk.appName,
		MetricType:  metricType,
		MetricValue: value,
		Unit:        unit,
		StudentID:   sdk.studentID,
		SessionID:   sdk.sessionID,
		Timestamp:   time.Now(),
		Metadata:    make(map[string]interface{}),
	}

	// Check for anomalies
	metric.IsAnomaly, metric.AnomalyScore = sdk.detectAnomaly(metricType, value)

	// Buffer the metric
	sdk.bufferedMetrics = append(sdk.bufferedMetrics, metric)

	// Flush if buffer is full
	if len(sdk.bufferedMetrics) >= sdk.bufferSize {
		return sdk.flushMetricsLocked(ctx)
	}

	return nil
}

// RecordMetricWithMetadata records a metric with additional metadata
func (sdk *EducationAppSDK) RecordMetricWithMetadata(
	ctx context.Context,
	metricType string,
	value float64,
	unit string,
	metadata map[string]interface{},
) error {
	sdk.mu.Lock()
	defer sdk.mu.Unlock()

	if !sdk.isInitialized {
		return fmt.Errorf("SDK not initialized")
	}

	metric := &AppMetric{
		ID:          uuid.New().String(),
		AppName:     sdk.appName,
		MetricType:  metricType,
		MetricValue: value,
		Unit:        unit,
		StudentID:   sdk.studentID,
		SessionID:   sdk.sessionID,
		Timestamp:   time.Now(),
		Metadata:    metadata,
	}

	metric.IsAnomaly, metric.AnomalyScore = sdk.detectAnomaly(metricType, value)

	sdk.bufferedMetrics = append(sdk.bufferedMetrics, metric)

	if len(sdk.bufferedMetrics) >= sdk.bufferSize {
		return sdk.flushMetricsLocked(ctx)
	}

	return nil
}

// RecordEvent records an event from the education app
func (sdk *EducationAppSDK) RecordEvent(ctx context.Context, eventType string, severity string, details map[string]interface{}) error {
	sdk.mu.Lock()
	defer sdk.mu.Unlock()

	if !sdk.isInitialized {
		return fmt.Errorf("SDK not initialized")
	}

	event := &AppEvent{
		ID:        uuid.New().String(),
		AppName:   sdk.appName,
		EventType: eventType,
		StudentID: sdk.studentID,
		SessionID: sdk.sessionID,
		Details:   details,
		Severity:  severity,
		Timestamp: time.Now(),
	}

	// Flush pending metrics
	if len(sdk.bufferedMetrics) > 0 {
		_ = sdk.flushMetricsLocked(ctx)
	}

	// Call event handlers
	if handlers, exists := sdk.eventHandlers[eventType]; exists {
		for _, handler := range handlers {
			go func(h EventHandler) {
				if err := h(event); err != nil {
					// Log error but don't fail
					fmt.Printf("Event handler error: %v\n", err)
				}
			}(handler)
		}
	}

	return nil
}

// RegisterEventHandler registers a handler for an event type
func (sdk *EducationAppSDK) RegisterEventHandler(eventType string, handler EventHandler) {
	sdk.mu.Lock()
	defer sdk.mu.Unlock()

	if _, exists := sdk.eventHandlers[eventType]; !exists {
		sdk.eventHandlers[eventType] = make([]EventHandler, 0)
	}

	sdk.eventHandlers[eventType] = append(sdk.eventHandlers[eventType], handler)
}

// SetPerformanceThreshold sets a performance threshold for a metric
func (sdk *EducationAppSDK) SetPerformanceThreshold(threshold PerformanceThreshold) {
	sdk.mu.Lock()
	defer sdk.mu.Unlock()

	sdk.performanceThresholds[threshold.Name] = threshold
}

// Flush flushes all buffered metrics to the metrics service
func (sdk *EducationAppSDK) Flush(ctx context.Context) error {
	sdk.mu.Lock()
	defer sdk.mu.Unlock()

	return sdk.flushMetricsLocked(ctx)
}

// flushMetricsLocked flushes metrics (must be called with lock held)
func (sdk *EducationAppSDK) flushMetricsLocked(ctx context.Context) error {
	if len(sdk.bufferedMetrics) == 0 {
		return nil
	}

	// Send metrics to aggregator
	for _, metric := range sdk.bufferedMetrics {
		if sdk.metricsService != nil {
			if err := sdk.metricsService.RecordMetric(ctx, metric); err != nil {
				fmt.Printf("Error recording metric: %v\n", err)
			}
		}
	}

	sdk.bufferedMetrics = make([]*AppMetric, 0)
	sdk.lastFlushTime = time.Now()

	return nil
}

// startBufferFlusher periodically flushes buffered metrics
func (sdk *EducationAppSDK) startBufferFlusher(ctx context.Context) {
	ticker := time.NewTicker(sdk.flushInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			// Flush remaining metrics before exit
			sdk.Flush(ctx)
			return
		case <-ticker.C:
			sdk.Flush(ctx)
		}
	}
}

// detectAnomaly detects if a metric value is anomalous
func (sdk *EducationAppSDK) detectAnomaly(metricType string, value float64) (bool, float64) {
	if threshold, exists := sdk.performanceThresholds[metricType]; exists {
		if value >= threshold.CriticalValue {
			// Critical anomaly
			anomalyScore := (value - threshold.CriticalValue) / threshold.CriticalValue
			return true, anomalyScore
		} else if value >= threshold.WarningValue {
			// Warning anomaly
			anomalyScore := (value - threshold.WarningValue) / threshold.WarningValue
			return false, anomalyScore
		}
	}

	return false, 0.0
}

// GetBufferedMetricCount returns the number of buffered metrics
func (sdk *EducationAppSDK) GetBufferedMetricCount() int {
	sdk.mu.RLock()
	defer sdk.mu.RUnlock()

	return len(sdk.bufferedMetrics)
}

// GetStatus returns the current status of the SDK
func (sdk *EducationAppSDK) GetStatus() map[string]interface{} {
	sdk.mu.RLock()
	defer sdk.mu.RUnlock()

	return map[string]interface{}{
		"app_name":            sdk.appName,
		"student_id":          sdk.studentID,
		"session_id":          sdk.sessionID,
		"initialized":         sdk.isInitialized,
		"buffered_metrics":    len(sdk.bufferedMetrics),
		"last_flush_time":     sdk.lastFlushTime.Format(time.RFC3339),
		"event_handlers":      len(sdk.eventHandlers),
		"performance_checks":  len(sdk.performanceThresholds),
	}
}

// Close gracefully closes the SDK and flushes remaining metrics
func (sdk *EducationAppSDK) Close(ctx context.Context) error {
	sdk.mu.Lock()
	defer sdk.mu.Unlock()

	if !sdk.isInitialized {
		return fmt.Errorf("SDK not initialized")
	}

	// Flush remaining metrics
	err := sdk.flushMetricsLocked(ctx)

	sdk.isInitialized = false

	return err
}

// PresetApps defines preset configurations for education apps
var PresetApps = map[string]struct {
	name          string
	expectedMetrics []string
}{
	"typing": {
		name: "Typing Application",
		expectedMetrics: []string{
			"words_per_minute",
			"accuracy_percentage",
			"error_count",
			"correction_count",
			"session_duration",
		},
	},
	"math": {
		name: "Mathematics Application",
		expectedMetrics: []string{
			"problems_solved",
			"problems_correct",
			"accuracy_percentage",
			"time_per_problem",
			"difficulty_level",
		},
	},
	"reading": {
		name: "Reading Application",
		expectedMetrics: []string{
			"words_read",
			"reading_speed",
			"comprehension_score",
			"focus_time",
			"page_completion_rate",
		},
	},
	"piano": {
		name: "Piano Application",
		expectedMetrics: []string{
			"notes_played",
			"notes_correct",
			"accuracy_percentage",
			"tempo_bpm",
			"hand_coordination_score",
		},
	},
	"comprehension": {
		name: "Comprehension Application",
		expectedMetrics: []string{
			"questions_answered",
			"questions_correct",
			"accuracy_percentage",
			"confidence_score",
			"comprehension_level",
		},
	},
}
