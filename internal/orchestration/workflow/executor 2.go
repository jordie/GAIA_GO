package workflow

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"
)

// Executor handles execution of individual workflow tasks
type Executor struct {
	workDir string
}

// NewExecutor creates a new task executor
func NewExecutor(workDir string) *Executor {
	return &Executor{
		workDir: workDir,
	}
}

// Execute runs a single task and returns its output
func (e *Executor) Execute(ctx context.Context, workflow *Workflow, task *Task) (string, error) {
	switch task.Type {
	case TaskTypeShell:
		return e.executeShell(ctx, task)
	case TaskTypeCode:
		return e.executeCode(ctx, workflow, task)
	case TaskTypeTest:
		return e.executeTest(ctx, task)
	case TaskTypeReview:
		return e.executeReview(ctx, workflow, task)
	case TaskTypeRefactor:
		return e.executeRefactor(ctx, workflow, task)
	default:
		return "", fmt.Errorf("unsupported task type: %s", task.Type)
	}
}

// executeShell runs a shell command task
func (e *Executor) executeShell(ctx context.Context, task *Task) (string, error) {
	workDir := task.WorkDir
	if workDir == "" {
		workDir = e.workDir
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
