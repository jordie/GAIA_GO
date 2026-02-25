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

// IntegrationHealthHandlers handles integration health HTTP requests
type IntegrationHealthHandlers struct {
	service    services.IntegrationHealthService
	errHandler *errors.Handler
}

// NewIntegrationHealthHandlers creates new integration health handlers
func NewIntegrationHealthHandlers(service services.IntegrationHealthService, errHandler *errors.Handler) *IntegrationHealthHandlers {
	return &IntegrationHealthHandlers{
		service:    service,
		errHandler: errHandler,
	}
}

// GetOverallHealth handles GET /api/health/overall
func (ih *IntegrationHealthHandlers) GetOverallHealth(w http.ResponseWriter, r *http.Request) {
	health, err := ih.service.GetOverallHealth(r.Context())
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(health)
}

// CheckIntegrationHealth handles GET /api/health/integrations/{integrationID}
func (ih *IntegrationHealthHandlers) CheckIntegrationHealth(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	if integrationID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	health, err := ih.service.CheckIntegrationHealth(r.Context(), integrationID)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(health)
}

// CheckHealthByType handles GET /api/health/by-type/{type}
func (ih *IntegrationHealthHandlers) CheckHealthByType(w http.ResponseWriter, r *http.Request) {
	integrationType := chi.URLParam(r, "type")
	if integrationType == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_TYPE", "Integration type is required"), httputil.GetTraceID(r))
		return
	}

	health, err := ih.service.CheckHealthByType(r.Context(), integrationType)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(health)
}

// GetCriticalIssues handles GET /api/health/critical-issues
func (ih *IntegrationHealthHandlers) GetCriticalIssues(w http.ResponseWriter, r *http.Request) {
	issues, err := ih.service.GetCriticalIssues(r.Context())
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"issues": issues,
		"count":  len(issues),
	})
}

// GetWarnings handles GET /api/health/warnings
func (ih *IntegrationHealthHandlers) GetWarnings(w http.ResponseWriter, r *http.Request) {
	warnings, err := ih.service.GetWarnings(r.Context())
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"warnings": warnings,
		"count":    len(warnings),
	})
}

// RunFullHealthCheck handles POST /api/health/check
func (ih *IntegrationHealthHandlers) RunFullHealthCheck(w http.ResponseWriter, r *http.Request) {
	result, err := ih.service.RunFullHealthCheck(r.Context())
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(result)
}

// RunIntegrationHealthCheck handles POST /api/health/check/{integrationID}
func (ih *IntegrationHealthHandlers) RunIntegrationHealthCheck(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	if integrationID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	result, err := ih.service.RunIntegrationHealthCheck(r.Context(), integrationID)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(result)
}

// GetDiagnostics handles GET /api/health/diagnostics/{integrationID}
func (ih *IntegrationHealthHandlers) GetDiagnostics(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	if integrationID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	diags, err := ih.service.GetDiagnostics(r.Context(), integrationID)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(diags)
}

// GetMetrics handles GET /api/health/metrics/{integrationID}
func (ih *IntegrationHealthHandlers) GetMetrics(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	if integrationID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	metrics, err := ih.service.GetMetrics(r.Context(), integrationID)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(metrics)
}

// GetComponentMetrics handles GET /api/health/metrics/{integrationID}/components/{component}
func (ih *IntegrationHealthHandlers) GetComponentMetrics(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	component := chi.URLParam(r, "component")
	if integrationID == "" || component == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_PARAMS", "Integration ID and component are required"), httputil.GetTraceID(r))
		return
	}

	metrics, err := ih.service.GetComponentMetrics(r.Context(), integrationID, component)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(metrics)
}

// GetDependencyStatus handles GET /api/health/dependencies/{integrationID}
func (ih *IntegrationHealthHandlers) GetDependencyStatus(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	if integrationID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	status, err := ih.service.GetDependencyStatus(r.Context(), integrationID)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(status)
}

// GetUptimeStats handles GET /api/health/uptime/{integrationID}
func (ih *IntegrationHealthHandlers) GetUptimeStats(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	period := r.URL.Query().Get("period")
	if integrationID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}
	if period == "" {
		period = "7d"
	}

	uptime, err := ih.service.GetUptimeStats(r.Context(), integrationID, period)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(uptime)
}

