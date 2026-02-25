package http

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"architect-go/pkg/auth"
	"architect-go/pkg/models"
)

// mockUserRepoForAuth implements repository.UserRepository
type mockUserRepoForAuth struct {
	getByUsernameFunc func(ctx context.Context, username string) (*models.User, error)
	getFunc           func(ctx context.Context, id string) (*models.User, error)
	updateFunc        func(ctx context.Context, user *models.User) error
	createFunc        func(ctx context.Context, user *models.User) error
	listFunc          func(ctx context.Context, limit int, offset int) ([]*models.User, int64, error)
	getByEmailFunc    func(ctx context.Context, email string) (*models.User, error)
	deleteFunc        func(ctx context.Context, id string) error
}

func (m *mockUserRepoForAuth) GetByUsername(ctx context.Context, username string) (*models.User, error) {
	return m.getByUsernameFunc(ctx, username)
}

func (m *mockUserRepoForAuth) Get(ctx context.Context, id string) (*models.User, error) {
	return m.getFunc(ctx, id)
}

func (m *mockUserRepoForAuth) Update(ctx context.Context, user *models.User) error {
	if m.updateFunc == nil {
		return nil
	}
	return m.updateFunc(ctx, user)
}

func (m *mockUserRepoForAuth) Create(ctx context.Context, user *models.User) error {
	return m.createFunc(ctx, user)
}

func (m *mockUserRepoForAuth) List(ctx context.Context, limit int, offset int) ([]*models.User, int64, error) {
	return m.listFunc(ctx, limit, offset)
}

func (m *mockUserRepoForAuth) GetByEmail(ctx context.Context, email string) (*models.User, error) {
	return m.getByEmailFunc(ctx, email)
}

func (m *mockUserRepoForAuth) Delete(ctx context.Context, id string) error {
	return m.deleteFunc(ctx, id)
}

// mockSessionRepoForAuth implements repository.SessionRepository
type mockSessionRepoForAuth struct {
	createFunc        func(ctx context.Context, session *models.Session) error
	getByTokenFunc    func(ctx context.Context, token string) (*models.Session, error)
	deleteFunc        func(ctx context.Context, id string) error
	deleteExpiredFunc func(ctx context.Context) error
	listByUserFunc    func(ctx context.Context, userID string) ([]*models.Session, error)
	updateFunc        func(ctx context.Context, session *models.Session) error
	getFunc           func(ctx context.Context, id string) (*models.Session, error)
}

func (m *mockSessionRepoForAuth) Create(ctx context.Context, session *models.Session) error {
	return m.createFunc(ctx, session)
}

func (m *mockSessionRepoForAuth) GetByToken(ctx context.Context, token string) (*models.Session, error) {
	return m.getByTokenFunc(ctx, token)
}

func (m *mockSessionRepoForAuth) Delete(ctx context.Context, id string) error {
	return m.deleteFunc(ctx, id)
}

func (m *mockSessionRepoForAuth) DeleteExpired(ctx context.Context) error {
	return m.deleteExpiredFunc(ctx)
}

func (m *mockSessionRepoForAuth) ListByUser(ctx context.Context, userID string) ([]*models.Session, error) {
	return m.listByUserFunc(ctx, userID)
}

func (m *mockSessionRepoForAuth) Update(ctx context.Context, session *models.Session) error {
	return m.updateFunc(ctx, session)
}

func (m *mockSessionRepoForAuth) Get(ctx context.Context, id string) (*models.Session, error) {
	return m.getFunc(ctx, id)
}

func TestAuthMiddleware_ValidBearerToken(t *testing.T) {
	pm := auth.NewPasswordManager()

	mockUserRepo := &mockUserRepoForAuth{
		getFunc: func(ctx context.Context, id string) (*models.User, error) {
			return &models.User{
				ID:       "user123",
				Username: "testuser",
				Email:    "user@example.com",
				Status:   "active",
			}, nil
		},
	}

	token := "valid-token"
	mockSessionRepo := &mockSessionRepoForAuth{
		getByTokenFunc: func(ctx context.Context, t string) (*models.Session, error) {
			return &models.Session{
				ID:        "session123",
				UserID:    "user123",
				Token:     token,
				ExpiresAt: time.Now().Add(24 * time.Hour),
			}, nil
		},
	}

	tm := auth.NewTokenManager("secret", 24*time.Hour, "test-issuer")
	sessionMgr := auth.NewSessionManager(mockUserRepo, mockSessionRepo, pm, tm, 24*time.Hour)

	validToken, _ := tm.GenerateToken("user123", "user@example.com", "user")

	middleware := AuthMiddleware(sessionMgr)
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest("GET", "/protected", nil)
	req.Header.Set("Authorization", "Bearer "+validToken)
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", recorder.Code)
	}
}

func TestAuthMiddleware_ValidCookieToken(t *testing.T) {
	pm := auth.NewPasswordManager()
	mockUserRepo := &mockUserRepoForAuth{
		getFunc: func(ctx context.Context, id string) (*models.User, error) {
			return &models.User{
				ID:     "user123",
				Status: "active",
			}, nil
		},
	}

	mockSessionRepo := &mockSessionRepoForAuth{
		getByTokenFunc: func(ctx context.Context, token string) (*models.Session, error) {
			return &models.Session{
				ID:        "session123",
				UserID:    "user123",
				ExpiresAt: time.Now().Add(24 * time.Hour),
			}, nil
		},
	}

	tm := auth.NewTokenManager("secret", 24*time.Hour, "test-issuer")
	sessionMgr := auth.NewSessionManager(mockUserRepo, mockSessionRepo, pm, tm, 24*time.Hour)

	validToken, _ := tm.GenerateToken("user123", "user@example.com", "user")

	middleware := AuthMiddleware(sessionMgr)
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest("GET", "/protected", nil)
	req.AddCookie(&http.Cookie{
		Name:  "session_token",
		Value: validToken,
	})
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", recorder.Code)
	}
}

