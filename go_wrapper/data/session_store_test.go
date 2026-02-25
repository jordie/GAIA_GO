package data

import (
	"fmt"
	"os"
	"testing"
	"time"
)

func TestNewSessionStore(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewSessionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	if store.db == nil {
		t.Error("Database connection not initialized")
	}
}

func TestSessionStore_CreateAndGet(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewSessionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create session
	sessionID := "session-001"
	agentName := "test-agent"
	environment := "dev"

	if err := store.CreateSession(agentName, sessionID, environment); err != nil {
		t.Fatalf("Failed to create session: %v", err)
	}

	// Get session
	session, err := store.GetSession(sessionID)
	if err != nil {
		t.Fatalf("Failed to get session: %v", err)
	}

	if session.SessionID != sessionID {
		t.Errorf("Session ID mismatch: got %s, want %s", session.SessionID, sessionID)
	}
	if session.AgentName != agentName {
		t.Errorf("Agent name mismatch: got %s, want %s", session.AgentName, agentName)
	}
	if session.Environment != environment {
		t.Errorf("Environment mismatch: got %s, want %s", session.Environment, environment)
	}
	if session.EndedAt != nil {
		t.Error("EndedAt should be nil for active session")
	}
}

func TestSessionStore_CompleteSession(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewSessionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create session
	sessionID := "session-001"
	if err := store.CreateSession("test-agent", sessionID, "dev"); err != nil {
		t.Fatalf("Failed to create session: %v", err)
	}

	// Complete session
	exitCode := 0
	stats := SessionStats{
		TotalLines:       100,
		TotalExtractions: 50,
		TotalFeedback:    10,
	}

	if err := store.CompleteSession(sessionID, exitCode, stats); err != nil {
		t.Fatalf("Failed to complete session: %v", err)
	}

	// Verify completion
	session, err := store.GetSession(sessionID)
	if err != nil {
		t.Fatalf("Failed to get session: %v", err)
	}

	if session.EndedAt == nil {
		t.Error("EndedAt should be set after completion")
	}
	if session.ExitCode == nil || *session.ExitCode != exitCode {
		t.Errorf("Exit code mismatch")
	}
	if session.TotalLinesProcessed != stats.TotalLines {
		t.Errorf("Total lines mismatch: got %d, want %d", session.TotalLinesProcessed, stats.TotalLines)
	}
	if session.TotalExtractionEvents != stats.TotalExtractions {
		t.Errorf("Total extractions mismatch: got %d, want %d", session.TotalExtractionEvents, stats.TotalExtractions)
	}
}

func TestSessionStore_UpdateSession(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewSessionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create session
	sessionID := "session-001"
	if err := store.CreateSession("test-agent", sessionID, "dev"); err != nil {
		t.Fatalf("Failed to create session: %v", err)
	}

	// Update session
	totalLines := 42
	totalExtractions := 20
	updates := SessionUpdate{
		TotalLinesProcessed:   &totalLines,
		TotalExtractionEvents: &totalExtractions,
	}

	if err := store.UpdateSession(sessionID, updates); err != nil {
		t.Fatalf("Failed to update session: %v", err)
	}

	// Verify update
	session, err := store.GetSession(sessionID)
	if err != nil {
		t.Fatalf("Failed to get session: %v", err)
	}

	if session.TotalLinesProcessed != totalLines {
		t.Errorf("Total lines mismatch: got %d, want %d", session.TotalLinesProcessed, totalLines)
	}
	if session.TotalExtractionEvents != totalExtractions {
		t.Errorf("Total extractions mismatch: got %d, want %d", session.TotalExtractionEvents, totalExtractions)
	}
}

func TestSessionStore_GetSessionsByAgent(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewSessionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create multiple sessions for different agents
	agentSessions := map[string][]string{
		"agent-1": {"session-1a", "session-1b", "session-1c"},
		"agent-2": {"session-2a", "session-2b"},
	}

	for agent, sessions := range agentSessions {
		for _, sessionID := range sessions {
			if err := store.CreateSession(agent, sessionID, "dev"); err != nil {
				t.Fatalf("Failed to create session %s: %v", sessionID, err)
			}
			time.Sleep(1 * time.Millisecond) // Ensure different timestamps
		}
	}

	// Get sessions for agent-1
	sessions, err := store.GetSessionsByAgent("agent-1", 10)
	if err != nil {
		t.Fatalf("Failed to get sessions: %v", err)
	}

	if len(sessions) != 3 {
		t.Errorf("Expected 3 sessions for agent-1, got %d", len(sessions))
	}

	// Verify they're in descending order (most recent first)
	if len(sessions) >= 2 {
		if sessions[0].StartedAt.Before(sessions[1].StartedAt) {
			t.Error("Sessions not in descending order by start time")
		}
	}
}

