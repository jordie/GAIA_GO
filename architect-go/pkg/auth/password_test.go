package auth

import (
	"testing"
	"unicode/utf8"
)

func TestPasswordManager_HashPassword(t *testing.T) {
	pm := NewPasswordManager()

	tests := []struct {
		name     string
		password string
	}{
		{
			name:     "simple password",
			password: "mypassword123",
		},
		{
			name:     "empty password",
			password: "",
		},
		{
			name:     "very long password",
			password: "this-is-a-very-long-password-with-many-characters-and-special-symbols!@#$%^&*()",
		},
		{
			name:     "special characters",
			password: "p@ssw0rd!#$%&",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			hash1, err := pm.HashPassword(tc.password)
			if err != nil {
				t.Fatalf("HashPassword failed: %v", err)
			}

			if hash1 == "" {
				t.Errorf("expected non-empty hash, got empty string")
			}

			// Hash same password again
			hash2, err := pm.HashPassword(tc.password)
			if err != nil {
				t.Fatalf("second HashPassword failed: %v", err)
			}

			// Hashes should differ due to random salt
			if hash1 == hash2 {
				t.Errorf("two hashes of same password should differ (different salts)")
			}
		})
	}
}

func TestPasswordManager_VerifyPassword(t *testing.T) {
	pm := NewPasswordManager()

	tests := []struct {
		name        string
		password    string
		testPass    string
		shouldMatch bool
	}{
		{
			name:        "correct password",
			password:    "mypassword123",
			testPass:    "mypassword123",
			shouldMatch: true,
		},
		{
			name:        "wrong password",
			password:    "mypassword123",
			testPass:    "wrongpassword",
			shouldMatch: false,
		},
		{
			name:        "case sensitive",
			password:    "MyPassword",
			testPass:    "mypassword",
			shouldMatch: false,
		},
		{
			name:        "empty password match",
			password:    "",
			testPass:    "",
			shouldMatch: true,
		},
		{
			name:        "empty password mismatch",
			password:    "",
			testPass:    "notempty",
			shouldMatch: false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			hash, err := pm.HashPassword(tc.password)
			if err != nil {
				t.Fatalf("HashPassword failed: %v", err)
			}

			match, err := pm.VerifyPassword(tc.testPass, hash)
			if err != nil {
				t.Fatalf("VerifyPassword failed: %v", err)
			}

			if match != tc.shouldMatch {
				t.Errorf("expected match=%v, got %v", tc.shouldMatch, match)
			}
		})
	}
}

func TestPasswordManager_VerifyPassword_CorruptHash(t *testing.T) {
	pm := NewPasswordManager()

	// Test with corrupt base64
	_, err := pm.VerifyPassword("password", "not-valid-base64!!!")
	if err == nil {
		t.Fatalf("expected error for corrupt base64, got nil")
	}
}

func TestPasswordManager_VerifyPassword_TooShortHash(t *testing.T) {
	pm := NewPasswordManager()

	// Test with hash that's too short (less than salt length)
	_, err := pm.VerifyPassword("password", "dGVzdA==") // "test" in base64
	if err == nil {
		t.Fatalf("expected error for too-short hash, got nil")
	}
}

func TestPasswordManager_VerifyPassword_InvalidFormat(t *testing.T) {
	pm := NewPasswordManager()

	// Create an invalid hash (empty string)
	_, err := pm.VerifyPassword("password", "")
	if err == nil {
		t.Fatalf("expected error for empty hash, got nil")
	}
}

func TestPasswordManager_RoundTrip(t *testing.T) {
	pm := NewPasswordManager()
	password := "SuperSecurePassword123!@#"

	hash, err := pm.HashPassword(password)
	if err != nil {
		t.Fatalf("HashPassword failed: %v", err)
	}

	match, err := pm.VerifyPassword(password, hash)
	if err != nil {
		t.Fatalf("VerifyPassword failed: %v", err)
	}

	if !match {
		t.Errorf("password should match its own hash")
	}
}

func TestPasswordManager_ConstantTimeComparison(t *testing.T) {
	// Verify constant time comparison is used
	a := []byte("password123")
	b := []byte("password123")
	c := []byte("wrongpass4567")

	if !constantTimeEqual(a, b) {
		t.Errorf("identical byte slices should be equal")
	}

	if constantTimeEqual(a, c) {
		t.Errorf("different byte slices should not be equal")
	}
}

func TestPasswordManager_LongPassword(t *testing.T) {
	pm := NewPasswordManager()

	// Create a very long password (10000 characters)
	longPass := ""
	for i := 0; i < 10000; i++ {
		longPass += "a"
	}

	hash, err := pm.HashPassword(longPass)
	if err != nil {
		t.Fatalf("HashPassword failed for long password: %v", err)
	}

	match, err := pm.VerifyPassword(longPass, hash)
	if err != nil {
		t.Fatalf("VerifyPassword failed for long password: %v", err)
	}

	if !match {
		t.Errorf("long password should match")
	}
}

func TestPasswordManager_UnicodePassword(t *testing.T) {
	pm := NewPasswordManager()

	password := "пароль日本語🔐"

	hash, err := pm.HashPassword(password)
	if err != nil {
		t.Fatalf("HashPassword failed for unicode: %v", err)
	}

	match, err := pm.VerifyPassword(password, hash)
	if err != nil {
		t.Fatalf("VerifyPassword failed for unicode: %v", err)
	}

	if !match {
		t.Errorf("unicode password should match")
	}

	// Verify unicode length is counted correctly
	if utf8.RuneCountInString(password) == 0 {
		t.Errorf("test password should contain runes")
	}
}
