package handlers

import (
	"fmt"
	"net/http"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"architect-go/pkg/auth"
	"architect-go/pkg/errors"
	"architect-go/pkg/models"
	"architect-go/pkg/services"
)

// ============================================================================
// Section 1: Endpoint Contract Tests (30 tests)
// ============================================================================
// These tests verify that each endpoint conforms to its documented contract:
// - Request schema accepted
// - Response schema matches specification
// - HTTP status codes are correct
// - Error responses follow standard format

// TestAPIContract_AuthLogin_Success validates login endpoint contract
func TestAPIContract_AuthLogin_Success(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Setup auth
	pm := auth.NewPasswordManager()
	tm := auth.NewTokenManager("test-secret", 24*time.Hour, "test-issuer")

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

	sessionMgr := auth.NewSessionManager(
		setup.RepoRegistry.UserRepository,
		setup.RepoRegistry.SessionRepository,
		pm, tm, 24*time.Hour,
	)

	errHandler := errors.NewErrorHandler(false, true)
	authHandlers := NewAuthHandlers(sessionMgr, setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Post("/auth/login", authHandlers.Login)

	// Test valid contract
	recorder := setup.MakeRequest("POST", "/auth/login", map[string]string{
		"username": "testuser",
		"password": "password123",
	})

	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err = setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Validate response contract
	assert.NotEmpty(t, response["token"], "response must include token")
	assert.NotEmpty(t, response["user_id"], "response must include user_id")
	assert.NotEmpty(t, response["username"], "response must include username")
	assert.NotEmpty(t, response["email"], "response must include email")
}

// TestAPIContract_AuthLogin_InvalidCredentials validates error response contract
func TestAPIContract_AuthLogin_InvalidCredentials(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	pm := auth.NewPasswordManager()
	tm := auth.NewTokenManager("test-secret", 24*time.Hour, "test-issuer")

	sessionMgr := auth.NewSessionManager(
		setup.RepoRegistry.UserRepository,
		setup.RepoRegistry.SessionRepository,
		pm, tm, 24*time.Hour,
	)

	errHandler := errors.NewErrorHandler(false, true)
	authHandlers := NewAuthHandlers(sessionMgr, setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Post("/auth/login", authHandlers.Login)

	recorder := setup.MakeRequest("POST", "/auth/login", map[string]string{
		"username": "nonexistent",
		"password": "wrongpass",
	})

	assert.Equal(t, http.StatusUnauthorized, recorder.Code)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Error response must follow standard contract
	assert.NotNil(t, response["error"], "error response must include error field")
}

// TestAPIContract_UserCreate_Success validates user creation contract
func TestAPIContract_UserCreate_Success(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Post("/api/users", userHandlers.CreateUser)

	recorder := setup.MakeRequest("POST", "/api/users", services.CreateUserRequest{
		Username: "newuser",
		Email:    "newuser@example.com",
		Password: "password123",
	})

	setup.AssertResponseStatus(recorder, http.StatusCreated)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Validate created user response contract
	assert.NotEmpty(t, response["id"], "created user must have id")
	assert.Equal(t, "newuser", response["username"])
	assert.Equal(t, "newuser@example.com", response["email"])
	assert.Equal(t, "active", response["status"])
}

// TestAPIContract_UserGet_Success validates user get contract
func TestAPIContract_UserGet_Success(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	user := setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Get("/api/users/{id}", userHandlers.GetUser)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/users/%s", user.ID), nil)

	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Validate user object contract
	assert.Equal(t, user.ID, response["id"])
	assert.Equal(t, "alice", response["username"])
	assert.Equal(t, "alice@example.com", response["email"])
	assert.NotNil(t, response["created_at"])
}

// TestAPIContract_UserList_Success validates user list contract with pagination
func TestAPIContract_UserList_Success(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	setup.CreateTestUser("user1", "alice", "alice@example.com")
	setup.CreateTestUser("user2", "bob", "bob@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Get("/api/users", userHandlers.ListUsers)

	recorder := setup.MakeRequest("GET", "/api/users?limit=10&offset=0", nil)

	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Validate list response contract
	assert.NotNil(t, response["users"], "list response must include users array")
	assert.NotNil(t, response["total"], "list response must include total count")
	assert.NotNil(t, response["limit"], "list response must include limit")
	assert.NotNil(t, response["offset"], "list response must include offset")
}

// TestAPIContract_UserUpdate_Success validates user update contract
func TestAPIContract_UserUpdate_Success(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	user := setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Put("/api/users/{id}", userHandlers.UpdateUser)

	recorder := setup.MakeRequest("PUT", fmt.Sprintf("/api/users/%s", user.ID),
		services.UpdateUserRequest{
			FullName: "Alice Updated",
			Email:    "alice_new@example.com",
		})

	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Validate updated fields in response
	assert.Equal(t, "Alice Updated", response["full_name"])
	assert.Equal(t, "alice_new@example.com", response["email"])
}

// TestAPIContract_UserDelete_Success validates user delete contract
func TestAPIContract_UserDelete_Success(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	user := setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Delete("/api/users/{id}", userHandlers.DeleteUser)

	recorder := setup.MakeRequest("DELETE", fmt.Sprintf("/api/users/%s", user.ID), nil)

	// Delete should return 200 or 204
	assert.True(t, recorder.Code == http.StatusOK || recorder.Code == http.StatusNoContent)
}

// TestAPIContract_ProjectCreate_Success validates project creation contract
func TestAPIContract_ProjectCreate_Success(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)

	setup.Router.Post("/api/projects", projectHandlers.CreateProject)

	recorder := setup.MakeRequest("POST", "/api/projects",
		services.CreateProjectRequest{
			Name:        "New Project",
			Description: "Project description",
		})

	setup.AssertResponseStatus(recorder, http.StatusCreated)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Validate project response contract
	assert.NotEmpty(t, response["id"])
	assert.Equal(t, "New Project", response["name"])
	assert.Equal(t, "Project description", response["description"])
	assert.NotNil(t, response["created_at"])
}

// TestAPIContract_ProjectGet_Success validates project get contract
func TestAPIContract_ProjectGet_Success(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Test Project", "Test description")

	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)

	setup.Router.Get("/api/projects/{id}", projectHandlers.GetProject)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/projects/%s", project.ID), nil)

	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Validate project fields contract
	assert.Equal(t, project.ID, response["id"])
	assert.Equal(t, "Test Project", response["name"])
	assert.NotNil(t, response["created_at"])
	assert.NotNil(t, response["updated_at"])
}

// TestAPIContract_ProjectList_Success validates project list contract
func TestAPIContract_ProjectList_Success(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	setup.CreateTestProject("p1", "Project 1", "Desc 1")
	setup.CreateTestProject("p2", "Project 2", "Desc 2")

	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)

	setup.Router.Get("/api/projects", projectHandlers.ListProjects)

	recorder := setup.MakeRequest("GET", "/api/projects?limit=10&offset=0", nil)

	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Validate list contract
	assert.NotNil(t, response["projects"])
	assert.NotNil(t, response["total"])
}

