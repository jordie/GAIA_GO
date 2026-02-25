package auth

import (
	"context"
	"fmt"
	"testing"
	"time"

	"architect-go/pkg/models"
)

// mockUserRepo implements repository.UserRepository
type mockUserRepo struct {
	getByUsernameFunc func(ctx context.Context, username string) (*models.User, error)
	getFunc           func(ctx context.Context, id string) (*models.User, error)
	updateFunc        func(ctx context.Context, user *models.User) error
	createFunc        func(ctx context.Context, user *models.User) error
	listFunc          func(ctx context.Context, limit int, offset int) ([]*models.User, int64, error)
	getByEmailFunc    func(ctx context.Context, email string) (*models.User, error)
	deleteFunc        func(ctx context.Context, id string) error
}

func (m *mockUserRepo) GetByUsername(ctx context.Context, username string) (*models.User, error) {
	return m.getByUsernameFunc(ctx, username)
}

func (m *mockUserRepo) Get(ctx context.Context, id string) (*models.User, error) {
	return m.getFunc(ctx, id)
}

func (m *mockUserRepo) Update(ctx context.Context, user *models.User) error {
	if m.updateFunc == nil {
		return nil
	}
	return m.updateFunc(ctx, user)
}

func (m *mockUserRepo) Create(ctx context.Context, user *models.User) error {
	return m.createFunc(ctx, user)
}

func (m *mockUserRepo) List(ctx context.Context, limit int, offset int) ([]*models.User, int64, error) {
	return m.listFunc(ctx, limit, offset)
}

func (m *mockUserRepo) GetByEmail(ctx context.Context, email string) (*models.User, error) {
	return m.getByEmailFunc(ctx, email)
}

func (m *mockUserRepo) Delete(ctx context.Context, id string) error {
	return m.deleteFunc(ctx, id)
}

// mockSessionRepo implements repository.SessionRepository
type mockSessionRepo struct {
	createFunc        func(ctx context.Context, session *models.Session) error
	getByTokenFunc    func(ctx context.Context, token string) (*models.Session, error)
	deleteFunc        func(ctx context.Context, id string) error
	deleteExpiredFunc func(ctx context.Context) error
	listByUserFunc    func(ctx context.Context, userID string) ([]*models.Session, error)
	updateFunc        func(ctx context.Context, session *models.Session) error
	getFunc           func(ctx context.Context, id string) (*models.Session, error)
}

func (m *mockSessionRepo) Create(ctx context.Context, session *models.Session) error {
	return m.createFunc(ctx, session)
}

func (m *mockSessionRepo) GetByToken(ctx context.Context, token string) (*models.Session, error) {
	return m.getByTokenFunc(ctx, token)
}

func (m *mockSessionRepo) Delete(ctx context.Context, id string) error {
	return m.deleteFunc(ctx, id)
}

func (m *mockSessionRepo) DeleteExpired(ctx context.Context) error {
	return m.deleteExpiredFunc(ctx)
}

func (m *mockSessionRepo) ListByUser(ctx context.Context, userID string) ([]*models.Session, error) {
	return m.listByUserFunc(ctx, userID)
}

func (m *mockSessionRepo) Update(ctx context.Context, session *models.Session) error {
	return m.updateFunc(ctx, session)
}

func (m *mockSessionRepo) Get(ctx context.Context, id string) (*models.Session, error) {
	return m.getFunc(ctx, id)
}

