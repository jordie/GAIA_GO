package dtos

import (
	"time"
)

// ============================================================================
// Component 1: Tmux Session DTOs
// ============================================================================

// CreateSessionRequest represents a request to create a new GAIA session
type CreateSessionRequest struct {
	Name        string            `json:"name" binding:"required"`
	ProjectPath string            `json:"project_path" binding:"required"`
	Shell       string            `json:"shell"`
	Metadata    map[string]string `json:"metadata"`
	Tags        []string          `json:"tags"`
}

// SessionResponse represents a GAIA session in API responses
type SessionResponse struct {
	ID          string            `json:"id"`
	Name        string            `json:"name"`
	ProjectPath string            `json:"project_path"`
	Status      string            `json:"status"`
	CreatedAt   time.Time         `json:"created_at"`
	LastActive  time.Time         `json:"last_active"`
	Metadata    map[string]string `json:"metadata"`
	Tags        []string          `json:"tags"`
}

// CreateWindowRequest represents a request to add a window to a session
type CreateWindowRequest struct {
	Name string `json:"name" binding:"required"`
}

// WindowResponse represents a window in API responses
type WindowResponse struct {
	ID        string    `json:"id"`
	Name      string    `json:"name"`
	Index     int       `json:"index"`
	Active    bool      `json:"active"`
	CreatedAt time.Time `json:"created_at"`
}

// CreatePaneRequest represents a request to create a pane
type CreatePaneRequest struct {
	Command  string `json:"command"`
	WorkDir  string `json:"work_dir"`
	Vertical bool   `json:"vertical"`
}

// PaneResponse represents a pane in API responses
type PaneResponse struct {
	ID        string    `json:"id"`
	Index     int       `json:"index"`
	Command   string    `json:"command"`
	WorkDir   string    `json:"work_dir"`
	Active    bool      `json:"active"`
	CreatedAt time.Time `json:"created_at"`
}

// SendKeysRequest represents a request to send keys to a pane
type SendKeysRequest struct {
	Keys      string `json:"keys" binding:"required"`
	SendEnter bool   `json:"send_enter"`
}

// CaptureResponse represents pane output
type CaptureResponse struct {
	Content string `json:"content"`
	Pane    string `json:"pane"`
}

// ============================================================================
// Component 2: Workflow Orchestrator DTOs
// ============================================================================

// CreateWorkflowRequest represents a request to create a workflow
type CreateWorkflowRequest struct {
	Definition string                 `json:"definition" binding:"required"` // YAML content
	Variables  map[string]interface{} `json:"variables"`
}

// WorkflowResponse represents a workflow in API responses
type WorkflowResponse struct {
	ID          string                 `json:"id"`
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	Version     string                 `json:"version"`
	Status      string                 `json:"status"`
	Variables   map[string]interface{} `json:"variables"`
	CreatedAt   time.Time              `json:"created_at"`
	StartedAt   *time.Time             `json:"started_at"`
	CompletedAt *time.Time             `json:"completed_at"`
	Error       string                 `json:"error,omitempty"`
}

// StartWorkflowRequest represents a request to start a workflow
type StartWorkflowRequest struct {
	Variables map[string]interface{} `json:"variables"`
}

// TaskResponse represents a task in API responses
type TaskResponse struct {
	ID           string    `json:"id"`
	Name         string    `json:"name"`
	Type         string    `json:"type"`
	Agent        string    `json:"agent"`
	Status       string    `json:"status"`
	Output       string    `json:"output,omitempty"`
	Error        string    `json:"error,omitempty"`
	StartedAt    *time.Time `json:"started_at"`
	CompletedAt  *time.Time `json:"completed_at"`
	RetryCount   int       `json:"retry_count"`
	MaxRetries   int       `json:"max_retries"`
}

// WorkflowStatusResponse represents the complete status of a workflow
type WorkflowStatusResponse struct {
	Workflow *WorkflowResponse `json:"workflow"`
	Tasks    []*TaskResponse   `json:"tasks"`
	Progress struct {
		Total       int `json:"total"`
		Completed   int `json:"completed"`
		Failed      int `json:"failed"`
		Percentage  int `json:"percentage"`
	} `json:"progress"`
}

// ============================================================================
// Component 3: Project Scaffolder DTOs
// ============================================================================

