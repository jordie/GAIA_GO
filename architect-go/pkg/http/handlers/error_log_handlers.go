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

// ErrorLogHandlers handles error logging HTTP requests
type ErrorLogHandlers struct {
	service    services.ErrorLogService
	errHandler *errors.Handler
}

// NewErrorLogHandlers creates new error log handlers
func NewErrorLogHandlers(service services.ErrorLogService, errHandler *errors.Handler) *ErrorLogHandlers {
	return &ErrorLogHandlers{
		service:    service,
		errHandler: errHandler,
	}
}

// LogError handles POST /api/errors
func (eh *ErrorLogHandlers) LogError(w http.ResponseWriter, r *http.Request) {
	var req services.LogErrorRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		eh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	errorLog, err := eh.service.LogError(r.Context(), &req)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]interface{}{"error": errorLog})
}

// GetError handles GET /api/errors/{id}
func (eh *ErrorLogHandlers) GetError(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Error ID is required"), httputil.GetTraceID(r))
		return
	}

	errorLog, err := eh.service.GetError(r.Context(), id)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"error": errorLog})
}

// ListErrors handles GET /api/errors
func (eh *ErrorLogHandlers) ListErrors(w http.ResponseWriter, r *http.Request) {
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

	var req services.LogErrorRequest
	errorLogs, total, err := eh.service.ListErrors(r.Context(), &req, limit, offset)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"errors": errorLogs,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// ListErrorsByType handles GET /api/errors/by-type/{type}
func (eh *ErrorLogHandlers) ListErrorsByType(w http.ResponseWriter, r *http.Request) {
	errorType := chi.URLParam(r, "type")
	if errorType == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_TYPE", "Error type is required"), httputil.GetTraceID(r))
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

	errorLogs, total, err := eh.service.ListErrorsByType(r.Context(), errorType, limit, offset)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"errors": errorLogs,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// ListCriticalErrors handles GET /api/errors/critical
func (eh *ErrorLogHandlers) ListCriticalErrors(w http.ResponseWriter, r *http.Request) {
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

	errorLogs, total, err := eh.service.ListCriticalErrors(r.Context(), limit, offset)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"errors": errorLogs,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// ListRecentErrors handles GET /api/errors/recent
func (eh *ErrorLogHandlers) ListRecentErrors(w http.ResponseWriter, r *http.Request) {
	limit := 10
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	errorLogs, err := eh.service.ListRecentErrors(r.Context(), limit)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"errors": errorLogs})
}

// UpdateErrorStatus handles PUT /api/errors/{id}/status
func (eh *ErrorLogHandlers) UpdateErrorStatus(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Error ID is required"), httputil.GetTraceID(r))
		return
	}

	var req services.ResolveErrorRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		eh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	errorLog, err := eh.service.UpdateErrorStatus(r.Context(), id, &req)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(errorLog)
}

// ResolveError handles POST /api/errors/{id}/resolve
func (eh *ErrorLogHandlers) ResolveError(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Error ID is required"), httputil.GetTraceID(r))
		return
	}

	var req services.ResolveErrorRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		eh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := eh.service.ResolveError(r.Context(), id, &req); err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "resolved"})
}

// DismissError handles POST /api/errors/{id}/dismiss
func (eh *ErrorLogHandlers) DismissError(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Error ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := eh.service.DismissError(r.Context(), id); err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "dismissed"})
}

// DeleteError handles DELETE /api/errors/{id}
func (eh *ErrorLogHandlers) DeleteError(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Error ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := eh.service.DeleteError(r.Context(), id); err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// CreateBugFromError handles POST /api/errors/{id}/create-bug
func (eh *ErrorLogHandlers) CreateBugFromError(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Error ID is required"), httputil.GetTraceID(r))
		return
	}

	var req services.CreateBugFromErrorRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		eh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	bug, err := eh.service.CreateBugFromError(r.Context(), id, &req)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(bug)
}

// GetErrorHistory handles GET /api/errors/{id}/history
func (eh *ErrorLogHandlers) GetErrorHistory(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Error ID is required"), httputil.GetTraceID(r))
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

	errorLogs, total, err := eh.service.GetErrorHistory(r.Context(), id, limit, offset)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"errors": errorLogs,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// GetErrorStats handles GET /api/errors/stats
func (eh *ErrorLogHandlers) GetErrorStats(w http.ResponseWriter, r *http.Request) {
	var req services.ErrorStatsRequest
	stats, err := eh.service.GetErrorStats(r.Context(), &req)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(stats)
}

// GetTrendingErrors handles GET /api/errors/trending
func (eh *ErrorLogHandlers) GetTrendingErrors(w http.ResponseWriter, r *http.Request) {
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

	errorLogs, err := eh.service.GetTrendingErrors(r.Context(), timeWindow, limit)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"errors": errorLogs,
		"window": timeWindow,
		"limit":  limit,
	})
}

// SearchErrors handles GET /api/errors/search
func (eh *ErrorLogHandlers) SearchErrors(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query().Get("q")
	if query == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_QUERY", "Search query is required"), httputil.GetTraceID(r))
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

	errorLogs, total, err := eh.service.SearchErrors(r.Context(), query, limit, offset)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"errors": errorLogs,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// ExportErrors handles GET /api/errors/export
func (eh *ErrorLogHandlers) ExportErrors(w http.ResponseWriter, r *http.Request) {
	format := r.URL.Query().Get("format")
	if format == "" {
		format = "json"
	}

	export, err := eh.service.ExportErrors(r.Context(), format)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(export)
}

// GetFullStackTrace handles GET /api/errors/{id}/stack-trace
func (eh *ErrorLogHandlers) GetFullStackTrace(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Error ID is required"), httputil.GetTraceID(r))
		return
	}

	stackTrace, err := eh.service.GetFullStackTrace(r.Context(), id)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "text/plain")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(stackTrace))
}