func TestAuthMiddleware_MissingToken(t *testing.T) {
	pm := auth.NewPasswordManager()
	mockUserRepo := &mockUserRepoForAuth{}
	mockSessionRepo := &mockSessionRepoForAuth{}
	tm := auth.NewTokenManager("secret", 24*time.Hour, "test-issuer")
	sessionMgr := auth.NewSessionManager(mockUserRepo, mockSessionRepo, pm, tm, 24*time.Hour)

	middleware := AuthMiddleware(sessionMgr)
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest("GET", "/protected", nil)
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusUnauthorized {
		t.Errorf("expected status 401, got %d", recorder.Code)
	}

	if recorder.Header().Get("Content-Type") != "application/json" {
		t.Errorf("expected content-type application/json")
	}
}

func TestAuthMiddleware_InvalidToken(t *testing.T) {
	pm := auth.NewPasswordManager()
	mockUserRepo := &mockUserRepoForAuth{}
	mockSessionRepo := &mockSessionRepoForAuth{}
	tm := auth.NewTokenManager("secret", 24*time.Hour, "test-issuer")
	sessionMgr := auth.NewSessionManager(mockUserRepo, mockSessionRepo, pm, tm, 24*time.Hour)

	middleware := AuthMiddleware(sessionMgr)
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest("GET", "/protected", nil)
	req.Header.Set("Authorization", "Bearer invalid-token")
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusUnauthorized {
		t.Errorf("expected status 401, got %d", recorder.Code)
	}
}

func TestAuthMiddleware_BearerTakesPrecedence(t *testing.T) {
	pm := auth.NewPasswordManager()

	tm := auth.NewTokenManager("secret", 24*time.Hour, "test-issuer")

	validBearerToken, _ := tm.GenerateToken("user123", "user@example.com", "user")
	invalidCookieToken := "invalid-token"

	mockUserRepo := &mockUserRepoForAuth{
		getFunc: func(ctx context.Context, id string) (*models.User, error) {
			return &models.User{
				ID:     "user123",
				Status: "active",
			}, nil
		},
	}

	mockSessionRepo := &mockSessionRepoForAuth{
		getByTokenFunc: func(ctx context.Context, token string) (*models.Session, error) {
			if token == validBearerToken {
				return &models.Session{
					ID:        "session123",
					UserID:    "user123",
					ExpiresAt: time.Now().Add(24 * time.Hour),
				}, nil
			}
			return nil, fmt.Errorf("invalid token")
		},
	}

	sessionMgr := auth.NewSessionManager(mockUserRepo, mockSessionRepo, pm, tm, 24*time.Hour)

	middleware := AuthMiddleware(sessionMgr)
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest("GET", "/protected", nil)
	req.Header.Set("Authorization", "Bearer "+validBearerToken)
	req.AddCookie(&http.Cookie{
		Name:  "session_token",
		Value: invalidCookieToken,
	})
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Errorf("expected status 200 (Bearer takes precedence), got %d", recorder.Code)
	}
}

func TestGetUserFromContext(t *testing.T) {
	expectedUser := &models.User{
		ID:       "user123",
		Username: "testuser",
	}

	ctx := context.WithValue(context.Background(), UserContextKey, expectedUser)
	req := httptest.NewRequest("GET", "/", nil).WithContext(ctx)

	user := GetUserFromContext(req)
	if user == nil {
		t.Fatalf("expected user, got nil")
	}

	if user.ID != "user123" {
		t.Errorf("expected UserID user123, got %s", user.ID)
	}
}

func TestGetUserFromContext_Missing(t *testing.T) {
	req := httptest.NewRequest("GET", "/", nil)

	user := GetUserFromContext(req)
	if user != nil {
		t.Errorf("expected nil, got user")
	}
}

func TestGetUserFromContext_WrongType(t *testing.T) {
	ctx := context.WithValue(context.Background(), UserContextKey, "not-a-user")
	req := httptest.NewRequest("GET", "/", nil).WithContext(ctx)

	user := GetUserFromContext(req)
	if user != nil {
		t.Errorf("expected nil for wrong type, got user")
	}
}

func TestGetTokenFromContext(t *testing.T) {
	expectedToken := "test-token-123"

	ctx := context.WithValue(context.Background(), TokenContextKey, expectedToken)
	req := httptest.NewRequest("GET", "/", nil).WithContext(ctx)

	token := GetTokenFromContext(req)
	if token != expectedToken {
		t.Errorf("expected token %s, got %s", expectedToken, token)
	}
}

func TestGetTokenFromContext_Missing(t *testing.T) {
	req := httptest.NewRequest("GET", "/", nil)

	token := GetTokenFromContext(req)
	if token != "" {
		t.Errorf("expected empty string, got %s", token)
	}
}

func TestGetTokenFromContext_WrongType(t *testing.T) {
	ctx := context.WithValue(context.Background(), TokenContextKey, 12345)
	req := httptest.NewRequest("GET", "/", nil).WithContext(ctx)

	token := GetTokenFromContext(req)
	if token != "" {
		t.Errorf("expected empty string for wrong type, got %s", token)
	}
}
