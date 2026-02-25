package agents

import (
	"bytes"
	"context"
	"fmt"
	"os/exec"
	"sync"
	"sync/atomic"
	"time"
)

// GeminiAgent implements the Agent interface for Gemini
type GeminiAgent struct {
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

// NewGeminiAgent creates a new Gemini agent
func NewGeminiAgent(config AgentConfig) (*GeminiAgent, error) {
	if config.BinaryPath == "" {
		config.BinaryPath = "gemini" // Default to PATH lookup
	}

	// Verify Gemini is available
	if _, err := exec.LookPath(config.BinaryPath); err != nil {
		return nil, fmt.Errorf("Gemini binary not found at %s: %w", config.BinaryPath, err)
	}

	if config.MaxConcurrent == 0 {
		config.MaxConcurrent = 1 // Default: one task at a time
	}

	if config.Timeout == 0 {
		config.Timeout = 30 * time.Minute // Default timeout
	}

	agent := &GeminiAgent{
		config:     config,
		binaryPath: config.BinaryPath,
		semaphore:  make(chan struct{}, config.MaxConcurrent),
	}

	return agent, nil
}

// GetID returns the agent's identifier
func (ga *GeminiAgent) GetID() AgentID {
	return ga.config.ID
}

// GetType returns the agent type
func (ga *GeminiAgent) GetType() string {
	return ga.config.Type
}

// GetCapabilities returns what this agent can do
func (ga *GeminiAgent) GetCapabilities() []AgentCapability {
	return ga.config.Capabilities
}

// GetStatus returns the current status of the agent
func (ga *GeminiAgent) GetStatus() AgentStatus {
	activeTasks := atomic.LoadInt32(&ga.activeTasks)
	if activeTasks >= int32(ga.config.MaxConcurrent) {
		return AgentStatusBusy
	}
	return AgentStatusAvailable
}

// Execute runs a task with Gemini
func (ga *GeminiAgent) Execute(ctx context.Context, task *AgentTask) (*AgentResult, error) {
	result := &AgentResult{
		TaskID:      task.ID,
		AgentID:     ga.config.ID,
		CompletedAt: time.Now(),
	}

	startTime := time.Now()

	// Acquire semaphore slot
	select {
	case ga.semaphore <- struct{}{}:
		defer func() { <-ga.semaphore }()
	case <-ctx.Done():
		result.Error = "context cancelled before execution"
		return result, fmt.Errorf("context cancelled")
	}

	// Increment active task counter
	atomic.AddInt32(&ga.activeTasks, 1)
	defer func() {
		atomic.AddInt32(&ga.activeTasks, -1)
	}()

	// Update last used time
	now := time.Now()
	ga.mutex.Lock()
	ga.lastUsed = &now
	ga.mutex.Unlock()

	// Increment total tasks
	atomic.AddInt64(&ga.totalTasks, 1)

	// Create execution context with timeout
	execCtx, cancel := context.WithTimeout(ctx, task.Timeout)
	defer cancel()

	// Build Gemini command
	cmd := exec.CommandContext(execCtx, ga.binaryPath)

	// Add instruction as argument
	cmd.Args = append(cmd.Args, "--prompt", task.Instruction)

	// Set working directory if specified
	if task.WorkDir != "" {
		cmd.Dir = task.WorkDir
	}

	// Add environment variables from agent config
	if ga.config.Environment != nil {
		for k, v := range ga.config.Environment {
			cmd.Env = append(cmd.Env, fmt.Sprintf("%s=%s", k, v))
		}
	}

	// Capture output
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	// Execute Gemini
	err := cmd.Run()

	result.Output = stdout.String()
	if stderr.Len() > 0 {
		result.Output += "\nSTDERR:\n" + stderr.String()
	}

	result.Duration = time.Since(startTime)

	if err != nil {
		result.Success = false
		result.Error = err.Error()
		atomic.AddInt64(&ga.failedTasks, 1)
		return result, fmt.Errorf("gemini execution failed: %w", err)
	}

	result.Success = true
	atomic.AddInt64(&ga.successfulTasks, 1)

	// Parse output for modified files
	result.ModifiedFiles = extractModifiedFiles(result.Output)

	return result, nil
}

// IsAvailable checks if the agent can accept more work
func (ga *GeminiAgent) IsAvailable() bool {
	return ga.GetStatus() == AgentStatusAvailable
}

// GetQueueLength returns number of queued tasks (placeholder)
func (ga *GeminiAgent) GetQueueLength() int {
	return 0 // No queue tracking for now
}

// GetActiveTaskCount returns number of currently running tasks
func (ga *GeminiAgent) GetActiveTaskCount() int {
	return int(atomic.LoadInt32(&ga.activeTasks))
}

// GetStats returns agent statistics
func (ga *GeminiAgent) GetStats() *AgentStats {
	ga.mutex.RLock()
	lastUsed := ga.lastUsed
	ga.mutex.Unlock()

	total := atomic.LoadInt64(&ga.totalTasks)
	successful := atomic.LoadInt64(&ga.successfulTasks)

	successRate := 0.0
	if total > 0 {
		successRate = float64(successful) / float64(total) * 100
	}

	return &AgentStats{
		AgentID:         ga.config.ID,
		Status:          ga.GetStatus(),
		TotalTasks:      total,
		SuccessfulTasks: successful,
		FailedTasks:     atomic.LoadInt64(&ga.failedTasks),
		ActiveTasks:     ga.GetActiveTaskCount(),
		LastUsed:        lastUsed,
		SuccessRate:     successRate,
	}
}
