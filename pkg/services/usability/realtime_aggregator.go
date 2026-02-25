package usability

import (
	"sync"
	"time"
)

// MetricsSnapshot represents aggregated metrics for a student/app combination at a point in time
type MetricsSnapshot struct {
	StudentID           string    `json:"student_id"`
	AppName             string    `json:"app_name"`
	KeyPressCount       int       `json:"key_press_count"`
	BackspaceCount      int       `json:"backspace_count"`
	ErrorCount          int       `json:"error_count"`
	CompletionCount     int       `json:"completion_count"`
	FocusCount          int       `json:"focus_count"`
	BlurCount           int       `json:"blur_count"`
	ScrollingCount      int       `json:"scrolling_count"`
	MouseMovementCount  int       `json:"mouse_movement_count"`
	AverageHesitation   time.Duration `json:"average_hesitation"`
	CurrentHesitation   time.Duration `json:"current_hesitation"`
	ErrorRate           float64   `json:"error_rate"` // errors per 100 keypresses
	BackspaceRate       float64   `json:"backspace_rate"` // backspaces per 100 keypresses
	CompletionRate      float64   `json:"completion_rate"` // completions per keypresses
	LastUpdated         time.Time `json:"last_updated"`
}

// ClassroomMetricsSnapshot represents aggregated metrics for a classroom
type ClassroomMetricsSnapshot struct {
	ClassroomID        string                      `json:"classroom_id"`
	AppName            string                      `json:"app_name"`
	TotalStudents      int                         `json:"total_students"`
	ActiveStudents     int                         `json:"active_students"`
	AverageErrorRate   float64                     `json:"average_error_rate"`
	AverageBackspaceRate float64                   `json:"average_backspace_rate"`
	StudentSnapshots   map[string]*MetricsSnapshot `json:"student_snapshots"`
	LastUpdated        time.Time                   `json:"last_updated"`
}

// RealtimeMetricsAggregator aggregates metrics in real-time for multiple students and apps
type RealtimeMetricsAggregator struct {
	mu                  sync.RWMutex
	studentMetrics      map[string]*MetricsSnapshot // key: "studentID:appName"
	classroomMetrics    map[string]*ClassroomMetricsSnapshot // key: classroomID:appName
	windowSize          time.Duration
	hesitationDurations map[string][]time.Duration // key: "studentID:appName", value: hesitation samples
}

// NewRealtimeMetricsAggregator creates a new real-time metrics aggregator
func NewRealtimeMetricsAggregator(windowSize time.Duration) *RealtimeMetricsAggregator {
	if windowSize == 0 {
		windowSize = 1 * time.Minute
	}

	return &RealtimeMetricsAggregator{
		studentMetrics:      make(map[string]*MetricsSnapshot),
		classroomMetrics:    make(map[string]*ClassroomMetricsSnapshot),
		windowSize:          windowSize,
		hesitationDurations: make(map[string][]time.Duration),
	}
}

