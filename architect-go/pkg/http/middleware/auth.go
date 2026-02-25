package middleware

import (
	"context"
	"net/http"
	"strings"

	apperrors "architect-go/pkg/errors"
	"architect-go/pkg/models"
)

// SessionValidator is an interface for session validation
type SessionValidator interface {
	ValidateSession(ctx context.Context, token string) (*models.User, error)
}

// contextKey is a type for context keys
type contextKey string

const (
	// UserIDKey is the key for user ID in context
	UserIDKey contextKey = "user_id"
	// UsernameKey is the key for username in context
	UsernameKey contextKey = "username"
	// EmailKey is the key for email in context
	EmailKey contextKey = "email"
	// UserKey is the key for full user object in context
	UserKey contextKey = "user"
)

// RequireAuth validates Bearer token via SessionValidator, injects user into context.
// Returns 401 JSON if missing or invalid.
func RequireAuth(sessionValidator SessionValidator, errHandler *apperrors.Handler) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Extract token from Authorization header or X-Auth-Token header
			token := extractToken(r)
			if token == "" {
				// Try session_token cookie as fallback
				cookie, err := r.Cookie("session_token")
				if err != nil {
					errHandler.Handle(w, apperrors.AuthenticationErrorf("MISSING_TOKEN", "missing authentication token"), "")
					return
				}
				token = cookie.Value
			}

			// Validate session and get user
			user, err := sessionValidator.ValidateSession(r.Context(), token)
			if err != nil {
				errHandler.Handle(w, apperrors.AuthenticationErrorf("INVALID_SESSION", "invalid or expired session"), "")
				return
			}

			// Create context with user data
			ctx := context.WithValue(r.Context(), UserKey, user)
			ctx = context.WithValue(ctx, UserIDKey, user.ID)
			ctx = context.WithValue(ctx, UsernameKey, user.Username)
			ctx = context.WithValue(ctx, EmailKey, user.Email)

			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// extractToken extracts Bearer token from Authorization header or X-Auth-Token header
func extractToken(r *http.Request) string {
	// Try Authorization: Bearer <token>
	authHeader := r.Header.Get("Authorization")
	if authHeader != "" {
		parts := strings.Fields(authHeader)
		if len(parts) == 2 && parts[0] == "Bearer" {
			return parts[1]
		}
	}

	// Try X-Auth-Token header
	if token := r.Header.Get("X-Auth-Token"); token != "" {
		return token
	}

	return ""
}

// UserIDFromContext retrieves the user ID from context (returns "" if not set)
func UserIDFromContext(ctx context.Context) string {
	userID, ok := ctx.Value(UserIDKey).(string)
	if !ok {
		return ""
	}
	return userID
}

// UsernameFromContext retrieves the username from context (returns "" if not set)
func UsernameFromContext(ctx context.Context) string {
	username, ok := ctx.Value(UsernameKey).(string)
	if !ok {
		return ""
	}
	return username
}

// EmailFromContext retrieves the email from context (returns "" if not set)
func EmailFromContext(ctx context.Context) string {
	email, ok := ctx.Value(EmailKey).(string)
	if !ok {
		return ""
	}
	return email
}

// UserFromContext retrieves the full user object from context (returns nil if not set)
func UserFromContext(ctx context.Context) *models.User {
	user, ok := ctx.Value(UserKey).(*models.User)
	if !ok {
		return nil
	}
	return user
}
