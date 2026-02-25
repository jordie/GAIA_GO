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

// AuditLogHandlers handles audit logging HTTP requests
type AuditLogHandlers struct {
	service    services.AuditLogService
	errHandler *errors.Handler
}

// NewAuditLogHandlers creates new audit log handlers
func NewAuditLogHandlers(service services.AuditLogService, errHandler *errors.Handler) *AuditLogHandlers {
	return &AuditLogHandlers{
		service:    service,
		errHandler: errHandler,
	}
}

// ListAuditLogs handles GET /api/audit-logs
func (ah *AuditLogHandlers) ListAuditLogs(w http.ResponseWriter, r *http.Request) {
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

	logs, total, err := ah.service.ListAuditLogs(r.Context(), limit, offset)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"logs":   logs,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// GetAuditLog handles GET /api/audit-logs/{id}
func (ah *AuditLogHandlers) GetAuditLog(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Audit log ID is required"), httputil.GetTraceID(r))
		return
	}

	log, err := ah.service.GetAuditLog(r.Context(), id)
	if err != nil {
		ah.errHandler.Handle(w, errors.NotFoundErrorf("AUDIT_LOG_NOT_FOUND", "Audit log not found"), httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(log)
}

// GetAuditLogsByUser handles GET /api/audit-logs/by-user/{userID}
func (ah *AuditLogHandlers) GetAuditLogsByUser(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
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

	logs, total, err := ah.service.GetAuditLogsByUser(r.Context(), userID, limit, offset)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"logs":   logs,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// GetAuditLogsByAction handles GET /api/audit-logs/by-action/{action}
func (ah *AuditLogHandlers) GetAuditLogsByAction(w http.ResponseWriter, r *http.Request) {
	action := chi.URLParam(r, "action")
	if action == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ACTION", "Action is required"), httputil.GetTraceID(r))
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

	logs, total, err := ah.service.GetAuditLogsByAction(r.Context(), action, limit, offset)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"logs":   logs,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// GetRecentAuditLogs handles GET /api/audit-logs/recent
func (ah *AuditLogHandlers) GetRecentAuditLogs(w http.ResponseWriter, r *http.Request) {
	limit := 50
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	logs, err := ah.service.GetRecentAuditLogs(r.Context(), limit)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"logs":  logs,
		"limit": limit,
	})
}

// SearchAuditLogs handles POST /api/audit-logs/search
func (ah *AuditLogHandlers) SearchAuditLogs(w http.ResponseWriter, r *http.Request) {
	var req services.AuditSearchRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		ah.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	logs, total, err := ah.service.SearchAuditLogs(r.Context(), &req)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"logs":   logs,
		"total":  total,
		"limit":  req.Limit,
		"offset": req.Offset,
	})
}

// GetAuditStats handles GET /api/audit-logs/stats
func (ah *AuditLogHandlers) GetAuditStats(w http.ResponseWriter, r *http.Request) {
	stats, err := ah.service.GetAuditStats(r.Context())
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(stats)
}

// ExportAuditTrail handles GET /api/audit-logs/export
func (ah *AuditLogHandlers) ExportAuditTrail(w http.ResponseWriter, r *http.Request) {
	format := r.URL.Query().Get("format")
	if format == "" {
		format = "json"
	}

	export, err := ah.service.ExportAuditTrail(r.Context(), format)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(export)
}

// GetComplianceReport handles GET /api/audit-logs/compliance-report
func (ah *AuditLogHandlers) GetComplianceReport(w http.ResponseWriter, r *http.Request) {
	startDate := r.URL.Query().Get("start_date")
	endDate := r.URL.Query().Get("end_date")

	report, err := ah.service.GenerateComplianceReport(r.Context(), startDate, endDate)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(report)
}

// VerifyIntegrity handles GET /api/audit-logs/verify-integrity
func (ah *AuditLogHandlers) VerifyIntegrity(w http.ResponseWriter, r *http.Request) {
	result, err := ah.service.VerifyIntegrity(r.Context())
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(result)
}

