package rate_limiting

import (
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
)

// MiddlewareConfig configures rate limiting middleware behavior
type MiddlewareConfig struct {
	SystemID string
	Enabled  bool

	// Extract scope from request
	ExtractScope      func(r *http.Request) string      // Default: IP
	ExtractScopeValue func(r *http.Request) string      // Default: remote IP
	ExtractResource   func(r *http.Request) string      // Default: endpoint path

	// Response customization
	RateLimitedHandler func(http.ResponseWriter, *http.Request, Decision) // Default: 429 JSON

	// Skip certain requests
	SkipPaths map[string]bool // Paths to skip rate limiting
}

// DefaultMiddlewareConfig returns default configuration
func DefaultMiddlewareConfig(systemID string) MiddlewareConfig {
	return MiddlewareConfig{
		SystemID: systemID,
		Enabled:  true,
		ExtractScope: func(r *http.Request) string {
			return ScopeIP
		},
		ExtractScopeValue: func(r *http.Request) string {
			return getClientIP(r)
		},
		ExtractResource: func(r *http.Request) string {
			return r.URL.Path
		},
		RateLimitedHandler: defaultRateLimitedHandler,
		SkipPaths:          make(map[string]bool),
	}
}

// Middleware creates a rate limiting middleware for Chi
func Middleware(limiter RateLimiter, cfg MiddlewareConfig) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Skip if disabled
			if !cfg.Enabled {
				next.ServeHTTP(w, r)
				return
			}

			// Skip health check and other essential endpoints
			if cfg.SkipPaths[r.URL.Path] {
				next.ServeHTTP(w, r)
				return
			}

			// Extract request metadata
			req := LimitCheckRequest{
				SystemID:     cfg.SystemID,
				Scope:        cfg.ExtractScope(r),
				ScopeValue:   cfg.ExtractScopeValue(r),
				ResourceType: cfg.ExtractResource(r),
				RequestPath:  r.URL.Path,
				Method:       r.Method,
				Headers: map[string]string{
					"user-agent": r.UserAgent(),
				},
			}

			// Check rate limit
			decision, err := limiter.CheckLimit(r.Context(), req)
			if err != nil {
				// Log error but allow request
				next.ServeHTTP(w, r)
				return
			}

			// Set rate limit headers
			setRateLimitHeaders(w, decision)

			// Handle rate limit decision
			if !decision.Allowed {
				cfg.RateLimitedHandler(w, r, decision)
				return
			}

			// Request allowed, continue
			next.ServeHTTP(w, r)
		})
	}
}

// setRateLimitHeaders sets X-RateLimit-* response headers
func setRateLimitHeaders(w http.ResponseWriter, decision Decision) {
	w.Header().Set("X-RateLimit-Limit", strconv.Itoa(decision.Limit))
	w.Header().Set("X-RateLimit-Remaining", strconv.Itoa(decision.Remaining))
	w.Header().Set("X-RateLimit-Reset", strconv.FormatInt(decision.ResetTime.Unix(), 10))

	if decision.RetryAfterSeconds > 0 {
		w.Header().Set("Retry-After", strconv.Itoa(decision.RetryAfterSeconds))
	}
}

// defaultRateLimitedHandler sends a 429 response
func defaultRateLimitedHandler(w http.ResponseWriter, r *http.Request, decision Decision) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Retry-After", strconv.Itoa(decision.RetryAfterSeconds))
	w.WriteHeader(http.StatusTooManyRequests)

	responseBody := map[string]interface{}{
		"error":             "rate_limit_exceeded",
		"message":           decision.Reason,
		"limit":             decision.Limit,
		"remaining":         decision.Remaining,
		"retry_after_sec":   decision.RetryAfterSeconds,
		"reset_time":        decision.ResetTime.Unix(),
	}

	// Simple JSON encoding
	w.Write([]byte(`{"error":"rate_limit_exceeded","message":"` + decision.Reason + `","limit":` +
		strconv.Itoa(decision.Limit) + `,"remaining":` + strconv.Itoa(decision.Remaining) +
		`,"retry_after_sec":` + strconv.Itoa(decision.RetryAfterSeconds) + `}`))
}

