package handlers

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"architect-go/pkg/auth"
	"architect-go/pkg/errors"
	"architect-go/pkg/models"
	"architect-go/pkg/services"
)

// TestE2E_UserProjectTaskLifecycle tests the full user-project-task lifecycle
func TestE2E_UserProjectTaskLifecycle(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Setup auth
	pm := auth.NewPasswordManager()
	tm := auth.NewTokenManager("test-secret", 24*time.Hour, "test-issuer")

	// Create a test user with hashed password
	hashedPassword, err := pm.HashPassword("password123")
	require.NoError(t, err)

	user := &models.User{
		ID:           "user1",
		Username:     "testuser",
		Email:        "test@example.com",
		PasswordHash: hashedPassword,
		Status:       "active",
	}
	err = setup.DB.Create(user).Error
	require.NoError(t, err)

	// Create session manager
	sessionMgr := auth.NewSessionManager(
		setup.RepoRegistry.UserRepository,
		setup.RepoRegistry.SessionRepository,
		pm, tm, 24*time.Hour,
	)

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	authHandlers := NewAuthHandlers(sessionMgr, setup.ServiceRegistry.UserService, errHandler)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)

	// Setup routes
	setup.Router.Post("/auth/login", authHandlers.Login)
	setup.Router.Post("/projects", projectHandlers.CreateProject)
	setup.Router.Get("/projects/{id}", projectHandlers.GetProject)
	setup.Router.Post("/tasks", taskHandlers.CreateTask)
	setup.Router.Post("/tasks/{id}/complete", taskHandlers.CompleteTask)
	setup.Router.Get("/projects/{id}/stats", projectHandlers.GetProjectStats)
	setup.Router.Delete("/projects/{id}", projectHandlers.DeleteProject)

	// Step 1: Login
	loginResponse := setup.MakeRequest("POST", "/auth/login", map[string]string{
		"username": "testuser",
		"password": "password123",
	})
	setup.AssertResponseStatus(loginResponse, http.StatusOK)

	var loginData map[string]interface{}
	err = setup.DecodeResponse(loginResponse, &loginData)
	require.NoError(t, err)

	token := loginData["token"].(string)
	assert.NotEmpty(t, token)

	// Step 2: Create project
	projectRequest := setup.MakeRequest("POST", "/projects", services.CreateProjectRequest{
		Name:        "E2E Test Project",
		Description: "Test Project for E2E",
	})
	setup.AssertResponseStatus(projectRequest, http.StatusCreated)

	var projectData map[string]interface{}
	err = setup.DecodeResponse(projectRequest, &projectData)
	require.NoError(t, err)

	projectID := projectData["id"].(string)
	assert.NotEmpty(t, projectID)

	// Step 3: Create task
	taskRequest := setup.MakeRequest("POST", "/tasks", services.CreateTaskRequest{
		ProjectID:   projectID,
		Title:       "E2E Test Task",
		Description: "Test task for E2E",
	})
	setup.AssertResponseStatus(taskRequest, http.StatusCreated)

	var taskData map[string]interface{}
	err = setup.DecodeResponse(taskRequest, &taskData)
	require.NoError(t, err)

	taskID := taskData["id"].(string)
	assert.NotEmpty(t, taskID)

	// Step 4: Complete task
	completeRequest := setup.MakeRequest("POST", fmt.Sprintf("/tasks/%s/complete", taskID), nil)
	setup.AssertResponseStatus(completeRequest, http.StatusOK)

	var completeData map[string]interface{}
	err = setup.DecodeResponse(completeRequest, &completeData)
	require.NoError(t, err)

	assert.Equal(t, "completed", completeData["status"])

	// Step 5: Get project stats
	statsRequest := setup.MakeRequest("GET", fmt.Sprintf("/projects/%s/stats", projectID), nil)
	setup.AssertResponseStatus(statsRequest, http.StatusOK)

	var statsData map[string]interface{}
	err = setup.DecodeResponse(statsRequest, &statsData)
	require.NoError(t, err)

	assert.NotNil(t, statsData)

	// Step 6: Delete project
	deleteRequest := setup.MakeRequest("DELETE", fmt.Sprintf("/projects/%s", projectID), nil)
	assert.True(t, deleteRequest.Code == http.StatusOK || deleteRequest.Code == http.StatusNoContent,
		"expected 200 or 204 but got %d", deleteRequest.Code)

	// Step 7: Verify project is deleted
	getRequest := setup.MakeRequest("GET", fmt.Sprintf("/projects/%s", projectID), nil)
	assert.Equal(t, http.StatusNotFound, getRequest.Code)
}

