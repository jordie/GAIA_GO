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

// EventLogHandlers handles event logging HTTP requests
type EventLogHandlers struct {
	service    services.EventLogService
	errHandler *errors.Handler
}

// NewEventLogHandlers creates new event log handlers
func NewEventLogHandlers(service services.EventLogService, errHandler *errors.Handler) *EventLogHandlers {
	return &EventLogHandlers{
		service:    service,
		errHandler: errHandler,
	}
}

// ListEvents handles GET /api/events
func (eh *EventLogHandlers) ListEvents(w http.ResponseWriter, r *http.Request) {
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

	req := &services.ListEventsRequest{
		Type:      r.URL.Query().Get("type"),
		Source:    r.URL.Query().Get("source"),
		UserID:    r.URL.Query().Get("user_id"),
		ProjectID: r.URL.Query().Get("project_id"),
		Limit:     limit,
		Offset:    offset,
	}

	events, total, err := eh.service.ListEvents(r.Context(), req)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"events": events,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// GetEvent handles GET /api/events/{id}
func (eh *EventLogHandlers) GetEvent(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Event ID is required"), httputil.GetTraceID(r))
		return
	}

	event, err := eh.service.GetEvent(r.Context(), id)
	if err != nil {
		eh.errHandler.Handle(w, errors.NotFoundErrorf("EVENT_NOT_FOUND", "Event not found"), httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"event": event})
}

// CreateEvent handles POST /api/events
func (eh *EventLogHandlers) CreateEvent(w http.ResponseWriter, r *http.Request) {
	var req services.CreateEventRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		eh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if req.Type == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_TYPE", "Event type is required"), httputil.GetTraceID(r))
		return
	}

	event, err := eh.service.CreateEvent(r.Context(), &req)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]interface{}{"event": event})
}

// UpdateEvent handles PUT /api/events/{id}
func (eh *EventLogHandlers) UpdateEvent(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Event ID is required"), httputil.GetTraceID(r))
		return
	}

	var req services.UpdateEventRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		eh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	event, err := eh.service.UpdateEvent(r.Context(), id, &req)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(event)
}

// DeleteEvent handles DELETE /api/events/{id}
func (eh *EventLogHandlers) DeleteEvent(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Event ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := eh.service.DeleteEvents(r.Context(), []string{id}); err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// GetEventsByType handles GET /api/events/by-type/{type}
func (eh *EventLogHandlers) GetEventsByType(w http.ResponseWriter, r *http.Request) {
	eventType := chi.URLParam(r, "type")
	if eventType == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_TYPE", "Event type is required"), httputil.GetTraceID(r))
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

	events, total, err := eh.service.GetEventsByType(r.Context(), eventType, limit, offset)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"events": events,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// GetEventsByUser handles GET /api/events/by-user/{userID}
func (eh *EventLogHandlers) GetEventsByUser(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
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

	events, total, err := eh.service.GetEventsByUser(r.Context(), userID, limit, offset)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"events": events,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// GetEventsByProject handles GET /api/events/by-project/{projectID}
func (eh *EventLogHandlers) GetEventsByProject(w http.ResponseWriter, r *http.Request) {
	projectID := chi.URLParam(r, "projectID")
	if projectID == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_PROJECT_ID", "Project ID is required"), httputil.GetTraceID(r))
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

	events, total, err := eh.service.GetEventsByProject(r.Context(), projectID, limit, offset)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"events": events,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// SearchEvents handles POST /api/events/search
func (eh *EventLogHandlers) SearchEvents(w http.ResponseWriter, r *http.Request) {
	var req services.EventSearchRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		eh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if req.Query == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_QUERY", "Search query is required"), httputil.GetTraceID(r))
		return
	}

	events, total, err := eh.service.SearchEvents(r.Context(), &req)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"events": events,
		"total":  total,
		"limit":  req.Limit,
		"offset": req.Offset,
	})
}

// GetEventStats handles GET /api/events/stats
func (eh *EventLogHandlers) GetEventStats(w http.ResponseWriter, r *http.Request) {
	startDate := r.URL.Query().Get("start_date")
	endDate := r.URL.Query().Get("end_date")

	stats, err := eh.service.GetEventStats(r.Context(), startDate, endDate)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(stats)
}

// GetTrendingEvents handles GET /api/events/trending
func (eh *EventLogHandlers) GetTrendingEvents(w http.ResponseWriter, r *http.Request) {
	timeWindow := r.URL.Query().Get("window")
	if timeWindow == "" {
		timeWindow = "24h"
	}
	limit := 10
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	events, err := eh.service.GetTrendingEvents(r.Context(), timeWindow, limit)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"events": events,
		"window": timeWindow,
		"limit":  limit,
	})
}

// GetEventTimeline handles GET /api/events/timeline
func (eh *EventLogHandlers) GetEventTimeline(w http.ResponseWriter, r *http.Request) {
	req := &services.ListEventsRequest{
		Limit:  50,
		Offset: 0,
	}
	if limit := r.URL.Query().Get("limit"); limit != "" {
		if parsed, err := strconv.Atoi(limit); err == nil && parsed > 0 {
			req.Limit = parsed
		}
	}

	timeline, err := eh.service.GetEventTimeline(r.Context(), req)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(timeline)
}

// ExportEvents handles GET /api/events/export
func (eh *EventLogHandlers) ExportEvents(w http.ResponseWriter, r *http.Request) {
	format := r.URL.Query().Get("format")
	if format == "" {
		format = "json"
	}

	export, err := eh.service.ExportEvents(r.Context(), format, nil)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(export)
}

