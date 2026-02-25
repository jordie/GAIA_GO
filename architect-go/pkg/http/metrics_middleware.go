package http

import (
	"fmt"
	"net/http"
	"time"

	"architect-go/pkg/metrics"
)

// MetricsMiddleware collects HTTP metrics
func MetricsMiddleware(m *metrics.Metrics) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Start timing the request
			start := time.Now()

			// Wrap response writer to capture status and size
			wrapped := &metricsResponseWriter{
				ResponseWriter: w,
				statusCode:     http.StatusOK,
			}

			// Call next handler
			next.ServeHTTP(wrapped, r)

			// Record metrics
			duration := time.Since(start).Seconds()
			m.RecordHTTPRequest(duration)
			m.RecordHTTPResponse(float64(wrapped.size))

			// Record errors
			if wrapped.statusCode >= 400 {
				m.RecordHTTPError()
			}

			// Optionally log slow requests
			if duration > 1.0 {
				fmt.Printf("[SLOW REQUEST] %s %s took %.2f seconds\n", r.Method, r.RequestURI, duration)
			}
		})
	}
}

// metricsResponseWriter wraps http.ResponseWriter to capture status and size
type metricsResponseWriter struct {
	http.ResponseWriter
	statusCode int
	size       int
	written    bool
}

// WriteHeader captures the status code
func (mrw *metricsResponseWriter) WriteHeader(statusCode int) {
	if !mrw.written {
		mrw.statusCode = statusCode
		mrw.written = true
		mrw.ResponseWriter.WriteHeader(statusCode)
	}
}

// Write captures the response size
func (mrw *metricsResponseWriter) Write(b []byte) (int, error) {
	if !mrw.written {
		mrw.written = true
	}
	mrw.size += len(b)
	return mrw.ResponseWriter.Write(b)
}