// TestE2E_AuthSessionLifecycle tests the full authentication session lifecycle
func TestE2E_AuthSessionLifecycle(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Setup auth
	pm := auth.NewPasswordManager()
	tm := auth.NewTokenManager("test-secret", 24*time.Hour, "test-issuer")

	// Create a test user
	hashedPassword, err := pm.HashPassword("password123")
	require.NoError(t, err)

	user := &models.User{
		ID:           "user1",
		Username:     "testuser",
		Email:        "test@example.com",
		PasswordHash: hashedPassword,
		Status:       "active",
	}
	err = setup.DB.Create(user).Error
	require.NoError(t, err)

	// Create session manager
	sessionMgr := auth.NewSessionManager(
		setup.RepoRegistry.UserRepository,
		setup.RepoRegistry.SessionRepository,
		pm, tm, 24*time.Hour,
	)

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	authHandlers := NewAuthHandlers(sessionMgr, setup.ServiceRegistry.UserService, errHandler)

	// Setup routes
	setup.Router.Post("/auth/login", authHandlers.Login)
	setup.Router.Get("/auth/verify", authHandlers.Verify)
	setup.Router.Post("/auth/logout", authHandlers.Logout)

	// Step 1: Login
	loginResponse := setup.MakeRequest("POST", "/auth/login", map[string]string{
		"username": "testuser",
		"password": "password123",
	})
	setup.AssertResponseStatus(loginResponse, http.StatusOK)

	var loginData map[string]interface{}
	err = setup.DecodeResponse(loginResponse, &loginData)
	require.NoError(t, err)

	token := loginData["token"].(string)
	assert.NotEmpty(t, token)
	assert.Equal(t, "user1", loginData["user_id"])

	// Step 2: Verify token is valid
	verifyReq := httptest.NewRequest("GET", "/auth/verify", nil)
	verifyReq.Header.Set("Authorization", fmt.Sprintf("Bearer %s", token))
	verifyReq.Header.Set("X-Request-ID", "test-request-id")
	verifyRequest := httptest.NewRecorder()
	setup.Router.ServeHTTP(verifyRequest, verifyReq)
	setup.AssertResponseStatus(verifyRequest, http.StatusOK)

	var verifyData map[string]interface{}
	err = setup.DecodeResponse(verifyRequest, &verifyData)
	require.NoError(t, err)

	assert.Equal(t, "user1", verifyData["user_id"])
	assert.Equal(t, "testuser", verifyData["username"])

	// Step 3: Logout
	logoutReq := httptest.NewRequest("POST", "/auth/logout", nil)
	logoutReq.Header.Set("Authorization", fmt.Sprintf("Bearer %s", token))
	logoutReq.Header.Set("X-Request-ID", "test-request-id")
	logoutRequest := httptest.NewRecorder()
	setup.Router.ServeHTTP(logoutRequest, logoutReq)
	assert.Equal(t, http.StatusNoContent, logoutRequest.Code)

	// Step 4: Verify token is now invalid
	verifyAfterLogoutReq := httptest.NewRequest("GET", "/auth/verify", nil)
	verifyAfterLogoutReq.Header.Set("Authorization", fmt.Sprintf("Bearer %s", token))
	verifyAfterLogoutReq.Header.Set("X-Request-ID", "test-request-id")
	verifyAfterLogout := httptest.NewRecorder()
	setup.Router.ServeHTTP(verifyAfterLogout, verifyAfterLogoutReq)
	assert.Equal(t, http.StatusUnauthorized, verifyAfterLogout.Code)
}