func TestSessionManager_Login_Success(t *testing.T) {
	pm := NewPasswordManager()
	hash, _ := pm.HashPassword("password123")

	mockUserRepo := &mockUserRepo{
		getByUsernameFunc: func(ctx context.Context, username string) (*models.User, error) {
			return &models.User{
				ID:           "user123",
				Username:     username,
				Email:        "user@example.com",
				PasswordHash: hash,
				Status:       "active",
			}, nil
		},
		updateFunc: func(ctx context.Context, user *models.User) error {
			return nil
		},
	}

	mockSessionRepo := &mockSessionRepo{
		createFunc: func(ctx context.Context, session *models.Session) error {
			return nil
		},
	}

	tm := NewTokenManager("secret", 24*time.Hour, "test-issuer")
	sm := NewSessionManager(mockUserRepo, mockSessionRepo, pm, tm, 24*time.Hour)

	req := &LoginRequest{
		Username: "testuser",
		Password: "password123",
	}

	resp, err := sm.Login(context.Background(), req)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	if resp == nil {
		t.Fatalf("expected response, got nil")
	}

	if resp.UserID != "user123" {
		t.Errorf("expected UserID user123, got %s", resp.UserID)
	}

	if resp.Token == "" {
		t.Errorf("expected non-empty token")
	}
}

func TestSessionManager_Login_WrongPassword(t *testing.T) {
	pm := NewPasswordManager()
	hash, _ := pm.HashPassword("correctpassword")

	mockUserRepo := &mockUserRepo{
		getByUsernameFunc: func(ctx context.Context, username string) (*models.User, error) {
			return &models.User{
				ID:           "user123",
				Username:     username,
				Email:        "user@example.com",
				PasswordHash: hash,
				Status:       "active",
			}, nil
		},
	}

	mockSessionRepo := &mockSessionRepo{}
	tm := NewTokenManager("secret", 24*time.Hour, "test-issuer")
	sm := NewSessionManager(mockUserRepo, mockSessionRepo, pm, tm, 24*time.Hour)

	req := &LoginRequest{
		Username: "testuser",
		Password: "wrongpassword",
	}

	_, err := sm.Login(context.Background(), req)
	if err == nil {
		t.Fatalf("expected error for wrong password")
	}
}

func TestSessionManager_Login_NonExistentUser(t *testing.T) {
	mockUserRepo := &mockUserRepo{
		getByUsernameFunc: func(ctx context.Context, username string) (*models.User, error) {
			return nil, fmt.Errorf("user not found")
		},
	}

	mockSessionRepo := &mockSessionRepo{}
	pm := NewPasswordManager()
	tm := NewTokenManager("secret", 24*time.Hour, "test-issuer")
	sm := NewSessionManager(mockUserRepo, mockSessionRepo, pm, tm, 24*time.Hour)

	req := &LoginRequest{
		Username: "nonexistent",
		Password: "password123",
	}

	_, err := sm.Login(context.Background(), req)
	if err == nil {
		t.Fatalf("expected error for non-existent user")
	}
}

func TestSessionManager_Login_InactiveUser(t *testing.T) {
	pm := NewPasswordManager()
	hash, _ := pm.HashPassword("password123")

	mockUserRepo := &mockUserRepo{
		getByUsernameFunc: func(ctx context.Context, username string) (*models.User, error) {
			return &models.User{
				ID:           "user123",
				Username:     username,
				Email:        "user@example.com",
				PasswordHash: hash,
				Status:       "inactive",
			}, nil
		},
	}

	mockSessionRepo := &mockSessionRepo{}
	tm := NewTokenManager("secret", 24*time.Hour, "test-issuer")
	sm := NewSessionManager(mockUserRepo, mockSessionRepo, pm, tm, 24*time.Hour)

	req := &LoginRequest{
		Username: "testuser",
		Password: "password123",
	}

	_, err := sm.Login(context.Background(), req)
	if err == nil {
		t.Fatalf("expected error for inactive user")
	}
}

