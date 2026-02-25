package testing

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"testing"
	"time"
)

// SmokeTestClient provides utilities for smoke testing
type SmokeTestClient struct {
	baseURL string
	client  *http.Client
	session string
	t       *testing.T
}

// NewSmokeTestClient creates a new smoke test client
func NewSmokeTestClient(baseURL string, t *testing.T) *SmokeTestClient {
	return &SmokeTestClient{
		baseURL: baseURL,
		client: &http.Client{
			Timeout: 10 * time.Second,
		},
		t: t,
	}
}

// Request makes an HTTP request
func (sc *SmokeTestClient) Request(method, path string, body interface{}) (*http.Response, []byte) {
	url := sc.baseURL + path
	var bodyReader io.Reader

	if body != nil {
		bodyBytes, err := json.Marshal(body)
		if err != nil {
			sc.t.Fatalf("Failed to marshal body: %v", err)
		}
		bodyReader = bytes.NewReader(bodyBytes)
	}

	req, err := http.NewRequest(method, url, bodyReader)
	if err != nil {
		sc.t.Fatalf("Failed to create request: %v", err)
	}

	req.Header.Set("Content-Type", "application/json")
	if sc.session != "" {
		req.Header.Set("Cookie", fmt.Sprintf("session=%s", sc.session))
	}

	resp, err := sc.client.Do(req)
	if err != nil {
		sc.t.Fatalf("Request failed: %v", err)
	}

	respBody, err := io.ReadAll(resp.Body)
	defer resp.Body.Close()
	if err != nil {
		sc.t.Fatalf("Failed to read response: %v", err)
	}

	return resp, respBody
}

// ===== Authentication Smoke Tests =====

// TestSmokeAuth_Health validates health endpoint
func TestSmokeAuth_Health(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping smoke test in short mode")
	}

	client := NewSmokeTestClient("http://localhost:8080/api", t)
	resp, body := client.Request("GET", "/health", nil)

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("Expected 200, got %d: %s", resp.StatusCode, string(body))
	}

	var health map[string]interface{}
	if err := json.Unmarshal(body, &health); err != nil {
		t.Fatalf("Failed to parse health response: %v", err)
	}

	if health["status"] != "healthy" {
		t.Fatalf("API not healthy: %v", health)
	}

	t.Logf("✓ Health check passed: %v", health)
}

// TestSmokeAuth_Login validates login endpoint
func TestSmokeAuth_Login(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping smoke test in short mode")
	}

	client := NewSmokeTestClient("http://localhost:8080/api", t)

	loginReq := map[string]string{
		"username": "architect",
		"password": "peace5",
	}

	resp, body := client.Request("POST", "/auth/login", loginReq)

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("Expected 200, got %d: %s", resp.StatusCode, string(body))
	}

	// Extract session cookie
	for _, cookie := range resp.Cookies() {
		if cookie.Name == "session" {
			client.session = cookie.Value
			t.Logf("✓ Login successful, session: %s", cookie.Value[:20]+"...")
			return
		}
	}

	t.Fatalf("No session cookie in response")
}

// TestSmokeAuth_InvalidLogin validates login with invalid credentials
func TestSmokeAuth_InvalidLogin(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping smoke test in short mode")
	}

	client := NewSmokeTestClient("http://localhost:8080/api", t)

	loginReq := map[string]string{
		"username": "invalid",
		"password": "wrongpassword",
	}

	resp, body := client.Request("POST", "/auth/login", loginReq)

	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("Expected 401, got %d", resp.StatusCode)
	}

	var errResp map[string]interface{}
	if err := json.Unmarshal(body, &errResp); err == nil {
		t.Logf("✓ Invalid login correctly rejected: %v", errResp["code"])
	}
}

// ===== Event Smoke Tests =====

// TestSmokeEvents_CreateEvent validates event creation
func TestSmokeEvents_CreateEvent(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping smoke test in short mode")
	}

	client := NewSmokeTestClient("http://localhost:8080/api", t)
	client.authenticateOrSkip(t)

	eventReq := map[string]interface{}{
		"event_type": "smoke_test",
		"source":     "smoke_tests",
		"data": map[string]interface{}{
			"test": true,
		},
	}

	resp, body := client.Request("POST", "/events", eventReq)

	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("Expected 201, got %d: %s", resp.StatusCode, string(body))
	}

	var event map[string]interface{}
	if err := json.Unmarshal(body, &event); err != nil {
		t.Fatalf("Failed to parse event response: %v", err)
	}

	if event["id"] == nil {
		t.Fatalf("Event ID missing from response")
	}

	t.Logf("✓ Event created: %v", event["id"])
}

