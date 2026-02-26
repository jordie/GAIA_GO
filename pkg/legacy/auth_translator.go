package legacy

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
)

// AuthTranslator handles authentication token translation between legacy and new format
type AuthTranslator struct {
	mu             sync.RWMutex
	tokenCache     map[string]*TokenMapping
	cacheTimeout   time.Duration
	lastCacheClean time.Time
}

// TokenMapping represents a mapping between legacy and new tokens
type TokenMapping struct {
	LegacyToken  string
	NewToken     string
	UserID       string
	CreatedAt    time.Time
	ExpiresAt    time.Time
	LegacyFormat string // Format of legacy token: "session_id", "api_key", "jwt_legacy"
}

// NewAuthTranslator creates a new auth translator
func NewAuthTranslator() *AuthTranslator {
	return &AuthTranslator{
		tokenCache:   make(map[string]*TokenMapping),
		cacheTimeout: 24 * time.Hour,
	}
}

// TranslateLegacyToken converts a legacy token to a new JWT token
func (at *AuthTranslator) TranslateLegacyToken(legacyToken string, headers map[string]string) (string, *TokenInfo, error) {
	at.mu.Lock()
	defer at.mu.Unlock()

	// Check cache first
	if mapping, exists := at.tokenCache[legacyToken]; exists {
		if time.Now().Before(mapping.ExpiresAt) {
			return mapping.NewToken, &TokenInfo{
				UserID:    mapping.UserID,
				Format:    mapping.LegacyFormat,
				Cached:    true,
				CachedAt:  mapping.CreatedAt,
			}, nil
		}
		// Token expired, remove from cache
		delete(at.tokenCache, legacyToken)
	}

	// Parse legacy token to extract user ID
	format, userID, err := at.parseLegacyToken(legacyToken, headers)
	if err != nil {
		return "", nil, fmt.Errorf("failed to parse legacy token: %w", err)
	}

	// Generate new token
	newToken := at.generateNewToken(userID)

	// Cache the mapping
	mapping := &TokenMapping{
		LegacyToken:  legacyToken,
		NewToken:     newToken,
		UserID:       userID,
		CreatedAt:    time.Now(),
		ExpiresAt:    time.Now().Add(at.cacheTimeout),
		LegacyFormat: format,
	}

	at.tokenCache[legacyToken] = mapping

	return newToken, &TokenInfo{
		UserID:    userID,
		Format:    format,
		Cached:    false,
		CachedAt:  time.Time{},
	}, nil
}

// TokenInfo contains information about a translated token
type TokenInfo struct {
	UserID   string
	Format   string // Format of original token
	Cached   bool
	CachedAt time.Time
}

// parseLegacyToken extracts user ID from various legacy token formats
func (at *AuthTranslator) parseLegacyToken(token string, headers map[string]string) (string, string, error) {
	// Try different token formats

	// Format 1: Session ID (GAIA_HOME session format)
	if at.isValidSessionID(token) {
		// Extract user ID from session headers or token
		if userID, ok := headers["X-User-ID"]; ok && userID != "" {
			return "session_id", userID, nil
		}
		// Fallback: use session ID as user ID
		return "session_id", token, nil
	}

	// Format 2: JWT (legacy JWT format from Python)
	if strings.HasPrefix(token, "eyJ") {
		// JWT token - extract claims
		userID, err := at.extractJWTUserID(token)
		if err == nil && userID != "" {
			return "jwt_legacy", userID, nil
		}
	}

	// Format 3: API Key (GAIA_HOME API key format)
	if strings.HasPrefix(token, "gaia_") || strings.HasPrefix(token, "gaia-") {
		// API key format
		userID := at.extractAPIKeyUserID(token)
		if userID != "" {
			return "api_key", userID, nil
		}
	}

	// Format 4: Bearer token
	if strings.HasPrefix(token, "Bearer ") {
		actualToken := strings.TrimPrefix(token, "Bearer ")
		return at.parseLegacyToken(actualToken, headers)
	}

	// Format 5: Basic auth (extract from headers)
	if auth, ok := headers["Authorization"]; ok {
		if strings.HasPrefix(auth, "Basic ") {
			userID, err := at.extractBasicAuthUserID(auth)
			if err == nil && userID != "" {
				return "basic_auth", userID, nil
			}
		}
	}

	// Unknown format
	return "unknown", "", fmt.Errorf("unable to parse legacy token format")
}

// isValidSessionID checks if a string looks like a session ID
func (at *AuthTranslator) isValidSessionID(token string) bool {
	// Session IDs are typically UUIDs or have specific patterns
	// Try to parse as UUID
	_, err := uuid.Parse(token)
	if err == nil {
		return true
	}

	// Check for GAIA session patterns
	if strings.HasPrefix(token, "session-") || strings.HasPrefix(token, "sess-") {
		return true
	}

	return false
}

