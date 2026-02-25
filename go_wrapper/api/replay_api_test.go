package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/architect/go_wrapper/data"
	"github.com/architect/go_wrapper/stream"
)

func setupReplayAPITest(t *testing.T) (*ReplayAPI, *data.ExtractionStore, *data.SessionStore) {
	// Create in-memory stores
	extractionStore, err := data.NewExtractionStore(":memory:")
	if err != nil {
		t.Fatalf("Failed to create extraction store: %v", err)
	}

	sessionStore, err := data.NewSessionStore(":memory:")
	if err != nil {
		t.Fatalf("Failed to create session store: %v", err)
	}

	// Create test data
	setupReplayTestData(t, extractionStore, sessionStore)

	// Create replay API
	broadcaster := stream.NewBroadcaster()
	replayAPI := NewReplayAPI(extractionStore, sessionStore, broadcaster)

	return replayAPI, extractionStore, sessionStore
}

func setupReplayTestData(t *testing.T, extractionStore *data.ExtractionStore, sessionStore *data.SessionStore) {
	// Create test session
	sessionID := "test-agent-20260210-120000"
	if err := sessionStore.CreateSession("test-agent", sessionID, "dev"); err != nil {
		t.Fatalf("Failed to create session: %v", err)
	}

	// Create test extractions with time spacing
	baseTime := time.Now().Add(-10 * time.Minute)
	events := []*data.ExtractionEvent{
		{
			AgentName:    "test-agent",
			SessionID:    sessionID,
			Timestamp:    baseTime,
			EventType:    "error",
			Pattern:      "error_pattern",
			MatchedValue: "Test error 1",
			LineNumber:   10,
			RiskLevel:    "high",
		},
		{
			AgentName:    "test-agent",
			SessionID:    sessionID,
			Timestamp:    baseTime.Add(2 * time.Second),
			EventType:    "warning",
			Pattern:      "warning_pattern",
			MatchedValue: "Test warning",
			LineNumber:   20,
			RiskLevel:    "medium",
		},
		{
			AgentName:    "test-agent",
			SessionID:    sessionID,
			Timestamp:    baseTime.Add(4 * time.Second),
			EventType:    "error",
			Pattern:      "error_pattern",
			MatchedValue: "Test error 2",
			LineNumber:   30,
			RiskLevel:    "high",
		},
	}

	if err := extractionStore.SaveExtractionBatch(events); err != nil {
		t.Fatalf("Failed to save extractions: %v", err)
	}

	// Add state changes
	if err := sessionStore.RecordStateChange(&data.StateChange{
		SessionID: sessionID,
		State:     "running",
		Timestamp: baseTime,
	}); err != nil {
		t.Fatalf("Failed to record state change: %v", err)
	}

	// Complete the session
	stats := data.SessionStats{
		TotalLines:       100,
		TotalExtractions: 3,
	}
	if err := sessionStore.CompleteSession(sessionID, 0, stats); err != nil {
		t.Fatalf("Failed to complete session: %v", err)
	}
}

