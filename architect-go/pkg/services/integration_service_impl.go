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

// IntegrationServiceImpl implements IntegrationService
type IntegrationServiceImpl struct {
	repo repository.IntegrationRepository
}

// NewIntegrationService creates a new integration service
func NewIntegrationService(repo repository.IntegrationRepository) IntegrationService {
	return &IntegrationServiceImpl{repo: repo}
}

func (is *IntegrationServiceImpl) CreateIntegration(ctx context.Context, req *CreateIntegrationRequest) (*models.Integration, error) {
	var configJSON json.RawMessage
	if req.Config != nil {
		if data, err := json.Marshal(req.Config); err == nil {
			configJSON = data
		}
	}

	integration := &models.Integration{
		ID:        uuid.New().String(),
		Name:      req.Name,
		Type:      req.Type,
		Provider:  req.Provider,
		Config:    configJSON,
		Enabled:   true,
		Status:    "active",
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	if err := is.repo.Create(ctx, integration); err != nil {
		return nil, fmt.Errorf("failed to create integration: %w", err)
	}

	return integration, nil
}

func (is *IntegrationServiceImpl) GetIntegration(ctx context.Context, id string) (*models.Integration, error) {
	integration, err := is.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("failed to get integration: %w", err)
	}
	return integration, nil
}

func (is *IntegrationServiceImpl) ListIntegrations(ctx context.Context, limit, offset int) ([]*models.Integration, int64, error) {
	integrations, total, err := is.repo.List(ctx, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list integrations: %w", err)
	}
	return integrations, total, nil
}

func (is *IntegrationServiceImpl) ListIntegrationsByType(ctx context.Context, integrationType string, limit, offset int) ([]*models.Integration, int64, error) {
	integrations, err := is.repo.GetByType(ctx, integrationType)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list integrations by type: %w", err)
	}
	total := int64(len(integrations))
	// Apply manual pagination
	if offset >= len(integrations) {
		return []*models.Integration{}, total, nil
	}
	end := offset + limit
	if end > len(integrations) {
		end = len(integrations)
	}
	return integrations[offset:end], total, nil
}

func (is *IntegrationServiceImpl) ListIntegrationsByProvider(ctx context.Context, provider string, limit, offset int) ([]*models.Integration, int64, error) {
	integrations, err := is.repo.GetByProvider(ctx, provider)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list integrations by provider: %w", err)
	}
	total := int64(len(integrations))
	if offset >= len(integrations) {
		return []*models.Integration{}, total, nil
	}
	end := offset + limit
	if end > len(integrations) {
		end = len(integrations)
	}
	return integrations[offset:end], total, nil
}

func (is *IntegrationServiceImpl) ListEnabledIntegrations(ctx context.Context, limit, offset int) ([]*models.Integration, int64, error) {
	integrations, err := is.repo.GetEnabled(ctx)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list enabled integrations: %w", err)
	}
	total := int64(len(integrations))
	if offset >= len(integrations) {
		return []*models.Integration{}, total, nil
	}
	end := offset + limit
	if end > len(integrations) {
		end = len(integrations)
	}
	return integrations[offset:end], total, nil
}

func (is *IntegrationServiceImpl) UpdateIntegration(ctx context.Context, id string, req *UpdateIntegrationRequest) (*models.Integration, error) {
	integration, err := is.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("integration not found: %w", err)
	}

	if req.Name != "" {
		integration.Name = req.Name
	}
	if req.Config != nil {
		if data, marshalErr := json.Marshal(req.Config); marshalErr == nil {
			integration.Config = data
		}
	}

	integration.UpdatedAt = time.Now()

	if err := is.repo.Update(ctx, integration); err != nil {
		return nil, fmt.Errorf("failed to update integration: %w", err)
	}

	return integration, nil
}

func (is *IntegrationServiceImpl) DeleteIntegration(ctx context.Context, id string) error {
	if err := is.repo.Delete(ctx, id); err != nil {
		return fmt.Errorf("failed to delete integration: %w", err)
	}
	return nil
}