// GenerateProjectRequest represents a request to generate a project
type GenerateProjectRequest struct {
	Name         string                 `json:"name" binding:"required"`
	TemplateName string                 `json:"template" binding:"required"`
	OutputPath   string                 `json:"path" binding:"required"`
	Variables    map[string]interface{} `json:"variables"`
}

// TemplateResponse represents a template in API responses
type TemplateResponse struct {
	Name        string `json:"name"`
	DisplayName string `json:"display_name"`
	Description string `json:"description"`
	Version     string `json:"version"`
	Language    string `json:"language"`
	Framework   string `json:"framework"`
}

// TemplateVariableResponse represents a template variable
type TemplateVariableResponse struct {
	Name        string      `json:"name"`
	Description string      `json:"description"`
	Type        string      `json:"type"`
	Required    bool        `json:"required"`
	Default     interface{} `json:"default"`
}

// TemplateDetailsResponse represents a template with full details
type TemplateDetailsResponse struct {
	*TemplateResponse
	Variables []*TemplateVariableResponse `json:"variables"`
	Hooks     map[string][]string         `json:"hooks"`
}

// ProjectGenerationResponse represents the result of project generation
type ProjectGenerationResponse struct {
	ProjectName string    `json:"project_name"`
	ProjectPath string    `json:"project_path"`
	Template    string    `json:"template"`
	CreatedAt   time.Time `json:"created_at"`
	FilesCount  int       `json:"files_count"`
	DirsCount   int       `json:"dirs_count"`
}

// ValidateProjectRequest represents a request to validate a project
type ValidateProjectRequest struct {
	Path string `json:"path" binding:"required"`
}

// ValidateProjectResponse represents project validation result
type ValidateProjectResponse struct {
	IsValid bool   `json:"is_valid"`
	Message string `json:"message"`
	Path    string `json:"path"`
}

// ============================================================================
// Component 4: Service Coordinator DTOs
// ============================================================================

// RegisterServiceRequest represents a request to register a service
type RegisterServiceRequest struct {
	Name        string                 `json:"name" binding:"required"`
	Type        string                 `json:"type" binding:"required"`
	Command     string                 `json:"command" binding:"required"`
	Args        []string               `json:"args"`
	WorkDir     string                 `json:"work_dir"`
	Port        int                    `json:"port"`
	Environment map[string]string      `json:"environment"`
	HealthCheck *HealthCheckConfig     `json:"health_check"`
	AutoRestart bool                   `json:"auto_restart"`
	Metadata    map[string]interface{} `json:"metadata"`
}

// HealthCheckConfig represents health check configuration
type HealthCheckConfig struct {
	Type       string `json:"type" binding:"required,oneof=http tcp exec none"`
	Endpoint   string `json:"endpoint"`
	Port       int    `json:"port"`
	Command    string `json:"command"`
	Interval   string `json:"interval"`
	Timeout    string `json:"timeout"`
	Retries    int    `json:"retries"`
	StartDelay string `json:"start_delay"`
}

// ServiceResponse represents a service in API responses
type ServiceResponse struct {
	ID              string                 `json:"id"`
	Name            string                 `json:"name"`
	Type            string                 `json:"type"`
	Command         string                 `json:"command"`
	Status          string                 `json:"status"`
	Port            int                    `json:"port"`
	ProcessID       int                    `json:"process_id"`
	Restarts        int                    `json:"restarts"`
	HealthStatus    string                 `json:"health_status"`
	StartedAt       *time.Time             `json:"started_at"`
	StoppedAt       *time.Time             `json:"stopped_at"`
	LastHealthCheck *time.Time             `json:"last_health_check"`
	Error           string                 `json:"error,omitempty"`
	CreatedAt       time.Time              `json:"created_at"`
}

// ServiceHealthResponse represents service health check result
type ServiceHealthResponse struct {
	ServiceID      string `json:"service_id"`
	IsHealthy      bool   `json:"is_healthy"`
	LastCheckTime  *time.Time `json:"last_check_time"`
	FailureCount   int    `json:"failure_count"`
	LastError      string `json:"last_error"`
	ResponseTimeMs int64  `json:"response_time_ms"`
}