func TestReplayAPI_HandleReplaySession_JSON(t *testing.T) {
	replayAPI, _, _ := setupReplayAPITest(t)

	tests := []struct {
		name           string
		sessionID      string
		format         string
		expectedStatus int
		checkFields    bool
	}{
		{
			name:           "Valid session with JSON format",
			sessionID:      "test-agent-20260210-120000",
			format:         "json",
			expectedStatus: http.StatusOK,
			checkFields:    true,
		},
		{
			name:           "Invalid session ID",
			sessionID:      "nonexistent-session",
			format:         "json",
			expectedStatus: http.StatusNotFound,
			checkFields:    false,
		},
		{
			name:           "Empty session ID",
			sessionID:      "",
			format:         "json",
			expectedStatus: http.StatusBadRequest,
			checkFields:    false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			url := fmt.Sprintf("/api/replay/session/%s?format=%s", tt.sessionID, tt.format)
			req := httptest.NewRequest(http.MethodGet, url, nil)
			w := httptest.NewRecorder()

			replayAPI.HandleReplaySession(w, req)

			if w.Code != tt.expectedStatus {
				t.Errorf("Expected status %d, got %d", tt.expectedStatus, w.Code)
			}

			if tt.checkFields && tt.expectedStatus == http.StatusOK {
				var response map[string]interface{}
				if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
					t.Fatalf("Failed to decode response: %v", err)
				}

				// Verify response structure
				if _, ok := response["session"]; !ok {
					t.Error("Response missing 'session' field")
				}
				if _, ok := response["extractions"]; !ok {
					t.Error("Response missing 'extractions' field")
				}
				if _, ok := response["state_changes"]; !ok {
					t.Error("Response missing 'state_changes' field")
				}
				if _, ok := response["total_events"]; !ok {
					t.Error("Response missing 'total_events' field")
				}

				// Verify event count
				totalEvents := int(response["total_events"].(float64))
				if totalEvents != 3 {
					t.Errorf("Expected 3 events, got %d", totalEvents)
				}
			}
		})
	}
}

func TestReplayAPI_HandleReplaySession_SSE(t *testing.T) {
	replayAPI, _, _ := setupReplayAPITest(t)

	// Test SSE streaming (default format)
	url := "/api/replay/session/test-agent-20260210-120000?speed=10.0"
	req := httptest.NewRequest(http.MethodGet, url, nil)
	w := httptest.NewRecorder()

	replayAPI.HandleReplaySession(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Expected status %d, got %d", http.StatusOK, w.Code)
	}

	// Verify SSE headers
	contentType := w.Header().Get("Content-Type")
	if contentType != "text/event-stream" {
		t.Errorf("Expected Content-Type 'text/event-stream', got '%s'", contentType)
	}

	cacheControl := w.Header().Get("Cache-Control")
	if cacheControl != "no-cache" {
		t.Errorf("Expected Cache-Control 'no-cache', got '%s'", cacheControl)
	}

	// Verify SSE output contains expected events
	body := w.Body.String()
	if !strings.Contains(body, "event: session_start") {
		t.Error("SSE output missing 'session_start' event")
	}
	if !strings.Contains(body, "event: extraction") {
		t.Error("SSE output missing 'extraction' event")
	}
	if !strings.Contains(body, "event: replay_complete") {
		t.Error("SSE output missing 'replay_complete' event")
	}
}

func TestReplayAPI_HandleReplayExport_JSON(t *testing.T) {
	replayAPI, _, _ := setupReplayAPITest(t)

	url := "/api/replay/export/test-agent-20260210-120000?format=json"
	req := httptest.NewRequest(http.MethodGet, url, nil)
	w := httptest.NewRecorder()

	replayAPI.HandleReplayExport(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Expected status %d, got %d", http.StatusOK, w.Code)
	}

	// Verify JSON response
	var response map[string]interface{}
	if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
		t.Fatalf("Failed to decode JSON: %v", err)
	}

	if _, ok := response["session"]; !ok {
		t.Error("Export missing 'session' field")
	}
	if _, ok := response["extractions"]; !ok {
		t.Error("Export missing 'extractions' field")
	}

	// Verify content-disposition header
	disposition := w.Header().Get("Content-Disposition")
	if !strings.Contains(disposition, "attachment") {
		t.Error("Missing attachment Content-Disposition header")
	}
}