// extractJWTUserID extracts user ID from JWT claims (without validation)
func (at *AuthTranslator) extractJWTUserID(token string) (string, error) {
	// Note: This is a simplified extraction that doesn't validate the JWT
	// In production, you would validate the signature

	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return "", fmt.Errorf("invalid JWT format")
	}

	// Decode payload (second part)
	// JWT payload is base64url encoded
	payload := parts[1]

	// Add padding if needed
	switch len(payload) % 4 {
	case 2:
		payload += "=="
	case 3:
		payload += "="
	}

	// In a real implementation, we'd decode the base64 and parse JSON
	// For now, we'll just extract a pattern or use a placeholder
	// This is a limitation of not validating the JWT

	// Try to extract sub or user_id from the token structure
	if strings.Contains(token, "sub") {
		// Has a subject claim
		return "user_" + hashToken(token), nil
	}

	return "", fmt.Errorf("unable to extract user ID from JWT")
}

// extractAPIKeyUserID extracts user ID from API key format
func (at *AuthTranslator) extractAPIKeyUserID(token string) string {
	// API key format: gaia_USERID_HASH or gaia-USERID-HASH
	parts := strings.FieldsFunc(token, func(r rune) bool {
		return r == '_' || r == '-'
	})

	if len(parts) >= 2 {
		// Second part is typically the user ID
		return parts[1]
	}

	// Fallback: hash the API key to create a consistent user ID
	return "user_" + hashToken(token)
}

// extractBasicAuthUserID extracts user ID from Basic auth header
func (at *AuthTranslator) extractBasicAuthUserID(auth string) (string, error) {
	// Basic auth format: "Basic base64(username:password)"
	// We'll just use the username as user ID

	// Remove "Basic " prefix
	encoded := strings.TrimPrefix(auth, "Basic ")

	// In a real implementation, decode base64 and extract username
	// For now, hash it to create a consistent user ID
	return "user_" + hashToken(encoded), nil
}

// generateNewToken creates a new JWT-like token for GAIA_GO
func (at *AuthTranslator) generateNewToken(userID string) string {
	// Generate a new token in GAIA_GO format
	// This is a simplified token - in production, you'd use proper JWT signing

	tokenID := uuid.New().String()
	timestamp := time.Now().Unix()

	// Create a token that GAIA_GO can understand
	// Format: gaia_go_USERID_TOKENID_TIMESTAMP
	token := fmt.Sprintf("gaia_go_%s_%s_%d",
		sanitizeUserID(userID),
		tokenID[:8],
		timestamp,
	)

	return token
}

// sanitizeUserID removes special characters from user ID for safe token usage
func sanitizeUserID(userID string) string {
	// Replace common non-alphanumeric characters
	replacer := strings.NewReplacer(
		" ", "_",
		"@", "_",
		".", "_",
		"-", "_",
	)
	return replacer.Replace(userID)
}

// hashToken creates a hash of a token for consistent user IDs
func hashToken(token string) string {
	hash := sha256.Sum256([]byte(token))
	return hex.EncodeToString(hash[:])[:12] // First 12 chars
}

// ValidateLegacyAuthHeader validates legacy authentication headers
func (at *AuthTranslator) ValidateLegacyAuthHeader(headers map[string]string) (bool, error) {
	// Check for various legacy auth formats

	// Format 1: Authorization header with token
	if auth, ok := headers["Authorization"]; ok && auth != "" {
		// Should be "Bearer TOKEN" or "Basic BASE64" or other formats
		if strings.HasPrefix(auth, "Bearer ") ||
			strings.HasPrefix(auth, "Basic ") ||
			strings.HasPrefix(auth, "Token ") {
			return true, nil
		}
		return false, fmt.Errorf("unsupported authorization format")
	}

	// Format 2: X-API-Key header
	if apiKey, ok := headers["X-API-Key"]; ok && apiKey != "" {
		if strings.HasPrefix(apiKey, "gaia_") {
			return true, nil
		}
		return false, fmt.Errorf("invalid API key format")
	}

	// Format 3: Session-specific headers
	if sessionID, ok := headers["X-Session-ID"]; ok && sessionID != "" {
		return true, nil
	}

	// Format 4: Custom Python client token
	if legacyToken, ok := headers["X-Legacy-Token"]; ok && legacyToken != "" {
		return true, nil
	}

	// No auth found
	return false, fmt.Errorf("no authentication provided")
}

