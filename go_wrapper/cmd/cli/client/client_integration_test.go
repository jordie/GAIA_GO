package client

import (
	"encoding/json"
	"fmt"
	"strings"
	"testing"

	mocktest "github.com/architect/go_wrapper/cmd/cli/testing"
)

func TestClient_Get_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	mock.AddAgent("test-agent", "codex", 14001)

	host, port := extractHostPort(mock.Server.URL)
	c := NewClient(host, port)

	body, err := c.Get("/api/health")
	if err != nil {
		t.Fatalf("Get failed: %v", err)
	}

	var result map[string]interface{}
	if err := json.Unmarshal(body, &result); err != nil {
		t.Fatalf("Failed to unmarshal response: %v", err)
	}

	if result["status"] != "healthy" {
		t.Errorf("Expected status 'healthy', got '%v'", result["status"])
	}
}

func TestClient_GetJSON_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	mock.AddAgent("worker-1", "codex", 15001)

	host, port := extractHostPort(mock.Server.URL)
	c := NewClient(host, port)

	var result struct {
		Agents []struct {
			Name string `json:"name"`
		} `json:"agents"`
		Count int `json:"count"`
	}

	err := c.GetJSON("/api/agents", &result)
	if err != nil {
		t.Fatalf("GetJSON failed: %v", err)
	}

	if result.Count != 1 {
		t.Errorf("Expected 1 agent, got %d", result.Count)
	}

	if result.Agents[0].Name != "worker-1" {
		t.Errorf("Expected agent 'worker-1', got '%s'", result.Agents[0].Name)
	}
}

func TestClient_Post_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	host, port := extractHostPort(mock.Server.URL)
	c := NewClient(host, port)

	data := map[string]string{
		"name":    "post-test",
		"command": "codex",
	}

	body, err := c.Post("/api/agents", data)
	if err != nil {
		t.Fatalf("Post failed: %v", err)
	}

	var result map[string]interface{}
	if err := json.Unmarshal(body, &result); err != nil {
		t.Fatalf("Failed to unmarshal response: %v", err)
	}

	if result["name"] != "post-test" {
		t.Errorf("Expected name 'post-test', got '%v'", result["name"])
	}

	// Verify agent was created
	if mock.GetAgent("post-test") == nil {
		t.Error("Agent was not created on server")
	}
}

func TestClient_PostJSON_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	host, port := extractHostPort(mock.Server.URL)
	c := NewClient(host, port)

	data := map[string]string{
		"name":    "json-test",
		"command": "comet",
	}

	var result struct {
		Name    string `json:"name"`
		Command string `json:"command"`
		PID     int    `json:"pid"`
	}

	err := c.PostJSON("/api/agents", data, &result)
	if err != nil {
		t.Fatalf("PostJSON failed: %v", err)
	}

	if result.Name != "json-test" {
		t.Errorf("Expected name 'json-test', got '%s'", result.Name)
	}

	if result.Command != "comet" {
		t.Errorf("Expected command 'comet', got '%s'", result.Command)
	}

	if result.PID == 0 {
		t.Error("Expected non-zero PID")
	}
}

func TestClient_Delete_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	mock.AddAgent("delete-test", "codex", 16001)

	host, port := extractHostPort(mock.Server.URL)
	c := NewClient(host, port)

	_, err := c.Delete("/api/agents/delete-test")
	if err != nil {
		t.Fatalf("Delete failed: %v", err)
	}

	// Verify agent was deleted
	if mock.GetAgent("delete-test") != nil {
		t.Error("Agent should have been deleted")
	}
}

func TestClient_Get_NotFound_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	host, port := extractHostPort(mock.Server.URL)
	c := NewClient(host, port)

	_, err := c.Get("/api/agents/nonexistent")
	if err == nil {
		t.Fatal("Expected error for nonexistent resource, got nil")
	}

	if !strings.Contains(err.Error(), "404") {
		t.Errorf("Expected 404 error, got: %v", err)
	}
}

func TestClient_Post_BadRequest_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	host, port := extractHostPort(mock.Server.URL)
	c := NewClient(host, port)

	// Missing required fields
	data := map[string]string{
		"name": "test",
		// Missing command
	}

	_, err := c.Post("/api/agents", data)
	if err == nil {
		t.Fatal("Expected error for bad request, got nil")
	}

	if !strings.Contains(err.Error(), "400") {
		t.Errorf("Expected 400 error, got: %v", err)
	}
}

func TestClient_ServerUnavailable_Integration(t *testing.T) {
	// Use non-existent server
	c := NewClient("localhost", 99999)

	_, err := c.Get("/api/health")
	if err == nil {
		t.Fatal("Expected error for unavailable server, got nil")
	}

	if !strings.Contains(err.Error(), "connection refused") && !strings.Contains(err.Error(), "failed") {
		t.Errorf("Expected connection error, got: %v", err)
	}
}

func TestClient_Timeout_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	host, port := extractHostPort(mock.Server.URL)
	c := NewClient(host, port)

	// Client has 30s timeout by default, so this should succeed
	_, err := c.Get("/api/health")
	if err != nil {
		t.Fatalf("Request should not timeout: %v", err)
	}
}

// Helper function to extract host and port from URL
func extractHostPort(url string) (string, int) {
	// URL format: http://127.0.0.1:12345
	parts := strings.Split(strings.TrimPrefix(url, "http://"), ":")
	port := 0
	if len(parts) == 2 {
		// Convert port string to int
		fmt.Sscanf(parts[1], "%d", &port)
	}
	return parts[0], port
}
