package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"architect-go/pkg/errors"
	"architect-go/pkg/events"
	"architect-go/pkg/models"
	"architect-go/pkg/services"
)

// mockProjectService implements ProjectService for testing
type mockProjectService struct {
	createdProjects []*models.Project
	updatedProjects []*models.Project
}

func (m *mockProjectService) CreateProject(ctx context.Context, req *services.CreateProjectRequest) (*models.Project, error) {
	project := &models.Project{ID: "p1", Name: req.Name, Status: "active"}
	m.createdProjects = append(m.createdProjects, project)
	return project, nil
}

func (m *mockProjectService) GetProject(ctx context.Context, id string) (*models.Project, error) {
	return &models.Project{ID: id, Name: "Test Project"}, nil
}

func (m *mockProjectService) ListProjects(ctx context.Context, req *services.ListProjectsRequest) ([]*models.Project, int64, error) {
	return nil, 0, nil
}

func (m *mockProjectService) UpdateProject(ctx context.Context, id string, req *services.UpdateProjectRequest) (*models.Project, error) {
	project := &models.Project{ID: id, Name: req.Name, Status: req.Status}
	m.updatedProjects = append(m.updatedProjects, project)
	return project, nil
}

func (m *mockProjectService) DeleteProject(ctx context.Context, id string) error {
	return nil
}

func (m *mockProjectService) GetProjectStats(ctx context.Context, id string) (map[string]interface{}, error) {
	return nil, nil
}

// TestProjectCreateDispatched tests that CreateProject dispatches event
func TestProjectCreateDispatched(t *testing.T) {
	mockSvc := &mockProjectService{}
	mockDispatcher := &mockEventDispatcher{}
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewProjectHandlersWithDispatcher(mockSvc, errHandler, mockDispatcher)

	reqBody := services.CreateProjectRequest{
		Name:        "New Project",
		Description: "Test description",
	}
	body, _ := json.Marshal(reqBody)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("POST", "/projects", bytes.NewReader(body))

	handler.CreateProject(w, r)

	if len(mockDispatcher.dispatchedEvents) != 1 {
		t.Errorf("expected 1 dispatched event, got %d", len(mockDispatcher.dispatchedEvents))
		return
	}

	event := mockDispatcher.dispatchedEvents[0]
	if event.Type != events.EventProjectCreated {
		t.Errorf("expected event type %s, got %s", events.EventProjectCreated, event.Type)
	}
	if event.Channel != "projects" {
		t.Errorf("expected channel projects, got %s", event.Channel)
	}
}

// TestProjectUpdateDispatched tests that UpdateProject dispatches event
func TestProjectUpdateDispatched(t *testing.T) {
	mockSvc := &mockProjectService{}
	mockDispatcher := &mockEventDispatcher{}
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewProjectHandlersWithDispatcher(mockSvc, errHandler, mockDispatcher)

	reqBody := services.UpdateProjectRequest{Name: "Updated Project"}
	body, _ := json.Marshal(reqBody)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("PUT", "/projects/p1", bytes.NewReader(body))
	r.Header.Set("Content-Type", "application/json")
	r = setURLParam(r, "id", "p1")

	handler.UpdateProject(w, r)

	if len(mockDispatcher.dispatchedEvents) != 1 {
		t.Errorf("expected 1 dispatched event, got %d", len(mockDispatcher.dispatchedEvents))
		return
	}

	event := mockDispatcher.dispatchedEvents[0]
	if event.Type != events.EventProjectUpdated {
		t.Errorf("expected event type %s, got %s", events.EventProjectUpdated, event.Type)
	}
}

// TestProjectNilDispatcherNoPanic tests that nil dispatcher doesn't panic
func TestProjectNilDispatcherNoPanic(t *testing.T) {
	mockSvc := &mockProjectService{}
	errHandler := errors.NewErrorHandler(false, true)

	// Create handler with nil dispatcher (should not panic)
	handler := NewProjectHandlers(mockSvc, errHandler)

	reqBody := services.CreateProjectRequest{
		Name:        "New Project",
		Description: "Test description",
	}
	body, _ := json.Marshal(reqBody)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("POST", "/projects", bytes.NewReader(body))

	// Should not panic
	handler.CreateProject(w, r)

	if w.Code != http.StatusCreated {
		t.Errorf("expected status 201, got %d", w.Code)
	}
}
