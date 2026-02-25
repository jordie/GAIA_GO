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

// TestUserHandlers_ListUsers tests the ListUsers endpoint
func TestUserHandlers_ListUsers(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test users
	setup.CreateTestUser("user1", "alice", "alice@example.com")
	setup.CreateTestUser("user2", "bob", "bob@example.com")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	// Setup route
	setup.Router.Get("/api/users", userHandlers.ListUsers)

	// Make request
	recorder := setup.MakeRequest("GET", "/api/users?limit=10&offset=0", nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["users"])
	assert.Equal(t, float64(2), response["total"])
}

// TestUserHandlers_GetUser tests the GetUser endpoint
func TestUserHandlers_GetUser(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test user
	user := setup.CreateTestUser("user1", "alice", "alice@example.com")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	// Setup route
	setup.Router.Get("/api/users/{id}", userHandlers.GetUser)

	// Make request
	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/users/%s", user.ID), nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.Equal(t, "alice", response["username"])
	assert.Equal(t, "alice@example.com", response["email"])
}

// TestUserHandlers_GetUser_NotFound tests GetUser with non-existent user
func TestUserHandlers_GetUser_NotFound(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	// Setup route
	setup.Router.Get("/api/users/{id}", userHandlers.GetUser)

	// Make request for non-existent user
	recorder := setup.MakeRequest("GET", "/api/users/nonexistent", nil)

	// Assertions
	assert.Equal(t, http.StatusNotFound, recorder.Code)
}

// TestUserHandlers_CreateUser tests the CreateUser endpoint
func TestUserHandlers_CreateUser(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	// Setup route
	setup.Router.Post("/api/users", userHandlers.CreateUser)

	// Prepare request
	requestBody := services.CreateUserRequest{
		Username: "newuser",
		Email:    "newuser@example.com",
		Password: "password123",
	}

	// Make request
	recorder := setup.MakeRequest("POST", "/api/users", requestBody)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusCreated)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotEmpty(t, response["id"])
	assert.Equal(t, "newuser", response["username"])
}

// TestUserHandlers_CreateUser_Duplicate tests CreateUser with duplicate username
func TestUserHandlers_CreateUser_Duplicate(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create existing user
	setup.CreateTestUser("user1", "alice", "alice@example.com")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	// Setup route
	setup.Router.Post("/api/users", userHandlers.CreateUser)

	// Prepare request with duplicate username
	requestBody := services.CreateUserRequest{
		Username: "alice",
		Email:    "different@example.com",
		Password: "password123",
	}

	// Make request
	recorder := setup.MakeRequest("POST", "/api/users", requestBody)

	// Assertions - should return error (may be 400, 409, or 500)
	assert.True(t, recorder.Code >= 400 && recorder.Code < 600,
		"expected 4xx or 5xx but got %d", recorder.Code)
}

// TestUserHandlers_UpdateUser tests the UpdateUser endpoint
func TestUserHandlers_UpdateUser(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test user
	user := setup.CreateTestUser("user1", "alice", "alice@example.com")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	// Setup route
	setup.Router.Put("/api/users/{id}", userHandlers.UpdateUser)

	// Prepare request
	requestBody := services.UpdateUserRequest{
		FullName: "Alice Updated",
		Email:    "alice_updated@example.com",
	}

	// Make request
	recorder := setup.MakeRequest("PUT", fmt.Sprintf("/api/users/%s", user.ID), requestBody)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.Equal(t, "Alice Updated", response["full_name"])
}

// TestUserHandlers_DeleteUser tests the DeleteUser endpoint
func TestUserHandlers_DeleteUser(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create test user
	user := setup.CreateTestUser("user1", "alice", "alice@example.com")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	// Setup route
	setup.Router.Delete("/api/users/{id}", userHandlers.DeleteUser)

	// Make request
	recorder := setup.MakeRequest("DELETE", fmt.Sprintf("/api/users/%s", user.ID), nil)

	// Assertions
	assert.True(t, recorder.Code == http.StatusOK || recorder.Code == http.StatusNoContent,
		"expected 200 or 204 but got %d", recorder.Code)
}