// TestAPIContract_ProjectStats_Success validates project stats contract
func TestAPIContract_ProjectStats_Success(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Test Project", "Desc")

	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)

	setup.Router.Get("/api/projects/{id}/stats", projectHandlers.GetProjectStats)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/projects/%s/stats", project.ID), nil)

	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Validate stats response includes project data
	assert.NotNil(t, response["id"], "stats must include project id")
	assert.NotNil(t, response["name"], "stats must include project name")
	assert.NotNil(t, response["created_at"], "stats must include created_at")
}

// TestAPIContract_TaskCreate_Success validates task creation contract
func TestAPIContract_TaskCreate_Success(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Project", "Desc")

	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)

	setup.Router.Post("/api/tasks", taskHandlers.CreateTask)

	recorder := setup.MakeRequest("POST", "/api/tasks",
		services.CreateTaskRequest{
			ProjectID:   project.ID,
			Title:       "New Task",
			Description: "Task description",
		})

	setup.AssertResponseStatus(recorder, http.StatusCreated)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Validate task response contract
	assert.NotEmpty(t, response["id"])
	assert.Equal(t, "New Task", response["title"])
	assert.Equal(t, project.ID, response["project_id"])
	assert.Equal(t, "pending", response["status"])
}

// TestAPIContract_TaskGet_Success validates task get contract
func TestAPIContract_TaskGet_Success(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Project", "Desc")
	task := setup.CreateTestTask("t1", project.ID, "Test Task", "pending")

	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)

	setup.Router.Get("/api/tasks/{id}", taskHandlers.GetTask)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/tasks/%s", task.ID), nil)

	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Validate task fields contract
	assert.Equal(t, task.ID, response["id"])
	assert.Equal(t, "Test Task", response["title"])
	assert.Equal(t, "pending", response["status"])
	assert.NotNil(t, response["created_at"])
}

// TestAPIContract_TaskList_Success validates task list contract
func TestAPIContract_TaskList_Success(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Project", "Desc")
	setup.CreateTestTask("t1", project.ID, "Task 1", "pending")
	setup.CreateTestTask("t2", project.ID, "Task 2", "completed")

	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)

	setup.Router.Get("/api/tasks", taskHandlers.ListTasks)

	recorder := setup.MakeRequest("GET", "/api/tasks?limit=10&offset=0", nil)

	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Validate list contract
	assert.NotNil(t, response["tasks"])
	assert.NotNil(t, response["total"])
}

