package manager

import (
	"fmt"
	"regexp"
	"strings"
	"time"
)

// AgentState represents the current state of an agent
type AgentState string

const (
	StateIdle      AgentState = "idle"
	StateThinking  AgentState = "thinking"
	StateWorking   AgentState = "working"
	StateExecuting AgentState = "executing"
	StateBlocked   AgentState = "blocked"
	StateError     AgentState = "error"
	StateCompleted AgentState = "completed"
)

// SemanticData represents extracted semantic information from logs
type SemanticData struct {
	Timestamp       time.Time
	AgentState      AgentState
	CurrentTask     *SemanticTask
	TaskList        []SemanticTask
	Errors          []ErrorInfo
	CompletedItems  []CompletedItem
	BlockedItems    []BlockedItem
	WorkContext     map[string]interface{}
}

// SemanticTask represents a task being worked on
type SemanticTask struct {
	ID          string
	Description string
	Status      string // pending, in_progress, completed, failed
	StartedAt   *time.Time
	CompletedAt *time.Time
	Errors      []ErrorInfo
}

// ErrorInfo represents an error encountered
type ErrorInfo struct {
	Message     string
	Source      string
	LineNumber  int
	Timestamp   time.Time
	Severity    string // low, medium, high, critical
	TaskID      string
	StackTrace  string
	Recoverable bool
}

// CompletedItem represents a completed work item
type CompletedItem struct {
	Description string
	Duration    time.Duration
	Timestamp   time.Time
	Success     bool
	Output      string
}

// BlockedItem represents something that's blocked
type BlockedItem struct {
	Description    string
	Reason         string
	Timestamp      time.Time
	RequiresAction string
	Severity       string
}

// SemanticExtractor extracts high-level semantic information from logs
type SemanticExtractor struct {
	patterns map[string]*regexp.Regexp
	state    *SemanticData
}

// NewSemanticExtractor creates a new semantic extractor
func NewSemanticExtractor() *SemanticExtractor {
	se := &SemanticExtractor{
		patterns: make(map[string]*regexp.Regexp),
		state: &SemanticData{
			TaskList:       make([]SemanticTask, 0),
			Errors:         make([]ErrorInfo, 0),
			CompletedItems: make([]CompletedItem, 0),
			BlockedItems:   make([]BlockedItem, 0),
			WorkContext:    make(map[string]interface{}),
		},
	}

	se.initPatterns()
	return se
}

// initPatterns initializes extraction patterns
func (se *SemanticExtractor) initPatterns() {
	se.patterns["idle_prompt"] = regexp.MustCompile(`(?i)(Type your message|❯\s*$|>\s*$)`)
	se.patterns["thinking"] = regexp.MustCompile(`(?i)(thinking|processing|analyzing|considering|✢.+…)`)
	se.patterns["working"] = regexp.MustCompile(`(?i)(working on|processing|building|compiling|running)`)
	se.patterns["executing"] = regexp.MustCompile(`⏺\s+(\w+)\(`)

	// Task patterns
	se.patterns["task_started"] = regexp.MustCompile(`(?i)(starting|beginning|working on).*task:?\s*(.+)`)
	se.patterns["task_description"] = regexp.MustCompile(`(?i)task:?\s*(.+)`)
	se.patterns["task_id"] = regexp.MustCompile(`(?i)task[_-]?(\w+)`)

	// Error patterns
	se.patterns["error"] = regexp.MustCompile(`(?i)(error|exception|failed|failure)[::\s]+(.+)`)
	se.patterns["exit_code"] = regexp.MustCompile(`(?i)exit code\s+(\d+)`)
	se.patterns["stack_trace"] = regexp.MustCompile(`^\s+at\s+|^\s+File\s+"`)
	se.patterns["warning"] = regexp.MustCompile(`(?i)warning[::\s]+(.+)`)

	// Completion patterns
	se.patterns["completed"] = regexp.MustCompile(`(?i)(✓|✔|completed|done|finished|success)`)
	se.patterns["duration"] = regexp.MustCompile(`(?i)(for|in)\s+(\d+[hms]+\s*\d*[ms]*)`)
	se.patterns["baked"] = regexp.MustCompile(`✻\s+(\w+)\s+for\s+(.+)`)

	// Blocked patterns
	se.patterns["blocked"] = regexp.MustCompile(`(?i)(blocked|stuck|waiting|cannot proceed|need to)`)
	se.patterns["requires"] = regexp.MustCompile(`(?i)requires?\s+(.+)`)
	se.patterns["approach_change"] = regexp.MustCompile(`(?i)(try different|alternative|change approach|need to rethink)`)

	// Context patterns
	se.patterns["file_operation"] = regexp.MustCompile(`(?i)(reading|writing|editing|creating|deleting)\s+(.+\.\w+)`)
	se.patterns["command"] = regexp.MustCompile(`⏺\s+Bash\((.+)\)`)
}

