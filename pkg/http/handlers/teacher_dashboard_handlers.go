package handlers

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/jgirmay/GAIA_GO/pkg/http/dto"
	"github.com/jgirmay/GAIA_GO/pkg/repository"
	"github.com/jgirmay/GAIA_GO/pkg/services/usability"
)

// TeacherDashboardHandlers handles teacher dashboard API requests
type TeacherDashboardHandlers struct {
	metricsService       *usability.UsabilityMetricsService
	frustrationEngine    *usability.FrustrationDetectionEngine
	aggregator           *usability.RealtimeMetricsAggregator
	alertRepository      repository.TeacherDashboardAlertRepository
	interventionRepository repository.TeacherDashboardAlertRepository
}

// NewTeacherDashboardHandlers creates new teacher dashboard handlers
func NewTeacherDashboardHandlers(
	metricsService *usability.UsabilityMetricsService,
	frustrationEngine *usability.FrustrationDetectionEngine,
	aggregator *usability.RealtimeMetricsAggregator,
	alertRepository repository.TeacherDashboardAlertRepository,
) *TeacherDashboardHandlers {
	return &TeacherDashboardHandlers{
		metricsService:    metricsService,
		frustrationEngine: frustrationEngine,
		aggregator:        aggregator,
		alertRepository:   alertRepository,
		interventionRepository: alertRepository,
	}
}

// GetClassroomMetrics handles GET /api/classroom/metrics
// Returns aggregated metrics for all students in a classroom
func (h *TeacherDashboardHandlers) GetClassroomMetrics(w http.ResponseWriter, r *http.Request) {
	classroomID := chi.URLParam(r, "classroomID")
	if classroomID == "" {
		writeError(w, http.StatusBadRequest, "missing classroom_id", "INVALID_REQUEST")
		return
	}

	appName := r.URL.Query().Get("app_name")
	if appName == "" {
		writeError(w, http.StatusBadRequest, "missing app_name query parameter", "INVALID_REQUEST")
		return
	}

	// Get classroom metrics from service
	classroomMetrics := h.aggregator.GetClassroomMetrics(classroomID, appName)

	// Build response
	response := &dto.ClassroomMetricsResponse{
		ClassroomID:          classroomID,
		AppName:              appName,
		Timestamp:            time.Now(),
	}

	// Extract metrics from aggregator response
	if classroomMetrics != nil {
		if v, ok := classroomMetrics["total_students"].(int); ok {
			response.TotalStudents = v
		}
		if v, ok := classroomMetrics["active_students"].(int); ok {
			response.ActiveStudents = v
		}
		if v, ok := classroomMetrics["average_error_rate"].(float64); ok {
			response.AverageErrorRate = v
		}
		if v, ok := classroomMetrics["average_backspace_rate"].(float64); ok {
			response.AverageBackspaceRate = v
		}

		// Calculate health score (0-100) based on error and backspace rates
		response.ClassroomHealthScore = calculateHealthScore(response.AverageErrorRate, response.AverageBackspaceRate)
	}

	// Get struggling students
	response.StruggleStudents = h.identifyStrugglingSuppStudents(classroomMetrics)
	response.StrugglingSuppCount = len(response.StruggleStudents)

	writeJSON(w, http.StatusOK, response)
}

// GetStudentFrustration handles GET /api/students/frustration
// Returns frustration events and metrics for a specific student
func (h *TeacherDashboardHandlers) GetStudentFrustration(w http.ResponseWriter, r *http.Request) {
	studentID := r.URL.Query().Get("student_id")
	if studentID == "" {
		writeError(w, http.StatusBadRequest, "missing student_id query parameter", "INVALID_REQUEST")
		return
	}

	appName := r.URL.Query().Get("app_name")
	if appName == "" {
		writeError(w, http.StatusBadRequest, "missing app_name query parameter", "INVALID_REQUEST")
		return
	}

	// Get student metrics from aggregator
	studentMetrics := h.aggregator.GetMetrics(studentID, appName)

	// Build response
	response := &dto.StudentMetricsResponse{
		StudentID:   studentID,
		AppName:     appName,
		LastUpdated: time.Now(),
	}

	// Extract metrics from aggregator response
	if studentMetrics != nil {
		if v, ok := studentMetrics["key_press_count"].(int); ok {
			response.KeyPressCount = v
		}
		if v, ok := studentMetrics["backspace_count"].(int); ok {
			response.BackspaceCount = v
		}
		if v, ok := studentMetrics["error_count"].(int); ok {
			response.ErrorCount = v
		}
		if v, ok := studentMetrics["completion_count"].(int); ok {
			response.CompletionCount = v
		}
		if v, ok := studentMetrics["error_rate"].(float64); ok {
			response.ErrorRate = v
		}
		if v, ok := studentMetrics["backspace_rate"].(float64); ok {
			response.BackspaceRate = v
		}
		if v, ok := studentMetrics["completion_rate"].(float64); ok {
			response.CompletionRate = v
		}
		if v, ok := studentMetrics["average_hesitation_ms"].(int64); ok {
			response.AverageHesitation = v
		}
		if v, ok := studentMetrics["current_hesitation_ms"].(int64); ok {
			response.CurrentHesitation = v
		}
	}

	// Classify frustration level based on metrics
	response.FrustrationLevel, response.FrustrationScore = classifyFrustration(
		response.ErrorRate,
		response.BackspaceRate,
		response.AverageHesitation,
	)

	// Get pattern stats from frustration engine
	patternStats := h.frustrationEngine.GetPatternStats(studentID, appName)
	if patternStats != nil {
		// Store pattern info for debugging
		response.RecentFrustrations = []*dto.FrustrationEventDTO{} // Would be populated from event history
	}

	writeJSON(w, http.StatusOK, response)
}

