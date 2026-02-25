package services

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"

	"architect-go/pkg/models"
	"architect-go/pkg/repository"
)

// WebhookServiceImpl implements WebhookService
type WebhookServiceImpl struct {
	repo repository.WebhookRepository
}

// NewWebhookService creates a new webhook service
func NewWebhookService(repo repository.WebhookRepository) WebhookService {
	return &WebhookServiceImpl{repo: repo}
}

func (ws *WebhookServiceImpl) CreateWebhook(ctx context.Context, req *CreateWebhookRequest) (*models.Webhook, error) {
	// Marshal Events ([]string) to json.RawMessage
	var eventsJSON json.RawMessage
	if len(req.Events) > 0 {
		if data, err := json.Marshal(req.Events); err == nil {
			eventsJSON = data
		}
	}

	webhook := &models.Webhook{
		ID:        uuid.New().String(),
		URL:       req.URL,
		Events:    eventsJSON,
		Active:    true,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	// Convert webhook model to map for repository
	webhookMap := webhookToMap(webhook)
	if err := ws.repo.Create(ctx, webhookMap); err != nil {
		return nil, fmt.Errorf("failed to create webhook: %w", err)
	}

	return webhook, nil
}

func (ws *WebhookServiceImpl) GetWebhook(ctx context.Context, id string) (*models.Webhook, error) {
	webhookMap, err := ws.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("failed to get webhook: %w", err)
	}
	webhook := mapToWebhook(webhookMap)
	return webhook, nil
}

func (ws *WebhookServiceImpl) ListWebhooks(ctx context.Context, limit, offset int) ([]*models.Webhook, int64, error) {
	webhookMaps, total, err := ws.repo.List(ctx, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list webhooks: %w", err)
	}
	webhooks := mapsToWebhooks(webhookMaps)
	return webhooks, total, nil
}

func (ws *WebhookServiceImpl) GetWebhooksByIntegration(ctx context.Context, integrationID string, limit, offset int) ([]*models.Webhook, int64, error) {
	webhookMaps, total, err := ws.repo.GetByIntegration(ctx, integrationID, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list webhooks by integration: %w", err)
	}
	webhooks := mapsToWebhooks(webhookMaps)
	return webhooks, total, nil
}

func (ws *WebhookServiceImpl) UpdateWebhook(ctx context.Context, id string, req *CreateWebhookRequest) (*models.Webhook, error) {
	webhookMap, err := ws.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("webhook not found: %w", err)
	}

	webhook := mapToWebhook(webhookMap)
	webhook.URL = req.URL

	// Marshal updated events
	if len(req.Events) > 0 {
		if data, marshalErr := json.Marshal(req.Events); marshalErr == nil {
			webhook.Events = data
		}
	}
	webhook.UpdatedAt = time.Now()

	updatedMap := webhookToMap(webhook)
	if err := ws.repo.Update(ctx, updatedMap); err != nil {
		return nil, fmt.Errorf("failed to update webhook: %w", err)
	}

	return webhook, nil
}

func (ws *WebhookServiceImpl) DeleteWebhook(ctx context.Context, id string) error {
	if err := ws.repo.Delete(ctx, id); err != nil {
		return fmt.Errorf("failed to delete webhook: %w", err)
	}
	return nil
}

func (ws *WebhookServiceImpl) TestWebhook(ctx context.Context, req *TestWebhookRequest) (bool, error) {
	return true, nil
}

func (ws *WebhookServiceImpl) DisableWebhook(ctx context.Context, id string) error {
	webhookMap, err := ws.repo.Get(ctx, id)
	if err != nil {
		return fmt.Errorf("webhook not found: %w", err)
	}

	webhookMap["active"] = false
	return ws.repo.Update(ctx, webhookMap)
}

func (ws *WebhookServiceImpl) EnableWebhook(ctx context.Context, id string) error {
	webhookMap, err := ws.repo.Get(ctx, id)
	if err != nil {
		return fmt.Errorf("webhook not found: %w", err)
	}

	webhookMap["active"] = true
	return ws.repo.Update(ctx, webhookMap)
}

func (ws *WebhookServiceImpl) GetDeliveryHistory(ctx context.Context, id string, limit, offset int) ([]*DeliveryResponse, int64, error) {
	deliveryMaps, total, err := ws.repo.GetDeliveryHistory(ctx, id, limit, offset)
	if err != nil {
		return nil, 0, err
	}

	deliveries := make([]*DeliveryResponse, 0, len(deliveryMaps))
	for _, dm := range deliveryMaps {
		d := &DeliveryResponse{}
		if v, ok := dm["id"].(string); ok {
			d.ID = v
		}
		if v, ok := dm["webhook_id"].(string); ok {
			d.WebhookID = v
		}
		if v, ok := dm["status"].(string); ok {
			d.Status = v
		}
		deliveries = append(deliveries, d)
	}
	return deliveries, total, nil
}

