package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/gorilla/websocket"
)

func TestWSMessage_Marshal(t *testing.T) {
	msg := WSMessage{
		Type:      "command",
		Timestamp: time.Now(),
		AgentName: "test-agent",
		Command:   "get_state",
		RequestID: "test-123",
	}

	data, err := json.Marshal(msg)
	if err != nil {
		t.Fatalf("Failed to marshal WSMessage: %v", err)
	}

	var decoded WSMessage
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("Failed to unmarshal WSMessage: %v", err)
	}

	if decoded.Type != msg.Type {
		t.Errorf("Type mismatch: got %s, want %s", decoded.Type, msg.Type)
	}
	if decoded.Command != msg.Command {
		t.Errorf("Command mismatch: got %s, want %s", decoded.Command, msg.Command)
	}
}

func TestWSManager_Creation(t *testing.T) {
	server := &Server{
		agents: make(map[string]*AgentSession),
	}

	wm := NewWSManager(server)
	if wm == nil {
		t.Fatal("NewWSManager returned nil")
	}

	if wm.connections == nil {
		t.Error("connections map not initialized")
	}

	if wm.server != server {
		t.Error("server reference not set correctly")
	}
}

func TestWSManager_GetStats(t *testing.T) {
	server := &Server{
		agents: make(map[string]*AgentSession),
	}

	wm := NewWSManager(server)

	// Initially no connections
	stats := wm.GetStats()
	totalConns := stats["total_connections"].(int)
	if totalConns != 0 {
		t.Errorf("Expected 0 connections, got %d", totalConns)
	}

	agents := stats["agents"].(map[string]int)
	if len(agents) != 0 {
		t.Errorf("Expected empty agents map, got %d entries", len(agents))
	}
}

func TestWSConnection_Close(t *testing.T) {
	// Create a test server that accepts WebSocket connections
	upgrader := websocket.Upgrader{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			t.Fatalf("Failed to upgrade: %v", err)
			return
		}
		defer conn.Close()

		// Keep connection open briefly
		time.Sleep(100 * time.Millisecond)
	}))
	defer server.Close()

	// Connect to test server
	wsURL := "ws" + strings.TrimPrefix(server.URL, "http")
	conn, _, err := websocket.DefaultDialer.Dial(wsURL, nil)
	if err != nil {
		t.Fatalf("Failed to connect: %v", err)
	}

	// Create WSConnection wrapper
	wsConn := &WSConnection{
		agentName: "test-agent",
		conn:      conn,
		send:      make(chan []byte, 256),
		closeChan: make(chan struct{}),
	}

	// Close the connection
	wsConn.Close()

	// Verify closed flag
	if !wsConn.closed {
		t.Error("Connection not marked as closed")
	}

	// Verify close channel
	select {
	case <-wsConn.closeChan:
		// Good - channel is closed
	case <-time.After(100 * time.Millisecond):
		t.Error("Close channel not closed")
	}
}

func TestHandleCommand_GetState(t *testing.T) {
	server := &Server{
		agents: make(map[string]*AgentSession),
	}

	// Create test agent
	server.mu.Lock()
	server.agents["test-agent"] = &AgentSession{
		Name:      "test-agent",
		StartedAt: time.Now(),
		Status:    "running",
		PID:       12345,
	}
	server.mu.Unlock()

	wm := NewWSManager(server)

	// Create test connection
	wsConn := &WSConnection{
		agentName: "test-agent",
		send:      make(chan []byte, 256),
		closeChan: make(chan struct{}),
	}

	// Create get_state command
	msg := WSMessage{
		Type:      "command",
		Command:   "get_state",
		AgentName: "test-agent",
		RequestID: "test-001",
	}

	// Handle command
	wm.handleCommand(wsConn, msg)

	// Check response was sent
	select {
	case response := <-wsConn.send:
		var respMsg WSMessage
		if err := json.Unmarshal(response, &respMsg); err != nil {
			t.Fatalf("Failed to unmarshal response: %v", err)
		}

		if respMsg.Type != "response" {
			t.Errorf("Expected response type, got %s", respMsg.Type)
		}

		if respMsg.Command != "get_state" {
			t.Errorf("Expected get_state command, got %s", respMsg.Command)
		}

		if respMsg.RequestID != "test-001" {
			t.Errorf("Expected request_id test-001, got %s", respMsg.RequestID)
		}

	case <-time.After(1 * time.Second):
		t.Error("No response received within timeout")
	}
}

