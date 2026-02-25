package errors

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
)

// ErrorResponse represents an error response to be sent to the client
type ErrorResponse struct {
	Error   ErrorDetail `json:"error"`
	TraceID string      `json:"trace_id,omitempty"`
}

// ErrorDetail contains error information
type ErrorDetail struct {
	Type    string                 `json:"type"`
	Code    string                 `json:"code"`
	Message string                 `json:"message"`
	Details map[string]interface{} `json:"details,omitempty"`
}

// Handler handles errors and writes appropriate HTTP responses
type Handler struct {
	includeStackTrace bool
	logErrors        bool
}

// NewErrorHandler creates a new error handler
func NewErrorHandler(includeStackTrace bool, logErrors bool) *Handler {
	return &Handler{
		includeStackTrace: includeStackTrace,
		logErrors:        logErrors,
	}
}

// Handle handles an error and writes the response
func (h *Handler) Handle(w http.ResponseWriter, err error, traceID string) {
	w.Header().Set("Content-Type", "application/json")

	// Convert to AppError if possible
	var appErr *AppError
	if ae, ok := err.(*AppError); ok {
		appErr = ae
	} else {
		// Wrap unknown errors as internal errors
		appErr = InternalErrorf("INTERNAL_ERROR", "An unexpected error occurred")
		appErr.Wrap(err)
	}

	// Log error if enabled
	if h.logErrors {
		h.logError(appErr, traceID)
	}

	// Write response
	statusCode := appErr.StatusCode
	w.WriteHeader(statusCode)

	response := h.buildErrorResponse(appErr, traceID)
	_ = json.NewEncoder(w).Encode(response)
}

// HandlePanic handles a panic and writes an error response
func (h *Handler) HandlePanic(w http.ResponseWriter, recover interface{}, traceID string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusInternalServerError)

	appErr := InternalErrorf("PANIC", "An unexpected error occurred")

	if h.logErrors {
		log.Printf("[PANIC] TraceID: %s, Value: %v\n%s", traceID, recover, appErr.StackTrace)
	}

	response := h.buildErrorResponse(appErr, traceID)
	_ = json.NewEncoder(w).Encode(response)
}

// buildErrorResponse builds an error response object
func (h *Handler) buildErrorResponse(appErr *AppError, traceID string) *ErrorResponse {
	response := &ErrorResponse{
		TraceID: traceID,
		Error: ErrorDetail{
			Type:    string(appErr.Type),
			Code:    appErr.Code,
			Message: appErr.Message,
			Details: appErr.Details,
		},
	}

	// Include stack trace if enabled and in development
	if h.includeStackTrace && appErr.StackTrace != "" {
		if response.Error.Details == nil {
			response.Error.Details = make(map[string]interface{})
		}
		response.Error.Details["stack_trace"] = appErr.StackTrace
	}

	return response
}

// logError logs an error
func (h *Handler) logError(appErr *AppError, traceID string) {
	logMsg := fmt.Sprintf(
		"[ERROR] TraceID: %s, Type: %s, Code: %s, Message: %s",
		traceID, appErr.Type, appErr.Code, appErr.Message,
	)

	if appErr.Err != nil {
		logMsg += fmt.Sprintf(", Cause: %v", appErr.Err)
	}

	if len(appErr.Details) > 0 {
		logMsg += fmt.Sprintf(", Details: %v", appErr.Details)
	}

	log.Println(logMsg)
}

// WriteError is a convenience function to write an error response
func WriteError(w http.ResponseWriter, err error) {
	h := NewErrorHandler(false, true)
	h.Handle(w, err, "")
}

// WriteErrorWithStatus writes an error response with specific status code
func WriteErrorWithStatus(w http.ResponseWriter, statusCode int, code string, message string) {
	h := NewErrorHandler(false, true)
	appErr := New(InternalError, code, message)
	appErr.StatusCode = statusCode
	h.Handle(w, appErr, "")
}

// WriteErrorWithCode writes an error response for a specific error code
func WriteErrorWithCode(w http.ResponseWriter, code string) {
	appErr := mapCodeToError(code)
	h := NewErrorHandler(false, true)
	h.Handle(w, appErr, "")
}

// mapCodeToError maps common error codes to AppErrors
func mapCodeToError(code string) *AppError {
	switch code {
	case "unauthorized":
		return AuthenticationErrorf("UNAUTHORIZED", "Authentication required")
	case "forbidden":
		return AuthorizationErrorf("FORBIDDEN", "You don't have permission to access this resource")
	case "not_found":
		return NotFoundErrorf("NOT_FOUND", "The requested resource was not found")
	case "conflict":
		return ConflictErrorf("CONFLICT", "The request conflicts with existing data")
	case "bad_request":
		return ValidationErrorf("BAD_REQUEST", "Invalid request")
	case "internal_error":
		return InternalErrorf("INTERNAL_ERROR", "An unexpected error occurred")
	case "service_unavailable":
		return ExternalServiceErrorf("SERVICE_UNAVAILABLE", "External service is currently unavailable")
	case "timeout":
		return TimeoutErrorf("TIMEOUT", "Request timeout")
	case "rate_limit":
		return RateLimitErrorf("RATE_LIMIT", "Too many requests")
	default:
		return InternalErrorf("UNKNOWN_ERROR", "An unexpected error occurred")
	}
}