// GetAuditLogsByResourceType handles GET /api/audit-logs/by-resource/{resourceType}
// Uses GetAuditLogsByResource with an empty resourceID to list by type only.
func (ah *AuditLogHandlers) GetAuditLogsByResourceType(w http.ResponseWriter, r *http.Request) {
	resourceType := chi.URLParam(r, "resourceType")
	if resourceType == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_RESOURCE_TYPE", "Resource type is required"), httputil.GetTraceID(r))
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

	logs, total, err := ah.service.GetAuditLogsByResource(r.Context(), resourceType, "", limit, offset)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"logs":   logs,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// GetAuditLogsByDateRange handles GET /api/audit-logs/date-range
// Uses SearchAuditLogs with date filters applied via the search request.
func (ah *AuditLogHandlers) GetAuditLogsByDateRange(w http.ResponseWriter, r *http.Request) {
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

	req := services.AuditSearchRequest{
		Limit:  limit,
		Offset: offset,
	}

	logs, total, err := ah.service.SearchAuditLogs(r.Context(), &req)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"logs":   logs,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// ExportAuditLogs handles GET /api/audit-logs/export-logs
// Delegates to ExportAuditTrail with the requested format.
func (ah *AuditLogHandlers) ExportAuditLogs(w http.ResponseWriter, r *http.Request) {
	format := r.URL.Query().Get("format")
	if format == "" {
		format = "json"
	}

	export, err := ah.service.ExportAuditTrail(r.Context(), format)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(export)
}

// GetActionsPerformed handles GET /api/audit-logs/actions
// Returns audit metrics which includes action breakdown information.
func (ah *AuditLogHandlers) GetActionsPerformed(w http.ResponseWriter, r *http.Request) {
	metrics, err := ah.service.GetAuditMetrics(r.Context())
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"actions": metrics,
	})
}

// GetAuditSummary handles GET /api/audit-logs/summary
// Returns audit metrics as a summary view.
func (ah *AuditLogHandlers) GetAuditSummary(w http.ResponseWriter, r *http.Request) {
	metrics, err := ah.service.GetAuditMetrics(r.Context())
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(metrics)
}

// GetUserActivity handles GET /api/audit-logs/user-activity/{userID}
func (ah *AuditLogHandlers) GetUserActivity(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if userID == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	activity, err := ah.service.GetUserActionSummary(r.Context(), userID)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(activity)
}

// GetResourceModifications handles GET /api/audit-logs/modifications/{resourceID}
func (ah *AuditLogHandlers) GetResourceModifications(w http.ResponseWriter, r *http.Request) {
	resourceID := chi.URLParam(r, "resourceID")
	if resourceID == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_RESOURCE_ID", "Resource ID is required"), httputil.GetTraceID(r))
		return
	}

	modifications, err := ah.service.GetResourceModificationHistory(r.Context(), resourceID)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(modifications)
}

// GetComplianceStatus handles GET /api/audit-logs/compliance-status
// Returns the latest integrity check status as a compliance indicator.
func (ah *AuditLogHandlers) GetComplianceStatus(w http.ResponseWriter, r *http.Request) {
	status, err := ah.service.GetIntegrityCheckStatus(r.Context())
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(status)
}

// GetAuditLogChanges handles GET /api/audit-logs/{id}/changes
// Retrieves the changes field from a specific audit log entry.
func (ah *AuditLogHandlers) GetAuditLogChanges(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Audit log ID is required"), httputil.GetTraceID(r))
		return
	}

	auditLog, err := ah.service.GetAuditLog(r.Context(), id)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"id":      auditLog.ID,
		"changes": auditLog.Changes,
	})
}

// GetAuditContext handles GET /api/audit-logs/{id}/context
// Retrieves the full context of a specific audit log entry.
func (ah *AuditLogHandlers) GetAuditContext(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Audit log ID is required"), httputil.GetTraceID(r))
		return
	}

	auditLog, err := ah.service.GetAuditLog(r.Context(), id)
	if err != nil {
		ah.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(auditLog)
}

// RegisterAuditLogRoutes registers audit log routes
func RegisterAuditLogRoutes(r interface {
	Get(pattern string, handlerFn http.HandlerFunc)
	Post(pattern string, handlerFn http.HandlerFunc)
}, handlers *AuditLogHandlers) {
	r.Get("/", handlers.ListAuditLogs)
	r.Get("/{id}", handlers.GetAuditLog)
	r.Get("/{id}/changes", handlers.GetAuditLogChanges)
	r.Get("/{id}/context", handlers.GetAuditContext)
	r.Get("/by-user/{userID}", handlers.GetAuditLogsByUser)
	r.Get("/by-action/{action}", handlers.GetAuditLogsByAction)
	r.Get("/recent", handlers.GetRecentAuditLogs)
	r.Post("/search", handlers.SearchAuditLogs)
	r.Get("/stats", handlers.GetAuditStats)
	r.Get("/export", handlers.ExportAuditTrail)
	r.Get("/compliance-report", handlers.GetComplianceReport)
	r.Get("/verify-integrity", handlers.VerifyIntegrity)
	r.Get("/by-resource/{resourceType}", handlers.GetAuditLogsByResourceType)
	r.Get("/date-range", handlers.GetAuditLogsByDateRange)
	r.Get("/export-logs", handlers.ExportAuditLogs)
	r.Get("/actions", handlers.GetActionsPerformed)
	r.Get("/summary", handlers.GetAuditSummary)
	r.Get("/user-activity/{userID}", handlers.GetUserActivity)
	r.Get("/modifications/{resourceID}", handlers.GetResourceModifications)
	r.Get("/compliance-status", handlers.GetComplianceStatus)
}
