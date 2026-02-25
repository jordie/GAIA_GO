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

// WebhookHandlers handles webhook management HTTP requests
type WebhookHandlers struct {
	service    services.WebhookService
	errHandler *errors.Handler
}

// NewWebhookHandlers creates new webhook handlers
func NewWebhookHandlers(service services.WebhookService, errHandler *errors.Handler) *WebhookHandlers {
	return &WebhookHandlers{
		service:    service,
		errHandler: errHandler,
	}
}

// CreateWebhook handles POST /api/webhooks
func (wh *WebhookHandlers) CreateWebhook(w http.ResponseWriter, r *http.Request) {
	var req services.CreateWebhookRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		wh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if req.URL == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_URL", "Webhook URL is required"), httputil.GetTraceID(r))
		return
	}

	webhook, err := wh.service.CreateWebhook(r.Context(), &req)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(webhook)
}

// GetWebhook handles GET /api/webhooks/{id}
func (wh *WebhookHandlers) GetWebhook(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Webhook ID is required"), httputil.GetTraceID(r))
		return
	}

	webhook, err := wh.service.GetWebhook(r.Context(), id)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(webhook)
}

// ListWebhooks handles GET /api/webhooks
func (wh *WebhookHandlers) ListWebhooks(w http.ResponseWriter, r *http.Request) {
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

	webhooks, total, err := wh.service.ListWebhooks(r.Context(), limit, offset)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"webhooks": webhooks,
		"total":    total,
		"limit":    limit,
		"offset":   offset,
	})
}

// GetWebhooksByIntegration handles GET /api/webhooks/integration/{integrationID}
func (wh *WebhookHandlers) GetWebhooksByIntegration(w http.ResponseWriter, r *http.Request) {
	integrationID := chi.URLParam(r, "integrationID")
	if integrationID == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_INTEGRATION_ID", "Integration ID is required"), httputil.GetTraceID(r))
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

	webhooks, total, err := wh.service.GetWebhooksByIntegration(r.Context(), integrationID, limit, offset)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"webhooks": webhooks,
		"total":    total,
		"limit":    limit,
		"offset":   offset,
	})
}

// UpdateWebhook handles PUT /api/webhooks/{id}
func (wh *WebhookHandlers) UpdateWebhook(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Webhook ID is required"), httputil.GetTraceID(r))
		return
	}

	var req services.CreateWebhookRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		wh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	webhook, err := wh.service.UpdateWebhook(r.Context(), id, &req)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(webhook)
}

// DeleteWebhook handles DELETE /api/webhooks/{id}
func (wh *WebhookHandlers) DeleteWebhook(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Webhook ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := wh.service.DeleteWebhook(r.Context(), id); err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// TestWebhook handles POST /api/webhooks/test
func (wh *WebhookHandlers) TestWebhook(w http.ResponseWriter, r *http.Request) {
	var req services.TestWebhookRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		wh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	success, err := wh.service.TestWebhook(r.Context(), &req)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]bool{"success": success})
}

// DisableWebhook handles POST /api/webhooks/{id}/disable
func (wh *WebhookHandlers) DisableWebhook(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Webhook ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := wh.service.DisableWebhook(r.Context(), id); err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "disabled"})
}

// EnableWebhook handles POST /api/webhooks/{id}/enable
func (wh *WebhookHandlers) EnableWebhook(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Webhook ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := wh.service.EnableWebhook(r.Context(), id); err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "enabled"})
}

// GetDeliveryHistory handles GET /api/webhooks/{id}/deliveries
func (wh *WebhookHandlers) GetDeliveryHistory(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Webhook ID is required"), httputil.GetTraceID(r))
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

	deliveries, total, err := wh.service.GetDeliveryHistory(r.Context(), id, limit, offset)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"deliveries": deliveries,
		"total":      total,
		"limit":      limit,
		"offset":     offset,
	})
}

