package http

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// MetricsMiddleware tests are covered by integration tests
// as the middleware requires a fully initialized Prometheus metrics registry

func TestMetricsResponseWriter_CapturesStatus(t *testing.T) {
	baseWriter := httptest.NewRecorder()
	mrw := &metricsResponseWriter{ResponseWriter: baseWriter}

	mrw.WriteHeader(http.StatusCreated)

	if mrw.statusCode != http.StatusCreated {
		t.Errorf("expected status 201, got %d", mrw.statusCode)
	}
}

func TestMetricsResponseWriter_AccumulatesSize(t *testing.T) {
	baseWriter := httptest.NewRecorder()
	mrw := &metricsResponseWriter{ResponseWriter: baseWriter}

	n1, _ := mrw.Write([]byte("hello"))
	n2, _ := mrw.Write([]byte(" world"))

	expectedSize := n1 + n2
	if mrw.size != expectedSize {
		t.Errorf("expected size %d, got %d", expectedSize, mrw.size)
	}
}

func TestMetricsResponseWriter_WriteHeaderIdempotent(t *testing.T) {
	baseWriter := httptest.NewRecorder()
	mrw := &metricsResponseWriter{ResponseWriter: baseWriter}

	mrw.WriteHeader(http.StatusOK)
	mrw.WriteHeader(http.StatusInternalServerError)

	if baseWriter.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", baseWriter.Code)
	}
}

func TestMetricsResponseWriter_DefaultStatus(t *testing.T) {
	baseWriter := httptest.NewRecorder()
	mrw := &metricsResponseWriter{ResponseWriter: baseWriter}

	mrw.Write([]byte("test"))

	if baseWriter.Code != http.StatusOK {
		t.Errorf("expected default status 200, got %d", baseWriter.Code)
	}
}
