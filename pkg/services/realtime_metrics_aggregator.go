package services

import (
	"context"
	"sync"
	"time"
)

// RealtimeMetricsAggregator aggregates metrics from multiple education apps in real-time
type RealtimeMetricsAggregator struct {
	mu                     sync.RWMutex
	metrics                map[string][]*AppMetric // Keyed by session_id
	studentMetrics         map[string]*StudentAggregatedMetrics
	classroomMetrics       map[string]*ClassroomMetrics
	metricsBuffer          chan *AppMetric
	aggregationInterval    time.Duration
	windowSize             time.Duration
	stopChan               chan struct{}
	metricsRepository      MetricsRepository
	frustrationDetector    *FrustrationDetectionEngine
	observers              map[string][]MetricsObserver
}

// StudentAggregatedMetrics represents aggregated metrics for a student
type StudentAggregatedMetrics struct {
	StudentID         string                 `json:"student_id"`
	SessionID         string                 `json:"session_id"`
	AppName           string                 `json:"app_name"`
	AverageMetrics    map[string]float64     `json:"average_metrics"`
	PeakMetrics       map[string]float64     `json:"peak_metrics"`
	MinMetrics        map[string]float64     `json:"min_metrics"`
	TotalCount        int64                  `json:"total_count"`
	AnomalousCount    int64                  `json:"anomalous_count"`
	LastUpdateTime    time.Time              `json:"last_update_time"`
	HealthScore       float64                `json:"health_score"` // 0-100
	FrustrationLevel  string                 `json:"frustration_level"`
	Recommendations   []string               `json:"recommendations"`
}

// ClassroomMetrics represents aggregated metrics for a classroom
type ClassroomMetrics struct {
	ClassroomID          string                          `json:"classroom_id"`
	TotalStudents        int                             `json:"total_students"`
	ActiveStudents       int                             `json:"active_students"`
	AverageHealthScore   float64                         `json:"average_health_score"`
	StruggleStudents     []StruggleStudentInfo           `json:"struggling_students"`
	MetricsSummary       map[string]ClassroomMetricSummary `json:"metrics_summary"`
	LastUpdateTime       time.Time                       `json:"last_update_time"`
	ClassroomHealthTrend string                          `json:"classroom_health_trend"` // 'improving', 'stable', 'degrading'
}

// StruggleStudentInfo contains information about a struggling student
type StruggleStudentInfo struct {
	StudentID        string  `json:"student_id"`
	HealthScore      float64 `json:"health_score"`
	FrustrationLevel string  `json:"frustration_level"`
	IssueDescription string  `json:"issue_description"`
	RecommendedAction string `json:"recommended_action"`
}

// ClassroomMetricSummary summarizes a metric across the classroom
type ClassroomMetricSummary struct {
	MetricName       string  `json:"metric_name"`
	Average          float64 `json:"average"`
	Median           float64 `json:"median"`
	Min              float64 `json:"min"`
	Max              float64 `json:"max"`
	StdDev           float64 `json:"std_dev"`
	AnomalyCount     int     `json:"anomaly_count"`
}

// MetricsRepository interface for persisting metrics
type MetricsRepository interface {
	SaveMetric(ctx context.Context, metric *AppMetric) error
	SaveAggregatedMetrics(ctx context.Context, aggregated *StudentAggregatedMetrics) error
	SaveClassroomMetrics(ctx context.Context, classroom *ClassroomMetrics) error
	GetMetrics(ctx context.Context, sessionID string, since time.Time) ([]*AppMetric, error)
	GetStudentMetrics(ctx context.Context, studentID string, since time.Time) ([]*AppMetric, error)
}

// MetricsObserver receives updates when metrics are available
type MetricsObserver interface {
	OnMetricsAggregated(aggregated *StudentAggregatedMetrics) error
	OnAnomalyDetected(metric *AppMetric) error
	OnFrustrationDetected(studentID string, level string) error
}