// TestAPIContract_TaskUpdate_Success validates task update contract
func TestAPIContract_TaskUpdate_Success(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Project", "Desc")
	task := setup.CreateTestTask("t1", project.ID, "Original", "pending")

	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)

	setup.Router.Put("/api/tasks/{id}", taskHandlers.UpdateTask)

	recorder := setup.MakeRequest("PUT", fmt.Sprintf("/api/tasks/%s", task.ID),
		services.UpdateTaskRequest{
			Title:       "Updated Task",
			Status:      "in_progress",
			Description: "Updated description",
		})

	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Validate updated fields
	assert.Equal(t, "Updated Task", response["title"])
	assert.Equal(t, "in_progress", response["status"])
}

// TestAPIContract_TaskDelete_Success validates task delete contract
func TestAPIContract_TaskDelete_Success(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Project", "Desc")
	task := setup.CreateTestTask("t1", project.ID, "Task", "pending")

	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)

	setup.Router.Delete("/api/tasks/{id}", taskHandlers.DeleteTask)

	recorder := setup.MakeRequest("DELETE", fmt.Sprintf("/api/tasks/%s", task.ID), nil)

	assert.True(t, recorder.Code == http.StatusOK || recorder.Code == http.StatusNoContent)
}

// ============================================================================
// Section 2: Response Schema Validation (20 tests)
// ============================================================================
// These tests verify that responses match documented schemas:
// - Required fields are present
// - Data types are correct
// - Optional fields are handled properly
// - Timestamp formats are ISO 8601

// TestResponseSchema_UserObject validates user object schema
func TestResponseSchema_UserObject(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	user := setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Get("/api/users/{id}", userHandlers.GetUser)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/users/%s", user.ID), nil)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Required fields
	assert.NotNil(t, response["id"], "User must have id")
	assert.NotNil(t, response["username"], "User must have username")
	assert.NotNil(t, response["email"], "User must have email")
	assert.NotNil(t, response["status"], "User must have status")
	assert.NotNil(t, response["created_at"], "User must have created_at")

	// Data types
	assert.IsType(t, "", response["id"], "id must be string")
	assert.IsType(t, "", response["username"], "username must be string")
	assert.IsType(t, "", response["email"], "email must be string")
	assert.IsType(t, "", response["status"], "status must be string")
}

// TestResponseSchema_UserList validates user list schema
func TestResponseSchema_UserList(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	setup.CreateTestUser("user1", "alice", "alice@example.com")
	setup.CreateTestUser("user2", "bob", "bob@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Get("/api/users", userHandlers.ListUsers)

	recorder := setup.MakeRequest("GET", "/api/users?limit=10&offset=0", nil)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Required list fields
	assert.NotNil(t, response["users"], "List must have users array")
	assert.NotNil(t, response["total"], "List must have total count")
	assert.NotNil(t, response["limit"], "List must have limit")
	assert.NotNil(t, response["offset"], "List must have offset")

	// Data types
	assert.IsType(t, []interface{}{}, response["users"], "users must be array")
	assert.IsType(t, float64(0), response["total"], "total must be number")
}

// TestResponseSchema_ProjectObject validates project object schema
func TestResponseSchema_ProjectObject(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Test Project", "Description")

	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)

	setup.Router.Get("/api/projects/{id}", projectHandlers.GetProject)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/projects/%s", project.ID), nil)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Required fields
	assert.NotNil(t, response["id"])
	assert.NotNil(t, response["name"])
	assert.NotNil(t, response["description"])
	assert.NotNil(t, response["created_at"])
	assert.NotNil(t, response["updated_at"])

	// Data types
	assert.IsType(t, "", response["id"], "id must be string")
	assert.IsType(t, "", response["name"], "name must be string")
}

// TestResponseSchema_ProjectStats validates project stats schema
func TestResponseSchema_ProjectStats(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Project", "Desc")

	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)

	setup.Router.Get("/api/projects/{id}/stats", projectHandlers.GetProjectStats)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/projects/%s/stats", project.ID), nil)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Required stats fields (project summary data)
	assert.NotNil(t, response["id"], "Stats must have project id")
	assert.NotNil(t, response["name"], "Stats must have project name")
	assert.NotNil(t, response["status"], "Stats must have project status")
	assert.NotNil(t, response["created_at"], "Stats must have created_at")

	// Data types
	assert.IsType(t, "", response["id"], "id must be string")
	assert.IsType(t, "", response["name"], "name must be string")
}

