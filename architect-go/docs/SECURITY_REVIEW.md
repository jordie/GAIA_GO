# Security Review and Hardening Guide - Phase 3.2.17

## Overview
This document provides security best practices and implementation guidance for the Architect Dashboard API.

## OWASP Top 10 Mitigation

### 1. Injection (SQL Injection, Command Injection)

**Vulnerability:** Attackers inject malicious SQL/commands through user input

**Mitigation:**
```go
// ✅ GOOD - Parameterized queries
query := db.Where("email = ?", email).First(&user)

// ❌ BAD - String concatenation
query := db.Where("email = '" + email + "'").First(&user)
```

**Validation:**
```go
validator := NewInputValidator()
if err := validator.PreventSQLInjection(userInput); err != nil {
    return err
}
```

### 2. Broken Authentication

**Vulnerability:** Weak password policies, session hijacking

**Mitigation:**
```go
// Implement strong password requirements
- Minimum 12 characters
- Mix of uppercase, lowercase, numbers, special characters
- Not common/dictionary words

// Session management
- Use secure session tokens (256-bit randomness)
- HttpOnly and Secure cookies
- Session timeout: 1 hour default
- Regenerate session ID on login
```

### 3. Broken Access Control

**Vulnerability:** Unauthorized access to resources

**Mitigation:**
```go
// Implement role-based access control (RBAC)
type AuthMiddleware struct {
    requiredRole string
}

func (am *AuthMiddleware) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    user := r.Context().Value("user").(*User)
    if !user.HasRole(am.requiredRole) {
        http.Error(w, "Forbidden", http.StatusForbidden)
        return
    }
}

// Always verify permissions
func (s *Service) UpdateResource(ctx context.Context, resourceID string) error {
    resource, _ := s.repo.Get(ctx, resourceID)
    if !userCanEdit(ctx, resource) {
        return errors.Forbidden("PERMISSION_DENIED", "You cannot edit this resource")
    }
}
```

### 4. Sensitive Data Exposure

**Vulnerability:** Exposing passwords, API keys, PII

**Mitigation:**
```go
// Encrypt sensitive data at rest
cm, _ := NewCredentialManager(encryptionKey)
encrypted, _ := cm.EncryptCredential(apiKey)

// Use HTTPS only (enforce in production)
// Set secure headers
w.Header().Set("Strict-Transport-Security", "max-age=31536000")

// Log safely - never log sensitive data
logger.Info("User login", zap.String("user_id", userID))
// Not: logger.Info("User login", zap.String("password", password))

// Mask credentials in responses
masked := cm.MaskCredential(apiKey, 4) // Shows first 4 and last 4 chars
```

### 5. Broken Object Level Access Control (BOLA)

**Vulnerability:** Direct object references without authorization

**Mitigation:**
```go
// ✅ GOOD - Verify ownership
func (s *Service) GetUserNotification(ctx context.Context, notificationID string) error {
    user := ctx.Value("user").(*User)
    notification, _ := s.repo.Get(ctx, notificationID)

    if notification.UserID != user.ID {
        return errors.Forbidden("FORBIDDEN", "You cannot access this notification")
    }
    return nil
}

// ❌ BAD - No ownership check
func (s *Service) GetUserNotification(ctx context.Context, notificationID string) error {
    notification, _ := s.repo.Get(ctx, notificationID)
    return notification
}
```

### 6. Cross-Site Scripting (XSS)

**Vulnerability:** Injecting malicious scripts into responses

**Mitigation:**
```go
// Sanitize output
validator := NewInputValidator()
if err := validator.PreventXSS(userInput); err != nil {
    return err
}

// HTML escape user-provided content
w.Header().Set("Content-Type", "application/json; charset=utf-8")
json.NewEncoder(w).Encode(map[string]interface{}{
    "message": html.EscapeString(userMessage),
})

// Content Security Policy
w.Header().Set("Content-Security-Policy", "default-src 'self'; script-src 'self'")
```

### 7. Cross-Site Request Forgery (CSRF)

**Vulnerability:** Forging requests on behalf of authenticated users

