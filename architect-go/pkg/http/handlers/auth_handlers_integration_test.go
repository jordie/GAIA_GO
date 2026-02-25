package handlers

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"architect-go/pkg/auth"
	"architect-go/pkg/errors"
	"architect-go/pkg/models"
)

// TestAuthHandlers_Login_Success tests successful login
func TestAuthHandlers_Login_Success(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create password and token managers
	pm := auth.NewPasswordManager()
	tm := auth.NewTokenManager("test-secret", 24*time.Hour, "test-issuer")

	// Hash a password
	hashedPassword, err := pm.HashPassword("password123")
	require.NoError(t, err, "failed to hash password")

	// Create a test user with hashed password
	user := &models.User{
		ID:           "user1",
		Username:     "testuser",
		Email:        "test@example.com",
		PasswordHash: hashedPassword,
		Status:       "active",
	}
	err = setup.DB.Create(user).Error
	require.NoError(t, err, "failed to create test user")

	// Create session manager
	sessionMgr := auth.NewSessionManager(
		setup.RepoRegistry.UserRepository,
		setup.RepoRegistry.SessionRepository,
		pm, tm, 24*time.Hour,
	)

	// Create auth handlers
	errHandler := errors.NewErrorHandler(false, true)
	authHandlers := NewAuthHandlers(sessionMgr, setup.ServiceRegistry.UserService, errHandler)

	// Setup routes
	setup.Router.Post("/auth/login", authHandlers.Login)

	// Make request
	recorder := setup.MakeRequest("POST", "/auth/login", map[string]string{
		"username": "testuser",
		"password": "password123",
	})

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err = setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotEmpty(t, response["token"])
	assert.Equal(t, "user1", response["user_id"])
	assert.Equal(t, "testuser", response["username"])
}

// TestAuthHandlers_Login_WrongPassword tests login with wrong password
func TestAuthHandlers_Login_WrongPassword(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create password and token managers
	pm := auth.NewPasswordManager()
	tm := auth.NewTokenManager("test-secret", 24*time.Hour, "test-issuer")

	// Hash a password
	hashedPassword, err := pm.HashPassword("password123")
	require.NoError(t, err, "failed to hash password")

	// Create a test user
	user := &models.User{
		ID:           "user1",
		Username:     "testuser",
		Email:        "test@example.com",
		PasswordHash: hashedPassword,
		Status:       "active",
	}
	err = setup.DB.Create(user).Error
	require.NoError(t, err, "failed to create test user")

	// Create session manager
	sessionMgr := auth.NewSessionManager(
		setup.RepoRegistry.UserRepository,
		setup.RepoRegistry.SessionRepository,
		pm, tm, 24*time.Hour,
	)

	// Create auth handlers
	errHandler := errors.NewErrorHandler(false, true)
	authHandlers := NewAuthHandlers(sessionMgr, setup.ServiceRegistry.UserService, errHandler)

	// Setup routes
	setup.Router.Post("/auth/login", authHandlers.Login)

	// Make request with wrong password
	recorder := setup.MakeRequest("POST", "/auth/login", map[string]string{
		"username": "testuser",
		"password": "wrongpassword",
	})

	// Assertions
	assert.Equal(t, http.StatusUnauthorized, recorder.Code)
}

// TestAuthHandlers_Login_UserNotFound tests login with non-existent user
func TestAuthHandlers_Login_UserNotFound(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create password and token managers
	pm := auth.NewPasswordManager()
	tm := auth.NewTokenManager("test-secret", 24*time.Hour, "test-issuer")

	// Create session manager
	sessionMgr := auth.NewSessionManager(
		setup.RepoRegistry.UserRepository,
		setup.RepoRegistry.SessionRepository,
		pm, tm, 24*time.Hour,
	)

	// Create auth handlers
	errHandler := errors.NewErrorHandler(false, true)
	authHandlers := NewAuthHandlers(sessionMgr, setup.ServiceRegistry.UserService, errHandler)

	// Setup routes
	setup.Router.Post("/auth/login", authHandlers.Login)

	// Make request with non-existent user
	recorder := setup.MakeRequest("POST", "/auth/login", map[string]string{
		"username": "nonexistent",
		"password": "password123",
	})

	// Assertions
	assert.Equal(t, http.StatusUnauthorized, recorder.Code)
}

