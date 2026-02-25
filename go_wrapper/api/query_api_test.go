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
)

func setupQueryAPITest(t *testing.T) (*QueryAPI, *data.ExtractionStore, *data.SessionStore) {
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
	setupTestData(t, extractionStore, sessionStore)

	// Create query API
	queryAPI := NewQueryAPI(extractionStore, sessionStore)

	return queryAPI, extractionStore, sessionStore
}

func setupTestData(t *testing.T, extractionStore *data.ExtractionStore, sessionStore *data.SessionStore) {
	// Create test session
	sessionID := "test-agent-20260210-120000"
	if err := sessionStore.CreateSession("test-agent", sessionID, "dev"); err != nil {
		t.Fatalf("Failed to create session: %v", err)
	}

	// Create test extractions
	events := []*data.ExtractionEvent{
		{
			AgentName:    "test-agent",
			SessionID:    sessionID,
			Timestamp:    time.Now().Add(-10 * time.Minute),
			EventType:    "error",
			Pattern:      "error_pattern",
			MatchedValue: "Test error 1",
			LineNumber:   10,
			RiskLevel:    "high",
		},
		{
			AgentName:    "test-agent",
			SessionID:    sessionID,
			Timestamp:    time.Now().Add(-5 * time.Minute),
			EventType:    "warning",
			Pattern:      "warning_pattern",
			MatchedValue: "Test warning",
			LineNumber:   20,
			RiskLevel:    "medium",
		},
		{
			AgentName:    "test-agent",
			SessionID:    sessionID,
			Timestamp:    time.Now(),
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

	// Complete the session
	stats := data.SessionStats{
		TotalLines:       100,
		TotalExtractions: 3,
	}
	if err := sessionStore.CompleteSession(sessionID, 0, stats); err != nil {
		t.Fatalf("Failed to complete session: %v", err)
	}
}

func TestQueryAPI_HandleQueryExtractions(t *testing.T) {
	queryAPI, _, _ := setupQueryAPITest(t)

	tests := []struct {
		name           string
		url            string
		expectedStatus int
		expectedCount  int
	}{
		{
			name:           "Query by agent",
			url:            "/api/query/extractions?agent=test-agent",
			expectedStatus: http.StatusOK,
			expectedCount:  3,
		},
		{
			name:           "Query by type",
			url:            "/api/query/extractions?agent=test-agent&type=error",
			expectedStatus: http.StatusOK,
			expectedCount:  2,
		},
		{
			name:           "Query by pattern",
			url:            "/api/query/extractions?agent=test-agent&pattern=error_pattern",
			expectedStatus: http.StatusOK,
			expectedCount:  2,
		},
		{
			name:           "Query with limit",
			url:            "/api/query/extractions?agent=test-agent&limit=1",
			expectedStatus: http.StatusOK,
			expectedCount:  1,
		},
		{
			name:           "Missing agent parameter",
			url:            "/api/query/extractions",
			expectedStatus: http.StatusBadRequest,
			expectedCount:  0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, tt.url, nil)
			w := httptest.NewRecorder()

			queryAPI.HandleQueryExtractions(w, req)

			if w.Code != tt.expectedStatus {
				t.Errorf("Expected status %d, got %d", tt.expectedStatus, w.Code)
			}

			if tt.expectedStatus == http.StatusOK {
				var response map[string]interface{}
				if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
					t.Fatalf("Failed to decode response: %v", err)
				}

				total := int(response["total"].(float64))
				if total != tt.expectedCount {
					t.Errorf("Expected %d extractions, got %d", tt.expectedCount, total)
				}
			}
		})
	}
}

func TestQueryAPI_HandleQuerySessions(t *testing.T) {
	queryAPI, _, _ := setupQueryAPITest(t)

	tests := []struct {
		name           string
		url            string
		expectedStatus int
		minCount       int
	}{
		{
			name:           "Query by agent",
			url:            "/api/query/sessions?agent=test-agent",
			expectedStatus: http.StatusOK,
			minCount:       1,
		},
		{
			name:           "Query with limit",
			url:            "/api/query/sessions?agent=test-agent&limit=10",
			expectedStatus: http.StatusOK,
			minCount:       1,
		},
		{
			name:           "Query by days",
			url:            "/api/query/sessions?agent=test-agent&days=7",
			expectedStatus: http.StatusOK,
			minCount:       1,
		},
		{
			name:           "Query active only",
			url:            "/api/query/sessions?active=true",
			expectedStatus: http.StatusOK,
			minCount:       0,
		},
		{
			name:           "Missing agent parameter",
			url:            "/api/query/sessions",
			expectedStatus: http.StatusBadRequest,
			minCount:       0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, tt.url, nil)
			w := httptest.NewRecorder()

			queryAPI.HandleQuerySessions(w, req)

			if w.Code != tt.expectedStatus {
				t.Errorf("Expected status %d, got %d", tt.expectedStatus, w.Code)
			}

			if tt.expectedStatus == http.StatusOK {
				var response map[string]interface{}
				if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
					t.Fatalf("Failed to decode response: %v", err)
				}

				total := int(response["total"].(float64))
				if total < tt.minCount {
					t.Errorf("Expected at least %d sessions, got %d", tt.minCount, total)
				}
			}
		})
	}
}