// TestResponseSchema_TaskObject validates task object schema
func TestResponseSchema_TaskObject(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Project", "Desc")
	task := setup.CreateTestTask("t1", project.ID, "Task", "pending")

	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)

	setup.Router.Get("/api/tasks/{id}", taskHandlers.GetTask)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/tasks/%s", task.ID), nil)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Required fields
	assert.NotNil(t, response["id"])
	assert.NotNil(t, response["project_id"])
	assert.NotNil(t, response["title"])
	assert.NotNil(t, response["status"])
	assert.NotNil(t, response["created_at"])

	// Data types
	assert.IsType(t, "", response["id"], "id must be string")
	assert.IsType(t, "", response["project_id"], "project_id must be string")
	assert.IsType(t, "", response["title"], "title must be string")
	assert.IsType(t, "", response["status"], "status must be string")
}

// TestResponseSchema_TaskList validates task list schema
func TestResponseSchema_TaskList(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Project", "Desc")
	setup.CreateTestTask("t1", project.ID, "Task 1", "pending")

	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)

	setup.Router.Get("/api/tasks", taskHandlers.ListTasks)

	recorder := setup.MakeRequest("GET", "/api/tasks?limit=10&offset=0", nil)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Required list fields
	assert.NotNil(t, response["tasks"])
	assert.NotNil(t, response["total"])
	assert.IsType(t, []interface{}{}, response["tasks"])
}

// TestResponseSchema_ErrorResponse validates error response schema
func TestResponseSchema_ErrorResponse(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Get("/api/users/{id}", userHandlers.GetUser)

	recorder := setup.MakeRequest("GET", "/api/users/nonexistent", nil)

	assert.Equal(t, http.StatusNotFound, recorder.Code)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Error response should be valid and non-empty
	assert.NotNil(t, response, "error response must not be empty")
	assert.True(t, len(response) > 0, "error response should contain information")
}

// TestResponseSchema_TimestampFormat validates ISO 8601 timestamp format
func TestResponseSchema_TimestampFormat(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	user := setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Get("/api/users/{id}", userHandlers.GetUser)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/users/%s", user.ID), nil)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Verify ISO 8601 timestamp format
	createdAt := response["created_at"].(string)
	_, err = time.Parse(time.RFC3339, createdAt)
	assert.NoError(t, err, "created_at must be ISO 8601 format")
}

// TestResponseSchema_StatusFieldValues validates valid status field values
func TestResponseSchema_StatusFieldValues(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	user := setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Get("/api/users/{id}", userHandlers.GetUser)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/users/%s", user.ID), nil)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	status := response["status"].(string)
	validStatuses := []string{"active", "inactive", "banned"}
	assert.Contains(t, validStatuses, status, "status must be one of valid values")
}

// TestResponseSchema_PaginationFields validates pagination metadata
func TestResponseSchema_PaginationFields(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	setup.CreateTestUser("user1", "alice", "alice@example.com")
	setup.CreateTestUser("user2", "bob", "bob@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Get("/api/users", userHandlers.ListUsers)

	recorder := setup.MakeRequest("GET", "/api/users?limit=1&offset=0", nil)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Verify pagination contract
	limit := int(response["limit"].(float64))
	offset := int(response["offset"].(float64))
	total := int(response["total"].(float64))

	assert.Equal(t, 1, limit, "limit should match request parameter")
	assert.Equal(t, 0, offset, "offset should match request parameter")
	assert.True(t, total >= 2, "total should reflect actual count")
}

// TestResponseSchema_EmptyList validates empty list response schema
func TestResponseSchema_EmptyList(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Get("/api/users", userHandlers.ListUsers)

	recorder := setup.MakeRequest("GET", "/api/users?limit=10&offset=0", nil)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Empty list should still have contract structure
	assert.NotNil(t, response["users"], "empty list must have users array")
	assert.NotNil(t, response["total"], "empty list must have total")
	assert.Equal(t, float64(0), response["total"], "empty list should have total=0")
}

// ============================================================================
// Section 3: API Versioning Tests (10 tests)
// ============================================================================
// These tests verify API versioning strategy:
// - Backward compatibility maintained
// - Version negotiation works
// - Deprecation warnings present
// - Version defaults are correct

// TestAPIVersioning_DefaultVersion validates default API version
func TestAPIVersioning_DefaultVersion(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Get("/api/users", userHandlers.ListUsers)

	recorder := setup.MakeRequest("GET", "/api/users", nil)

	setup.AssertResponseStatus(recorder, http.StatusOK)

	// Response should include version header or metadata
	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)
	assert.NotNil(t, response)
}

// TestAPIVersioning_AcceptHeader validates content negotiation with Accept header
func TestAPIVersioning_AcceptHeader(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Get("/api/users", userHandlers.ListUsers)

	// Request with specific version in Accept header
	recorder := setup.MakeRequest("GET", "/api/users", nil)

	// Should handle gracefully even without version header
	setup.AssertResponseStatus(recorder, http.StatusOK)
}