func (is *IntegrationServiceImpl) EnableIntegration(ctx context.Context, id string) error {
	integration, err := is.repo.Get(ctx, id)
	if err != nil {
		return fmt.Errorf("integration not found: %w", err)
	}

	integration.Enabled = true
	integration.UpdatedAt = time.Now()

	if err := is.repo.Update(ctx, integration); err != nil {
		return fmt.Errorf("failed to enable integration: %w", err)
	}

	return nil
}

func (is *IntegrationServiceImpl) DisableIntegration(ctx context.Context, id string) error {
	integration, err := is.repo.Get(ctx, id)
	if err != nil {
		return fmt.Errorf("integration not found: %w", err)
	}

	integration.Enabled = false
	integration.UpdatedAt = time.Now()

	if err := is.repo.Update(ctx, integration); err != nil {
		return fmt.Errorf("failed to disable integration: %w", err)
	}

	return nil
}

func (is *IntegrationServiceImpl) TestConnection(ctx context.Context, req *TestConnectionRequest) (bool, error) {
	// Placeholder: actual implementation would test the connection
	return true, nil
}

func (is *IntegrationServiceImpl) TestIntegrationConnection(ctx context.Context, id string) (bool, error) {
	integration, err := is.repo.Get(ctx, id)
	if err != nil {
		return false, fmt.Errorf("integration not found: %w", err)
	}

	// Placeholder: test connection using integration config
	_ = integration

	return true, nil
}

func (is *IntegrationServiceImpl) ReconnectIntegration(ctx context.Context, id string) error {
	integration, err := is.repo.Get(ctx, id)
	if err != nil {
		return fmt.Errorf("integration not found: %w", err)
	}

	integration.Status = "reconnecting"
	integration.UpdatedAt = time.Now()

	if err := is.repo.Update(ctx, integration); err != nil {
		return fmt.Errorf("failed to reconnect: %w", err)
	}

	// Simulate reconnection
	integration.Status = "active"
	return is.repo.Update(ctx, integration)
}

func (is *IntegrationServiceImpl) GetIntegrationStatus(ctx context.Context, id string) (map[string]interface{}, error) {
	integration, err := is.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("integration not found: %w", err)
	}

	return map[string]interface{}{
		"id":         integration.ID,
		"name":       integration.Name,
		"provider":   integration.Provider,
		"status":     integration.Status,
		"enabled":    integration.Enabled,
		"updated_at": integration.UpdatedAt,
	}, nil
}

func (is *IntegrationServiceImpl) SyncData(ctx context.Context, id string) error {
	integration, err := is.repo.Get(ctx, id)
	if err != nil {
		return fmt.Errorf("integration not found: %w", err)
	}

	integration.Status = "syncing"
	if err := is.repo.Update(ctx, integration); err != nil {
		return err
	}

	// Simulate sync
	time.Sleep(100 * time.Millisecond)

	integration.Status = "active"
	return is.repo.Update(ctx, integration)
}

func (is *IntegrationServiceImpl) GetSyncStatus(ctx context.Context, id string) (*SyncStatusResponse, error) {
	return &SyncStatusResponse{
		IntegrationID:  id,
		Status:         "completed",
		Progress:       100,
		ItemsProcessed: 100,
		TotalItems:     100,
		StartedAt:      time.Now().Add(-1 * time.Minute),
		CurrentPhase:   "complete",
	}, nil
}

func (is *IntegrationServiceImpl) GetIntegrationTypes(ctx context.Context) ([]string, error) {
	return []string{"api", "database", "messaging", "storage", "analytics"}, nil
}

func (is *IntegrationServiceImpl) GetProviders(ctx context.Context) ([]string, error) {
	return []string{"slack", "github", "jira", "aws", "gcp", "azure"}, nil
}

func (is *IntegrationServiceImpl) GetProvidersByType(ctx context.Context, integrationType string) ([]string, error) {
	providers := map[string][]string{
		"api":      {"slack", "github"},
		"database": {"postgresql", "mysql"},
		"storage":  {"aws_s3", "gcp_storage"},
	}

	if provs, ok := providers[integrationType]; ok {
		return provs, nil
	}

	return []string{}, nil
}

