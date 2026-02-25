package workflow

import (
	"fmt"
	"time"
)

// WorkflowStatus represents the execution state of a workflow
type WorkflowStatus string

const (
	WorkflowStatusPending   WorkflowStatus = "pending"
	WorkflowStatusRunning   WorkflowStatus = "running"
	WorkflowStatusCompleted WorkflowStatus = "completed"
	WorkflowStatusFailed    WorkflowStatus = "failed"
	WorkflowStatusCanceled  WorkflowStatus = "canceled"
)

// TaskStatus represents the execution state of a task
type TaskStatus string

const (
	TaskStatusPending   TaskStatus = "pending"
	TaskStatusRunning   TaskStatus = "running"
	TaskStatusCompleted TaskStatus = "completed"
	TaskStatusFailed    TaskStatus = "failed"
	TaskStatusSkipped   TaskStatus = "skipped"
	TaskStatusRetrying  TaskStatus = "retrying"
)

// TaskType represents the kind of task to execute
type TaskType string

const (
	TaskTypeShell    TaskType = "shell"
	TaskTypeCode     TaskType = "code"
	TaskTypeTest     TaskType = "test"
	TaskTypeReview   TaskType = "review"
	TaskTypeRefactor TaskType = "refactor"
)

// AgentType represents which agent executes a task
type AgentType string

const (
	AgentTypeSystem AgentType = "system"
	AgentTypeClaude AgentType = "claude"
	AgentTypeGemini AgentType = "gemini"
)

// ErrorAction specifies what to do on task failure
type ErrorAction string

const (
	ErrorActionRetry    ErrorAction = "retry"
	ErrorActionContinue ErrorAction = "continue"
	ErrorActionFail     ErrorAction = "fail"
)

// Workflow represents a complete workflow definition and execution state
type Workflow struct {
	ID          string                 `json:"id"`
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	Version     string                 `json:"version"`
	Status      WorkflowStatus         `json:"status"`
	Tasks       map[string]*Task       `json:"-"` // Task ID -> Task
	Variables   map[string]interface{} `json:"variables"`
	CreatedAt   time.Time              `json:"created_at"`
	StartedAt   *time.Time             `json:"started_at"`
	CompletedAt *time.Time             `json:"completed_at"`
	Error       string                 `json:"error"`
}

// Task represents a single work unit within a workflow
type Task struct {
	ID           string            `json:"id"`
	Name         string            `json:"name"`
	Type         TaskType          `json:"type"`
	Agent        AgentType         `json:"agent"`
	Command      string            `json:"command"`
	Status       TaskStatus        `json:"status"`
	WorkDir      string            `json:"work_dir"`
	Dependencies []string          `json:"dependencies"` // List of task IDs this depends on
	OnError      ErrorAction       `json:"on_error"`
	Timeout      time.Duration     `json:"timeout"`
	MaxRetries   int               `json:"max_retries"`
	RetryCount   int               `json:"retry_count"`
	Environment  map[string]string `json:"environment"`
	Output       string            `json:"output"`
	Error        string            `json:"error"`
	StartedAt    *time.Time        `json:"started_at"`
	CompletedAt  *time.Time        `json:"completed_at"`
}

// WorkflowDefinition is the parsed YAML structure
type WorkflowDefinition struct {
	Name        string                 `yaml:"name"`
	Description string                 `yaml:"description"`
	Version     string                 `yaml:"version"`
	Variables   map[string]interface{} `yaml:"variables"`
	Tasks       []*TaskDefinition      `yaml:"tasks"`
}

// TaskDefinition is the YAML representation of a task
type TaskDefinition struct {
	ID           string            `yaml:"id"`
	Name         string            `yaml:"name"`
	Type         string            `yaml:"type"`
	Agent        string            `yaml:"agent"`
	Command      string            `yaml:"command"`
	WorkDir      string            `yaml:"work_dir"`
	Dependencies []string          `yaml:"dependencies"`
	OnError      string            `yaml:"on_error"`
	Timeout      string            `yaml:"timeout"`
	MaxRetries   int               `yaml:"max_retries"`
	Environment  map[string]string `yaml:"environment"`
}

