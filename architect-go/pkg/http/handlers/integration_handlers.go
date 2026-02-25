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

// IntegrationHandlers handles integration management HTTP requests
type IntegrationHandlers struct {
	service    services.IntegrationService
	errHandler *errors.Handler
}

// NewIntegrationHandlers creates new integration handlers
func NewIntegrationHandlers(service services.IntegrationService, errHandler *errors.Handler) *IntegrationHandlers {
	return &IntegrationHandlers{
		service:    service,
		errHandler: errHandler,
	}
}

// CreateIntegration handles POST /api/integrations
func (ih *IntegrationHandlers) CreateIntegration(w http.ResponseWriter, r *http.Request) {
	var req services.CreateIntegrationRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		ih.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if req.Provider == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_PROVIDER", "Provider is required"), httputil.GetTraceID(r))
		return
	}

	integration, err := ih.service.CreateIntegration(r.Context(), &req)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]interface{}{"integration": integration})
}

// GetIntegration handles GET /api/integrations/{id}
func (ih *IntegrationHandlers) GetIntegration(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	integration, err := ih.service.GetIntegration(r.Context(), id)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"integration": integration})
}

// ListIntegrations handles GET /api/integrations
func (ih *IntegrationHandlers) ListIntegrations(w http.ResponseWriter, r *http.Request) {
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

	integrations, total, err := ih.service.ListIntegrations(r.Context(), limit, offset)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"integrations": integrations,
		"total":        total,
		"limit":        limit,
		"offset":       offset,
	})
}

// ListIntegrationsByType handles GET /api/integrations/by-type/{type}
func (ih *IntegrationHandlers) ListIntegrationsByType(w http.ResponseWriter, r *http.Request) {
	integrationType := chi.URLParam(r, "type")
	if integrationType == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_TYPE", "Type is required"), httputil.GetTraceID(r))
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

	integrations, total, err := ih.service.ListIntegrationsByType(r.Context(), integrationType, limit, offset)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"integrations": integrations,
		"total":        total,
		"limit":        limit,
		"offset":       offset,
	})
}

// ListIntegrationsByProvider handles GET /api/integrations/by-provider/{provider}
func (ih *IntegrationHandlers) ListIntegrationsByProvider(w http.ResponseWriter, r *http.Request) {
	provider := chi.URLParam(r, "provider")
	if provider == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_PROVIDER", "Provider is required"), httputil.GetTraceID(r))
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

	integrations, total, err := ih.service.ListIntegrationsByProvider(r.Context(), provider, limit, offset)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"integrations": integrations,
		"total":        total,
		"limit":        limit,
		"offset":       offset,
	})
}

// ListEnabledIntegrations handles GET /api/integrations/enabled
func (ih *IntegrationHandlers) ListEnabledIntegrations(w http.ResponseWriter, r *http.Request) {
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

	integrations, total, err := ih.service.ListEnabledIntegrations(r.Context(), limit, offset)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"integrations": integrations,
		"total":        total,
		"limit":        limit,
		"offset":       offset,
	})
}

// UpdateIntegration handles PUT /api/integrations/{id}
func (ih *IntegrationHandlers) UpdateIntegration(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	var req services.UpdateIntegrationRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		ih.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	integration, err := ih.service.UpdateIntegration(r.Context(), id, &req)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(integration)
}

// DeleteIntegration handles DELETE /api/integrations/{id}
func (ih *IntegrationHandlers) DeleteIntegration(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := ih.service.DeleteIntegration(r.Context(), id); err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// EnableIntegration handles POST /api/integrations/{id}/enable
func (ih *IntegrationHandlers) EnableIntegration(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := ih.service.EnableIntegration(r.Context(), id); err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "enabled"})
}

// DisableIntegration handles POST /api/integrations/{id}/disable
func (ih *IntegrationHandlers) DisableIntegration(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := ih.service.DisableIntegration(r.Context(), id); err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "disabled"})
}

// TestConnection handles POST /api/integrations/test-connection
func (ih *IntegrationHandlers) TestConnection(w http.ResponseWriter, r *http.Request) {
	var req services.TestConnectionRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		ih.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	success, err := ih.service.TestConnection(r.Context(), &req)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]bool{"success": success})
}

// TestIntegrationConnection handles POST /api/integrations/{id}/test
func (ih *IntegrationHandlers) TestIntegrationConnection(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	success, err := ih.service.TestIntegrationConnection(r.Context(), id)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]bool{"success": success})
}

// ReconnectIntegration handles POST /api/integrations/{id}/reconnect
func (ih *IntegrationHandlers) ReconnectIntegration(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := ih.service.ReconnectIntegration(r.Context(), id); err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "reconnected"})
}

// GetIntegrationStatus handles GET /api/integrations/{id}/status
func (ih *IntegrationHandlers) GetIntegrationStatus(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	status, err := ih.service.GetIntegrationStatus(r.Context(), id)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(status)
}

// SyncData handles POST /api/integrations/{id}/sync
func (ih *IntegrationHandlers) SyncData(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := ih.service.SyncData(r.Context(), id); err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "syncing"})
}

