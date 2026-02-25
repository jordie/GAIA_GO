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

// mockTaskService implements TaskService for testing
type mockTaskService struct {
	createdTasks   []*models.Task
	updatedTasks   []*models.Task
	completedTasks []*models.Task
}

func (m *mockTaskService) CreateTask(ctx context.Context, req *services.CreateTaskRequest) (*models.Task, error) {
	task := &models.Task{ID: "t1", Title: req.Title, Status: "pending", ProjectID: req.ProjectID}
	m.createdTasks = append(m.createdTasks, task)
	return task, nil
}

func (m *mockTaskService) GetTask(ctx context.Context, id string) (*models.Task, error) {
	return &models.Task{ID: id, Title: "Test Task"}, nil
}

func (m *mockTaskService) ListTasks(ctx context.Context, req *services.ListTasksRequest) ([]*models.Task, int64, error) {
	return nil, 0, nil
}

func (m *mockTaskService) UpdateTask(ctx context.Context, id string, req *services.UpdateTaskRequest) (*models.Task, error) {
	task := &models.Task{ID: id, Title: req.Title, Status: req.Status}
	m.updatedTasks = append(m.updatedTasks, task)
	return task, nil
}

func (m *mockTaskService) DeleteTask(ctx context.Context, id string) error {
	return nil
}

func (m *mockTaskService) CompleteTask(ctx context.Context, id string) (*models.Task, error) {
	task := &models.Task{ID: id, Title: "Test Task", Status: "completed"}
	m.completedTasks = append(m.completedTasks, task)
	return task, nil
}

func (m *mockTaskService) BulkUpdateTasks(ctx context.Context, req *services.BulkUpdateTasksRequest) (int, error) {
	return 0, nil
}

// TestTaskCreateDispatched tests that CreateTask dispatches event
func TestTaskCreateDispatched(t *testing.T) {
	mockSvc := &mockTaskService{}
	mockDispatcher := &mockEventDispatcher{}
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewTaskHandlersWithDispatcher(mockSvc, errHandler, mockDispatcher)

	reqBody := services.CreateTaskRequest{
		Title:     "New Task",
		ProjectID: "p1",
	}
	body, _ := json.Marshal(reqBody)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("POST", "/tasks", bytes.NewReader(body))

	handler.CreateTask(w, r)

	if len(mockDispatcher.dispatchedEvents) != 1 {
		t.Errorf("expected 1 dispatched event, got %d", len(mockDispatcher.dispatchedEvents))
		return
	}

	event := mockDispatcher.dispatchedEvents[0]
	if event.Type != events.EventTaskCreated {
		t.Errorf("expected event type %s, got %s", events.EventTaskCreated, event.Type)
	}
	if event.Channel != "tasks" {
		t.Errorf("expected channel tasks, got %s", event.Channel)
	}
}

// TestTaskUpdateDispatched tests that UpdateTask dispatches event
func TestTaskUpdateDispatched(t *testing.T) {
	mockSvc := &mockTaskService{}
	mockDispatcher := &mockEventDispatcher{}
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewTaskHandlersWithDispatcher(mockSvc, errHandler, mockDispatcher)

	reqBody := services.UpdateTaskRequest{Title: "Updated Task"}
	body, _ := json.Marshal(reqBody)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("PUT", "/tasks/t1", bytes.NewReader(body))
	r.Header.Set("Content-Type", "application/json")

	// Set URL param manually for testing
	r = setURLParam(r, "id", "t1")

	handler.UpdateTask(w, r)

	if len(mockDispatcher.dispatchedEvents) != 1 {
		t.Errorf("expected 1 dispatched event, got %d", len(mockDispatcher.dispatchedEvents))
		return
	}

	event := mockDispatcher.dispatchedEvents[0]
	if event.Type != events.EventTaskUpdated {
		t.Errorf("expected event type %s, got %s", events.EventTaskUpdated, event.Type)
	}
}

// TestTaskCompleteDispatched tests that CompleteTask dispatches event
func TestTaskCompleteDispatched(t *testing.T) {
	mockSvc := &mockTaskService{}
	mockDispatcher := &mockEventDispatcher{}
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewTaskHandlersWithDispatcher(mockSvc, errHandler, mockDispatcher)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("POST", "/tasks/t1/complete", nil)
	r = setURLParam(r, "id", "t1")

	handler.CompleteTask(w, r)

	if len(mockDispatcher.dispatchedEvents) != 1 {
		t.Errorf("expected 1 dispatched event, got %d", len(mockDispatcher.dispatchedEvents))
		return
	}

	event := mockDispatcher.dispatchedEvents[0]
	if event.Type != events.EventTaskCompleted {
		t.Errorf("expected event type %s, got %s", events.EventTaskCompleted, event.Type)
	}
}

// TestTaskNilDispatcherNoPanic tests that nil dispatcher doesn't panic
func TestTaskNilDispatcherNoPanic(t *testing.T) {
	mockSvc := &mockTaskService{}
	errHandler := errors.NewErrorHandler(false, true)

	// Create handler with nil dispatcher (should not panic)
	handler := NewTaskHandlers(mockSvc, errHandler)

	reqBody := services.CreateTaskRequest{
		Title:     "New Task",
		ProjectID: "p1",
	}
	body, _ := json.Marshal(reqBody)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("POST", "/tasks", bytes.NewReader(body))

	// Should not panic
	handler.CreateTask(w, r)

	if w.Code != http.StatusCreated {
		t.Errorf("expected status 201, got %d", w.Code)
	}
}