// ServiceMetricsResponse represents service metrics
type ServiceMetricsResponse struct {
	ServiceID    string `json:"service_id"`
	CPUPercent   float64 `json:"cpu_percent"`
	MemoryMB     int64  `json:"memory_mb"`
	PID          int    `json:"pid"`
	UptimeSeconds int64  `json:"uptime_seconds"`
	RestartCount int    `json:"restart_count"`
	SuccessCount int64  `json:"health_checks_passed"`
	FailureCount int64  `json:"health_checks_failed"`
}

// ServiceLogsResponse represents service logs
type ServiceLogsResponse struct {
	ServiceID string `json:"service_id"`
	Logs      string `json:"logs"`
	Lines     int    `json:"lines"`
}

// ============================================================================
// Component 5: AI Agent Bridge DTOs
// ============================================================================

// ExecuteAgentTaskRequest represents a request to execute an agent task
type ExecuteAgentTaskRequest struct {
	AgentID     string                 `json:"agent" binding:"required,oneof=claude gemini"`
	TaskType    string                 `json:"task_type"`
	Instruction string                 `json:"instruction" binding:"required"`
	Context     map[string]interface{} `json:"context"`
	WorkDir     string                 `json:"work_dir"`
	Files       []string               `json:"files"`
	Timeout     string                 `json:"timeout"`
	Priority    int                    `json:"priority"`
}

// ExecuteParallelRequest represents a request to execute tasks in parallel
type ExecuteParallelRequest struct {
	Tasks []*ExecuteAgentTaskRequest `json:"tasks" binding:"required,min=1"`
}

// AgentTaskResponse represents an agent task in API responses
type AgentTaskResponse struct {
	ID          string                 `json:"id"`
	AgentID     string                 `json:"agent_id"`
	TaskType    string                 `json:"task_type"`
	Instruction string                 `json:"instruction"`
	Status      string                 `json:"status"`
	CreatedAt   time.Time              `json:"created_at"`
	StartedAt   *time.Time             `json:"started_at"`
	CompletedAt *time.Time             `json:"completed_at"`
}

// AgentResultResponse represents the result of an agent task
type AgentResultResponse struct {
	TaskID         string        `json:"task_id"`
	AgentID        string        `json:"agent_id"`
	Success        bool          `json:"success"`
	Output         string        `json:"output"`
	ModifiedFiles  []string      `json:"modified_files"`
	Error          string        `json:"error,omitempty"`
	Duration       int64         `json:"duration_ms"`
	CompletedAt    time.Time     `json:"completed_at"`
}

// AgentResponse represents an agent in API responses
type AgentResponse struct {
	ID            string   `json:"id"`
	Type          string   `json:"type"`
	Status        string   `json:"status"`
	Capabilities  []string `json:"capabilities"`
	ActiveTasks   int      `json:"active_tasks"`
	QueuedTasks   int      `json:"queued_tasks"`
	IsAvailable   bool     `json:"is_available"`
}

// AgentStatsResponse represents agent statistics
type AgentStatsResponse struct {
	AgentID          string  `json:"agent_id"`
	Status           string  `json:"status"`
	TotalTasks       int64   `json:"total_tasks"`
	SuccessfulTasks  int64   `json:"successful_tasks"`
	FailedTasks      int64   `json:"failed_tasks"`
	ActiveTasks      int     `json:"active_tasks"`
	QueuedTasks      int     `json:"queued_tasks"`
	SuccessRate      float64 `json:"success_rate"`
	LastUsed         *time.Time `json:"last_used"`
}

// ============================================================================
// Common DTOs
// ============================================================================

// ErrorResponse represents an error in API responses
type ErrorResponse struct {
	Error      string `json:"error"`
	Message    string `json:"message"`
	StatusCode int    `json:"status_code"`
	Timestamp  time.Time `json:"timestamp"`
}

// SuccessResponse represents a successful operation
type SuccessResponse struct {
	Message string      `json:"message"`
	Data    interface{} `json:"data,omitempty"`
}

// ListResponse represents a paginated list response
type ListResponse struct {
	Items      interface{} `json:"items"`
	Total      int         `json:"total"`
	Page       int         `json:"page"`
	PageSize   int         `json:"page_size"`
	TotalPages int         `json:"total_pages"`
}
