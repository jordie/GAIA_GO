package handlers

import (
	"encoding/json"
	"net/http"

	"architect-go/pkg/auth"
	"architect-go/pkg/errors"
	httputil "architect-go/pkg/httputil"
	"architect-go/pkg/services"
)

// AuthHandlers handles authentication HTTP requests
type AuthHandlers struct {
	sessionMgr  *auth.SessionManager
	userService services.UserService
	errHandler  *errors.Handler
}

// NewAuthHandlers creates new auth handlers
func NewAuthHandlers(sessionMgr *auth.SessionManager, userService services.UserService, errHandler *errors.Handler) *AuthHandlers {
	return &AuthHandlers{
		sessionMgr:  sessionMgr,
		userService: userService,
		errHandler:  errHandler,
	}
}

// LoginRequest represents a login request
type LoginRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

// TokenResponse represents a token response
type TokenResponse struct {
	Token     string `json:"token"`
	ExpiresIn int64  `json:"expires_in"`
	UserID    string `json:"user_id"`
	Username  string `json:"username"`
	Email     string `json:"email"`
}

// Login handles POST /api/auth/login
func (ah *AuthHandlers) Login(w http.ResponseWriter, r *http.Request) {
	var req LoginRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		ah.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if req.Username == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_USERNAME", "Username is required"), httputil.GetTraceID(r))
		return
	}

	if req.Password == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_PASSWORD", "Password is required"), httputil.GetTraceID(r))
		return
	}

	loginReq := &auth.LoginRequest{
		Username: req.Username,
		Password: req.Password,
	}

	resp, err := ah.sessionMgr.Login(r.Context(), loginReq)
	if err != nil {
		ah.errHandler.Handle(w, errors.AuthenticationErrorf("LOGIN_FAILED", "Authentication failed"), httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(resp)
}

// Logout handles POST /api/auth/logout
func (ah *AuthHandlers) Logout(w http.ResponseWriter, r *http.Request) {
	token := r.Header.Get("Authorization")
	if token == "" {
		token = r.Header.Get("X-Auth-Token")
	}

	if token == "" {
		ah.errHandler.Handle(w, errors.AuthenticationErrorf("MISSING_TOKEN", "Token is required"), httputil.GetTraceID(r))
		return
	}

	// Remove "Bearer " prefix if present
	if len(token) > 7 && token[:7] == "Bearer " {
		token = token[7:]
	}

	if err := ah.sessionMgr.Logout(r.Context(), token); err != nil {
		ah.errHandler.Handle(w, errors.AuthenticationErrorf("LOGOUT_FAILED", "Failed to logout"), httputil.GetTraceID(r))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// RefreshToken handles POST /api/auth/refresh
func (ah *AuthHandlers) RefreshToken(w http.ResponseWriter, r *http.Request) {
	token := r.Header.Get("Authorization")
	if token == "" {
		token = r.Header.Get("X-Auth-Token")
	}

	if token == "" {
		ah.errHandler.Handle(w, errors.AuthenticationErrorf("MISSING_TOKEN", "Token is required"), httputil.GetTraceID(r))
		return
	}

	// Remove "Bearer " prefix if present
	if len(token) > 7 && token[:7] == "Bearer " {
		token = token[7:]
	}

	newToken, err := ah.sessionMgr.RefreshToken(r.Context(), token)
	if err != nil {
		ah.errHandler.Handle(w, errors.AuthenticationErrorf("REFRESH_FAILED", "Failed to refresh token"), httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"token": newToken,
	})
}

// ChangePasswordRequest represents a change password request
type ChangePasswordRequest struct {
	OldPassword string `json:"old_password"`
	NewPassword string `json:"new_password"`
}

// ChangePassword handles POST /api/auth/password
func (ah *AuthHandlers) ChangePassword(w http.ResponseWriter, r *http.Request) {
	userID := r.Context().Value("user_id")
	if userID == nil {
		ah.errHandler.Handle(w, errors.AuthenticationErrorf("MISSING_USER_ID", "User ID is required"), httputil.GetTraceID(r))
		return
	}

	var req ChangePasswordRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		ah.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if req.OldPassword == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_OLD_PASSWORD", "Old password is required"), httputil.GetTraceID(r))
		return
	}

	if req.NewPassword == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_NEW_PASSWORD", "New password is required"), httputil.GetTraceID(r))
		return
	}

	err := ah.userService.UpdatePassword(r.Context(), userID.(string), req.OldPassword, req.NewPassword)
	if err != nil {
		ah.errHandler.Handle(w, errors.AuthenticationErrorf("PASSWORD_UPDATE_FAILED", "Failed to update password"), httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"message": "Password updated successfully",
	})
}

// ResetPasswordRequest represents a reset password request
type ResetPasswordRequest struct {
	Email string `json:"email"`
}

// ResetPassword handles POST /api/auth/password/reset
func (ah *AuthHandlers) ResetPassword(w http.ResponseWriter, r *http.Request) {
	var req ResetPasswordRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		ah.errHandler.Handle(w, errors.ValidationErrorf("INVALID_JSON", "Invalid request body"), httputil.GetTraceID(r))
		return
	}

	if req.Email == "" {
		ah.errHandler.Handle(w, errors.ValidationErrorf("MISSING_EMAIL", "Email is required"), httputil.GetTraceID(r))
		return
	}

	user, err := ah.userService.GetByEmail(r.Context(), req.Email)
	if err != nil {
		// Don't reveal if email exists
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"message": "If email exists, password reset link will be sent",
		})
		return
	}

	// TODO: Send password reset email with token
	// For now, just acknowledge the request
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"message": "Password reset link sent to " + user.Email,
	})
}

// Verify handles GET /api/auth/verify
func (ah *AuthHandlers) Verify(w http.ResponseWriter, r *http.Request) {
	token := r.Header.Get("Authorization")
	if token == "" {
		token = r.Header.Get("X-Auth-Token")
	}

	if token == "" {
		ah.errHandler.Handle(w, errors.AuthenticationErrorf("MISSING_TOKEN", "Token is required"), httputil.GetTraceID(r))
		return
	}

	// Remove "Bearer " prefix if present
	if len(token) > 7 && token[:7] == "Bearer " {
		token = token[7:]
	}

	user, err := ah.sessionMgr.ValidateSession(r.Context(), token)
	if err != nil {
		ah.errHandler.Handle(w, errors.AuthenticationErrorf("INVALID_TOKEN", "Invalid or expired token"), httputil.GetTraceID(r))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"user_id":  user.ID,
		"username": user.Username,
		"email":    user.Email,
		"status":   user.Status,
	})
}

// RegisterAuthRoutes registers auth routes
func RegisterAuthRoutes(r interface {
	Post(pattern string, handlerFn http.HandlerFunc)
	Get(pattern string, handlerFn http.HandlerFunc)
}, handlers *AuthHandlers) {
	r.Post("/login", handlers.Login)
	r.Post("/logout", handlers.Logout)
	r.Post("/refresh", handlers.RefreshToken)
	r.Post("/password", handlers.ChangePassword)
	r.Post("/password/reset", handlers.ResetPassword)
	r.Get("/verify", handlers.Verify)
}
