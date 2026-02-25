package http

import (
	"net/http"
	"time"

	"go.uber.org/zap"

	"architect-go/pkg/logging"
)

// RequestLoggingMiddleware logs HTTP requests and responses
func RequestLoggingMiddleware(logger *logging.Logger) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Start timing the request
			start := time.Now()

			// Wrap response writer to capture status code and response size
			wrapped := &loggingResponseWriter{
				ResponseWriter: w,
				statusCode:     http.StatusOK,
			}

			// Log incoming request
			logger.Debug("HTTP request received",
				zap.String("method", r.Method),
				zap.String("path", r.RequestURI),
				zap.String("remote_addr", r.RemoteAddr),
				zap.String("user_agent", r.UserAgent()),
			)

			// Call next handler
			next.ServeHTTP(wrapped, r)

			// Calculate request duration
			duration := time.Since(start)

			// Log outgoing response
			fields := []zap.Field{
				zap.String("method", r.Method),
				zap.String("path", r.RequestURI),
				zap.Int("status_code", wrapped.statusCode),
				zap.Int("response_bytes", wrapped.size),
				zap.Duration("duration", duration),
				zap.Float64("duration_ms", duration.Seconds()*1000),
				zap.String("remote_addr", r.RemoteAddr),
			}

			// Log based on status code
			if wrapped.statusCode >= 500 {
				logger.Error("HTTP request completed with error", fields...)
			} else if wrapped.statusCode >= 400 {
				logger.Warn("HTTP request completed with warning", fields...)
			} else {
				logger.Info("HTTP request completed", fields...)
			}
		})
	}
}

// loggingResponseWriter wraps http.ResponseWriter to capture status code and size
type loggingResponseWriter struct {
	http.ResponseWriter
	statusCode int
	size       int
	written    bool
}

// WriteHeader captures the status code
func (lrw *loggingResponseWriter) WriteHeader(statusCode int) {
	if !lrw.written {
		lrw.statusCode = statusCode
		lrw.written = true
		lrw.ResponseWriter.WriteHeader(statusCode)
	}
}

// Write captures the response size
func (lrw *loggingResponseWriter) Write(b []byte) (int, error) {
	if !lrw.written {
		lrw.written = true
	}
	lrw.size += len(b)
	return lrw.ResponseWriter.Write(b)
}
