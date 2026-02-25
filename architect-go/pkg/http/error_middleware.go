package http

import (
	"net/http"

	"architect-go/pkg/errors"
	"architect-go/pkg/httputil"
)

// RecoveryMiddleware recovers from panics and logs errors
func RecoveryMiddleware(handler *errors.Handler) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			defer func() {
				if recover := recover(); recover != nil {
					traceID := httputil.GetTraceID(r)
					handler.HandlePanic(w, recover, traceID)
				}
			}()

			next.ServeHTTP(w, r)
		})
	}
}

// ErrorHandlingMiddleware handles errors in responses
func ErrorHandlingMiddleware(handler *errors.Handler) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Wrap response writer to capture status code
			wrapped := &responseWriter{ResponseWriter: w, statusCode: http.StatusOK}
			next.ServeHTTP(wrapped, r)

			// Handle errors if response is error status
			if wrapped.statusCode >= 400 && wrapped.statusCode != http.StatusNotFound {
				// Log the error response
				traceID := httputil.GetTraceID(r)
				if wrapped.statusCode >= 500 {
					// Log server errors
					appErr := errors.New(errors.InternalError, "HTTP_ERROR", "Server error")
					handler.Handle(wrapped, appErr, traceID)
				}
			}
		})
	}
}

// responseWriter wraps http.ResponseWriter to capture status code
type responseWriter struct {
	http.ResponseWriter
	statusCode int
	written    bool
}

// WriteHeader captures the status code
func (rw *responseWriter) WriteHeader(statusCode int) {
	if !rw.written {
		rw.statusCode = statusCode
		rw.written = true
		rw.ResponseWriter.WriteHeader(statusCode)
	}
}

// Write writes data
func (rw *responseWriter) Write(b []byte) (int, error) {
	if !rw.written {
		rw.written = true
	}
	return rw.ResponseWriter.Write(b)
}

// GetTraceID delegates to httputil.GetTraceID for backward compatibility.
func GetTraceID(r *http.Request) string {
	return httputil.GetTraceID(r)
}
