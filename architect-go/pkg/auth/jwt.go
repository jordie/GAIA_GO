package auth

import (
	"fmt"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

// TokenManager manages JWT token creation and validation
type TokenManager struct {
	secretKey  string
	expiresIn  time.Duration
	issuer     string
	audience   string
}

// Claims represents JWT claims
type Claims struct {
	UserID string `json:"user_id"`
	Email  string `json:"email"`
	Role   string `json:"role,omitempty"`
	jwt.RegisteredClaims
}

// NewTokenManager creates a new token manager
func NewTokenManager(secretKey string, expiresIn time.Duration, issuer string) *TokenManager {
	return &TokenManager{
		secretKey: secretKey,
		expiresIn: expiresIn,
		issuer:    issuer,
		audience:  "architect-dashboard",
	}
}

// GenerateToken generates a new JWT token
func (tm *TokenManager) GenerateToken(userID string, email string, role string) (string, error) {
	now := time.Now()
	expiresAt := now.Add(tm.expiresIn)

	claims := &Claims{
		UserID: userID,
		Email:  email,
		Role:   role,
		RegisteredClaims: jwt.RegisteredClaims{
			IssuedAt:  jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(expiresAt),
			Issuer:    tm.issuer,
			Audience:  jwt.ClaimStrings{tm.audience},
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, err := token.SignedString([]byte(tm.secretKey))
	if err != nil {
		return "", fmt.Errorf("failed to sign token: %w", err)
	}

	return tokenString, nil
}

// ValidateToken validates and parses a JWT token
func (tm *TokenManager) ValidateToken(tokenString string) (*Claims, error) {
	claims := &Claims{}

	token, err := jwt.ParseWithClaims(tokenString, claims, func(token *jwt.Token) (interface{}, error) {
		// Verify the signing method
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return []byte(tm.secretKey), nil
	})

	if err != nil {
		return nil, fmt.Errorf("failed to parse token: %w", err)
	}

	if !token.Valid {
		return nil, fmt.Errorf("token is invalid")
	}

	// Verify expiration
	if claims.ExpiresAt != nil && claims.ExpiresAt.Before(time.Now()) {
		return nil, fmt.Errorf("token has expired")
	}

	// Verify issuer
	if claims.Issuer != tm.issuer {
		return nil, fmt.Errorf("invalid issuer")
	}

	// Verify audience
	audienceFound := false
	for _, aud := range claims.Audience {
		if aud == tm.audience {
			audienceFound = true
			break
		}
	}
	if !audienceFound {
		return nil, fmt.Errorf("invalid audience")
	}

	return claims, nil
}

// RefreshToken generates a new token with updated expiration
func (tm *TokenManager) RefreshToken(oldToken string) (string, error) {
	claims, err := tm.ValidateToken(oldToken)
	if err != nil {
		return "", fmt.Errorf("failed to validate token: %w", err)
	}

	// Generate new token with same claims
	return tm.GenerateToken(claims.UserID, claims.Email, claims.Role)
}

// GetExpiresIn returns the token expiration duration
func (tm *TokenManager) GetExpiresIn() time.Duration {
	return tm.expiresIn
}
