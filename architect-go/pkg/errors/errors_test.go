package errors

import (
	"net/http"
	"strings"
	"testing"
)

func TestErrorTypeToStatusCode(t *testing.T) {
	tests := []struct {
		name       string
		errorType  ErrorType
		statusCode int
	}{
		{
			name:       "validation error",
			errorType:  ValidationError,
			statusCode: http.StatusBadRequest,
		},
		{
			name:       "not found error",
			errorType:  NotFoundError,
			statusCode: http.StatusNotFound,
		},
		{
			name:       "conflict error",
			errorType:  ConflictError,
			statusCode: http.StatusConflict,
		},
		{
			name:       "authentication error",
			errorType:  AuthenticationError,
			statusCode: http.StatusUnauthorized,
		},
		{
			name:       "authorization error",
			errorType:  AuthorizationError,
			statusCode: http.StatusForbidden,
		},
		{
			name:       "internal error",
			errorType:  InternalError,
			statusCode: http.StatusInternalServerError,
		},
		{
			name:       "timeout error",
			errorType:  TimeoutError,
			statusCode: http.StatusRequestTimeout,
		},
		{
			name:       "database error",
			errorType:  DatabaseError,
			statusCode: http.StatusInternalServerError,
		},
		{
			name:       "external service error",
			errorType:  ExternalServiceError,
			statusCode: http.StatusBadGateway,
		},
		{
			name:       "rate limit error",
			errorType:  RateLimitError,
			statusCode: http.StatusTooManyRequests,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			code := ErrorTypeToStatusCode(tc.errorType)
			if code != tc.statusCode {
				t.Errorf("expected status %d, got %d", tc.statusCode, code)
			}
		})
	}
}

func TestErrorTypeToStatusCode_Unknown(t *testing.T) {
	code := ErrorTypeToStatusCode(ErrorType("unknown"))
	if code != http.StatusInternalServerError {
		t.Errorf("unknown error type should map to 500, got %d", code)
	}
}

func TestNew_FieldsSet(t *testing.T) {
	errorType := ValidationError
	code := "INVALID_INPUT"
	message := "Input is invalid"

	appErr := New(errorType, code, message)

	if appErr.Type != errorType {
		t.Errorf("expected Type %s, got %s", errorType, appErr.Type)
	}

	if appErr.Code != code {
		t.Errorf("expected Code %s, got %s", code, appErr.Code)
	}

	if appErr.Message != message {
		t.Errorf("expected Message %s, got %s", message, appErr.Message)
	}

	if appErr.StatusCode != http.StatusBadRequest {
		t.Errorf("expected StatusCode 400, got %d", appErr.StatusCode)
	}

	if appErr.Details == nil {
		t.Errorf("expected Details map to be initialized")
	}

	if appErr.StackTrace == "" {
		t.Errorf("expected non-empty StackTrace")
	}
}

func TestNewWithStatus_OverridesStatus(t *testing.T) {
	appErr := NewWithStatus(ValidationError, "CODE", "message", http.StatusTeapot)

	if appErr.StatusCode != http.StatusTeapot {
		t.Errorf("expected StatusCode 418, got %d", appErr.StatusCode)
	}
}

func TestAppError_Wrap(t *testing.T) {
	appErr := New(InternalError, "ERR", "message")

	innerErr := New(ValidationError, "INNER", "inner")
	result := appErr.Wrap(innerErr)

	if appErr.Err != innerErr {
		t.Errorf("expected Err to be set")
	}

	if result != appErr {
		t.Errorf("expected Wrap to return same pointer")
	}
}

func TestAppError_WithDetails(t *testing.T) {
	appErr := New(ValidationError, "CODE", "message")

	result := appErr.WithDetails("field", "username").WithDetails("reason", "already exists")

	if appErr.Details["field"] != "username" {
		t.Errorf("expected field=username in details")
	}

	if appErr.Details["reason"] != "already exists" {
		t.Errorf("expected reason='already exists' in details")
	}

	if result != appErr {
		t.Errorf("expected WithDetails to return same pointer")
	}
}

func TestAppError_WithDetailsMap(t *testing.T) {
	appErr := New(ValidationError, "CODE", "message")

	detailsMap := map[string]interface{}{
		"field1": "value1",
		"field2": 42,
		"field3": true,
	}

	result := appErr.WithDetailsMap(detailsMap)

	for key, val := range detailsMap {
		if appErr.Details[key] != val {
			t.Errorf("expected %s=%v in details", key, val)
		}
	}

	if result != appErr {
		t.Errorf("expected WithDetailsMap to return same pointer")
	}
}

func TestAppError_Error_WithoutWrap(t *testing.T) {
	appErr := New(ValidationError, "INVALID", "Input is invalid")

	msg := appErr.Error()

	if !strings.Contains(msg, "INVALID") {
		t.Errorf("expected code in error message")
	}

	if !strings.Contains(msg, "Input is invalid") {
		t.Errorf("expected message in error message")
	}

	if strings.Contains(msg, "(") {
		t.Errorf("expected no wrapped error notation")
	}
}