func (ws *WebhookServiceImpl) GetDeliveryDetails(ctx context.Context, webhookID string, deliveryID string) (*DeliveryResponse, error) {
	return &DeliveryResponse{
		ID:          deliveryID,
		WebhookID:   webhookID,
		Status:      "success",
		DeliveredAt: time.Now(),
	}, nil
}

func (ws *WebhookServiceImpl) RetryDelivery(ctx context.Context, webhookID string, deliveryID string) error {
	delivery := map[string]interface{}{
		"id":          uuid.New().String(),
		"webhook_id":  webhookID,
		"delivery_id": deliveryID,
		"retry":       true,
		"status":      "pending",
		"created_at":  time.Now().Format(time.RFC3339),
	}

	if err := ws.repo.CreateDelivery(ctx, delivery); err != nil {
		return fmt.Errorf("failed to retry delivery %s: %w", deliveryID, err)
	}
	return nil
}

func (ws *WebhookServiceImpl) GetWebhookEvents(ctx context.Context, id string, limit, offset int) ([]map[string]interface{}, int64, error) {
	return make([]map[string]interface{}, 0), 0, nil
}

func (ws *WebhookServiceImpl) ReplayEvents(ctx context.Context, req *ReplayEventsRequest) (int64, error) {
	return 0, nil
}

func (ws *WebhookServiceImpl) GetAvailableTemplates(ctx context.Context) ([]map[string]interface{}, error) {
	return []map[string]interface{}{}, nil
}

func (ws *WebhookServiceImpl) GetAvailableEventTypes(ctx context.Context) ([]string, error) {
	return []string{"created", "updated", "deleted", "triggered"}, nil
}

func (ws *WebhookServiceImpl) ValidatePayload(ctx context.Context, signature string, payload []byte) (bool, error) {
	return true, nil
}

func (ws *WebhookServiceImpl) GetSigningKeys(ctx context.Context, webhookID string) ([]*SigningKeyResponse, error) {
	return make([]*SigningKeyResponse, 0), nil
}

func (ws *WebhookServiceImpl) RotateSigningKey(ctx context.Context, webhookID string, keyID string) (*SigningKeyResponse, error) {
	return &SigningKeyResponse{
		KeyID:     uuid.New().String(),
		Algorithm: "HMAC-SHA256",
		CreatedAt: time.Now(),
	}, nil
}

func (ws *WebhookServiceImpl) GetWebhookStats(ctx context.Context, id string) (*WebhookStatsResponse, error) {
	return &WebhookStatsResponse{
		WebhookID:       id,
		TotalDeliveries: 0,
		SuccessCount:    0,
		FailureCount:    0,
	}, nil
}

func (ws *WebhookServiceImpl) PauseWebhook(ctx context.Context, id string) error {
	return ws.DisableWebhook(ctx, id)
}

func (ws *WebhookServiceImpl) ResumeWebhook(ctx context.Context, id string) error {
	return ws.EnableWebhook(ctx, id)
}

func (ws *WebhookServiceImpl) GetFailedDeliveries(ctx context.Context, limit, offset int) ([]*DeliveryResponse, int64, error) {
	deliveryMaps, total, err := ws.repo.GetFailedDeliveries(ctx, limit, offset)
	if err != nil {
		return nil, 0, err
	}

	deliveries := make([]*DeliveryResponse, 0, len(deliveryMaps))
	for _, dm := range deliveryMaps {
		d := &DeliveryResponse{}
		if v, ok := dm["id"].(string); ok {
			d.ID = v
		}
		if v, ok := dm["webhook_id"].(string); ok {
			d.WebhookID = v
		}
		d.Status = "failed"
		deliveries = append(deliveries, d)
	}
	return deliveries, total, nil
}

func (ws *WebhookServiceImpl) BatchDeleteWebhooks(ctx context.Context, ids []string) error {
	for _, id := range ids {
		if err := ws.DeleteWebhook(ctx, id); err != nil {
			return err
		}
	}
	return nil
}

func (ws *WebhookServiceImpl) BatchDisableWebhooks(ctx context.Context, ids []string) error {
	for _, id := range ids {
		if err := ws.DisableWebhook(ctx, id); err != nil {
			return err
		}
	}
	return nil
}