// ArchiveEvents handles DELETE /api/events/archive
func (eh *EventLogHandlers) ArchiveEvents(w http.ResponseWriter, r *http.Request) {
	var req struct {
		EventIDs []string `json:"event_ids"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		eh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if len(req.EventIDs) == 0 {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_EVENT_IDS", "Event IDs are required"), httputil.GetTraceID(r))
		return
	}

	if err := eh.service.ArchiveEvents(r.Context(), req.EventIDs); err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// GetEventsByTag handles GET /api/events/by-tag/{tag}
func (eh *EventLogHandlers) GetEventsByTag(w http.ResponseWriter, r *http.Request) {
	tag := chi.URLParam(r, "tag")
	if tag == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_TAG", "Tag is required"), httputil.GetTraceID(r))
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

	events, total, err := eh.service.GetEventsByTag(r.Context(), tag, limit, offset)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"events": events,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// GetEventSources handles GET /api/events/sources
func (eh *EventLogHandlers) GetEventSources(w http.ResponseWriter, r *http.Request) {
	sources, err := eh.service.GetEventSources(r.Context())
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"sources": sources,
	})
}

// GetEventTypes handles GET /api/events/types
func (eh *EventLogHandlers) GetEventTypes(w http.ResponseWriter, r *http.Request) {
	types, err := eh.service.GetEventTypes(r.Context())
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"types": types,
	})
}

// GetRetentionPolicy handles GET /api/events/retention
func (eh *EventLogHandlers) GetRetentionPolicy(w http.ResponseWriter, r *http.Request) {
	policy, err := eh.service.GetRetentionPolicy(r.Context())
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(policy)
}

// UpdateRetentionPolicy handles PUT /api/events/retention
func (eh *EventLogHandlers) UpdateRetentionPolicy(w http.ResponseWriter, r *http.Request) {
	var policy map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&policy); err != nil {
		eh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := eh.service.UpdateRetentionPolicy(r.Context(), policy); err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{
		"status": "updated",
	})
}

// SubscribeToEventType handles POST /api/events/subscriptions/{type}
func (eh *EventLogHandlers) SubscribeToEventType(w http.ResponseWriter, r *http.Request) {
	eventType := chi.URLParam(r, "type")
	if eventType == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_TYPE", "Event type is required"), httputil.GetTraceID(r))
		return
	}

	var req struct {
		UserID string `json:"user_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		eh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := eh.service.SubscribeToEventType(r.Context(), req.UserID, eventType); err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]string{
		"status": "subscribed",
	})
}

// GetUserSubscriptions handles GET /api/events/subscriptions/user/{userID}
func (eh *EventLogHandlers) GetUserSubscriptions(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	subscriptions, err := eh.service.GetUserSubscriptions(r.Context(), userID)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"subscriptions": subscriptions,
	})
}

// BulkCreateEvents handles POST /api/events/bulk
func (eh *EventLogHandlers) BulkCreateEvents(w http.ResponseWriter, r *http.Request) {
	var rawRequests []services.CreateEventRequest
	if err := json.NewDecoder(r.Body).Decode(&rawRequests); err != nil {
		eh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if len(rawRequests) == 0 {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_EVENTS", "At least one event is required"), httputil.GetTraceID(r))
		return
	}

	requests := make([]*services.CreateEventRequest, len(rawRequests))
	for i := range rawRequests {
		requests[i] = &rawRequests[i]
	}

	events, err := eh.service.BulkCreateEvents(r.Context(), requests)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"events": events,
		"count":  len(events),
	})
}

// RegisterEventLogRoutes registers event log routes
func RegisterEventLogRoutes(r interface {
	Get(pattern string, handlerFn http.HandlerFunc)
	Post(pattern string, handlerFn http.HandlerFunc)
	Put(pattern string, handlerFn http.HandlerFunc)
	Delete(pattern string, handlerFn http.HandlerFunc)
}, handlers *EventLogHandlers) {
	r.Get("/", handlers.ListEvents)
	r.Post("/", handlers.CreateEvent)
	r.Get("/{id}", handlers.GetEvent)
	r.Put("/{id}", handlers.UpdateEvent)
	r.Delete("/{id}", handlers.DeleteEvent)
	r.Get("/by-type/{type}", handlers.GetEventsByType)
	r.Get("/by-user/{userID}", handlers.GetEventsByUser)
	r.Get("/by-project/{projectID}", handlers.GetEventsByProject)
	r.Post("/search", handlers.SearchEvents)
	r.Get("/stats", handlers.GetEventStats)
	r.Get("/trending", handlers.GetTrendingEvents)
	r.Get("/timeline", handlers.GetEventTimeline)
	r.Get("/export", handlers.ExportEvents)
	r.Delete("/archive", handlers.ArchiveEvents)
	r.Get("/by-tag/{tag}", handlers.GetEventsByTag)
	r.Get("/sources", handlers.GetEventSources)
	r.Get("/types", handlers.GetEventTypes)
	r.Get("/retention", handlers.GetRetentionPolicy)
	r.Put("/retention", handlers.UpdateRetentionPolicy)
	r.Post("/subscriptions/{type}", handlers.SubscribeToEventType)
	r.Get("/subscriptions/user/{userID}", handlers.GetUserSubscriptions)
	r.Post("/bulk", handlers.BulkCreateEvents)
}
