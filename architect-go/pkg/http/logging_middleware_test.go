package http

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"architect-go/pkg/logging"
)

func TestRequestLoggingMiddleware_2xx(t *testing.T) {
	logger, err := logging.NewLogger(logging.InfoLevel, "text")
	if err != nil {
		t.Fatalf("failed to create logger: %v", err)
	}

	middleware := RequestLoggingMiddleware(logger)
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("success"))
	}))

	req := httptest.NewRequest("GET", "/api/users", nil)
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", recorder.Code)
	}

	if recorder.Body.String() != "success" {
		t.Errorf("expected body 'success', got %s", recorder.Body.String())
	}
}

func TestRequestLoggingMiddleware_4xx(t *testing.T) {
	logger, _ := logging.NewLogger(logging.InfoLevel, "text")

	middleware := RequestLoggingMiddleware(logger)
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte("bad request"))
	}))

	req := httptest.NewRequest("POST", "/api/users", nil)
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusBadRequest {
		t.Errorf("expected status 400, got %d", recorder.Code)
	}
}

func TestRequestLoggingMiddleware_5xx(t *testing.T) {
	logger, _ := logging.NewLogger(logging.InfoLevel, "text")

	middleware := RequestLoggingMiddleware(logger)
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("error"))
	}))

	req := httptest.NewRequest("DELETE", "/api/users/123", nil)
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusInternalServerError {
		t.Errorf("expected status 500, got %d", recorder.Code)
	}
}

func TestRequestLoggingMiddleware_DefaultStatus200(t *testing.T) {
	logger, _ := logging.NewLogger(logging.InfoLevel, "text")

	middleware := RequestLoggingMiddleware(logger)
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Don't call WriteHeader, should default to 200
		w.Write([]byte("data"))
	}))

	req := httptest.NewRequest("GET", "/api/data", nil)
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Errorf("expected default status 200, got %d", recorder.Code)
	}
}

func TestLoggingResponseWriter_AccumulatesSize(t *testing.T) {
	baseWriter := httptest.NewRecorder()
	lrw := &loggingResponseWriter{ResponseWriter: baseWriter}

	// First write
	n1, err := lrw.Write([]byte("hello"))
	if err != nil {
		t.Fatalf("first write failed: %v", err)
	}

	// Second write
	n2, err := lrw.Write([]byte(" world"))
	if err != nil {
		t.Fatalf("second write failed: %v", err)
	}

	expectedSize := n1 + n2
	if lrw.size != expectedSize {
		t.Errorf("expected size %d, got %d", expectedSize, lrw.size)
	}

	if baseWriter.Body.String() != "hello world" {
		t.Errorf("expected body 'hello world', got %s", baseWriter.Body.String())
	}
}

func TestLoggingResponseWriter_WriteHeaderIdempotent(t *testing.T) {
	baseWriter := httptest.NewRecorder()
	lrw := &loggingResponseWriter{ResponseWriter: baseWriter}

	lrw.WriteHeader(http.StatusOK)
	lrw.WriteHeader(http.StatusInternalServerError) // Should be ignored

	if baseWriter.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", baseWriter.Code)
	}
}

func TestLoggingResponseWriter_DefaultStatus(t *testing.T) {
	baseWriter := httptest.NewRecorder()
	lrw := &loggingResponseWriter{ResponseWriter: baseWriter}

	lrw.Write([]byte("test"))

	if baseWriter.Code != http.StatusOK {
		t.Errorf("expected default status 200, got %d", baseWriter.Code)
	}
}

func TestLoggingResponseWriter_MultipleWrites(t *testing.T) {
	baseWriter := httptest.NewRecorder()
	lrw := &loggingResponseWriter{ResponseWriter: baseWriter}

	writes := []string{"hello", " ", "world", "!"}
	totalSize := 0

	for _, w := range writes {
		n, err := lrw.Write([]byte(w))
		if err != nil {
			t.Fatalf("write failed: %v", err)
		}
		totalSize += n
	}

	if lrw.size != totalSize {
		t.Errorf("expected size %d, got %d", totalSize, lrw.size)
	}

	if baseWriter.Body.String() != "hello world!" {
		t.Errorf("expected body 'hello world!', got %s", baseWriter.Body.String())
	}
}
