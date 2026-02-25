package middleware

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	apperrors "architect-go/pkg/errors"
	"architect-go/pkg/models"
)

// Mock SessionManager for testing
type mockSessionManager struct {
	validateSessionFunc func(ctx context.Context, token string) (*models.User, error)
}

func (m *mockSessionManager) ValidateSession(ctx context.Context, token string) (*models.User, error) {
	if m.validateSessionFunc != nil {
		return m.validateSessionFunc(ctx, token)
	}
	return nil, apperrors.AuthenticationErrorf("INVALID", "mock not configured")
}

func (m *mockSessionManager) Login(ctx context.Context, username, password string) (string, error) {
	return "", nil
}

func (m *mockSessionManager) Logout(ctx context.Context, token string) error {
	return nil
}

func (m *mockSessionManager) RefreshToken(ctx context.Context, token string) (string, error) {
	return "", nil
}

func (m *mockSessionManager) CleanupExpiredSessions(ctx context.Context) error {
	return nil
}

// Test helper: create a test handler that checks context
func testContextHandler(t *testing.T, expectedUserID string) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		userID := UserIDFromContext(r.Context())
		if userID != expectedUserID {
			t.Errorf("expected userID %q, got %q", expectedUserID, userID)
		}

		user := UserFromContext(r.Context())
		if expectedUserID != "" && user == nil {
			t.Errorf("expected user object, got nil")
		}

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok", "user_id": userID})
	})
}

func TestRequireAuth_ValidToken(t *testing.T) {
	// Setup
	sessionMgr := &mockSessionManager{
		validateSessionFunc: func(ctx context.Context, token string) (*models.User, error) {
			if token == "valid-token" {
				return &models.User{
					ID:       "user123",
					Username: "testuser",
					Email:    "test@example.com",
				}, nil
			}
			return nil, apperrors.AuthenticationErrorf("INVALID", "invalid token")
		},
	}

	errHandler := apperrors.NewErrorHandler(false, false)
	middleware := RequireAuth(sessionMgr, errHandler)
	handler := middleware(testContextHandler(t, "user123"))

	// Execute
	req := httptest.NewRequest("GET", "http://example.com/api/test", nil)
	req.Header.Set("Authorization", "Bearer valid-token")
	w := httptest.NewRecorder()

	handler.ServeHTTP(w, req)

	// Verify
	if w.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, w.Code)
	}
}

func TestRequireAuth_NoToken(t *testing.T) {
	// Setup
	sessionMgr := &mockSessionManager{}
	errHandler := apperrors.NewErrorHandler(false, false)
	middleware := RequireAuth(sessionMgr, errHandler)
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	// Execute - no Authorization header, no session_token cookie
	req := httptest.NewRequest("GET", "http://example.com/api/test", nil)
	w := httptest.NewRecorder()

	handler.ServeHTTP(w, req)

	// Verify - should be 401
	if w.Code != http.StatusUnauthorized {
		t.Errorf("expected status %d, got %d", http.StatusUnauthorized, w.Code)
	}
}

func TestRequireAuth_InvalidToken(t *testing.T) {
	// Setup
	sessionMgr := &mockSessionManager{
		validateSessionFunc: func(ctx context.Context, token string) (*models.User, error) {
			return nil, apperrors.AuthenticationErrorf("INVALID", "token not found")
		},
	}

	errHandler := apperrors.NewErrorHandler(false, false)
	middleware := RequireAuth(sessionMgr, errHandler)
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	// Execute
	req := httptest.NewRequest("GET", "http://example.com/api/test", nil)
	req.Header.Set("Authorization", "Bearer invalid-token")
	w := httptest.NewRecorder()

	handler.ServeHTTP(w, req)

	// Verify - should be 401
	if w.Code != http.StatusUnauthorized {
		t.Errorf("expected status %d, got %d", http.StatusUnauthorized, w.Code)
	}
}