// GetAuthFormat detects the authentication format from headers
func (at *AuthTranslator) GetAuthFormat(headers map[string]string) string {
	if auth, ok := headers["Authorization"]; ok {
		if strings.HasPrefix(auth, "Bearer ") {
			if strings.HasPrefix(auth, "Bearer eyJ") {
				return "jwt"
			}
			return "bearer_token"
		}
		if strings.HasPrefix(auth, "Basic ") {
			return "basic_auth"
		}
		if strings.HasPrefix(auth, "Token ") {
			return "token_auth"
		}
	}

	if _, ok := headers["X-API-Key"]; ok {
		return "api_key"
	}

	if _, ok := headers["X-Session-ID"]; ok {
		return "session_id"
	}

	if _, ok := headers["X-Legacy-Token"]; ok {
		return "legacy_token"
	}

	return "unknown"
}

// ClearExpiredTokens removes expired token mappings from cache
func (at *AuthTranslator) ClearExpiredTokens() {
	at.mu.Lock()
	defer at.mu.Unlock()

	now := time.Now()
	for token, mapping := range at.tokenCache {
		if now.After(mapping.ExpiresAt) {
			delete(at.tokenCache, token)
		}
	}

	at.lastCacheClean = now
}

// GetTokenCacheStats returns statistics about cached tokens
func (at *AuthTranslator) GetTokenCacheStats() map[string]interface{} {
	at.mu.RLock()
	defer at.mu.RUnlock()

	validTokens := 0
	expiredTokens := 0
	now := time.Now()

	for _, mapping := range at.tokenCache {
		if now.Before(mapping.ExpiresAt) {
			validTokens++
		} else {
			expiredTokens++
		}
	}

	return map[string]interface{}{
		"total_cached_tokens":  len(at.tokenCache),
		"valid_tokens":         validTokens,
		"expired_tokens":       expiredTokens,
		"last_cache_clean":     at.lastCacheClean.Format(time.RFC3339),
		"cache_timeout_hours":  int(at.cacheTimeout.Hours()),
	}
}

// MigrateAuthHeader converts legacy auth headers to new format
func (at *AuthTranslator) MigrateAuthHeader(headers map[string]string) (map[string]string, error) {
	newHeaders := make(map[string]string)

	// Copy non-auth headers
	for key, value := range headers {
		if !isAuthHeader(key) {
			newHeaders[key] = value
		}
	}

	// Get legacy token
	var legacyToken string
	var found bool

	if auth, ok := headers["Authorization"]; ok && auth != "" {
		legacyToken = auth
		found = true
	} else if apiKey, ok := headers["X-API-Key"]; ok && apiKey != "" {
		legacyToken = apiKey
		found = true
	} else if sessionID, ok := headers["X-Session-ID"]; ok && sessionID != "" {
		legacyToken = sessionID
		found = true
	} else if token, ok := headers["X-Legacy-Token"]; ok && token != "" {
		legacyToken = token
		found = true
	}

	if !found {
		return newHeaders, fmt.Errorf("no authentication header found")
	}

	// Translate token
	newToken, tokenInfo, err := at.TranslateLegacyToken(legacyToken, headers)
	if err != nil {
		return newHeaders, err
	}

	// Add new auth header
	newHeaders["Authorization"] = "Bearer " + newToken

	// Add migration info headers
	newHeaders["X-Legacy-Format"] = tokenInfo.Format
	newHeaders["X-User-ID"] = tokenInfo.UserID

	return newHeaders, nil
}

// isAuthHeader checks if a header is authentication-related
func isAuthHeader(key string) bool {
	authHeaders := map[string]bool{
		"Authorization":    true,
		"X-API-Key":        true,
		"X-Session-ID":     true,
		"X-Legacy-Token":   true,
		"X-Auth-Token":     true,
		"Cookie":           true,
	}
	return authHeaders[key]
}

// ExtractUserIDFromLegacyAuth extracts just the user ID from legacy auth
func (at *AuthTranslator) ExtractUserIDFromLegacyAuth(headers map[string]string) (string, error) {
	var legacyToken string

	if auth, ok := headers["Authorization"]; ok {
		legacyToken = auth
	} else if apiKey, ok := headers["X-API-Key"]; ok {
		legacyToken = apiKey
	} else if sessionID, ok := headers["X-Session-ID"]; ok {
		legacyToken = sessionID
	} else if token, ok := headers["X-Legacy-Token"]; ok {
		legacyToken = token
	}

	if legacyToken == "" {
		return "", fmt.Errorf("no authentication token found")
	}

	// Check cache first
	at.mu.RLock()
	if mapping, exists := at.tokenCache[legacyToken]; exists {
		if time.Now().Before(mapping.ExpiresAt) {
			defer at.mu.RUnlock()
			return mapping.UserID, nil
		}
	}
	at.mu.RUnlock()

	// Parse token
	_, userID, err := at.parseLegacyToken(legacyToken, headers)
	return userID, err
}