// ProcessLine processes a single log line and updates semantic state
func (se *SemanticExtractor) ProcessLine(line string, lineNumber int) {
	se.state.Timestamp = time.Now()

	// Detect agent state
	se.updateAgentState(line)

	// Extract task information
	se.extractTaskInfo(line, lineNumber)

	// Extract errors
	se.extractErrors(line, lineNumber)

	// Extract completions
	se.extractCompletions(line, lineNumber)

	// Extract blockers
	se.extractBlockers(line, lineNumber)

	// Update work context
	se.updateWorkContext(line)
}

// updateAgentState determines current agent state
func (se *SemanticExtractor) updateAgentState(line string) {
	if se.patterns["idle_prompt"].MatchString(line) {
		se.state.AgentState = StateIdle
	} else if se.patterns["thinking"].MatchString(line) {
		se.state.AgentState = StateThinking
	} else if se.patterns["executing"].MatchString(line) {
		se.state.AgentState = StateExecuting
	} else if se.patterns["error"].MatchString(line) {
		se.state.AgentState = StateError
	} else if se.patterns["blocked"].MatchString(line) {
		se.state.AgentState = StateBlocked
	} else if se.patterns["completed"].MatchString(line) {
		se.state.AgentState = StateCompleted
	} else if se.patterns["working"].MatchString(line) {
		se.state.AgentState = StateWorking
	}
}

// extractTaskInfo extracts task-related information
func (se *SemanticExtractor) extractTaskInfo(line string, lineNumber int) {
	// Task started
	if match := se.patterns["task_started"].FindStringSubmatch(line); match != nil {
		taskDesc := strings.TrimSpace(match[2])
		now := time.Now()

		task := SemanticTask{
			ID:          fmt.Sprintf("task_%d", time.Now().Unix()),
			Description: taskDesc,
			Status:      "in_progress",
			StartedAt:   &now,
			Errors:      make([]ErrorInfo, 0),
		}

		se.state.CurrentTask = &task
		se.state.TaskList = append(se.state.TaskList, task)
	}

	// Task ID mentioned
	if match := se.patterns["task_id"].FindStringSubmatch(line); match != nil && se.state.CurrentTask != nil {
		se.state.CurrentTask.ID = match[1]
	}
}

// extractErrors extracts error information
func (se *SemanticExtractor) extractErrors(line string, lineNumber int) {
	// General error
	if match := se.patterns["error"].FindStringSubmatch(line); match != nil {
		severity := "medium"
		if strings.Contains(strings.ToLower(match[2]), "critical") || strings.Contains(strings.ToLower(match[2]), "fatal") {
			severity = "critical"
		}

		errorInfo := ErrorInfo{
			Message:     strings.TrimSpace(match[2]),
			LineNumber:  lineNumber,
			Timestamp:   time.Now(),
			Severity:    severity,
			Recoverable: !strings.Contains(strings.ToLower(line), "fatal"),
		}

		if se.state.CurrentTask != nil {
			errorInfo.TaskID = se.state.CurrentTask.ID
			se.state.CurrentTask.Errors = append(se.state.CurrentTask.Errors, errorInfo)
		}

		se.state.Errors = append(se.state.Errors, errorInfo)
	}

	// Exit code error
	if match := se.patterns["exit_code"].FindStringSubmatch(line); match != nil {
		errorInfo := ErrorInfo{
			Message:     fmt.Sprintf("Exit code %s", match[1]),
			Source:      "command_execution",
			LineNumber:  lineNumber,
			Timestamp:   time.Now(),
			Severity:    "high",
			Recoverable: match[1] != "137" && match[1] != "139", // Not killed or segfault
		}

		if se.state.CurrentTask != nil {
			errorInfo.TaskID = se.state.CurrentTask.ID
			se.state.CurrentTask.Errors = append(se.state.CurrentTask.Errors, errorInfo)
		}

		se.state.Errors = append(se.state.Errors, errorInfo)
	}

	// Warning
	if match := se.patterns["warning"].FindStringSubmatch(line); match != nil {
		errorInfo := ErrorInfo{
			Message:     strings.TrimSpace(match[1]),
			LineNumber:  lineNumber,
			Timestamp:   time.Now(),
			Severity:    "low",
			Recoverable: true,
		}

		se.state.Errors = append(se.state.Errors, errorInfo)
	}
}