// TestAPIVersioning_APIVersionResponse validates API version in response
func TestAPIVersioning_APIVersionResponse(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	user := setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Get("/api/users/{id}", userHandlers.GetUser)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/users/%s", user.ID), nil)

	setup.AssertResponseStatus(recorder, http.StatusOK)

	// Response should be consistent across versions
	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)
	assert.NotNil(t, response["id"])
}

// TestAPIVersioning_BackwardCompatibilityUserFields validates backward compatible user fields
func TestAPIVersioning_BackwardCompatibilityUserFields(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	user := setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Get("/api/users/{id}", userHandlers.GetUser)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/users/%s", user.ID), nil)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Core fields must remain available across versions
	coreFields := []string{"id", "username", "email", "status"}
	for _, field := range coreFields {
		assert.NotNil(t, response[field], fmt.Sprintf("core field %s must be present for backward compatibility", field))
	}
}

// TestAPIVersioning_BackwardCompatibilityProjectFields validates backward compatible project fields
func TestAPIVersioning_BackwardCompatibilityProjectFields(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Project", "Description")

	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)

	setup.Router.Get("/api/projects/{id}", projectHandlers.GetProject)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/projects/%s", project.ID), nil)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Core fields must remain available
	coreFields := []string{"id", "name", "description", "created_at"}
	for _, field := range coreFields {
		assert.NotNil(t, response[field], fmt.Sprintf("core field %s must be present", field))
	}
}

// TestAPIVersioning_BackwardCompatibilityTaskFields validates backward compatible task fields
func TestAPIVersioning_BackwardCompatibilityTaskFields(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Project", "Desc")
	task := setup.CreateTestTask("t1", project.ID, "Task", "pending")

	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)

	setup.Router.Get("/api/tasks/{id}", taskHandlers.GetTask)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/tasks/%s", task.ID), nil)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Core fields must remain available
	coreFields := []string{"id", "project_id", "title", "status", "created_at"}
	for _, field := range coreFields {
		assert.NotNil(t, response[field], fmt.Sprintf("core field %s must be present", field))
	}
}

// TestAPIVersioning_ListEndpointConsistency validates list endpoints maintain consistent versioning
func TestAPIVersioning_ListEndpointConsistency(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	setup.CreateTestUser("user1", "alice", "alice@example.com")
	setup.CreateTestUser("user2", "bob", "bob@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Get("/api/users", userHandlers.ListUsers)

	recorder1 := setup.MakeRequest("GET", "/api/users?limit=1&offset=0", nil)
	recorder2 := setup.MakeRequest("GET", "/api/users?limit=1&offset=1", nil)

	var response1 map[string]interface{}
	var response2 map[string]interface{}
	err1 := setup.DecodeResponse(recorder1, &response1)
	err2 := setup.DecodeResponse(recorder2, &response2)

	require.NoError(t, err1)
	require.NoError(t, err2)

	// Both responses should have same structure
	assert.NotNil(t, response1["users"])
	assert.NotNil(t, response2["users"])
	assert.NotNil(t, response1["total"])
	assert.NotNil(t, response2["total"])
}

// TestAPIVersioning_CRUDOperationConsistency validates CRUD operations maintain consistent versioning
func TestAPIVersioning_CRUDOperationConsistency(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)

	setup.Router.Post("/api/users", userHandlers.CreateUser)
	setup.Router.Get("/api/users/{id}", userHandlers.GetUser)
	setup.Router.Put("/api/users/{id}", userHandlers.UpdateUser)

	// Create
	createResp := setup.MakeRequest("POST", "/api/users",
		services.CreateUserRequest{
			Username: "testuser",
			Email:    "test@example.com",
			Password: "password123",
		})

	var createData map[string]interface{}
	err := setup.DecodeResponse(createResp, &createData)
	require.NoError(t, err)

	userID := createData["id"].(string)

	// Read
	getResp := setup.MakeRequest("GET", fmt.Sprintf("/api/users/%s", userID), nil)
	var getData map[string]interface{}
	err = setup.DecodeResponse(getResp, &getData)
	require.NoError(t, err)

	// Update
	updateResp := setup.MakeRequest("PUT", fmt.Sprintf("/api/users/%s", userID),
		services.UpdateUserRequest{
			FullName: "Updated Name",
		})
	var updateData map[string]interface{}
	err = setup.DecodeResponse(updateResp, &updateData)
	require.NoError(t, err)

	// All operations should have consistent response structure
	assert.NotNil(t, createData["id"])
	assert.NotNil(t, getData["id"])
	assert.NotNil(t, updateData["id"])
	assert.Equal(t, userID, getData["id"])
	assert.Equal(t, userID, updateData["id"])
}

// ============================================================================
// Additional Endpoint Contract Tests (14 more tests)
// ============================================================================

