package handlers

import (
	"encoding/json"
	"io"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/jgirmay/GAIA_GO/pkg/legacy"
)

// LegacyCompatibilityHandler handles legacy Python API requests
type LegacyCompatibilityHandler struct {
	adapter *legacy.APIAdapter
}

// NewLegacyCompatibilityHandler creates a new legacy compatibility handler
func NewLegacyCompatibilityHandler(
	sessionRepo legacy.ClaudeSessionRepository,
	lessonRepo legacy.LessonRepository,
	config *legacy.MigrationConfig,
) *LegacyCompatibilityHandler {
	adapter := legacy.NewAPIAdapter(sessionRepo, lessonRepo, config)
	return &LegacyCompatibilityHandler{
		adapter: adapter,
	}
}

// RegisterLegacyRoutes registers all legacy API routes on the chi router
func (lch *LegacyCompatibilityHandler) RegisterLegacyRoutes(router chi.Router) {
	// Legacy API endpoints that map to GAIA_HOME Python API
	// These routes support both old and new format requests

	// Sessions endpoints
	router.HandleFunc("GET /api/sessions", lch.ListSessions)
	router.HandleFunc("POST /api/sessions", lch.CreateSession)
	router.HandleFunc("GET /api/sessions/{sessionID}", lch.GetSession)
	router.HandleFunc("PUT /api/sessions/{sessionID}", lch.UpdateSession)
	router.HandleFunc("DELETE /api/sessions/{sessionID}", lch.DeleteSession)

	// Lessons endpoints
	router.HandleFunc("GET /api/lessons", lch.ListLessons)
	router.HandleFunc("POST /api/lessons", lch.CreateLesson)
	router.HandleFunc("GET /api/lessons/{lessonID}", lch.GetLesson)
	router.HandleFunc("PUT /api/lessons/{lessonID}", lch.UpdateLesson)
	router.HandleFunc("DELETE /api/lessons/{lessonID}", lch.DeleteLesson)

	// Errors endpoint (legacy error logging)
	router.HandleFunc("POST /api/errors", lch.LogError)
	router.HandleFunc("GET /api/errors", lch.ListErrors)

	// Health check
	router.HandleFunc("GET /api/health", lch.HealthCheck)

	// Migration monitoring endpoints
	router.HandleFunc("GET /api/legacy/migration/metrics", lch.GetMigrationMetrics)
	router.HandleFunc("GET /api/legacy/migration/requests", lch.GetRequestLog)
	router.HandleFunc("GET /api/legacy/migration/requests/{requestID}", lch.GetRequestLogEntry)
}

// ListSessions handles GET /api/sessions
func (lch *LegacyCompatibilityHandler) ListSessions(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	legacyReq := &legacy.LegacyRequest{
		Method:    r.Method,
		Endpoint:  r.RequestURI,
		Headers:   extractHeaders(r),
		ClientID:  getClientID(r),
		Timestamp: now(),
	}

	response, err := lch.adapter.HandleRequest(ctx, legacyReq)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	sendLegacyResponse(w, response)
}

// GetSession handles GET /api/sessions/{sessionID}
func (lch *LegacyCompatibilityHandler) GetSession(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	sessionID := chi.URLParam(r, "sessionID")

	legacyReq := &legacy.LegacyRequest{
		Method:    r.Method,
		Endpoint:  "/api/sessions/" + sessionID,
		Headers:   extractHeaders(r),
		ClientID:  getClientID(r),
		Timestamp: now(),
	}

	response, err := lch.adapter.HandleRequest(ctx, legacyReq)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	sendLegacyResponse(w, response)
}

// CreateSession handles POST /api/sessions
func (lch *LegacyCompatibilityHandler) CreateSession(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	// Parse request body
	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "Failed to read request body", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	var bodyData map[string]interface{}
	if err := json.Unmarshal(body, &bodyData); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	legacyReq := &legacy.LegacyRequest{
		Method:    r.Method,
		Endpoint:  "/api/sessions",
		Headers:   extractHeaders(r),
		Body:      bodyData,
		ClientID:  getClientID(r),
		Timestamp: now(),
	}

	response, err := lch.adapter.HandleRequest(ctx, legacyReq)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	sendLegacyResponse(w, response)
}

// UpdateSession handles PUT /api/sessions/{sessionID}
func (lch *LegacyCompatibilityHandler) UpdateSession(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	sessionID := chi.URLParam(r, "sessionID")

	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "Failed to read request body", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	var bodyData map[string]interface{}
	if err := json.Unmarshal(body, &bodyData); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	legacyReq := &legacy.LegacyRequest{
		Method:    r.Method,
		Endpoint:  "/api/sessions/" + sessionID,
		Headers:   extractHeaders(r),
		Body:      bodyData,
		ClientID:  getClientID(r),
		Timestamp: now(),
	}

	response, err := lch.adapter.HandleRequest(ctx, legacyReq)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	sendLegacyResponse(w, response)
}

// DeleteSession handles DELETE /api/sessions/{sessionID}
func (lch *LegacyCompatibilityHandler) DeleteSession(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	sessionID := chi.URLParam(r, "sessionID")

	legacyReq := &legacy.LegacyRequest{
		Method:    r.Method,
		Endpoint:  "/api/sessions/" + sessionID,
		Headers:   extractHeaders(r),
		ClientID:  getClientID(r),
		Timestamp: now(),
	}

	response, err := lch.adapter.HandleRequest(ctx, legacyReq)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	sendLegacyResponse(w, response)
}