// UpdateMetric updates the aggregator with a new metric
func (a *RealtimeMetricsAggregator) UpdateMetric(metric *Metric) {
	if metric == nil {
		return
	}

	a.mu.Lock()
	defer a.mu.Unlock()

	snapshotKey := metric.StudentID + ":" + metric.AppName
	snapshot, exists := a.studentMetrics[snapshotKey]

	if !exists {
		snapshot = &MetricsSnapshot{
			StudentID:   metric.StudentID,
			AppName:     metric.AppName,
			LastUpdated: time.Now(),
		}
		a.studentMetrics[snapshotKey] = snapshot
	}

	snapshot.LastUpdated = time.Now()

	// Update counts based on metric type
	switch metric.MetricType {
	case MetricTypeKeyPress:
		snapshot.KeyPressCount++

	case MetricTypeBackspace:
		snapshot.BackspaceCount++

	case MetricTypeError:
		snapshot.ErrorCount++

	case MetricTypeCompletion:
		snapshot.CompletionCount++

	case MetricTypeFocus:
		snapshot.FocusCount++

	case MetricTypeBlur:
		snapshot.BlurCount++

	case MetricTypeScrolling:
		snapshot.ScrollingCount++

	case MetricTypeMouseMovement:
		snapshot.MouseMovementCount++

	case MetricTypeHesitation:
		hesitation := time.Duration(metric.MetricValue*1000) * time.Millisecond
		snapshot.CurrentHesitation = hesitation

		// Track hesitation samples for average calculation
		hesitationKey := metric.StudentID + ":" + metric.AppName
		a.hesitationDurations[hesitationKey] = append(a.hesitationDurations[hesitationKey], hesitation)

		// Keep only recent samples (within window size)
		if len(a.hesitationDurations[hesitationKey]) > 100 {
			a.hesitationDurations[hesitationKey] = a.hesitationDurations[hesitationKey][len(a.hesitationDurations[hesitationKey])-100:]
		}

		// Calculate average
		if len(a.hesitationDurations[hesitationKey]) > 0 {
			totalHesitation := time.Duration(0)
			for _, h := range a.hesitationDurations[hesitationKey] {
				totalHesitation += h
			}
			snapshot.AverageHesitation = totalHesitation / time.Duration(len(a.hesitationDurations[hesitationKey]))
		}
	}

	// Calculate error and backspace rates
	if snapshot.KeyPressCount > 0 {
		snapshot.ErrorRate = float64(snapshot.ErrorCount) * 100 / float64(snapshot.KeyPressCount)
		snapshot.BackspaceRate = float64(snapshot.BackspaceCount) * 100 / float64(snapshot.KeyPressCount)
		snapshot.CompletionRate = float64(snapshot.CompletionCount) / float64(snapshot.KeyPressCount)
	}
}

// GetMetrics returns the current metrics snapshot for a student/app combination
func (a *RealtimeMetricsAggregator) GetMetrics(studentID, appName string) map[string]interface{} {
	a.mu.RLock()
	defer a.mu.RUnlock()

	snapshotKey := studentID + ":" + appName
	snapshot, exists := a.studentMetrics[snapshotKey]

	if !exists {
		return map[string]interface{}{
			"student_id":      studentID,
			"app_name":        appName,
			"no_data":         true,
			"last_updated":    time.Now(),
		}
	}

	return map[string]interface{}{
		"student_id":            snapshot.StudentID,
		"app_name":              snapshot.AppName,
		"key_press_count":       snapshot.KeyPressCount,
		"backspace_count":       snapshot.BackspaceCount,
		"error_count":           snapshot.ErrorCount,
		"completion_count":      snapshot.CompletionCount,
		"focus_count":           snapshot.FocusCount,
		"blur_count":            snapshot.BlurCount,
		"scrolling_count":       snapshot.ScrollingCount,
		"mouse_movement_count":  snapshot.MouseMovementCount,
		"average_hesitation_ms": snapshot.AverageHesitation.Milliseconds(),
		"current_hesitation_ms": snapshot.CurrentHesitation.Milliseconds(),
		"error_rate":            snapshot.ErrorRate,
		"backspace_rate":        snapshot.BackspaceRate,
		"completion_rate":       snapshot.CompletionRate,
		"last_updated":          snapshot.LastUpdated,
	}
}

// GetStudentMetrics returns all current metrics for a student across all apps
func (a *RealtimeMetricsAggregator) GetStudentMetrics(studentID string) map[string]interface{} {
	a.mu.RLock()
	defer a.mu.RUnlock()

	studentSnapshots := make(map[string]interface{})

	for _, snapshot := range a.studentMetrics {
		if snapshot.StudentID == studentID {
			studentSnapshots[snapshot.AppName] = map[string]interface{}{
				"app_name":         snapshot.AppName,
				"key_press_count":  snapshot.KeyPressCount,
				"error_count":      snapshot.ErrorCount,
				"error_rate":       snapshot.ErrorRate,
				"backspace_count":  snapshot.BackspaceCount,
				"backspace_rate":   snapshot.BackspaceRate,
				"completion_rate":  snapshot.CompletionRate,
				"last_updated":     snapshot.LastUpdated,
			}
		}
	}

	return map[string]interface{}{
		"student_id": studentID,
		"apps":       studentSnapshots,
		"timestamp":  time.Now(),
	}
}