// AddErrorTag handles POST /api/errors/{id}/tags/{tag}
func (eh *ErrorLogHandlers) AddErrorTag(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	tag := chi.URLParam(r, "tag")
	if id == "" || tag == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_PARAMS", "Error ID and tag are required"), httputil.GetTraceID(r))
		return
	}

	if err := eh.service.AddErrorTag(r.Context(), id, tag); err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "tagged"})
}

// RemoveErrorTag handles DELETE /api/errors/{id}/tags/{tag}
func (eh *ErrorLogHandlers) RemoveErrorTag(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	tag := chi.URLParam(r, "tag")
	if id == "" || tag == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_PARAMS", "Error ID and tag are required"), httputil.GetTraceID(r))
		return
	}

	if err := eh.service.RemoveErrorTag(r.Context(), id, tag); err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// GetErrorsByTag handles GET /api/errors/by-tag/{tag}
func (eh *ErrorLogHandlers) GetErrorsByTag(w http.ResponseWriter, r *http.Request) {
	tag := chi.URLParam(r, "tag")
	if tag == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_TAG", "Tag is required"), httputil.GetTraceID(r))
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

	errorLogs, total, err := eh.service.GetErrorsByTag(r.Context(), tag, limit, offset)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"errors": errorLogs,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// GetErrorGroups handles GET /api/errors/groups
func (eh *ErrorLogHandlers) GetErrorGroups(w http.ResponseWriter, r *http.Request) {
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

	groups, total, err := eh.service.GetErrorGroups(r.Context(), limit, offset)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"groups": groups,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// GetActiveAlerts handles GET /api/errors/alerts/active
func (eh *ErrorLogHandlers) GetActiveAlerts(w http.ResponseWriter, r *http.Request) {
	alerts, err := eh.service.GetActiveAlerts(r.Context())
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"alerts": alerts})
}

// CreateAlert handles POST /api/errors/alerts
func (eh *ErrorLogHandlers) CreateAlert(w http.ResponseWriter, r *http.Request) {
	var req services.ErrorAlertRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		eh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	alertID, err := eh.service.CreateAlert(r.Context(), &req)
	if err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]string{"alert_id": alertID})
}

// DeleteAlert handles DELETE /api/errors/alerts/{alertID}
func (eh *ErrorLogHandlers) DeleteAlert(w http.ResponseWriter, r *http.Request) {
	alertID := chi.URLParam(r, "alertID")
	if alertID == "" {
		eh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ALERT_ID", "Alert ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := eh.service.DeleteAlert(r.Context(), alertID); err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// BulkDeleteErrors handles POST /api/errors/bulk-delete
func (eh *ErrorLogHandlers) BulkDeleteErrors(w http.ResponseWriter, r *http.Request) {
	var req struct {
		ErrorIDs []string `json:"error_ids"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		eh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := eh.service.BulkDeleteErrors(r.Context(), req.ErrorIDs); err != nil {
		eh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// RegisterErrorLogRoutes registers error log routes
func RegisterErrorLogRoutes(r interface {
	Get(pattern string, handlerFn http.HandlerFunc)
	Post(pattern string, handlerFn http.HandlerFunc)
	Put(pattern string, handlerFn http.HandlerFunc)
	Delete(pattern string, handlerFn http.HandlerFunc)
}, handlers *ErrorLogHandlers) {
	r.Post("/", handlers.LogError)
	r.Get("/", handlers.ListErrors)
	r.Get("/{id}", handlers.GetError)
	r.Put("/{id}/status", handlers.UpdateErrorStatus)
	r.Post("/{id}/resolve", handlers.ResolveError)
	r.Post("/{id}/dismiss", handlers.DismissError)
	r.Delete("/{id}", handlers.DeleteError)
	r.Post("/{id}/create-bug", handlers.CreateBugFromError)
	r.Get("/{id}/history", handlers.GetErrorHistory)
	r.Get("/{id}/stack-trace", handlers.GetFullStackTrace)
	r.Post("/{id}/tags/{tag}", handlers.AddErrorTag)
	r.Delete("/{id}/tags/{tag}", handlers.RemoveErrorTag)
	r.Get("/by-type/{type}", handlers.ListErrorsByType)
	r.Get("/by-tag/{tag}", handlers.GetErrorsByTag)
	r.Get("/critical", handlers.ListCriticalErrors)
	r.Get("/recent", handlers.ListRecentErrors)
	r.Get("/stats", handlers.GetErrorStats)
	r.Get("/trending", handlers.GetTrendingErrors)
	r.Get("/search", handlers.SearchErrors)
	r.Get("/export", handlers.ExportErrors)
	r.Get("/groups", handlers.GetErrorGroups)
	r.Get("/alerts/active", handlers.GetActiveAlerts)
	r.Post("/alerts", handlers.CreateAlert)
	r.Delete("/alerts/{alertID}", handlers.DeleteAlert)
	r.Post("/bulk-delete", handlers.BulkDeleteErrors)
}