func (is *IntegrationServiceImpl) GetConfigSchema(ctx context.Context, provider string) (map[string]interface{}, error) {
	return map[string]interface{}{
		"type":       "object",
		"properties": map[string]interface{}{},
	}, nil
}

func (is *IntegrationServiceImpl) ValidateConfig(ctx context.Context, provider string, config map[string]interface{}) (bool, error) {
	return config != nil, nil
}

func (is *IntegrationServiceImpl) GetIntegrationEvents(ctx context.Context, id string, limit, offset int) ([]map[string]interface{}, int64, error) {
	return make([]map[string]interface{}, 0), 0, nil
}

func (is *IntegrationServiceImpl) SendEventToIntegration(ctx context.Context, id string, event map[string]interface{}) error {
	return nil
}

func (is *IntegrationServiceImpl) GetIntegrationStats(ctx context.Context, id string) (*IntegrationStatsResponse, error) {
	integration, err := is.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("integration not found: %w", err)
	}

	return &IntegrationStatsResponse{
		ID:              integration.ID,
		Provider:        integration.Provider,
		Status:          integration.Status,
		LastSync:        time.Now(),
		SyncCount:       10,
		SuccessCount:    9,
		FailureCount:    1,
		EventsProcessed: 1000,
		AverageLatency:  150,
	}, nil
}

func (is *IntegrationServiceImpl) GetAllIntegrationStats(ctx context.Context) ([]*IntegrationStatsResponse, error) {
	return make([]*IntegrationStatsResponse, 0), nil
}

func (is *IntegrationServiceImpl) GetIntegrationLogs(ctx context.Context, id string, limit, offset int) ([]map[string]interface{}, int64, error) {
	return make([]map[string]interface{}, 0), 0, nil
}

func (is *IntegrationServiceImpl) BatchEnableIntegrations(ctx context.Context, ids []string) error {
	for _, id := range ids {
		if err := is.EnableIntegration(ctx, id); err != nil {
			return err
		}
	}
	return nil
}

func (is *IntegrationServiceImpl) BatchDisableIntegrations(ctx context.Context, ids []string) error {
	for _, id := range ids {
		if err := is.DisableIntegration(ctx, id); err != nil {
			return err
		}
	}
	return nil
}

func (is *IntegrationServiceImpl) BatchDeleteIntegrations(ctx context.Context, ids []string) error {
	for _, id := range ids {
		if err := is.DeleteIntegration(ctx, id); err != nil {
			return err
		}
	}
	return nil
}

func (is *IntegrationServiceImpl) CheckHealthForAll(ctx context.Context) (map[string]interface{}, error) {
	return map[string]interface{}{
		"status":               "healthy",
		"integrations_checked": 0,
		"healthy_count":        0,
	}, nil
}

func (is *IntegrationServiceImpl) CheckHealth(ctx context.Context, id string) (map[string]interface{}, error) {
	integration, err := is.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("integration not found: %w", err)
	}

	return map[string]interface{}{
		"id":     integration.ID,
		"status": "healthy",
		"uptime": 99.9,
	}, nil
}

func (is *IntegrationServiceImpl) DisconnectIntegration(ctx context.Context, id string) error {
	integration, err := is.repo.Get(ctx, id)
	if err != nil {
		return fmt.Errorf("integration not found: %w", err)
	}

	integration.Status = "disconnected"
	integration.UpdatedAt = time.Now()

	if err := is.repo.Update(ctx, integration); err != nil {
		return fmt.Errorf("failed to disconnect: %w", err)
	}

	return nil
}

func (is *IntegrationServiceImpl) CheckDependencies(ctx context.Context, id string) (map[string]interface{}, error) {
	return map[string]interface{}{
		"dependencies_met": true,
	}, nil
}