**Mitigation:**
```go
// Implement CSRF token validation
func (m *CSRFMiddleware) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    if r.Method != "GET" && r.Method != "HEAD" && r.Method != "OPTIONS" {
        token := r.FormValue("csrf_token")
        if !m.validateToken(token) {
            http.Error(w, "CSRF token invalid", http.StatusForbidden)
            return
        }
    }
}

// Use SameSite cookie attribute
cookie := &http.Cookie{
    Name:     "session",
    Value:    sessionToken,
    SameSite: http.SameSiteLaxMode,
    HttpOnly: true,
    Secure:   true,
}
```

### 8. Using Components with Known Vulnerabilities

**Vulnerability:** Outdated dependencies with security flaws

**Mitigation:**
```bash
# Regular dependency scanning
go mod tidy
go list -u -m all

# Use security tools
go install github.com/securego/gosec/v2/cmd/gosec@latest
gosec ./...

# Keep dependencies updated
go get -u ./...
```

### 9. Insufficient Logging & Monitoring

**Vulnerability:** Not detecting attacks or breaches

**Mitigation:**
```go
// Log security events
logger.Info("Failed login attempt",
    zap.String("user_id", userID),
    zap.String("ip_address", r.RemoteAddr),
    zap.Int("failed_attempts", attempts),
)

logger.Warn("Unauthorized access attempt",
    zap.String("resource_id", resourceID),
    zap.String("user_id", userID),
    zap.String("action", "delete"),
)

// Monitor for suspicious patterns
- Multiple failed login attempts
- Accessing resources owned by other users
- Mass data downloads
- Unusual API usage patterns
```

### 10. Server-Side Request Forgery (SSRF)

**Vulnerability:** Forcing server to make requests to unintended targets

**Mitigation:**
```go
// Validate URLs before making requests
validator := NewInputValidator()
if err := validator.ValidateURL(webhookURL); err != nil {
    return err
}

// Prevent requests to internal resources
allowedHosts := []string{"api.example.com", "webhook.example.com"}
if !isHostAllowed(parsedURL.Host, allowedHosts) {
    return errors.Forbidden("INVALID_HOST", "Host not allowed")
}

// Use timeout for external requests
client := &http.Client{
    Timeout: 5 * time.Second,
}
```

## Credential Management

### Secure Storage
```go
// At rest encryption
cm, _ := NewCredentialManager(encryptionKey)
encrypted, _ := cm.EncryptCredential(apiKey)

// Store encrypted in database
credential := &Credential{
    Name:      "slack-api-key",
    Type:      "api_key",
    Value:     encrypted, // Store encrypted value
    CreatedAt: time.Now(),
}
db.Create(credential)
```

### In-Transit Protection
```go
// Always use HTTPS
// In production:
server := &http.Server{
    Addr:      ":443",
    TLSConfig: tlsConfig,
}
server.ListenAndServeTLS(certFile, keyFile)

// Use strong ciphers
TLSConfig: &tls.Config{
    MinVersion:               tls.VersionTLS12,
    PreferServerCipherSuites: true,
    CipherSuites: []uint16{
        tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
        tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
        tls.TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305,
        tls.TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305,
    },
}
```

### Rotation Policy
```go
// Implement credential rotation
type CredentialRotationService struct {
    rotationPolicy CredentialRotationPolicy
}

func (s *CredentialRotationService) CheckRotationNeeded(cred *Credential) bool {
    age := time.Since(cred.CreatedAt).Hours() / 24
    return age > float64(s.rotationPolicy.RotationInterval)
}

// Default: Rotate every 90 days, max age 365 days
```

## API Security Headers

### Essential Headers
```go
// Security headers middleware
func SecurityHeadersMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        // Prevent clickjacking
        w.Header().Set("X-Frame-Options", "DENY")

        // Prevent MIME type sniffing
        w.Header().Set("X-Content-Type-Options", "nosniff")

        // Enable XSS protection
        w.Header().Set("X-XSS-Protection", "1; mode=block")

        // Content Security Policy
        w.Header().Set("Content-Security-Policy", "default-src 'self'")

        // Enforce HTTPS
        w.Header().Set("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

        // Referrer Policy
        w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")

        next.ServeHTTP(w, r)
    })
}
```