// GetDeliveryDetails handles GET /api/webhooks/{id}/deliveries/{deliveryID}
func (wh *WebhookHandlers) GetDeliveryDetails(w http.ResponseWriter, r *http.Request) {
	webhookID := chi.URLParam(r, "id")
	deliveryID := chi.URLParam(r, "deliveryID")
	if webhookID == "" || deliveryID == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_IDS", "Webhook ID and delivery ID are required"), httputil.GetTraceID(r))
		return
	}

	delivery, err := wh.service.GetDeliveryDetails(r.Context(), webhookID, deliveryID)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(delivery)
}

// RetryDelivery handles POST /api/webhooks/{id}/deliveries/{deliveryID}/retry
func (wh *WebhookHandlers) RetryDelivery(w http.ResponseWriter, r *http.Request) {
	webhookID := chi.URLParam(r, "id")
	deliveryID := chi.URLParam(r, "deliveryID")
	if webhookID == "" || deliveryID == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_IDS", "Webhook ID and delivery ID are required"), httputil.GetTraceID(r))
		return
	}

	if err := wh.service.RetryDelivery(r.Context(), webhookID, deliveryID); err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "retrying"})
}

// GetWebhookEvents handles GET /api/webhooks/{id}/events
func (wh *WebhookHandlers) GetWebhookEvents(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Webhook ID is required"), httputil.GetTraceID(r))
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

	events, total, err := wh.service.GetWebhookEvents(r.Context(), id, limit, offset)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
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

// ReplayEvents handles POST /api/webhooks/replay-events
func (wh *WebhookHandlers) ReplayEvents(w http.ResponseWriter, r *http.Request) {
	var req services.ReplayEventsRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		wh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	count, err := wh.service.ReplayEvents(r.Context(), &req)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]int64{"replayed": count})
}

// GetAvailableTemplates handles GET /api/webhooks/templates
func (wh *WebhookHandlers) GetAvailableTemplates(w http.ResponseWriter, r *http.Request) {
	templates, err := wh.service.GetAvailableTemplates(r.Context())
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"templates": templates})
}

// GetAvailableEventTypes handles GET /api/webhooks/event-types
func (wh *WebhookHandlers) GetAvailableEventTypes(w http.ResponseWriter, r *http.Request) {
	eventTypes, err := wh.service.GetAvailableEventTypes(r.Context())
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"event_types": eventTypes})
}

// GetSigningKeys handles GET /api/webhooks/{id}/signing-keys
func (wh *WebhookHandlers) GetSigningKeys(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Webhook ID is required"), httputil.GetTraceID(r))
		return
	}

	keys, err := wh.service.GetSigningKeys(r.Context(), id)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{"keys": keys})
}

// RotateSigningKey handles POST /api/webhooks/{id}/signing-keys/{keyID}/rotate
func (wh *WebhookHandlers) RotateSigningKey(w http.ResponseWriter, r *http.Request) {
	webhookID := chi.URLParam(r, "id")
	keyID := chi.URLParam(r, "keyID")
	if webhookID == "" || keyID == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_IDS", "Webhook ID and key ID are required"), httputil.GetTraceID(r))
		return
	}

	key, err := wh.service.RotateSigningKey(r.Context(), webhookID, keyID)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(key)
}

// GetWebhookStats handles GET /api/webhooks/{id}/stats
func (wh *WebhookHandlers) GetWebhookStats(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Webhook ID is required"), httputil.GetTraceID(r))
		return
	}

	stats, err := wh.service.GetWebhookStats(r.Context(), id)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(stats)
}

// PauseWebhook handles POST /api/webhooks/{id}/pause
func (wh *WebhookHandlers) PauseWebhook(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Webhook ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := wh.service.PauseWebhook(r.Context(), id); err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "paused"})
}

// ResumeWebhook handles POST /api/webhooks/{id}/resume
func (wh *WebhookHandlers) ResumeWebhook(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Webhook ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := wh.service.ResumeWebhook(r.Context(), id); err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "resumed"})
}

// GetFailedDeliveries handles GET /api/webhooks/deliveries/failed
func (wh *WebhookHandlers) GetFailedDeliveries(w http.ResponseWriter, r *http.Request) {
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

	deliveries, total, err := wh.service.GetFailedDeliveries(r.Context(), limit, offset)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"deliveries": deliveries,
		"total":      total,
		"limit":      limit,
		"offset":     offset,
	})
}