// extractCompletions extracts completion information
func (se *SemanticExtractor) extractCompletions(line string, lineNumber int) {
	if se.patterns["completed"].MatchString(line) {
		item := CompletedItem{
			Description: line,
			Timestamp:   time.Now(),
			Success:     true,
		}

		// Extract duration if present
		if match := se.patterns["duration"].FindStringSubmatch(line); match != nil {
			// Parse duration (simplified)
			item.Output = fmt.Sprintf("Completed in %s", match[2])
		}

		// Extract from "baked" pattern
		if match := se.patterns["baked"].FindStringSubmatch(line); match != nil {
			item.Description = match[1]
			item.Output = match[2]
		}

		se.state.CompletedItems = append(se.state.CompletedItems, item)

		// Mark current task as completed
		if se.state.CurrentTask != nil {
			se.state.CurrentTask.Status = "completed"
			now := time.Now()
			se.state.CurrentTask.CompletedAt = &now
			se.state.CurrentTask = nil // Clear current task
		}
	}
}

// extractBlockers extracts blocked/stuck situations
func (se *SemanticExtractor) extractBlockers(line string, lineNumber int) {
	if se.patterns["blocked"].MatchString(line) {
		blocked := BlockedItem{
			Description: line,
			Timestamp:   time.Now(),
			Severity:    "medium",
		}

		// Extract what's required
		if match := se.patterns["requires"].FindStringSubmatch(line); match != nil {
			blocked.Reason = fmt.Sprintf("Requires: %s", strings.TrimSpace(match[1]))
			blocked.RequiresAction = strings.TrimSpace(match[1])
		}

		// Check if approach change is needed
		if se.patterns["approach_change"].MatchString(line) {
			blocked.Severity = "high"
			blocked.RequiresAction = "Change of approach needed"
		}

		se.state.BlockedItems = append(se.state.BlockedItems, blocked)

		// Mark current task as blocked
		if se.state.CurrentTask != nil {
			se.state.CurrentTask.Status = "blocked"
		}
	}
}

// updateWorkContext updates the work context with current activity
func (se *SemanticExtractor) updateWorkContext(line string) {
	// File operations
	if match := se.patterns["file_operation"].FindStringSubmatch(line); match != nil {
		se.state.WorkContext["current_operation"] = match[1]
		se.state.WorkContext["current_file"] = match[2]
	}

	// Command execution
	if match := se.patterns["command"].FindStringSubmatch(line); match != nil {
		se.state.WorkContext["current_command"] = match[1]
	}
}

// GetState returns the current semantic state
func (se *SemanticExtractor) GetState() *SemanticData {
	return se.state
}

// Summary generates a human-readable summary
func (sd *SemanticData) Summary() string {
	summary := "=== Agent Semantic Analysis ===\n\n"

	summary += fmt.Sprintf("Current State: %s\n", sd.AgentState)

	if sd.CurrentTask != nil {
		summary += fmt.Sprintf("Current Task: %s (Status: %s)\n", sd.CurrentTask.Description, sd.CurrentTask.Status)
	} else {
		summary += "Current Task: None\n"
	}

	summary += fmt.Sprintf("\nTask List: %d total\n", len(sd.TaskList))
	for i, task := range sd.TaskList {
		if i >= 5 {
			summary += fmt.Sprintf("  ... and %d more\n", len(sd.TaskList)-5)
			break
		}
		status := task.Status
		if len(task.Errors) > 0 {
			status += fmt.Sprintf(" (%d errors)", len(task.Errors))
		}
		summary += fmt.Sprintf("  %d. %s [%s]\n", i+1, truncate(task.Description, 60), status)
	}

	summary += fmt.Sprintf("\nErrors: %d total\n", len(sd.Errors))
	for i, err := range sd.Errors {
		if i >= 5 {
			summary += fmt.Sprintf("  ... and %d more\n", len(sd.Errors)-5)
			break
		}
		summary += fmt.Sprintf("  Line %d: [%s] %s\n", err.LineNumber, err.Severity, truncate(err.Message, 60))
	}

	summary += fmt.Sprintf("\nCompleted Items: %d\n", len(sd.CompletedItems))
	for i, item := range sd.CompletedItems {
		if i >= 5 {
			summary += fmt.Sprintf("  ... and %d more\n", len(sd.CompletedItems)-5)
			break
		}
		summary += fmt.Sprintf("  ✓ %s\n", truncate(item.Description, 70))
	}

	if len(sd.BlockedItems) > 0 {
		summary += fmt.Sprintf("\n⚠ Blocked Items: %d\n", len(sd.BlockedItems))
		for i, blocked := range sd.BlockedItems {
			if i >= 5 {
				summary += fmt.Sprintf("  ... and %d more\n", len(sd.BlockedItems)-5)
				break
			}
			summary += fmt.Sprintf("  %s: %s\n", blocked.RequiresAction, truncate(blocked.Description, 60))
		}
	}

	if len(sd.WorkContext) > 0 {
		summary += "\nWork Context:\n"
		for key, value := range sd.WorkContext {
			summary += fmt.Sprintf("  %s: %v\n", key, value)
		}
	}

	return summary
}
