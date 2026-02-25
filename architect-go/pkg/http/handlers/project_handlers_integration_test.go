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

// TestProjectHandlers_ListProjects_Empty tests ListProjects with no projects
func TestProjectHandlers_ListProjects_Empty(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)

	// Setup route
	setup.Router.Get("/api/projects", projectHandlers.ListProjects)

	// Make request
	recorder := setup.MakeRequest("GET", "/api/projects", nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.Equal(t, float64(0), response["total"])
	projects := response["projects"].([]interface{})
	assert.Equal(t, 0, len(projects))
}

// TestProjectHandlers_ListProjects_WithData tests ListProjects with seeded projects
func TestProjectHandlers_ListProjects_WithData(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Seed projects
	setup.CreateTestProject("p1", "Project One", "Description 1")
	setup.CreateTestProject("p2", "Project Two", "Description 2")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)

	// Setup route
	setup.Router.Get("/api/projects", projectHandlers.ListProjects)

	// Make request
	recorder := setup.MakeRequest("GET", "/api/projects", nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.Equal(t, float64(2), response["total"])
	projects := response["projects"].([]interface{})
	assert.Equal(t, 2, len(projects))
}

// TestProjectHandlers_GetProject tests the GetProject endpoint
func TestProjectHandlers_GetProject(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Seed project
	project := setup.CreateTestProject("p1", "My Project", "My Description")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)

	// Setup route
	setup.Router.Get("/api/projects/{id}", projectHandlers.GetProject)

	// Make request
	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/projects/%s", project.ID), nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.Equal(t, "My Project", response["name"])
	assert.Equal(t, "My Description", response["description"])
}

// TestProjectHandlers_GetProject_NotFound tests GetProject with non-existent project
func TestProjectHandlers_GetProject_NotFound(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)

	// Setup route
	setup.Router.Get("/api/projects/{id}", projectHandlers.GetProject)

	// Make request for non-existent project
	recorder := setup.MakeRequest("GET", "/api/projects/nonexistent", nil)

	// Assertions
	assert.Equal(t, http.StatusNotFound, recorder.Code)
}

// TestProjectHandlers_CreateProject tests the CreateProject endpoint
func TestProjectHandlers_CreateProject(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)

	// Setup route
	setup.Router.Post("/api/projects", projectHandlers.CreateProject)

	// Prepare request
	requestBody := services.CreateProjectRequest{
		Name:        "New Project",
		Description: "New Project Description",
	}

	// Make request
	recorder := setup.MakeRequest("POST", "/api/projects", requestBody)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusCreated)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotEmpty(t, response["id"])
	assert.Equal(t, "New Project", response["name"])
}

// TestProjectHandlers_UpdateProject tests the UpdateProject endpoint
func TestProjectHandlers_UpdateProject(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Seed project
	project := setup.CreateTestProject("p1", "Original Name", "Original Description")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)

	// Setup route
	setup.Router.Put("/api/projects/{id}", projectHandlers.UpdateProject)

	// Prepare request
	requestBody := services.UpdateProjectRequest{
		Name:        "Updated Name",
		Description: "Updated Description",
	}

	// Make request
	recorder := setup.MakeRequest("PUT", fmt.Sprintf("/api/projects/%s", project.ID), requestBody)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.Equal(t, "Updated Name", response["name"])
	assert.Equal(t, "Updated Description", response["description"])
}

// TestProjectHandlers_DeleteProject tests the DeleteProject endpoint
func TestProjectHandlers_DeleteProject(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Seed project
	project := setup.CreateTestProject("p1", "To Delete", "Will be deleted")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)

	// Setup route
	setup.Router.Delete("/api/projects/{id}", projectHandlers.DeleteProject)

	// Make request
	recorder := setup.MakeRequest("DELETE", fmt.Sprintf("/api/projects/%s", project.ID), nil)

	// Assertions
	assert.True(t, recorder.Code == http.StatusOK || recorder.Code == http.StatusNoContent,
		"expected 200 or 204 but got %d", recorder.Code)
}

// TestProjectHandlers_GetProjectStats tests the GetProjectStats endpoint
func TestProjectHandlers_GetProjectStats(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Seed project and tasks
	project := setup.CreateTestProject("p1", "My Project", "Description")
	setup.CreateTestTask("t1", project.ID, "Task 1", "completed")
	setup.CreateTestTask("t2", project.ID, "Task 2", "pending")
	setup.CreateTestTask("t3", project.ID, "Task 3", "pending")

	// Create handlers
	errHandler := errors.NewErrorHandler(false, true)
	projectHandlers := NewProjectHandlers(setup.ServiceRegistry.ProjectService, errHandler)

	// Setup route
	setup.Router.Get("/api/projects/{id}/stats", projectHandlers.GetProjectStats)

	// Make request
	recorder := setup.MakeRequest("GET", fmt.Sprintf("/api/projects/%s/stats", project.ID), nil)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err := setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	// Stats should contain numeric fields
	assert.NotNil(t, response)
}
