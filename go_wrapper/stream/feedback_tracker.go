package stream

import (
	"encoding/json"
	"fmt"
	"os"
	"sync"
	"time"
)

// FeedbackOutcome represents the result of an agent operation
type FeedbackOutcome struct {
	ID          string                 `json:"id"`
	Timestamp   time.Time              `json:"timestamp"`
	AgentName   string                 `json:"agent_name"`
	Environment string                 `json:"environment"`
	TaskType    string                 `json:"task_type"` // tool_use, decision, operation
	Action      string                 `json:"action"`    // What was attempted
	Success     bool                   `json:"success"`
	Duration    time.Duration          `json:"duration"`
	ErrorMsg    string                 `json:"error_msg,omitempty"`
	Context     map[string]interface{} `json:"context,omitempty"`

	// Analysis fields
	Pattern     string                 `json:"pattern,omitempty"`      // Pattern that matched
	RiskLevel   string                 `json:"risk_level,omitempty"`   // low, medium, high
	WasBlocked  bool                   `json:"was_blocked"`            // Was operation blocked by constraints?
	BlockReason string                 `json:"block_reason,omitempty"` // Why it was blocked
}

// FeedbackStats aggregates feedback data for analysis
type FeedbackStats struct {
	TotalOutcomes    int                       `json:"total_outcomes"`
	SuccessRate      float64                   `json:"success_rate"`
	ByTaskType       map[string]int            `json:"by_task_type"`
	ByEnvironment    map[string]int            `json:"by_environment"`
	TopErrors        []ErrorFrequency          `json:"top_errors"`
	TopSuccesses     []SuccessPattern          `json:"top_successes"`
	BlockedOperations []string                 `json:"blocked_operations"`
}

// ErrorFrequency tracks how often errors occur
type ErrorFrequency struct {
	Error string `json:"error"`
	Count int    `json:"count"`
}

// SuccessPattern tracks successful operation patterns
type SuccessPattern struct {
	Pattern string  `json:"pattern"`
	Count   int     `json:"count"`
	AvgDuration time.Duration `json:"avg_duration"`
}

// FeedbackTracker collects and analyzes agent operation outcomes
type FeedbackTracker struct {
	agentName   string
	environment string
	outcomes    []FeedbackOutcome
	mu          sync.RWMutex
	logFile     *os.File
	outcomeCount int
}

// NewFeedbackTracker creates a new feedback tracker
func NewFeedbackTracker(agentName, environment, dataPath string) (*FeedbackTracker, error) {
	os.MkdirAll(dataPath, 0755)

	logPath := fmt.Sprintf("%s/%s-%s-feedback-%s.jsonl",
		dataPath,
		agentName,
		environment,
		time.Now().Format("2006-01-02-15-04-05"))

	logFile, err := os.Create(logPath)
	if err != nil {
		return nil, fmt.Errorf("failed to create feedback log: %w", err)
	}

	fmt.Printf("[Feedback] Tracking outcomes for %s in %s environment\n", agentName, environment)
	fmt.Printf("[Feedback] Log: %s\n", logPath)

	return &FeedbackTracker{
		agentName:   agentName,
		environment: environment,
		outcomes:    make([]FeedbackOutcome, 0, 1000),
		logFile:     logFile,
	}, nil
}

// RecordOutcome logs an operation outcome
func (ft *FeedbackTracker) RecordOutcome(outcome FeedbackOutcome) error {
	ft.mu.Lock()
	defer ft.mu.Unlock()

	// Set metadata
	outcome.ID = fmt.Sprintf("%s-%d", ft.agentName, ft.outcomeCount)
	outcome.Timestamp = time.Now()
	outcome.AgentName = ft.agentName
	outcome.Environment = ft.environment

	ft.outcomeCount++
	ft.outcomes = append(ft.outcomes, outcome)

	// Write to log file
	data, err := json.Marshal(outcome)
	if err != nil {
		return fmt.Errorf("failed to marshal outcome: %w", err)
	}

	if _, err := fmt.Fprintf(ft.logFile, "%s\n", data); err != nil {
		return fmt.Errorf("failed to write outcome: %w", err)
	}

	return nil
}

// RecordSuccess logs a successful operation
func (ft *FeedbackTracker) RecordSuccess(taskType, action, pattern string, duration time.Duration, context map[string]interface{}) error {
	return ft.RecordOutcome(FeedbackOutcome{
		TaskType: taskType,
		Action:   action,
		Success:  true,
		Duration: duration,
		Pattern:  pattern,
		Context:  context,
	})
}

// RecordFailure logs a failed operation
func (ft *FeedbackTracker) RecordFailure(taskType, action, errorMsg string, duration time.Duration, context map[string]interface{}) error {
	return ft.RecordOutcome(FeedbackOutcome{
		TaskType: taskType,
		Action:   action,
		Success:  false,
		Duration: duration,
		ErrorMsg: errorMsg,
		Context:  context,
	})
}

// RecordBlocked logs a blocked operation due to constraints
func (ft *FeedbackTracker) RecordBlocked(action, reason, riskLevel string) error {
	return ft.RecordOutcome(FeedbackOutcome{
		TaskType:    "constraint_check",
		Action:      action,
		Success:     false,
		WasBlocked:  true,
		BlockReason: reason,
		RiskLevel:   riskLevel,
	})
}

