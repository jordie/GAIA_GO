package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
	"github.com/jgirmay/GAIA_GO/pkg/http/dto"
	"github.com/jgirmay/GAIA_GO/pkg/services/usability"
)

// Helper to create a route context with URL params
func createRouteContext(r *http.Request, params map[string]string) *http.Request {
	ctx := chi.NewRouteContext()
	for k, v := range params {
		ctx.URLParams.Add(k, v)
	}
	return r.WithContext(context.WithValue(r.Context(), chi.RouteCtxKey, ctx))
}

// SimpleEventBus is a minimal EventBus implementation for testing
type SimpleEventBus struct{}

func (e *SimpleEventBus) PublishFrustrationEvent(event *usability.FrustrationEvent)       {}
func (e *SimpleEventBus) PublishSatisfactionRating(studentID, appName string, rating int, feedback string) {}
func (e *SimpleEventBus) PublishMetricEvent(metric *usability.Metric)                     {}
func (e *SimpleEventBus) Subscribe(listener usability.FrustrationEventListener)           {}
func (e *SimpleEventBus) Unsubscribe(listener usability.FrustrationEventListener)         {}
func (e *SimpleEventBus) Close()                                                          {}

// SimpleRepository is a minimal repository implementation for testing
type SimpleRepository struct {
	metrics []interface{}
}

func (r *SimpleRepository) RecordMetric(ctx context.Context, metricData interface{}) error {
	r.metrics = append(r.metrics, metricData)
	return nil
}

func (r *SimpleRepository) GetStudentMetrics(ctx context.Context, studentID, appName string, since time.Time) ([]interface{}, error) {
	return r.metrics, nil
}

func (r *SimpleRepository) GetClassroomMetrics(ctx context.Context, classroomID, appName string) (map[string]interface{}, error) {
	return map[string]interface{}{}, nil
}

func (r *SimpleRepository) GetMetricsByType(ctx context.Context, sessionID string, since time.Time) ([]interface{}, error) {
	return r.metrics, nil
}

// Test helper to create a test handler instance with real services
func newTestHandlers() *TeacherDashboardHandlers {
	frustrationEngine := usability.NewFrustrationDetectionEngine(nil)
	aggregator := usability.NewRealtimeMetricsAggregator(time.Minute)
	eventBus := &SimpleEventBus{}
	repo := &SimpleRepository{}

	metricsService := usability.NewUsabilityMetricsService(
		repo,
		frustrationEngine,
		aggregator,
		eventBus,
		usability.DefaultConfig(),
	)

	alertRepo := &TestAlertRepository{}

	return NewTeacherDashboardHandlers(
		metricsService,
		frustrationEngine,
		aggregator,
		alertRepo,
	)
}

// TestAlertRepository is a simple test implementation
type TestAlertRepository struct {
	alerts map[string]interface{}
}

func (t *TestAlertRepository) Create(ctx context.Context, alert interface{}) error {
	if t.alerts == nil {
		t.alerts = make(map[string]interface{})
	}
	t.alerts["test"] = alert
	return nil
}

func (t *TestAlertRepository) GetForTeacher(ctx context.Context, teacherID uuid.UUID) ([]interface{}, error) {
	return []interface{}{}, nil
}

func (t *TestAlertRepository) GetUnacknowledged(ctx context.Context) ([]interface{}, error) {
	return []interface{}{}, nil
}

func (t *TestAlertRepository) Acknowledge(ctx context.Context, id uuid.UUID, note string) error {
	return nil
}

func (t *TestAlertRepository) GetStrugglingStudents(ctx context.Context, appName string) ([]string, error) {
	return []string{}, nil
}

func (t *TestAlertRepository) DeleteOld(ctx context.Context, olderThan time.Duration) error {
	return nil
}

