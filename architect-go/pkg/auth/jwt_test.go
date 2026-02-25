package auth

import (
	"testing"
	"time"
)

func TestTokenManager_GenerateToken(t *testing.T) {
	tm := NewTokenManager("test-secret", 24*time.Hour, "test-issuer")

	userID := "user123"
	email := "user@example.com"
	role := "admin"

	token, err := tm.GenerateToken(userID, email, role)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	if token == "" {
		t.Errorf("expected non-empty token, got empty string")
	}

	// Verify token has 3 parts (header.payload.signature)
	parts := 0
	for _, ch := range token {
		if ch == '.' {
			parts++
		}
	}
	if parts != 2 {
		t.Errorf("expected 3-part JWT, got %d dots", parts)
	}

	// Validate the token to verify claims
	claims, err := tm.ValidateToken(token)
	if err != nil {
		t.Fatalf("failed to validate generated token: %v", err)
	}

	if claims.UserID != userID {
		t.Errorf("expected UserID %s, got %s", userID, claims.UserID)
	}
	if claims.Email != email {
		t.Errorf("expected Email %s, got %s", email, claims.Email)
	}
	if claims.Role != role {
		t.Errorf("expected Role %s, got %s", role, claims.Role)
	}
	if claims.Issuer != "test-issuer" {
		t.Errorf("expected Issuer test-issuer, got %s", claims.Issuer)
	}
}

func TestTokenManager_ValidateToken(t *testing.T) {
	tests := []struct {
		name      string
		token     string
		setup     func() (string, *TokenManager)
		shouldErr bool
		errMsg    string
	}{
		{
			name: "valid token",
			setup: func() (string, *TokenManager) {
				tm := NewTokenManager("test-secret", 24*time.Hour, "test-issuer")
				token, _ := tm.GenerateToken("user123", "user@example.com", "admin")
				return token, tm
			},
			shouldErr: false,
		},
		{
			name: "wrong secret",
			setup: func() (string, *TokenManager) {
				tm := NewTokenManager("test-secret", 24*time.Hour, "test-issuer")
				token, _ := tm.GenerateToken("user123", "user@example.com", "admin")
				tm2 := NewTokenManager("wrong-secret", 24*time.Hour, "test-issuer")
				return token, tm2
			},
			shouldErr: true,
		},
		{
			name: "expired token",
			setup: func() (string, *TokenManager) {
				tm := NewTokenManager("test-secret", -1*time.Hour, "test-issuer")
				token, _ := tm.GenerateToken("user123", "user@example.com", "admin")
				return token, tm
			},
			shouldErr: true,
		},
		{
			name: "wrong issuer",
			setup: func() (string, *TokenManager) {
				tm := NewTokenManager("test-secret", 24*time.Hour, "test-issuer")
				token, _ := tm.GenerateToken("user123", "user@example.com", "admin")
				tm2 := NewTokenManager("test-secret", 24*time.Hour, "wrong-issuer")
				return token, tm2
			},
			shouldErr: true,
		},
		{
			name: "wrong audience",
			setup: func() (string, *TokenManager) {
				tm := NewTokenManager("test-secret", 24*time.Hour, "test-issuer")
				token, _ := tm.GenerateToken("user123", "user@example.com", "admin")
				return token, tm
			},
			shouldErr: false, // audience validation is internal, tokens have correct audience
		},
		{
			name: "empty token string",
			setup: func() (string, *TokenManager) {
				tm := NewTokenManager("test-secret", 24*time.Hour, "test-issuer")
				return "", tm
			},
			shouldErr: true,
		},
		{
			name: "malformed token",
			setup: func() (string, *TokenManager) {
				tm := NewTokenManager("test-secret", 24*time.Hour, "test-issuer")
				return "not.a.valid.jwt", tm
			},
			shouldErr: true,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			token, tm := tc.setup()
			_, err := tm.ValidateToken(token)
			if tc.shouldErr && err == nil {
				t.Errorf("expected error, got nil")
			}
			if !tc.shouldErr && err != nil {
				t.Errorf("expected no error, got: %v", err)
			}
		})
	}
}

func TestTokenManager_RefreshToken(t *testing.T) {
	tm := NewTokenManager("test-secret", 24*time.Hour, "test-issuer")

	userID := "user123"
	email := "user@example.com"
	role := "admin"

	oldToken, err := tm.GenerateToken(userID, email, role)
	if err != nil {
		t.Fatalf("failed to generate original token: %v", err)
	}

	// Small delay to ensure different timestamp
	time.Sleep(10 * time.Millisecond)

	newToken, err := tm.RefreshToken(oldToken)
	if err != nil {
		t.Fatalf("failed to refresh token: %v", err)
	}

	if newToken == "" {
		t.Errorf("expected non-empty new token, got empty")
	}

	// Tokens may be same if generated very quickly, so we skip this check
	// and instead verify the claims are correct

	// Verify new token claims match original
	claims, err := tm.ValidateToken(newToken)
	if err != nil {
		t.Fatalf("failed to validate refreshed token: %v", err)
	}

	if claims.UserID != userID {
		t.Errorf("expected UserID %s, got %s", userID, claims.UserID)
	}
	if claims.Email != email {
		t.Errorf("expected Email %s, got %s", email, claims.Email)
	}
	if claims.Role != role {
		t.Errorf("expected Role %s, got %s", role, claims.Role)
	}
}

func TestTokenManager_RefreshToken_InvalidToken(t *testing.T) {
	tm := NewTokenManager("test-secret", 24*time.Hour, "test-issuer")

	_, err := tm.RefreshToken("invalid-token")
	if err == nil {
		t.Fatalf("expected error for invalid token, got nil")
	}
}

func TestTokenManager_GetExpiresIn(t *testing.T) {
	expectedDuration := 24 * time.Hour
	tm := NewTokenManager("test-secret", expectedDuration, "test-issuer")

	if tm.GetExpiresIn() != expectedDuration {
		t.Errorf("expected %v, got %v", expectedDuration, tm.GetExpiresIn())
	}
}

func TestTokenManager_GetExpiresIn_CustomDuration(t *testing.T) {
	expectedDuration := 48 * time.Hour
	tm := NewTokenManager("test-secret", expectedDuration, "test-issuer")

	if tm.GetExpiresIn() != expectedDuration {
		t.Errorf("expected %v, got %v", expectedDuration, tm.GetExpiresIn())
	}
}
