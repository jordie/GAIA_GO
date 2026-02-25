package stream

import (
	"testing"
)

// TestCommandHandlerCreation tests creating a new command handler
func TestCommandHandlerCreation(t *testing.T) {
	wrapper := NewProcessWrapper("test-agent", "logs", "echo", "hello")
	handler := NewCommandHandler(wrapper)

	if handler == nil {
		t.Fatal("Expected handler to be created")
	}

	if handler.wrapper != wrapper {
		t.Error("Handler wrapper mismatch")
	}

	if handler.paused {
		t.Error("Handler should not be paused initially")
	}

	if len(handler.commandLog) != 0 {
		t.Error("Command log should be empty initially")
	}
}

// TestGetStateCommand tests the get_state command
func TestGetStateCommand(t *testing.T) {
	wrapper := NewProcessWrapper("test-agent", "logs", "echo", "hello")
	handler := NewCommandHandler(wrapper)

	cmd := Command{
		Type:      "get_state",
		RequestID: "req-1",
		Data:      make(map[string]interface{}),
	}

	response := handler.HandleCommand(cmd)

	if !response.Success {
		t.Errorf("Expected success, got: %s", response.Message)
	}

	if response.RequestID != "req-1" {
		t.Errorf("Expected request ID 'req-1', got: %s", response.RequestID)
	}

	if response.Data == nil {
		t.Fatal("Expected data in response")
	}

	state, ok := response.Data["state"]
	if !ok {
		t.Error("Expected 'state' field in response data")
	}

	if state != "not_started" {
		t.Errorf("Expected state 'not_started', got: %v", state)
	}
}

// TestUnknownCommand tests handling of unknown commands
func TestUnknownCommand(t *testing.T) {
	wrapper := NewProcessWrapper("test-agent", "logs", "echo", "hello")
	handler := NewCommandHandler(wrapper)

	cmd := Command{
		Type:      "unknown_command",
		RequestID: "req-2",
		Data:      make(map[string]interface{}),
	}

	response := handler.HandleCommand(cmd)

	if response.Success {
		t.Error("Expected failure for unknown command")
	}

	if response.Message == "" {
		t.Error("Expected error message for unknown command")
	}
}

// TestSendInputCommand tests the send_input command
func TestSendInputCommand(t *testing.T) {
	wrapper := NewProcessWrapper("test-agent", "logs", "cat")
	handler := NewCommandHandler(wrapper)

	cmd := Command{
		Type:      "send_input",
		RequestID: "req-3",
		Data: map[string]interface{}{
			"input": "test input",
		},
	}

	// Without stdin pipe, should fail
	response := handler.HandleCommand(cmd)

	if response.Success {
		t.Error("Expected failure when stdin pipe not available")
	}

	if response.Message != "Stdin pipe not available" {
		t.Errorf("Expected 'Stdin pipe not available', got: %s", response.Message)
	}
}

// TestCommandHistory tests command logging
func TestCommandHistory(t *testing.T) {
	wrapper := NewProcessWrapper("test-agent", "logs", "echo", "hello")
	handler := NewCommandHandler(wrapper)

	commands := []Command{
		{Type: "get_state", RequestID: "req-1", Data: make(map[string]interface{})},
		{Type: "pause", RequestID: "req-2", Data: make(map[string]interface{})},
		{Type: "resume", RequestID: "req-3", Data: make(map[string]interface{})},
	}

	for _, cmd := range commands {
		handler.HandleCommand(cmd)
	}

	history := handler.GetCommandHistory()

	if len(history) != 3 {
		t.Errorf("Expected 3 commands in history, got: %d", len(history))
	}

	for i, cmd := range history {
		if cmd.RequestID != commands[i].RequestID {
			t.Errorf("Command %d request ID mismatch: expected %s, got %s",
				i, commands[i].RequestID, cmd.RequestID)
		}
	}
}

