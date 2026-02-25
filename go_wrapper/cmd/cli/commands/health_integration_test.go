package commands

import (
	"bytes"
	"encoding/json"
	"os"
	"strings"
	"testing"

	"github.com/architect/go_wrapper/cmd/cli/output"
	mocktest "github.com/architect/go_wrapper/cmd/cli/testing"
)

func TestHealthCommand_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	mock.AddAgent("health-test", "codex", 12001)

	output.NoColor = true
	host, port := extractHostPort(mock.Server.URL)

	args := []string{"--host", host, "--port", port}

	err := HealthCommand(args)
	if err != nil {
		t.Fatalf("HealthCommand failed: %v", err)
	}
}

func TestHealthCommand_JSON_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	mock.AddAgent("worker-1", "codex", 13001)
	mock.AddAgent("worker-2", "comet", 13002)

	// Capture stdout
	old := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	host, port := extractHostPort(mock.Server.URL)
	args := []string{"--host", host, "--port", port, "--format", "json"}

	err := HealthCommand(args)
	if err != nil {
		t.Fatalf("HealthCommand failed: %v", err)
	}

	w.Close()
	os.Stdout = old

	var buf bytes.Buffer
	buf.ReadFrom(r)
	outputStr := buf.String()

	// Verify JSON output
	var result struct {
		Status    string `json:"status"`
		Uptime    string `json:"uptime"`
		StartedAt string `json:"started_at"`
		Agents    int    `json:"agents"`
		Version   string `json:"version"`
	}

	if err := json.Unmarshal([]byte(outputStr), &result); err != nil {
		t.Fatalf("Invalid JSON output: %v", err)
	}

	if result.Status != "healthy" {
		t.Errorf("Expected status 'healthy', got '%s'", result.Status)
	}

	if result.Uptime == "" {
		t.Error("Expected uptime to be non-empty")
	}

	if result.StartedAt == "" {
		t.Error("Expected started_at to be non-empty")
	}

	if result.Agents != 2 {
		t.Errorf("Expected 2 agents, got %d", result.Agents)
	}

	if result.Version != "1.0.0-test" {
		t.Errorf("Expected version '1.0.0-test', got '%s'", result.Version)
	}
}

func TestHealthCommand_ServerDown_Integration(t *testing.T) {
	output.NoColor = true

	// Use non-existent server
	args := []string{"--host", "localhost", "--port", "99999"}

	err := HealthCommand(args)
	if err == nil {
		t.Fatal("Expected error for unreachable server, got nil")
	}

	if !strings.Contains(err.Error(), "connection refused") && !strings.Contains(err.Error(), "failed") {
		t.Errorf("Expected connection error, got: %v", err)
	}
}

func TestHealthCommand_InvalidHost_Integration(t *testing.T) {
	output.NoColor = true

	args := []string{"--host", "invalid-host-that-does-not-exist", "--port", "8151"}

	err := HealthCommand(args)
	if err == nil {
		t.Fatal("Expected error for invalid host, got nil")
	}
}