func TestReplayAPI_HandleReplayExport_CSV(t *testing.T) {
	replayAPI, _, _ := setupReplayAPITest(t)

	url := "/api/replay/export/test-agent-20260210-120000?format=csv"
	req := httptest.NewRequest(http.MethodGet, url, nil)
	w := httptest.NewRecorder()

	replayAPI.HandleReplayExport(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Expected status %d, got %d", http.StatusOK, w.Code)
	}

	// Verify CSV headers
	contentType := w.Header().Get("Content-Type")
	if contentType != "text/csv" {
		t.Errorf("Expected Content-Type 'text/csv', got '%s'", contentType)
	}

	// Verify CSV content
	body := w.Body.String()
	if !strings.Contains(body, "Timestamp,Type,Pattern,Value,Line,Risk") {
		t.Error("CSV missing header row")
	}
	if !strings.Contains(body, "error") {
		t.Error("CSV missing error events")
	}
}

func TestReplayAPI_HandleReplayExport_HAR(t *testing.T) {
	replayAPI, _, _ := setupReplayAPITest(t)

	url := "/api/replay/export/test-agent-20260210-120000?format=har"
	req := httptest.NewRequest(http.MethodGet, url, nil)
	w := httptest.NewRecorder()

	replayAPI.HandleReplayExport(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Expected status %d, got %d", http.StatusOK, w.Code)
	}

	// Verify HAR structure
	var har map[string]interface{}
	if err := json.NewDecoder(w.Body).Decode(&har); err != nil {
		t.Fatalf("Failed to decode HAR: %v", err)
	}

	if _, ok := har["log"]; !ok {
		t.Error("HAR missing 'log' field")
	}

	log := har["log"].(map[string]interface{})
	if _, ok := log["version"]; !ok {
		t.Error("HAR log missing 'version' field")
	}
	if _, ok := log["creator"]; !ok {
		t.Error("HAR log missing 'creator' field")
	}
	if _, ok := log["entries"]; !ok {
		t.Error("HAR log missing 'entries' field")
	}
}

func TestReplayAPI_HandleReplayExport_InvalidFormat(t *testing.T) {
	replayAPI, _, _ := setupReplayAPITest(t)

	url := "/api/replay/export/test-agent-20260210-120000?format=xml"
	req := httptest.NewRequest(http.MethodGet, url, nil)
	w := httptest.NewRecorder()

	replayAPI.HandleReplayExport(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("Expected status %d, got %d", http.StatusBadRequest, w.Code)
	}
}

func TestReplayAPI_HandleReplayControl(t *testing.T) {
	replayAPI, _, _ := setupReplayAPITest(t)

	tests := []struct {
		name           string
		sessionID      string
		action         string
		expectedStatus int
	}{
		{
			name:           "Valid pause action",
			sessionID:      "test-agent-20260210-120000",
			action:         "pause",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "Valid resume action",
			sessionID:      "test-agent-20260210-120000",
			action:         "resume",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "Valid stop action",
			sessionID:      "test-agent-20260210-120000",
			action:         "stop",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "Valid skip action",
			sessionID:      "test-agent-20260210-120000",
			action:         "skip",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "Invalid action",
			sessionID:      "test-agent-20260210-120000",
			action:         "rewind",
			expectedStatus: http.StatusBadRequest,
		},
		{
			name:           "Missing action",
			sessionID:      "test-agent-20260210-120000",
			action:         "",
			expectedStatus: http.StatusBadRequest,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			url := fmt.Sprintf("/api/replay/control/%s/%s", tt.sessionID, tt.action)
			req := httptest.NewRequest(http.MethodPost, url, nil)
			w := httptest.NewRecorder()

			replayAPI.HandleReplayControl(w, req)

			if w.Code != tt.expectedStatus {
				t.Errorf("Expected status %d, got %d", tt.expectedStatus, w.Code)
			}

			if tt.expectedStatus == http.StatusOK {
				var response map[string]interface{}
				if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
					t.Fatalf("Failed to decode response: %v", err)
				}

				if response["action"] != tt.action {
					t.Errorf("Expected action '%s', got '%s'", tt.action, response["action"])
				}
			}
		})
	}
}