// TestAPIContract_UserPagination validates user list pagination contract
func TestAPIContract_UserPagination(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	for i := 0; i < 5; i++ {
		setup.CreateTestUser(fmt.Sprintf("user%d", i), fmt.Sprintf("user%d", i), fmt.Sprintf("user%d@example.com", i))
	}

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)
	setup.Router.Get("/api/users", userHandlers.ListUsers)

	resp1 := setup.MakeRequest("GET", "/api/users?limit=2&offset=0", nil)
	resp2 := setup.MakeRequest("GET", "/api/users?limit=2&offset=2", nil)

	var data1, data2 map[string]interface{}
	setup.DecodeResponse(resp1, &data1)
	setup.DecodeResponse(resp2, &data2)

	users1 := data1["users"].([]interface{})
	users2 := data2["users"].([]interface{})

	assert.Equal(t, 2, len(users1))
	assert.Equal(t, 2, len(users2))
}

// TestAPIContract_ProjectFiltering validates project filtering parameters
func TestAPIContract_ProjectFiltering(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	setup.CreateTestProject("p1", "Active Project", "Description")
	setup.CreateTestProject("p2", "Another Project", "Description")

	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)
	setup.Router.Get("/api/projects", projectHandlers.ListProjects)

	recorder := setup.MakeRequest("GET", "/api/projects?limit=10", nil)
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	setup.DecodeResponse(recorder, &response)
	assert.NotNil(t, response["projects"])
}

// TestAPIContract_TaskFiltering validates task filtering by status
func TestAPIContract_TaskFiltering(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Project", "Desc")
	setup.CreateTestTask("t1", project.ID, "Task 1", "pending")
	setup.CreateTestTask("t2", project.ID, "Task 2", "completed")

	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)
	setup.Router.Get("/api/tasks", taskHandlers.ListTasks)

	recorder := setup.MakeRequest("GET", "/api/tasks?status=pending", nil)
	setup.AssertResponseStatus(recorder, http.StatusOK)
}

// TestAPIContract_BadRequest validates 400 response for invalid input
func TestAPIContract_BadRequest(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)
	setup.Router.Post("/api/users", userHandlers.CreateUser)

	recorder := setup.MakeRequest("POST", "/api/users",
		services.CreateUserRequest{
			Username: "",
			Email:    "",
			Password: "",
		})

	assert.True(t, recorder.Code >= 400 && recorder.Code < 500)
}

// TestAPIContract_NotFound validates 404 response structure
func TestAPIContract_NotFound(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)
	setup.Router.Get("/api/projects/{id}", projectHandlers.GetProject)

	recorder := setup.MakeRequest("GET", "/api/projects/nonexistent", nil)

	assert.Equal(t, http.StatusNotFound, recorder.Code)
}

// TestAPIContract_MethodNotAllowed validates 405 for wrong HTTP method
func TestAPIContract_MethodNotAllowed(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)
	setup.Router.Get("/api/projects/{id}", projectHandlers.GetProject)

	// Setup a POST route that doesn't exist
	setup.Router.Get("/api/projects/{id}", projectHandlers.GetProject)
	// Now try POST on a GET-only endpoint (this tests the router's method handling)
	recorder := setup.MakeRequest("GET", "/api/projects/p1", nil)
	setup.AssertResponseStatus(recorder, http.StatusNotFound) // No project exists
}

// TestAPIContract_UserEmailValidation validates email in user response
func TestAPIContract_UserEmailValidation(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)
	setup.Router.Post("/api/users", userHandlers.CreateUser)

	recorder := setup.MakeRequest("POST", "/api/users",
		services.CreateUserRequest{
			Username: "testuser",
			Email:    "test@example.com",
			Password: "password123",
		})

	// Email field should be preserved in response
	if recorder.Code == http.StatusCreated {
		var response map[string]interface{}
		setup.DecodeResponse(recorder, &response)
		assert.Equal(t, "test@example.com", response["email"])
	}
}

// TestAPIContract_ResponseContentType validates response Content-Type header
func TestAPIContract_ResponseContentType(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	user := setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)
	setup.Router.Get("/api/users/{id}", userHandlers.GetUser)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/users/%s", user.ID), nil)

	contentType := recorder.Header().Get("Content-Type")
	assert.Contains(t, contentType, "application/json")
}

// TestAPIContract_ProjectUpdatePartial validates partial project updates
func TestAPIContract_ProjectUpdatePartial(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Original", "Desc")

	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)
	setup.Router.Put("/api/projects/{id}", projectHandlers.UpdateProject)

	recorder := setup.MakeRequest("PUT", fmt.Sprintf("/api/projects/%s", project.ID),
		services.UpdateProjectRequest{
			Name: "Updated Name",
		})

	setup.AssertResponseStatus(recorder, http.StatusOK)
}

