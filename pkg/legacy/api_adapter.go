package legacy

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/jgirmay/GAIA_GO/pkg/models"
)

// APIAdapter bridges legacy Python API calls to GAIA_GO
type APIAdapter struct {
	mu              sync.RWMutex
	sessionRepo     ClaudeSessionRepository
	lessonRepo      LessonRepository
	requestLogger   *RequestLogger
	authTranslator  *AuthTranslator
	reqTranslator   *RequestTranslator
	migrationConfig *MigrationConfig
}

// MigrationConfig holds settings for gradual client migration
type MigrationConfig struct {
	// LegacyModeEnabled - Continue accepting legacy API calls
	LegacyModeEnabled bool
	// LogLegacyRequests - Log all legacy API usage for tracking client migration
	LogLegacyRequests bool
	// TranslationEnabled - Translate requests or pass through
	TranslationEnabled bool
	// StrictMode - Fail on unknown fields or accept gracefully
	StrictMode bool
	// ClientMigrationDeadline - Date when legacy API will be disabled
	ClientMigrationDeadline time.Time
}

// LegacyRequest represents a request from legacy Python client
type LegacyRequest struct {
	// HTTP method and endpoint (e.g., "GET /api/sessions/123")
	Method   string
	Endpoint string

	// Request data
	Headers map[string]string
	Body    map[string]interface{}

	// Context
	ClientID  string
	Timestamp time.Time
}

// LegacyResponse represents a response to legacy Python client
type LegacyResponse struct {
	// HTTP status code
	StatusCode int
	// Response body (matches old Python format)
	Body interface{}
	// Headers to send back
	Headers map[string]string
}

// RequestLogger tracks all legacy API requests for migration analysis
type RequestLogger struct {
	mu       sync.Mutex
	entries  []*RequestLogEntry
	maxSize  int
	filepath string
}

// RequestLogEntry represents a single legacy API request
type RequestLogEntry struct {
	ID                  string
	ClientID            string
	Method              string
	Endpoint            string
	StatusCode          int
	Duration            time.Duration
	TranslationApplied  bool
	TranslationErrors   []string
	AuthTokenType       string
	SessionID           string
	Timestamp           time.Time
	ClientSDKVersion    string
	SourceIP            string
	UserAgent           string
}

// NewAPIAdapter creates a new legacy API adapter
func NewAPIAdapter(
	sessionRepo ClaudeSessionRepository,
	lessonRepo LessonRepository,
	config *MigrationConfig,
) *APIAdapter {
	if config == nil {
		config = &MigrationConfig{
			LegacyModeEnabled:  true,
			LogLegacyRequests:  true,
			TranslationEnabled: true,
			StrictMode:         false,
		}
	}

	return &APIAdapter{
		sessionRepo:     sessionRepo,
		lessonRepo:      lessonRepo,
		requestLogger:   NewRequestLogger(10000),
		authTranslator:  NewAuthTranslator(),
		reqTranslator:   NewRequestTranslator(),
		migrationConfig: config,
	}
}

// HandleRequest processes a legacy Python API request
func (aa *APIAdapter) HandleRequest(ctx context.Context, legacyReq *LegacyRequest) (*LegacyResponse, error) {
	if !aa.migrationConfig.LegacyModeEnabled {
		return &LegacyResponse{
			StatusCode: 410, // Gone - API no longer supported
			Body: map[string]string{
				"error": "Legacy API is no longer supported. Please update your client.",
			},
		}, nil
	}

	// Start timing
	startTime := time.Now()
	logEntry := &RequestLogEntry{
		ClientID:  legacyReq.ClientID,
		Method:    legacyReq.Method,
		Endpoint:  legacyReq.Endpoint,
		Timestamp: startTime,
	}

	// Extract client info from headers
	if clientVersion, ok := legacyReq.Headers["X-Client-Version"]; ok {
		logEntry.ClientSDKVersion = clientVersion
	}
	if sourceIP, ok := legacyReq.Headers["X-Forwarded-For"]; ok {
		logEntry.SourceIP = sourceIP
	}
	if userAgent, ok := legacyReq.Headers["User-Agent"]; ok {
		logEntry.UserAgent = userAgent
	}

	// Route to appropriate handler
	var response *LegacyResponse
	var err error

	switch legacyReq.Method {
	case "GET":
		response, err = aa.handleGetRequest(ctx, legacyReq)
	case "POST":
		response, err = aa.handlePostRequest(ctx, legacyReq)
	case "PUT":
		response, err = aa.handlePutRequest(ctx, legacyReq)
	case "DELETE":
		response, err = aa.handleDeleteRequest(ctx, legacyReq)
	default:
		return &LegacyResponse{
			StatusCode: 405,
			Body: map[string]string{
				"error": fmt.Sprintf("Method %s not allowed", legacyReq.Method),
			},
		}, nil
	}

	// Log the request
	logEntry.Duration = time.Since(startTime)
	if response != nil {
		logEntry.StatusCode = response.StatusCode
	}
	if err != nil {
		logEntry.TranslationErrors = append(logEntry.TranslationErrors, err.Error())
	}

	if aa.migrationConfig.LogLegacyRequests {
		aa.requestLogger.Log(logEntry)
	}

	return response, err
}

