package auth

import (
	"crypto/rand"
	"encoding/base64"
	"fmt"

	"golang.org/x/crypto/scrypt"
)

// PasswordManager handles password hashing and verification
type PasswordManager struct {
	saltLength int
	n          int
	r          int
	p          int
	keyLen     int
}

// NewPasswordManager creates a new password manager with default parameters
func NewPasswordManager() *PasswordManager {
	return &PasswordManager{
		saltLength: 32,
		n:          32768, // 2^15
		r:          8,
		p:          1,
		keyLen:     64,
	}
}

// HashPassword hashes a password with a random salt
func (pm *PasswordManager) HashPassword(password string) (string, error) {
	// Generate random salt
	salt := make([]byte, pm.saltLength)
	if _, err := rand.Read(salt); err != nil {
		return "", fmt.Errorf("failed to generate salt: %w", err)
	}

	// Hash password using scrypt
	hash, err := scrypt.Key([]byte(password), salt, pm.n, pm.r, pm.p, pm.keyLen)
	if err != nil {
		return "", fmt.Errorf("failed to hash password: %w", err)
	}

	// Combine salt and hash
	combined := append(salt, hash...)

	// Encode to base64 for storage
	encoded := base64.StdEncoding.EncodeToString(combined)
	return encoded, nil
}

// VerifyPassword checks if a password matches the hash
func (pm *PasswordManager) VerifyPassword(password string, hash string) (bool, error) {
	// Decode hash from base64
	combined, err := base64.StdEncoding.DecodeString(hash)
	if err != nil {
		return false, fmt.Errorf("failed to decode hash: %w", err)
	}

	// Extract salt and stored hash
	if len(combined) < pm.saltLength {
		return false, fmt.Errorf("invalid hash format")
	}

	salt := combined[:pm.saltLength]
	storedHash := combined[pm.saltLength:]

	// Hash the provided password with the same salt
	computedHash, err := scrypt.Key([]byte(password), salt, pm.n, pm.r, pm.p, pm.keyLen)
	if err != nil {
		return false, fmt.Errorf("failed to hash password: %w", err)
	}

	// Compare hashes (constant-time comparison)
	match := constantTimeEqual(computedHash, storedHash)
	return match, nil
}

// constantTimeEqual performs constant-time comparison
func constantTimeEqual(a, b []byte) bool {
	if len(a) != len(b) {
		return false
	}

	result := 0
	for i := 0; i < len(a); i++ {
		result |= int(a[i]) ^ int(b[i])
	}

	return result == 0
}