// Test 1: GetClassroomMetrics returns classroom data
func TestGetClassroomMetrics_ValidResponse(t *testing.T) {
	handlers := newTestHandlers()

	req := httptest.NewRequest("GET", "/api/dashboard/classroom/class-1/metrics?app_name=typing-app", nil)
	req = createRouteContext(req, map[string]string{"classroomID": "class-1"})

	w := httptest.NewRecorder()
	handlers.GetClassroomMetrics(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", w.Code)
	}

	var response dto.ClassroomMetricsResponse
	if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
		t.Fatalf("Failed to decode response: %v", err)
	}

	if response.ClassroomID != "class-1" {
		t.Errorf("Expected classroom ID 'class-1', got '%s'", response.ClassroomID)
	}

	if response.AppName != "typing-app" {
		t.Errorf("Expected app name 'typing-app', got '%s'", response.AppName)
	}
}

// Test 2: GetClassroomMetrics requires classroom ID
func TestGetClassroomMetrics_MissingClassroomID(t *testing.T) {
	handlers := newTestHandlers()

	req := httptest.NewRequest("GET", "/api/dashboard/classroom//metrics?app_name=app1", nil)
	w := httptest.NewRecorder()
	handlers.GetClassroomMetrics(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("Expected status 400, got %d", w.Code)
	}
}

// Test 3: GetClassroomMetrics requires app_name parameter
func TestGetClassroomMetrics_MissingAppName(t *testing.T) {
	handlers := newTestHandlers()

	req := httptest.NewRequest("GET", "/api/dashboard/classroom/class-1/metrics", nil)
	req = createRouteContext(req, map[string]string{"classroomID": "class-1"})

	w := httptest.NewRecorder()
	handlers.GetClassroomMetrics(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("Expected status 400, got %d", w.Code)
	}
}

// Test 4: GetStudentFrustration returns student metrics
func TestGetStudentFrustration_ValidResponse(t *testing.T) {
	handlers := newTestHandlers()

	req := httptest.NewRequest("GET", "/api/dashboard/student/frustration?student_id=student-1&app_name=typing-app", nil)
	w := httptest.NewRecorder()
	handlers.GetStudentFrustration(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", w.Code)
	}

	var response dto.StudentMetricsResponse
	if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
		t.Fatalf("Failed to decode response: %v", err)
	}

	if response.StudentID != "student-1" {
		t.Errorf("Expected student ID 'student-1', got '%s'", response.StudentID)
	}

	if response.AppName != "typing-app" {
		t.Errorf("Expected app name 'typing-app', got '%s'", response.AppName)
	}
}

// Test 5: GetStudentFrustration requires student_id
func TestGetStudentFrustration_MissingStudentID(t *testing.T) {
	handlers := newTestHandlers()

	req := httptest.NewRequest("GET", "/api/dashboard/student/frustration?app_name=app1", nil)
	w := httptest.NewRecorder()
	handlers.GetStudentFrustration(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("Expected status 400, got %d", w.Code)
	}
}

// Test 6: GetStudentFrustration requires app_name
func TestGetStudentFrustration_MissingAppName(t *testing.T) {
	handlers := newTestHandlers()

	req := httptest.NewRequest("GET", "/api/dashboard/student/frustration?student_id=student-1", nil)
	w := httptest.NewRecorder()
	handlers.GetStudentFrustration(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("Expected status 400, got %d", w.Code)
	}
}

// Test 7: GetStrugglingSuppStudents returns list structure
func TestGetStrugglingSuppStudents_ReturnsStructure(t *testing.T) {
	handlers := newTestHandlers()

	req := httptest.NewRequest("GET", "/api/dashboard/struggling-students?classroom_id=class-1&app_name=typing-app", nil)
	w := httptest.NewRecorder()
	handlers.GetStrugglingSuppStudents(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", w.Code)
	}

	var response map[string]interface{}
	if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
		t.Fatalf("Failed to decode response: %v", err)
	}

	if response["classroom_id"] != "class-1" {
		t.Errorf("Expected classroom ID 'class-1'")
	}

	if response["app_name"] != "typing-app" {
		t.Errorf("Expected app name 'typing-app'")
	}

	if _, ok := response["students"]; !ok {
		t.Error("Expected 'students' key in response")
	}
}

