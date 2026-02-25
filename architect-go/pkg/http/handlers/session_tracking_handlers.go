package handlers

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"

	"architect-go/pkg/errors"
	httputil "architect-go/pkg/httputil"
	"architect-go/pkg/services"
)

// SessionTrackingHandlers handles session management HTTP requests
type SessionTrackingHandlers struct {
	service    services.SessionTrackingService
	errHandler *errors.Handler
}

// NewSessionTrackingHandlers creates new session tracking handlers
func NewSessionTrackingHandlers(service services.SessionTrackingService, errHandler *errors.Handler) *SessionTrackingHandlers {
	return &SessionTrackingHandlers{
		service:    service,
		errHandler: errHandler,
	}
}

// ListSessions handles GET /api/sessions
func (sh *SessionTrackingHandlers) ListSessions(w http.ResponseWriter, r *http.Request) {
	limit, offset := 20, 0
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}
	if o := r.URL.Query().Get("offset"); o != "" {
		if parsed, err := strconv.Atoi(o); err == nil && parsed >= 0 {
			offset = parsed
		}
	}

	sessions, total, err := sh.service.ListSessions(r.Context(), limit, offset)
	if err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"sessions": sessions,
		"total":    total,
		"limit":    limit,
		"offset":   offset,
	})
}

// GetSession handles GET /api/sessions/{id}
func (sh *SessionTrackingHandlers) GetSession(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		sh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Session ID is required"), httputil.GetTraceID(r))
		return
	}

	session, err := sh.service.GetSession(r.Context(), id)
	if err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"session": session})
}

// GetCurrentSession handles GET /api/sessions/current/{userID}
func (sh *SessionTrackingHandlers) GetCurrentSession(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		sh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	session, err := sh.service.GetCurrentSession(r.Context(), userID)
	if err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"session": session})
}

