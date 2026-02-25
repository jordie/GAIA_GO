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

// ActivityHandlers handles activity-related HTTP requests
type ActivityHandlers struct {
	service    services.ActivityService
	errHandler *errors.Handler
	dispatcher events.EventDispatcher
}

// NewActivityHandlers creates new activity handlers without event dispatcher
func NewActivityHandlers(service services.ActivityService, errHandler *errors.Handler) *ActivityHandlers {
	return &ActivityHandlers{
		service:    service,
		errHandler: errHandler,
	}
}

// NewActivityHandlersWithDispatcher creates new activity handlers with event dispatcher
func NewActivityHandlersWithDispatcher(service services.ActivityService, errHandler *errors.Handler, dispatcher events.EventDispatcher) *ActivityHandlers {
	return &ActivityHandlers{
		service:    service,
		errHandler: errHandler,
		dispatcher: dispatcher,
	}
}

// LogActivity handles POST /api/activity
func (ah *ActivityHandlers) LogActivity(w http.ResponseWriter, r *http.Request) {
	var req struct {
		UserID       string                 `json:"user_id"`
		Action       string                 `json:"action"`
		ResourceType string                 `json:"resource_type,omitempty"`
		ResourceID   string                 `json:"resource_id,omitempty"`
		Metadata     map[string]interface{} `json:"metadata,omitempty"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		ah.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if req.UserID == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	if req.Action == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ACTION", "Action is required"), httputil.GetTraceID(r))
		return
	}

	err := ah.service.LogActivity(r.Context(), req.UserID, req.Action, req.ResourceType, req.ResourceID, req.Metadata)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	// Broadcast activity event
	if ah.dispatcher != nil {
		ah.broadcastActivityEvent(r.Context(), req.UserID, req.Action, req.ResourceType, req.ResourceID, req.Metadata)
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]string{"status": "logged"})
}

// GetUserActivity handles GET /api/activity/user/{userID}
func (ah *ActivityHandlers) GetUserActivity(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	limit, offset, err := ParsePaginationParams(r, 20, 500)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	activities, total, err := ah.service.GetUserActivity(r.Context(), userID, limit, offset)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"activities": activities,
		"total":      total,
		"limit":      limit,
		"offset":     offset,
	})
}

// GetProjectActivity handles GET /api/activity/resource/{resourceType}/{resourceID}
func (ah *ActivityHandlers) GetProjectActivity(w http.ResponseWriter, r *http.Request) {
	resourceType := chi.URLParam(r, "resourceType")
	resourceID := chi.URLParam(r, "resourceID")

	if resourceType == "" || resourceID == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_PARAMS", "Resource type and ID are required"), httputil.GetTraceID(r))
		return
	}

	limit, offset, err := ParsePaginationParams(r, 20, 500)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	activities, total, err := ah.service.GetProjectActivity(r.Context(), resourceType, resourceID, limit, offset)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"activities":    activities,
		"total":         total,
		"resource_type": resourceType,
		"resource_id":   resourceID,
		"limit":         limit,
		"offset":        offset,
	})
}

// FilterActivity handles GET /api/activity?filter=...
func (ah *ActivityHandlers) FilterActivity(w http.ResponseWriter, r *http.Request) {
	filters, err := BuildActivityFilters(r)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	limit, offset, err := ParsePaginationParams(r, 20, 500)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	activities, total, err := ah.service.FilterActivity(r.Context(), filters, limit, offset)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"activities": activities,
		"total":      total,
		"filters":    filters,
		"limit":      limit,
		"offset":     offset,
	})
}

// GetActivityStats handles GET /api/activity/stats/{userID}
func (ah *ActivityHandlers) GetActivityStats(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	stats, err := ah.service.GetActivityStats(r.Context(), userID)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"stats":  stats,
		"period": "all_time",
	})
}

// GetRecentActivity handles GET /api/activity/recent
func (ah *ActivityHandlers) GetRecentActivity(w http.ResponseWriter, r *http.Request) {
	limit := 50
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 && parsed <= 500 {
			limit = parsed
		}
	}

	activities, err := ah.service.GetRecentActivity(r.Context(), limit)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"activities": activities,
		"limit":      limit,
	})
}

// DeleteActivity handles DELETE /api/activity/{activityID}
func (ah *ActivityHandlers) DeleteActivity(w http.ResponseWriter, r *http.Request) {
	activityID := chi.URLParam(r, "activityID")
	if activityID == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ACTIVITY_ID", "Activity ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := ah.service.DeleteActivity(r.Context(), activityID); err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// Private helper methods

func (ah *ActivityHandlers) isSignificantAction(action string) bool {
	significantActions := map[string]bool{
		"project_created": true,
		"project_deleted": true,
		"bug_resolved":    true,
		"deployment_complete": true,
		"feature_released":    true,
		"milestone_achieved":  true,
		"task_completed":      true,
		"merge_completed":     true,
	}
	return significantActions[action]
}

func (ah *ActivityHandlers) broadcastActivityEvent(ctx interface{}, userID, action, resourceType, resourceID string, metadata map[string]interface{}) {
	// Check if action should be suppressed
	if ah.shouldSuppressActivity(action) {
		return
	}

	eventType := events.EventActivityLogged
	channel := "activity:" + userID

	// Dispatch user-specific event
	ah.dispatcher.Dispatch(events.Event{
		Type:    eventType,
		Channel: channel,
		UserID:  userID,
		Data: map[string]interface{}{
			"user_id":       userID,
			"action":        action,
			"resource_type": resourceType,
			"resource_id":   resourceID,
			"metadata":      metadata,
		},
	})

	// Dispatch to resource channel if applicable
	if resourceType != "" && resourceID != "" {
		ah.dispatcher.Dispatch(events.Event{
			Type:    eventType,
			Channel: "activity:resource:" + resourceType + ":" + resourceID,
			Data: map[string]interface{}{
				"user_id":       userID,
				"action":        action,
				"resource_type": resourceType,
				"resource_id":   resourceID,
			},
		})
	}

	// Dispatch to all clients for significant actions
	if ah.isSignificantAction(action) {
		ah.dispatcher.Dispatch(events.Event{
			Type: eventType,
			Data: map[string]interface{}{
				"user_id":       userID,
				"action":        action,
				"resource_type": resourceType,
				"resource_id":   resourceID,
			},
		})
	}
}

func (ah *ActivityHandlers) shouldSuppressActivity(action string) bool {
	// Suppress read-only actions
	suppressedActions := map[string]bool{
		"view_activity":      true,
		"list_activities":    true,
		"view_stats":         true,
		"export_activities":  true,
	}
	return suppressedActions[action]
}

// RegisterActivityRoutes registers all activity routes
func RegisterActivityRoutes(r chi.Router, handlers *ActivityHandlers) {
	r.Post("/", handlers.LogActivity)
	r.Get("/user/{userID}", handlers.GetUserActivity)
	r.Get("/resource/{resourceType}/{resourceID}", handlers.GetProjectActivity)
	r.Get("/stats/{userID}", handlers.GetActivityStats)
	r.Get("/recent", handlers.GetRecentActivity)
	r.Get("/", handlers.FilterActivity)
	r.Delete("/{activityID}", handlers.DeleteActivity)
}