func TestQueryAPI_HandleQuerySession(t *testing.T) {
	queryAPI, _, _ := setupQueryAPITest(t)

	tests := []struct {
		name           string
		sessionID      string
		expectedStatus int
	}{
		{
			name:           "Valid session",
			sessionID:      "test-agent-20260210-120000",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "Invalid session",
			sessionID:      "nonexistent-session",
			expectedStatus: http.StatusNotFound,
		},
		{
			name:           "Empty session ID",
			sessionID:      "",
			expectedStatus: http.StatusBadRequest,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			url := fmt.Sprintf("/api/query/session/%s", tt.sessionID)
			req := httptest.NewRequest(http.MethodGet, url, nil)
			w := httptest.NewRecorder()

			queryAPI.HandleQuerySession(w, req)

			if w.Code != tt.expectedStatus {
				t.Errorf("Expected status %d, got %d", tt.expectedStatus, w.Code)
			}

			if tt.expectedStatus == http.StatusOK {
				var response map[string]interface{}
				if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
					t.Fatalf("Failed to decode response: %v", err)
				}

				// Verify response structure
				if _, ok := response["session"]; !ok {
					t.Error("Response missing 'session' field")
				}
				if _, ok := response["state_changes"]; !ok {
					t.Error("Response missing 'state_changes' field")
				}
				if _, ok := response["extractions"]; !ok {
					t.Error("Response missing 'extractions' field")
				}
			}
		})
	}
}

func TestQueryAPI_HandleQueryAgentStats(t *testing.T) {
	queryAPI, _, _ := setupQueryAPITest(t)

	tests := []struct {
		name           string
		agentName      string
		expectedStatus int
	}{
		{
			name:           "Valid agent",
			agentName:      "test-agent",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "Nonexistent agent",
			agentName:      "nonexistent-agent",
			expectedStatus: http.StatusOK, // Returns empty stats
		},
		{
			name:           "Empty agent name",
			agentName:      "",
			expectedStatus: http.StatusBadRequest,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			url := fmt.Sprintf("/api/query/stats/agent/%s", tt.agentName)
			req := httptest.NewRequest(http.MethodGet, url, nil)
			w := httptest.NewRecorder()

			queryAPI.HandleQueryAgentStats(w, req)

			if w.Code != tt.expectedStatus {
				t.Errorf("Expected status %d, got %d", tt.expectedStatus, w.Code)
			}

			if tt.expectedStatus == http.StatusOK {
				var response map[string]interface{}
				if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
					t.Fatalf("Failed to decode response: %v", err)
				}

				// Verify response structure
				if _, ok := response["extractions"]; !ok {
					t.Error("Response missing 'extractions' field")
				}
				if _, ok := response["sessions"]; !ok {
					t.Error("Response missing 'sessions' field")
				}

				if tt.agentName == "test-agent" {
					sessions := response["sessions"].(map[string]interface{})
					total := int(sessions["total"].(float64))
					if total != 1 {
						t.Errorf("Expected 1 session, got %d", total)
					}
				}
			}
		})
	}
}

func TestQueryAPI_HandleQueryTimeline(t *testing.T) {
	queryAPI, _, _ := setupQueryAPITest(t)

	tests := []struct {
		name           string
		url            string
		expectedStatus int
	}{
		{
			name:           "Query timeline by agent",
			url:            "/api/query/timeline?agent=test-agent",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "Query timeline with limit",
			url:            "/api/query/timeline?agent=test-agent&limit=10",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "Missing agent parameter",
			url:            "/api/query/timeline",
			expectedStatus: http.StatusBadRequest,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, tt.url, nil)
			w := httptest.NewRecorder()

			queryAPI.HandleQueryTimeline(w, req)

			if w.Code != tt.expectedStatus {
				t.Errorf("Expected status %d, got %d", tt.expectedStatus, w.Code)
			}

			if tt.expectedStatus == http.StatusOK {
				var response map[string]interface{}
				if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
					t.Fatalf("Failed to decode response: %v", err)
				}

				// Verify response structure
				if _, ok := response["timeline"]; !ok {
					t.Error("Response missing 'timeline' field")
				}
				if _, ok := response["extractions"]; !ok {
					t.Error("Response missing 'extractions' field")
				}
			}
		})
	}
}