// GetSyncStatus handles GET /api/integrations/{id}/sync-status
func (ih *IntegrationHandlers) GetSyncStatus(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	status, err := ih.service.GetSyncStatus(r.Context(), id)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(status)
}

// GetIntegrationTypes handles GET /api/integrations/types
func (ih *IntegrationHandlers) GetIntegrationTypes(w http.ResponseWriter, r *http.Request) {
	types, err := ih.service.GetIntegrationTypes(r.Context())
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"types": types})
}

// GetProviders handles GET /api/integrations/providers
func (ih *IntegrationHandlers) GetProviders(w http.ResponseWriter, r *http.Request) {
	providers, err := ih.service.GetProviders(r.Context())
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"providers": providers})
}

// GetProvidersByType handles GET /api/integrations/providers-by-type/{type}
func (ih *IntegrationHandlers) GetProvidersByType(w http.ResponseWriter, r *http.Request) {
	integrationType := chi.URLParam(r, "type")
	if integrationType == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_TYPE", "Type is required"), httputil.GetTraceID(r))
		return
	}

	providers, err := ih.service.GetProvidersByType(r.Context(), integrationType)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"providers": providers})
}

// GetConfigSchema handles GET /api/integrations/config-schema/{provider}
func (ih *IntegrationHandlers) GetConfigSchema(w http.ResponseWriter, r *http.Request) {
	provider := chi.URLParam(r, "provider")
	if provider == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_PROVIDER", "Provider is required"), httputil.GetTraceID(r))
		return
	}

	schema, err := ih.service.GetConfigSchema(r.Context(), provider)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(schema)
}

// ValidateConfig handles POST /api/integrations/validate-config
func (ih *IntegrationHandlers) ValidateConfig(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Provider string                 `json:"provider"`
		Config   map[string]interface{} `json:"config"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		ih.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	valid, err := ih.service.ValidateConfig(r.Context(), req.Provider, req.Config)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]bool{"valid": valid})
}

// GetIntegrationEvents handles GET /api/integrations/{id}/events
func (ih *IntegrationHandlers) GetIntegrationEvents(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
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

	events, total, err := ih.service.GetIntegrationEvents(r.Context(), id, limit, offset)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
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

// SendEventToIntegration handles POST /api/integrations/{id}/send-event
func (ih *IntegrationHandlers) SendEventToIntegration(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	var event map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&event); err != nil {
		ih.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := ih.service.SendEventToIntegration(r.Context(), id, event); err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "sent"})
}

// GetIntegrationStats handles GET /api/integrations/{id}/stats
func (ih *IntegrationHandlers) GetIntegrationStats(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	stats, err := ih.service.GetIntegrationStats(r.Context(), id)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(stats)
}

// GetAllIntegrationStats handles GET /api/integrations/stats/all
func (ih *IntegrationHandlers) GetAllIntegrationStats(w http.ResponseWriter, r *http.Request) {
	stats, err := ih.service.GetAllIntegrationStats(r.Context())
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"stats": stats})
}

// GetIntegrationLogs handles GET /api/integrations/{id}/logs
func (ih *IntegrationHandlers) GetIntegrationLogs(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
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

	logs, total, err := ih.service.GetIntegrationLogs(r.Context(), id, limit, offset)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
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

// BatchEnableIntegrations handles POST /api/integrations/batch-enable
func (ih *IntegrationHandlers) BatchEnableIntegrations(w http.ResponseWriter, r *http.Request) {
	var req struct {
		IDs []string `json:"ids"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		ih.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := ih.service.BatchEnableIntegrations(r.Context(), req.IDs); err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "enabled"})
}

// BatchDisableIntegrations handles POST /api/integrations/batch-disable
func (ih *IntegrationHandlers) BatchDisableIntegrations(w http.ResponseWriter, r *http.Request) {
	var req struct {
		IDs []string `json:"ids"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		ih.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := ih.service.BatchDisableIntegrations(r.Context(), req.IDs); err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "disabled"})
}

// BatchDeleteIntegrations handles POST /api/integrations/batch-delete
func (ih *IntegrationHandlers) BatchDeleteIntegrations(w http.ResponseWriter, r *http.Request) {
	var req struct {
		IDs []string `json:"ids"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		ih.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := ih.service.BatchDeleteIntegrations(r.Context(), req.IDs); err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// CheckHealth handles GET /api/integrations/{id}/health
func (ih *IntegrationHandlers) CheckHealth(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	health, err := ih.service.CheckHealth(r.Context(), id)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(health)
}

// CheckHealthForAll handles GET /api/integrations/health/all
func (ih *IntegrationHandlers) CheckHealthForAll(w http.ResponseWriter, r *http.Request) {
	health, err := ih.service.CheckHealthForAll(r.Context())
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(health)
}

// DisconnectIntegration handles POST /api/integrations/{id}/disconnect
func (ih *IntegrationHandlers) DisconnectIntegration(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := ih.service.DisconnectIntegration(r.Context(), id); err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "disconnected"})
}