// FrustrationDetectionEngine detects frustration levels from metrics
type FrustrationDetectionEngine struct {
	// Configuration for frustration detection thresholds and patterns
}

// DetectFrustration analyzes metrics and returns frustration level
func (fde *FrustrationDetectionEngine) DetectFrustration(metrics []*AppMetric) string {
	if fde == nil || len(metrics) == 0 {
		return "low"
	}

	// Placeholder implementation - returns low frustration
	// Will be enhanced in Task 22: Frustration Detection Optimization
	return "low"
}

// NewRealtimeMetricsAggregator creates a new aggregator
func NewRealtimeMetricsAggregator(
	metricsRepository MetricsRepository,
	frustrationDetector *FrustrationDetectionEngine,
) *RealtimeMetricsAggregator {
	return &RealtimeMetricsAggregator{
		metrics:                make(map[string][]*AppMetric),
		studentMetrics:         make(map[string]*StudentAggregatedMetrics),
		classroomMetrics:       make(map[string]*ClassroomMetrics),
		metricsBuffer:          make(chan *AppMetric, 1000),
		aggregationInterval:    10 * time.Second,
		windowSize:             5 * time.Minute,
		metricsRepository:      metricsRepository,
		frustrationDetector:    frustrationDetector,
		observers:              make(map[string][]MetricsObserver),
		stopChan:               make(chan struct{}),
	}
}

// Start starts the aggregator
func (rma *RealtimeMetricsAggregator) Start(ctx context.Context) error {
	// Start metric processing goroutine
	go rma.processMetrics(ctx)

	// Start aggregation goroutine
	go rma.aggregateMetrics(ctx)

	return nil
}

// RecordMetric records a metric to be aggregated
func (rma *RealtimeMetricsAggregator) RecordMetric(ctx context.Context, metric *AppMetric) error {
	select {
	case rma.metricsBuffer <- metric:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

// processMetrics processes metrics from the buffer
func (rma *RealtimeMetricsAggregator) processMetrics(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case <-rma.stopChan:
			return
		case metric := <-rma.metricsBuffer:
			rma.mu.Lock()

			// Store metric
			if _, exists := rma.metrics[metric.SessionID]; !exists {
				rma.metrics[metric.SessionID] = make([]*AppMetric, 0)
			}
			rma.metrics[metric.SessionID] = append(rma.metrics[metric.SessionID], metric)

			// Persist to repository
			if rma.metricsRepository != nil {
				go rma.metricsRepository.SaveMetric(ctx, metric)
			}

			// Detect anomalies
			if metric.IsAnomaly {
				rma.notifyAnomalyDetected(metric)
			}

			rma.mu.Unlock()
		}
	}
}

// aggregateMetrics periodically aggregates collected metrics
func (rma *RealtimeMetricsAggregator) aggregateMetrics(ctx context.Context) {
	ticker := time.NewTicker(rma.aggregationInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-rma.stopChan:
			return
		case <-ticker.C:
			rma.performAggregation(ctx)
		}
	}
}

// performAggregation performs the actual metric aggregation
func (rma *RealtimeMetricsAggregator) performAggregation(ctx context.Context) {
	rma.mu.Lock()
	defer rma.mu.Unlock()

	now := time.Now()
	windowStart := now.Add(-rma.windowSize)

	// Aggregate by session/student
	for sessionID, metrics := range rma.metrics {
		// Filter metrics within window
		windowMetrics := make([]*AppMetric, 0)
		for _, metric := range metrics {
			if metric.Timestamp.After(windowStart) {
				windowMetrics = append(windowMetrics, metric)
			}
		}

		if len(windowMetrics) == 0 {
			continue
		}

		// Calculate aggregated metrics
		aggregated := rma.calculateAggregatedMetrics(sessionID, windowMetrics)

		// Store aggregated metrics
		rma.studentMetrics[sessionID] = aggregated

		// Detect frustration
		if rma.frustrationDetector != nil {
			frustrationLevel := rma.frustrationDetector.DetectFrustration(windowMetrics)
			if frustrationLevel != "low" {
				rma.notifyFrustrationDetected(aggregated.StudentID, frustrationLevel)
			}
		}

		// Persist aggregated metrics
		if rma.metricsRepository != nil {
			go rma.metricsRepository.SaveAggregatedMetrics(ctx, aggregated)
		}

		// Notify observers
		rma.notifyMetricsAggregated(aggregated)
	}

	// Clean up old metrics
	rma.cleanupOldMetrics(windowStart)
}