func TestSessionStore_GetSessionHistory(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewSessionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create sessions with different timestamps
	agentName := "test-agent"

	// Old session (shouldn't be included in 7-day history)
	oldSessionID := "session-old"
	if err := store.CreateSession(agentName, oldSessionID, "dev"); err != nil {
		t.Fatalf("Failed to create old session: %v", err)
	}

	// Manually update timestamp to be old
	_, err = store.db.Exec(
		"UPDATE process_sessions SET started_at = ? WHERE session_id = ?",
		time.Now().AddDate(0, 0, -10),
		oldSessionID,
	)
	if err != nil {
		t.Fatalf("Failed to update old session timestamp: %v", err)
	}

	// Recent sessions (should be included)
	for i := 0; i < 3; i++ {
		sessionID := fmt.Sprintf("session-recent-%d", i)
		if err := store.CreateSession(agentName, sessionID, "dev"); err != nil {
			t.Fatalf("Failed to create recent session: %v", err)
		}
		time.Sleep(1 * time.Millisecond)
	}

	// Get 7-day history
	sessions, err := store.GetSessionHistory(agentName, 7)
	if err != nil {
		t.Fatalf("Failed to get session history: %v", err)
	}

	if len(sessions) != 3 {
		t.Errorf("Expected 3 recent sessions, got %d", len(sessions))
	}

	// Verify old session not included
	for _, session := range sessions {
		if session.SessionID == oldSessionID {
			t.Error("Old session should not be in 7-day history")
		}
	}
}

func TestSessionStore_GetActiveSessions(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewSessionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create 3 sessions
	for i := 0; i < 3; i++ {
		sessionID := fmt.Sprintf("session-%d", i)
		if err := store.CreateSession("test-agent", sessionID, "dev"); err != nil {
			t.Fatalf("Failed to create session: %v", err)
		}
	}

	// Complete 1 session
	if err := store.CompleteSession("session-1", 0, SessionStats{}); err != nil {
		t.Fatalf("Failed to complete session: %v", err)
	}

	// Get active sessions (should be 2)
	active, err := store.GetActiveSessions()
	if err != nil {
		t.Fatalf("Failed to get active sessions: %v", err)
	}

	if len(active) != 2 {
		t.Errorf("Expected 2 active sessions, got %d", len(active))
	}

	// Verify completed session not in active list
	for _, session := range active {
		if session.SessionID == "session-1" {
			t.Error("Completed session should not be in active list")
		}
	}
}

func TestSessionStore_RecordStateChange(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewSessionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create session
	sessionID := "session-001"
	if err := store.CreateSession("test-agent", sessionID, "dev"); err != nil {
		t.Fatalf("Failed to create session: %v", err)
	}

	// Record state changes
	states := []string{"running", "paused", "resumed", "completed"}
	for _, state := range states {
		change := &StateChange{
			SessionID: sessionID,
			Timestamp: time.Now(),
			State:     state,
			Metadata:  map[string]interface{}{"reason": "test"},
		}

		if err := store.RecordStateChange(change); err != nil {
			t.Fatalf("Failed to record state change %s: %v", state, err)
		}

		if change.ID == 0 {
			t.Errorf("State change ID not set for state %s", state)
		}

		time.Sleep(1 * time.Millisecond)
	}

	// Get state changes
	changes, err := store.GetStateChanges(sessionID)
	if err != nil {
		t.Fatalf("Failed to get state changes: %v", err)
	}

	// Should have 5 changes: 1 from CreateSession (started) + 4 from manual records
	if len(changes) != 5 {
		t.Errorf("Expected 5 state changes, got %d", len(changes))
	}

	// Verify order (chronological)
	if len(changes) >= 2 {
		if changes[0].Timestamp.After(changes[1].Timestamp) {
			t.Error("State changes not in chronological order")
		}
	}

	// Verify first state is "started" (from CreateSession)
	if changes[0].State != "started" {
		t.Errorf("First state should be 'started', got %s", changes[0].State)
	}
}