// CheckDependencies handles GET /api/integrations/{id}/dependencies
func (ih *IntegrationHandlers) CheckDependencies(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	deps, err := ih.service.CheckDependencies(r.Context(), id)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(deps)
}

// ExportConfig handles GET /api/integrations/{id}/export
func (ih *IntegrationHandlers) ExportConfig(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	config, err := ih.service.ExportConfig(r.Context(), id)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(config)
}

// RotateCredentials handles POST /api/integrations/{id}/rotate-credentials
func (ih *IntegrationHandlers) RotateCredentials(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	var req services.RotateCredentialsRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		ih.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := ih.service.RotateCredentials(r.Context(), id, &req); err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "rotated"})
}

// GetAuditLog handles GET /api/integrations/{id}/audit-log
func (ih *IntegrationHandlers) GetAuditLog(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
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

	logs, total, err := ih.service.GetAuditLog(r.Context(), id, limit, offset)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
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

// GetUsageAnalytics handles GET /api/integrations/{id}/analytics
func (ih *IntegrationHandlers) GetUsageAnalytics(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	timeframe := r.URL.Query().Get("timeframe")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}
	if timeframe == "" {
		timeframe = "7d"
	}

	analytics, err := ih.service.GetUsageAnalytics(r.Context(), id, timeframe)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(analytics)
}

// GetRateLimitStatus handles GET /api/integrations/{id}/rate-limit
func (ih *IntegrationHandlers) GetRateLimitStatus(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	status, err := ih.service.GetRateLimitStatus(r.Context(), id)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(status)
}

// GetCredentialsStatus handles GET /api/integrations/{id}/credentials-status
func (ih *IntegrationHandlers) GetCredentialsStatus(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ih.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Integration ID is required"), httputil.GetTraceID(r))
		return
	}

	status, err := ih.service.GetCredentialsStatus(r.Context(), id)
	if err != nil {
		ih.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(status)
}

// RegisterIntegrationRoutes registers integration routes
func RegisterIntegrationRoutes(r interface {
	Get(pattern string, handlerFn http.HandlerFunc)
	Post(pattern string, handlerFn http.HandlerFunc)
	Put(pattern string, handlerFn http.HandlerFunc)
	Delete(pattern string, handlerFn http.HandlerFunc)
}, handlers *IntegrationHandlers) {
	r.Post("/", handlers.CreateIntegration)
	r.Get("/", handlers.ListIntegrations)
	r.Get("/{id}", handlers.GetIntegration)
	r.Put("/{id}", handlers.UpdateIntegration)
	r.Delete("/{id}", handlers.DeleteIntegration)
	r.Post("/{id}/enable", handlers.EnableIntegration)
	r.Post("/{id}/disable", handlers.DisableIntegration)
	r.Post("/test-connection", handlers.TestConnection)
	r.Post("/{id}/test", handlers.TestIntegrationConnection)
	r.Post("/{id}/reconnect", handlers.ReconnectIntegration)
	r.Get("/{id}/status", handlers.GetIntegrationStatus)
	r.Post("/{id}/sync", handlers.SyncData)
	r.Get("/{id}/sync-status", handlers.GetSyncStatus)
	r.Get("/types", handlers.GetIntegrationTypes)
	r.Get("/providers", handlers.GetProviders)
	r.Get("/providers-by-type/{type}", handlers.GetProvidersByType)
	r.Get("/config-schema/{provider}", handlers.GetConfigSchema)
	r.Post("/validate-config", handlers.ValidateConfig)
	r.Get("/{id}/events", handlers.GetIntegrationEvents)
	r.Post("/{id}/send-event", handlers.SendEventToIntegration)
	r.Get("/{id}/stats", handlers.GetIntegrationStats)
	r.Get("/stats/all", handlers.GetAllIntegrationStats)
	r.Get("/{id}/logs", handlers.GetIntegrationLogs)
	r.Get("/by-type/{type}", handlers.ListIntegrationsByType)
	r.Get("/by-provider/{provider}", handlers.ListIntegrationsByProvider)
	r.Get("/enabled", handlers.ListEnabledIntegrations)
	r.Post("/batch-enable", handlers.BatchEnableIntegrations)
	r.Post("/batch-disable", handlers.BatchDisableIntegrations)
	r.Post("/batch-delete", handlers.BatchDeleteIntegrations)
	r.Get("/{id}/health", handlers.CheckHealth)
	r.Get("/health/all", handlers.CheckHealthForAll)
	r.Post("/{id}/disconnect", handlers.DisconnectIntegration)
	r.Get("/{id}/dependencies", handlers.CheckDependencies)
	r.Get("/{id}/export", handlers.ExportConfig)
	r.Post("/{id}/rotate-credentials", handlers.RotateCredentials)
	r.Get("/{id}/audit-log", handlers.GetAuditLog)
	r.Get("/{id}/analytics", handlers.GetUsageAnalytics)
	r.Get("/{id}/rate-limit", handlers.GetRateLimitStatus)
	r.Get("/{id}/credentials-status", handlers.GetCredentialsStatus)
}
