package handlers

import (
	"fmt"
	"net/http"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"architect-go/pkg/errors"
	"architect-go/pkg/services"
)

// TestNotificationHandlers_ListNotifications tests the ListNotifications endpoint
func TestNotificationHandlers_ListNotifications(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	setup.CreateTestNotification(user.ID, "Test Notification", "alert")
	setup.CreateTestNotification(user.ID, "Another Notification", "info")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	notificationHandlers := NewNotificationHandlers(setup.ServiceRegistry.NotificationService, errHandler)

	// Setup route
	setup.Router.Get("/api/notifications", notificationHandlers.ListNotifications)

	// Make request
	recorder := setup.MakeRequest("GET", "/api/notifications?limit=10&offset=0", nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["notifications"])
	assert.NotNil(t, response["total"])
}

// TestNotificationHandlers_GetNotification tests the GetNotification endpoint
func TestNotificationHandlers_GetNotification(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	notification := setup.CreateTestNotification(user.ID, "Test Notification", "alert")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	notificationHandlers := NewNotificationHandlers(setup.ServiceRegistry.NotificationService, errHandler)

	// Setup route
	setup.Router.Get("/api/notifications/{id}", notificationHandlers.GetNotification)

	// Make request
	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/notifications/%s", notification.ID), nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["notification"])
}

// TestNotificationHandlers_CreateNotification tests creating a notification
func TestNotificationHandlers_CreateNotification(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	notificationHandlers := NewNotificationHandlers(setup.ServiceRegistry.NotificationService, errHandler)

	// Setup route
	setup.Router.Post("/api/notifications", notificationHandlers.CreateNotification)

	// Prepare request
	requestBody := services.CreateNotificationRequest{
		Recipients:       []string{user.ID},
		Title:            "Test Notification",
		Message:          "This is a test notification",
		NotificationType: "alert",
		Channels:         []string{"email"},
		Priority:         "high",
	}

	// Make request
	recorder := setup.MakeRequest("POST", "/api/notifications", requestBody)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusCreated)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["notification"])
}

// TestNotificationHandlers_MarkAsRead tests marking notification as read
func TestNotificationHandlers_MarkAsRead(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	notification := setup.CreateTestNotification(user.ID, "Test Notification", "alert")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	notificationHandlers := NewNotificationHandlers(setup.ServiceRegistry.NotificationService, errHandler)

	// Setup route
	setup.Router.Put("/api/notifications/{id}/read", notificationHandlers.MarkAsRead)

	// Make request
	recorder := setup.MakeRequest("PUT", fmt.Sprintf("/api/notifications/%s/read", notification.ID), nil)

	// Assertions
	assert.True(t, recorder.Code == http.StatusOK || recorder.Code == http.StatusNoContent,
		"expected 200 or 204 but got %d", recorder.Code)
}

// TestNotificationHandlers_DeleteNotification tests deleting a notification
func TestNotificationHandlers_DeleteNotification(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	notification := setup.CreateTestNotification(user.ID, "Test Notification", "alert")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	notificationHandlers := NewNotificationHandlers(setup.ServiceRegistry.NotificationService, errHandler)

	// Setup route
	setup.Router.Delete("/api/notifications/{id}", notificationHandlers.DeleteNotification)

	// Make request
	recorder := setup.MakeRequest("DELETE", fmt.Sprintf("/api/notifications/%s", notification.ID), nil)

	// Assertions
	assert.True(t, recorder.Code == http.StatusOK || recorder.Code == http.StatusNoContent,
		"expected 200 or 204 but got %d", recorder.Code)
}

// TestNotificationHandlers_ListUnreadNotifications tests listing unread notifications
func TestNotificationHandlers_ListUnreadNotifications(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	setup.CreateTestNotification(user.ID, "Unread Notification 1", "alert")
	setup.CreateTestNotification(user.ID, "Unread Notification 2", "info")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	notificationHandlers := NewNotificationHandlers(setup.ServiceRegistry.NotificationService, errHandler)

	// Setup route
	setup.Router.Get("/api/notifications/unread", notificationHandlers.ListUnreadNotifications)

	// Make request
	recorder := setup.MakeRequest("GET", "/api/notifications/unread?limit=10&offset=0", nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["notifications"])
}

// TestNotificationHandlers_SendNotification tests sending a notification
func TestNotificationHandlers_SendNotification(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	notificationHandlers := NewNotificationHandlers(setup.ServiceRegistry.NotificationService, errHandler)

	// Setup route
	setup.Router.Post("/api/notifications/send", notificationHandlers.SendNotification)

	// Prepare request
	requestBody := services.SendNotificationRequest{
		NotificationID: "test-notif-1",
		UserIDs:        []string{user.ID},
		Channels:       []string{"push"},
	}

	// Make request
	recorder := setup.MakeRequest("POST", "/api/notifications/send", requestBody)

	// Assertions
	assert.True(t, recorder.Code == http.StatusOK || recorder.Code == http.StatusCreated,
		"expected 200 or 201 but got %d", recorder.Code)
}