// TestIsPaused tests the IsPaused method
func TestIsPaused(t *testing.T) {
	wrapper := NewProcessWrapper("test-agent", "logs", "sleep", "10")
	handler := NewCommandHandler(wrapper)

	if handler.IsPaused() {
		t.Error("Handler should not be paused initially")
	}

	// Start process
	if err := wrapper.Start(); err != nil {
		t.Skipf("Cannot start process: %v", err)
		return
	}
	defer wrapper.Stop()

	// Try to pause
	pauseCmd := Command{
		Type:      "pause",
		RequestID: "req-pause",
		Data:      make(map[string]interface{}),
	}

	response := handler.HandleCommand(pauseCmd)

	if response.Success {
		// Pause succeeded, check status
		if !handler.IsPaused() {
			t.Error("Handler should be paused after pause command")
		}

		// Try to resume
		resumeCmd := Command{
			Type:      "resume",
			RequestID: "req-resume",
			Data:      make(map[string]interface{}),
		}

		response = handler.HandleCommand(resumeCmd)
		if response.Success {
			if handler.IsPaused() {
				t.Error("Handler should not be paused after resume command")
			}
		}
	}
}

// TestPauseWithoutProcess tests pause command when process not running
func TestPauseWithoutProcess(t *testing.T) {
	wrapper := NewProcessWrapper("test-agent", "logs", "echo", "hello")
	handler := NewCommandHandler(wrapper)

	cmd := Command{
		Type:      "pause",
		RequestID: "req-pause",
		Data:      make(map[string]interface{}),
	}

	response := handler.HandleCommand(cmd)

	if response.Success {
		t.Error("Expected failure when pausing non-running process")
	}
}

// TestKillCommand tests the kill command
func TestKillCommand(t *testing.T) {
	wrapper := NewProcessWrapper("test-agent", "logs", "sleep", "60")
	handler := NewCommandHandler(wrapper)

	// Start the process
	if err := wrapper.Start(); err != nil {
		t.Skipf("Cannot start process: %v", err)
		return
	}

	// Kill it
	cmd := Command{
		Type:      "kill",
		RequestID: "req-kill",
		Data:      make(map[string]interface{}),
	}

	response := handler.HandleCommand(cmd)

	// Kill command calls wrapper.Stop() which may return an error if process already exiting
	// Either success or "signal: killed" error is acceptable
	if !response.Success && response.Message != "Failed to kill: signal: killed" {
		t.Errorf("Unexpected kill response: %s", response.Message)
	}

	// Wait for process to actually exit
	wrapper.Wait()

	// After wait, state should reflect termination
	// Accept any non-running state
	state := wrapper.GetState()
	if state == "not_started" {
		t.Errorf("Unexpected state after kill: %s", state)
	}
}

// TestMultipleCommandHandlers tests independence of multiple handlers
func TestMultipleCommandHandlers(t *testing.T) {
	wrapper1 := NewProcessWrapper("agent-1", "logs", "echo", "one")
	wrapper2 := NewProcessWrapper("agent-2", "logs", "echo", "two")

	handler1 := NewCommandHandler(wrapper1)
	handler2 := NewCommandHandler(wrapper2)

	cmd1 := Command{Type: "get_state", RequestID: "req-1", Data: make(map[string]interface{})}
	cmd2 := Command{Type: "get_state", RequestID: "req-2", Data: make(map[string]interface{})}

	handler1.HandleCommand(cmd1)
	handler2.HandleCommand(cmd2)

	history1 := handler1.GetCommandHistory()
	history2 := handler2.GetCommandHistory()

	if len(history1) != 1 {
		t.Errorf("Handler1 should have 1 command, got: %d", len(history1))
	}

	if len(history2) != 1 {
		t.Errorf("Handler2 should have 1 command, got: %d", len(history2))
	}

	if history1[0].RequestID == history2[0].RequestID {
		t.Error("Commands should have different request IDs")
	}
}
