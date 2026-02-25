package commands

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"testing"

	"github.com/architect/go_wrapper/cmd/cli/client"
	"github.com/architect/go_wrapper/cmd/cli/output"
	mocktest "github.com/architect/go_wrapper/cmd/cli/testing"
)

func TestAgentsListCommand_Integration(t *testing.T) {
	// Start mock server
	mock := mocktest.NewMockServer()
	defer mock.Close()

	// Add test agents
	mock.AddAgent("test-agent-1", "codex", 1001)
	mock.AddAgent("test-agent-2", "comet", 1002)

	// Extract host and port from mock server
	host, port := extractHostPort(mock.Server.URL)

	// Test table format
	output.NoColor = true
	args := []string{"--host", host, "--port", port}

	err := agentsListCommand(args)
	if err != nil {
		t.Fatalf("agentsListCommand failed: %v", err)
	}
}

func TestAgentsListCommand_JSON_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	mock.AddAgent("worker-1", "codex", 2001)

	// Capture stdout
	old := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	host, port := extractHostPort(mock.Server.URL)
	args := []string{"--host", host, "--port", port, "--format", "json"}

	err := agentsListCommand(args)
	if err != nil {
		t.Fatalf("agentsListCommand failed: %v", err)
	}

	w.Close()
	os.Stdout = old

	var buf bytes.Buffer
	buf.ReadFrom(r)
	outputStr := buf.String()

	// Verify JSON output
	var result struct {
		Agents []struct {
			Name string `json:"name"`
		} `json:"agents"`
		Count int `json:"count"`
	}

	if err := json.Unmarshal([]byte(outputStr), &result); err != nil {
		t.Fatalf("Invalid JSON output: %v", err)
	}

	if result.Count != 1 {
		t.Errorf("Expected 1 agent, got %d", result.Count)
	}

	if result.Agents[0].Name != "worker-1" {
		t.Errorf("Expected agent name 'worker-1', got '%s'", result.Agents[0].Name)
	}
}

func TestAgentsStartCommand_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	output.NoColor = true
	host, port := extractHostPort(mock.Server.URL)

	args := []string{
		"--host", host,
		"--port", port,
		"--name", "new-agent",
		"--command", "codex",
	}

	err := agentsStartCommand(args)
	if err != nil {
		t.Fatalf("agentsStartCommand failed: %v", err)
	}

	// Verify agent was created
	agent := mock.GetAgent("new-agent")
	if agent == nil {
		t.Fatal("Agent was not created on server")
	}

	if agent.Command != "codex" {
		t.Errorf("Expected command 'codex', got '%s'", agent.Command)
	}
}

func TestAgentsStartCommand_MissingName_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	host, port := extractHostPort(mock.Server.URL)

	args := []string{
		"--host", host,
		"--port", port,
		"--command", "codex",
		// Missing --name
	}

	err := agentsStartCommand(args)
	if err == nil {
		t.Fatal("Expected error for missing name, got nil")
	}

	if !strings.Contains(err.Error(), "name is required") {
		t.Errorf("Expected 'name is required' error, got: %v", err)
	}
}

func TestAgentsStopCommand_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	mock.AddAgent("stop-test", "codex", 3001)

	output.NoColor = true
	host, port := extractHostPort(mock.Server.URL)

	args := []string{"--host", host, "--port", port, "stop-test"}

	err := agentsStopCommand(args)
	if err != nil {
		t.Fatalf("agentsStopCommand failed: %v", err)
	}

	// Verify agent was removed
	agent := mock.GetAgent("stop-test")
	if agent != nil {
		t.Error("Agent should have been removed")
	}
}

func TestAgentsStopCommand_NotFound_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	output.NoColor = true
	host, port := extractHostPort(mock.Server.URL)

	args := []string{"--host", host, "--port", port, "nonexistent"}

	err := agentsStopCommand(args)
	if err == nil {
		t.Fatal("Expected error for nonexistent agent, got nil")
	}

	if !strings.Contains(err.Error(), "404") {
		t.Errorf("Expected 404 error, got: %v", err)
	}
}

func TestAgentsStatusCommand_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	mock.AddAgent("status-test", "comet", 4001)

	output.NoColor = true
	host, port := extractHostPort(mock.Server.URL)

	args := []string{"--host", host, "--port", port, "status-test"}

	err := agentsStatusCommand(args)
	if err != nil {
		t.Fatalf("agentsStatusCommand failed: %v", err)
	}
}

func TestAgentsPauseCommand_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	mock.AddAgent("pause-test", "codex", 5001)

	output.NoColor = true
	host, port := extractHostPort(mock.Server.URL)

	args := []string{"--host", host, "--port", port, "pause-test"}

	err := agentsPauseCommand(args)
	if err != nil {
		t.Fatalf("agentsPauseCommand failed: %v", err)
	}

	// Verify agent status changed
	agent := mock.GetAgent("pause-test")
	if agent.Status != "paused" {
		t.Errorf("Expected status 'paused', got '%s'", agent.Status)
	}
}

func TestAgentsResumeCommand_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	mock.AddAgent("resume-test", "codex", 6001)
	agent := mock.GetAgent("resume-test")
	agent.Status = "paused"

	output.NoColor = true
	host, port := extractHostPort(mock.Server.URL)

	args := []string{"--host", host, "--port", port, "resume-test"}

	err := agentsResumeCommand(args)
	if err != nil {
		t.Fatalf("agentsResumeCommand failed: %v", err)
	}

	// Verify agent status changed
	agent = mock.GetAgent("resume-test")
	if agent.Status != "running" {
		t.Errorf("Expected status 'running', got '%s'", agent.Status)
	}
}

func TestAgentsCommand_RemoteServer_Integration(t *testing.T) {
	mock := mocktest.NewMockServer()
	defer mock.Close()

	mock.AddAgent("remote-test", "codex", 7001)

	output.NoColor = true
	host, portStr := extractHostPort(mock.Server.URL)

	// Convert port to int
	var port int
	fmt.Sscanf(portStr, "%d", &port)

	// Test connecting to remote server
	c := client.NewClient(host, port)

	var resp AgentsResponse
	err := c.GetJSON("/api/agents", &resp)
	if err != nil {
		t.Fatalf("Failed to connect to remote server: %v", err)
	}

	if resp.Count != 1 {
		t.Errorf("Expected 1 agent, got %d", resp.Count)
	}
}

// Helper function to extract host and port from URL
func extractHostPort(url string) (string, string) {
	// URL format: http://127.0.0.1:12345
	parts := strings.Split(strings.TrimPrefix(url, "http://"), ":")
	if len(parts) != 2 {
		return "localhost", "8151"
	}
	return parts[0], parts[1]
}
