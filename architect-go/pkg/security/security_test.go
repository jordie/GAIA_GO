package security

import (
	"crypto/rand"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestCredentialManager_EncryptDecrypt tests encryption and decryption
func TestCredentialManager_EncryptDecrypt(t *testing.T) {
	key := make([]byte, 32)
	rand.Read(key)

	cm, err := NewCredentialManager(key)
	require.NoError(t, err)

	plaintext := "super-secret-api-key-12345"
	encrypted, err := cm.EncryptCredential(plaintext)
	require.NoError(t, err)
	assert.NotEqual(t, plaintext, encrypted)

	decrypted, err := cm.DecryptCredential(encrypted)
	require.NoError(t, err)
	assert.Equal(t, plaintext, decrypted)
}

// TestCredentialManager_InvalidKey tests invalid key handling
func TestCredentialManager_InvalidKey(t *testing.T) {
	invalidKey := []byte("too-short")
	_, err := NewCredentialManager(invalidKey)
	assert.Error(t, err)
}

// TestCredentialManager_MaskCredential tests credential masking
func TestCredentialManager_MaskCredential(t *testing.T) {
	key := make([]byte, 32)
	rand.Read(key)

	cm, _ := NewCredentialManager(key)

	credential := "super-secret-api-key-1234567890"
	masked := cm.MaskCredential(credential, 4)

	assert.NotContains(t, masked, credential[4:28])
	assert.Contains(t, masked, "supe")  // First 4 chars
	assert.Contains(t, masked, "7890")  // Last 4 chars
	assert.Contains(t, masked, "***")   // Masked middle
}

// TestCredentialManager_ValidateCredentialFormat tests format validation
func TestCredentialManager_ValidateCredentialFormat(t *testing.T) {
	key := make([]byte, 32)
	rand.Read(key)

	cm, _ := NewCredentialManager(key)

	tests := []struct {
		credType string
		value    string
		hasErr   bool
	}{
		{"api_key", "short", true},
		{"api_key", "this-is-a-valid-api-key-with-32-characters", false},
		{"password", "short", true},
		{"password", "ValidPassword123!", false},
		{"token", "short", true},
		{"token", "this-is-a-valid-token-token", false},
	}

	for _, tt := range tests {
		err := cm.ValidateCredentialFormat(tt.credType, tt.value)
		if tt.hasErr {
			assert.Error(t, err)
		} else {
			assert.NoError(t, err)
		}
	}
}

// TestInputValidator_ValidateString tests string validation
func TestInputValidator_ValidateString(t *testing.T) {
	iv := NewInputValidator()

	tests := []struct {
		value  string
		minLen int
		maxLen int
		hasErr bool
	}{
		{"", 1, 100, true},      // Too short
		{"short", 10, 100, true}, // Below min
		{"valid", 1, 10, false},
		{strings.Repeat("x", 200), 1, 100, true}, // Exceeds max
	}

	for _, tt := range tests {
		err := iv.ValidateString(tt.value, "test", tt.minLen, tt.maxLen)
		if tt.hasErr {
			assert.Error(t, err)
		} else {
			assert.NoError(t, err)
		}
	}
}

// TestInputValidator_ValidateEmail tests email validation
func TestInputValidator_ValidateEmail(t *testing.T) {
	iv := NewInputValidator()

	tests := []struct {
		email  string
		hasErr bool
	}{
		{"user@example.com", false},
		{"invalid.email", true},
		{"@example.com", true},
		{"user@", true},
		{"user@example", true},
		{"user+tag@example.co.uk", false},
	}

	for _, tt := range tests {
		err := iv.ValidateEmail(tt.email)
		if tt.hasErr {
			assert.Error(t, err)
		} else {
			assert.NoError(t, err)
		}
	}
}

// TestInputValidator_ValidateID tests ID validation
func TestInputValidator_ValidateID(t *testing.T) {
	iv := NewInputValidator()

	tests := []struct {
		id     string
		hasErr bool
	}{
		{"", true},                            // Empty
		{"valid-id-123", false},
		{"550e8400-e29b-41d4-a716-446655440000", false},
		{"invalid id with spaces", true},
		{"invalid@id#symbols", true},
	}

	for _, tt := range tests {
		err := iv.ValidateID(tt.id)
		if tt.hasErr {
			assert.Error(t, err)
		} else {
			assert.NoError(t, err)
		}
	}
}

// TestInputValidator_PreventSQLInjection tests SQL injection prevention
func TestInputValidator_PreventSQLInjection(t *testing.T) {
	iv := NewInputValidator()

	tests := []struct {
		value  string
		hasErr bool
	}{
		{"normal input", false},
		{"'; DROP TABLE users;--", true},
		{"1 UNION SELECT * FROM users", true},
		{"admin'--", true},
		{"1 OR 1=1", false}, // Not a SQL keyword
	}

	for _, tt := range tests {
		err := iv.PreventSQLInjection(tt.value)
		if tt.hasErr {
			assert.Error(t, err)
		} else {
			assert.NoError(t, err)
		}
	}
}

// TestInputValidator_PreventXSS tests XSS prevention
func TestInputValidator_PreventXSS(t *testing.T) {
	iv := NewInputValidator()

	tests := []struct {
		value  string
		hasErr bool
	}{
		{"normal text", false},
		{"<script>alert('xss')</script>", true},
		{"<img src='x' onerror='alert(1)'>", true},
		{"javascript:alert('xss')", true},
		{"<iframe src='evil.com'></iframe>", true},
		{"onclick='malicious()'", true},
	}

	for _, tt := range tests {
		err := iv.PreventXSS(tt.value)
		if tt.hasErr {
			assert.Error(t, err)
		} else {
			assert.NoError(t, err)
		}
	}
}

// TestInputValidator_SanitizeString tests string sanitization
func TestInputValidator_SanitizeString(t *testing.T) {
	iv := NewInputValidator()

	input := "Test & <script>alert('xss')</script>"
	sanitized := iv.SanitizeString(input)

	assert.NotContains(t, sanitized, "<script>")
	assert.Contains(t, sanitized, "&amp;")
}

// TestInputValidator_ValidatePagination tests pagination validation
func TestInputValidator_ValidatePagination(t *testing.T) {
	iv := NewInputValidator()

	tests := []struct {
		limit  int
		offset int
		hasErr bool
	}{
		{20, 0, false},
		{0, 0, true},      // limit too small
		{1001, 0, true},   // limit too large
		{20, -1, true},    // negative offset
		{100, 100, false},
	}

	for _, tt := range tests {
		err := iv.ValidatePagination(tt.limit, tt.offset)
		if tt.hasErr {
			assert.Error(t, err)
		} else {
			assert.NoError(t, err)
		}
	}
}

// TestInputValidator_ValidateAndSanitize tests complete validation
func TestInputValidator_ValidateAndSanitize(t *testing.T) {
	iv := NewInputValidator()

	// Valid email
	sanitized, err := iv.ValidateAndSanitize("user@example.com", "email")
	assert.NoError(t, err)
	assert.Equal(t, "user@example.com", sanitized)

	// SQL injection attempt
	_, err = iv.ValidateAndSanitize("'; DROP TABLE users;--", "string")
	assert.Error(t, err)

	// XSS attempt
	_, err = iv.ValidateAndSanitize("<script>alert('xss')</script>", "string")
	assert.Error(t, err)
}

// TestInputValidator_ValidateStatus tests status validation
func TestInputValidator_ValidateStatus(t *testing.T) {
	iv := NewInputValidator()

	allowedStatuses := []string{"active", "inactive", "pending"}

	tests := []struct {
		status string
		hasErr bool
	}{
		{"active", false},
		{"inactive", false},
		{"deleted", true},
		{"unknown", true},
	}

	for _, tt := range tests {
		err := iv.ValidateStatus(tt.status, allowedStatuses)
		if tt.hasErr {
			assert.Error(t, err)
		} else {
			assert.NoError(t, err)
		}
	}
}

// TestDefaultRotationPolicy tests default rotation policy
func TestDefaultRotationPolicy(t *testing.T) {
	policy := DefaultRotationPolicy()

	assert.Equal(t, 365, policy.MaxAge)
	assert.Equal(t, 90, policy.RotationInterval)
	assert.Equal(t, 7, policy.GracePeriod)
}