func TestAppError_Error_WithWrap(t *testing.T) {
	appErr := New(InternalError, "DB_ERROR", "Database operation failed")

	wrappedErr := New(ValidationError, "INNER", "validation failed")
	appErr.Wrap(wrappedErr)

	msg := appErr.Error()

	if !strings.Contains(msg, "DB_ERROR") {
		t.Errorf("expected code in error message")
	}

	if !strings.Contains(msg, "Database operation failed") {
		t.Errorf("expected message in error message")
	}

	// Verify wrapped error is included (format: "CODE: message (error)")
	if !strings.Contains(msg, "(") {
		t.Errorf("expected wrapped error notation in message")
	}
}

func TestIsAppError(t *testing.T) {
	appErr := New(ValidationError, "CODE", "message")

	if !IsAppError(appErr) {
		t.Errorf("expected IsAppError to return true for *AppError")
	}

	if IsAppError(nil) {
		t.Errorf("expected IsAppError to return false for nil")
	}

	plainErr := New(InternalError, "CODE", "message")
	if !IsAppError(plainErr) {
		t.Errorf("expected IsAppError to return true for AppError pointer")
	}
}

func TestAsAppError(t *testing.T) {
	appErr := New(ValidationError, "CODE", "message")

	result := AsAppError(appErr)

	if result != appErr {
		t.Errorf("expected AsAppError to return same pointer")
	}

	if AsAppError(nil) != nil {
		t.Errorf("expected AsAppError to return nil for nil input")
	}

	if AsAppError(New(InternalError, "C", "m")) == nil {
		t.Errorf("expected non-nil for AppError")
	}
}

func TestConstructorHelpers_ValidationError(t *testing.T) {
	appErr := ValidationErrorf("INVALID_EMAIL", "Invalid email: %s", "test")

	if appErr.Type != ValidationError {
		t.Errorf("expected ValidationError type")
	}

	if appErr.Code != "INVALID_EMAIL" {
		t.Errorf("expected code INVALID_EMAIL")
	}

	if !strings.Contains(appErr.Message, "test") {
		t.Errorf("expected formatted message")
	}
}

func TestConstructorHelpers_NotFoundError(t *testing.T) {
	appErr := NotFoundErrorf("USER_NOT_FOUND", "User %d not found", 123)

	if appErr.Type != NotFoundError {
		t.Errorf("expected NotFoundError type")
	}

	if appErr.StatusCode != http.StatusNotFound {
		t.Errorf("expected 404 status")
	}
}

func TestConstructorHelpers_ConflictError(t *testing.T) {
	appErr := ConflictErrorf("DUPLICATE_USER", "User %s already exists", "john")

	if appErr.Type != ConflictError {
		t.Errorf("expected ConflictError type")
	}

	if appErr.StatusCode != http.StatusConflict {
		t.Errorf("expected 409 status")
	}
}

func TestConstructorHelpers_AuthenticationError(t *testing.T) {
	appErr := AuthenticationErrorf("INVALID_CREDS", "Invalid credentials")

	if appErr.Type != AuthenticationError {
		t.Errorf("expected AuthenticationError type")
	}

	if appErr.StatusCode != http.StatusUnauthorized {
		t.Errorf("expected 401 status")
	}
}

func TestConstructorHelpers_AuthorizationError(t *testing.T) {
	appErr := AuthorizationErrorf("ACCESS_DENIED", "You don't have permission")

	if appErr.Type != AuthorizationError {
		t.Errorf("expected AuthorizationError type")
	}

	if appErr.StatusCode != http.StatusForbidden {
		t.Errorf("expected 403 status")
	}
}

func TestConstructorHelpers_InternalError(t *testing.T) {
	appErr := InternalErrorf("SYSTEM_ERROR", "System error occurred")

	if appErr.Type != InternalError {
		t.Errorf("expected InternalError type")
	}

	if appErr.StatusCode != http.StatusInternalServerError {
		t.Errorf("expected 500 status")
	}
}

func TestConstructorHelpers_DatabaseError(t *testing.T) {
	appErr := DatabaseErrorf("DB_CONN_ERROR", "Database connection failed")

	if appErr.Type != DatabaseError {
		t.Errorf("expected DatabaseError type")
	}

	if appErr.StatusCode != http.StatusInternalServerError {
		t.Errorf("expected 500 status")
	}
}

func TestConstructorHelpers_ExternalServiceError(t *testing.T) {
	appErr := ExternalServiceErrorf("PAYMENT_FAILED", "Payment service error")

	if appErr.Type != ExternalServiceError {
		t.Errorf("expected ExternalServiceError type")
	}

	if appErr.StatusCode != http.StatusBadGateway {
		t.Errorf("expected 502 status")
	}
}

func TestConstructorHelpers_TimeoutError(t *testing.T) {
	appErr := TimeoutErrorf("REQUEST_TIMEOUT", "Request timed out")

	if appErr.Type != TimeoutError {
		t.Errorf("expected TimeoutError type")
	}

	if appErr.StatusCode != http.StatusRequestTimeout {
		t.Errorf("expected 408 status")
	}
}

func TestConstructorHelpers_RateLimitError(t *testing.T) {
	appErr := RateLimitErrorf("TOO_MANY_REQUESTS", "Rate limit exceeded")

	if appErr.Type != RateLimitError {
		t.Errorf("expected RateLimitError type")
	}

	if appErr.StatusCode != http.StatusTooManyRequests {
		t.Errorf("expected 429 status")
	}
}