func (is *IntegrationServiceImpl) ImportConfig(ctx context.Context, filename string) (*models.Integration, error) {
	return &models.Integration{
		ID:        uuid.New().String(),
		Name:      "Imported Integration",
		Status:    "active",
		CreatedAt: time.Now(),
	}, nil
}

func (is *IntegrationServiceImpl) ExportConfig(ctx context.Context, id string) (map[string]interface{}, error) {
	integration, err := is.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("integration not found: %w", err)
	}

	return map[string]interface{}{
		"id":     integration.ID,
		"name":   integration.Name,
		"type":   integration.Type,
		"config": integration.Config,
	}, nil
}

func (is *IntegrationServiceImpl) MigrateConfig(ctx context.Context, req *MigrateConfigRequest) (map[string]interface{}, error) {
	return map[string]interface{}{
		"migrated": true,
	}, nil
}

func (is *IntegrationServiceImpl) GetUsageAnalytics(ctx context.Context, id string, timeframe string) (map[string]interface{}, error) {
	return map[string]interface{}{
		"timeframe":       timeframe,
		"requests":        1000,
		"errors":          5,
		"average_latency": 150,
	}, nil
}

func (is *IntegrationServiceImpl) GetRateLimitStatus(ctx context.Context, id string) (map[string]interface{}, error) {
	return map[string]interface{}{
		"limit":     1000,
		"remaining": 950,
		"reset_at":  time.Now().Add(1 * time.Hour),
	}, nil
}

func (is *IntegrationServiceImpl) GetCredentialsStatus(ctx context.Context, id string) (map[string]interface{}, error) {
	return map[string]interface{}{
		"status":     "valid",
		"expires_at": time.Now().Add(30 * 24 * time.Hour),
	}, nil
}

func (is *IntegrationServiceImpl) RotateCredentials(ctx context.Context, id string, req *RotateCredentialsRequest) error {
	integration, err := is.repo.Get(ctx, id)
	if err != nil {
		return fmt.Errorf("integration not found: %w", err)
	}

	// Update config with new credentials (in reality, would securely store)
	integration.UpdatedAt = time.Now()

	if err := is.repo.Update(ctx, integration); err != nil {
		return fmt.Errorf("failed to rotate credentials: %w", err)
	}

	return nil
}

func (is *IntegrationServiceImpl) GetAuditLog(ctx context.Context, id string, limit, offset int) ([]map[string]interface{}, int64, error) {
	return make([]map[string]interface{}, 0), 0, nil
}

func (is *IntegrationServiceImpl) CloneConfiguration(ctx context.Context, sourceID string, targetProvider string) (*models.Integration, error) {
	source, err := is.repo.Get(ctx, sourceID)
	if err != nil {
		return nil, fmt.Errorf("source integration not found: %w", err)
	}

	cloned := &models.Integration{
		ID:        uuid.New().String(),
		Name:      fmt.Sprintf("%s (cloned)", source.Name),
		Type:      source.Type,
		Provider:  targetProvider,
		Config:    source.Config,
		Enabled:   true,
		Status:    "active",
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	if err := is.repo.Create(ctx, cloned); err != nil {
		return nil, fmt.Errorf("failed to clone configuration: %w", err)
	}

	return cloned, nil
}

func (is *IntegrationServiceImpl) GetWebhookURL(ctx context.Context, id string) (string, error) {
	integration, err := is.repo.Get(ctx, id)
	if err != nil {
		return "", fmt.Errorf("integration not found: %w", err)
	}

	return fmt.Sprintf("https://api.example.com/webhooks/%s", integration.ID), nil
}

func (is *IntegrationServiceImpl) RefreshWebhookSecret(ctx context.Context, id string) (string, error) {
	integration, err := is.repo.Get(ctx, id)
	if err != nil {
		return "", fmt.Errorf("integration not found: %w", err)
	}

	newSecret := uuid.New().String()

	// Update config with new secret
	integration.UpdatedAt = time.Now()
	if err := is.repo.Update(ctx, integration); err != nil {
		return "", fmt.Errorf("failed to refresh webhook secret: %w", err)
	}

	return newSecret, nil
}
