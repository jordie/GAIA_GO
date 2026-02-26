package models

import (
	"time"

	"github.com/google/uuid"
)

// AppMetric represents a single metric from education app
type AppMetric struct {
	ID           string                 `json:"id"`
	AppName      string                 `json:"app_name"`
	MetricType   string                 `json:"metric_type"`
	MetricValue  float64                `json:"metric_value"`
	Unit         string                 `json:"unit"`
	StudentID    string                 `json:"student_id"`
	SessionID    string                 `json:"session_id"`
	Timestamp    time.Time              `json:"timestamp"`
	Metadata     map[string]interface{} `json:"metadata"`
	IsAnomaly    bool                   `json:"is_anomaly"`
	AnomalyScore float64                `json:"anomaly_score"`
}

// NewAppMetric creates a new app metric
func NewAppMetric(
	appName string,
	metricType string,
	value float64,
	unit string,
	studentID string,
	sessionID string,
) *AppMetric {
	return &AppMetric{
		ID:        uuid.New().String(),
		AppName:   appName,
		MetricType: metricType,
		MetricValue: value,
		Unit:      unit,
		StudentID: studentID,
		SessionID: sessionID,
		Timestamp: time.Now(),
		Metadata:  make(map[string]interface{}),
	}
}

// StudentAggregatedMetrics represents aggregated metrics for a student
type StudentAggregatedMetrics struct {
	StudentID        string             `json:"student_id"`
	SessionID        string             `json:"session_id"`
	AppName          string             `json:"app_name"`
	AverageMetrics   map[string]float64 `json:"average_metrics"`
	PeakMetrics      map[string]float64 `json:"peak_metrics"`
	MinMetrics       map[string]float64 `json:"min_metrics"`
	TotalCount       int64              `json:"total_count"`
	AnomalousCount   int64              `json:"anomalous_count"`
	HealthScore      float64            `json:"health_score"`
	FrustrationLevel string             `json:"frustration_level"`
	Recommendations  []string           `json:"recommendations"`
	LastUpdateTime   time.Time          `json:"last_update_time"`
}

// ClassroomMetrics represents aggregated metrics for a classroom
type ClassroomMetrics struct {
	ClassroomID          string
	TotalStudents        int
	ActiveStudents       int
	AverageHealthScore   float64
	StruggleStudents     []StruggleStudentInfo
	LastUpdateTime       time.Time
	ClassroomHealthTrend string // 'improving', 'stable', 'degrading'
}

// StruggleStudentInfo contains information about a struggling student
type StruggleStudentInfo struct {
	StudentID        string
	HealthScore      float64
	FrustrationLevel string
	IssueDescription string
	RecommendedAction string
}

// MetricType constants
const (
	MetricTypeResponseTime = "response_time"
	MetricTypeAccuracy     = "accuracy"
	MetricTypeErrors       = "errors"
	MetricTypeAttempts     = "attempts"
	MetricTypeProgress     = "progress"
)

// FrustrationLevel constants
const (
	FrustrationLevelLow    = "low"
	FrustrationLevelMedium = "medium"
	FrustrationLevelHigh   = "high"
	FrustrationLevelCritical = "critical"
)

// HealthScore ranges
const (
	HealthScoreExcellent = 80.0  // 80-100
	HealthScoreGood      = 60.0  // 60-79
	HealthScoreAverage   = 40.0  // 40-59
	HealthScorePoor      = 20.0  // 20-39
	HealthScoreCritical  = 0.0   // 0-19
)

// TimeNow returns current time for use in models
func TimeNow() time.Time {
	return time.Now()
}