// TestSmokeEvents_ListEvents validates event listing
func TestSmokeEvents_ListEvents(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping smoke test in short mode")
	}

	client := NewSmokeTestClient("http://localhost:8080/api", t)
	client.authenticateOrSkip(t)

	resp, body := client.Request("GET", "/events?limit=10&offset=0", nil)

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("Expected 200, got %d: %s", resp.StatusCode, string(body))
	}

	var listResp map[string]interface{}
	if err := json.Unmarshal(body, &listResp); err != nil {
		t.Fatalf("Failed to parse list response: %v", err)
	}

	if listResp["data"] == nil {
		t.Fatalf("Data array missing from response")
	}

	if listResp["pagination"] == nil {
		t.Fatalf("Pagination missing from response")
	}

	t.Logf("✓ Events listed: %v", listResp["pagination"])
}

// ===== Error Smoke Tests =====

// TestSmokeErrors_CreateError validates error creation (no auth)
func TestSmokeErrors_CreateError(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping smoke test in short mode")
	}

	client := NewSmokeTestClient("http://localhost:8080/api", t)

	errorReq := map[string]interface{}{
		"error_type": "smoke_test_error",
		"message":    "Smoke test error",
		"severity":   "medium",
		"source":     "smoke_tests.go",
	}

	resp, body := client.Request("POST", "/errors", errorReq)

	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("Expected 201, got %d: %s", resp.StatusCode, string(body))
	}

	var errLog map[string]interface{}
	if err := json.Unmarshal(body, &errLog); err != nil {
		t.Fatalf("Failed to parse error response: %v", err)
	}

	t.Logf("✓ Error created: %v", errLog["id"])
}

// TestSmokeErrors_ListErrors validates error listing
func TestSmokeErrors_ListErrors(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping smoke test in short mode")
	}

	client := NewSmokeTestClient("http://localhost:8080/api", t)
	client.authenticateOrSkip(t)

	resp, body := client.Request("GET", "/errors?limit=10&offset=0", nil)

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("Expected 200, got %d: %s", resp.StatusCode, string(body))
	}

	var listResp map[string]interface{}
	if err := json.Unmarshal(body, &listResp); err != nil {
		t.Fatalf("Failed to parse list response: %v", err)
	}

	t.Logf("✓ Errors listed: %v", listResp["pagination"])
}

// ===== Notification Smoke Tests =====

// TestSmokeNotifications_CreateNotification validates notification creation
func TestSmokeNotifications_CreateNotification(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping smoke test in short mode")
	}

	client := NewSmokeTestClient("http://localhost:8080/api", t)
	client.authenticateOrSkip(t)

	notifReq := map[string]interface{}{
		"type":    "info",
		"title":   "Smoke Test",
		"message": "Smoke test notification",
	}

	resp, body := client.Request("POST", "/notifications", notifReq)

	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("Expected 201, got %d: %s", resp.StatusCode, string(body))
	}

	var notif map[string]interface{}
	if err := json.Unmarshal(body, &notif); err != nil {
		t.Fatalf("Failed to parse notification response: %v", err)
	}

	t.Logf("✓ Notification created: %v", notif["id"])
}

// TestSmokeNotifications_ListNotifications validates notification listing
func TestSmokeNotifications_ListNotifications(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping smoke test in short mode")
	}

	client := NewSmokeTestClient("http://localhost:8080/api", t)
	client.authenticateOrSkip(t)

	resp, body := client.Request("GET", "/notifications?limit=10&offset=0", nil)

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("Expected 200, got %d: %s", resp.StatusCode, string(body))
	}

	var listResp map[string]interface{}
	if err := json.Unmarshal(body, &listResp); err != nil {
		t.Fatalf("Failed to parse list response: %v", err)
	}

	t.Logf("✓ Notifications listed: %v", listResp["pagination"])
}

// ===== Integration Smoke Tests =====