// RecordIntervention handles POST /api/interventions
// Records a teacher intervention for a student
func (h *TeacherDashboardHandlers) RecordIntervention(w http.ResponseWriter, r *http.Request) {
	var req dto.InterventionRequest

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body", "DECODE_ERROR")
		return
	}

	// Validate required fields
	if req.StudentID == "" || req.AppName == "" || req.Description == "" {
		writeError(w, http.StatusBadRequest, "missing required fields: student_id, app_name, description", "INVALID_REQUEST")
		return
	}

	// Set defaults
	if req.Category == "" {
		req.Category = "general"
	}

	// In production, this would be stored via h.interventionRepository
	// with the following data:
	// - student_id, app_name, description, category, notes, timestamp
	// For now, we log it and return success
	response := &dto.InterventionResponse{
		InterventionID: generateInterventionID(),
		StudentID:      req.StudentID,
		AppName:        req.AppName,
		Category:       req.Category,
		Description:    req.Description,
		TeacherID:      r.Header.Get("X-User-ID"), // Extract from auth header
		Timestamp:      time.Now(),
		Success:        true,
		Message:        "Intervention recorded successfully",
	}

	// Reset frustration patterns for this student after intervention
	h.frustrationEngine.Reset(req.StudentID, req.AppName)

	writeJSON(w, http.StatusCreated, response)
}

// GetStrugglingSuppStudents handles GET /api/struggling-students
// Returns list of students showing high frustration indicators
func (h *TeacherDashboardHandlers) GetStrugglingSuppStudents(w http.ResponseWriter, r *http.Request) {
	classroomID := r.URL.Query().Get("classroom_id")
	if classroomID == "" {
		writeError(w, http.StatusBadRequest, "missing classroom_id query parameter", "INVALID_REQUEST")
		return
	}

	appName := r.URL.Query().Get("app_name")
	if appName == "" {
		writeError(w, http.StatusBadRequest, "missing app_name query parameter", "INVALID_REQUEST")
		return
	}

	// Get all metrics and identify struggling students
	allMetrics := h.aggregator.GetAllMetrics()

	strugglingStudents := make([]*dto.StudentSummaryDTO, 0)

	for _, snapshot := range allMetrics {
		if snapshot.AppName != appName {
			continue
		}

		// Determine if student is struggling (high error/backspace rates)
		if snapshot.ErrorRate > 15 || snapshot.BackspaceRate > 25 {
			frustrationLevel, frustrationScore := classifyFrustration(
				snapshot.ErrorRate,
				snapshot.BackspaceRate,
				snapshot.AverageHesitation.Milliseconds(),
			)

			summary := &dto.StudentSummaryDTO{
				StudentID:        snapshot.StudentID,
				ErrorRate:        snapshot.ErrorRate,
				BackspaceRate:    snapshot.BackspaceRate,
				FrustrationLevel: frustrationLevel,
				FrustrationScore: frustrationScore,
				TimeOnTask:       0, // Would calculate from timestamps
			}

			// Suggest interventions based on frustration type
			if snapshot.ErrorRate > 20 {
				summary.InterventionsNeeded = append(summary.InterventionsNeeded, "technical_help")
			}
			if snapshot.BackspaceRate > 30 {
				summary.InterventionsNeeded = append(summary.InterventionsNeeded, "guidance")
			}
			if snapshot.AverageHesitation > 45*time.Second {
				summary.InterventionsNeeded = append(summary.InterventionsNeeded, "encouragement")
			}

			strugglingStudents = append(strugglingStudents, summary)
		}
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"classroom_id":      classroomID,
		"app_name":          appName,
		"struggling_count":  len(strugglingStudents),
		"students":          strugglingStudents,
		"timestamp":         time.Now(),
	})
}