// BatchDeleteWebhooks handles POST /api/webhooks/batch-delete
func (wh *WebhookHandlers) BatchDeleteWebhooks(w http.ResponseWriter, r *http.Request) {
	var req struct {
		IDs []string `json:"ids"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		wh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := wh.service.BatchDeleteWebhooks(r.Context(), req.IDs); err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// BatchDisableWebhooks handles POST /api/webhooks/batch-disable
func (wh *WebhookHandlers) BatchDisableWebhooks(w http.ResponseWriter, r *http.Request) {
	var req struct {
		IDs []string `json:"ids"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		wh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := wh.service.BatchDisableWebhooks(r.Context(), req.IDs); err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "disabled"})
}

// BatchEnableWebhooks handles POST /api/webhooks/batch-enable
func (wh *WebhookHandlers) BatchEnableWebhooks(w http.ResponseWriter, r *http.Request) {
	var req struct {
		IDs []string `json:"ids"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		wh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := wh.service.BatchEnableWebhooks(r.Context(), req.IDs); err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "enabled"})
}

// GetRoutingRules handles GET /api/webhooks/routing-rules
func (wh *WebhookHandlers) GetRoutingRules(w http.ResponseWriter, r *http.Request) {
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

	rules, total, err := wh.service.GetRoutingRules(r.Context(), limit, offset)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"rules":  rules,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// CreateRoutingRule handles POST /api/webhooks/routing-rules
func (wh *WebhookHandlers) CreateRoutingRule(w http.ResponseWriter, r *http.Request) {
	var req services.RoutingRuleRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		wh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	ruleID, err := wh.service.CreateRoutingRule(r.Context(), &req)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]string{"id": ruleID})
}

// UpdateRoutingRule handles PUT /api/webhooks/routing-rules/{ruleID}
func (wh *WebhookHandlers) UpdateRoutingRule(w http.ResponseWriter, r *http.Request) {
	ruleID := chi.URLParam(r, "ruleID")
	if ruleID == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_RULE_ID", "Rule ID is required"), httputil.GetTraceID(r))
		return
	}

	var req services.RoutingRuleRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		wh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := wh.service.UpdateRoutingRule(r.Context(), ruleID, &req); err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "updated"})
}

// DeleteRoutingRule handles DELETE /api/webhooks/routing-rules/{ruleID}
func (wh *WebhookHandlers) DeleteRoutingRule(w http.ResponseWriter, r *http.Request) {
	ruleID := chi.URLParam(r, "ruleID")
	if ruleID == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_RULE_ID", "Rule ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := wh.service.DeleteRoutingRule(r.Context(), ruleID); err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// GetRetryPolicy handles GET /api/webhooks/retry-policy
func (wh *WebhookHandlers) GetRetryPolicy(w http.ResponseWriter, r *http.Request) {
	policy, err := wh.service.GetRetryPolicy(r.Context())
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(policy)
}

// UpdateRetryPolicy handles PUT /api/webhooks/retry-policy
func (wh *WebhookHandlers) UpdateRetryPolicy(w http.ResponseWriter, r *http.Request) {
	var policy map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&policy); err != nil {
		wh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := wh.service.UpdateRetryPolicy(r.Context(), policy); err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "updated"})
}

// ManuallyTriggerWebhook handles POST /api/webhooks/{id}/trigger
func (wh *WebhookHandlers) ManuallyTriggerWebhook(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Webhook ID is required"), httputil.GetTraceID(r))
		return
	}

	var event map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&event); err != nil {
		wh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if err := wh.service.ManuallyTriggerWebhook(r.Context(), id, event); err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "triggered"})
}

// GetQueuedDeliveries handles GET /api/webhooks/deliveries/queued
func (wh *WebhookHandlers) GetQueuedDeliveries(w http.ResponseWriter, r *http.Request) {
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

	deliveries, total, err := wh.service.GetQueuedDeliveries(r.Context(), limit, offset)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"deliveries": deliveries,
		"total":      total,
		"limit":      limit,
		"offset":     offset,
	})
}

// CancelQueuedDelivery handles POST /api/webhooks/deliveries/{deliveryID}/cancel
func (wh *WebhookHandlers) CancelQueuedDelivery(w http.ResponseWriter, r *http.Request) {
	deliveryID := chi.URLParam(r, "deliveryID")
	if deliveryID == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_DELIVERY_ID", "Delivery ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := wh.service.CancelQueuedDelivery(r.Context(), deliveryID); err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "cancelled"})
}

// GetDeliveryMetrics handles GET /api/webhooks/{id}/metrics
func (wh *WebhookHandlers) GetDeliveryMetrics(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	timeframe := r.URL.Query().Get("timeframe")
	if id == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Webhook ID is required"), httputil.GetTraceID(r))
		return
	}
	if timeframe == "" {
		timeframe = "24h"
	}

	metrics, err := wh.service.GetDeliveryMetrics(r.Context(), id, timeframe)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(metrics)
}

// RegisterWebhookRoutes registers webhook routes
func RegisterWebhookRoutes(r interface {
	Get(pattern string, handlerFn http.HandlerFunc)
	Post(pattern string, handlerFn http.HandlerFunc)
	Put(pattern string, handlerFn http.HandlerFunc)
	Delete(pattern string, handlerFn http.HandlerFunc)
}, handlers *WebhookHandlers) {
	r.Post("/", handlers.CreateWebhook)
	r.Get("/", handlers.ListWebhooks)
	r.Get("/{id}", handlers.GetWebhook)
	r.Put("/{id}", handlers.UpdateWebhook)
	r.Delete("/{id}", handlers.DeleteWebhook)
	r.Post("/test", handlers.TestWebhook)
	r.Post("/{id}/disable", handlers.DisableWebhook)
	r.Post("/{id}/enable", handlers.EnableWebhook)
	r.Get("/{id}/deliveries", handlers.GetDeliveryHistory)
	r.Get("/{id}/deliveries/{deliveryID}", handlers.GetDeliveryDetails)
	r.Post("/{id}/deliveries/{deliveryID}/retry", handlers.RetryDelivery)
	r.Get("/{id}/events", handlers.GetWebhookEvents)
	r.Post("/replay-events", handlers.ReplayEvents)
	r.Get("/templates", handlers.GetAvailableTemplates)
	r.Get("/event-types", handlers.GetAvailableEventTypes)
	r.Get("/{id}/signing-keys", handlers.GetSigningKeys)
	r.Post("/{id}/signing-keys/{keyID}/rotate", handlers.RotateSigningKey)
	r.Get("/{id}/stats", handlers.GetWebhookStats)
	r.Post("/{id}/pause", handlers.PauseWebhook)
	r.Post("/{id}/resume", handlers.ResumeWebhook)
	r.Get("/deliveries/failed", handlers.GetFailedDeliveries)
	r.Post("/batch-delete", handlers.BatchDeleteWebhooks)
	r.Post("/batch-disable", handlers.BatchDisableWebhooks)
	r.Post("/batch-enable", handlers.BatchEnableWebhooks)
	r.Get("/routing-rules", handlers.GetRoutingRules)
	r.Post("/routing-rules", handlers.CreateRoutingRule)
	r.Put("/routing-rules/{ruleID}", handlers.UpdateRoutingRule)
	r.Delete("/routing-rules/{ruleID}", handlers.DeleteRoutingRule)
	r.Get("/retry-policy", handlers.GetRetryPolicy)
	r.Put("/retry-policy", handlers.UpdateRetryPolicy)
	r.Post("/{id}/trigger", handlers.ManuallyTriggerWebhook)
	r.Get("/deliveries/queued", handlers.GetQueuedDeliveries)
	r.Post("/deliveries/{deliveryID}/cancel", handlers.CancelQueuedDelivery)
	r.Get("/{id}/metrics", handlers.GetDeliveryMetrics)
	r.Get("/integration/{integrationID}", handlers.GetWebhooksByIntegration)
}
