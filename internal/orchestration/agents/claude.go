package agents

import (
	"bytes"
	"context"
	"fmt"
	"os/exec"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

// ClaudeAgent implements the Agent interface for Claude Code CLI
type ClaudeAgent struct {
	config           AgentConfig
	binaryPath       string
	semaphore        chan struct{}    // Concurrency limiting
	activeTasks      int32            // Atomic counter
	totalTasks       int64
	successfulTasks  int64
	failedTasks      int64
	lastUsed         *time.Time
	mutex            sync.RWMutex
}

// NewClaudeAgent creates a new Claude Code agent
func NewClaudeAgent(config AgentConfig) (*ClaudeAgent, error) {
	if config.BinaryPath == "" {
		config.BinaryPath = "claude" // Default to PATH lookup
	}

	// Verify Claude is available
	if _, err := exec.LookPath(config.BinaryPath); err != nil {
		return nil, fmt.Errorf("Claude binary not found at %s: %w", config.BinaryPath, err)
	}

	if config.MaxConcurrent == 0 {
		config.MaxConcurrent = 1 // Default: one task at a time
	}

	if config.Timeout == 0 {
		config.Timeout = 30 * time.Minute // Default timeout
	}

	agent := &ClaudeAgent{
		config:     config,
		binaryPath: config.BinaryPath,
		semaphore:  make(chan struct{}, config.MaxConcurrent),
	}

	return agent, nil
}

// GetID returns the agent's identifier
func (ca *ClaudeAgent) GetID() AgentID {
	return ca.config.ID
}

// GetType returns the agent type
func (ca *ClaudeAgent) GetType() string {
	return ca.config.Type
}

// GetCapabilities returns what this agent can do
func (ca *ClaudeAgent) GetCapabilities() []AgentCapability {
	return ca.config.Capabilities
}

// GetStatus returns the current status of the agent
func (ca *ClaudeAgent) GetStatus() AgentStatus {
	activeTasks := atomic.LoadInt32(&ca.activeTasks)
	if activeTasks >= int32(ca.config.MaxConcurrent) {
		return AgentStatusBusy
	}
	return AgentStatusAvailable
}

// Execute runs a task with Claude Code
func (ca *ClaudeAgent) Execute(ctx context.Context, task *AgentTask) (*AgentResult, error) {
	result := &AgentResult{
		TaskID:      task.ID,
		AgentID:     ca.config.ID,
		CompletedAt: time.Now(),
	}

	startTime := time.Now()

	// Acquire semaphore slot
	select {
	case ca.semaphore <- struct{}{}:
		defer func() { <-ca.semaphore }()
	case <-ctx.Done():
		result.Error = "context cancelled before execution"
		return result, fmt.Errorf("context cancelled")
	}

	// Increment active task counter
	atomic.AddInt32(&ca.activeTasks, 1)
	defer func() {
		atomic.AddInt32(&ca.activeTasks, -1)
	}()

	// Update last used time
	now := time.Now()
	ca.mutex.Lock()
	ca.lastUsed = &now
	ca.mutex.Unlock()

	// Increment total tasks
	atomic.AddInt64(&ca.totalTasks, 1)

	// Create execution context with timeout
	execCtx, cancel := context.WithTimeout(ctx, task.Timeout)
	defer cancel()

	// Build Claude command
	cmd := exec.CommandContext(execCtx, ca.binaryPath)

	// Add instruction as argument
	cmd.Args = append(cmd.Args, "--prompt", task.Instruction)

	// Set working directory if specified
	if task.WorkDir != "" {
		cmd.Dir = task.WorkDir
	}

	// Add environment variables from task context if any
	if ca.config.Environment != nil {
		for k, v := range ca.config.Environment {
			cmd.Env = append(cmd.Env, fmt.Sprintf("%s=%s", k, v))
		}
	}

	// Capture output
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	// Execute Claude
	err := cmd.Run()

	result.Output = stdout.String()
	if stderr.Len() > 0 {
		result.Output += "\nSTDERR:\n" + stderr.String()
	}

	result.Duration = time.Since(startTime)

	if err != nil {
		result.Success = false
		result.Error = err.Error()
		atomic.AddInt64(&ca.failedTasks, 1)
		return result, fmt.Errorf("claude execution failed: %w", err)
	}

	result.Success = true
	atomic.AddInt64(&ca.successfulTasks, 1)

	// Parse output for modified files (basic extraction)
	result.ModifiedFiles = extractModifiedFiles(result.Output)

	return result, nil
}

// IsAvailable checks if the agent can accept more work
func (ca *ClaudeAgent) IsAvailable() bool {
	return ca.GetStatus() == AgentStatusAvailable
}

// GetQueueLength returns number of queued tasks (placeholder)
func (ca *ClaudeAgent) GetQueueLength() int {
	return 0 // No queue tracking for now
}

// GetActiveTaskCount returns number of currently running tasks
func (ca *ClaudeAgent) GetActiveTaskCount() int {
	return int(atomic.LoadInt32(&ca.activeTasks))
}

// GetStats returns agent statistics
func (ca *ClaudeAgent) GetStats() *AgentStats {
	ca.mutex.RLock()
	lastUsed := ca.lastUsed
	ca.mutex.RUnlock()

	total := atomic.LoadInt64(&ca.totalTasks)
	successful := atomic.LoadInt64(&ca.successfulTasks)

	successRate := 0.0
	if total > 0 {
		successRate = float64(successful) / float64(total) * 100
	}

	return &AgentStats{
		AgentID:         ca.config.ID,
		Status:          ca.GetStatus(),
		TotalTasks:      total,
		SuccessfulTasks: successful,
		FailedTasks:     atomic.LoadInt64(&ca.failedTasks),
		ActiveTasks:     ca.GetActiveTaskCount(),
		LastUsed:        lastUsed,
		SuccessRate:     successRate,
	}
}

// Helper functions

func extractModifiedFiles(output string) []string {
	// Simple extraction - look for file mentions in output
	// In a real implementation, this would be more sophisticated
	var files []string

	lines := strings.Split(output, "\n")
	for _, line := range lines {
		if strings.Contains(line, "modified:") || strings.Contains(line, "created:") {
			// Try to extract file path
			parts := strings.Fields(line)
			if len(parts) > 1 {
				files = append(files, parts[len(parts)-1])
			}
		}
	}

	return files
}
