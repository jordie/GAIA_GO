package errors

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestHandler_Handle_AppError(t *testing.T) {
	handler := NewErrorHandler(false, false)
	appErr := NotFoundErrorf("USER_NOT_FOUND", "User not found")

	recorder := httptest.NewRecorder()
	handler.Handle(recorder, appErr, "trace-123")

	if recorder.Code != http.StatusNotFound {
		t.Errorf("expected status 404, got %d", recorder.Code)
	}

	if recorder.Header().Get("Content-Type") != "application/json" {
		t.Errorf("expected application/json content type")
	}

	var response ErrorResponse
	err := json.NewDecoder(recorder.Body).Decode(&response)
	if err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if response.Error.Code != "USER_NOT_FOUND" {
		t.Errorf("expected code USER_NOT_FOUND")
	}

	if response.TraceID != "trace-123" {
		t.Errorf("expected TraceID trace-123")
	}
}

func TestHandler_Handle_PlainError(t *testing.T) {
	handler := NewErrorHandler(false, false)
	plainErr := New(InternalError, "ERR", "test error")

	recorder := httptest.NewRecorder()
	handler.Handle(recorder, plainErr, "")

	if recorder.Code != http.StatusInternalServerError {
		t.Errorf("expected status 500, got %d", recorder.Code)
	}
}

func TestHandler_Handle_WithStackTrace(t *testing.T) {
	handler := NewErrorHandler(true, false) // includeStackTrace = true
	appErr := New(ValidationError, "INVALID", "validation failed")

	recorder := httptest.NewRecorder()
	handler.Handle(recorder, appErr, "")

	var response ErrorResponse
	json.NewDecoder(recorder.Body).Decode(&response)

	if response.Error.Details == nil {
		t.Fatalf("expected Details map")
	}

	stackTrace, exists := response.Error.Details["stack_trace"]
	if !exists {
		t.Errorf("expected stack_trace in details when includeStackTrace=true")
	}

	if stackTrace == "" {
		t.Errorf("expected non-empty stack_trace")
	}
}

func TestHandler_Handle_WithoutStackTrace(t *testing.T) {
	handler := NewErrorHandler(false, false) // includeStackTrace = false
	appErr := New(ValidationError, "INVALID", "validation failed")

	recorder := httptest.NewRecorder()
	handler.Handle(recorder, appErr, "")

	var response ErrorResponse
	json.NewDecoder(recorder.Body).Decode(&response)

	if response.Error.Details != nil {
		if _, exists := response.Error.Details["stack_trace"]; exists {
			t.Errorf("expected no stack_trace when includeStackTrace=false")
		}
	}
}

func TestHandler_Handle_TraceID(t *testing.T) {
	handler := NewErrorHandler(false, false)
	appErr := New(InternalError, "ERR", "error")

	tests := []struct {
		name    string
		traceID string
	}{
		{
			name:    "with trace id",
			traceID: "trace-123-abc",
		},
		{
			name:    "empty trace id",
			traceID: "",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			recorder := httptest.NewRecorder()
			handler.Handle(recorder, appErr, tc.traceID)

			var response ErrorResponse
			json.NewDecoder(recorder.Body).Decode(&response)

			if tc.traceID != "" {
				if response.TraceID != tc.traceID {
					t.Errorf("expected TraceID %s", tc.traceID)
				}
			} else {
				if response.TraceID != "" {
					t.Errorf("expected empty TraceID for empty input")
				}
			}
		})
	}
}

func TestHandler_HandlePanic(t *testing.T) {
	handler := NewErrorHandler(false, false)

	recorder := httptest.NewRecorder()
	handler.HandlePanic(recorder, "test panic", "trace-panic")

	if recorder.Code != http.StatusInternalServerError {
		t.Errorf("expected status 500, got %d", recorder.Code)
	}

	var response ErrorResponse
	json.NewDecoder(recorder.Body).Decode(&response)

	if response.Error.Code != "PANIC" {
		t.Errorf("expected code PANIC")
	}

	if response.TraceID != "trace-panic" {
		t.Errorf("expected TraceID trace-panic")
	}
}

func TestHandler_HandlePanic_WithValue(t *testing.T) {
	handler := NewErrorHandler(false, false)

	recorder := httptest.NewRecorder()
	handler.HandlePanic(recorder, "critical panic: database down", "trace-123")

	var response ErrorResponse
	json.NewDecoder(recorder.Body).Decode(&response)

	if response.Error.Code != "PANIC" {
		t.Errorf("expected PANIC code")
	}
}

