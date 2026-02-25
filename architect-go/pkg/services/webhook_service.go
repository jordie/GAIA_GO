package services

import (
	"context"

	"architect-go/pkg/models"
)

// WebhookService defines webhook management business logic
type WebhookService interface {
	// CreateWebhook creates new webhook
	CreateWebhook(ctx context.Context, req *CreateWebhookRequest) (*models.Webhook, error)

	// GetWebhook retrieves webhook by ID
	GetWebhook(ctx context.Context, id string) (*models.Webhook, error)

	// ListWebhooks retrieves all webhooks with pagination
	ListWebhooks(ctx context.Context, limit, offset int) ([]*models.Webhook, int64, error)

	// GetWebhooksByIntegration retrieves webhooks for specific integration
	GetWebhooksByIntegration(ctx context.Context, integrationID string, limit, offset int) ([]*models.Webhook, int64, error)

	// UpdateWebhook updates webhook configuration
	UpdateWebhook(ctx context.Context, id string, req *CreateWebhookRequest) (*models.Webhook, error)

	// DeleteWebhook deletes a webhook
	DeleteWebhook(ctx context.Context, id string) error

	// TestWebhook sends test webhook to URL
	TestWebhook(ctx context.Context, req *TestWebhookRequest) (bool, error)

	// DisableWebhook disables webhook
	DisableWebhook(ctx context.Context, id string) error

	// EnableWebhook enables webhook
	EnableWebhook(ctx context.Context, id string) error

	// GetDeliveryHistory retrieves webhook delivery history
	GetDeliveryHistory(ctx context.Context, id string, limit, offset int) ([]*DeliveryResponse, int64, error)

	// GetDeliveryDetails retrieves specific delivery details
	GetDeliveryDetails(ctx context.Context, webhookID string, deliveryID string) (*DeliveryResponse, error)

	// RetryDelivery retries failed webhook delivery
	RetryDelivery(ctx context.Context, webhookID string, deliveryID string) error

	// GetWebhookEvents retrieves events associated with webhook
	GetWebhookEvents(ctx context.Context, id string, limit, offset int) ([]map[string]interface{}, int64, error)

	// ReplayEvents replays historical events to webhook
	ReplayEvents(ctx context.Context, req *ReplayEventsRequest) (int64, error)

	// GetAvailableTemplates returns available webhook templates
	GetAvailableTemplates(ctx context.Context) ([]map[string]interface{}, error)

	// GetAvailableEventTypes returns available event types for webhooks
	GetAvailableEventTypes(ctx context.Context) ([]string, error)

	// ValidatePayload validates webhook payload signature
	ValidatePayload(ctx context.Context, signature string, payload []byte) (bool, error)

	// GetSigningKeys retrieves webhook signing keys
	GetSigningKeys(ctx context.Context, webhookID string) ([]*SigningKeyResponse, error)

	// RotateSigningKey rotates webhook signing key
	RotateSigningKey(ctx context.Context, webhookID string, keyID string) (*SigningKeyResponse, error)

	// GetWebhookStats retrieves webhook statistics
	GetWebhookStats(ctx context.Context, id string) (*WebhookStatsResponse, error)

	// PauseWebhook pauses webhook delivery
	PauseWebhook(ctx context.Context, id string) error

	// ResumeWebhook resumes paused webhook
	ResumeWebhook(ctx context.Context, id string) error

	// GetFailedDeliveries retrieves failed deliveries
	GetFailedDeliveries(ctx context.Context, limit, offset int) ([]*DeliveryResponse, int64, error)

	// BatchDeleteWebhooks deletes multiple webhooks
	BatchDeleteWebhooks(ctx context.Context, ids []string) error

	// BatchDisableWebhooks disables multiple webhooks
	BatchDisableWebhooks(ctx context.Context, ids []string) error

	// BatchEnableWebhooks enables multiple webhooks
	BatchEnableWebhooks(ctx context.Context, ids []string) error

	// CreateRoutingRule creates event routing rule
	CreateRoutingRule(ctx context.Context, req *RoutingRuleRequest) (string, error)

	// GetRoutingRules retrieves routing rules
	GetRoutingRules(ctx context.Context, limit, offset int) ([]map[string]interface{}, int64, error)

	// UpdateRoutingRule updates routing rule
	UpdateRoutingRule(ctx context.Context, ruleID string, req *RoutingRuleRequest) error

	// DeleteRoutingRule deletes routing rule
	DeleteRoutingRule(ctx context.Context, ruleID string) error

	// GetRetryPolicy retrieves webhook retry policy
	GetRetryPolicy(ctx context.Context) (map[string]interface{}, error)

	// UpdateRetryPolicy updates webhook retry policy
	UpdateRetryPolicy(ctx context.Context, policy map[string]interface{}) error

	// ProcessIncomingWebhook processes incoming webhook payload
	ProcessIncomingWebhook(ctx context.Context, name string, payload []byte, signature string) error

	// GetEventRoutingStatus retrieves event routing status
	GetEventRoutingStatus(ctx context.Context, eventType string) ([]map[string]interface{}, error)

	// ManuallyTriggerWebhook manually triggers webhook delivery
	ManuallyTriggerWebhook(ctx context.Context, id string, event map[string]interface{}) error

	// GetQueuedDeliveries retrieves queued deliveries
	GetQueuedDeliveries(ctx context.Context, limit, offset int) ([]*DeliveryResponse, int64, error)

	// CancelQueuedDelivery cancels queued delivery
	CancelQueuedDelivery(ctx context.Context, deliveryID string) error

	// CleanupOldDeliveries removes old delivery records
	CleanupOldDeliveries(ctx context.Context, beforeDate string) (int64, error)

	// GetDeliveryMetrics retrieves delivery performance metrics
	GetDeliveryMetrics(ctx context.Context, id string, timeframe string) (map[string]interface{}, error)
}
