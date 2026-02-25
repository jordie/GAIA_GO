package handlers

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"

	"architect-go/pkg/errors"
	httputil "architect-go/pkg/httputil"
	"architect-go/pkg/services"
)

// WorkerHandlers handles worker HTTP requests
type WorkerHandlers struct {
	service    services.WorkerService
	errHandler *errors.Handler
}

// NewWorkerHandlers creates new worker handlers
func NewWorkerHandlers(service services.WorkerService, errHandler *errors.Handler) *WorkerHandlers {
	return &WorkerHandlers{
		service:    service,
		errHandler: errHandler,
	}
}

// ListWorkers handles GET /api/workers
func (wh *WorkerHandlers) ListWorkers(w http.ResponseWriter, r *http.Request) {
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

	req := &services.ListWorkersRequest{
		Type:   r.URL.Query().Get("type"),
		Status: r.URL.Query().Get("status"),
		Limit:  limit,
		Offset: offset,
	}

	workers, total, err := wh.service.ListWorkers(r.Context(), req)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"workers": workers,
		"total":   total,
		"limit":   limit,
		"offset":  offset,
	})
}

// RegisterWorkerRequest represents a worker registration request
type RegisterWorkerRequest struct {
	Type     string                 `json:"type"`
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// RegisterWorker handles POST /api/workers
func (wh *WorkerHandlers) RegisterWorker(w http.ResponseWriter, r *http.Request) {
	var req RegisterWorkerRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		wh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if req.Type == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_TYPE", "Worker type is required"), httputil.GetTraceID(r))
		return
	}

	registerReq := &services.RegisterWorkerRequest{
		Type:     req.Type,
		Metadata: req.Metadata,
	}

	worker, err := wh.service.RegisterWorker(r.Context(), registerReq)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(worker)
}

// GetWorker handles GET /api/workers/{id}
func (wh *WorkerHandlers) GetWorker(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Worker ID is required"), httputil.GetTraceID(r))
		return
	}

	worker, err := wh.service.GetWorker(r.Context(), id)
	if err != nil {
		wh.errHandler.Handle(w, errors.NotFoundErrorf("WORKER_NOT_FOUND", "Worker not found"), httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(worker)
}

// HeartbeatRequest represents a heartbeat request
type HeartbeatRequest struct {
	Status   string                 `json:"status,omitempty"`
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// Heartbeat handles POST /api/workers/{id}/heartbeat
func (wh *WorkerHandlers) Heartbeat(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Worker ID is required"), httputil.GetTraceID(r))
		return
	}

	var req HeartbeatRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		// Allow empty body for heartbeat
		if err.Error() != "EOF" {
			wh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
			return
		}
	}

	if err := wh.service.Heartbeat(r.Context(), id); err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"message": "Heartbeat received",
	})
}

// UnregisterWorker handles DELETE /api/workers/{id}
func (wh *WorkerHandlers) UnregisterWorker(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Worker ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := wh.service.UnregisterWorker(r.Context(), id); err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// GetWorkerStats handles GET /api/workers/{id}/stats
func (wh *WorkerHandlers) GetWorkerStats(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Worker ID is required"), httputil.GetTraceID(r))
		return
	}

	stats, err := wh.service.GetWorkerStats(r.Context(), id)
	if err != nil {
		wh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(stats)
}

// GetWorkerStatus handles GET /api/workers/{id}/status
func (wh *WorkerHandlers) GetWorkerStatus(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		wh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "Worker ID is required"), httputil.GetTraceID(r))
		return
	}

	worker, err := wh.service.GetWorker(r.Context(), id)
	if err != nil {
		wh.errHandler.Handle(w, errors.NotFoundErrorf("WORKER_NOT_FOUND", "Worker not found"), httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"id":     worker.ID,
		"status": worker.Status,
		"type":   worker.Type,
	})
}

// RegisterWorkerRoutes registers worker routes
func RegisterWorkerRoutes(r interface {
	Get(pattern string, handlerFn http.HandlerFunc)
	Post(pattern string, handlerFn http.HandlerFunc)
	Delete(pattern string, handlerFn http.HandlerFunc)
}, handlers *WorkerHandlers) {
	r.Get("/", handlers.ListWorkers)
	r.Post("/", handlers.RegisterWorker)
	r.Get("/{id}", handlers.GetWorker)
	r.Post("/{id}/heartbeat", handlers.Heartbeat)
	r.Delete("/{id}", handlers.UnregisterWorker)
	r.Get("/{id}/stats", handlers.GetWorkerStats)
	r.Get("/{id}/status", handlers.GetWorkerStatus)
}
