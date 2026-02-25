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

// TestEventLogHandlers_ListEvents tests the ListEvents endpoint
func TestEventLogHandlers_ListEvents(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	setup.CreateTestEventLog("user_action", "dashboard", user.ID)
	setup.CreateTestEventLog("user_action", "api", user.ID)

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	eventLogHandlers := NewEventLogHandlers(setup.ServiceRegistry.EventLogService, errHandler)

	// Setup route
	setup.Router.Get("/api/event-logs", eventLogHandlers.ListEvents)

	// Make request
	recorder := setup.MakeRequest("GET", "/api/event-logs?limit=10&offset=0", nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["events"])
	assert.NotNil(t, response["total"])
	assert.Equal(t, float64(10), response["limit"])
	assert.Equal(t, float64(0), response["offset"])
}

// TestEventLogHandlers_GetEvent tests the GetEvent endpoint
func TestEventLogHandlers_GetEvent(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	event := setup.CreateTestEventLog("user_action", "dashboard", user.ID)

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	eventLogHandlers := NewEventLogHandlers(setup.ServiceRegistry.EventLogService, errHandler)

	// Setup route
	setup.Router.Get("/api/event-logs/{id}", eventLogHandlers.GetEvent)

	// Make request
	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/event-logs/%s", event.ID), nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["event"])
}

// TestEventLogHandlers_GetEventNotFound tests 404 error handling
func TestEventLogHandlers_GetEventNotFound(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	eventLogHandlers := NewEventLogHandlers(setup.ServiceRegistry.EventLogService, errHandler)

	// Setup route
	setup.Router.Get("/api/event-logs/{id}", eventLogHandlers.GetEvent)

	// Make request for non-existent event
	recorder := setup.MakeRequest("GET", "/api/event-logs/non-existent-id", nil)

	// Assertions
	assert.NotEqual(t, http.StatusOK, recorder.Code)
}

// TestEventLogHandlers_CreateEvent tests creating an event through the handler
func TestEventLogHandlers_CreateEvent(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	setup.CreateTestUser("user-1", "Test User", "test@example.com")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	eventLogHandlers := NewEventLogHandlers(setup.ServiceRegistry.EventLogService, errHandler)

	// Setup route
	setup.Router.Post("/api/event-logs", eventLogHandlers.CreateEvent)

	// Prepare request
	requestBody := services.CreateEventRequest{
		Type:        "user_action",
		Description: "Test event creation",
		Source:      "api",
		UserID:      "user-1",
		ProjectID:   "project-1",
		Tags:        []string{"test"},
	}

	// Make request
	recorder := setup.MakeRequest("POST", "/api/event-logs", requestBody)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusCreated)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["event"])
}

// TestEventLogHandlers_ListEventsByType tests filtering events by type
func TestEventLogHandlers_ListEventsByType(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	setup.CreateTestEventLog("user_action", "dashboard", user.ID)
	setup.CreateTestEventLog("system", "api", user.ID)

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	eventLogHandlers := NewEventLogHandlers(setup.ServiceRegistry.EventLogService, errHandler)

	// Setup route
	setup.Router.Get("/api/event-logs", eventLogHandlers.ListEvents)

	// Make request with type filter
	recorder := setup.MakeRequest("GET", "/api/event-logs?type=user_action", nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["events"])
}

// TestEventLogHandlers_DeleteEvent tests deleting an event
func TestEventLogHandlers_DeleteEvent(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	event := setup.CreateTestEventLog("user_action", "dashboard", user.ID)

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	eventLogHandlers := NewEventLogHandlers(setup.ServiceRegistry.EventLogService, errHandler)

	// Setup route
	setup.Router.Delete("/api/event-logs/{id}", eventLogHandlers.DeleteEvent)

	// Make request
	recorder := setup.MakeRequest("DELETE", fmt.Sprintf("/api/event-logs/%s", event.ID), nil)

	// Assertions - check that the response is successful (200 or 204)
	assert.True(t, recorder.Code == http.StatusOK || recorder.Code == http.StatusNoContent,
		"expected 200 or 204 but got %d", recorder.Code)

	// Verify event was deleted from database
	var deletedEvent *models.EventLog
	result := setup.DB.Where("id = ?", event.ID).First(&deletedEvent)
	assert.Error(t, result.Error, "event should be deleted")
}