// Test 8: GetStrugglingSuppStudents requires classroom_id
func TestGetStrugglingSuppStudents_MissingClassroomID(t *testing.T) {
	handlers := newTestHandlers()

	req := httptest.NewRequest("GET", "/api/dashboard/struggling-students?app_name=app1", nil)
	w := httptest.NewRecorder()
	handlers.GetStrugglingSuppStudents(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("Expected status 400, got %d", w.Code)
	}
}

// Test 9: GetStrugglingSuppStudents requires app_name
func TestGetStrugglingSuppStudents_MissingAppName(t *testing.T) {
	handlers := newTestHandlers()

	req := httptest.NewRequest("GET", "/api/dashboard/struggling-students?classroom_id=class-1", nil)
	w := httptest.NewRecorder()
	handlers.GetStrugglingSuppStudents(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("Expected status 400, got %d", w.Code)
	}
}

// Test 10: RecordIntervention requires valid JSON
func TestRecordIntervention_ValidRequest(t *testing.T) {
	handlers := newTestHandlers()

	interventionReq := dto.InterventionRequest{
		StudentID:   "student-1",
		AppName:     "typing-app",
		Description: "Student needs encouragement",
		Category:    "encouragement",
	}

	body, _ := json.Marshal(interventionReq)
	req := httptest.NewRequest("POST", "/api/dashboard/interventions", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-User-ID", "teacher-1")

	w := httptest.NewRecorder()
	handlers.RecordIntervention(w, req)

	if w.Code != http.StatusCreated {
		t.Errorf("Expected status 201, got %d: %s", w.Code, w.Body.String())
	}

	var response dto.InterventionResponse
	if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
		t.Fatalf("Failed to decode response: %v", err)
	}

	if response.StudentID != "student-1" {
		t.Errorf("Expected student ID 'student-1', got '%s'", response.StudentID)
	}

	if !response.Success {
		t.Error("Expected intervention to be recorded successfully")
	}
}

