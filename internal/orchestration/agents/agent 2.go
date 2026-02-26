package agents

import (
	"context"
	"time"
)

// AgentID represents the unique identifier for an agent
type AgentID string

const (
	AgentIDClaude AgentID = "claude"
	AgentIDGemini AgentID = "gemini"
)

// AgentCapability represents what an agent can do
type AgentCapability string

const (
	CapabilityCodeGeneration AgentCapability = "code_generation"
	CapabilityCodeReview     AgentCapability = "code_review"
	CapabilityRefactoring    AgentCapability = "refactoring"
	CapabilityTesting        AgentCapability = "testing"
	CapabilityDocumentation  AgentCapability = "documentation"
)

// AgentStatus represents the current state of an agent
type AgentStatus string

const (
	AgentStatusAvailable   AgentStatus = "available"
	AgentStatusBusy        AgentStatus = "busy"
	AgentStatusUnavailable AgentStatus = "unavailable"
)

// AgentTask represents work to be performed by an agent
type AgentTask struct {
	ID           string                 `json:"id"`
	AgentID      AgentID                `json:"agent_id"`
	TaskType     string                 `json:"task_type"`        // code_generation, code_review, etc.
	Instruction  string                 `json:"instruction"`      // Natural language instruction
	Context      map[string]interface{} `json:"context"`          // Additional context
	WorkDir      string                 `json:"work_dir"`         // Working directory
	Files        []string               `json:"files"`            // Files to work with
	Timeout      time.Duration          `json:"timeout"`          // Execution timeout
	Priority     int                    `json:"priority"`         // Higher = more important
	CreatedAt    time.Time              `json:"created_at"`
	StartedAt    *time.Time             `json:"started_at"`
	CompletedAt  *time.Time             `json:"completed_at"`
}

// AgentResult represents the output of a completed agent task
type AgentResult struct {
	TaskID      string        `json:"task_id"`
	AgentID     AgentID       `json:"agent_id"`
	Success     bool          `json:"success"`
	Output      string        `json:"output"`
	ModifiedFiles []string    `json:"modified_files"`
	Error       string        `json:"error"`
	Duration    time.Duration `json:"duration"`
	CompletedAt time.Time     `json:"completed_at"`
}

// Agent interface defines how to interact with AI agents
type Agent interface {
	// Identity
	GetID() AgentID
	GetType() string
	GetCapabilities() []AgentCapability
	GetStatus() AgentStatus

	// Execution
	Execute(ctx context.Context, task *AgentTask) (*AgentResult, error)

	// Availability
	IsAvailable() bool
	GetQueueLength() int
	GetActiveTaskCount() int
}

// AgentConfig holds configuration for an agent
type AgentConfig struct {
	ID           AgentID
	Type         string
	Capabilities []AgentCapability
	BinaryPath   string // Path to agent binary (claude, gemini, etc.)
	MaxConcurrent int    // Maximum concurrent tasks
	Timeout      time.Duration
	Environment  map[string]string
}

// AgentStats holds performance statistics for an agent
type AgentStats struct {
	AgentID           AgentID       `json:"agent_id"`
	Status            AgentStatus   `json:"status"`
	TotalTasks        int64         `json:"total_tasks"`
	SuccessfulTasks   int64         `json:"successful_tasks"`
	FailedTasks       int64         `json:"failed_tasks"`
	ActiveTasks       int           `json:"active_tasks"`
	QueuedTasks       int           `json:"queued_tasks"`
	AverageLoadTime   time.Duration `json:"average_load_time"`
	AverageTaskTime   time.Duration `json:"average_task_time"`
	LastUsed          *time.Time    `json:"last_used"`
	SuccessRate       float64       `json:"success_rate"`
}