// CreateSession handles POST /api/sessions
func (sh *SessionTrackingHandlers) CreateSession(w http.ResponseWriter, r *http.Request) {
	var req struct {
		UserID    string `json:"user_id"`
		IPAddress string `json:"ip_address"`
		UserAgent string `json:"user_agent"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	session, err := sh.service.CreateSession(r.Context(), req.UserID, req.IPAddress, req.UserAgent)
	if err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]interface{}{"session": session})
}

// DestroySession handles DELETE /api/sessions/{id}
func (sh *SessionTrackingHandlers) DestroySession(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		sh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Session ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := sh.service.DestroySession(r.Context(), id); err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// DestroyAllUserSessions handles DELETE /api/sessions/user/{userID}/all
func (sh *SessionTrackingHandlers) DestroyAllUserSessions(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		sh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := sh.service.DestroyAllUserSessions(r.Context(), userID); err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// ExtendSession handles POST /api/sessions/{id}/extend
func (sh *SessionTrackingHandlers) ExtendSession(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		sh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Session ID is required"), httputil.GetTraceID(r))
		return
	}

	var req services.SessionExtendRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := sh.service.ExtendSession(r.Context(), id, &req); err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "extended"})
}

// GetUserSessions handles GET /api/sessions/user/{userID} or /api/sessions/user/{user_id}
func (sh *SessionTrackingHandlers) GetUserSessions(w http.ResponseWriter, r *http.Request) {
	// Support both {userID} and {user_id} path parameter names
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		userID = chi.URLParam(r, "user_id")
	}
	if userID == "" {
		sh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	limit, offset := 20, 0
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}
	if o := r.URL.Query().Get("offset"); o != "" {
		if parsed, err := strconv.Atoi(o); err == nil && parsed >= 0 {
			offset = parsed
		}
	}

	sessions, total, err := sh.service.GetUserSessions(r.Context(), userID, limit, offset)
	if err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"sessions": sessions,
		"total":    total,
		"limit":    limit,
		"offset":   offset,
	})
}

// ListActiveSessions handles GET /api/sessions/active
func (sh *SessionTrackingHandlers) ListActiveSessions(w http.ResponseWriter, r *http.Request) {
	limit, offset := 20, 0
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}
	if o := r.URL.Query().Get("offset"); o != "" {
		if parsed, err := strconv.Atoi(o); err == nil && parsed >= 0 {
			offset = parsed
		}
	}

	sessions, total, err := sh.service.ListActiveSessions(r.Context(), limit, offset)
	if err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"sessions": sessions,
		"total":    total,
		"limit":    limit,
		"offset":   offset,
	})
}

// GetSessionStats handles GET /api/sessions/stats
func (sh *SessionTrackingHandlers) GetSessionStats(w http.ResponseWriter, r *http.Request) {
	stats, err := sh.service.GetSessionStats(r.Context())
	if err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"stats": stats})
}

// GetConcurrentUserCount handles GET /api/sessions/concurrent-users
func (sh *SessionTrackingHandlers) GetConcurrentUserCount(w http.ResponseWriter, r *http.Request) {
	count, err := sh.service.GetConcurrentUserCount(r.Context())
	if err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(count)
}

// ValidateSession handles GET /api/sessions/{id}/validate
func (sh *SessionTrackingHandlers) ValidateSession(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		sh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Session ID is required"), httputil.GetTraceID(r))
		return
	}

	valid, err := sh.service.ValidateSession(r.Context(), id)
	if err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]bool{"valid": valid})
}

// LogActivity handles POST /api/sessions/{id}/activity
func (sh *SessionTrackingHandlers) LogActivity(w http.ResponseWriter, r *http.Request) {
	sessionID := chi.URLParam(r, "id")
	if sessionID == "" {
		sh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Session ID is required"), httputil.GetTraceID(r))
		return
	}

	var req services.SessionActivityRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := sh.service.LogActivity(r.Context(), sessionID, &req); err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "logged"})
}

// GetActivityHistory handles GET /api/sessions/{id}/activity-history
func (sh *SessionTrackingHandlers) GetActivityHistory(w http.ResponseWriter, r *http.Request) {
	sessionID := chi.URLParam(r, "id")
	if sessionID == "" {
		sh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Session ID is required"), httputil.GetTraceID(r))
		return
	}

	limit, offset := 20, 0
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}
	if o := r.URL.Query().Get("offset"); o != "" {
		if parsed, err := strconv.Atoi(o); err == nil && parsed >= 0 {
			offset = parsed
		}
	}

	history, total, err := sh.service.GetActivityHistory(r.Context(), sessionID, limit, offset)
	if err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"history": history,
		"total":   total,
		"limit":   limit,
		"offset":  offset,
	})
}

// GetGeographicDistribution handles GET /api/sessions/geography
func (sh *SessionTrackingHandlers) GetGeographicDistribution(w http.ResponseWriter, r *http.Request) {
	distribution, err := sh.service.GetGeographicDistribution(r.Context())
	if err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"distribution": distribution})
}

// GetDeviceStats handles GET /api/sessions/device-stats
func (sh *SessionTrackingHandlers) GetDeviceStats(w http.ResponseWriter, r *http.Request) {
	stats, err := sh.service.GetDeviceStats(r.Context())
	if err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"stats": stats})
}

// KickUser handles POST /api/sessions/user/{userID}/kick
func (sh *SessionTrackingHandlers) KickUser(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		sh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := sh.service.KickUser(r.Context(), userID); err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "kicked"})
}

// KickSession handles POST /api/sessions/{id}/kick
func (sh *SessionTrackingHandlers) KickSession(w http.ResponseWriter, r *http.Request) {
	sessionID := chi.URLParam(r, "id")
	if sessionID == "" {
		sh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Session ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := sh.service.KickSession(r.Context(), sessionID); err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "kicked"})
}

// LockSession handles POST /api/sessions/{id}/lock
func (sh *SessionTrackingHandlers) LockSession(w http.ResponseWriter, r *http.Request) {
	sessionID := chi.URLParam(r, "id")
	if sessionID == "" {
		sh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Session ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := sh.service.LockSession(r.Context(), sessionID); err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "locked"})
}

// UnlockSession handles POST /api/sessions/{id}/unlock
func (sh *SessionTrackingHandlers) UnlockSession(w http.ResponseWriter, r *http.Request) {
	sessionID := chi.URLParam(r, "id")
	if sessionID == "" {
		sh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Session ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := sh.service.UnlockSession(r.Context(), sessionID); err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "unlocked"})
}

// DetectSuspiciousActivity handles GET /api/sessions/suspicious-activity
func (sh *SessionTrackingHandlers) DetectSuspiciousActivity(w http.ResponseWriter, r *http.Request) {
	activities, err := sh.service.DetectSuspiciousActivity(r.Context())
	if err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"activities": activities})
}

// GetOnlineUsers handles GET /api/sessions/online-users
func (sh *SessionTrackingHandlers) GetOnlineUsers(w http.ResponseWriter, r *http.Request) {
	users, err := sh.service.GetOnlineUsers(r.Context())
	if err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"users": users})
}

// CheckUserOnlineStatus handles GET /api/sessions/user/{userID}/online-status
func (sh *SessionTrackingHandlers) CheckUserOnlineStatus(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		sh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	online, err := sh.service.CheckUserOnlineStatus(r.Context(), userID)
	if err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]bool{"online": online})
}

// GetRiskySessions handles GET /api/sessions/risky
func (sh *SessionTrackingHandlers) GetRiskySessions(w http.ResponseWriter, r *http.Request) {
	limit, offset := 20, 0
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}
	if o := r.URL.Query().Get("offset"); o != "" {
		if parsed, err := strconv.Atoi(o); err == nil && parsed >= 0 {
			offset = parsed
		}
	}

	sessions, total, err := sh.service.GetRiskySessions(r.Context(), limit, offset)
	if err != nil {
		sh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"sessions": sessions,
		"total":    total,
		"limit":    limit,
		"offset":   offset,
	})
}

// RegisterSessionTrackingRoutes registers session tracking routes
func RegisterSessionTrackingRoutes(r interface {
	Get(pattern string, handlerFn http.HandlerFunc)
	Post(pattern string, handlerFn http.HandlerFunc)
	Delete(pattern string, handlerFn http.HandlerFunc)
}, handlers *SessionTrackingHandlers) {
	r.Get("/", handlers.ListSessions)
	r.Post("/", handlers.CreateSession)
	r.Get("/{id}", handlers.GetSession)
	r.Delete("/{id}", handlers.DestroySession)
	r.Get("/current/{userID}", handlers.GetCurrentSession)
	r.Post("/{id}/extend", handlers.ExtendSession)
	r.Post("/{id}/activity", handlers.LogActivity)
	r.Get("/{id}/activity-history", handlers.GetActivityHistory)
	r.Post("/{id}/lock", handlers.LockSession)
	r.Post("/{id}/unlock", handlers.UnlockSession)
	r.Post("/{id}/kick", handlers.KickSession)
	r.Get("/user/{userID}", handlers.GetUserSessions)
	r.Post("/user/{userID}/kick", handlers.KickUser)
	r.Get("/user/{userID}/online-status", handlers.CheckUserOnlineStatus)
	r.Delete("/user/{userID}/all", handlers.DestroyAllUserSessions)
	r.Get("/active", handlers.ListActiveSessions)
	r.Get("/stats", handlers.GetSessionStats)
	r.Get("/concurrent-users", handlers.GetConcurrentUserCount)
	r.Get("/{id}/validate", handlers.ValidateSession)
	r.Get("/geography", handlers.GetGeographicDistribution)
	r.Get("/device-stats", handlers.GetDeviceStats)
	r.Get("/suspicious-activity", handlers.DetectSuspiciousActivity)
	r.Get("/online-users", handlers.GetOnlineUsers)
	r.Get("/risky", handlers.GetRiskySessions)
}