// calculateAggregatedMetrics calculates aggregated metrics from raw metrics
func (rma *RealtimeMetricsAggregator) calculateAggregatedMetrics(sessionID string, metrics []*AppMetric) *StudentAggregatedMetrics {
	if len(metrics) == 0 {
		return &StudentAggregatedMetrics{
			SessionID:       sessionID,
			AverageMetrics:  make(map[string]float64),
			PeakMetrics:     make(map[string]float64),
			MinMetrics:      make(map[string]float64),
			LastUpdateTime:  time.Now(),
			HealthScore:     50.0,
			FrustrationLevel: "low",
		}
	}

	aggregated := &StudentAggregatedMetrics{
		SessionID:       sessionID,
		StudentID:       metrics[0].StudentID,
		AppName:         metrics[0].AppName,
		AverageMetrics:  make(map[string]float64),
		PeakMetrics:     make(map[string]float64),
		MinMetrics:      make(map[string]float64),
		TotalCount:      int64(len(metrics)),
		LastUpdateTime:  time.Now(),
	}

	// Group metrics by type and calculate statistics
	metricsByType := make(map[string][]float64)
	for _, metric := range metrics {
		if _, exists := metricsByType[metric.MetricType]; !exists {
			metricsByType[metric.MetricType] = make([]float64, 0)
		}
		metricsByType[metric.MetricType] = append(metricsByType[metric.MetricType], metric.MetricValue)

		if metric.IsAnomaly {
			aggregated.AnomalousCount++
		}
	}

	// Calculate average, peak, and min for each metric type
	for metricType, values := range metricsByType {
		sum := 0.0
		max := values[0]
		min := values[0]

		for _, v := range values {
			sum += v
			if v > max {
				max = v
			}
			if v < min {
				min = v
			}
		}

		aggregated.AverageMetrics[metricType] = sum / float64(len(values))
		aggregated.PeakMetrics[metricType] = max
		aggregated.MinMetrics[metricType] = min
	}

	// Calculate health score (0-100)
	anomalyRate := float64(aggregated.AnomalousCount) / float64(len(metrics))
	aggregated.HealthScore = (1.0 - anomalyRate) * 100.0

	// Generate recommendations based on health score
	aggregated.Recommendations = generateRecommendations(aggregated.HealthScore)

	return aggregated
}

// generateRecommendations generates recommendations based on health score
func generateRecommendations(healthScore float64) []string {
	recommendations := make([]string, 0)

	if healthScore < 40 {
		recommendations = append(recommendations, "Student needs immediate intervention")
		recommendations = append(recommendations, "Consider providing personalized support")
		recommendations = append(recommendations, "Check for underlying learning difficulties")
	} else if healthScore < 60 {
		recommendations = append(recommendations, "Student performance below average")
		recommendations = append(recommendations, "Provide additional practice exercises")
		recommendations = append(recommendations, "Monitor closely for improvement")
	} else if healthScore < 80 {
		recommendations = append(recommendations, "Student performing adequately")
		recommendations = append(recommendations, "Continue with current learning plan")
	} else {
		recommendations = append(recommendations, "Student performing well")
		recommendations = append(recommendations, "Consider advancing to more challenging material")
	}

	return recommendations
}

