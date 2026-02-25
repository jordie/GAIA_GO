package stream

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// TrainingEvent represents a single event for training auto-confirmation systems
type TrainingEvent struct {
	EventID      string                 `json:"event_id"`
	Timestamp    time.Time              `json:"timestamp"`
	EventType    string                 `json:"event_type"` // tool_use, decision, permission, state_change
	AgentName    string                 `json:"agent_name"`
	SessionID    string                 `json:"session_id"`

	// Tool usage information
	ToolName     string                 `json:"tool_name,omitempty"`
	ToolParams   map[string]interface{} `json:"tool_params,omitempty"`
	ToolResult   string                 `json:"tool_result,omitempty"`
	ToolSuccess  bool                   `json:"tool_success"`
	ToolDuration time.Duration          `json:"tool_duration,omitempty"`

	// Decision information
	DecisionType string                 `json:"decision_type,omitempty"` // approach, tool_choice, parameter
	Options      []string               `json:"options,omitempty"`       // Available options
	ChosenOption string                 `json:"chosen_option,omitempty"` // What was chosen
	Reasoning    string                 `json:"reasoning,omitempty"`     // Why it was chosen

	// Permission/Confirmation information
	PermissionType   string            `json:"permission_type,omitempty"` // bash, edit, write, etc.
	PermissionPrompt string            `json:"permission_prompt,omitempty"`
	PermissionGiven  bool              `json:"permission_given"`
	AutoConfirmable  bool              `json:"auto_confirmable"` // Could this be auto-confirmed?
	RiskLevel        string            `json:"risk_level,omitempty"` // low, medium, high

	// Context information
	TaskDescription string                 `json:"task_description,omitempty"`
	PriorActions    []string               `json:"prior_actions,omitempty"`
	CurrentState    string                 `json:"current_state,omitempty"`
	FilesInContext  []string               `json:"files_in_context,omitempty"`

	// Outcome information
	Success      bool                   `json:"success"`
	ErrorMessage string                 `json:"error_message,omitempty"`
	OutputSummary string                `json:"output_summary,omitempty"`

	// Metadata for training
	Metadata     map[string]interface{} `json:"metadata,omitempty"`
	Labels       []string               `json:"labels,omitempty"` // For classification
}

