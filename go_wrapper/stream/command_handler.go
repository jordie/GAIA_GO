package stream

import (
	"fmt"
	"io"
	"log"
	"sync"
)

// Command represents a command to be executed on a process
type Command struct {
	Type      string                 `json:"type"`       // pause, resume, kill, send_input, get_state
	Data      map[string]interface{} `json:"data"`
	RequestID string                 `json:"request_id,omitempty"`
}

// CommandResponse represents the result of a command execution
type CommandResponse struct {
	RequestID string                 `json:"request_id"`
	Success   bool                   `json:"success"`
	Message   string                 `json:"message,omitempty"`
	Data      map[string]interface{} `json:"data,omitempty"`
}

// CommandHandler processes commands for a ProcessWrapper
type CommandHandler struct {
	wrapper    *ProcessWrapper
	stdinPipe  io.WriteCloser
	paused     bool
	commandLog []Command
	mu         sync.RWMutex
}

// NewCommandHandler creates a new command handler
func NewCommandHandler(wrapper *ProcessWrapper) *CommandHandler {
	return &CommandHandler{
		wrapper:    wrapper,
		paused:     false,
		commandLog: make([]Command, 0),
	}
}

// SetStdinPipe sets the stdin pipe for sending input
func (ch *CommandHandler) SetStdinPipe(pipe io.WriteCloser) {
	ch.mu.Lock()
	defer ch.mu.Unlock()
	ch.stdinPipe = pipe
}

// HandleCommand processes a command and returns a response
func (ch *CommandHandler) HandleCommand(cmd Command) CommandResponse {
	ch.mu.Lock()
	ch.commandLog = append(ch.commandLog, cmd)
	ch.mu.Unlock()

	response := CommandResponse{
		RequestID: cmd.RequestID,
		Success:   false,
	}

	switch cmd.Type {
	case "pause":
		response = ch.handlePause(cmd)
	case "resume":
		response = ch.handleResume(cmd)
	case "kill":
		response = ch.handleKill(cmd)
	case "send_input":
		response = ch.handleSendInput(cmd)
	case "get_state":
		response = ch.handleGetState(cmd)
	case "send_signal":
		response = ch.handleSendSignal(cmd)
	default:
		response.Message = fmt.Sprintf("Unknown command type: %s", cmd.Type)
	}

	return response
}

// handlePause pauses the process (SIGSTOP on Unix)
func (ch *CommandHandler) handlePause(cmd Command) CommandResponse {
	ch.mu.Lock()
	defer ch.mu.Unlock()

	if ch.paused {
		return CommandResponse{
			RequestID: cmd.RequestID,
			Success:   false,
			Message:   "Process is already paused",
		}
	}

	// Send SIGSTOP signal
	if err := ch.wrapper.Pause(); err != nil {
		return CommandResponse{
			RequestID: cmd.RequestID,
			Success:   false,
			Message:   fmt.Sprintf("Failed to pause: %v", err),
		}
	}

	ch.paused = true
	log.Printf("[CommandHandler] Process paused: %s", ch.wrapper.sessionID)

	return CommandResponse{
		RequestID: cmd.RequestID,
		Success:   true,
		Message:   "Process paused successfully",
		Data: map[string]interface{}{
			"paused": true,
		},
	}
}

// handleResume resumes the process (SIGCONT on Unix)
func (ch *CommandHandler) handleResume(cmd Command) CommandResponse {
	ch.mu.Lock()
	defer ch.mu.Unlock()

	if !ch.paused {
		return CommandResponse{
			RequestID: cmd.RequestID,
			Success:   false,
			Message:   "Process is not paused",
		}
	}

	// Send SIGCONT signal
	if err := ch.wrapper.Resume(); err != nil {
		return CommandResponse{
			RequestID: cmd.RequestID,
			Success:   false,
			Message:   fmt.Sprintf("Failed to resume: %v", err),
		}
	}

	ch.paused = false
	log.Printf("[CommandHandler] Process resumed: %s", ch.wrapper.sessionID)

	return CommandResponse{
		RequestID: cmd.RequestID,
		Success:   true,
		Message:   "Process resumed successfully",
		Data: map[string]interface{}{
			"paused": false,
		},
	}
}

