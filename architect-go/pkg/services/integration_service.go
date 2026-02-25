package services

import (
	"context"

	"architect-go/pkg/models"
)

// IntegrationService defines third-party integration management business logic
type IntegrationService interface {
	// CreateIntegration creates new third-party integration
	CreateIntegration(ctx context.Context, req *CreateIntegrationRequest) (*models.Integration, error)

	// GetIntegration retrieves integration by ID
	GetIntegration(ctx context.Context, id string) (*models.Integration, error)

	// ListIntegrations retrieves all integrations with pagination
	ListIntegrations(ctx context.Context, limit, offset int) ([]*models.Integration, int64, error)

	// ListIntegrationsByType retrieves integrations filtered by type
	ListIntegrationsByType(ctx context.Context, integrationType string, limit, offset int) ([]*models.Integration, int64, error)

	// ListIntegrationsByProvider retrieves integrations filtered by provider
	ListIntegrationsByProvider(ctx context.Context, provider string, limit, offset int) ([]*models.Integration, int64, error)

	// ListEnabledIntegrations retrieves only enabled integrations
	ListEnabledIntegrations(ctx context.Context, limit, offset int) ([]*models.Integration, int64, error)

	// UpdateIntegration updates integration configuration
	UpdateIntegration(ctx context.Context, id string, req *UpdateIntegrationRequest) (*models.Integration, error)

	// DeleteIntegration deletes an integration
	DeleteIntegration(ctx context.Context, id string) error

	// EnableIntegration enables an integration
	EnableIntegration(ctx context.Context, id string) error

	// DisableIntegration disables an integration
	DisableIntegration(ctx context.Context, id string) error

	// TestConnection tests integration connection with provided credentials
	TestConnection(ctx context.Context, req *TestConnectionRequest) (bool, error)

	// TestIntegrationConnection tests connection for existing integration
	TestIntegrationConnection(ctx context.Context, id string) (bool, error)

	// ReconnectIntegration reconnects to integration service
	ReconnectIntegration(ctx context.Context, id string) error

	// GetIntegrationStatus retrieves current status of integration
	GetIntegrationStatus(ctx context.Context, id string) (map[string]interface{}, error)

	// SyncData initiates data synchronization with integration
	SyncData(ctx context.Context, id string) error

	// GetSyncStatus retrieves synchronization status
	GetSyncStatus(ctx context.Context, id string) (*SyncStatusResponse, error)

	// GetIntegrationTypes returns available integration types
	GetIntegrationTypes(ctx context.Context) ([]string, error)

	// GetProviders returns available providers
	GetProviders(ctx context.Context) ([]string, error)

	// GetProvidersByType returns providers for specific type
	GetProvidersByType(ctx context.Context, integrationType string) ([]string, error)

	// GetConfigSchema retrieves configuration schema for integration
	GetConfigSchema(ctx context.Context, provider string) (map[string]interface{}, error)

	// ValidateConfig validates integration configuration
	ValidateConfig(ctx context.Context, provider string, config map[string]interface{}) (bool, error)

	// GetIntegrationEvents retrieves events from integration
	GetIntegrationEvents(ctx context.Context, id string, limit, offset int) ([]map[string]interface{}, int64, error)

	// SendEventToIntegration sends event to integration service
	SendEventToIntegration(ctx context.Context, id string, event map[string]interface{}) error

	// GetIntegrationStats retrieves integration statistics
	GetIntegrationStats(ctx context.Context, id string) (*IntegrationStatsResponse, error)

	// GetAllIntegrationStats retrieves statistics for all integrations
	GetAllIntegrationStats(ctx context.Context) ([]*IntegrationStatsResponse, error)

	// GetIntegrationLogs retrieves integration activity logs
	GetIntegrationLogs(ctx context.Context, id string, limit, offset int) ([]map[string]interface{}, int64, error)

	// BatchEnableIntegrations enables multiple integrations
	BatchEnableIntegrations(ctx context.Context, ids []string) error

	// BatchDisableIntegrations disables multiple integrations
	BatchDisableIntegrations(ctx context.Context, ids []string) error

	// BatchDeleteIntegrations deletes multiple integrations
	BatchDeleteIntegrations(ctx context.Context, ids []string) error

	// CheckHealthForAll performs health check on all integrations
	CheckHealthForAll(ctx context.Context) (map[string]interface{}, error)

	// CheckHealth checks health of specific integration
	CheckHealth(ctx context.Context, id string) (map[string]interface{}, error)

	// DisconnectIntegration safely disconnects integration
	DisconnectIntegration(ctx context.Context, id string) error

	// CheckDependencies checks if integration has unmet dependencies
	CheckDependencies(ctx context.Context, id string) (map[string]interface{}, error)

	// ImportConfig imports integration configuration from file
	ImportConfig(ctx context.Context, filename string) (*models.Integration, error)

	// ExportConfig exports integration configuration
	ExportConfig(ctx context.Context, id string) (map[string]interface{}, error)

	// MigrateConfig migrates integration configuration to new version
	MigrateConfig(ctx context.Context, req *MigrateConfigRequest) (map[string]interface{}, error)

	// GetUsageAnalytics retrieves integration usage analytics
	GetUsageAnalytics(ctx context.Context, id string, timeframe string) (map[string]interface{}, error)

	// GetRateLimitStatus retrieves rate limit information
	GetRateLimitStatus(ctx context.Context, id string) (map[string]interface{}, error)

	// GetCredentialsStatus retrieves credential status (masked)
	GetCredentialsStatus(ctx context.Context, id string) (map[string]interface{}, error)

	// RotateCredentials rotates integration credentials
	RotateCredentials(ctx context.Context, id string, req *RotateCredentialsRequest) error

	// GetAuditLog retrieves audit log of integration changes
	GetAuditLog(ctx context.Context, id string, limit, offset int) ([]map[string]interface{}, int64, error)

	// CloneConfiguration clones configuration from one integration to another
	CloneConfiguration(ctx context.Context, sourceID string, targetProvider string) (*models.Integration, error)

	// GetWebhookURL gets webhook URL for integration
	GetWebhookURL(ctx context.Context, id string) (string, error)

	// RefreshWebhookSecret refreshes webhook secret
	RefreshWebhookSecret(ctx context.Context, id string) (string, error)
}
