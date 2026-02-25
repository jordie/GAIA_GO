package handlers

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"

	"architect-go/pkg/errors"
	"architect-go/pkg/events"
	httputil "architect-go/pkg/httputil"
	"architect-go/pkg/services"
)

// TaskHandlers handles task-related HTTP requests
type TaskHandlers struct {
	service    services.TaskService
	errHandler *errors.Handler
	dispatcher events.EventDispatcher
}

// NewTaskHandlers creates new task handlers
func NewTaskHandlers(service services.TaskService, errHandler *errors.Handler) *TaskHandlers {
	return &TaskHandlers{
		service:    service,
		errHandler: errHandler,
	}
}

// NewTaskHandlersWithDispatcher creates new task handlers with event dispatcher
func NewTaskHandlersWithDispatcher(service services.TaskService, errHandler *errors.Handler, dispatcher events.EventDispatcher) *TaskHandlers {
	return &TaskHandlers{
		service:    service,
		errHandler: errHandler,
		dispatcher: dispatcher,
	}
}

// ListTasks handles GET /api/tasks
func (th *TaskHandlers) ListTasks(w http.ResponseWriter, r *http.Request) {
	limit := 10
	offset := 0

	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}
	if o := r.URL.Query().Get("offset"); o != "" {
		if parsed, err := strconv.Atoi(o); err == nil && parsed >= 0 {
			offset = parsed
		}
	}

	req := &services.ListTasksRequest{
		ProjectID: r.URL.Query().Get("project_id"),
		Status:    r.URL.Query().Get("status"),
		Limit:     limit,
		Offset:    offset,
	}

	tasks, total, err := th.service.ListTasks(r.Context(), req)
	if err != nil {
		th.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"tasks":  tasks,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// CreateTask handles POST /api/tasks
func (th *TaskHandlers) CreateTask(w http.ResponseWriter, r *http.Request) {
	var req services.CreateTaskRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		th.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if req.Title == "" {
		th.errHandler.Handle(w, errors.ValidationErrorf("MISSING_TITLE", "Task title is required"), httputil.GetTraceID(r))
		return
	}

	if req.ProjectID == "" {
		th.errHandler.Handle(w, errors.ValidationErrorf("MISSING_PROJECT_ID", "Project ID is required"), httputil.GetTraceID(r))
		return
	}

	task, err := th.service.CreateTask(r.Context(), &req)
	if err != nil {
		th.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	// Dispatch event
	if th.dispatcher != nil {
		th.dispatcher.Dispatch(events.Event{
			Type:    events.EventTaskCreated,
			Channel: "tasks",
			Data:    task,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(task)
}

// GetTask handles GET /api/tasks/{id}
func (th *TaskHandlers) GetTask(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		th.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Task ID is required"), httputil.GetTraceID(r))
		return
	}

	task, err := th.service.GetTask(r.Context(), id)
	if err != nil {
		th.errHandler.Handle(w, errors.NotFoundErrorf("TASK_NOT_FOUND", "Task not found"), httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(task)
}

// UpdateTask handles PUT /api/tasks/{id}
func (th *TaskHandlers) UpdateTask(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		th.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Task ID is required"), httputil.GetTraceID(r))
		return
	}

	var req services.UpdateTaskRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		th.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	task, err := th.service.UpdateTask(r.Context(), id, &req)
	if err != nil {
		th.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	// Dispatch event
	if th.dispatcher != nil {
		th.dispatcher.Dispatch(events.Event{
			Type:    events.EventTaskUpdated,
			Channel: "tasks",
			Data:    task,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(task)
}

// DeleteTask handles DELETE /api/tasks/{id}
func (th *TaskHandlers) DeleteTask(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		th.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Task ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := th.service.DeleteTask(r.Context(), id); err != nil {
		th.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// CompleteTask handles POST /api/tasks/{id}/complete
func (th *TaskHandlers) CompleteTask(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		th.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Task ID is required"), httputil.GetTraceID(r))
		return
	}

	task, err := th.service.CompleteTask(r.Context(), id)
	if err != nil {
		th.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	// Dispatch event
	if th.dispatcher != nil {
		th.dispatcher.Dispatch(events.Event{
			Type:    events.EventTaskCompleted,
			Channel: "tasks",
			Data:    task,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(task)
}

// RegisterTaskRoutes registers task routes
func RegisterTaskRoutes(r chi.Router, handlers *TaskHandlers) {
	r.Get("/", handlers.ListTasks)
	r.Post("/", handlers.CreateTask)
	r.Get("/{id}", handlers.GetTask)
	r.Put("/{id}", handlers.UpdateTask)
	r.Delete("/{id}", handlers.DeleteTask)
	r.Post("/{id}/complete", handlers.CompleteTask)
}