// Lesson handlers

// ListLessons handles GET /api/lessons
func (lch *LegacyCompatibilityHandler) ListLessons(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	legacyReq := &legacy.LegacyRequest{
		Method:    r.Method,
		Endpoint:  "/api/lessons",
		Headers:   extractHeaders(r),
		ClientID:  getClientID(r),
		Timestamp: now(),
	}

	response, err := lch.adapter.HandleRequest(ctx, legacyReq)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	sendLegacyResponse(w, response)
}

// GetLesson handles GET /api/lessons/{lessonID}
func (lch *LegacyCompatibilityHandler) GetLesson(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	lessonID := chi.URLParam(r, "lessonID")

	legacyReq := &legacy.LegacyRequest{
		Method:    r.Method,
		Endpoint:  "/api/lessons/" + lessonID,
		Headers:   extractHeaders(r),
		ClientID:  getClientID(r),
		Timestamp: now(),
	}

	response, err := lch.adapter.HandleRequest(ctx, legacyReq)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	sendLegacyResponse(w, response)
}

// CreateLesson handles POST /api/lessons
func (lch *LegacyCompatibilityHandler) CreateLesson(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "Failed to read request body", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	var bodyData map[string]interface{}
	if err := json.Unmarshal(body, &bodyData); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	legacyReq := &legacy.LegacyRequest{
		Method:    r.Method,
		Endpoint:  "/api/lessons",
		Headers:   extractHeaders(r),
		Body:      bodyData,
		ClientID:  getClientID(r),
		Timestamp: now(),
	}

	response, err := lch.adapter.HandleRequest(ctx, legacyReq)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	sendLegacyResponse(w, response)
}

// UpdateLesson handles PUT /api/lessons/{lessonID}
func (lch *LegacyCompatibilityHandler) UpdateLesson(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	lessonID := chi.URLParam(r, "lessonID")

	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "Failed to read request body", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	var bodyData map[string]interface{}
	if err := json.Unmarshal(body, &bodyData); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	legacyReq := &legacy.LegacyRequest{
		Method:    r.Method,
		Endpoint:  "/api/lessons/" + lessonID,
		Headers:   extractHeaders(r),
		Body:      bodyData,
		ClientID:  getClientID(r),
		Timestamp: now(),
	}

	response, err := lch.adapter.HandleRequest(ctx, legacyReq)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	sendLegacyResponse(w, response)
}

// DeleteLesson handles DELETE /api/lessons/{lessonID}
func (lch *LegacyCompatibilityHandler) DeleteLesson(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	lessonID := chi.URLParam(r, "lessonID")

	legacyReq := &legacy.LegacyRequest{
		Method:    r.Method,
		Endpoint:  "/api/lessons/" + lessonID,
		Headers:   extractHeaders(r),
		ClientID:  getClientID(r),
		Timestamp: now(),
	}

	response, err := lch.adapter.HandleRequest(ctx, legacyReq)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	sendLegacyResponse(w, response)
}

// LogError handles POST /api/errors
func (lch *LegacyCompatibilityHandler) LogError(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusAccepted)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status": "logged",
		"message": "Error logged successfully",
	})
}

// ListErrors handles GET /api/errors
func (lch *LegacyCompatibilityHandler) ListErrors(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode([]map[string]interface{}{})
}

// HealthCheck handles GET /api/health
func (lch *LegacyCompatibilityHandler) HealthCheck(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":    "healthy",
		"timestamp": now().Format("2006-01-02T15:04:05Z07:00"),
		"version":   "1.0.0",
	})
}

// GetMigrationMetrics returns statistics about legacy API usage
func (lch *LegacyCompatibilityHandler) GetMigrationMetrics(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(lch.adapter.GetMigrationMetrics())
}

// GetRequestLog returns all logged legacy requests
func (lch *LegacyCompatibilityHandler) GetRequestLog(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(lch.adapter.GetRequestLog())
}

// GetRequestLogEntry returns a specific request log entry
func (lch *LegacyCompatibilityHandler) GetRequestLogEntry(w http.ResponseWriter, r *http.Request) {
	requestID := chi.URLParam(r, "requestID")

	entry := lch.adapter.GetRequestLog()
	if len(entry) == 0 {
		http.Error(w, "Not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"request_id": requestID,
		"message":    "Request log entry for migration tracking",
	})
}

// Helper functions

func extractHeaders(r *http.Request) map[string]string {
	headers := make(map[string]string)
	for key, values := range r.Header {
		if len(values) > 0 {
			headers[key] = values[0]
		}
	}
	return headers
}

func getClientID(r *http.Request) string {
	// Try to get client ID from various sources
	if clientID := r.Header.Get("X-Client-ID"); clientID != "" {
		return clientID
	}
	if userAgent := r.Header.Get("User-Agent"); userAgent != "" {
		return userAgent
	}
	return r.RemoteAddr
}

func sendLegacyResponse(w http.ResponseWriter, response *legacy.LegacyResponse) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("X-Legacy-API-Response", "true")

	// Set status code
	if response.StatusCode > 0 {
		w.WriteHeader(response.StatusCode)
	} else {
		w.WriteHeader(http.StatusOK)
	}

	// Add any additional headers
	for key, value := range response.Headers {
		w.Header().Set(key, value)
	}

	// Send body
	if response.Body != nil {
		json.NewEncoder(w).Encode(response.Body)
	}
}

// now returns current time (extracted for testability)
func now() time.Time {
	return time.Now()
}