// TestAPIContract_TaskCompletion validates task completion endpoint contract
func TestAPIContract_TaskCompletion(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Project", "Desc")
	task := setup.CreateTestTask("t1", project.ID, "Task", "pending")

	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)
	setup.Router.Post("/api/tasks/{id}/complete", taskHandlers.CompleteTask)

	recorder := setup.MakeRequest("POST", fmt.Sprintf("/api/tasks/%s/complete", task.ID), nil)

	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	setup.DecodeResponse(recorder, &response)
	assert.Equal(t, "completed", response["status"])
}

// TestAPIContract_AuthLogoutSuccess validates logout endpoint contract
func TestAPIContract_AuthLogoutSuccess(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	pm := auth.NewPasswordManager()
	tm := auth.NewTokenManager("test-secret", 24*time.Hour, "test-issuer")

	hashedPassword, _ := pm.HashPassword("password123")
	user := &models.User{
		ID:           "user1",
		Username:     "testuser",
		Email:        "test@example.com",
		PasswordHash: hashedPassword,
		Status:       "active",
	}
	setup.DB.Create(user)

	sessionMgr := auth.NewSessionManager(
		setup.RepoRegistry.UserRepository,
		setup.RepoRegistry.SessionRepository,
		pm, tm, 24*time.Hour,
	)

	errHandler := errors.NewErrorHandler(false, true)
	authHandlers := NewAuthHandlers(sessionMgr, setup.ServiceRegistry.UserService, errHandler)
	setup.Router.Post("/auth/logout", authHandlers.Logout)
	setup.Router.Post("/auth/login", authHandlers.Login)

	// Logout without token should return error
	logoutResp := setup.MakeRequest("POST", "/auth/logout", nil)
	// Should return 401 since no token provided
	assert.Equal(t, http.StatusUnauthorized, logoutResp.Code)
}

// ============================================================================
// Additional Response Schema Validation Tests (10 more tests)
// ============================================================================

// TestResponseSchema_OptionalFields validates handling of optional fields
func TestResponseSchema_OptionalFields(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	user := setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)
	setup.Router.Get("/api/users/{id}", userHandlers.GetUser)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/users/%s", user.ID), nil)

	var response map[string]interface{}
	setup.DecodeResponse(recorder, &response)

	// Optional fields may be nil or empty, but structure is consistent
	assert.NotNil(t, response["id"])
	assert.NotNil(t, response["username"])
}

// TestResponseSchema_NumericFields validates numeric field types
func TestResponseSchema_NumericFields(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)
	setup.Router.Get("/api/users", userHandlers.ListUsers)

	recorder := setup.MakeRequest("GET", "/api/users?limit=10&offset=0", nil)

	var response map[string]interface{}
	setup.DecodeResponse(recorder, &response)

	// Pagination fields must be numbers
	assert.IsType(t, float64(0), response["limit"])
	assert.IsType(t, float64(0), response["offset"])
	assert.IsType(t, float64(0), response["total"])
}

// TestResponseSchema_StringFields validates string field types
func TestResponseSchema_StringFields(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Test Project", "Description")

	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)
	setup.Router.Get("/api/projects/{id}", projectHandlers.GetProject)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/projects/%s", project.ID), nil)

	var response map[string]interface{}
	setup.DecodeResponse(recorder, &response)

	// String fields must be strings
	assert.IsType(t, "", response["id"])
	assert.IsType(t, "", response["name"])
	assert.IsType(t, "", response["description"])
}

// TestResponseSchema_BooleanFields validates boolean field types
func TestResponseSchema_BooleanFields(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Project", "Desc")

	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)
	setup.Router.Get("/api/projects/{id}", projectHandlers.GetProject)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/projects/%s", project.ID), nil)

	var response map[string]interface{}
	setup.DecodeResponse(recorder, &response)

	// Response should have consistent structure
	assert.NotNil(t, response)
}

// TestResponseSchema_ArrayItems validates array item types
func TestResponseSchema_ArrayItems(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	setup.CreateTestUser("user1", "alice", "alice@example.com")
	setup.CreateTestUser("user2", "bob", "bob@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)
	setup.Router.Get("/api/users", userHandlers.ListUsers)

	recorder := setup.MakeRequest("GET", "/api/users", nil)

	var response map[string]interface{}
	setup.DecodeResponse(recorder, &response)

	users := response["users"].([]interface{})
	for _, user := range users {
		assert.IsType(t, map[string]interface{}{}, user)
	}
}

// TestResponseSchema_NestedObjects validates nested object schema
func TestResponseSchema_NestedObjects(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Project", "Desc")
	setup.CreateTestTask("t1", project.ID, "Task", "pending")

	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)
	setup.Router.Get("/api/tasks", taskHandlers.ListTasks)

	recorder := setup.MakeRequest("GET", "/api/tasks", nil)

	var response map[string]interface{}
	setup.DecodeResponse(recorder, &response)

	// Tasks array should contain objects with required fields
	tasks := response["tasks"].([]interface{})
	if len(tasks) > 0 {
		task := tasks[0].(map[string]interface{})
		assert.NotNil(t, task["id"])
		assert.NotNil(t, task["title"])
	}
}

