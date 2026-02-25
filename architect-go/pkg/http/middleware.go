package http

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"strings"

	"architect-go/pkg/auth"
	"architect-go/pkg/models"
)

// ContextKey is a type for context keys
type ContextKey string

const (
	// UserContextKey is the key for user in context
	UserContextKey ContextKey = "user"

	// TokenContextKey is the key for token in context
	TokenContextKey ContextKey = "token"
)

// AuthMiddleware checks authentication on protected routes
func AuthMiddleware(sessionMgr *auth.SessionManager) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Get token from header
			token := extractBearerToken(r)
			if token == "" {
				// Check for cookie
				cookie, err := r.Cookie("session_token")
				if err != nil {
					w.Header().Set("Content-Type", "application/json")
					w.WriteHeader(http.StatusUnauthorized)
					fmt.Fprintf(w, `{"error": "missing authentication token"}`)
					return
				}
				token = cookie.Value
			}

			// Validate session
			user, err := sessionMgr.ValidateSession(r.Context(), token)
			if err != nil {
				log.Printf("Session validation failed: %v", err)
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusUnauthorized)
				fmt.Fprintf(w, `{"error": "invalid or expired session"}`)
				return
			}

			// Add user and token to context
			ctx := context.WithValue(r.Context(), UserContextKey, user)
			ctx = context.WithValue(ctx, TokenContextKey, token)

			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// GetUserFromContext extracts user from request context
func GetUserFromContext(r *http.Request) *models.User {
	user, ok := r.Context().Value(UserContextKey).(*models.User)
	if !ok {
		return nil
	}
	return user
}

// GetTokenFromContext extracts token from request context
func GetTokenFromContext(r *http.Request) string {
	token, ok := r.Context().Value(TokenContextKey).(string)
	if !ok {
		return ""
	}
	return token
}

// extractBearerToken extracts bearer token from Authorization header
func extractBearerToken(r *http.Request) string {
	authHeader := r.Header.Get("Authorization")
	if authHeader == "" {
		return ""
	}

	parts := strings.Fields(authHeader)
	if len(parts) == 2 && parts[0] == "Bearer" {
		return parts[1]
	}

	return ""
}
