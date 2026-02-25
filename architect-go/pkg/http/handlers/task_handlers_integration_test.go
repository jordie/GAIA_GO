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

// TestTaskHandlers_ListTasks tests the ListTasks endpoint
func TestTaskHandlers_ListTasks(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Seed project and tasks
	project := setup.CreateTestProject("p1", "My Project", "Description")
	setup.CreateTestTask("t1", project.ID, "Task 1", "pending")
	setup.CreateTestTask("t2", project.ID, "Task 2", "pending")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)

	// Setup route
	setup.Router.Get("/api/tasks", taskHandlers.ListTasks)

	// Make request
	recorder := setup.MakeRequest("GET", "/api/tasks?limit=10&offset=0", nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotNil(t, response["tasks"])
	assert.Equal(t, float64(2), response["total"])
}

// TestTaskHandlers_GetTask tests the GetTask endpoint
func TestTaskHandlers_GetTask(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Seed project and task
	project := setup.CreateTestProject("p1", "My Project", "Description")
	task := setup.CreateTestTask("t1", project.ID, "My Task", "pending")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)

	// Setup route
	setup.Router.Get("/api/tasks/{id}", taskHandlers.GetTask)

	// Make request
	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/tasks/%s", task.ID), nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.Equal(t, "My Task", response["title"])
	assert.Equal(t, "pending", response["status"])
}

// TestTaskHandlers_GetTask_NotFound tests GetTask with non-existent task
func TestTaskHandlers_GetTask_NotFound(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)

	// Setup route
	setup.Router.Get("/api/tasks/{id}", taskHandlers.GetTask)

	// Make request for non-existent task
	recorder := setup.MakeRequest("GET", "/api/tasks/nonexistent", nil)

	// Assertions
	assert.Equal(t, http.StatusNotFound, recorder.Code)
}

// TestTaskHandlers_CreateTask tests the CreateTask endpoint
func TestTaskHandlers_CreateTask(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Seed project
	project := setup.CreateTestProject("p1", "My Project", "Description")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)

	// Setup route
	setup.Router.Post("/api/tasks", taskHandlers.CreateTask)

	// Prepare request
	requestBody := services.CreateTaskRequest{
		ProjectID:   project.ID,
		Title:       "New Task",
		Description: "Task Description",
	}

	// Make request
	recorder := setup.MakeRequest("POST", "/api/tasks", requestBody)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusCreated)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotEmpty(t, response["id"])
	assert.Equal(t, "New Task", response["title"])
	assert.Equal(t, project.ID, response["project_id"])
}

// TestTaskHandlers_UpdateTask tests the UpdateTask endpoint
func TestTaskHandlers_UpdateTask(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Seed project and task
	project := setup.CreateTestProject("p1", "My Project", "Description")
	task := setup.CreateTestTask("t1", project.ID, "Original Title", "pending")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)

	// Setup route
	setup.Router.Put("/api/tasks/{id}", taskHandlers.UpdateTask)

	// Prepare request
	requestBody := services.UpdateTaskRequest{
		Title:       "Updated Title",
		Description: "Updated Description",
		Status:      "in_progress",
	}

	// Make request
	recorder := setup.MakeRequest("PUT", fmt.Sprintf("/api/tasks/%s", task.ID), requestBody)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.Equal(t, "Updated Title", response["title"])
	assert.Equal(t, "in_progress", response["status"])
}

// TestTaskHandlers_CompleteTask tests the CompleteTask endpoint
func TestTaskHandlers_CompleteTask(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Seed project and task
	project := setup.CreateTestProject("p1", "My Project", "Description")
	task := setup.CreateTestTask("t1", project.ID, "Task to Complete", "pending")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)

	// Setup route
	setup.Router.Post("/api/tasks/{id}/complete", taskHandlers.CompleteTask)

	// Make request
	recorder := setup.MakeRequest("POST", fmt.Sprintf("/api/tasks/%s/complete", task.ID), nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.Equal(t, "completed", response["status"])
}

// TestTaskHandlers_DeleteTask tests the DeleteTask endpoint
func TestTaskHandlers_DeleteTask(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Seed project and task
	project := setup.CreateTestProject("p1", "My Project", "Description")
	task := setup.CreateTestTask("t1", project.ID, "Task to Delete", "pending")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	taskHandlers := NewTaskHandlers(setup.ServiceRegistry.TaskService, errHandler)

	// Setup route
	setup.Router.Delete("/api/tasks/{id}", taskHandlers.DeleteTask)

	// Make request
	recorder := setup.MakeRequest("DELETE", fmt.Sprintf("/api/tasks/%s", task.ID), nil)

	// Assertions
	assert.True(t, recorder.Code == http.StatusOK || recorder.Code == http.StatusNoContent,
		"expected 200 or 204 but got %d", recorder.Code)
}