func TestWriteError(t *testing.T) {
	appErr := New(ValidationError, "TEST", "test error")

	recorder := httptest.NewRecorder()
	WriteError(recorder, appErr)

	if recorder.Code != http.StatusBadRequest {
		t.Errorf("expected status 400, got %d", recorder.Code)
	}

	var response ErrorResponse
	json.NewDecoder(recorder.Body).Decode(&response)

	if response.Error.Code != "TEST" {
		t.Errorf("expected code TEST")
	}
}

func TestWriteErrorWithStatus(t *testing.T) {
	recorder := httptest.NewRecorder()
	WriteErrorWithStatus(recorder, http.StatusTeapot, "TEAPOT", "I'm a teapot")

	if recorder.Code != http.StatusTeapot {
		t.Errorf("expected status 418, got %d", recorder.Code)
	}

	var response ErrorResponse
	json.NewDecoder(recorder.Body).Decode(&response)

	if response.Error.Code != "TEAPOT" {
		t.Errorf("expected code TEAPOT")
	}
}

func TestWriteErrorWithCode(t *testing.T) {
	tests := []struct {
		code       string
		expectCode string
		expectDesc string
	}{
		{
			code:       "unauthorized",
			expectCode: "UNAUTHORIZED",
			expectDesc: "Authentication required",
		},
		{
			code:       "forbidden",
			expectCode: "FORBIDDEN",
			expectDesc: "You don't have permission",
		},
		{
			code:       "not_found",
			expectCode: "NOT_FOUND",
			expectDesc: "The requested resource",
		},
		{
			code:       "conflict",
			expectCode: "CONFLICT",
			expectDesc: "conflicts",
		},
		{
			code:       "bad_request",
			expectCode: "BAD_REQUEST",
			expectDesc: "Invalid request",
		},
	}

	for _, tc := range tests {
		t.Run(tc.code, func(t *testing.T) {
			recorder := httptest.NewRecorder()
			WriteErrorWithCode(recorder, tc.code)

			if recorder.Code == 0 {
				t.Errorf("expected non-zero status code")
			}

			var response ErrorResponse
			json.NewDecoder(recorder.Body).Decode(&response)

			if response.Error.Code != tc.expectCode {
				t.Errorf("expected code %s, got %s", tc.expectCode, response.Error.Code)
			}
		})
	}
}

func TestWriteErrorWithCode_UnknownCode(t *testing.T) {
	recorder := httptest.NewRecorder()
	WriteErrorWithCode(recorder, "unknown_code")

	if recorder.Code != http.StatusInternalServerError {
		t.Errorf("expected 500 for unknown code, got %d", recorder.Code)
	}

	var response ErrorResponse
	json.NewDecoder(recorder.Body).Decode(&response)

	if response.Error.Code != "UNKNOWN_ERROR" {
		t.Errorf("expected UNKNOWN_ERROR code")
	}
}

func TestHandler_BuildErrorResponse_Details(t *testing.T) {
	handler := NewErrorHandler(false, false)
	appErr := New(ValidationError, "CODE", "message")
	appErr.WithDetails("field", "email").WithDetails("reason", "invalid format")

	recorder := httptest.NewRecorder()
	handler.Handle(recorder, appErr, "")

	var response ErrorResponse
	json.NewDecoder(recorder.Body).Decode(&response)

	if response.Error.Details["field"] != "email" {
		t.Errorf("expected field detail")
	}

	if response.Error.Details["reason"] != "invalid format" {
		t.Errorf("expected reason detail")
	}
}

func TestHandler_Handle_JSONEncoding(t *testing.T) {
	handler := NewErrorHandler(false, false)
	appErr := New(ValidationError, "TEST_CODE", "Test message")

	recorder := httptest.NewRecorder()
	handler.Handle(recorder, appErr, "trace-id")

	var response ErrorResponse
	err := json.NewDecoder(recorder.Body).Decode(&response)
	if err != nil {
		t.Fatalf("response should be valid JSON: %v", err)
	}

	if response.Error.Type != string(ValidationError) {
		t.Errorf("expected Type to be ValidationError")
	}

	if response.Error.Message != "Test message" {
		t.Errorf("expected Message 'Test message'")
	}
}
