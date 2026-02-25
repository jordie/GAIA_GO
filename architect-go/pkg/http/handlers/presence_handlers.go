package handlers

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"

	"architect-go/pkg/errors"
	"architect-go/pkg/events"
	httputil "architect-go/pkg/httputil"
	"architect-go/pkg/services"
)

// PresenceHandlers handles presence-related HTTP requests
type PresenceHandlers struct {
	service    services.PresenceService
	errHandler *errors.Handler
	dispatcher events.EventDispatcher
}

// NewPresenceHandlers creates new presence handlers without event dispatcher
func NewPresenceHandlers(service services.PresenceService, errHandler *errors.Handler) *PresenceHandlers {
	return &PresenceHandlers{
		service:    service,
		errHandler: errHandler,
	}
}

// NewPresenceHandlersWithDispatcher creates new presence handlers with event dispatcher
func NewPresenceHandlersWithDispatcher(service services.PresenceService, errHandler *errors.Handler, dispatcher events.EventDispatcher) *PresenceHandlers {
	return &PresenceHandlers{
		service:    service,
		errHandler: errHandler,
		dispatcher: dispatcher,
	}
}

// ListOnlineUsers handles GET /api/presence/online
func (ph *PresenceHandlers) ListOnlineUsers(w http.ResponseWriter, r *http.Request) {
	limit, offset, err := ParsePaginationParams(r, 50, 5000)
	if err != nil {
		ph.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	users, err := ph.service.GetOnlineUsers(r.Context())
	if err != nil {
		ph.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	// Calculate total and apply pagination
	total := int64(len(users))
	if offset >= len(users) {
		users = []string{}
	} else {
		endIdx := offset + limit
		if endIdx > len(users) {
			endIdx = len(users)
		}
		users = users[offset:endIdx]
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"users":  users,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// GetPresenceByStatus handles GET /api/presence?status={status}
func (ph *PresenceHandlers) GetPresenceByStatus(w http.ResponseWriter, r *http.Request) {
	status := r.URL.Query().Get("status")
	if status == "" {
		ph.errHandler.Handle(w, errors.ValidationErrorf("MISSING_STATUS", "Status parameter is required"), httputil.GetTraceID(r))
		return
	}

	limit, offset, err := ParsePaginationParams(r, 50, 5000)
	if err != nil {
		ph.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	users, err := ph.service.GetPresenceByStatus(r.Context(), status)
	if err != nil {
		ph.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	// Calculate total and apply pagination
	total := int64(len(users))
	if offset >= len(users) {
		users = []string{}
	} else {
		endIdx := offset + limit
		if endIdx > len(users) {
			endIdx = len(users)
		}
		users = users[offset:endIdx]
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"users":  users,
		"total":  total,
		"status": status,
		"limit":  limit,
		"offset": offset,
	})
}

// GetUserPresence handles GET /api/presence/{userID}
func (ph *PresenceHandlers) GetUserPresence(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		ph.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	presence, err := ph.service.GetPresence(r.Context(), userID)
	if err != nil {
		ph.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(presence)
}

// UpdatePresence handles POST /api/presence
func (ph *PresenceHandlers) UpdatePresence(w http.ResponseWriter, r *http.Request) {
	var req struct {
		UserID   string                 `json:"user_id"`
		Status   string                 `json:"status"`
		Metadata map[string]interface{} `json:"metadata,omitempty"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		ph.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if req.UserID == "" {
		ph.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	if req.Status == "" {
		ph.errHandler.Handle(w, errors.ValidationErrorf("MISSING_STATUS", "Status is required"), httputil.GetTraceID(r))
		return
	}

	if !ph.validatePresenceStatus(req.Status) {
		ph.errHandler.Handle(w, errors.ValidationErrorf("INVALID_STATUS", "Invalid status value"), httputil.GetTraceID(r))
		return
	}

	// Get current presence to track old status
	currentPresence, _ := ph.service.GetPresence(r.Context(), req.UserID)
	oldStatus := ""
	if currentPresence != nil {
		oldStatus = currentPresence.Status
	}

	// Update presence
	if err := ph.service.UpdatePresence(r.Context(), req.UserID, req.Status, req.Metadata); err != nil {
		ph.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	// Fetch updated presence
	presence, err := ph.service.GetPresence(r.Context(), req.UserID)
	if err != nil {
		ph.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	// Broadcast presence change event
	if ph.dispatcher != nil && oldStatus != req.Status {
		ph.broadcastPresenceChange(r.Context(), req.UserID, oldStatus, req.Status, presence)
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(presence)
}

// SetUserOffline handles DELETE /api/presence/{userID}
func (ph *PresenceHandlers) SetUserOffline(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		ph.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	// Get current presence
	currentPresence, _ := ph.service.GetPresence(r.Context(), userID)
	oldStatus := "unknown"
	if currentPresence != nil {
		oldStatus = currentPresence.Status
	}

	// Set offline
	if err := ph.service.SetOffline(r.Context(), userID); err != nil {
		ph.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	// Broadcast offline event
	if ph.dispatcher != nil {
		ph.broadcastPresenceChange(r.Context(), userID, oldStatus, "offline", nil)
	}

	w.WriteHeader(http.StatusNoContent)
}

// GetPresenceHistory handles GET /api/presence/{userID}/history
func (ph *PresenceHandlers) GetPresenceHistory(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		ph.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	limit := 20
	offset := 0

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

	history, total, err := ph.service.GetPresenceHistory(r.Context(), userID, limit, offset)
	if err != nil {
		ph.errHandler.Handle(w, err, httputil.GetTraceID(r))
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

// Private helper methods

func (ph *PresenceHandlers) validatePresenceStatus(status string) bool {
	validStatuses := map[string]bool{
		"online":           true,
		"away":             true,
		"idle":             true,
		"offline":          true,
		"do_not_disturb":   true,
	}
	return validStatuses[status]
}

func (ph *PresenceHandlers) broadcastPresenceChange(ctx interface{}, userID, oldStatus, newStatus string, presence interface{}) {
	// User-specific event
	ph.dispatcher.Dispatch(events.Event{
		Type:    events.EventPresenceUpdated,
		Channel: "presence:" + userID,
		UserID:  userID,
		Data: map[string]interface{}{
			"user_id":    userID,
			"old_status": oldStatus,
			"new_status": newStatus,
			"presence":   presence,
		},
	})

	// Online users channel
	if newStatus == "online" || oldStatus == "online" {
		ph.dispatcher.Dispatch(events.Event{
			Type:    events.EventPresenceOnline,
			Channel: "presence:online_users",
			Data: map[string]interface{}{
				"user_id":    userID,
				"old_status": oldStatus,
				"new_status": newStatus,
			},
		})
	}

	// Broadcast to all
	ph.dispatcher.Dispatch(events.Event{
		Type:    events.EventPresenceUpdated,
		Channel: "presence",
		Data: map[string]interface{}{
			"user_id":    userID,
			"old_status": oldStatus,
			"new_status": newStatus,
		},
	})
}

// RegisterPresenceRoutes registers all presence routes
func RegisterPresenceRoutes(r chi.Router, handlers *PresenceHandlers) {
	r.Get("/online", handlers.ListOnlineUsers)
	r.Get("/", handlers.GetPresenceByStatus)
	r.Post("/", handlers.UpdatePresence)
	r.Delete("/{userID}", handlers.SetUserOffline)
	r.Get("/{userID}", handlers.GetUserPresence)
	r.Get("/{userID}/history", handlers.GetPresenceHistory)
}
