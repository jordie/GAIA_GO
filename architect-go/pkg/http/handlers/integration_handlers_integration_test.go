package handlers

import (
	"fmt"
	"net/http"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"architect-go/pkg/errors"
	"architect-go/pkg/models"
	"architect-go/pkg/services"
)

// TestIntegrationHandlers_ListIntegrations tests the ListIntegrations endpoint
func TestIntegrationHandlers_ListIntegrations(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	integration1 := &models.Integration{
		ID:       "int-1",
		Name:     "Slack",
		Type:     "messaging",
		Provider: "slack",
		Enabled:  true,
	}
	integration2 := &models.Integration{
		ID:       "int-2",
		Name:     "GitHub",
		Type:     "vcs",
		Provider: "github",
		Enabled:  true,
	}
	setup.DB.Create(integration1)
	setup.DB.Create(integration2)

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	integrationHandlers := NewIntegrationHandlers(setup.ServiceRegistry.IntegrationService, errHandler)

	// Setup route
	setup.Router.Get("/api/integrations", integrationHandlers.ListIntegrations)

	// Make request
	recorder := setup.MakeRequest("GET", "/api/integrations?limit=10&offset=0", nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["integrations"])
	assert.NotNil(t, response["total"])
}

// TestIntegrationHandlers_GetIntegration tests the GetIntegration endpoint
func TestIntegrationHandlers_GetIntegration(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	integration := &models.Integration{
		ID:       "int-1",
		Name:     "Slack",
		Type:     "messaging",
		Provider: "slack",
		Enabled:  true,
	}
	setup.DB.Create(integration)

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	integrationHandlers := NewIntegrationHandlers(setup.ServiceRegistry.IntegrationService, errHandler)

	// Setup route
	setup.Router.Get("/api/integrations/{id}", integrationHandlers.GetIntegration)

	// Make request
	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/integrations/%s", integration.ID), nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["integration"])
}

// TestIntegrationHandlers_CreateIntegration tests creating an integration
func TestIntegrationHandlers_CreateIntegration(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	integrationHandlers := NewIntegrationHandlers(setup.ServiceRegistry.IntegrationService, errHandler)

	// Setup route
	setup.Router.Post("/api/integrations", integrationHandlers.CreateIntegration)

	// Prepare request
	requestBody := services.CreateIntegrationRequest{
		Name:     "Slack",
		Type:     "messaging",
		Provider: "slack",
		Config: map[string]interface{}{
			"token": "xoxb-123456789",
		},
	}

	// Make request
	recorder := setup.MakeRequest("POST", "/api/integrations", requestBody)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusCreated)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["integration"])
}

// TestIntegrationHandlers_EnableIntegration tests enabling an integration
func TestIntegrationHandlers_EnableIntegration(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	integration := &models.Integration{
		ID:       "int-1",
		Name:     "Slack",
		Type:     "messaging",
		Provider: "slack",
		Enabled:  false,
	}
	setup.DB.Create(integration)

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	integrationHandlers := NewIntegrationHandlers(setup.ServiceRegistry.IntegrationService, errHandler)

	// Setup route
	setup.Router.Put("/api/integrations/{id}/enable", integrationHandlers.EnableIntegration)

	// Make request
	recorder := setup.MakeRequest("PUT", fmt.Sprintf("/api/integrations/%s/enable", integration.ID), nil)

	// Assertions
	assert.True(t, recorder.Code == http.StatusOK || recorder.Code == http.StatusNoContent,
		"expected 200 or 204 but got %d", recorder.Code)
}

// TestIntegrationHandlers_DisableIntegration tests disabling an integration
func TestIntegrationHandlers_DisableIntegration(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	integration := &models.Integration{
		ID:       "int-1",
		Name:     "Slack",
		Type:     "messaging",
		Provider: "slack",
		Enabled:  true,
	}
	setup.DB.Create(integration)

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	integrationHandlers := NewIntegrationHandlers(setup.ServiceRegistry.IntegrationService, errHandler)

	// Setup route
	setup.Router.Put("/api/integrations/{id}/disable", integrationHandlers.DisableIntegration)

	// Make request
	recorder := setup.MakeRequest("PUT", fmt.Sprintf("/api/integrations/%s/disable", integration.ID), nil)

	// Assertions
	assert.True(t, recorder.Code == http.StatusOK || recorder.Code == http.StatusNoContent,
		"expected 200 or 204 but got %d", recorder.Code)
}

// TestIntegrationHandlers_TestConnection tests connection validation
func TestIntegrationHandlers_TestConnection(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	integrationHandlers := NewIntegrationHandlers(setup.ServiceRegistry.IntegrationService, errHandler)

	// Setup route
	setup.Router.Post("/api/integrations/test-connection", integrationHandlers.TestConnection)

	// Prepare request
	requestBody := services.TestConnectionRequest{
		Config: map[string]interface{}{
			"provider": "slack",
			"token":    "xoxb-123456789",
		},
	}

	// Make request
	recorder := setup.MakeRequest("POST", "/api/integrations/test-connection", requestBody)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["success"])
}

// TestIntegrationHandlers_DeleteIntegration tests deleting an integration
func TestIntegrationHandlers_DeleteIntegration(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	integration := &models.Integration{
		ID:       "int-1",
		Name:     "Slack",
		Type:     "messaging",
		Provider: "slack",
		Enabled:  true,
	}
	setup.DB.Create(integration)

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	integrationHandlers := NewIntegrationHandlers(setup.ServiceRegistry.IntegrationService, errHandler)

	// Setup route
	setup.Router.Delete("/api/integrations/{id}", integrationHandlers.DeleteIntegration)

	// Make request
	recorder := setup.MakeRequest("DELETE", fmt.Sprintf("/api/integrations/%s", integration.ID), nil)

	// Assertions
	assert.True(t, recorder.Code == http.StatusOK || recorder.Code == http.StatusNoContent,
		"expected 200 or 204 but got %d", recorder.Code)
}

// TestIntegrationHandlers_GetIntegrationStatus tests status retrieval
func TestIntegrationHandlers_GetIntegrationStatus(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	integration := &models.Integration{
		ID:       "int-1",
		Name:     "Slack",
		Type:     "messaging",
		Provider: "slack",
		Enabled:  true,
	}
	setup.DB.Create(integration)

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	integrationHandlers := NewIntegrationHandlers(setup.ServiceRegistry.IntegrationService, errHandler)

	// Setup route
	setup.Router.Get("/api/integrations/{id}/status", integrationHandlers.GetIntegrationStatus)

	// Make request
	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/integrations/%s/status", integration.ID), nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["status"])
}
