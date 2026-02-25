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

// UserHandlers handles user-related HTTP requests
type UserHandlers struct {
	service    services.UserService
	errHandler *errors.Handler
}

// NewUserHandlers creates new user handlers
func NewUserHandlers(service services.UserService, errHandler *errors.Handler) *UserHandlers {
	return &UserHandlers{
		service:    service,
		errHandler: errHandler,
	}
}

// ListUsers handles GET /api/users
func (uh *UserHandlers) ListUsers(w http.ResponseWriter, r *http.Request) {
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

	req := &services.ListUsersRequest{
		Status: r.URL.Query().Get("status"),
		Limit:  limit,
		Offset: offset,
	}

	users, total, err := uh.service.ListUsers(r.Context(), req)
	if err != nil {
		uh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"users":  users,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// CreateUser handles POST /api/users
func (uh *UserHandlers) CreateUser(w http.ResponseWriter, r *http.Request) {
	var req services.CreateUserRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		uh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if req.Username == "" {
		uh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USERNAME", "Username is required"), httputil.GetTraceID(r))
		return
	}

	if req.Email == "" {
		uh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_EMAIL", "Email is required"), httputil.GetTraceID(r))
		return
	}

	user, err := uh.service.CreateUser(r.Context(), &req)
	if err != nil {
		uh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(user)
}

// GetUser handles GET /api/users/{id}
func (uh *UserHandlers) GetUser(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		uh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	user, err := uh.service.GetUser(r.Context(), id)
	if err != nil {
		uh.errHandler.Handle(w, errors.NotFoundErrorf("USER_NOT_FOUND", "User not found"), httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(user)
}

// UpdateUser handles PUT /api/users/{id}
func (uh *UserHandlers) UpdateUser(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		uh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	var req services.UpdateUserRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		uh.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	user, err := uh.service.UpdateUser(r.Context(), id, &req)
	if err != nil {
		uh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(user)
}

// DeleteUser handles DELETE /api/users/{id}
func (uh *UserHandlers) DeleteUser(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		uh.errHandler.Handle(w, errors.ValidationErrorf("MISSING_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	if err := uh.service.DeleteUser(r.Context(), id); err != nil {
		uh.errHandler.Handle(w, err, httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// RegisterUserRoutes registers user routes
func RegisterUserRoutes(r chi.Router, handlers *UserHandlers) {
	r.Get("/", handlers.ListUsers)
	r.Post("/", handlers.CreateUser)
	r.Get("/{id}", handlers.GetUser)
	r.Put("/{id}", handlers.UpdateUser)
	r.Delete("/{id}", handlers.DeleteUser)
}
