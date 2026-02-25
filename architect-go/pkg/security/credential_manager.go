package security

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"errors"
	"fmt"
	"io"
)

// CredentialManager handles secure credential storage and retrieval
type CredentialManager struct {
	encryptionKey []byte
}

// NewCredentialManager creates a new credential manager with the given encryption key
func NewCredentialManager(key []byte) (*CredentialManager, error) {
	if len(key) != 32 {
		return nil, errors.New("encryption key must be 32 bytes (256-bit)")
	}
	return &CredentialManager{
		encryptionKey: key,
	}, nil
}

// EncryptCredential encrypts sensitive credential data
func (cm *CredentialManager) EncryptCredential(plaintext string) (string, error) {
	if plaintext == "" {
		return "", errors.New("plaintext cannot be empty")
	}

	block, err := aes.NewCipher(cm.encryptionKey)
	if err != nil {
		return "", fmt.Errorf("failed to create cipher: %w", err)
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", fmt.Errorf("failed to create GCM: %w", err)
	}

	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return "", fmt.Errorf("failed to generate nonce: %w", err)
	}

	ciphertext := gcm.Seal(nonce, nonce, []byte(plaintext), nil)
	return base64.StdEncoding.EncodeToString(ciphertext), nil
}

// DecryptCredential decrypts encrypted credential data
func (cm *CredentialManager) DecryptCredential(encrypted string) (string, error) {
	if encrypted == "" {
		return "", errors.New("encrypted data cannot be empty")
	}

	ciphertext, err := base64.StdEncoding.DecodeString(encrypted)
	if err != nil {
		return "", fmt.Errorf("failed to decode base64: %w", err)
	}

	block, err := aes.NewCipher(cm.encryptionKey)
	if err != nil {
		return "", fmt.Errorf("failed to create cipher: %w", err)
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", fmt.Errorf("failed to create GCM: %w", err)
	}

	nonceSize := gcm.NonceSize()
	if len(ciphertext) < nonceSize {
		return "", errors.New("ciphertext too short")
	}

	nonce, ciphertext := ciphertext[:nonceSize], ciphertext[nonceSize:]
	plaintext, err := gcm.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		return "", fmt.Errorf("decryption failed: %w", err)
	}

	return string(plaintext), nil
}

// HashCredential creates a one-way hash of a credential for comparison
// Use for password hashing with bcrypt in production
func (cm *CredentialManager) MaskCredential(credential string, showChars int) string {
	if len(credential) <= showChars {
		return "***"
	}
	return credential[:showChars] + "***" + credential[len(credential)-showChars:]
}

// ValidateCredentialFormat checks if credential follows expected format
func (cm *CredentialManager) ValidateCredentialFormat(credentialType string, value string) error {
	if value == "" {
		return errors.New("credential cannot be empty")
	}

	switch credentialType {
	case "api_key":
		if len(value) < 32 {
			return errors.New("API key must be at least 32 characters")
		}
	case "password":
		if len(value) < 12 {
			return errors.New("password must be at least 12 characters")
		}
	case "token":
		if len(value) < 20 {
			return errors.New("token must be at least 20 characters")
		}
	case "ssh_key":
		if len(value) < 100 {
			return errors.New("SSH key seems too short")
		}
	}

	return nil
}

// CredentialRotationPolicy defines policy for credential rotation
type CredentialRotationPolicy struct {
	MaxAge           int // days
	RotationInterval int // days
	GracePeriod      int // days for old credential to still work
}

// DefaultRotationPolicy returns recommended credential rotation policy
func DefaultRotationPolicy() CredentialRotationPolicy {
	return CredentialRotationPolicy{
		MaxAge:           365,
		RotationInterval: 90,
		GracePeriod:      7,
	}
}
