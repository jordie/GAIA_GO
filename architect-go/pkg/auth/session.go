package auth

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/google/uuid"

	"architect-go/pkg/models"
	"architect-go/pkg/repository"
)

// SessionManager manages user sessions
type SessionManager struct {
	userRepo      repository.UserRepository
	sessionRepo   repository.SessionRepository
	passwordMgr   *PasswordManager
	tokenMgr      *TokenManager
	sessionExpiry time.Duration
}

// NewSessionManager creates a new session manager
func NewSessionManager(
	userRepo repository.UserRepository,
	sessionRepo repository.SessionRepository,
	passwordMgr *PasswordManager,
	tokenMgr *TokenManager,
	sessionExpiry time.Duration,
) *SessionManager {
	return &SessionManager{
		userRepo:      userRepo,
		sessionRepo:   sessionRepo,
		passwordMgr:   passwordMgr,
		tokenMgr:      tokenMgr,
		sessionExpiry: sessionExpiry,
	}
}

// LoginRequest represents a login request
type LoginRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

// LoginResponse represents a login response
type LoginResponse struct {
	Token     string `json:"token"`
	ExpiresIn int64  `json:"expires_in"`
	UserID    string `json:"user_id"`
	Username  string `json:"username"`
	Email     string `json:"email"`
}

// Login authenticates a user and creates a session
func (sm *SessionManager) Login(ctx context.Context, req *LoginRequest) (*LoginResponse, error) {
	// Find user by username
	user, err := sm.userRepo.GetByUsername(ctx, req.Username)
	if err != nil {
		// Log attempt but don't reveal user existence
		log.Printf("Login attempt for non-existent user: %s", req.Username)
		return nil, fmt.Errorf("invalid username or password")
	}

	// Check if user is active
	if user.Status != "active" {
		return nil, fmt.Errorf("user account is not active")
	}

	// Verify password
	match, err := sm.passwordMgr.VerifyPassword(req.Password, user.PasswordHash)
	if err != nil || !match {
		log.Printf("Failed password verification for user: %s", user.Username)
		return nil, fmt.Errorf("invalid username or password")
	}

	// Generate token
	token, err := sm.tokenMgr.GenerateToken(user.ID, user.Email, "user")
	if err != nil {
		return nil, fmt.Errorf("failed to generate token: %w", err)
	}

	// Create session in database
	session := &models.Session{
		ID:        uuid.New().String(),
		UserID:    user.ID,
		Token:     token,
		ExpiresAt: time.Now().Add(sm.sessionExpiry),
	}

	if err := sm.sessionRepo.Create(ctx, session); err != nil {
		log.Printf("Failed to create session for user %s: %v", user.ID, err)
		return nil, fmt.Errorf("failed to create session")
	}

	// Update last login
	user.LastLoginAt = &time.Time{}
	*user.LastLoginAt = time.Now()
	_ = sm.userRepo.Update(ctx, user)

	log.Printf("User logged in: %s (session: %s)", user.Username, session.ID)

	return &LoginResponse{
		Token:     token,
		ExpiresIn: int64(sm.tokenMgr.GetExpiresIn().Seconds()),
		UserID:    user.ID,
		Username:  user.Username,
		Email:     user.Email,
	}, nil
}

// Logout invalidates a user session
func (sm *SessionManager) Logout(ctx context.Context, token string) error {
	// Validate token
	claims, err := sm.tokenMgr.ValidateToken(token)
	if err != nil {
		return fmt.Errorf("invalid token")
	}

	// Find and delete session
	session, err := sm.sessionRepo.GetByToken(ctx, token)
	if err != nil {
		log.Printf("Session not found for user %s", claims.UserID)
		return nil // Already logged out
	}

	if err := sm.sessionRepo.Delete(ctx, session.ID); err != nil {
		log.Printf("Failed to delete session for user %s: %v", claims.UserID, err)
		return fmt.Errorf("failed to logout")
	}

	log.Printf("User logged out: %s", claims.UserID)
	return nil
}

// ValidateSession validates a token and returns user information
func (sm *SessionManager) ValidateSession(ctx context.Context, token string) (*models.User, error) {
	// Validate token
	claims, err := sm.tokenMgr.ValidateToken(token)
	if err != nil {
		return nil, fmt.Errorf("invalid token: %w", err)
	}

	// Verify session exists in database
	session, err := sm.sessionRepo.GetByToken(ctx, token)
	if err != nil {
		return nil, fmt.Errorf("session not found")
	}

	// Check session expiration
	if session.ExpiresAt.Before(time.Now()) {
		_ = sm.sessionRepo.Delete(ctx, session.ID)
		return nil, fmt.Errorf("session expired")
	}

	// Get user
	user, err := sm.userRepo.Get(ctx, claims.UserID)
	if err != nil {
		return nil, fmt.Errorf("user not found")
	}

	// Check user is active
	if user.Status != "active" {
		return nil, fmt.Errorf("user account is not active")
	}

	return user, nil
}

// CleanupExpiredSessions removes all expired sessions
func (sm *SessionManager) CleanupExpiredSessions(ctx context.Context) error {
	return sm.sessionRepo.DeleteExpired(ctx)
}

// RefreshToken generates a new token for an active session
func (sm *SessionManager) RefreshToken(ctx context.Context, token string) (string, error) {
	// Validate current token
	_, err := sm.ValidateSession(ctx, token)
	if err != nil {
		return "", fmt.Errorf("invalid session: %w", err)
	}

	// Generate new token
	newToken, err := sm.tokenMgr.RefreshToken(token)
	if err != nil {
		return "", fmt.Errorf("failed to refresh token: %w", err)
	}

	// Update session with new token
	session, err := sm.sessionRepo.GetByToken(ctx, token)
	if err != nil {
		return "", fmt.Errorf("session not found")
	}

	session.Token = newToken
	session.ExpiresAt = time.Now().Add(sm.sessionExpiry)

	if err := sm.sessionRepo.Update(ctx, session); err != nil {
		return "", fmt.Errorf("failed to update session")
	}

	log.Printf("Session token refreshed for user: %s", session.UserID)
	return newToken, nil
}

// GetSessionCount returns the number of active sessions for a user
func (sm *SessionManager) GetSessionCount(ctx context.Context, userID string) (int, error) {
	sessions, err := sm.sessionRepo.ListByUser(ctx, userID)
	if err != nil {
		return 0, err
	}
	return len(sessions), nil
}

// InvalidateUserSessions invalidates all sessions for a user
func (sm *SessionManager) InvalidateUserSessions(ctx context.Context, userID string) error {
	sessions, err := sm.sessionRepo.ListByUser(ctx, userID)
	if err != nil {
		return err
	}

	for _, session := range sessions {
		if err := sm.sessionRepo.Delete(ctx, session.ID); err != nil {
			log.Printf("Failed to delete session %s: %v", session.ID, err)
		}
	}

	log.Printf("Invalidated all sessions for user: %s", userID)
	return nil
}