// TestAuthHandlers_Logout_Success tests successful logout
func TestAuthHandlers_Logout_Success(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create password and token managers
	pm := auth.NewPasswordManager()
	tm := auth.NewTokenManager("test-secret", 24*time.Hour, "test-issuer")

	// Create a test user
	hashedPassword, _ := pm.HashPassword("password123")
	user := &models.User{
		ID:           "user1",
		Username:     "testuser",
		Email:        "test@example.com",
		PasswordHash: hashedPassword,
		Status:       "active",
	}
	err := setup.DB.Create(user).Error
	require.NoError(t, err)

	// Generate a valid token
	token, err := tm.GenerateToken(user.ID, user.Email, "user")
	require.NoError(t, err)

	// Create a session in the database
	session := &models.Session{
		ID:        "session1",
		UserID:    user.ID,
		Token:     token,
		ExpiresAt: time.Now().Add(24 * time.Hour),
	}
	err = setup.DB.Create(session).Error
	require.NoError(t, err)

	// Create session manager
	sessionMgr := auth.NewSessionManager(
		setup.RepoRegistry.UserRepository,
		setup.RepoRegistry.SessionRepository,
		pm, tm, 24*time.Hour,
	)

	// Create auth handlers
	errHandler := errors.NewErrorHandler(false, true)
	authHandlers := NewAuthHandlers(sessionMgr, setup.ServiceRegistry.UserService, errHandler)

	// Setup routes
	setup.Router.Post("/auth/logout", authHandlers.Logout)

	// Create request manually to set headers
	reqBody := httptest.NewRequest("POST", "/auth/logout", nil)
	reqBody.Header.Set("Authorization", fmt.Sprintf("Bearer %s", token))
	reqBody.Header.Set("X-Request-ID", "test-request-id")
	recorder := httptest.NewRecorder()
	setup.Router.ServeHTTP(recorder, reqBody)

	// Assertions
	assert.Equal(t, http.StatusNoContent, recorder.Code)
}

// TestAuthHandlers_Logout_NoToken tests logout without token
func TestAuthHandlers_Logout_NoToken(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create password and token managers
	pm := auth.NewPasswordManager()
	tm := auth.NewTokenManager("test-secret", 24*time.Hour, "test-issuer")

	// Create session manager
	sessionMgr := auth.NewSessionManager(
		setup.RepoRegistry.UserRepository,
		setup.RepoRegistry.SessionRepository,
		pm, tm, 24*time.Hour,
	)

	// Create auth handlers
	errHandler := errors.NewErrorHandler(false, true)
	authHandlers := NewAuthHandlers(sessionMgr, setup.ServiceRegistry.UserService, errHandler)

	// Setup routes
	setup.Router.Post("/auth/logout", authHandlers.Logout)

	// Make request without token
	recorder := setup.MakeRequest("POST", "/auth/logout", nil)

	// Assertions
	assert.Equal(t, http.StatusUnauthorized, recorder.Code)
}

// TestAuthHandlers_Refresh_Success tests successful token refresh
func TestAuthHandlers_Refresh_Success(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create password and token managers
	pm := auth.NewPasswordManager()
	tm := auth.NewTokenManager("test-secret", 24*time.Hour, "test-issuer")

	// Create a test user
	user := &models.User{
		ID:       "user1",
		Username: "testuser",
		Email:    "test@example.com",
		Status:   "active",
	}
	err := setup.DB.Create(user).Error
	require.NoError(t, err)

	// Generate a valid token
	token, err := tm.GenerateToken(user.ID, user.Email, "user")
	require.NoError(t, err)

	// Create a session in the database
	session := &models.Session{
		ID:        "session1",
		UserID:    user.ID,
		Token:     token,
		ExpiresAt: time.Now().Add(24 * time.Hour),
	}
	err = setup.DB.Create(session).Error
	require.NoError(t, err)

	// Create session manager
	sessionMgr := auth.NewSessionManager(
		setup.RepoRegistry.UserRepository,
		setup.RepoRegistry.SessionRepository,
		pm, tm, 24*time.Hour,
	)

	// Create auth handlers
	errHandler := errors.NewErrorHandler(false, true)
	authHandlers := NewAuthHandlers(sessionMgr, setup.ServiceRegistry.UserService, errHandler)

	// Setup routes
	setup.Router.Post("/auth/refresh", authHandlers.RefreshToken)

	// Create request manually to set headers
	req := httptest.NewRequest("POST", "/auth/refresh", nil)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", token))
	req.Header.Set("X-Request-ID", "test-request-id")
	recorder := httptest.NewRecorder()
	setup.Router.ServeHTTP(recorder, req)

	// Assertions
	assert.Equal(t, http.StatusOK, recorder.Code)

	var response map[string]interface{}
	err = setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.NotEmpty(t, response["token"])
}