// handleGetRequest processes GET requests
func (aa *APIAdapter) handleGetRequest(ctx context.Context, legacyReq *LegacyRequest) (*LegacyResponse, error) {
	// Parse endpoint
	endpoint := legacyReq.Endpoint

	// Session operations
	if endpoint == "/api/sessions" {
		return aa.listSessions(ctx, legacyReq)
	}

	if len(endpoint) > len("/api/sessions/") && endpoint[:len("/api/sessions/")] == "/api/sessions/" {
		sessionID := endpoint[len("/api/sessions/"):]
		return aa.getSession(ctx, legacyReq, sessionID)
	}

	// Lesson operations
	if endpoint == "/api/lessons" {
		return aa.listLessons(ctx, legacyReq)
	}

	if len(endpoint) > len("/api/lessons/") && endpoint[:len("/api/lessons/")] == "/api/lessons/" {
		lessonID := endpoint[len("/api/lessons/"):]
		return aa.getLesson(ctx, legacyReq, lessonID)
	}

	return &LegacyResponse{
		StatusCode: 404,
		Body: map[string]string{
			"error": fmt.Sprintf("Endpoint not found: %s", endpoint),
		},
	}, nil
}

// handlePostRequest processes POST requests
func (aa *APIAdapter) handlePostRequest(ctx context.Context, legacyReq *LegacyRequest) (*LegacyResponse, error) {
	endpoint := legacyReq.Endpoint

	// Create session
	if endpoint == "/api/sessions" {
		return aa.createSession(ctx, legacyReq)
	}

	// Create lesson
	if endpoint == "/api/lessons" {
		return aa.createLesson(ctx, legacyReq)
	}

	return &LegacyResponse{
		StatusCode: 404,
		Body: map[string]string{
			"error": fmt.Sprintf("Endpoint not found: %s", endpoint),
		},
	}, nil
}

// handlePutRequest processes PUT requests
func (aa *APIAdapter) handlePutRequest(ctx context.Context, legacyReq *LegacyRequest) (*LegacyResponse, error) {
	endpoint := legacyReq.Endpoint

	// Update session
	if len(endpoint) > len("/api/sessions/") && endpoint[:len("/api/sessions/")] == "/api/sessions/" {
		sessionID := endpoint[len("/api/sessions/"):]
		return aa.updateSession(ctx, legacyReq, sessionID)
	}

	// Update lesson
	if len(endpoint) > len("/api/lessons/") && endpoint[:len("/api/lessons/")] == "/api/lessons/" {
		lessonID := endpoint[len("/api/lessons/"):]
		return aa.updateLesson(ctx, legacyReq, lessonID)
	}

	return &LegacyResponse{
		StatusCode: 404,
		Body: map[string]string{
			"error": fmt.Sprintf("Endpoint not found: %s", endpoint),
		},
	}, nil
}