// TestE2E_UserCRUDCycle tests user creation, update, password change, and deletion
func TestE2E_UserCRUDCycle(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	// Setup routes
	setup.Router.Post("/users", userHandlers.CreateUser)
	setup.Router.Get("/users/{id}", userHandlers.GetUser)
	setup.Router.Put("/users/{id}", userHandlers.UpdateUser)
	setup.Router.Delete("/users/{id}", userHandlers.DeleteUser)

	// Step 1: Create user
	createRequest := setup.MakeRequest("POST", "/users", services.CreateUserRequest{
		Username: "newuser",
		Email:    "newuser@example.com",
		Password: "password123",
	})
	setup.AssertResponseStatus(createRequest, http.StatusCreated)

	var createData map[string]interface{}
	err := setup.DecodeResponse(createRequest, &createData)
	require.NoError(t, err)

	userID := createData["id"].(string)
	assert.NotEmpty(t, userID)
	assert.Equal(t, "newuser", createData["username"])

	// Step 2: Get user
	getRequest := setup.MakeRequest("GET", fmt.Sprintf("/users/%s", userID), nil)
	setup.AssertResponseStatus(getRequest, http.StatusOK)

	var getData map[string]interface{}
	err = setup.DecodeResponse(getRequest, &getData)
	require.NoError(t, err)

	assert.Equal(t, "newuser", getData["username"])
	assert.Equal(t, "newuser@example.com", getData["email"])

	// Step 3: Update user
	updateRequest := setup.MakeRequest("PUT", fmt.Sprintf("/users/%s", userID), services.UpdateUserRequest{
		FullName: "Updated User",
		Email:    "updated@example.com",
	})
	setup.AssertResponseStatus(updateRequest, http.StatusOK)

	var updateData map[string]interface{}
	err = setup.DecodeResponse(updateRequest, &updateData)
	require.NoError(t, err)

	assert.Equal(t, "Updated User", updateData["full_name"])
	assert.Equal(t, "updated@example.com", updateData["email"])

	// Step 4: Verify update persisted
	verifyRequest := setup.MakeRequest("GET", fmt.Sprintf("/users/%s", userID), nil)
	setup.AssertResponseStatus(verifyRequest, http.StatusOK)

	var verifyData map[string]interface{}
	err = setup.DecodeResponse(verifyRequest, &verifyData)
	require.NoError(t, err)

	assert.Equal(t, "Updated User", verifyData["full_name"])

	// Step 5: Delete user
	deleteRequest := setup.MakeRequest("DELETE", fmt.Sprintf("/users/%s", userID), nil)
	assert.True(t, deleteRequest.Code == http.StatusOK || deleteRequest.Code == http.StatusNoContent,
		"expected 200 or 204 but got %d", deleteRequest.Code)

	// Step 6: Verify user is deleted
	getAfterDelete := setup.MakeRequest("GET", fmt.Sprintf("/users/%s", userID), nil)
	assert.Equal(t, http.StatusNotFound, getAfterDelete.Code)
}

// TestE2E_MultiProjectWithMultipleTasks tests managing multiple projects with multiple tasks
func TestE2E_MultiProjectWithMultipleTasks(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)

	// Setup routes
	setup.Router.Post("/projects", projectHandlers.CreateProject)
	setup.Router.Get("/projects/{id}", projectHandlers.GetProject)
	setup.Router.Post("/tasks", taskHandlers.CreateTask)
	setup.Router.Get("/tasks/{id}", taskHandlers.GetTask)
	setup.Router.Get("/projects/{id}/stats", projectHandlers.GetProjectStats)

	// Step 1: Create multiple projects
	projectIDs := make([]string, 3)
	for i := 0; i < 3; i++ {
		projectRequest := setup.MakeRequest("POST", "/projects", services.CreateProjectRequest{
			Name:        fmt.Sprintf("Project %d", i+1),
			Description: fmt.Sprintf("Description for Project %d", i+1),
		})
		setup.AssertResponseStatus(projectRequest, http.StatusCreated)

		var projectData map[string]interface{}
		err := setup.DecodeResponse(projectRequest, &projectData)
		require.NoError(t, err)

		projectIDs[i] = projectData["id"].(string)
	}

	// Step 2: Create multiple tasks for each project
	taskCount := 0
	for _, projectID := range projectIDs {
		for j := 0; j < 2; j++ {
			taskRequest := setup.MakeRequest("POST", "/tasks", services.CreateTaskRequest{
				ProjectID:   projectID,
				Title:       fmt.Sprintf("Task %d for Project", j+1),
				Description: fmt.Sprintf("Task description"),
			})
			setup.AssertResponseStatus(taskRequest, http.StatusCreated)

			var taskData map[string]interface{}
			err := setup.DecodeResponse(taskRequest, &taskData)
			require.NoError(t, err)

			taskCount++
		}
	}

	assert.Equal(t, 6, taskCount, "should have created 6 tasks (2 per project, 3 projects)")

	// Step 3: Verify stats for first project
	statsRequest := setup.MakeRequest("GET", fmt.Sprintf("/projects/%s/stats", projectIDs[0]), nil)
	setup.AssertResponseStatus(statsRequest, http.StatusOK)

	var statsData map[string]interface{}
	err := setup.DecodeResponse(statsRequest, &statsData)
	require.NoError(t, err)

	assert.NotNil(t, statsData)
}
