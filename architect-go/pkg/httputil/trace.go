package httputil

import "net/http"

// GetTraceID gets a trace ID from the request context or headers.
// This utility is in a separate package to avoid circular imports between
// pkg/http and pkg/http/handlers.
func GetTraceID(r *http.Request) string {
	// Try to get from context
	traceID, ok := r.Context().Value("X-Trace-ID").(string)
	if ok && traceID != "" {
		return traceID
	}

	// Try to get from header
	traceID = r.Header.Get("X-Trace-ID")
	if traceID != "" {
		return traceID
	}

	// Try to get from request ID middleware
	requestID := r.Header.Get("X-Request-ID")
	if requestID != "" {
		return requestID
	}

	return ""
}