// handleDeleteRequest processes DELETE requests
func (aa *APIAdapter) handleDeleteRequest(ctx context.Context, legacyReq *LegacyRequest) (*LegacyResponse, error) {
	endpoint := legacyReq.Endpoint

	// Delete session
	if len(endpoint) > len("/api/sessions/") && endpoint[:len("/api/sessions/")] == "/api/sessions/" {
		sessionID := endpoint[len("/api/sessions/"):]
		return aa.deleteSession(ctx, legacyReq, sessionID)
	}

	// Delete lesson
	if len(endpoint) > len("/api/lessons/") && endpoint[:len("/api/lessons/")] == "/api/lessons/" {
		lessonID := endpoint[len("/api/lessons/"):]
		return aa.deleteLesson(ctx, legacyReq, lessonID)
	}

	return &LegacyResponse{
		StatusCode: 404,
		Body: map[string]string{
			"error": fmt.Sprintf("Endpoint not found: %s", endpoint),
		},
	}, nil
}

// Session operations

func (aa *APIAdapter) listSessions(ctx context.Context, legacyReq *LegacyRequest) (*LegacyResponse, error) {
	sessions, err := aa.sessionRepo.GetAll(ctx)
	if err != nil {
		return &LegacyResponse{
			StatusCode: 500,
			Body: map[string]string{
				"error": "Failed to list sessions",
			},
		}, err
	}

	// Convert to legacy format
	legacySessions := make([]map[string]interface{}, 0)
	for i := range sessions {
		legacySessions = append(legacySessions, aa.convertSessionToLegacy(&sessions[i]))
	}

	return &LegacyResponse{
		StatusCode: 200,
		Body:       legacySessions,
	}, nil
}

func (aa *APIAdapter) getSession(ctx context.Context, legacyReq *LegacyRequest, sessionID string) (*LegacyResponse, error) {
	session, err := aa.sessionRepo.GetByID(ctx, sessionID)
	if err != nil {
		return &LegacyResponse{
			StatusCode: 404,
			Body: map[string]string{
				"error": "Session not found",
			},
		}, nil
	}

	return &LegacyResponse{
		StatusCode: 200,
		Body:       aa.convertSessionToLegacy(session),
	}, nil
}

func (aa *APIAdapter) createSession(ctx context.Context, legacyReq *LegacyRequest) (*LegacyResponse, error) {
	// Translate legacy request to new session model
	newSession, err := aa.reqTranslator.TranslateSessionCreate(legacyReq.Body)
	if err != nil {
		return &LegacyResponse{
			StatusCode: 400,
			Body: map[string]string{
				"error": fmt.Sprintf("Invalid request: %v", err),
			},
		}, nil
	}

	// Create session
	created, err := aa.sessionRepo.Create(ctx, newSession)
	if err != nil {
		return &LegacyResponse{
			StatusCode: 500,
			Body: map[string]string{
				"error": "Failed to create session",
			},
		}, err
	}

	return &LegacyResponse{
		StatusCode: 201,
		Body:       aa.convertSessionToLegacy(created),
	}, nil
}

func (aa *APIAdapter) updateSession(ctx context.Context, legacyReq *LegacyRequest, sessionID string) (*LegacyResponse, error) {
	// Get existing session
	session, err := aa.sessionRepo.GetByID(ctx, sessionID)
	if err != nil {
		return &LegacyResponse{
			StatusCode: 404,
			Body: map[string]string{
				"error": "Session not found",
			},
		}, nil
	}

	// Translate and apply updates
	updated := aa.reqTranslator.TranslateSessionUpdate(session, legacyReq.Body)

	// Save
	result, err := aa.sessionRepo.Update(ctx, updated)
	if err != nil {
		return &LegacyResponse{
			StatusCode: 500,
			Body: map[string]string{
				"error": "Failed to update session",
			},
		}, err
	}

	return &LegacyResponse{
		StatusCode: 200,
		Body:       aa.convertSessionToLegacy(result),
	}, nil
}

func (aa *APIAdapter) deleteSession(ctx context.Context, legacyReq *LegacyRequest, sessionID string) (*LegacyResponse, error) {
	err := aa.sessionRepo.Delete(ctx, sessionID)
	if err != nil {
		return &LegacyResponse{
			StatusCode: 500,
			Body: map[string]string{
				"error": "Failed to delete session",
			},
		}, err
	}

	return &LegacyResponse{
		StatusCode: 204,
		Body:       nil,
	}, nil
}

// Lesson operations