func TestRequireAuth_ExpiredToken(t *testing.T) {
	// Setup
	sessionMgr := &mockSessionManager{
		validateSessionFunc: func(ctx context.Context, token string) (*models.User, error) {
			if token == "expired-token" {
				return nil, apperrors.AuthenticationErrorf("EXPIRED", "session expired")
			}
			return nil, apperrors.AuthenticationErrorf("INVALID", "invalid token")
		},
	}

	errHandler := apperrors.NewErrorHandler(false, false)
	middleware := RequireAuth(sessionMgr, errHandler)
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	// Execute
	req := httptest.NewRequest("GET", "http://example.com/api/test", nil)
	req.Header.Set("Authorization", "Bearer expired-token")
	w := httptest.NewRecorder()

	handler.ServeHTTP(w, req)

	// Verify - should be 401
	if w.Code != http.StatusUnauthorized {
		t.Errorf("expected status %d, got %d", http.StatusUnauthorized, w.Code)
	}
}

func TestRequireAuth_BearerPrefixStripped(t *testing.T) {
	// Setup
	sessionMgr := &mockSessionManager{
		validateSessionFunc: func(ctx context.Context, token string) (*models.User, error) {
			// Token passed to ValidateSession should be without "Bearer " prefix
			if token == "abc123" {
				return &models.User{
					ID:       "user456",
					Username: "anotheruser",
					Email:    "another@example.com",
				}, nil
			}
			return nil, apperrors.AuthenticationErrorf("INVALID", "invalid token")
		},
	}

	errHandler := apperrors.NewErrorHandler(false, false)
	middleware := RequireAuth(sessionMgr, errHandler)
	handler := middleware(testContextHandler(t, "user456"))

	// Execute - with "Bearer " prefix
	req := httptest.NewRequest("GET", "http://example.com/api/test", nil)
	req.Header.Set("Authorization", "Bearer abc123")
	w := httptest.NewRecorder()

	handler.ServeHTTP(w, req)

	// Verify
	if w.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, w.Code)
	}
}

func TestRequireAuth_XAuthTokenFallback(t *testing.T) {
	// Setup
	sessionMgr := &mockSessionManager{
		validateSessionFunc: func(ctx context.Context, token string) (*models.User, error) {
			if token == "x-auth-token-123" {
				return &models.User{
					ID:       "user789",
					Username: "xauthuser",
					Email:    "xauth@example.com",
				}, nil
			}
			return nil, apperrors.AuthenticationErrorf("INVALID", "invalid token")
		},
	}

	errHandler := apperrors.NewErrorHandler(false, false)
	middleware := RequireAuth(sessionMgr, errHandler)
	handler := middleware(testContextHandler(t, "user789"))

	// Execute - using X-Auth-Token header
	req := httptest.NewRequest("GET", "http://example.com/api/test", nil)
	req.Header.Set("X-Auth-Token", "x-auth-token-123")
	w := httptest.NewRecorder()

	handler.ServeHTTP(w, req)

	// Verify
	if w.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, w.Code)
	}
}

func TestRequireAuth_SessionTokenCookie(t *testing.T) {
	// Setup
	sessionMgr := &mockSessionManager{
		validateSessionFunc: func(ctx context.Context, token string) (*models.User, error) {
			if token == "cookie-token" {
				return &models.User{
					ID:       "user-cookie",
					Username: "cookieuser",
					Email:    "cookie@example.com",
				}, nil
			}
			return nil, apperrors.AuthenticationErrorf("INVALID", "invalid token")
		},
	}

	errHandler := apperrors.NewErrorHandler(false, false)
	middleware := RequireAuth(sessionMgr, errHandler)
	handler := middleware(testContextHandler(t, "user-cookie"))

	// Execute - using session_token cookie
	req := httptest.NewRequest("GET", "http://example.com/api/test", nil)
	req.AddCookie(&http.Cookie{
		Name:    "session_token",
		Value:   "cookie-token",
		Expires: time.Now().Add(24 * time.Hour),
	})
	w := httptest.NewRecorder()

	handler.ServeHTTP(w, req)

	// Verify
	if w.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, w.Code)
	}
}