// Test 11: RecordIntervention requires student_id
func TestRecordIntervention_MissingStudentID(t *testing.T) {
	handlers := newTestHandlers()

	interventionReq := dto.InterventionRequest{
		AppName:     "app1",
		Description: "Help needed",
		Category:    "help",
	}

	body, _ := json.Marshal(interventionReq)
	req := httptest.NewRequest("POST", "/api/dashboard/interventions", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	handlers.RecordIntervention(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("Expected status 400, got %d", w.Code)
	}
}

// Test 12: RecordIntervention requires app_name
func TestRecordIntervention_MissingAppName(t *testing.T) {
	handlers := newTestHandlers()

	interventionReq := dto.InterventionRequest{
		StudentID:   "student-1",
		Description: "Help needed",
		Category:    "help",
	}

	body, _ := json.Marshal(interventionReq)
	req := httptest.NewRequest("POST", "/api/dashboard/interventions", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	handlers.RecordIntervention(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("Expected status 400, got %d", w.Code)
	}
}

// Test 13: RecordIntervention requires description
func TestRecordIntervention_MissingDescription(t *testing.T) {
	handlers := newTestHandlers()

	interventionReq := dto.InterventionRequest{
		StudentID: "student-1",
		AppName:   "app1",
		Category:  "help",
	}

	body, _ := json.Marshal(interventionReq)
	req := httptest.NewRequest("POST", "/api/dashboard/interventions", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	handlers.RecordIntervention(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("Expected status 400, got %d", w.Code)
	}
}

// Test 14: RecordIntervention rejects invalid JSON
func TestRecordIntervention_InvalidJSON(t *testing.T) {
	handlers := newTestHandlers()

	req := httptest.NewRequest("POST", "/api/dashboard/interventions", bytes.NewReader([]byte("invalid")))
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	handlers.RecordIntervention(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("Expected status 400, got %d", w.Code)
	}
}

// Test 15: GetHealthStatus returns healthy status
func TestGetHealthStatus_ReturnsHealthy(t *testing.T) {
	handlers := newTestHandlers()

	req := httptest.NewRequest("GET", "/api/dashboard/health", nil)
	w := httptest.NewRecorder()
	handlers.GetHealthStatus(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", w.Code)
	}

	var response dto.HealthCheckResponse
	if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
		t.Fatalf("Failed to decode response: %v", err)
	}

	if response.Status != "healthy" {
		t.Errorf("Expected status 'healthy', got '%s'", response.Status)
	}
}

// Test 16: classifyFrustration calculates low frustration correctly
func TestClassifyFrustration_Low(t *testing.T) {
	level, score := classifyFrustration(1.0, 3.0, 1000)

	if level != "low" {
		t.Errorf("Expected level 'low', got '%s'", level)
	}

	if score > 0.25 {
		t.Errorf("Expected score < 0.25, got %v", score)
	}
}

// Test 17: classifyFrustration calculates medium frustration correctly
func TestClassifyFrustration_Medium(t *testing.T) {
	level, score := classifyFrustration(8.0, 12.0, 20000)

	if level != "medium" {
		t.Errorf("Expected level 'medium', got '%s'", level)
	}

	if score < 0.25 || score > 0.50 {
		t.Errorf("Expected score in range 0.25-0.50, got %v", score)
	}
}

// Test 18: classifyFrustration calculates high frustration correctly
func TestClassifyFrustration_High(t *testing.T) {
	level, score := classifyFrustration(12.0, 22.0, 40000)

	if level != "high" {
		t.Errorf("Expected level 'high', got '%s'", level)
	}

	if score < 0.50 || score > 0.75 {
		t.Errorf("Expected score in range 0.50-0.75, got %v", score)
	}
}

// Test 19: classifyFrustration calculates critical frustration correctly
func TestClassifyFrustration_Critical(t *testing.T) {
	level, score := classifyFrustration(25.0, 35.0, 70000)

	if level != "critical" {
		t.Errorf("Expected level 'critical', got '%s'", level)
	}

	if score < 0.75 {
		t.Errorf("Expected score >= 0.75, got %v", score)
	}
}

// Test 20: calculateHealthScore for healthy classroom
func TestCalculateHealthScore_Healthy(t *testing.T) {
	score := calculateHealthScore(3.0, 8.0)

	if score < 70 || score > 100 {
		t.Errorf("Expected health score > 70 for healthy classroom, got %v", score)
	}
}

// Test 21: calculateHealthScore for struggling classroom
func TestCalculateHealthScore_Struggling(t *testing.T) {
	score := calculateHealthScore(20.0, 30.0)

	if score > 60 {
		t.Errorf("Expected health score < 60 for struggling classroom, got %v", score)
	}
}

// Test 22: calculateHealthScore clamps to valid range
func TestCalculateHealthScore_ClampsRange(t *testing.T) {
	score := calculateHealthScore(50.0, 50.0) // Extreme values

	if score < 0 || score > 100 {
		t.Errorf("Expected health score in range 0-100, got %v", score)
	}
}

// Test 23: Error responses have correct structure
func TestErrorResponse_Structure(t *testing.T) {
	handlers := newTestHandlers()

	req := httptest.NewRequest("GET", "/api/dashboard/student/frustration", nil)
	w := httptest.NewRecorder()
	handlers.GetStudentFrustration(w, req)

	var errorResp dto.ErrorResponse
	if err := json.NewDecoder(w.Body).Decode(&errorResp); err != nil {
		t.Fatalf("Failed to decode error response: %v", err)
	}

	if errorResp.Error == "" {
		t.Error("Expected error field to be set")
	}

	if errorResp.Message == "" {
		t.Error("Expected message field to be set")
	}
}

// Test 24: RecordIntervention sets default category
func TestRecordIntervention_DefaultCategory(t *testing.T) {
	handlers := newTestHandlers()

	interventionReq := dto.InterventionRequest{
		StudentID:   "student-1",
		AppName:     "app1",
		Description: "Help needed",
		// Category not set
	}

	body, _ := json.Marshal(interventionReq)
	req := httptest.NewRequest("POST", "/api/dashboard/interventions", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	handlers.RecordIntervention(w, req)

	if w.Code != http.StatusCreated {
		t.Errorf("Expected status 201, got %d", w.Code)
	}

	var response dto.InterventionResponse
	json.NewDecoder(w.Body).Decode(&response)

	if response.Category != "general" {
		t.Errorf("Expected default category 'general', got '%s'", response.Category)
	}
}