// TestAuthHandlers_Refresh_Expired tests refresh with expired token
func TestAuthHandlers_Refresh_Expired(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create password and token managers
	pm := auth.NewPasswordManager()
	tm := auth.NewTokenManager("test-secret", 1*time.Nanosecond, "test-issuer") // Immediately expired

	// Create a test user
	user := &models.User{
		ID:       "user1",
		Username: "testuser",
		Email:    "test@example.com",
		Status:   "active",
	}
	err := setup.DB.Create(user).Error
	require.NoError(t, err)

	// Generate a token that will be expired
	token, err := tm.GenerateToken(user.ID, user.Email, "user")
	require.NoError(t, err)

	// Create session manager
	sessionMgr := auth.NewSessionManager(
		setup.RepoRegistry.UserRepository,
		setup.RepoRegistry.SessionRepository,
		pm, tm, 24*time.Hour,
	)

	// Create auth handlers
	errHandler := errors.NewErrorHandler(false, true)
	authHandlers := NewAuthHandlers(sessionMgr, setup.ServiceRegistry.UserService, errHandler)

	// Setup routes
	setup.Router.Post("/auth/refresh", authHandlers.RefreshToken)

	// Wait a bit to ensure token is expired
	time.Sleep(10 * time.Millisecond)

	// Create request manually to set headers
	req := httptest.NewRequest("POST", "/auth/refresh", nil)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", token))
	req.Header.Set("X-Request-ID", "test-request-id")
	recorder := httptest.NewRecorder()
	setup.Router.ServeHTTP(recorder, req)

	// Assertions
	assert.Equal(t, http.StatusUnauthorized, recorder.Code)
}

// TestAuthHandlers_Verify_ValidToken tests token verification with valid token
func TestAuthHandlers_Verify_ValidToken(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create password and token managers
	pm := auth.NewPasswordManager()
	tm := auth.NewTokenManager("test-secret", 24*time.Hour, "test-issuer")

	// Create a test user
	user := &models.User{
		ID:       "user1",
		Username: "testuser",
		Email:    "test@example.com",
		Status:   "active",
	}
	err := setup.DB.Create(user).Error
	require.NoError(t, err)

	// Generate a valid token
	token, err := tm.GenerateToken(user.ID, user.Email, "user")
	require.NoError(t, err)

	// Create a session in the database
	session := &models.Session{
		ID:        "session1",
		UserID:    user.ID,
		Token:     token,
		ExpiresAt: time.Now().Add(24 * time.Hour),
	}
	err = setup.DB.Create(session).Error
	require.NoError(t, err)

	// Create session manager
	sessionMgr := auth.NewSessionManager(
		setup.RepoRegistry.UserRepository,
		setup.RepoRegistry.SessionRepository,
		pm, tm, 24*time.Hour,
	)

	// Create auth handlers
	errHandler := errors.NewErrorHandler(false, true)
	authHandlers := NewAuthHandlers(sessionMgr, setup.ServiceRegistry.UserService, errHandler)

	// Setup routes
	setup.Router.Get("/auth/verify", authHandlers.Verify)

	// Create request manually to set headers
	req := httptest.NewRequest("GET", "/auth/verify", nil)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", token))
	req.Header.Set("X-Request-ID", "test-request-id")
	recorder := httptest.NewRecorder()
	setup.Router.ServeHTTP(recorder, req)

	// Assertions
	setup.AssertResponseStatus(recorder, http.StatusOK)

	var response map[string]interface{}
	err = setup.DecodeResponse(recorder, &response)
	require.NoError(t, err)

	assert.Equal(t, "user1", response["user_id"])
	assert.Equal(t, "testuser", response["username"])
}

// TestAuthHandlers_Verify_InvalidToken tests token verification with invalid token
func TestAuthHandlers_Verify_InvalidToken(t *testing.T) {
	setup := NewTestSetup(t)
	defer setup.Cleanup()

	// Create password and token managers
	pm := auth.NewPasswordManager()
	tm := auth.NewTokenManager("test-secret", 24*time.Hour, "test-issuer")

	// Create session manager
	sessionMgr := auth.NewSessionManager(
		setup.RepoRegistry.UserRepository,
		setup.RepoRegistry.SessionRepository,
		pm, tm, 24*time.Hour,
	)

	// Create auth handlers
	errHandler := errors.NewErrorHandler(false, true)
	authHandlers := NewAuthHandlers(sessionMgr, setup.ServiceRegistry.UserService, errHandler)

	// Setup routes
	setup.Router.Get("/auth/verify", authHandlers.Verify)

	// Create request manually to set headers
	req := httptest.NewRequest("GET", "/auth/verify", nil)
	req.Header.Set("Authorization", "Bearer invalid_token")
	req.Header.Set("X-Request-ID", "test-request-id")
	recorder := httptest.NewRecorder()
	setup.Router.ServeHTTP(recorder, req)

	// Assertions
	assert.Equal(t, http.StatusUnauthorized, recorder.Code)
}