// cleanupOldMetrics removes metrics older than the window
func (rma *RealtimeMetricsAggregator) cleanupOldMetrics(cutoffTime time.Time) {
	for sessionID, metrics := range rma.metrics {
		newMetrics := make([]*AppMetric, 0)
		for _, metric := range metrics {
			if metric.Timestamp.After(cutoffTime) {
				newMetrics = append(newMetrics, metric)
			}
		}
		if len(newMetrics) == 0 {
			delete(rma.metrics, sessionID)
		} else {
			rma.metrics[sessionID] = newMetrics
		}
	}
}

// GetStudentMetrics returns aggregated metrics for a student
func (rma *RealtimeMetricsAggregator) GetStudentMetrics(sessionID string) *StudentAggregatedMetrics {
	rma.mu.RLock()
	defer rma.mu.RUnlock()

	if aggregated, exists := rma.studentMetrics[sessionID]; exists {
		return aggregated
	}
	return nil
}

// GetClassroomMetrics returns aggregated metrics for a classroom
func (rma *RealtimeMetricsAggregator) GetClassroomMetrics(classroomID string) *ClassroomMetrics {
	rma.mu.RLock()
	defer rma.mu.RUnlock()

	if metrics, exists := rma.classroomMetrics[classroomID]; exists {
		return metrics
	}
	return nil
}

// RegisterObserver registers a metrics observer
func (rma *RealtimeMetricsAggregator) RegisterObserver(name string, observer MetricsObserver) {
	rma.mu.Lock()
	defer rma.mu.Unlock()

	if _, exists := rma.observers[name]; !exists {
		rma.observers[name] = make([]MetricsObserver, 0)
	}

	rma.observers[name] = append(rma.observers[name], observer)
}

// notifyMetricsAggregated notifies observers of aggregated metrics
func (rma *RealtimeMetricsAggregator) notifyMetricsAggregated(aggregated *StudentAggregatedMetrics) {
	for _, observers := range rma.observers {
		for _, observer := range observers {
			go func(o MetricsObserver) {
				if err := o.OnMetricsAggregated(aggregated); err != nil {
					// Log but don't fail
				}
			}(observer)
		}
	}
}

// notifyAnomalyDetected notifies observers of anomalies
func (rma *RealtimeMetricsAggregator) notifyAnomalyDetected(metric *AppMetric) {
	for _, observers := range rma.observers {
		for _, observer := range observers {
			go func(o MetricsObserver) {
				if err := o.OnAnomalyDetected(metric); err != nil {
					// Log but don't fail
				}
			}(observer)
		}
	}
}

// notifyFrustrationDetected notifies observers of frustration detection
func (rma *RealtimeMetricsAggregator) notifyFrustrationDetected(studentID, level string) {
	for _, observers := range rma.observers {
		for _, observer := range observers {
			go func(o MetricsObserver) {
				if err := o.OnFrustrationDetected(studentID, level); err != nil {
					// Log but don't fail
				}
			}(observer)
		}
	}
}

// Stop stops the aggregator
func (rma *RealtimeMetricsAggregator) Stop() error {
	close(rma.stopChan)
	return nil
}

// GetStatistics returns overall statistics
func (rma *RealtimeMetricsAggregator) GetStatistics() map[string]interface{} {
	rma.mu.RLock()
	defer rma.mu.RUnlock()

	totalMetrics := 0
	for _, metrics := range rma.metrics {
		totalMetrics += len(metrics)
	}

	return map[string]interface{}{
		"total_metrics":           totalMetrics,
		"active_sessions":         len(rma.metrics),
		"aggregated_students":     len(rma.studentMetrics),
		"classroom_counts":        len(rma.classroomMetrics),
		"buffer_size":             len(rma.metricsBuffer),
		"aggregation_interval_ms": int(rma.aggregationInterval.Milliseconds()),
		"window_size_minutes":     int(rma.windowSize.Minutes()),
	}
}