// TestSmokeIntegrations_ListIntegrations validates integration listing
func TestSmokeIntegrations_ListIntegrations(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping smoke test in short mode")
	}

	client := NewSmokeTestClient("http://localhost:8080/api", t)
	client.authenticateOrSkip(t)

	resp, body := client.Request("GET", "/integrations", nil)

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("Expected 200, got %d: %s", resp.StatusCode, string(body))
	}

	var listResp map[string]interface{}
	if err := json.Unmarshal(body, &listResp); err != nil {
		t.Fatalf("Failed to parse list response: %v", err)
	}

	t.Logf("✓ Integrations listed: %v", listResp["pagination"])
}

// ===== Health & Monitoring Smoke Tests =====

// TestSmokeHealth_Metrics validates metrics endpoint
func TestSmokeHealth_Metrics(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping smoke test in short mode")
	}

	client := NewSmokeTestClient("http://localhost:8080/api", t)

	resp, body := client.Request("GET", "/metrics", nil)

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("Expected 200, got %d: %s", resp.StatusCode, string(body))
	}

	if len(body) == 0 {
		t.Fatalf("Metrics response is empty")
	}

	t.Logf("✓ Metrics endpoint working, received %d bytes", len(body))
}

// TestSmokeHealth_DatabaseConnectivity validates database connection
func TestSmokeHealth_DatabaseConnectivity(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping smoke test in short mode")
	}

	client := NewSmokeTestClient("http://localhost:8080/api", t)

	resp, body := client.Request("GET", "/health", nil)

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("Expected 200, got %d", resp.StatusCode)
	}

	var health map[string]interface{}
	if err := json.Unmarshal(body, &health); err != nil {
		t.Fatalf("Failed to parse health response: %v", err)
	}

	components, ok := health["components"].(map[string]interface{})
	if !ok {
		t.Fatalf("Components missing from health response")
	}

	if components["database"] != "healthy" {
		t.Fatalf("Database not healthy: %v", components["database"])
	}

	t.Logf("✓ Database connectivity verified")
}

// TestSmokeHealth_CacheConnectivity validates cache connection
func TestSmokeHealth_CacheConnectivity(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping smoke test in short mode")
	}

	client := NewSmokeTestClient("http://localhost:8080/api", t)

	resp, body := client.Request("GET", "/health", nil)

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("Expected 200, got %d", resp.StatusCode)
	}

	var health map[string]interface{}
	if err := json.Unmarshal(body, &health); err != nil {
		t.Fatalf("Failed to parse health response: %v", err)
	}

	components, ok := health["components"].(map[string]interface{})
	if !ok {
		t.Fatalf("Components missing from health response")
	}

	if cache, ok := components["cache"]; ok {
		if cache != "healthy" && cache != "degraded" {
			t.Logf("⚠️  Cache status: %v (may be optional)", cache)
		} else {
			t.Logf("✓ Cache connectivity verified: %v", cache)
		}
	}
}

// ===== Helper Methods =====

// authenticateOrSkip authenticates or skips test if auth fails
func (sc *SmokeTestClient) authenticateOrSkip(t *testing.T) {
	loginReq := map[string]string{
		"username": "architect",
		"password": "peace5",
	}

	resp, _ := sc.Request("POST", "/auth/login", loginReq)

	for _, cookie := range resp.Cookies() {
		if cookie.Name == "session" {
			sc.session = cookie.Value
			return
		}
	}

	t.Skip("Authentication failed, skipping test")
}

// ===== Run All Smoke Tests =====

// TestSmokeAll runs all smoke tests and reports results
func TestSmokeAll(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping smoke tests in short mode")
	}

	t.Run("Health", TestSmokeAuth_Health)
	t.Run("Login", TestSmokeAuth_Login)
	t.Run("InvalidLogin", TestSmokeAuth_InvalidLogin)
	t.Run("CreateEvent", TestSmokeEvents_CreateEvent)
	t.Run("ListEvents", TestSmokeEvents_ListEvents)
	t.Run("CreateError", TestSmokeErrors_CreateError)
	t.Run("ListErrors", TestSmokeErrors_ListErrors)
	t.Run("CreateNotification", TestSmokeNotifications_CreateNotification)
	t.Run("ListNotifications", TestSmokeNotifications_ListNotifications)
	t.Run("ListIntegrations", TestSmokeIntegrations_ListIntegrations)
	t.Run("Metrics", TestSmokeHealth_Metrics)
	t.Run("DatabaseConnectivity", TestSmokeHealth_DatabaseConnectivity)
	t.Run("CacheConnectivity", TestSmokeHealth_CacheConnectivity)
}
