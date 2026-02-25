package multiplayer

import (
	"testing"
	"time"
)

// TestGameRoomCreation verifies room creation and basic operations
func TestGameRoomCreation(t *testing.T) {
	room := NewGameRoom("test-room-1", "Test Race", "the quick brown fox", 1, nil)

	if room.ID != "test-room-1" {
		t.Errorf("Expected room ID test-room-1, got %s", room.ID)
	}

	if room.GetState() != StateWaiting {
		t.Errorf("Expected state %s, got %s", StateWaiting, room.GetState())
	}

	if room.GetPlayerCount() != 0 {
		t.Errorf("Expected 0 players, got %d", room.GetPlayerCount())
	}
}

// TestPlayerConnection verifies player operations
func TestPlayerConnection(t *testing.T) {
	player := &PlayerConnection{
		UserID:          1,
		Username:        "TestPlayer",
		SendChan:        make(chan []byte, 64),
		CurrentPosition: 0,
		CurrentWPM:      0,
		CurrentAccuracy: 0,
	}

	// Test progress update (within 5 char buffer)
	err := player.UpdateProgress(5, 50, 95.5)
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}

	pos, wpm, acc, _ := player.GetStats()
	if pos != 5 || wpm != 50 || acc != 95.5 {
		t.Errorf("Expected 5,50,95.5 got %d,%d,%f", pos, wpm, acc)
	}

	// Test invalid progress (going backwards)
	err = player.UpdateProgress(3, 50, 95.5)
	if err != ErrInvalidProgress {
		t.Errorf("Expected ErrInvalidProgress for backwards, got %v", err)
	}

	// Test invalid progress (WPM too high)
	err = player.UpdateProgress(8, 300, 95.5)
	if err != ErrInvalidProgress {
		t.Errorf("Expected ErrInvalidProgress for high WPM, got %v", err)
	}

	// Test invalid progress (skipping too far)
	err = player.UpdateProgress(15, 50, 95.5)
	if err != ErrInvalidProgress {
		t.Errorf("Expected ErrInvalidProgress for big skip, got %v", err)
	}
}

// TestRateLimiter verifies rate limiting
func TestRateLimiter(t *testing.T) {
	limiter := NewRateLimiter(10)
	defer limiter.Stop()

	// Should allow first 10 messages
	for i := 0; i < 10; i++ {
		if !limiter.Allow() {
			t.Errorf("Message %d should be allowed", i+1)
		}
	}

	// 11th message should be blocked
	if limiter.Allow() {
		t.Errorf("Message 11 should be blocked")
	}

	// Wait for token refill
	time.Sleep(150 * time.Millisecond)
	if !limiter.Allow() {
		t.Errorf("Message after refill should be allowed")
	}
}

// TestValidRoomName checks room name validation
func TestValidRoomName(t *testing.T) {
	tests := []struct {
		name    string
		input   string
		expected bool
	}{
		{"valid name", "Cool Race", true},
		{"valid with hyphens", "Cool-Race-2024", true},
		{"empty name", "", false},
		{"too long", "this-is-a-very-very-very-very-very-very-very-very-very-long-name", false},
		{"invalid chars", "Cool@Race!", false},
	}

	for _, tc := range tests {
		result := isValidRoomName(tc.input)
		if result != tc.expected {
			t.Errorf("Test %s: expected %v, got %v", tc.name, tc.expected, result)
		}
	}
}
