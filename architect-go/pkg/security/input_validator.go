package security

import (
	"fmt"
	"html"
	"regexp"
	"strings"
)

// InputValidator validates user input to prevent injection attacks
type InputValidator struct {
	maxStringLength int
	maxIntValue     int
}

// NewInputValidator creates a new input validator
func NewInputValidator() *InputValidator {
	return &InputValidator{
		maxStringLength: 10000,
		maxIntValue:     2147483647,
	}
}

// ValidateString validates and sanitizes string input
func (iv *InputValidator) ValidateString(value string, fieldName string, minLen, maxLen int) error {
	if len(value) < minLen {
		return fmt.Errorf("%s must be at least %d characters", fieldName, minLen)
	}
	if len(value) > maxLen {
		return fmt.Errorf("%s must not exceed %d characters", fieldName, maxLen)
	}
	return nil
}

// SanitizeString removes potentially dangerous characters from input
func (iv *InputValidator) SanitizeString(value string) string {
	// HTML escape
	value = html.EscapeString(value)
	// Remove null bytes
	value = strings.ReplaceAll(value, "\x00", "")
	return value
}

// ValidateEmail validates email format
func (iv *InputValidator) ValidateEmail(email string) error {
	if len(email) > 255 {
		return fmt.Errorf("email too long")
	}
	// Simple email validation regex
	emailRegex := regexp.MustCompile(`^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`)
	if !emailRegex.MatchString(email) {
		return fmt.Errorf("invalid email format")
	}
	return nil
}

// ValidateID validates ID format (UUID or alphanumeric)
func (iv *InputValidator) ValidateID(id string) error {
	if len(id) == 0 {
		return fmt.Errorf("ID cannot be empty")
	}
	if len(id) > 36 {
		return fmt.Errorf("ID too long")
	}

	// Allow UUID and alphanumeric with dashes
	idRegex := regexp.MustCompile(`^[a-zA-Z0-9-]+$`)
	if !idRegex.MatchString(id) {
		return fmt.Errorf("invalid ID format")
	}
	return nil
}

// ValidateURL validates URL format
func (iv *InputValidator) ValidateURL(urlString string) error {
	if len(urlString) > 2048 {
		return fmt.Errorf("URL too long")
	}

	// Simple URL validation
	urlRegex := regexp.MustCompile(`^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`)
	if !urlRegex.MatchString(urlString) {
		return fmt.Errorf("invalid URL format")
	}
	return nil
}

// ValidateJSON validates JSON structure
func (iv *InputValidator) ValidateJSONSize(jsonData []byte) error {
	if len(jsonData) == 0 {
		return fmt.Errorf("JSON data cannot be empty")
	}
	if len(jsonData) > 1048576 { // 1MB limit
		return fmt.Errorf("JSON data too large")
	}
	return nil
}

// ValidateIntRange validates integer is within acceptable range
func (iv *InputValidator) ValidateIntRange(value int, min, max int) error {
	if value < min || value > max {
		return fmt.Errorf("value must be between %d and %d", min, max)
	}
	return nil
}

// ValidatePagination validates pagination parameters
func (iv *InputValidator) ValidatePagination(limit, offset int) error {
	if limit < 1 {
		return fmt.Errorf("limit must be at least 1")
	}
	if limit > 1000 {
		return fmt.Errorf("limit must not exceed 1000")
	}
	if offset < 0 {
		return fmt.Errorf("offset must be non-negative")
	}
	return nil
}

// ValidateStatus validates status values
func (iv *InputValidator) ValidateStatus(status string, allowedValues []string) error {
	for _, allowed := range allowedValues {
		if status == allowed {
			return nil
		}
	}
	return fmt.Errorf("invalid status: %s", status)
}

// PreventSQLInjection checks for common SQL injection patterns
func (iv *InputValidator) PreventSQLInjection(value string) error {
	dangerousPatterns := []string{
		"DROP",
		"DELETE",
		"INSERT",
		"UPDATE",
		"UNION",
		"SELECT",
		"--",
		"/*",
		"*/",
		"xp_",
		"sp_",
		"';",
	}

	upperValue := strings.ToUpper(value)
	for _, pattern := range dangerousPatterns {
		if strings.Contains(upperValue, pattern) {
			return fmt.Errorf("potentially dangerous SQL pattern detected")
		}
	}
	return nil
}

// PreventXSS checks for common XSS patterns
func (iv *InputValidator) PreventXSS(value string) error {
	xssPatterns := []string{
		"<script",
		"javascript:",
		"onerror=",
		"onload=",
		"onclick=",
		"<iframe",
		"<embed",
		"<object",
	}

	lowerValue := strings.ToLower(value)
	for _, pattern := range xssPatterns {
		if strings.Contains(lowerValue, pattern) {
			return fmt.Errorf("potentially dangerous XSS pattern detected")
		}
	}
	return nil
}

// ValidateAndSanitize performs complete validation and sanitization
func (iv *InputValidator) ValidateAndSanitize(value string, fieldType string) (string, error) {
	// Check for SQL injection
	if err := iv.PreventSQLInjection(value); err != nil {
		return "", err
	}

	// Check for XSS
	if err := iv.PreventXSS(value); err != nil {
		return "", err
	}

	// Sanitize
	sanitized := iv.SanitizeString(value)

	// Validate based on type
	switch fieldType {
	case "email":
		if err := iv.ValidateEmail(sanitized); err != nil {
			return "", err
		}
	case "url":
		if err := iv.ValidateURL(sanitized); err != nil {
			return "", err
		}
	case "id":
		if err := iv.ValidateID(sanitized); err != nil {
			return "", err
		}
	}

	return sanitized, nil
}