func (aa *APIAdapter) listLessons(ctx context.Context, legacyReq *LegacyRequest) (*LegacyResponse, error) {
	lessons, err := aa.lessonRepo.GetAll(ctx)
	if err != nil {
		return &LegacyResponse{
			StatusCode: 500,
			Body: map[string]string{
				"error": "Failed to list lessons",
			},
		}, err
	}

	legacyLessons := make([]map[string]interface{}, 0)
	for _, lesson := range lessons {
		legacyLessons = append(legacyLessons, aa.convertLessonToLegacy(&lesson))
	}

	return &LegacyResponse{
		StatusCode: 200,
		Body:       legacyLessons,
	}, nil
}

func (aa *APIAdapter) getLesson(ctx context.Context, legacyReq *LegacyRequest, lessonID string) (*LegacyResponse, error) {
	lesson, err := aa.lessonRepo.GetByID(ctx, lessonID)
	if err != nil {
		return &LegacyResponse{
			StatusCode: 404,
			Body: map[string]string{
				"error": "Lesson not found",
			},
		}, nil
	}

	return &LegacyResponse{
		StatusCode: 200,
		Body:       aa.convertLessonToLegacy(lesson),
	}, nil
}

func (aa *APIAdapter) createLesson(ctx context.Context, legacyReq *LegacyRequest) (*LegacyResponse, error) {
	newLesson, err := aa.reqTranslator.TranslateLessonCreate(legacyReq.Body)
	if err != nil {
		return &LegacyResponse{
			StatusCode: 400,
			Body: map[string]string{
				"error": fmt.Sprintf("Invalid request: %v", err),
			},
		}, nil
	}

	created, err := aa.lessonRepo.Create(ctx, newLesson)
	if err != nil {
		return &LegacyResponse{
			StatusCode: 500,
			Body: map[string]string{
				"error": "Failed to create lesson",
			},
		}, err
	}

	return &LegacyResponse{
		StatusCode: 201,
		Body:       aa.convertLessonToLegacy(created),
	}, nil
}

func (aa *APIAdapter) updateLesson(ctx context.Context, legacyReq *LegacyRequest, lessonID string) (*LegacyResponse, error) {
	lesson, err := aa.lessonRepo.GetByID(ctx, lessonID)
	if err != nil {
		return &LegacyResponse{
			StatusCode: 404,
			Body: map[string]string{
				"error": "Lesson not found",
			},
		}, nil
	}

	updated := aa.reqTranslator.TranslateLessonUpdate(lesson, legacyReq.Body)

	result, err := aa.lessonRepo.Update(ctx, updated)
	if err != nil {
		return &LegacyResponse{
			StatusCode: 500,
			Body: map[string]string{
				"error": "Failed to update lesson",
			},
		}, err
	}

	return &LegacyResponse{
		StatusCode: 200,
		Body:       aa.convertLessonToLegacy(result),
	}, nil
}

func (aa *APIAdapter) deleteLesson(ctx context.Context, legacyReq *LegacyRequest, lessonID string) (*LegacyResponse, error) {
	err := aa.lessonRepo.Delete(ctx, lessonID)
	if err != nil {
		return &LegacyResponse{
			StatusCode: 500,
			Body: map[string]string{
				"error": "Failed to delete lesson",
			},
		}, err
	}

	return &LegacyResponse{
		StatusCode: 204,
		Body:       nil,
	}, nil
}

// Helper methods

func (aa *APIAdapter) convertSessionToLegacy(session *models.ClaudeSession) map[string]interface{} {
	result := map[string]interface{}{
		"id":           session.ID.String(),
		"session_name": session.SessionName,
		"status":       session.Status,
		"tier":         session.Tier,
		"provider":     session.Provider,
		"created_at":   session.CreatedAt.Format(time.RFC3339),
		"updated_at":   session.UpdatedAt.Format(time.RFC3339),
	}

	if session.UserID != nil {
		result["user_id"] = session.UserID.String()
	}

	// Parse metadata if available
	if len(session.Metadata) > 0 {
		var metadata map[string]interface{}
		if err := json.Unmarshal(session.Metadata, &metadata); err == nil {
			result["metadata"] = metadata
		}
	}

	return result
}

