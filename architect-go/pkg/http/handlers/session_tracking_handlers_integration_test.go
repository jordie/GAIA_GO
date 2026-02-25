package handlers

import (
	"fmt"
	"net/http"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"architect-go/pkg/errors"
	"architect-go/pkg/models"
)

// TestSessionTrackingHandlers_ListSessions tests the ListSessions endpoint
func TestSessionTrackingHandlers_ListSessions(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	session1 := &models.Session{
		ID:     "session-1",
		UserID: user.ID,
	}
	session2 := &models.Session{
		ID:     "session-2",
		UserID: user.ID,
	}
	setup.DB.Create(session1)
	setup.DB.Create(session2)

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	sessionHandlers := NewSessionTrackingHandlers(setup.ServiceRegistry.SessionTrackingService, errHandler)

	// Setup route
	setup.Router.Get("/api/sessions", sessionHandlers.ListSessions)

	// Make request
	recorder := setup.MakeRequest("GET", "/api/sessions?limit=10&offset=0", nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["sessions"])
}

// TestSessionTrackingHandlers_GetSession tests the GetSession endpoint
func TestSessionTrackingHandlers_GetSession(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	session := &models.Session{
		ID:     "session-1",
		UserID: user.ID,
	}
	setup.DB.Create(session)

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	sessionHandlers := NewSessionTrackingHandlers(setup.ServiceRegistry.SessionTrackingService, errHandler)

	// Setup route
	setup.Router.Get("/api/sessions/{id}", sessionHandlers.GetSession)

	// Make request
	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/sessions/%s", session.ID), nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["session"])
}

// TestSessionTrackingHandlers_CreateSession tests creating a session
func TestSessionTrackingHandlers_CreateSession(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	sessionHandlers := NewSessionTrackingHandlers(setup.ServiceRegistry.SessionTrackingService, errHandler)

	// Setup route
	setup.Router.Post("/api/sessions", sessionHandlers.CreateSession)

	// Prepare request
	requestBody := map[string]interface{}{
		"user_id":    user.ID,
		"ip_address": "192.168.1.1",
		"user_agent": "Mozilla/5.0",
	}

	// Make request
	recorder := setup.MakeRequest("POST", "/api/sessions", requestBody)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusCreated)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["session"])
}

// TestSessionTrackingHandlers_ValidateSession tests session validation
func TestSessionTrackingHandlers_ValidateSession(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	session := &models.Session{
		ID:     "session-1",
		UserID: user.ID,
	}
	setup.DB.Create(session)

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	sessionHandlers := NewSessionTrackingHandlers(setup.ServiceRegistry.SessionTrackingService, errHandler)

	// Setup route
	setup.Router.Get("/api/sessions/{id}/validate", sessionHandlers.ValidateSession)

	// Make request
	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/sessions/%s/validate", session.ID), nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["valid"])
}

// TestSessionTrackingHandlers_DestroySession tests destroying a session
func TestSessionTrackingHandlers_DestroySession(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	session := &models.Session{
		ID:     "session-1",
		UserID: user.ID,
	}
	setup.DB.Create(session)

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	sessionHandlers := NewSessionTrackingHandlers(setup.ServiceRegistry.SessionTrackingService, errHandler)

	// Setup route
	setup.Router.Delete("/api/sessions/{id}", sessionHandlers.DestroySession)

	// Make request
	recorder := setup.MakeRequest("DELETE", fmt.Sprintf("/api/sessions/%s", session.ID), nil)

	// Assertions
	assert.True(t, recorder.Code == http.StatusOK || recorder.Code == http.StatusNoContent,
		"expected 200 or 204 but got %d", recorder.Code)
}

// TestSessionTrackingHandlers_GetUserSessions tests getting all sessions for a user
func TestSessionTrackingHandlers_GetUserSessions(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	session1 := &models.Session{
		ID:     "session-1",
		UserID: user.ID,
	}
	session2 := &models.Session{
		ID:     "session-2",
		UserID: user.ID,
	}
	setup.DB.Create(session1)
	setup.DB.Create(session2)

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	sessionHandlers := NewSessionTrackingHandlers(setup.ServiceRegistry.SessionTrackingService, errHandler)

	// Setup route
	setup.Router.Get("/api/sessions/user/{user_id}", sessionHandlers.GetUserSessions)

	// Make request
	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/sessions/user/%s", user.ID), nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["sessions"])
}

// TestSessionTrackingHandlers_GetSessionStats tests session statistics
func TestSessionTrackingHandlers_GetSessionStats(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test data
	user := setup.CreateTestUser("user-1", "Test User", "test@example.com")
	session := &models.Session{
		ID:     "session-1",
		UserID: user.ID,
	}
	setup.DB.Create(session)

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	sessionHandlers := NewSessionTrackingHandlers(setup.ServiceRegistry.SessionTrackingService, errHandler)

	// Setup route
	setup.Router.Get("/api/sessions/stats", sessionHandlers.GetSessionStats)

	// Make request
	recorder := setup.MakeRequest("GET", "/api/sessions/stats", nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["stats"])
}