// GetStats returns aggregated statistics
func (ft *FeedbackTracker) GetStats() FeedbackStats {
	ft.mu.RLock()
	defer ft.mu.RUnlock()

	stats := FeedbackStats{
		TotalOutcomes: len(ft.outcomes),
		ByTaskType:    make(map[string]int),
		ByEnvironment: make(map[string]int),
	}

	successCount := 0
	errorCounts := make(map[string]int)
	patternCounts := make(map[string]int)
	patternDurations := make(map[string][]time.Duration)
	blocked := make([]string, 0)

	for _, outcome := range ft.outcomes {
		// Count by task type
		stats.ByTaskType[outcome.TaskType]++
		stats.ByEnvironment[outcome.Environment]++

		// Track success rate
		if outcome.Success {
			successCount++
			if outcome.Pattern != "" {
				patternCounts[outcome.Pattern]++
				patternDurations[outcome.Pattern] = append(patternDurations[outcome.Pattern], outcome.Duration)
			}
		} else {
			if outcome.ErrorMsg != "" {
				errorCounts[outcome.ErrorMsg]++
			}
		}

		// Track blocked operations
		if outcome.WasBlocked {
			blocked = append(blocked, fmt.Sprintf("%s: %s", outcome.Action, outcome.BlockReason))
		}
	}

	// Calculate success rate
	if len(ft.outcomes) > 0 {
		stats.SuccessRate = float64(successCount) / float64(len(ft.outcomes)) * 100
	}

	// Build top errors list
	stats.TopErrors = make([]ErrorFrequency, 0)
	for err, count := range errorCounts {
		stats.TopErrors = append(stats.TopErrors, ErrorFrequency{
			Error: err,
			Count: count,
		})
	}

	// Build top successes list
	stats.TopSuccesses = make([]SuccessPattern, 0)
	for pattern, count := range patternCounts {
		durations := patternDurations[pattern]
		var totalDuration time.Duration
		for _, d := range durations {
			totalDuration += d
		}
		avgDuration := totalDuration / time.Duration(len(durations))

		stats.TopSuccesses = append(stats.TopSuccesses, SuccessPattern{
			Pattern:     pattern,
			Count:       count,
			AvgDuration: avgDuration,
		})
	}

	stats.BlockedOperations = blocked

	return stats
}

// GetRecentOutcomes returns the most recent N outcomes
func (ft *FeedbackTracker) GetRecentOutcomes(n int) []FeedbackOutcome {
	ft.mu.RLock()
	defer ft.mu.RUnlock()

	if n <= 0 || n > len(ft.outcomes) {
		n = len(ft.outcomes)
	}

	start := len(ft.outcomes) - n
	if start < 0 {
		start = 0
	}

	return ft.outcomes[start:]
}

// GetSuccessfulOutcomes returns only successful outcomes
func (ft *FeedbackTracker) GetSuccessfulOutcomes() []FeedbackOutcome {
	ft.mu.RLock()
	defer ft.mu.RUnlock()

	successful := make([]FeedbackOutcome, 0)
	for _, outcome := range ft.outcomes {
		if outcome.Success {
			successful = append(successful, outcome)
		}
	}
	return successful
}

// GetFailedOutcomes returns only failed outcomes
func (ft *FeedbackTracker) GetFailedOutcomes() []FeedbackOutcome {
	ft.mu.RLock()
	defer ft.mu.RUnlock()

	failed := make([]FeedbackOutcome, 0)
	for _, outcome := range ft.outcomes {
		if !outcome.Success {
			failed = append(failed, outcome)
		}
	}
	return failed
}

// GenerateReport creates a summary report
func (ft *FeedbackTracker) GenerateReport() string {
	stats := ft.GetStats()

	report := fmt.Sprintf("=== Feedback Report for %s (%s) ===\n\n", ft.agentName, ft.environment)
	report += fmt.Sprintf("Total Outcomes: %d\n", stats.TotalOutcomes)
	report += fmt.Sprintf("Success Rate: %.2f%%\n\n", stats.SuccessRate)

	report += "By Task Type:\n"
	for taskType, count := range stats.ByTaskType {
		report += fmt.Sprintf("  %s: %d\n", taskType, count)
	}
	report += "\n"

	if len(stats.TopSuccesses) > 0 {
		report += "Top Successful Patterns:\n"
		for _, success := range stats.TopSuccesses {
			report += fmt.Sprintf("  %s: %d times (avg: %v)\n",
				success.Pattern, success.Count, success.AvgDuration)
		}
		report += "\n"
	}

	if len(stats.TopErrors) > 0 {
		report += "Top Errors:\n"
		for _, err := range stats.TopErrors {
			report += fmt.Sprintf("  %s: %d times\n", err.Error, err.Count)
		}
		report += "\n"
	}

	if len(stats.BlockedOperations) > 0 {
		report += "Blocked Operations:\n"
		for _, blocked := range stats.BlockedOperations {
			report += fmt.Sprintf("  %s\n", blocked)
		}
	}

	return report
}

// Close flushes and closes the log file
func (ft *FeedbackTracker) Close() error {
	ft.mu.Lock()
	defer ft.mu.Unlock()

	if ft.logFile != nil {
		return ft.logFile.Close()
	}
	return nil
}