// GetIncidentHistory handles GET /api/health/incidents/{integrationID}
func (ih *IntegrationHealthHandlers) GetIncidentHistory(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	if integrationID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
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

	incidents, total, err := ih.service.GetIncidentHistory(r.Context(), integrationID, limit, offset)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"incidents": incidents,
		"total":     total,
		"limit":     limit,
		"offset":    offset,
	})
}

// ReportIncident handles POST /api/health/incidents/{integrationID}/report
func (ih *IntegrationHealthHandlers) ReportIncident(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	if integrationID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	var req struct {
		Severity    string `json:"severity"`
		Description string `json:"description"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		ih.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if req.Severity == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_SEVERITY", "Severity is required"), httputil.GetTraceID(r))
		return
	}
	if req.Description == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_DESCRIPTION", "Description is required"), httputil.GetTraceID(r))
		return
	}

	incidentID, err := ih.service.ReportIncident(r.Context(), integrationID, req.Severity, req.Description)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]string{
		"incident_id": incidentID,
	})
}

// ResolveIncident handles POST /api/health/incidents/{incidentID}/resolve
func (ih *IntegrationHealthHandlers) ResolveIncident(w http.ResponseWriter, r *http.Request) {
	incidentID := chi.URLParam(r, "incidentID")
	if incidentID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INCIDENT_ID", "Incident ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := ih.service.ResolveIncident(r.Context(), incidentID); err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{
		"status": "resolved",
	})
}

// GetActiveIncidents handles GET /api/health/incidents/active
func (ih *IntegrationHealthHandlers) GetActiveIncidents(w http.ResponseWriter, r *http.Request) {
	incidents, err := ih.service.GetActiveIncidents(r.Context())
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"incidents": incidents,
		"count":     len(incidents),
	})
}

// GetActiveAlerts handles GET /api/health/alerts/active
func (ih *IntegrationHealthHandlers) GetActiveAlerts(w http.ResponseWriter, r *http.Request) {
	alerts, err := ih.service.GetActiveAlerts(r.Context())
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"alerts": alerts,
		"count":  len(alerts),
	})
}

// GetAlertHistory handles GET /api/health/alerts/history
func (ih *IntegrationHealthHandlers) GetAlertHistory(w http.ResponseWriter, r *http.Request) {
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

	alerts, total, err := ih.service.GetAlertHistory(r.Context(), limit, offset)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"alerts": alerts,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// GetResponseTimeAnalytics handles GET /api/health/analytics/response-time/{integrationID}
func (ih *IntegrationHealthHandlers) GetResponseTimeAnalytics(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	timeframe := r.URL.Query().Get("timeframe")
	if integrationID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}
	if timeframe == "" {
		timeframe = "24h"
	}

	analytics, err := ih.service.GetResponseTimeAnalytics(r.Context(), integrationID, timeframe)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(analytics)
}

// GetErrorRateAnalytics handles GET /api/health/analytics/error-rate/{integrationID}
func (ih *IntegrationHealthHandlers) GetErrorRateAnalytics(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	timeframe := r.URL.Query().Get("timeframe")
	if integrationID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}
	if timeframe == "" {
		timeframe = "24h"
	}

	analytics, err := ih.service.GetErrorRateAnalytics(r.Context(), integrationID, timeframe)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(analytics)
}

// GetSLAStatus handles GET /api/health/sla/{integrationID}
func (ih *IntegrationHealthHandlers) GetSLAStatus(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	if integrationID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	status, err := ih.service.GetSLAStatus(r.Context(), integrationID)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(status)
}

// GetSLAViolations handles GET /api/health/sla/{integrationID}/violations
func (ih *IntegrationHealthHandlers) GetSLAViolations(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	if integrationID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
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

	violations, total, err := ih.service.GetSLAViolations(r.Context(), integrationID, limit, offset)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"violations": violations,
		"total":      total,
		"limit":      limit,
		"offset":     offset,
	})
}

// GetHealthTrend handles GET /api/health/trends/{integrationID}
func (ih *IntegrationHealthHandlers) GetHealthTrend(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	timeframe := r.URL.Query().Get("timeframe")
	if integrationID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}
	if timeframe == "" {
		timeframe = "7d"
	}

	trend, err := ih.service.GetHealthTrend(r.Context(), integrationID, timeframe)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(trend)
}

// GetResourceUtilization handles GET /api/health/resources/{integrationID}
func (ih *IntegrationHealthHandlers) GetResourceUtilization(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	if integrationID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	resources, err := ih.service.GetResourceUtilization(r.Context(), integrationID)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(resources)
}

// GetComplianceStatus handles GET /api/health/compliance/{integrationID}
func (ih *IntegrationHealthHandlers) GetComplianceStatus(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	if integrationID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	status, err := ih.service.GetComplianceStatus(r.Context(), integrationID)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(status)
}

// GetSecurityStatus handles GET /api/health/security/{integrationID}
func (ih *IntegrationHealthHandlers) GetSecurityStatus(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	if integrationID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	status, err := ih.service.GetSecurityStatus(r.Context(), integrationID)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(status)
}

// GetAuditReport handles GET /api/health/audit-report/{integrationID}
func (ih *IntegrationHealthHandlers) GetAuditReport(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	timeframe := r.URL.Query().Get("timeframe")
	if integrationID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}
	if timeframe == "" {
		timeframe = "30d"
	}

	report, err := ih.service.GetAuditReport(r.Context(), integrationID, timeframe)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(report)
}

// GetLatencyPercentiles handles GET /api/health/latency/{integrationID}
func (ih *IntegrationHealthHandlers) GetLatencyPercentiles(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	if integrationID == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	percentiles, err := ih.service.GetLatencyPercentiles(r.Context(), integrationID)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(percentiles)
}

// RegisterIntegrationHealthRoutes registers integration health routes
func RegisterIntegrationHealthRoutes(r interface {
	Get(pattern string, handlerFn http.HandlerFunc)
	Post(pattern string, handlerFn http.HandlerFunc)
}, handlers *IntegrationHealthHandlers) {
	r.Get("/overall", handlers.GetOverallHealth)
	r.Get("/integrations/{integrationID}", handlers.CheckIntegrationHealth)
	r.Get("/by-type/{type}", handlers.CheckHealthByType)
	r.Get("/critical-issues", handlers.GetCriticalIssues)
	r.Get("/warnings", handlers.GetWarnings)
	r.Post("/check", handlers.RunFullHealthCheck)
	r.Post("/check/{integrationID}", handlers.RunIntegrationHealthCheck)
	r.Get("/diagnostics/{integrationID}", handlers.GetDiagnostics)
	r.Get("/metrics/{integrationID}", handlers.GetMetrics)
	r.Get("/metrics/{integrationID}/components/{component}", handlers.GetComponentMetrics)
	r.Get("/dependencies/{integrationID}", handlers.GetDependencyStatus)
	r.Get("/uptime/{integrationID}", handlers.GetUptimeStats)
	r.Get("/incidents/{integrationID}", handlers.GetIncidentHistory)
	r.Post("/incidents/{integrationID}/report", handlers.ReportIncident)
	r.Post("/incidents/{incidentID}/resolve", handlers.ResolveIncident)
	r.Get("/incidents/active", handlers.GetActiveIncidents)
	r.Get("/alerts/active", handlers.GetActiveAlerts)
	r.Get("/alerts/history", handlers.GetAlertHistory)
	r.Get("/analytics/response-time/{integrationID}", handlers.GetResponseTimeAnalytics)
	r.Get("/analytics/error-rate/{integrationID}", handlers.GetErrorRateAnalytics)
	r.Get("/sla/{integrationID}", handlers.GetSLAStatus)
	r.Get("/sla/{integrationID}/violations", handlers.GetSLAViolations)
	r.Get("/trends/{integrationID}", handlers.GetHealthTrend)
	r.Get("/resources/{integrationID}", handlers.GetResourceUtilization)
	r.Get("/compliance/{integrationID}", handlers.GetComplianceStatus)
	r.Get("/security/{integrationID}", handlers.GetSecurityStatus)
	r.Get("/audit-report/{integrationID}", handlers.GetAuditReport)
	r.Get("/latency/{integrationID}", handlers.GetLatencyPercentiles)
}