func TestSessionStore_StateTrackingLifecycle(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewSessionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create session (records "started" state)
	sessionID := "session-lifecycle"
	if err := store.CreateSession("test-agent", sessionID, "dev"); err != nil {
		t.Fatalf("Failed to create session: %v", err)
	}

	// Complete session (records "completed" state)
	if err := store.CompleteSession(sessionID, 0, SessionStats{TotalLines: 100}); err != nil {
		t.Fatalf("Failed to complete session: %v", err)
	}

	// Verify state changes
	changes, err := store.GetStateChanges(sessionID)
	if err != nil {
		t.Fatalf("Failed to get state changes: %v", err)
	}

	if len(changes) != 2 {
		t.Fatalf("Expected 2 state changes (started, completed), got %d", len(changes))
	}

	// Verify states
	if changes[0].State != "started" {
		t.Errorf("First state should be 'started', got %s", changes[0].State)
	}
	if changes[1].State != "completed" {
		t.Errorf("Second state should be 'completed', got %s", changes[1].State)
	}

	// Verify exit code in completed state
	if changes[1].ExitCode == nil || *changes[1].ExitCode != 0 {
		t.Error("Exit code should be 0 in completed state")
	}

	// Verify metadata in completed state
	if changes[1].Metadata["total_lines"] != float64(100) { // JSON unmarshal converts to float64
		t.Error("Metadata should contain total_lines")
	}
}

func TestSessionStore_GetSessionNotFound(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewSessionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Try to get non-existent session
	_, err = store.GetSession("nonexistent-session")
	if err == nil {
		t.Error("Expected error for non-existent session, got nil")
	}

	expectedMsg := "session not found"
	if err != nil && err.Error()[:len(expectedMsg)] != expectedMsg {
		t.Errorf("Expected error message to start with '%s', got '%s'", expectedMsg, err.Error())
	}
}

func TestSessionStore_Persistence(t *testing.T) {
	// Create temporary database file
	dbPath := "/tmp/test_session_store.db"
	defer os.Remove(dbPath)

	// Create store and save data
	store1, err := NewSessionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}

	sessionID := "session-persist"
	if err := store1.CreateSession("test-agent", sessionID, "dev"); err != nil {
		t.Fatalf("Failed to create session: %v", err)
	}

	store1.Close()

	// Reopen store and verify data persists
	store2, err := NewSessionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to reopen store: %v", err)
	}
	defer store2.Close()

	session, err := store2.GetSession(sessionID)
	if err != nil {
		t.Fatalf("Failed to get session after reopen: %v", err)
	}

	if session.SessionID != sessionID {
		t.Errorf("Session ID mismatch after reopen: got %s, want %s", session.SessionID, sessionID)
	}
}

func TestSessionStore_EmptyUpdate(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewSessionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create session
	sessionID := "session-001"
	if err := store.CreateSession("test-agent", sessionID, "dev"); err != nil {
		t.Fatalf("Failed to create session: %v", err)
	}

	// Update with no fields set (should be no-op)
	updates := SessionUpdate{}
	if err := store.UpdateSession(sessionID, updates); err != nil {
		t.Errorf("Empty update should not error: %v", err)
	}
}

func BenchmarkSessionStore_CreateSession(b *testing.B) {
	dbPath := ":memory:"
	store, err := NewSessionStore(dbPath)
	if err != nil {
		b.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		sessionID := fmt.Sprintf("bench-session-%d", i)
		if err := store.CreateSession("bench-agent", sessionID, "dev"); err != nil {
			b.Fatalf("Failed to create session: %v", err)
		}
	}
}

func BenchmarkSessionStore_GetSession(b *testing.B) {
	dbPath := ":memory:"
	store, err := NewSessionStore(dbPath)
	if err != nil {
		b.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create test session
	sessionID := "bench-session"
	if err := store.CreateSession("bench-agent", sessionID, "dev"); err != nil {
		b.Fatalf("Failed to create session: %v", err)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		if _, err := store.GetSession(sessionID); err != nil {
			b.Fatalf("Failed to get session: %v", err)
		}
	}
}