func TestSessionManager_Logout_Success(t *testing.T) {
	tm := NewTokenManager("secret", 24*time.Hour, "test-issuer")
	pm := NewPasswordManager()

	// Generate a valid token
	token, _ := tm.GenerateToken("user123", "user@example.com", "user")

	mockSessionRepo := &mockSessionRepo{
		getByTokenFunc: func(ctx context.Context, t string) (*models.Session, error) {
			return &models.Session{
				ID:        "session123",
				UserID:    "user123",
				Token:     token,
				ExpiresAt: time.Now().Add(24 * time.Hour),
			}, nil
		},
		deleteFunc: func(ctx context.Context, id string) error {
			return nil
		},
	}

	mockUserRepo := &mockUserRepo{}
	sm := NewSessionManager(mockUserRepo, mockSessionRepo, pm, tm, 24*time.Hour)

	err := sm.Logout(context.Background(), token)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
}

func TestSessionManager_Logout_InvalidToken(t *testing.T) {
	mockSessionRepo := &mockSessionRepo{}
	mockUserRepo := &mockUserRepo{}
	tm := NewTokenManager("secret", 24*time.Hour, "test-issuer")
	pm := NewPasswordManager()
	sm := NewSessionManager(mockUserRepo, mockSessionRepo, pm, tm, 24*time.Hour)

	err := sm.Logout(context.Background(), "invalid-token")
	if err == nil {
		t.Fatalf("expected error for invalid token")
	}
}

func TestSessionManager_Logout_SessionNotFound(t *testing.T) {
	pm := NewPasswordManager()
	passwordHash, _ := pm.HashPassword("password")

	mockUserRepo := &mockUserRepo{
		getByUsernameFunc: func(ctx context.Context, username string) (*models.User, error) {
			return &models.User{
				ID:           "user123",
				Username:     username,
				PasswordHash: passwordHash,
				Status:       "active",
			}, nil
		},
	}

	mockSessionRepo := &mockSessionRepo{
		createFunc: func(ctx context.Context, session *models.Session) error {
			return nil
		},
		getByTokenFunc: func(ctx context.Context, token string) (*models.Session, error) {
			return nil, fmt.Errorf("session not found")
		},
	}

	tm := NewTokenManager("secret", 24*time.Hour, "test-issuer")
	sm := NewSessionManager(mockUserRepo, mockSessionRepo, pm, tm, 24*time.Hour)

	// Login first to get valid token
	loginReq := &LoginRequest{Username: "user", Password: "password"}
	loginResp, _ := sm.Login(context.Background(), loginReq)

	// Logout should return nil (idempotent)
	err := sm.Logout(context.Background(), loginResp.Token)
	if err != nil {
		t.Fatalf("expected nil error (idempotent), got: %v", err)
	}
}