// GetClassroomMetrics returns aggregated metrics for a classroom
func (a *RealtimeMetricsAggregator) GetClassroomMetrics(classroomID, appName string) map[string]interface{} {
	a.mu.RLock()
	defer a.mu.RUnlock()

	classroomKey := classroomID + ":" + appName
	classroom, exists := a.classroomMetrics[classroomKey]

	if !exists {
		classroom = &ClassroomMetricsSnapshot{
			ClassroomID:      classroomID,
			AppName:          appName,
			StudentSnapshots: make(map[string]*MetricsSnapshot),
			LastUpdated:      time.Now(),
		}
	}

	// Calculate aggregates
	var totalErrorRate float64
	var totalBackspaceRate float64
	studentCount := 0

	for _, snapshot := range a.studentMetrics {
		if snapshot.AppName == appName {
			classroom.StudentSnapshots[snapshot.StudentID] = snapshot
			totalErrorRate += snapshot.ErrorRate
			totalBackspaceRate += snapshot.BackspaceRate
			studentCount++
		}
	}

	classroom.TotalStudents = studentCount
	classroom.ActiveStudents = 0

	// Count active students (updated in last 30 seconds)
	thirtySecondsAgo := time.Now().Add(-30 * time.Second)
	for _, snapshot := range classroom.StudentSnapshots {
		if snapshot.LastUpdated.After(thirtySecondsAgo) {
			classroom.ActiveStudents++
		}
	}

	if studentCount > 0 {
		classroom.AverageErrorRate = totalErrorRate / float64(studentCount)
		classroom.AverageBackspaceRate = totalBackspaceRate / float64(studentCount)
	}

	classroom.LastUpdated = time.Now()

	return map[string]interface{}{
		"classroom_id":          classroom.ClassroomID,
		"app_name":              classroom.AppName,
		"total_students":        classroom.TotalStudents,
		"active_students":       classroom.ActiveStudents,
		"average_error_rate":    classroom.AverageErrorRate,
		"average_backspace_rate": classroom.AverageBackspaceRate,
		"students":              classroom.StudentSnapshots,
		"last_updated":          classroom.LastUpdated,
	}
}

// Reset clears metrics for a student/app combination
func (a *RealtimeMetricsAggregator) Reset(studentID, appName string) {
	a.mu.Lock()
	defer a.mu.Unlock()

	snapshotKey := studentID + ":" + appName
	delete(a.studentMetrics, snapshotKey)
	delete(a.hesitationDurations, snapshotKey)
}

// ResetAll clears all metrics
func (a *RealtimeMetricsAggregator) ResetAll() {
	a.mu.Lock()
	defer a.mu.Unlock()

	a.studentMetrics = make(map[string]*MetricsSnapshot)
	a.classroomMetrics = make(map[string]*ClassroomMetricsSnapshot)
	a.hesitationDurations = make(map[string][]time.Duration)
}

// GetAllMetrics returns snapshots for all tracked students
func (a *RealtimeMetricsAggregator) GetAllMetrics() map[string]*MetricsSnapshot {
	a.mu.RLock()
	defer a.mu.RUnlock()

	// Return a copy
	result := make(map[string]*MetricsSnapshot)
	for key, snapshot := range a.studentMetrics {
		result[key] = snapshot
	}
	return result
}

// GetStudentCount returns the number of students currently being tracked
func (a *RealtimeMetricsAggregator) GetStudentCount() int {
	a.mu.RLock()
	defer a.mu.RUnlock()

	return len(a.studentMetrics)
}
