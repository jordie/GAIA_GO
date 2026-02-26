package usability

import (
	"sync"
	"time"
)

// FrustrationEvent represents a detected frustration event
type FrustrationEvent struct {
	StudentID   string            `json:"student_id"`
	AppName     string            `json:"app_name"`
	EventType   string            `json:"event_type"`
	Severity    string            `json:"severity"` // low, medium, high, critical
	Details     map[string]interface{} `json:"details"`
	DetectedAt  time.Time         `json:"detected_at"`
	ConfidenceScore float64       `json:"confidence_score"` // 0-1
}

// FrustrationPattern tracks metrics for frustration detection
type FrustrationPattern struct {
	mu                      sync.RWMutex
	studentID               string
	appName                 string
	consecutiveErrors       int
	consecutiveBackspaces   int
	hesitationDuration      time.Duration
	lastActivityTime        time.Time
	keyPressCount           int
	backspaceCount          int
	errorCount              int
	windowStartTime         time.Time
}

// FrustrationDetectionEngine detects frustration patterns
type FrustrationDetectionEngine struct {
	mu              sync.RWMutex
	patterns        map[string]*FrustrationPattern
	thresholds      *FrustrationThresholds
	eventHandlers   []func(*FrustrationEvent)
}

// FrustrationThresholds defines thresholds for frustration detection
type FrustrationThresholds struct {
	ErrorThreshold          int           // consecutive errors before high severity
	BackspaceThreshold      int           // consecutive backspaces
	HesitationThreshold     time.Duration // inactivity duration
	CriticalErrorCount      int           // errors for critical severity
	CriticalBackspaceCount  int           // backspaces for critical severity
	WindowSize              time.Duration // analysis window
}

// DefaultThresholds returns default frustration thresholds
func DefaultThresholds() *FrustrationThresholds {
	return &FrustrationThresholds{
		ErrorThreshold:        3,          // 3 errors = high
		BackspaceThreshold:    10,         // 10+ backspaces = concern
		HesitationThreshold:   30 * time.Second,
		CriticalErrorCount:    5,          // 5+ errors = critical
		CriticalBackspaceCount: 20,        // 20+ backspaces = critical
		WindowSize:            1 * time.Minute,
	}
}

// NewFrustrationDetectionEngine creates a new frustration detection engine
func NewFrustrationDetectionEngine(thresholds *FrustrationThresholds) *FrustrationDetectionEngine {
	if thresholds == nil {
		thresholds = DefaultThresholds()
	}

	return &FrustrationDetectionEngine{
		patterns:    make(map[string]*FrustrationPattern),
		thresholds:  thresholds,
		eventHandlers: make([]func(*FrustrationEvent), 0),
	}
}

// AnalyzeMetric analyzes a metric and detects frustration patterns
func (e *FrustrationDetectionEngine) AnalyzeMetric(metric *Metric) *FrustrationEvent {
	e.mu.Lock()
	defer e.mu.Unlock()

	patternKey := metric.StudentID + ":" + metric.AppName
	pattern, ok := e.patterns[patternKey]
	if !ok {
		pattern = &FrustrationPattern{
			studentID:       metric.StudentID,
			appName:         metric.AppName,
			windowStartTime: metric.Timestamp,
		}
		e.patterns[patternKey] = pattern
	}

	// Check if window has expired
	if metric.Timestamp.Sub(pattern.windowStartTime) > e.thresholds.WindowSize {
		// Reset window
		pattern.keyPressCount = 0
		pattern.backspaceCount = 0
		pattern.errorCount = 0
		pattern.windowStartTime = metric.Timestamp
	}

	// Update metrics based on type
	switch metric.MetricType {
	case MetricTypeKeyPress:
		pattern.keyPressCount++
		pattern.lastActivityTime = metric.Timestamp
		pattern.consecutiveBackspaces = 0 // Reset backspace counter

	case MetricTypeBackspace:
		pattern.backspaceCount++
		pattern.consecutiveBackspaces++
		pattern.lastActivityTime = metric.Timestamp

	case MetricTypeError:
		pattern.errorCount++
		pattern.consecutiveErrors++
		pattern.lastActivityTime = metric.Timestamp

	case MetricTypeHesitation:
		// Check if hesitation exceeds threshold
		hesitation := time.Duration(metric.MetricValue * 1000) * time.Millisecond
		if hesitation > e.thresholds.HesitationThreshold {
			pattern.hesitationDuration = hesitation
		}
	}

	// Check for frustration patterns
	return e.detectFrustration(pattern, metric)
}