func (ws *WebhookServiceImpl) BatchEnableWebhooks(ctx context.Context, ids []string) error {
	for _, id := range ids {
		if err := ws.EnableWebhook(ctx, id); err != nil {
			return err
		}
	}
	return nil
}

func (ws *WebhookServiceImpl) CreateRoutingRule(ctx context.Context, req *RoutingRuleRequest) (string, error) {
	return uuid.New().String(), nil
}

func (ws *WebhookServiceImpl) GetRoutingRules(ctx context.Context, limit, offset int) ([]map[string]interface{}, int64, error) {
	return make([]map[string]interface{}, 0), 0, nil
}

func (ws *WebhookServiceImpl) UpdateRoutingRule(ctx context.Context, ruleID string, req *RoutingRuleRequest) error {
	return nil
}

func (ws *WebhookServiceImpl) DeleteRoutingRule(ctx context.Context, ruleID string) error {
	return nil
}

func (ws *WebhookServiceImpl) GetRetryPolicy(ctx context.Context) (map[string]interface{}, error) {
	return map[string]interface{}{
		"max_retries":    3,
		"initial_delay":  1000,
		"backoff_factor": 2,
	}, nil
}

func (ws *WebhookServiceImpl) UpdateRetryPolicy(ctx context.Context, policy map[string]interface{}) error {
	return nil
}

func (ws *WebhookServiceImpl) ProcessIncomingWebhook(ctx context.Context, name string, payload []byte, signature string) error {
	return nil
}

func (ws *WebhookServiceImpl) GetEventRoutingStatus(ctx context.Context, eventType string) ([]map[string]interface{}, error) {
	return make([]map[string]interface{}, 0), nil
}

func (ws *WebhookServiceImpl) ManuallyTriggerWebhook(ctx context.Context, id string, event map[string]interface{}) error {
	return nil
}

func (ws *WebhookServiceImpl) GetQueuedDeliveries(ctx context.Context, limit, offset int) ([]*DeliveryResponse, int64, error) {
	return make([]*DeliveryResponse, 0), 0, nil
}

func (ws *WebhookServiceImpl) CancelQueuedDelivery(ctx context.Context, deliveryID string) error {
	return nil
}

func (ws *WebhookServiceImpl) CleanupOldDeliveries(ctx context.Context, beforeDate string) (int64, error) {
	return 0, nil
}

func (ws *WebhookServiceImpl) GetDeliveryMetrics(ctx context.Context, id string, timeframe string) (map[string]interface{}, error) {
	return map[string]interface{}{
		"timeframe": timeframe,
		"delivered": 0,
		"failed":    0,
	}, nil
}

func (ws *WebhookServiceImpl) VerifySignature(ctx context.Context, signature string, payload []byte, secret string) (bool, error) {
	return true, nil
}

func (ws *WebhookServiceImpl) ExportWebhookConfig(ctx context.Context, id string) (map[string]interface{}, error) {
	webhookMap, err := ws.repo.Get(ctx, id)
	if err != nil {
		return nil, err
	}

	return map[string]interface{}{
		"id":  webhookMap["id"],
		"url": webhookMap["url"],
	}, nil
}

func (ws *WebhookServiceImpl) ImportWebhookConfig(ctx context.Context, config map[string]interface{}) (*models.Webhook, error) {
	webhook := &models.Webhook{
		ID:        uuid.New().String(),
		Active:    true,
		CreatedAt: time.Now(),
	}
	return webhook, nil
}

func (ws *WebhookServiceImpl) GetCircuitBreakerStatus(ctx context.Context, id string) (map[string]interface{}, error) {
	return map[string]interface{}{
		"status": "closed",
	}, nil
}

func (ws *WebhookServiceImpl) ResetCircuitBreaker(ctx context.Context, id string) error {
	return nil
}

func (ws *WebhookServiceImpl) GetTransformationRules(ctx context.Context, id string) ([]map[string]interface{}, error) {
	return make([]map[string]interface{}, 0), nil
}

func (ws *WebhookServiceImpl) AddTransformationRule(ctx context.Context, id string, rule map[string]interface{}) (string, error) {
	return uuid.New().String(), nil
}

func (ws *WebhookServiceImpl) RemoveTransformationRule(ctx context.Context, id string, ruleID string) error {
	return nil
}

func (ws *WebhookServiceImpl) GetDeliveryStats(ctx context.Context, id string, timeframe string) (map[string]interface{}, error) {
	return map[string]interface{}{
		"timeframe": timeframe,
		"delivered": 0,
		"failed":    0,
	}, nil
}

func (ws *WebhookServiceImpl) ClearDeliveryHistory(ctx context.Context, id string, beforeDate string) (int64, error) {
	return 0, nil
}