func (aa *APIAdapter) convertLessonToLegacy(lesson *models.Lesson) map[string]interface{} {
	result := map[string]interface{}{
		"id":          lesson.ID.String(),
		"title":       lesson.Title,
		"description": lesson.Description,
		"status":      lesson.Status,
		"priority":    lesson.Priority,
		"created_at":  lesson.CreatedAt.Format(time.RFC3339),
		"updated_at":  lesson.UpdatedAt.Format(time.RFC3339),
	}

	// Parse metadata if available
	if len(lesson.Metadata) > 0 {
		var metadata map[string]interface{}
		if err := json.Unmarshal(lesson.Metadata, &metadata); err == nil {
			result["metadata"] = metadata
		}
	}

	return result
}

// GetRequestLog returns all logged requests (for debugging)
func (aa *APIAdapter) GetRequestLog() []*RequestLogEntry {
	return aa.requestLogger.GetAll()
}

// GetMigrationMetrics returns statistics about legacy API usage
func (aa *APIAdapter) GetMigrationMetrics() map[string]interface{} {
	log := aa.requestLogger.GetAll()

	if len(log) == 0 {
		return map[string]interface{}{
			"total_requests":      0,
			"unique_clients":      0,
			"endpoints_used":      []string{},
			"auth_types_used":     []string{},
			"translation_errors":  0,
		}
	}

	// Aggregate stats
	clientSet := make(map[string]bool)
	endpointSet := make(map[string]bool)
	authTypeSet := make(map[string]bool)
	translationErrors := 0

	for _, entry := range log {
		clientSet[entry.ClientID] = true
		endpointSet[entry.Endpoint] = true
		if entry.AuthTokenType != "" {
			authTypeSet[entry.AuthTokenType] = true
		}
		if len(entry.TranslationErrors) > 0 {
			translationErrors++
		}
	}

	endpoints := make([]string, 0, len(endpointSet))
	for ep := range endpointSet {
		endpoints = append(endpoints, ep)
	}

	authTypes := make([]string, 0, len(authTypeSet))
	for at := range authTypeSet {
		authTypes = append(authTypes, at)
	}

	return map[string]interface{}{
		"total_requests":      len(log),
		"unique_clients":      len(clientSet),
		"endpoints_used":      endpoints,
		"auth_types_used":     authTypes,
		"translation_errors":  translationErrors,
	}
}

// NewRequestLogger creates a new request logger
func NewRequestLogger(maxSize int) *RequestLogger {
	return &RequestLogger{
		entries: make([]*RequestLogEntry, 0, maxSize),
		maxSize: maxSize,
	}
}

// Log adds an entry to the request log
func (rl *RequestLogger) Log(entry *RequestLogEntry) {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	// Assign ID
	entry.ID = fmt.Sprintf("req_%d", len(rl.entries)+1)

	rl.entries = append(rl.entries, entry)

	// Keep log size bounded
	if len(rl.entries) > rl.maxSize {
		rl.entries = rl.entries[len(rl.entries)-rl.maxSize:]
	}
}

// GetAll returns all logged entries
func (rl *RequestLogger) GetAll() []*RequestLogEntry {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	result := make([]*RequestLogEntry, len(rl.entries))
	copy(result, rl.entries)
	return result
}

// GetByID returns a specific log entry
func (rl *RequestLogger) GetByID(id string) *RequestLogEntry {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	for _, entry := range rl.entries {
		if entry.ID == id {
			return entry
		}
	}
	return nil
}

// GetByClientID returns all entries from a specific client
func (rl *RequestLogger) GetByClientID(clientID string) []*RequestLogEntry {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	result := make([]*RequestLogEntry, 0)
	for _, entry := range rl.entries {
		if entry.ClientID == clientID {
			result = append(result, entry)
		}
	}
	return result
}

// ClearOlderThan removes entries older than the specified duration
func (rl *RequestLogger) ClearOlderThan(duration time.Duration) {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	cutoff := time.Now().Add(-duration)
	newEntries := make([]*RequestLogEntry, 0)

	for _, entry := range rl.entries {
		if entry.Timestamp.After(cutoff) {
			newEntries = append(newEntries, entry)
		}
	}

	rl.entries = newEntries
}