func TestSessionManager_ValidateSession_Valid(t *testing.T) {
	pm := NewPasswordManager()

	mockUserRepo := &mockUserRepo{
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
	mockSessionRepo := &mockSessionRepo{
		getByTokenFunc: func(ctx context.Context, t string) (*models.Session, error) {
			return &models.Session{
				ID:        "session123",
				UserID:    "user123",
				Token:     token,
				ExpiresAt: time.Now().Add(24 * time.Hour),
			}, nil
		},
	}

	tm := NewTokenManager("secret", 24*time.Hour, "test-issuer")
	sm := NewSessionManager(mockUserRepo, mockSessionRepo, pm, tm, 24*time.Hour)

	// Generate valid token
	validToken, _ := tm.GenerateToken("user123", "user@example.com", "user")

	user, err := sm.ValidateSession(context.Background(), validToken)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	if user == nil {
		t.Fatalf("expected user, got nil")
	}

	if user.ID != "user123" {
		t.Errorf("expected UserID user123, got %s", user.ID)
	}
}

func TestSessionManager_ValidateSession_ExpiredSession(t *testing.T) {
	mockUserRepo := &mockUserRepo{}
	mockSessionRepo := &mockSessionRepo{
		getByTokenFunc: func(ctx context.Context, token string) (*models.Session, error) {
			return &models.Session{
				ID:        "session123",
				UserID:    "user123",
				Token:     token,
				ExpiresAt: time.Now().Add(-1 * time.Hour), // Already expired
			}, nil
		},
		deleteFunc: func(ctx context.Context, id string) error {
			return nil
		},
	}

	pm := NewPasswordManager()
	tm := NewTokenManager("secret", 24*time.Hour, "test-issuer")
	sm := NewSessionManager(mockUserRepo, mockSessionRepo, pm, tm, 24*time.Hour)

	validToken, _ := tm.GenerateToken("user123", "user@example.com", "user")

	_, err := sm.ValidateSession(context.Background(), validToken)
	if err == nil {
		t.Fatalf("expected error for expired session")
	}
}

func TestSessionManager_CleanupExpiredSessions(t *testing.T) {
	mockSessionRepo := &mockSessionRepo{
		deleteExpiredFunc: func(ctx context.Context) error {
			return nil
		},
	}

	mockUserRepo := &mockUserRepo{}
	pm := NewPasswordManager()
	tm := NewTokenManager("secret", 24*time.Hour, "test-issuer")
	sm := NewSessionManager(mockUserRepo, mockSessionRepo, pm, tm, 24*time.Hour)

	err := sm.CleanupExpiredSessions(context.Background())
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
}

func TestSessionManager_GetSessionCount(t *testing.T) {
	mockSessionRepo := &mockSessionRepo{
		listByUserFunc: func(ctx context.Context, userID string) ([]*models.Session, error) {
			return []*models.Session{
				{ID: "s1", UserID: userID},
				{ID: "s2", UserID: userID},
				{ID: "s3", UserID: userID},
			}, nil
		},
	}

	mockUserRepo := &mockUserRepo{}
	pm := NewPasswordManager()
	tm := NewTokenManager("secret", 24*time.Hour, "test-issuer")
	sm := NewSessionManager(mockUserRepo, mockSessionRepo, pm, tm, 24*time.Hour)

	count, err := sm.GetSessionCount(context.Background(), "user123")
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	if count != 3 {
		t.Errorf("expected count 3, got %d", count)
	}
}

func TestSessionManager_InvalidateUserSessions(t *testing.T) {
	sessions := []*models.Session{
		{ID: "s1", UserID: "user123"},
		{ID: "s2", UserID: "user123"},
	}

	mockSessionRepo := &mockSessionRepo{
		listByUserFunc: func(ctx context.Context, userID string) ([]*models.Session, error) {
			return sessions, nil
		},
		deleteFunc: func(ctx context.Context, id string) error {
			return nil
		},
	}

	mockUserRepo := &mockUserRepo{}
	pm := NewPasswordManager()
	tm := NewTokenManager("secret", 24*time.Hour, "test-issuer")
	sm := NewSessionManager(mockUserRepo, mockSessionRepo, pm, tm, 24*time.Hour)

	err := sm.InvalidateUserSessions(context.Background(), "user123")
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
}

func TestSessionManager_RefreshToken_Success(t *testing.T) {
	pm := NewPasswordManager()
	tm := NewTokenManager("secret", 24*time.Hour, "test-issuer")

	oldToken, _ := tm.GenerateToken("user123", "user@example.com", "user")

	mockUserRepo := &mockUserRepo{
		getFunc: func(ctx context.Context, id string) (*models.User, error) {
			return &models.User{
				ID:     "user123",
				Status: "active",
			}, nil
		},
	}

	mockSessionRepo := &mockSessionRepo{
		getByTokenFunc: func(ctx context.Context, token string) (*models.Session, error) {
			return &models.Session{
				ID:        "session123",
				UserID:    "user123",
				Token:     token,
				ExpiresAt: time.Now().Add(24 * time.Hour),
			}, nil
		},
		updateFunc: func(ctx context.Context, session *models.Session) error {
			return nil
		},
	}

	sm := NewSessionManager(mockUserRepo, mockSessionRepo, pm, tm, 24*time.Hour)

	newToken, err := sm.RefreshToken(context.Background(), oldToken)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	if newToken == "" {
		t.Errorf("expected non-empty new token")
	}
}
