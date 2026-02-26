package dto

import (
	"time"
)

// ClassroomMetricsRequest is the request for classroom metrics
type ClassroomMetricsRequest struct {
	ClassroomID string `json:"classroom_id" validate:"required"`
	AppName     string `json:"app_name" validate:"required"`
}

// StudentMetricsRequest is the request for student metrics
type StudentMetricsRequest struct {
	StudentID string `json:"student_id" validate:"required"`
	AppName   string `json:"app_name" validate:"required"`
}

// FrustrationEventsRequest is the request for frustration events
type FrustrationEventsRequest struct {
	Severity  string `json:"severity"`   // optional: filter by severity
	StudentID string `json:"student_id"` // optional: filter by student
	AppName   string `json:"app_name"`   // optional: filter by app
	Limit     int    `json:"limit"`      // default: 50
}

// InterventionRequest is the request to log a teacher intervention
type InterventionRequest struct {
	StudentID   string `json:"student_id" validate:"required"`
	AppName     string `json:"app_name" validate:"required"`
	Description string `json:"description" validate:"required"`
	Category    string `json:"category"`    // e.g., "encouragement", "guidance", "technical_help"
	Notes       string `json:"notes,omitempty"`
}

// InterventionResponse is the response after logging an intervention
type InterventionResponse struct {
	InterventionID string    `json:"intervention_id"`
	StudentID      string    `json:"student_id"`
	AppName        string    `json:"app_name"`
	Category       string    `json:"category"`
	Description    string    `json:"description"`
	TeacherID      string    `json:"teacher_id"`
	Timestamp      time.Time `json:"timestamp"`
	Success        bool      `json:"success"`
	Message        string    `json:"message,omitempty"`
}

// StudentMetricsResponse is the response for student metrics
type StudentMetricsResponse struct {
	StudentID          string                 `json:"student_id"`
	AppName            string                 `json:"app_name"`
	KeyPressCount      int                    `json:"key_press_count"`
	BackspaceCount     int                    `json:"backspace_count"`
	ErrorCount         int                    `json:"error_count"`
	CompletionCount    int                    `json:"completion_count"`
	ErrorRate          float64                `json:"error_rate"`
	BackspaceRate      float64                `json:"backspace_rate"`
	CompletionRate     float64                `json:"completion_rate"`
	AverageHesitation  int64                  `json:"average_hesitation_ms"`
	CurrentHesitation  int64                  `json:"current_hesitation_ms"`
	FrustrationLevel   string                 `json:"frustration_level"`   // low, medium, high, critical
	FrustrationScore   float64                `json:"frustration_score"`   // 0-1
	RecentFrustrations []*FrustrationEventDTO `json:"recent_frustrations"` // last 3 frustration events
	LastUpdated        time.Time              `json:"last_updated"`
}

// FrustrationEventDTO represents a frustration event
type FrustrationEventDTO struct {
	EventID         int64             `json:"event_id"`
	StudentID       string            `json:"student_id"`
	AppName         string            `json:"app_name"`
	EventType       string            `json:"event_type"`
	Severity        string            `json:"severity"`
	ConfidenceScore float64           `json:"confidence_score"`
	Details         map[string]interface{} `json:"details"`
	DetectedAt      time.Time         `json:"detected_at"`
	AcknowledgedAt  *time.Time        `json:"acknowledged_at,omitempty"`
}

// ClassroomMetricsResponse is the response for classroom metrics
type ClassroomMetricsResponse struct {
	ClassroomID           string                     `json:"classroom_id"`
	AppName               string                     `json:"app_name"`
	TotalStudents         int                        `json:"total_students"`
	ActiveStudents        int                        `json:"active_students"`
	AverageErrorRate      float64                    `json:"average_error_rate"`
	AverageBackspaceRate  float64                    `json:"average_backspace_rate"`
	StrugglingSuppCount   int                        `json:"struggling_student_count"`
	StruggleStudents      []*StudentSummaryDTO       `json:"struggling_students"`
	ClassroomHealthScore  float64                    `json:"classroom_health_score"` // 0-100
	RecentFrustrationCount int                      `json:"recent_frustration_count"`
	Timestamp             time.Time                  `json:"timestamp"`
}

// StudentSummaryDTO is a summary of a student's metrics
type StudentSummaryDTO struct {
	StudentID            string    `json:"student_id"`
	ErrorRate            float64   `json:"error_rate"`
	BackspaceRate        float64   `json:"backspace_rate"`
	FrustrationLevel     string    `json:"frustration_level"`
	FrustrationScore     float64   `json:"frustration_score"`
	LastFrustrationEvent *time.Time `json:"last_frustration_event,omitempty"`
	TimeOnTask           int64     `json:"time_on_task_seconds"` // estimated
	InterventionsNeeded  []string  `json:"interventions_needed"` // suggested intervention types
}

// HealthCheckResponse is the response for health checks
type HealthCheckResponse struct {
	Status      string    `json:"status"` // "healthy", "degraded", "unhealthy"
	Timestamp   time.Time `json:"timestamp"`
	Message     string    `json:"message,omitempty"`
	SessionsActive int    `json:"sessions_active"`
	MetricsProcessed int `json:"metrics_processed_today"`
}

// ErrorResponse is a standard error response
type ErrorResponse struct {
	Error      string `json:"error"`
	Code       string `json:"code,omitempty"`
	Message    string `json:"message"`
	Timestamp  time.Time `json:"timestamp"`
}