func TestReplayAPI_MethodNotAllowed(t *testing.T) {
	replayAPI, _, _ := setupReplayAPITest(t)

	tests := []struct {
		name     string
		endpoint string
		method   string
		handler  func(http.ResponseWriter, *http.Request)
	}{
		{
			name:     "ReplaySession POST not allowed",
			endpoint: "/api/replay/session/test-session",
			method:   http.MethodPost,
			handler:  replayAPI.HandleReplaySession,
		},
		{
			name:     "ReplayExport POST not allowed",
			endpoint: "/api/replay/export/test-session",
			method:   http.MethodPost,
			handler:  replayAPI.HandleReplayExport,
		},
		{
			name:     "ReplayControl GET not allowed",
			endpoint: "/api/replay/control/test-session/pause",
			method:   http.MethodGet,
			handler:  replayAPI.HandleReplayControl,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(tt.method, tt.endpoint, nil)
			w := httptest.NewRecorder()

			tt.handler(w, req)

			if w.Code != http.StatusMethodNotAllowed {
				t.Errorf("Expected status %d, got %d", http.StatusMethodNotAllowed, w.Code)
			}
		})
	}
}

func TestReplayAPI_RegisterRoutes(t *testing.T) {
	replayAPI, _, _ := setupReplayAPITest(t)

	mux := http.NewServeMux()
	replayAPI.RegisterReplayRoutes(mux)

	// Test that routes are registered by attempting valid requests
	// Note: We expect errors for invalid session IDs, but not 404s
	endpoints := []struct {
		url            string
		method         string
		expectedStatus int
	}{
		{"/api/replay/session/test", http.MethodGet, http.StatusNotFound}, // Session not found, but route exists
		{"/api/replay/export/test", http.MethodGet, http.StatusNotFound},  // Session not found, but route exists
		{"/api/replay/control/test/pause", http.MethodPost, http.StatusOK}, // Control endpoint acknowledges
	}

	for _, endpoint := range endpoints {
		req := httptest.NewRequest(endpoint.method, endpoint.url, nil)
		w := httptest.NewRecorder()

		mux.ServeHTTP(w, req)

		// Routes are registered if we don't get 404 (unless it's the expected not found for missing session)
		if w.Code == http.StatusNotFound && endpoint.expectedStatus != http.StatusNotFound {
			t.Errorf("Route %s not registered (got 404)", endpoint.url)
		}
	}
}

func TestReplayAPI_SpeedParameter(t *testing.T) {
	replayAPI, _, _ := setupReplayAPITest(t)

	tests := []struct {
		name          string
		speed         string
		expectedSpeed float64
	}{
		{
			name:          "Default speed (no parameter)",
			speed:         "",
			expectedSpeed: 1.0,
		},
		{
			name:          "Speed 2x",
			speed:         "2.0",
			expectedSpeed: 2.0,
		},
		{
			name:          "Speed 0.5x",
			speed:         "0.5",
			expectedSpeed: 0.5,
		},
		{
			name:          "Speed 10x (max)",
			speed:         "10.0",
			expectedSpeed: 10.0,
		},
		{
			name:          "Invalid speed (too high)",
			speed:         "100.0",
			expectedSpeed: 1.0, // Should default to 1.0
		},
		{
			name:          "Invalid speed (negative)",
			speed:         "-1.0",
			expectedSpeed: 1.0, // Should default to 1.0
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			url := "/api/replay/session/test-agent-20260210-120000?format=json"
			if tt.speed != "" {
				url += "&speed=" + tt.speed
			}

			req := httptest.NewRequest(http.MethodGet, url, nil)
			w := httptest.NewRecorder()

			replayAPI.HandleReplaySession(w, req)

			if w.Code == http.StatusOK {
				var response map[string]interface{}
				if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
					t.Fatalf("Failed to decode response: %v", err)
				}

				speed := response["playback_speed"].(float64)
				if speed != tt.expectedSpeed {
					t.Errorf("Expected speed %.1f, got %.1f", tt.expectedSpeed, speed)
				}
			}
		})
	}
}