// ToolSequence tracks a sequence of tool uses for pattern analysis
type ToolSequence struct {
	SequenceID  string                 `json:"sequence_id"`
	StartTime   time.Time              `json:"start_time"`
	EndTime     time.Time              `json:"end_time"`
	AgentName   string                 `json:"agent_name"`
	Tools       []ToolUse              `json:"tools"`
	TaskGoal    string                 `json:"task_goal"`
	Success     bool                   `json:"success"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

// ToolUse represents a single tool invocation
type ToolUse struct {
	ToolName    string                 `json:"tool_name"`
	Timestamp   time.Time              `json:"timestamp"`
	Parameters  map[string]interface{} `json:"parameters"`
	Result      string                 `json:"result,omitempty"`
	Success     bool                   `json:"success"`
	Duration    time.Duration          `json:"duration"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

// DecisionPoint captures an agent's decision-making moment
type DecisionPoint struct {
	DecisionID   string                 `json:"decision_id"`
	Timestamp    time.Time              `json:"timestamp"`
	Context      string                 `json:"context"`
	DecisionType string                 `json:"decision_type"`
	Options      []DecisionOption       `json:"options"`
	Chosen       string                 `json:"chosen"`
	Reasoning    string                 `json:"reasoning"`
	Outcome      string                 `json:"outcome"`
	Metadata     map[string]interface{} `json:"metadata,omitempty"`
}

// DecisionOption represents one possible choice at a decision point
type DecisionOption struct {
	ID          string                 `json:"id"`
	Description string                 `json:"description"`
	Pros        []string               `json:"pros,omitempty"`
	Cons        []string               `json:"cons,omitempty"`
	RiskLevel   string                 `json:"risk_level"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

// TrainingLogger handles structured logging for ML training
type TrainingLogger struct {
	agentName     string
	sessionID     string
	outputDir     string
	eventsFile    *os.File
	sequencesFile *os.File
	decisionsFile *os.File
	mu            sync.Mutex

	// In-memory tracking
	currentSequence *ToolSequence
	eventCount      int
	sequenceCount   int
	decisionCount   int
}

// NewTrainingLogger creates a new training data logger
func NewTrainingLogger(agentName, sessionID, outputDir string) (*TrainingLogger, error) {
	// Create training data directory structure
	trainingDir := filepath.Join(outputDir, "training_data", agentName)
	if err := os.MkdirAll(trainingDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create training dir: %w", err)
	}

	// Create timestamped files for this session
	timestamp := time.Now().Format("2006-01-02-15-04-05")

	eventsPath := filepath.Join(trainingDir, fmt.Sprintf("%s-events.jsonl", timestamp))
	eventsFile, err := os.Create(eventsPath)
	if err != nil {
		return nil, fmt.Errorf("failed to create events file: %w", err)
	}

	sequencesPath := filepath.Join(trainingDir, fmt.Sprintf("%s-sequences.jsonl", timestamp))
	sequencesFile, err := os.Create(sequencesPath)
	if err != nil {
		eventsFile.Close()
		return nil, fmt.Errorf("failed to create sequences file: %w", err)
	}

	decisionsPath := filepath.Join(trainingDir, fmt.Sprintf("%s-decisions.jsonl", timestamp))
	decisionsFile, err := os.Create(decisionsPath)
	if err != nil {
		eventsFile.Close()
		sequencesFile.Close()
		return nil, fmt.Errorf("failed to create decisions file: %w", err)
	}

	fmt.Printf("[Training] Logging to: %s\n", trainingDir)

	return &TrainingLogger{
		agentName:     agentName,
		sessionID:     sessionID,
		outputDir:     outputDir,
		eventsFile:    eventsFile,
		sequencesFile: sequencesFile,
		decisionsFile: decisionsFile,
	}, nil
}

// LogEvent logs a training event
func (tl *TrainingLogger) LogEvent(event *TrainingEvent) error {
	tl.mu.Lock()
	defer tl.mu.Unlock()

	// Set metadata
	event.EventID = fmt.Sprintf("%s-%d", tl.sessionID, tl.eventCount)
	event.AgentName = tl.agentName
	event.SessionID = tl.sessionID
	event.Timestamp = time.Now()

	tl.eventCount++

	// Write as JSON line
	data, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	if _, err := fmt.Fprintf(tl.eventsFile, "%s\n", data); err != nil {
		return fmt.Errorf("failed to write event: %w", err)
	}

	return nil
}

// StartToolSequence begins tracking a sequence of tool uses
func (tl *TrainingLogger) StartToolSequence(taskGoal string) string {
	tl.mu.Lock()
	defer tl.mu.Unlock()

	sequenceID := fmt.Sprintf("%s-seq-%d", tl.sessionID, tl.sequenceCount)
	tl.sequenceCount++

	tl.currentSequence = &ToolSequence{
		SequenceID: sequenceID,
		StartTime:  time.Now(),
		AgentName:  tl.agentName,
		TaskGoal:   taskGoal,
		Tools:      make([]ToolUse, 0),
		Metadata:   make(map[string]interface{}),
	}

	return sequenceID
}

// LogToolUse adds a tool use to the current sequence
func (tl *TrainingLogger) LogToolUse(tool ToolUse) error {
	tl.mu.Lock()
	defer tl.mu.Unlock()

	if tl.currentSequence == nil {
		tl.StartToolSequence("unknown")
	}

	tool.Timestamp = time.Now()
	tl.currentSequence.Tools = append(tl.currentSequence.Tools, tool)

	// Also log as an event
	event := &TrainingEvent{
		EventType:    "tool_use",
		ToolName:     tool.ToolName,
		ToolParams:   tool.Parameters,
		ToolResult:   tool.Result,
		ToolSuccess:  tool.Success,
		ToolDuration: tool.Duration,
		Success:      tool.Success,
	}

	return tl.LogEvent(event)
}

// EndToolSequence completes and logs the current tool sequence
func (tl *TrainingLogger) EndToolSequence(success bool) error {
	tl.mu.Lock()
	defer tl.mu.Unlock()

	if tl.currentSequence == nil {
		return nil
	}

	tl.currentSequence.EndTime = time.Now()
	tl.currentSequence.Success = success

	// Write sequence as JSON line
	data, err := json.Marshal(tl.currentSequence)
	if err != nil {
		return fmt.Errorf("failed to marshal sequence: %w", err)
	}

	if _, err := fmt.Fprintf(tl.sequencesFile, "%s\n", data); err != nil {
		return fmt.Errorf("failed to write sequence: %w", err)
	}

	tl.currentSequence = nil
	return nil
}

// LogDecision logs an agent decision point
func (tl *TrainingLogger) LogDecision(decision *DecisionPoint) error {
	tl.mu.Lock()
	defer tl.mu.Unlock()

	decision.DecisionID = fmt.Sprintf("%s-dec-%d", tl.sessionID, tl.decisionCount)
	decision.Timestamp = time.Now()
	tl.decisionCount++

	// Write decision as JSON line
	data, err := json.Marshal(decision)
	if err != nil {
		return fmt.Errorf("failed to marshal decision: %w", err)
	}

	if _, err := fmt.Fprintf(tl.decisionsFile, "%s\n", data); err != nil {
		return fmt.Errorf("failed to write decision: %w", err)
	}

	// Also log as an event
	event := &TrainingEvent{
		EventType:    "decision",
		DecisionType: decision.DecisionType,
		ChosenOption: decision.Chosen,
		Reasoning:    decision.Reasoning,
		Metadata: map[string]interface{}{
			"options": decision.Options,
			"context": decision.Context,
		},
	}

	return tl.LogEvent(event)
}

// Close flushes and closes all log files
func (tl *TrainingLogger) Close() error {
	tl.mu.Lock()
	defer tl.mu.Unlock()

	// End any active sequence
	if tl.currentSequence != nil {
		tl.currentSequence.EndTime = time.Now()
		data, _ := json.Marshal(tl.currentSequence)
		fmt.Fprintf(tl.sequencesFile, "%s\n", data)
	}

	// Close files
	tl.eventsFile.Close()
	tl.sequencesFile.Close()
	tl.decisionsFile.Close()

	return nil
}

// GetStats returns statistics about logged training data
func (tl *TrainingLogger) GetStats() map[string]interface{} {
	tl.mu.Lock()
	defer tl.mu.Unlock()

	return map[string]interface{}{
		"session_id":      tl.sessionID,
		"agent_name":      tl.agentName,
		"events_logged":   tl.eventCount,
		"sequences_logged": tl.sequenceCount,
		"decisions_logged": tl.decisionCount,
		"active_sequence": tl.currentSequence != nil,
	}
}
