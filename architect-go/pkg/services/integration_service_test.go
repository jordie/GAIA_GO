package services

import (
	"context"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"

	"architect-go/pkg/models"
)

// MockIntegrationRepository mocks the IntegrationRepository
type MockIntegrationRepository struct {
	mock.Mock
}

func (m *MockIntegrationRepository) Create(ctx context.Context, integration *models.Integration) error {
	args := m.Called(ctx, integration)
	return args.Error(0)
}

func (m *MockIntegrationRepository) Get(ctx context.Context, id string) (*models.Integration, error) {
	args := m.Called(ctx, id)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*models.Integration), args.Error(1)
}

func (m *MockIntegrationRepository) List(ctx context.Context, limit int, offset int) ([]*models.Integration, int64, error) {
	args := m.Called(ctx, limit, offset)
	if args.Get(0) == nil {
		return nil, 0, args.Error(2)
	}
	return args.Get(0).([]*models.Integration), args.Get(1).(int64), args.Error(2)
}

func (m *MockIntegrationRepository) GetByType(ctx context.Context, integrationType string) ([]*models.Integration, error) {
	args := m.Called(ctx, integrationType)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]*models.Integration), args.Error(1)
}

func (m *MockIntegrationRepository) GetByProvider(ctx context.Context, provider string) ([]*models.Integration, error) {
	args := m.Called(ctx, provider)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]*models.Integration), args.Error(1)
}

func (m *MockIntegrationRepository) GetEnabled(ctx context.Context) ([]*models.Integration, error) {
	args := m.Called(ctx)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]*models.Integration), args.Error(1)
}

func (m *MockIntegrationRepository) Update(ctx context.Context, integration *models.Integration) error {
	args := m.Called(ctx, integration)
	return args.Error(0)
}

func (m *MockIntegrationRepository) Delete(ctx context.Context, id string) error {
	args := m.Called(ctx, id)
	return args.Error(0)
}

func (m *MockIntegrationRepository) CreateSyncRecord(ctx context.Context, syncRecord map[string]interface{}) error {
	args := m.Called(ctx, syncRecord)
	return args.Error(0)
}

func (m *MockIntegrationRepository) GetSyncStatus(ctx context.Context, integrationID string) (map[string]interface{}, error) {
	args := m.Called(ctx, integrationID)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(map[string]interface{}), args.Error(1)
}

// TestIntegrationService_CreateIntegration tests integration creation
func TestIntegrationService_CreateIntegration(t *testing.T) {
	mockRepo := new(MockIntegrationRepository)
	ctx := context.Background()

	mockRepo.On("Create", ctx, mock.MatchedBy(func(i *models.Integration) bool {
		return i.Name == "Slack" && i.Provider == "slack"
	})).Return(nil)

	service := NewIntegrationService(mockRepo)
	req := &CreateIntegrationRequest{
		Name:     "Slack",
		Type:     "messaging",
		Provider: "slack",
		Config:   map[string]interface{}{"token": "xxx"},
	}

	result, err := service.CreateIntegration(ctx, req)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Equal(t, "Slack", result.Name)
	mockRepo.AssertCalled(t, "Create", ctx, mock.AnythingOfType("*models.Integration"))
}

// TestIntegrationService_EnableIntegration tests enabling integration
func TestIntegrationService_EnableIntegration(t *testing.T) {
	mockRepo := new(MockIntegrationRepository)
	ctx := context.Background()

	integration := &models.Integration{
		ID:      "int-1",
		Enabled: false,
	}

	mockRepo.On("Get", ctx, "int-1").Return(integration, nil)
	mockRepo.On("Update", ctx, mock.MatchedBy(func(i *models.Integration) bool {
		return i.Enabled == true
	})).Return(nil)

	service := NewIntegrationService(mockRepo)
	err := service.EnableIntegration(ctx, "int-1")

	assert.NoError(t, err)
	mockRepo.AssertCalled(t, "Get", ctx, "int-1")
	mockRepo.AssertCalled(t, "Update", ctx, mock.AnythingOfType("*models.Integration"))
}

// TestIntegrationService_DisableIntegration tests disabling integration
func TestIntegrationService_DisableIntegration(t *testing.T) {
	mockRepo := new(MockIntegrationRepository)
	ctx := context.Background()

	integration := &models.Integration{
		ID:      "int-1",
		Enabled: true,
	}

	mockRepo.On("Get", ctx, "int-1").Return(integration, nil)
	mockRepo.On("Update", ctx, mock.MatchedBy(func(i *models.Integration) bool {
		return i.Enabled == false
	})).Return(nil)

	service := NewIntegrationService(mockRepo)
	err := service.DisableIntegration(ctx, "int-1")

	assert.NoError(t, err)
	mockRepo.AssertCalled(t, "Get", ctx, "int-1")
	mockRepo.AssertCalled(t, "Update", ctx, mock.AnythingOfType("*models.Integration"))
}

// TestIntegrationService_ListIntegrationsByType tests filtering by type
func TestIntegrationService_ListIntegrationsByType(t *testing.T) {
	mockRepo := new(MockIntegrationRepository)
	ctx := context.Background()

	integrations := []*models.Integration{
		{ID: "int-1", Type: "messaging"},
		{ID: "int-2", Type: "messaging"},
	}

	mockRepo.On("GetByType", ctx, "messaging").Return(integrations, nil)

	service := NewIntegrationService(mockRepo)
	results, total, err := service.ListIntegrationsByType(ctx, "messaging", 10, 0)

	assert.NoError(t, err)
	assert.Equal(t, int64(2), total)
	assert.Equal(t, 2, len(results))
	mockRepo.AssertCalled(t, "GetByType", ctx, "messaging")
}

// TestIntegrationService_TestConnection tests connection validation
func TestIntegrationService_TestConnection(t *testing.T) {
	mockRepo := new(MockIntegrationRepository)
	ctx := context.Background()

	service := NewIntegrationService(mockRepo)
	req := &TestConnectionRequest{
		Config: map[string]interface{}{"token": "xxx"},
	}

	result, err := service.TestConnection(ctx, req)

	assert.NoError(t, err)
	assert.True(t, result)
}

// TestIntegrationService_GetIntegrationStatus tests status retrieval
func TestIntegrationService_GetIntegrationStatus(t *testing.T) {
	mockRepo := new(MockIntegrationRepository)
	ctx := context.Background()

	integration := &models.Integration{
		ID:      "int-1",
		Name:    "Slack",
		Status:  "active",
		Enabled: true,
	}

	mockRepo.On("Get", ctx, "int-1").Return(integration, nil)

	service := NewIntegrationService(mockRepo)
	status, err := service.GetIntegrationStatus(ctx, "int-1")

	assert.NoError(t, err)
	assert.NotNil(t, status)
	assert.Equal(t, "active", status["status"])
	mockRepo.AssertCalled(t, "Get", ctx, "int-1")
}
