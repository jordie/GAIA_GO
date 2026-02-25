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

// ProjectHandlers handles project-related HTTP requests
type ProjectHandlers struct {
	service    services.ProjectService
	errHandler *errors.Handler
	dispatcher events.EventDispatcher
}

// NewProjectHandlers creates new project handlers
func NewProjectHandlers(service services.ProjectService, errHandler *errors.Handler) *ProjectHandlers {
	return &ProjectHandlers{
		service:    service,
		errHandler: errHandler,
	}
}

// NewProjectHandlersWithDispatcher creates new project handlers with event dispatcher
func NewProjectHandlersWithDispatcher(service services.ProjectService, errHandler *errors.Handler, dispatcher events.EventDispatcher) *ProjectHandlers {
	return &ProjectHandlers{
		service:    service,
		errHandler: errHandler,
		dispatcher: dispatcher,
	}
}

// ListProjects handles GET /api/projects
func (ph *ProjectHandlers) ListProjects(w http.ResponseWriter, r *http.Request) {
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

	req := &services.ListProjectsRequest{
		Status: r.URL.Query().Get("status"),
		Name:   r.URL.Query().Get("name"),
		Limit:  limit,
		Offset: offset,
	}

	projects, total, err := ph.service.ListProjects(r.Context(), req)
	if err != nil {
		ph.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"projects": projects,
		"total":    total,
		"limit":    limit,
		"offset":   offset,
	})
}

// CreateProject handles POST /api/projects
func (ph *ProjectHandlers) CreateProject(w http.ResponseWriter, r *http.Request) {
	var req services.CreateProjectRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		ph.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if req.Name == "" {
		ph.errHandler.Handle(w, errors.ValidationErrorf("MISSING_NAME", "Project name is required"), httputil.GetTraceID(r))
		return
	}

	project, err := ph.service.CreateProject(r.Context(), &req)
	if err != nil {
		ph.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	// Dispatch event
	if ph.dispatcher != nil {
		ph.dispatcher.Dispatch(events.Event{
			Type:    events.EventProjectCreated,
			Channel: "projects",
			Data:    project,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(project)
}

// GetProject handles GET /api/projects/{id}
func (ph *ProjectHandlers) GetProject(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ph.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Project ID is required"), httputil.GetTraceID(r))
		return
	}

	project, err := ph.service.GetProject(r.Context(), id)
	if err != nil {
		ph.errHandler.Handle(w, errors.NotFoundErrorf("PROJECT_NOT_FOUND", "Project not found"), httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(project)
}

// UpdateProject handles PUT /api/projects/{id}
func (ph *ProjectHandlers) UpdateProject(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ph.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Project ID is required"), httputil.GetTraceID(r))
		return
	}

	var req services.UpdateProjectRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		ph.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	project, err := ph.service.UpdateProject(r.Context(), id, &req)
	if err != nil {
		ph.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	// Dispatch event
	if ph.dispatcher != nil {
		ph.dispatcher.Dispatch(events.Event{
			Type:    events.EventProjectUpdated,
			Channel: "projects",
			Data:    project,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(project)
}

// DeleteProject handles DELETE /api/projects/{id}
func (ph *ProjectHandlers) DeleteProject(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ph.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Project ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := ph.service.DeleteProject(r.Context(), id); err != nil {
		ph.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// GetProjectStats handles GET /api/projects/{id}/stats
func (ph *ProjectHandlers) GetProjectStats(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		ph.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Project ID is required"), httputil.GetTraceID(r))
		return
	}

	stats, err := ph.service.GetProjectStats(r.Context(), id)
	if err != nil {
		ph.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(stats)
}

// RegisterProjectRoutes registers project routes
func RegisterProjectRoutes(r chi.Router, handlers *ProjectHandlers) {
	r.Get("/", handlers.ListProjects)
	r.Post("/", handlers.CreateProject)
	r.Get("/{id}", handlers.GetProject)
	r.Put("/{id}", handlers.UpdateProject)
	r.Delete("/{id}", handlers.DeleteProject)
	r.Get("/{id}/stats", handlers.GetProjectStats)
}