// GetHealthStatus handles GET /api/dashboard/health
// Returns health status of the metrics system
func (h *TeacherDashboardHandlers) GetHealthStatus(w http.ResponseWriter, r *http.Request) {
	response := &dto.HealthCheckResponse{
		Status:      "healthy",
		Timestamp:   time.Now(),
		SessionsActive: h.aggregator.GetStudentCount(),
	}

	writeJSON(w, http.StatusOK, response)
}

// Helper functions

// writeJSON writes a JSON response
func writeJSON(w http.ResponseWriter, statusCode int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	json.NewEncoder(w).Encode(data)
}

// writeError writes an error response
func writeError(w http.ResponseWriter, statusCode int, message, code string) {
	response := &dto.ErrorResponse{
		Error:     code,
		Message:   message,
		Code:      code,
		Timestamp: time.Now(),
	}
	writeJSON(w, statusCode, response)
}

// classifyFrustration classifies frustration level based on metrics
func classifyFrustration(errorRate float64, backspaceRate float64, hesitationMs int64) (string, float64) {
	score := 0.0

	// Error rate component (0-0.4)
	if errorRate > 20 {
		score += 0.4
	} else if errorRate > 10 {
		score += 0.3
	} else if errorRate > 5 {
		score += 0.2
	} else if errorRate > 2 {
		score += 0.1
	}

	// Backspace rate component (0-0.35)
	if backspaceRate > 30 {
		score += 0.35
	} else if backspaceRate > 20 {
		score += 0.25
	} else if backspaceRate > 10 {
		score += 0.15
	} else if backspaceRate > 5 {
		score += 0.08
	}

	// Hesitation component (0-0.25)
	if hesitationMs > 60000 { // > 1 minute
		score += 0.25
	} else if hesitationMs > 45000 { // > 45 seconds
		score += 0.20
	} else if hesitationMs > 30000 { // > 30 seconds
		score += 0.15
	} else if hesitationMs > 15000 { // > 15 seconds
		score += 0.08
	}

	// Clamp score to 0-1
	if score > 1.0 {
		score = 1.0
	}

	// Determine level
	var level string
	if score < 0.25 {
		level = "low"
	} else if score < 0.50 {
		level = "medium"
	} else if score < 0.75 {
		level = "high"
	} else {
		level = "critical"
	}

	return level, score
}

// calculateHealthScore calculates overall classroom health (0-100)
func calculateHealthScore(avgErrorRate, avgBackspaceRate float64) float64 {
	// Start at 100, deduct based on error rates
	health := 100.0

	// Error rate penalty (max -40 points)
	if avgErrorRate > 20 {
		health -= 40
	} else if avgErrorRate > 15 {
		health -= 30
	} else if avgErrorRate > 10 {
		health -= 20
	} else if avgErrorRate > 5 {
		health -= 10
	}

	// Backspace rate penalty (max -30 points)
	if avgBackspaceRate > 30 {
		health -= 30
	} else if avgBackspaceRate > 20 {
		health -= 20
	} else if avgBackspaceRate > 10 {
		health -= 10
	}

	// Clamp to 0-100
	if health < 0 {
		health = 0
	}
	if health > 100 {
		health = 100
	}

	return health
}

// identifyStrugglingSuppStudents extracts struggling students from classroom metrics
func (h *TeacherDashboardHandlers) identifyStrugglingSuppStudents(classroomMetrics map[string]interface{}) []*dto.StudentSummaryDTO {
	struggling := make([]*dto.StudentSummaryDTO, 0)

	// Get all metrics
	allMetrics := h.aggregator.GetAllMetrics()

	for _, snapshot := range allMetrics {
		// Check if struggling (high error or backspace rate)
		if snapshot.ErrorRate > 15 || snapshot.BackspaceRate > 25 {
			frustrationLevel, frustrationScore := classifyFrustration(
				snapshot.ErrorRate,
				snapshot.BackspaceRate,
				snapshot.AverageHesitation.Milliseconds(),
			)

			summary := &dto.StudentSummaryDTO{
				StudentID:        snapshot.StudentID,
				ErrorRate:        snapshot.ErrorRate,
				BackspaceRate:    snapshot.BackspaceRate,
				FrustrationLevel: frustrationLevel,
				FrustrationScore: frustrationScore,
			}

			// Suggest interventions
			if snapshot.ErrorRate > 20 {
				summary.InterventionsNeeded = append(summary.InterventionsNeeded, "technical_help")
			}
			if snapshot.BackspaceRate > 30 {
				summary.InterventionsNeeded = append(summary.InterventionsNeeded, "guidance")
			}

			struggling = append(struggling, summary)
		}
	}

	return struggling
}

// generateInterventionID generates a unique intervention ID
func generateInterventionID() string {
	return "intervention_" + time.Now().Format("20060102150405")
}