func TestHandleCommand_InvalidCommand(t *testing.T) {
	server := &Server{
		agents: make(map[string]*AgentSession),
	}

	server.mu.Lock()
	server.agents["test-agent"] = &AgentSession{
		Name:   "test-agent",
		Status: "running",
	}
	server.mu.Unlock()

	wm := NewWSManager(server)

	wsConn := &WSConnection{
		agentName: "test-agent",
		send:      make(chan []byte, 256),
		closeChan: make(chan struct{}),
	}

	// Send invalid command
	msg := WSMessage{
		Type:      "command",
		Command:   "invalid_command_xyz",
		AgentName: "test-agent",
		RequestID: "test-002",
	}

	wm.handleCommand(wsConn, msg)

	// Check error response
	select {
	case response := <-wsConn.send:
		var respMsg WSMessage
		if err := json.Unmarshal(response, &respMsg); err != nil {
			t.Fatalf("Failed to unmarshal response: %v", err)
		}

		if respMsg.Type != "error" {
			t.Errorf("Expected error type, got %s", respMsg.Type)
		}

		if respMsg.Error == "" {
			t.Error("Expected error message, got empty string")
		}

	case <-time.After(1 * time.Second):
		t.Error("No error response received")
	}
}

func TestHandleCommand_AgentNotFound(t *testing.T) {
	server := &Server{
		agents: make(map[string]*AgentSession),
	}

	wm := NewWSManager(server)

	wsConn := &WSConnection{
		agentName: "nonexistent-agent",
		send:      make(chan []byte, 256),
		closeChan: make(chan struct{}),
	}

	msg := WSMessage{
		Type:      "command",
		Command:   "get_state",
		AgentName: "nonexistent-agent",
		RequestID: "test-003",
	}

	wm.handleCommand(wsConn, msg)

	// Check error response
	select {
	case response := <-wsConn.send:
		var respMsg WSMessage
		if err := json.Unmarshal(response, &respMsg); err != nil {
			t.Fatalf("Failed to unmarshal response: %v", err)
		}

		if respMsg.Type != "error" {
			t.Errorf("Expected error type, got %s", respMsg.Type)
		}

		if !strings.Contains(respMsg.Error, "not found") {
			t.Errorf("Expected 'not found' error, got: %s", respMsg.Error)
		}

	case <-time.After(1 * time.Second):
		t.Error("No error response received")
	}
}

func TestConcurrentConnections(t *testing.T) {
	server := &Server{
		agents: make(map[string]*AgentSession),
	}

	wm := NewWSManager(server)

	// Add test agents
	for i := 1; i <= 3; i++ {
		agentName := "agent-" + string(rune('0'+i))
		server.mu.Lock()
		server.agents[agentName] = &AgentSession{
			Name:   agentName,
			Status: "running",
		}
		server.mu.Unlock()

		// Add connections
		for j := 1; j <= 2; j++ {
			conn := &WSConnection{
				agentName: agentName,
				send:      make(chan []byte, 256),
				closeChan: make(chan struct{}),
			}

			wm.mu.Lock()
			if wm.connections[agentName] == nil {
				wm.connections[agentName] = make(map[string]*WSConnection)
			}
			connID := agentName + "-conn-" + string(rune('0'+j))
			wm.connections[agentName][connID] = conn
			wm.mu.Unlock()
		}
	}

	// Verify stats
	stats := wm.GetStats()
	totalConns := stats["total_connections"].(int)
	agents := stats["agents"].(map[string]int)

	if totalConns != 6 {
		t.Errorf("Expected 6 total connections, got %d", totalConns)
	}

	if len(agents) != 3 {
		t.Errorf("Expected 3 agents, got %d", len(agents))
	}

	for agent, count := range agents {
		if count != 2 {
			t.Errorf("Expected 2 connections for %s, got %d", agent, count)
		}
	}
}

func TestWSMessage_AllCommands(t *testing.T) {
	commands := []string{"get_state", "pause", "resume", "kill", "send_input"}

	for _, cmd := range commands {
		msg := WSMessage{
			Type:      "command",
			Command:   cmd,
			AgentName: "test-agent",
			RequestID: "test-" + cmd,
			Data:      make(map[string]interface{}),
		}

		data, err := json.Marshal(msg)
		if err != nil {
			t.Errorf("Failed to marshal command %s: %v", cmd, err)
			continue
		}

		var decoded WSMessage
		if err := json.Unmarshal(data, &decoded); err != nil {
			t.Errorf("Failed to unmarshal command %s: %v", cmd, err)
			continue
		}

		if decoded.Command != cmd {
			t.Errorf("Command mismatch for %s: got %s", cmd, decoded.Command)
		}
	}
}