// detectFrustration checks metrics against frustration thresholds
func (e *FrustrationDetectionEngine) detectFrustration(pattern *FrustrationPattern, metric *Metric) *FrustrationEvent {
	now := time.Now()
	severity := "low"
	confidenceScore := 0.0
	details := make(map[string]interface{})
	eventType := ""

	// Check for high error count
	if pattern.errorCount >= e.thresholds.CriticalErrorCount {
		severity = "critical"
		confidenceScore = 0.95
		eventType = "excessive_errors"
		details["error_count"] = pattern.errorCount
		details["threshold"] = e.thresholds.CriticalErrorCount
	} else if pattern.errorCount >= e.thresholds.ErrorThreshold {
		severity = "high"
		confidenceScore = 0.85
		eventType = "repeated_errors"
		details["error_count"] = pattern.errorCount
		details["threshold"] = e.thresholds.ErrorThreshold
	}

	// Check for high backspace count
	if pattern.backspaceCount >= e.thresholds.CriticalBackspaceCount {
		if severity == "critical" {
			confidenceScore = 0.99 // Multiple indicators
		} else {
			severity = "high"
			confidenceScore = 0.80
		}
		eventType = "excessive_corrections"
		details["backspace_count"] = pattern.backspaceCount
		details["threshold"] = e.thresholds.CriticalBackspaceCount
	} else if pattern.backspaceCount >= e.thresholds.BackspaceThreshold {
		if severity != "critical" {
			severity = "medium"
			confidenceScore = 0.70
		}
		eventType = "repeated_corrections"
		details["backspace_count"] = pattern.backspaceCount
		details["threshold"] = e.thresholds.BackspaceThreshold
	}

	// Check for long hesitation
	if pattern.hesitationDuration > e.thresholds.HesitationThreshold {
		if severity != "critical" && severity != "high" {
			severity = "medium"
			confidenceScore = 0.65
		}
		eventType = "prolonged_hesitation"
		details["hesitation_ms"] = pattern.hesitationDuration.Milliseconds()
		details["threshold_ms"] = e.thresholds.HesitationThreshold.Milliseconds()
	}

	// Only return event if frustration detected
	if severity == "low" {
		return nil
	}

	event := &FrustrationEvent{
		StudentID:       pattern.studentID,
		AppName:         pattern.appName,
		EventType:       eventType,
		Severity:        severity,
		Details:         details,
		DetectedAt:      now,
		ConfidenceScore: confidenceScore,
	}

	// Call event handlers
	for _, handler := range e.eventHandlers {
		go handler(event)
	}

	return event
}

// OnFrustrationDetected registers a handler for frustration events
func (e *FrustrationDetectionEngine) OnFrustrationDetected(handler func(*FrustrationEvent)) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.eventHandlers = append(e.eventHandlers, handler)
}

// Reset resets patterns for a student
func (e *FrustrationDetectionEngine) Reset(studentID string, appName string) {
	e.mu.Lock()
	defer e.mu.Unlock()

	patternKey := studentID + ":" + appName
	delete(e.patterns, patternKey)
}

// ResetAll resets all patterns
func (e *FrustrationDetectionEngine) ResetAll() {
	e.mu.Lock()
	defer e.mu.Unlock()

	e.patterns = make(map[string]*FrustrationPattern)
}

// GetPatternStats returns statistics for a pattern
func (e *FrustrationDetectionEngine) GetPatternStats(studentID string, appName string) map[string]interface{} {
	e.mu.RLock()
	defer e.mu.RUnlock()

	patternKey := studentID + ":" + appName
	pattern, ok := e.patterns[patternKey]
	if !ok {
		return nil
	}

	return map[string]interface{}{
		"student_id":               pattern.studentID,
		"app_name":                 pattern.appName,
		"error_count":              pattern.errorCount,
		"backspace_count":          pattern.backspaceCount,
		"key_press_count":          pattern.keyPressCount,
		"hesitation_duration_ms":   pattern.hesitationDuration.Milliseconds(),
		"last_activity":            pattern.lastActivityTime,
		"window_start":             pattern.windowStartTime,
	}
}
