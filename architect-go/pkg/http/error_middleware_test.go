package http

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"architect-go/pkg/errors"
)

func TestRecoveryMiddleware_CatchesPanic(t *testing.T) {
	errorHandler := errors.NewErrorHandler(false, false)

	middleware := RecoveryMiddleware(errorHandler)
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		panic("test panic")
	}))

	req := httptest.NewRequest("GET", "/", nil)
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusInternalServerError {
		t.Errorf("expected status 500, got %d", recorder.Code)
	}

	if recorder.Header().Get("Content-Type") != "application/json" {
		t.Errorf("expected content-type application/json")
	}
}

func TestRecoveryMiddleware_PassesThrough(t *testing.T) {
	errorHandler := errors.NewErrorHandler(false, false)

	middleware := RecoveryMiddleware(errorHandler)
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("success"))
	}))

	req := httptest.NewRequest("GET", "/", nil)
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", recorder.Code)
	}
}

func TestErrorHandlingMiddleware_200(t *testing.T) {
	errorHandler := errors.NewErrorHandler(false, false)

	middleware := ErrorHandlingMiddleware(errorHandler)
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("success"))
	}))

	req := httptest.NewRequest("GET", "/", nil)
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", recorder.Code)
	}
}

func TestErrorHandlingMiddleware_500(t *testing.T) {
	errorHandler := errors.NewErrorHandler(false, false)

	middleware := ErrorHandlingMiddleware(errorHandler)
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("error"))
	}))

	req := httptest.NewRequest("GET", "/", nil)
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusInternalServerError {
		t.Errorf("expected status 500, got %d", recorder.Code)
	}
}

func TestResponseWriter_WriteHeaderIdempotent(t *testing.T) {
	baseWriter := httptest.NewRecorder()
	rw := &responseWriter{ResponseWriter: baseWriter}

	rw.WriteHeader(http.StatusOK)
	rw.WriteHeader(http.StatusInternalServerError) // Should be ignored

	if baseWriter.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", baseWriter.Code)
	}
}

func TestResponseWriter_DefaultStatus(t *testing.T) {
	baseWriter := httptest.NewRecorder()
	rw := &responseWriter{ResponseWriter: baseWriter}

	// Write without calling WriteHeader
	rw.Write([]byte("test"))

	if baseWriter.Code != http.StatusOK {
		t.Errorf("expected default status 200, got %d", baseWriter.Code)
	}
}

func TestResponseWriter_CapturesStatusCode(t *testing.T) {
	baseWriter := httptest.NewRecorder()
	rw := &responseWriter{ResponseWriter: baseWriter}

	rw.WriteHeader(http.StatusNotFound)

	if rw.statusCode != http.StatusNotFound {
		t.Errorf("expected status 404, got %d", rw.statusCode)
	}
}