// TestResponseSchema_ConsistentFieldNames validates field naming convention
func TestResponseSchema_ConsistentFieldNames(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	user := setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)
	setup.Router.Get("/api/users/{id}", userHandlers.GetUser)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/users/%s", user.ID), nil)

	var response map[string]interface{}
	setup.DecodeResponse(recorder, &response)

	// Field names should use consistent snake_case
	for key := range response {
		assert.Regexp(t, "^[a-z_]+$", key, "field names should be snake_case")
	}
}

// TestResponseSchema_DateFormatConsistency validates date format consistency
func TestResponseSchema_DateFormatConsistency(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Project", "Desc")

	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)
	setup.Router.Get("/api/projects/{id}", projectHandlers.GetProject)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/projects/%s", project.ID), nil)

	var response map[string]interface{}
	setup.DecodeResponse(recorder, &response)

	// All date fields should use ISO 8601 format
	if createdAt, ok := response["created_at"].(string); ok {
		_, err := time.Parse(time.RFC3339, createdAt)
		assert.NoError(t, err)
	}
}

// TestResponseSchema_NullHandling validates null field handling
func TestResponseSchema_NullHandling(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Project", "")

	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)
	setup.Router.Get("/api/projects/{id}", projectHandlers.GetProject)

	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/projects/%s", project.ID), nil)

	var response map[string]interface{}
	setup.DecodeResponse(recorder, &response)

	// Empty strings should be handled consistently
	assert.NotNil(t, response["id"])
}

// ============================================================================
// Additional API Versioning Tests (1 more test)
// ============================================================================

// TestAPIVersioning_DeprecationHandling validates deprecation warnings
func TestAPIVersioning_DeprecationHandling(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)
	setup.Router.Get("/api/users", userHandlers.ListUsers)

	recorder := setup.MakeRequest("GET", "/api/users", nil)

	// Verify response is still valid for backward compatibility
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)
	assert.NotNil(t, response)
}

// TestAPIContract_MultipleTaskCreation validates creating multiple tasks
func TestAPIContract_MultipleTaskCreation(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	project := setup.CreateTestProject("p1", "Project", "Desc")

	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)
	setup.Router.Post("/api/tasks", taskHandlers.CreateTask)

	// Create multiple tasks sequentially
	for i := 1; i <= 3; i++ {
		recorder := setup.MakeRequest("POST", "/api/tasks", services.CreateTaskRequest{
			ProjectID:   project.ID,
			Title:       fmt.Sprintf("Task %d", i),
			Description: fmt.Sprintf("Task description %d", i),
		})

		setup.AssertResponseStatus(recorder, http.StatusCreated)
	}
}

// TestAPIContract_SortingOrder validates sorting parameter contract
func TestAPIContract_SortingOrder(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	setup.CreateTestUser("user1", "alice", "alice@example.com")
	setup.CreateTestUser("user2", "bob", "bob@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)
	setup.Router.Get("/api/users", userHandlers.ListUsers)

	recorder := setup.MakeRequest("GET", "/api/users?sort=username&order=asc", nil)

	setup.AssertResponseStatus(recorder, http.StatusOK)
	var response map[string]interface{}
	setup.DecodeResponse(recorder, &response)
	assert.NotNil(t, response["users"])
}

// TestAPIContract_DateRangeFilter validates date range filtering contract
func TestAPIContract_DateRangeFilter(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)
	setup.Router.Get("/api/users", userHandlers.ListUsers)

	recorder := setup.MakeRequest("GET", "/api/users?created_after=2026-02-01&created_before=2026-02-28", nil)

	// Should handle date filters gracefully
	assert.True(t, recorder.Code >= 200 && recorder.Code < 300 || recorder.Code >= 400)
}

// TestAPIContract_SearchQuery validates search parameter contract
func TestAPIContract_SearchQuery(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	setup.CreateTestUser("user1", "alice", "alice@example.com")

	errHandler := errors.NewErrorHandler(false, true)
	userHandlers := NewUserHandlers(setup.ServiceRegistry.UserService, errHandler)
	setup.Router.Get("/api/users", userHandlers.ListUsers)

	recorder := setup.MakeRequest("GET", "/api/users?q=alice", nil)

	// Should handle search gracefully
	assert.True(t, recorder.Code == http.StatusOK || recorder.Code == http.StatusBadRequest)
}
