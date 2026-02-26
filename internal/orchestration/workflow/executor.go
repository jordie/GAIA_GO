package workflow

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"

	"github.com/jgirmay/GAIA_GO/pkg/services/rate_limiting"
)

// Executor handles execution of individual workflow tasks
type Executor struct {
	workDir       string
	quotaService  *rate_limiting.CommandQuotaService
}

// NewExecutor creates a new task executor
func NewExecutor(workDir string) *Executor {
	return &Executor{
		workDir: workDir,
	}
}

// NewExecutorWithQuotas creates a new task executor with quota service
func NewExecutorWithQuotas(workDir string, quotaService *rate_limiting.CommandQuotaService) *Executor {
	return &Executor{
		workDir:      workDir,
		quotaService: quotaService,
	}
}

// SetQuotaService sets the quota service for enforcing command limits
func (e *Executor) SetQuotaService(quotaService *rate_limiting.CommandQuotaService) {
	e.quotaService = quotaService
}

// Execute runs a single task and returns its output
func (e *Executor) Execute(ctx context.Context, workflow *Workflow, task *Task) (string, error) {
	// Check command quota if quota service is available
	if e.quotaService != nil {
		userID := int64(1) // Default user ID, can be passed via context
		if uid, ok := ctx.Value("user_id").(int64); ok {
			userID = uid
		}

		sessionID, ok := ctx.Value("session_id").(string)
		var sessionIDPtr *string
		if ok {
			sessionIDPtr = &sessionID
		}

		quotaReq := rate_limiting.CommandQuotaRequest{
			UserID:      userID,
			SessionID:   sessionIDPtr,
			CommandType: task.Type,
			CommandSize: len(task.Command),
		}

		decision, err := e.quotaService.CheckCommandQuota(ctx, quotaReq)
		if err != nil {
			// Log error but don't fail execution (quota service is optional)
			fmt.Printf("Warning: quota check failed: %v\n", err)
		} else if !decision.Allowed {
			return "", fmt.Errorf("command quota exceeded: %s (reset at %s)",
				decision.WarningMessage, decision.ResetTime.Format("15:04 MST"))
		} else if decision.ThrottleFactor < 1.0 {
			// Apply throttle factor to context
			ctx = context.WithValue(ctx, "throttle_factor", decision.ThrottleFactor)
		}
	}

	// Execute task based on type
	start := time.Now()
	var output string
	var err error

	switch task.Type {
	case TaskTypeShell:
		output, err = e.executeShell(ctx, task)
	case TaskTypeCode:
		output, err = e.executeCode(ctx, workflow, task)
	case TaskTypeTest:
		output, err = e.executeTest(ctx, task)
	case TaskTypeReview:
		output, err = e.executeReview(ctx, workflow, task)
	case TaskTypeRefactor:
		output, err = e.executeRefactor(ctx, workflow, task)
	default:
		return "", fmt.Errorf("unsupported task type: %s", task.Type)
	}

	// Record execution if quota service is available
	if e.quotaService != nil && err == nil {
		duration := time.Since(start)
		userID := int64(1)
		if uid, ok := ctx.Value("user_id").(int64); ok {
			userID = uid
		}

		if recordErr := e.quotaService.RecordCommandExecution(ctx, userID, task.Type, duration, 0, 0); recordErr != nil {
			fmt.Printf("Warning: failed to record command execution: %v\n", recordErr)
		}
	}

	return output, err
}