func TestUserIDFromContext_WhenSet(t *testing.T) {
	ctx := context.WithValue(context.Background(), UserIDKey, "test-user-id")
	userID := UserIDFromContext(ctx)
	if userID != "test-user-id" {
		t.Errorf("expected userID 'test-user-id', got '%s'", userID)
	}
}

func TestUserIDFromContext_WhenNotSet(t *testing.T) {
	ctx := context.Background()
	userID := UserIDFromContext(ctx)
	if userID != "" {
		t.Errorf("expected empty userID, got '%s'", userID)
	}
}

func TestUsernameFromContext_WhenSet(t *testing.T) {
	ctx := context.WithValue(context.Background(), UsernameKey, "testuser")
	username := UsernameFromContext(ctx)
	if username != "testuser" {
		t.Errorf("expected username 'testuser', got '%s'", username)
	}
}

func TestUsernameFromContext_WhenNotSet(t *testing.T) {
	ctx := context.Background()
	username := UsernameFromContext(ctx)
	if username != "" {
		t.Errorf("expected empty username, got '%s'", username)
	}
}

func TestEmailFromContext_WhenSet(t *testing.T) {
	ctx := context.WithValue(context.Background(), EmailKey, "test@example.com")
	email := EmailFromContext(ctx)
	if email != "test@example.com" {
		t.Errorf("expected email 'test@example.com', got '%s'", email)
	}
}

func TestEmailFromContext_WhenNotSet(t *testing.T) {
	ctx := context.Background()
	email := EmailFromContext(ctx)
	if email != "" {
		t.Errorf("expected empty email, got '%s'", email)
	}
}

func TestUserFromContext_WhenSet(t *testing.T) {
	expectedUser := &models.User{
		ID:       "user123",
		Username: "testuser",
		Email:    "test@example.com",
	}
	ctx := context.WithValue(context.Background(), UserKey, expectedUser)
	user := UserFromContext(ctx)
	if user == nil {
		t.Errorf("expected user object, got nil")
	}
	if user.ID != expectedUser.ID {
		t.Errorf("expected user ID '%s', got '%s'", expectedUser.ID, user.ID)
	}
}

func TestUserFromContext_WhenNotSet(t *testing.T) {
	ctx := context.Background()
	user := UserFromContext(ctx)
	if user != nil {
		t.Errorf("expected nil user, got %v", user)
	}
}

func TestExtractToken_AuthorizationHeader(t *testing.T) {
	req := httptest.NewRequest("GET", "http://example.com", nil)
	req.Header.Set("Authorization", "Bearer my-token-123")
	token := extractToken(req)
	if token != "my-token-123" {
		t.Errorf("expected token 'my-token-123', got '%s'", token)
	}
}

func TestExtractToken_XAuthTokenHeader(t *testing.T) {
	req := httptest.NewRequest("GET", "http://example.com", nil)
	req.Header.Set("X-Auth-Token", "x-token-456")
	token := extractToken(req)
	if token != "x-token-456" {
		t.Errorf("expected token 'x-token-456', got '%s'", token)
	}
}

func TestExtractToken_NoToken(t *testing.T) {
	req := httptest.NewRequest("GET", "http://example.com", nil)
	token := extractToken(req)
	if token != "" {
		t.Errorf("expected empty token, got '%s'", token)
	}
}

func TestExtractToken_InvalidBearerFormat(t *testing.T) {
	req := httptest.NewRequest("GET", "http://example.com", nil)
	req.Header.Set("Authorization", "BadBearer token")
	token := extractToken(req)
	if token != "" {
		t.Errorf("expected empty token for invalid format, got '%s'", token)
	}
}
