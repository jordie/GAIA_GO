package websocket

import (
	"net/http/httptest"
	"testing"
)

// TestExtractTokenFromQuery tests extracting token from query parameter
func TestExtractTokenFromQuery(t *testing.T) {
	r := httptest.NewRequest("GET", "/?token=test-token-123", nil)
	token := extractWSToken(r)

	if token != "test-token-123" {
		t.Errorf("expected token 'test-token-123', got '%s'", token)
	}
}

// TestExtractTokenFromHeader tests extracting token from Authorization header
func TestExtractTokenFromHeader(t *testing.T) {
	r := httptest.NewRequest("GET", "/", nil)
	r.Header.Set("Authorization", "Bearer test-token-456")
	token := extractWSToken(r)

	if token != "test-token-456" {
		t.Errorf("expected token 'test-token-456', got '%s'", token)
	}
}

// TestExtractTokenPrefersQuery tests that query parameter takes precedence
func TestExtractTokenPrefersQuery(t *testing.T) {
	r := httptest.NewRequest("GET", "/?token=query-token", nil)
	r.Header.Set("Authorization", "Bearer header-token")
	token := extractWSToken(r)

	if token != "query-token" {
		t.Errorf("expected query token to take precedence, got '%s'", token)
	}
}

// TestExtractTokenEmpty tests extracting token when none provided
func TestExtractTokenEmpty(t *testing.T) {
	r := httptest.NewRequest("GET", "/", nil)
	token := extractWSToken(r)

	if token != "" {
		t.Errorf("expected empty token, got '%s'", token)
	}
}

// TestExtractTokenBadAuthHeader tests handling invalid Authorization header
func TestExtractTokenBadAuthHeader(t *testing.T) {
	r := httptest.NewRequest("GET", "/", nil)
	r.Header.Set("Authorization", "Basic dXNlcjpwYXNz")
	token := extractWSToken(r)

	if token != "" {
		t.Errorf("expected empty token for non-Bearer auth, got '%s'", token)
	}
}

// TestExtractTokenShortAuthHeader tests handling short Authorization header
func TestExtractTokenShortAuthHeader(t *testing.T) {
	r := httptest.NewRequest("GET", "/", nil)
	r.Header.Set("Authorization", "x")
	token := extractWSToken(r)

	if token != "" {
		t.Errorf("expected empty token for short header, got '%s'", token)
	}
}


// TestWebSocketAuthMissingToken tests that missing token is detected
func TestWebSocketAuthMissingToken(t *testing.T) {
	// Create test request without token
	r := httptest.NewRequest("GET", "/ws", nil)

	// Verify token is empty
	if token := extractWSToken(r); token != "" {
		t.Errorf("expected empty token, got %s", token)
	}
}

// TestWebSocketAuthInvalidToken tests that invalid token is extracted
func TestWebSocketAuthInvalidToken(t *testing.T) {
	r := httptest.NewRequest("GET", "/?token=invalid-token", nil)

	token := extractWSToken(r)
	if token == "" {
		t.Error("expected token to be extracted")
	}

	// Verify token was extracted correctly
	if token != "invalid-token" {
		t.Errorf("expected invalid-token, got %s", token)
	}
}

// TestWebSocketTokenInQueryParam tests valid token in query parameter
func TestWebSocketTokenInQueryParam(t *testing.T) {
	r := httptest.NewRequest("GET", "/?token=valid-token-123", nil)
	token := extractWSToken(r)

	if token != "valid-token-123" {
		t.Errorf("expected valid-token-123, got %s", token)
	}
}

// TestWebSocketTokenInHeader tests valid token in Authorization header
func TestWebSocketTokenInHeader(t *testing.T) {
	r := httptest.NewRequest("GET", "/ws", nil)
	r.Header.Set("Authorization", "Bearer valid-token-456")
	token := extractWSToken(r)

	if token != "valid-token-456" {
		t.Errorf("expected valid-token-456, got %s", token)
	}
}