func TestQueryAPI_HandleQueryCodeBlocks(t *testing.T) {
	queryAPI, extractionStore, _ := setupQueryAPITest(t)

	// Add a code block
	block := &data.CodeBlock{
		AgentName: "test-agent",
		SessionID: "test-session",
		Timestamp: time.Now(),
		Language:  "python",
		Content:   "def test():\n    pass",
		Digest:    "test-digest",
	}
	extractionStore.SaveCodeBlock(block)

	tests := []struct {
		name           string
		url            string
		expectedStatus int
		minCount       int
	}{
		{
			name:           "Query by agent",
			url:            "/api/query/code-blocks?agent=test-agent",
			expectedStatus: http.StatusOK,
			minCount:       1,
		},
		{
			name:           "Query by language",
			url:            "/api/query/code-blocks?agent=test-agent&language=python",
			expectedStatus: http.StatusOK,
			minCount:       1,
		},
		{
			name:           "Missing agent parameter",
			url:            "/api/query/code-blocks",
			expectedStatus: http.StatusBadRequest,
			minCount:       0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, tt.url, nil)
			w := httptest.NewRecorder()

			queryAPI.HandleQueryCodeBlocks(w, req)

			if w.Code != tt.expectedStatus {
				t.Errorf("Expected status %d, got %d", tt.expectedStatus, w.Code)
			}

			if tt.expectedStatus == http.StatusOK {
				var response map[string]interface{}
				if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
					t.Fatalf("Failed to decode response: %v", err)
				}

				total := int(response["total"].(float64))
				if total < tt.minCount {
					t.Errorf("Expected at least %d code blocks, got %d", tt.minCount, total)
				}
			}
		})
	}
}

func TestQueryAPI_MethodNotAllowed(t *testing.T) {
	queryAPI, _, _ := setupQueryAPITest(t)

	endpoints := []string{
		"/api/query/extractions",
		"/api/query/sessions",
		"/api/query/session/test",
		"/api/query/stats/agent/test",
		"/api/query/timeline",
		"/api/query/code-blocks",
	}

	for _, endpoint := range endpoints {
		t.Run(endpoint, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodPost, endpoint, nil)
			w := httptest.NewRecorder()

			// Call appropriate handler
			switch {
			case endpoint == "/api/query/extractions":
				queryAPI.HandleQueryExtractions(w, req)
			case endpoint == "/api/query/sessions":
				queryAPI.HandleQuerySessions(w, req)
			case strings.HasPrefix(endpoint, "/api/query/session/"):
				queryAPI.HandleQuerySession(w, req)
			case strings.HasPrefix(endpoint, "/api/query/stats/agent/"):
				queryAPI.HandleQueryAgentStats(w, req)
			case endpoint == "/api/query/timeline":
				queryAPI.HandleQueryTimeline(w, req)
			case endpoint == "/api/query/code-blocks":
				queryAPI.HandleQueryCodeBlocks(w, req)
			}

			if w.Code != http.StatusMethodNotAllowed {
				t.Errorf("Expected status %d, got %d", http.StatusMethodNotAllowed, w.Code)
			}
		})
	}
}

func TestQueryAPI_RegisterRoutes(t *testing.T) {
	queryAPI, _, _ := setupQueryAPITest(t)

	mux := http.NewServeMux()
	queryAPI.RegisterQueryRoutes(mux)

	// Test that routes are registered
	endpoints := []string{
		"/api/query/extractions",
		"/api/query/sessions",
		"/api/query/code-blocks",
	}

	for _, endpoint := range endpoints {
		req := httptest.NewRequest(http.MethodGet, endpoint+"?agent=test", nil)
		w := httptest.NewRecorder()

		mux.ServeHTTP(w, req)

		// Should not return 404
		if w.Code == http.StatusNotFound {
			t.Errorf("Route %s not registered", endpoint)
		}
	}
}