// getClientIP extracts client IP from request
func getClientIP(r *http.Request) string {
	// Check X-Forwarded-For header (from load balancer/proxy)
	if forwarded := r.Header.Get("X-Forwarded-For"); forwarded != "" {
		// X-Forwarded-For can contain multiple IPs, take the first
		ips := strings.Split(forwarded, ",")
		if len(ips) > 0 {
			return strings.TrimSpace(ips[0])
		}
	}

	// Check X-Real-IP header
	if realIP := r.Header.Get("X-Real-IP"); realIP != "" {
		return realIP
	}

	// Fall back to RemoteAddr
	if colon := strings.LastIndex(r.RemoteAddr, ":"); colon != -1 {
		return r.RemoteAddr[:colon]
	}
	return r.RemoteAddr
}

// SessionExtractor extracts session ID from request
func SessionExtractor(r *http.Request) string {
	// Try query parameter first
	if sessionID := r.URL.Query().Get("session_id"); sessionID != "" {
		return sessionID
	}

	// Try header
	if sessionID := r.Header.Get("X-Session-ID"); sessionID != "" {
		return sessionID
	}

	// Try cookie
	if cookie, err := r.Cookie("session_id"); err == nil && cookie.Value != "" {
		return cookie.Value
	}

	// Fall back to IP
	return getClientIP(r)
}

// APIKeyExtractor extracts API key from request
func APIKeyExtractor(r *http.Request) string {
	// Try header first (Bearer token)
	if auth := r.Header.Get("Authorization"); auth != "" {
		parts := strings.Fields(auth)
		if len(parts) == 2 && strings.ToLower(parts[0]) == "bearer" {
			return parts[1]
		}
	}

	// Try X-API-Key header
	if apiKey := r.Header.Get("X-API-Key"); apiKey != "" {
		return apiKey
	}

	// Try query parameter
	if apiKey := r.URL.Query().Get("api_key"); apiKey != "" {
		return apiKey
	}

	return ""
}

// WithSessionScope creates a middleware that uses session-based rate limiting
func WithSessionScope(limiter RateLimiter, systemID string) func(http.Handler) http.Handler {
	cfg := DefaultMiddlewareConfig(systemID)
	cfg.ExtractScope = func(r *http.Request) string {
		return ScopeSession
	}
	cfg.ExtractScopeValue = SessionExtractor
	cfg.SkipPaths["/health"] = true

	return Middleware(limiter, cfg)
}

// WithIPScope creates a middleware that uses IP-based rate limiting
func WithIPScope(limiter RateLimiter, systemID string) func(http.Handler) http.Handler {
	cfg := DefaultMiddlewareConfig(systemID)
	cfg.ExtractScope = func(r *http.Request) string {
		return ScopeIP
	}
	cfg.SkipPaths["/health"] = true

	return Middleware(limiter, cfg)
}

// WithAPIKeyScope creates a middleware that uses API key-based rate limiting
func WithAPIKeyScope(limiter RateLimiter, systemID string) func(http.Handler) http.Handler {
	cfg := DefaultMiddlewareConfig(systemID)
	cfg.ExtractScope = func(r *http.Request) string {
		return ScopeAPIKey
	}
	cfg.ExtractScopeValue = APIKeyExtractor
	cfg.SkipPaths["/health"] = true

	return Middleware(limiter, cfg)
}

// RouteRateLimiter limits specific routes
func RouteRateLimiter(limiter RateLimiter, systemID, resourceType string, scope string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			scopeValue := ""
			switch scope {
			case ScopeSession:
				scopeValue = SessionExtractor(r)
			case ScopeAPIKey:
				scopeValue = APIKeyExtractor(r)
			case ScopeIP:
				scopeValue = getClientIP(r)
			default:
				scopeValue = getClientIP(r)
			}

			req := LimitCheckRequest{
				SystemID:     systemID,
				Scope:        scope,
				ScopeValue:   scopeValue,
				ResourceType: resourceType,
				RequestPath:  r.URL.Path,
				Method:       r.Method,
				Headers: map[string]string{
					"user-agent": r.UserAgent(),
				},
			}

			decision, err := limiter.CheckLimit(r.Context(), req)
			if err != nil {
				next.ServeHTTP(w, r)
				return
			}

			setRateLimitHeaders(w, decision)

			if !decision.Allowed {
				defaultRateLimitedHandler(w, r, decision)
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}