## Rate Limiting and Throttling

### API Rate Limiting
```go
import "golang.org/x/time/rate"

type RateLimiter struct {
    limiters map[string]*rate.Limiter
}

// Per-user rate limiting
func (rl *RateLimiter) Allow(userID string) bool {
    limiter := rl.getLimiter(userID)
    return limiter.Allow()
}

// Recommended: 100 requests/second per user, 10 request burst
limiter := rate.NewLimiter(rate.Every(time.Second/100), 10)
```

## Input Validation

### Validation Rules
```go
// Use InputValidator for all external input
validator := NewInputValidator()

// Email validation
if err := validator.ValidateEmail(email); err != nil {
    return err
}

// SQL injection prevention
if err := validator.PreventSQLInjection(query); err != nil {
    return err
}

// XSS prevention
if err := validator.PreventXSS(htmlContent); err != nil {
    return err
}

// Complete validation
sanitized, err := validator.ValidateAndSanitize(userInput, "email")
```

## Database Security

### Connection Security
```go
// Never log connection strings
sqlDB, _ := db.DB()

// Use environment variables for credentials
dsn := os.Getenv("DATABASE_URL")

// Example DSN (never hardcode)
// postgres://user:password@localhost:5432/dbname?sslmode=require
```

### Query Injection Prevention
```go
// Always use parameterized queries
db.Where("email = ?", email).First(&user)

// Never concatenate user input
// WRONG: db.Where("email = '" + email + "'")
```

## Audit Logging

### Security Events to Log
```go
// Authentication events
logger.Info("User logged in",
    zap.String("user_id", userID),
    zap.String("ip_address", ipAddress),
)

logger.Warn("Failed authentication attempt",
    zap.String("email", email),
    zap.String("ip_address", ipAddress),
)

// Authorization events
logger.Warn("Unauthorized access attempt",
    zap.String("resource_id", resourceID),
    zap.String("user_id", userID),
    zap.String("action", "delete"),
)

// Credential events
logger.Info("Credential rotated",
    zap.String("credential_id", credID),
    zap.Time("rotated_at", time.Now()),
)
```

## Security Testing

### Manual Testing
- Test SQL injection on all input fields
- Test XSS on all output
- Test authentication bypass
- Test CSRF tokens
- Test authorization boundaries
- Test rate limiting
- Test sensitive data exposure

### Automated Testing
```bash
# Security scanning with gosec
gosec ./...

# Dependency vulnerability scanning
go list -json -m all | nancy sleuth

# OWASP ZAP scan
zaproxy -cmd -quickurl http://localhost:8080
```

## Security Checklist

- [ ] All sensitive data encrypted at rest
- [ ] HTTPS enforced in production
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention verified
- [ ] XSS prevention verified
- [ ] CSRF tokens implemented
- [ ] Rate limiting configured
- [ ] Security headers enabled
- [ ] Credential rotation policy implemented
- [ ] Audit logging for security events
- [ ] Dependencies up-to-date
- [ ] No hardcoded credentials
- [ ] Error messages don't leak information
- [ ] Access control verified on all endpoints
- [ ] Security testing automated in CI/CD

## Deployment Security

### Environment Variables
```bash
# Use .env file (never commit)
ENCRYPTION_KEY=<32-byte-hex-key>
DATABASE_URL=postgres://...?sslmode=require
JWT_SECRET=<strong-random-string>
API_KEY_SALT=<random-string>
```

### TLS Configuration
```bash
# Generate self-signed cert (testing only)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365

# In production use proper certificates (Let's Encrypt, etc.)
```

## Incident Response

### Security Incident Procedure
1. Identify and isolate the incident
2. Preserve evidence and logs
3. Notify security team
4. Assess impact and scope
5. Remediate vulnerabilities
6. Post-incident review
7. Document lessons learned

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)
- [Go Security Best Practices](https://golang.org/doc/effective_go)
- [CWE Top 25](https://cwe.mitre.org/top25/)
