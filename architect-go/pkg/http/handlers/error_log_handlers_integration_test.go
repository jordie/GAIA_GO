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

// TestErrorLogHandlers_ListErrors tests the ListErrors endpoint
func TestErrorLogHandlers_ListErrors(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	setup.CreateTestErrorLog("runtime_error", "critical", "api")
	setup.CreateTestErrorLog("network_error", "warning", "api")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	errorLogHandlers := NewErrorLogHandlers(setup.ServiceRegistry.ErrorLogService, errHandler)

	// Setup route
	setup.Router.Get("/api/error-logs", errorLogHandlers.ListErrors)

	// Make request
	recorder := setup.MakeRequest("GET", "/api/error-logs?limit=10&offset=0", nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["errors"])
	assert.NotNil(t, response["total"])
}

// TestErrorLogHandlers_GetError tests the GetError endpoint
func TestErrorLogHandlers_GetError(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	errorLog := setup.CreateTestErrorLog("runtime_error", "critical", "api")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	errorLogHandlers := NewErrorLogHandlers(setup.ServiceRegistry.ErrorLogService, errHandler)

	// Setup route
	setup.Router.Get("/api/error-logs/{id}", errorLogHandlers.GetError)

	// Make request
	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/error-logs/%s", errorLog.ID), nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["error"])
}

// TestErrorLogHandlers_CreateError tests creating an error through the handler
func TestErrorLogHandlers_CreateError(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	errorLogHandlers := NewErrorLogHandlers(setup.ServiceRegistry.ErrorLogService, errHandler)

	// Setup route
	setup.Router.Post("/api/error-logs", errorLogHandlers.LogError)

	// Prepare request
	requestBody := services.LogErrorRequest{
		ErrorType:  "runtime_error",
		Message:    "Test error creation",
		Source:     "api",
		Severity:   "high",
		StackTrace: "test stack trace",
	}

	// Make request
	recorder := setup.MakeRequest("POST", "/api/error-logs", requestBody)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusCreated)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["error"])
}

// TestErrorLogHandlers_ListCriticalErrors tests filtering critical errors
func TestErrorLogHandlers_ListCriticalErrors(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	setup.CreateTestErrorLog("runtime_error", "critical", "api")
	setup.CreateTestErrorLog("runtime_error", "warning", "api")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	errorLogHandlers := NewErrorLogHandlers(setup.ServiceRegistry.ErrorLogService, errHandler)

	// Setup route
	setup.Router.Get("/api/error-logs", errorLogHandlers.ListErrors)

	// Make request with severity filter
	recorder := setup.MakeRequest("GET", "/api/error-logs?severity=critical", nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["errors"])
}

// TestErrorLogHandlers_ResolveError tests resolving an error
func TestErrorLogHandlers_ResolveError(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	errorLog := setup.CreateTestErrorLog("runtime_error", "critical", "api")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	errorLogHandlers := NewErrorLogHandlers(setup.ServiceRegistry.ErrorLogService, errHandler)

	// Setup route
	setup.Router.Put("/api/error-logs/{id}/resolve", errorLogHandlers.ResolveError)

	// Prepare request
	requestBody := services.ResolveErrorRequest{
		Status:     "resolved",
		Resolution: "Fixed in v1.0.0",
	}

	// Make request
	recorder := setup.MakeRequest("PUT", fmt.Sprintf("/api/error-logs/%s/resolve", errorLog.ID), requestBody)

	// Assertions
	assert.True(t, recorder.Code == http.StatusOK || recorder.Code == http.StatusNoContent,
		"expected 200 or 204 but got %d", recorder.Code)
}

// TestErrorLogHandlers_DeleteError tests deleting an error
func TestErrorLogHandlers_DeleteError(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	errorLog := setup.CreateTestErrorLog("runtime_error", "critical", "api")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	errorLogHandlers := NewErrorLogHandlers(setup.ServiceRegistry.ErrorLogService, errHandler)

	// Setup route
	setup.Router.Delete("/api/error-logs/{id}", errorLogHandlers.DeleteError)

	// Make request
	recorder := setup.MakeRequest("DELETE", fmt.Sprintf("/api/error-logs/%s", errorLog.ID), nil)

	// Assertions
	assert.True(t, recorder.Code == http.StatusOK || recorder.Code == http.StatusNoContent,
		"expected 200 or 204 but got %d", recorder.Code)

	// Verify error was deleted from database
	var deletedError *models.ErrorLog
	result := setup.DB.Where("id = ?", errorLog.ID).First(&deletedError)
	assert.Error(t, result.Error, "error should be deleted")
}

// TestErrorLogHandlers_GetErrorStats tests error statistics
func TestErrorLogHandlers_GetErrorStats(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	setup.CreateTestErrorLog("runtime_error", "critical", "api")
	setup.CreateTestErrorLog("network_error", "warning", "api")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	errorLogHandlers := NewErrorLogHandlers(setup.ServiceRegistry.ErrorLogService, errHandler)

	// Setup route
	setup.Router.Get("/api/error-logs/stats", errorLogHandlers.GetErrorStats)

	// Make request
	recorder := setup.MakeRequest("GET", "/api/error-logs/stats", nil)

	// Assertions
	assert.Equal(t, http.StatusOK, recorder.Code)
}