// ExecutionContext holds runtime information during workflow execution
type ExecutionContext struct {
	WorkflowID   string
	CurrentTask  *Task
	Variables    map[string]interface{}
	Results      map[string]TaskResult // Task ID -> Result
	SessionID    string                // Optional GAIA session ID
	StartTime    time.Time
}

// TaskResult holds the result of a completed task
type TaskResult struct {
	TaskID      string
	Status      TaskStatus
	Output      string
	Error       string
	Duration    time.Duration
	RetryCount  int
	CompletedAt time.Time
}

// TaskDAG represents task dependencies as a directed acyclic graph
type TaskDAG struct {
	tasks      map[string]*Task
	adjacency  map[string][]string // task ID -> dependencies
	inDegree   map[string]int       // number of dependencies per task
	completed  map[string]bool      // completed task tracking
}

// NewTaskDAG creates a new task DAG from a workflow
func NewTaskDAG(workflow *Workflow) *TaskDAG {
	dag := &TaskDAG{
		tasks:     workflow.Tasks,
		adjacency: make(map[string][]string),
		inDegree:  make(map[string]int),
		completed: make(map[string]bool),
	}

	// Build adjacency list and calculate in-degrees
	for taskID := range workflow.Tasks {
		dag.adjacency[taskID] = []string{}
		dag.inDegree[taskID] = 0
	}

	for taskID, task := range workflow.Tasks {
		dag.inDegree[taskID] = len(task.Dependencies)
		for _, dep := range task.Dependencies {
			dag.adjacency[dep] = append(dag.adjacency[dep], taskID)
		}
	}

	return dag
}

// TopologicalSort returns tasks in execution order
// Tasks with no dependencies come first, followed by their dependents
func (dag *TaskDAG) TopologicalSort() ([][]*Task, error) {
	// Group tasks by depth level (all independents first, then their dependents, etc.)
	levels := make([][]*Task, 0)
	inDegree := make(map[string]int)
	for taskID, deg := range dag.inDegree {
		inDegree[taskID] = deg
	}

	for len(inDegree) > 0 {
		// Find all tasks with no remaining dependencies
		currentLevel := make([]*Task, 0)
		for taskID, deg := range inDegree {
			if deg == 0 {
				currentLevel = append(currentLevel, dag.tasks[taskID])
				delete(inDegree, taskID)
			}
		}

		if len(currentLevel) == 0 && len(inDegree) > 0 {
			// Circular dependency detected
			return nil, fmt.Errorf("circular dependency detected in workflow")
		}

		if len(currentLevel) > 0 {
			levels = append(levels, currentLevel)

			// Decrement in-degree for dependent tasks
			for _, task := range currentLevel {
				for _, dependent := range dag.adjacency[task.ID] {
					inDegree[dependent]--
				}
			}
		}
	}

	return levels, nil
}

// GetReadyTasks returns all tasks that can run now (no pending dependencies)
func (dag *TaskDAG) GetReadyTasks() []*Task {
	ready := make([]*Task, 0)

	for taskID, task := range dag.tasks {
		if task.Status != TaskStatusPending {
			continue // Skip if not pending
		}

		// Check if all dependencies are completed
		allDepsCompleted := true
		for _, dep := range task.Dependencies {
			if !dag.completed[dep] {
				allDepsCompleted = false
				break
			}
		}

		if allDepsCompleted {
			ready = append(ready, task)
		}
	}

	return ready
}

// MarkCompleted marks a task as completed and updates the graph state
func (dag *TaskDAG) MarkCompleted(taskID string) {
	dag.completed[taskID] = true
}

// IsCyclic checks if the DAG has any cycles
func (dag *TaskDAG) IsCyclic() bool {
	visited := make(map[string]bool)
	recStack := make(map[string]bool)

	for taskID := range dag.tasks {
		if !visited[taskID] {
			if dag.isCyclicUtil(taskID, visited, recStack) {
				return true
			}
		}
	}

	return false
}

func (dag *TaskDAG) isCyclicUtil(taskID string, visited map[string]bool, recStack map[string]bool) bool {
	visited[taskID] = true
	recStack[taskID] = true

	// Check all dependents
	for _, dependent := range dag.adjacency[taskID] {
		if !visited[dependent] {
			if dag.isCyclicUtil(dependent, visited, recStack) {
				return true
			}
		} else if recStack[dependent] {
			return true
		}
	}

	recStack[taskID] = false
	return false
}