// handleKill kills the process
func (ch *CommandHandler) handleKill(cmd Command) CommandResponse {
	ch.mu.Lock()
	defer ch.mu.Unlock()

	if err := ch.wrapper.Stop(); err != nil {
		return CommandResponse{
			RequestID: cmd.RequestID,
			Success:   false,
			Message:   fmt.Sprintf("Failed to kill: %v", err),
		}
	}

	log.Printf("[CommandHandler] Process killed: %s", ch.wrapper.sessionID)

	return CommandResponse{
		RequestID: cmd.RequestID,
		Success:   true,
		Message:   "Process killed successfully",
	}
}

// handleSendInput sends input to process stdin
func (ch *CommandHandler) handleSendInput(cmd Command) CommandResponse {
	ch.mu.RLock()
	pipe := ch.stdinPipe
	ch.mu.RUnlock()

	if pipe == nil {
		return CommandResponse{
			RequestID: cmd.RequestID,
			Success:   false,
			Message:   "Stdin pipe not available",
		}
	}

	input, ok := cmd.Data["input"].(string)
	if !ok {
		return CommandResponse{
			RequestID: cmd.RequestID,
			Success:   false,
			Message:   "Invalid input data",
		}
	}

	// Write to stdin
	_, err := pipe.Write([]byte(input + "\n"))
	if err != nil {
		return CommandResponse{
			RequestID: cmd.RequestID,
			Success:   false,
			Message:   fmt.Sprintf("Failed to write to stdin: %v", err),
		}
	}

	log.Printf("[CommandHandler] Sent input to %s: %s", ch.wrapper.sessionID, input)

	return CommandResponse{
		RequestID: cmd.RequestID,
		Success:   true,
		Message:   "Input sent successfully",
		Data: map[string]interface{}{
			"bytes_written": len(input) + 1,
		},
	}
}

// handleGetState returns the current state
func (ch *CommandHandler) handleGetState(cmd Command) CommandResponse {
	ch.mu.RLock()
	paused := ch.paused
	ch.mu.RUnlock()

	state := ch.wrapper.GetState()

	return CommandResponse{
		RequestID: cmd.RequestID,
		Success:   true,
		Message:   "State retrieved successfully",
		Data: map[string]interface{}{
			"state":      state,
			"paused":     paused,
			"session_id": ch.wrapper.sessionID,
			"exit_code":  ch.wrapper.exitCode,
		},
	}
}

// handleSendSignal sends a custom signal to the process
func (ch *CommandHandler) handleSendSignal(cmd Command) CommandResponse {
	signalName, ok := cmd.Data["signal"].(string)
	if !ok {
		return CommandResponse{
			RequestID: cmd.RequestID,
			Success:   false,
			Message:   "Signal name required",
		}
	}

	if err := ch.wrapper.SendSignal(signalName); err != nil {
		return CommandResponse{
			RequestID: cmd.RequestID,
			Success:   false,
			Message:   fmt.Sprintf("Failed to send signal: %v", err),
		}
	}

	log.Printf("[CommandHandler] Sent signal %s to %s", signalName, ch.wrapper.sessionID)

	return CommandResponse{
		RequestID: cmd.RequestID,
		Success:   true,
		Message:   fmt.Sprintf("Signal %s sent successfully", signalName),
	}
}

// GetCommandHistory returns the command history
func (ch *CommandHandler) GetCommandHistory() []Command {
	ch.mu.RLock()
	defer ch.mu.RUnlock()

	history := make([]Command, len(ch.commandLog))
	copy(history, ch.commandLog)
	return history
}

// IsPaused returns whether the process is paused
func (ch *CommandHandler) IsPaused() bool {
	ch.mu.RLock()
	defer ch.mu.RUnlock()
	return ch.paused
}