// executeShell runs a shell command task
func (e *Executor) executeShell(ctx context.Context, task *Task) (string, error) {
	workDir := task.WorkDir
	if workDir == "" {
		workDir = e.workDir
	}

	// Check for throttle factor in context
	var throttleFactor float64 = 1.0
	if tf, ok := ctx.Value("throttle_factor").(float64); ok {
		throttleFactor = tf
	}

	// Apply throttle delay if system is throttled
	if throttleFactor < 1.0 && throttleFactor > 0 {
		// Calculate delay: if throttle is 0.5, we insert 50% delay
		delay := time.Duration(float64(time.Second) * (1.0 - throttleFactor))
		select {
		case <-time.After(delay):
			// Delay complete
		case <-ctx.Done():
			return "", ctx.Err()
		}
	}

	// Create command
	cmd := exec.CommandContext(ctx, "bash", "-c", task.Command)
	cmd.Dir = workDir

	// Apply environment variables
	cmd.Env = os.Environ()
	for k, v := range task.Environment {
		cmd.Env = append(cmd.Env, fmt.Sprintf("%s=%s", k, v))
	}

	// Capture output
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	// Run command
	err := cmd.Run()

	output := stdout.String()
	if stderr.Len() > 0 {
		output += "\nSTDERR:\n" + stderr.String()
	}

	if err != nil {
		return output, fmt.Errorf("shell command failed: %w", err)
	}

	return output, nil
}

// executeCode runs a code task (delegates to Claude or Gemini)
func (e *Executor) executeCode(ctx context.Context, workflow *Workflow, task *Task) (string, error) {
	// For now, just return the command as output
	// In Component 5 (AI Agent Bridge), this will delegate to Claude/Gemini

	switch task.Agent {
	case AgentTypeClaude:
		return e.executeClaude(ctx, task)
	case AgentTypeGemini:
		return e.executeGemini(ctx, task)
	default:
		return "", fmt.Errorf("unsupported agent for code task: %s", task.Agent)
	}
}

// executeTest runs test tasks (typically shell commands)
func (e *Executor) executeTest(ctx context.Context, task *Task) (string, error) {
	workDir := task.WorkDir
	if workDir == "" {
		workDir = e.workDir
	}

	// Default test command if not specified
	testCmd := task.Command
	if testCmd == "" {
		testCmd = "make test"
	}

	cmd := exec.CommandContext(ctx, "bash", "-c", testCmd)
	cmd.Dir = workDir

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()

	output := stdout.String()
	if stderr.Len() > 0 {
		output += "\nSTDERR:\n" + stderr.String()
	}

	if err != nil {
		return output, fmt.Errorf("test command failed: %w", err)
	}

	return output, nil
}

// executeReview runs code review tasks (delegates to Claude)
func (e *Executor) executeReview(ctx context.Context, workflow *Workflow, task *Task) (string, error) {
	if task.Agent != AgentTypeClaude && task.Agent != AgentTypeGemini {
		return "", fmt.Errorf("review tasks require Claude or Gemini agent")
	}

	// Placeholder: will be implemented in Component 5
	return fmt.Sprintf("Review task: %s (to be implemented in Agent Bridge)", task.Command), nil
}

// executeRefactor runs refactoring tasks (delegates to Claude or Gemini)
func (e *Executor) executeRefactor(ctx context.Context, workflow *Workflow, task *Task) (string, error) {
	if task.Agent != AgentTypeClaude && task.Agent != AgentTypeGemini {
		return "", fmt.Errorf("refactor tasks require Claude or Gemini agent")
	}

	// Placeholder: will be implemented in Component 5
	return fmt.Sprintf("Refactor task: %s (to be implemented in Agent Bridge)", task.Command), nil
}

// Placeholder implementations for agent tasks (will be replaced in Component 5)

func (e *Executor) executeClaude(ctx context.Context, task *Task) (string, error) {
	// Placeholder: In Component 5, this will call Claude Code CLI
	return fmt.Sprintf("Claude task executed: %s\nOutput: Placeholder (Claude Code integration pending)", task.Command), nil
}

func (e *Executor) executeGemini(ctx context.Context, task *Task) (string, error) {
	// Placeholder: In Component 5, this will call Gemini API
	return fmt.Sprintf("Gemini task executed: %s\nOutput: Placeholder (Gemini integration pending)", task.Command), nil
}

// Helper to expand command string with workflow variables
func (e *Executor) expandCommand(cmd string, variables map[string]interface{}) string {
	expanded := cmd
	for k, v := range variables {
		placeholder := fmt.Sprintf("${%s}", k)
		expanded = strings.ReplaceAll(expanded, placeholder, fmt.Sprintf("%v", v))
	}
	return expanded
}
