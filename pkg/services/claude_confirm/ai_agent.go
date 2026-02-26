package claude_confirm

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
	"gorm.io/gorm"
)

// AIAgentConfig holds configuration for the AI agent
type AIAgentConfig struct {
	Model           string  // e.g., "claude-opus-4.5"
	MaxTokens       int
	DecisionTimeout time.Duration
	CostPerMillion  float64 // Cost per million tokens
	Enabled         bool
}

// AIAgent provides AI-based decision making for unmatched confirmation requests
type AIAgent struct {
	db     *gorm.DB
	config AIAgentConfig
	// In real implementation, would have anthropic.Client here
}

// NewAIAgent creates a new AI agent
func NewAIAgent(db *gorm.DB, config AIAgentConfig) *AIAgent {
	return &AIAgent{
		db:     db,
		config: config,
	}
}

// AIDecisionRequest represents the data sent to Claude for a decision
type AIDecisionRequest struct {
	PermissionType string `json:"permission_type"`
	ResourceType   string `json:"resource_type"`
	ResourcePath   string `json:"resource_path"`
	Context        string `json:"context"`
	SessionID      string `json:"session_id"`
	MatchedPatterns []PatternSummary `json:"matched_patterns"`
}

// PatternSummary is a brief summary of matched patterns
type PatternSummary struct {
	Name       string  `json:"name"`
	Confidence float64 `json:"confidence"`
	Decision   string  `json:"decision"`
}

// AIDecisionResponse represents Claude's response
type AIDecisionResponse struct {
	Decision   DecisionType `json:"decision"`    // "approve" or "deny"
	Confidence float64      `json:"confidence"`  // 0.0-1.0
	Reasoning  string       `json:"reasoning"`   // Why this decision was made
	Patterns   []uuid.UUID  `json:"patterns"`    // Which patterns support this decision
	Risk       string       `json:"risk"`        // "low", "medium", "high"
}

// MakeDecision uses the AI agent to make a decision on a confirmation request
func (aa *AIAgent) MakeDecision(ctx context.Context, req *ConfirmationRequest, matchedPatterns []*PatternMatchResult) (*AIAgentDecision, error) {
	if !aa.config.Enabled {
		return nil, fmt.Errorf("AI agent is disabled")
	}

	startTime := time.Now()

	// Build the prompt for Claude
	prompt := aa.buildPrompt(req, matchedPatterns)

	// Call Claude API (in real implementation)
	// response, usage, err := aa.callClaudeAPI(ctx, prompt)

	// For now, use a mock implementation
	response := aa.mockClaudeDecision(req, matchedPatterns)

	// Record the decision
	decision := &AIAgentDecision{
		ID:             uuid.New(),
		ConfirmationID: req.ID,
		Decision:       response.Decision,
		Confidence:     response.Confidence,
		Reasoning:      response.Reasoning,
		MatchedPatterns: response.Patterns,
		ResponseTime:   int(time.Since(startTime).Milliseconds()),
		Model:          aa.config.Model,
		CreatedAt:      time.Now(),
		UpdatedAt:      time.Now(),
	}

	// Save to database
	if err := aa.db.Create(decision).Error; err != nil {
		return nil, fmt.Errorf("failed to save AI decision: %w", err)
	}

	return decision, nil
}

// buildPrompt creates a detailed prompt for Claude to make a decision
func (aa *AIAgent) buildPrompt(req *ConfirmationRequest, matchedPatterns []*PatternMatchResult) string {
	var prompt strings.Builder

	prompt.WriteString("You are a security decision AI for Claude Code. ")
	prompt.WriteString("A Claude Code session is requesting permission to perform an operation. ")
	prompt.WriteString("Based on the context and matched patterns, decide whether to approve or deny.\n\n")

	// Request details
	prompt.WriteString("REQUEST DETAILS:\n")
	prompt.WriteString(fmt.Sprintf("- Permission Type: %s\n", req.PermissionType))
	prompt.WriteString(fmt.Sprintf("- Resource Type: %s\n", req.ResourceType))
	prompt.WriteString(fmt.Sprintf("- Resource Path: %s\n", req.ResourcePath))
	prompt.WriteString(fmt.Sprintf("- Context: %s\n", req.Context))
	prompt.WriteString(fmt.Sprintf("- Session: %s\n\n", req.SessionID))

	// Matched patterns
	if len(matchedPatterns) > 0 {
		prompt.WriteString("MATCHED PATTERNS:\n")
		for _, match := range matchedPatterns {
			prompt.WriteString(fmt.Sprintf("- %s (confidence: %.1f%%)\n", match.Pattern.Name, match.Score*100))
			prompt.WriteString(fmt.Sprintf("  Decision: %s\n", match.Decision))
			prompt.WriteString(fmt.Sprintf("  Reasons: %s\n", strings.Join(match.Reasons, "; ")))
		}
		prompt.WriteString("\n")
	}

	// Decision guidelines
	prompt.WriteString("DECISION GUIDELINES:\n")
	prompt.WriteString("1. Approve if the operation is safe and expected (e.g., reading project files)\n")
	prompt.WriteString("2. Deny if the operation could be harmful (e.g., deleting system files, network access to unknown services)\n")
	prompt.WriteString("3. Consider the session's known purpose and previous patterns\n")
	prompt.WriteString("4. Be conservative with network operations and system-level changes\n")
	prompt.WriteString("5. Allow read operations more readily than write or delete operations\n\n")

	prompt.WriteString("Respond with JSON only, no markdown:\n")
	prompt.WriteString(`{"decision":"approve|deny", "confidence":0.0-1.0, "reasoning":"...", "risk":"low|medium|high"}`)

	return prompt.String()
}

// mockClaudeDecision provides a mock decision (until real Claude API integration)
func (aa *AIAgent) mockClaudeDecision(req *ConfirmationRequest, matchedPatterns []*PatternMatchResult) *AIDecisionResponse {
	decision := &AIDecisionResponse{
		Confidence: 0.8,
		Risk:       "low",
	}

	// Simple heuristics for mock decisions
	switch req.PermissionType {
	case PermissionRead:
		// Generally safe to approve read operations
		decision.Decision = DecisionApprove
		decision.Confidence = 0.9
		decision.Reasoning = "Read operations are generally safe and allow Claude to understand project context"
		decision.Risk = "low"

	case PermissionWrite:
		// More cautious with write operations
		if strings.Contains(req.ResourcePath, "/data/") || strings.Contains(req.ResourcePath, "~/") {
			decision.Decision = DecisionApprove
			decision.Reasoning = "Writing to user project directories is typically acceptable"
			decision.Risk = "medium"
		} else {
			decision.Decision = DecisionDeny
			decision.Reasoning = "Write operations outside project directories are restricted"
			decision.Risk = "high"
			decision.Confidence = 0.95
		}

	case PermissionExecute:
		// Very cautious with execute operations
		if strings.Contains(req.Context, "test") || strings.Contains(req.Context, "build") {
			decision.Decision = DecisionApprove
			decision.Reasoning = "Test and build commands are typically safe"
			decision.Risk = "medium"
		} else {
			decision.Decision = DecisionDeny
			decision.Reasoning = "Execute operations are restricted unless explicitly for testing"
			decision.Risk = "high"
			decision.Confidence = 0.95
		}

	case PermissionDelete:
		// Very cautious with delete operations
		decision.Decision = DecisionDeny
		decision.Reasoning = "Delete operations require explicit user approval"
		decision.Risk = "high"
		decision.Confidence = 0.95

	case PermissionNetwork:
		// Restrict network operations
		decision.Decision = DecisionDeny
		decision.Reasoning = "Network operations are restricted to prevent data exfiltration"
		decision.Risk = "high"
		decision.Confidence = 0.95

	default:
		decision.Decision = DecisionDeny
		decision.Reasoning = "Unknown permission type"
		decision.Risk = "high"
	}

	// Consider matched patterns
	if len(matchedPatterns) > 0 {
		// If patterns suggest approval, boost confidence
		if matchedPatterns[0].Decision == DecisionApprove {
			decision.Confidence += 0.1
			if decision.Confidence > 1.0 {
				decision.Confidence = 1.0
			}
			decision.Reasoning = fmt.Sprintf("Pattern '%s' supports: %s", matchedPatterns[0].Pattern.Name, decision.Reasoning)
		}
	}

	return decision
}

// GetAgentStats returns statistics about AI agent performance
func (aa *AIAgent) GetAgentStats(ctx context.Context) (map[string]interface{}, error) {
	var decisions []AIAgentDecision
	if err := aa.db.Find(&decisions).Error; err != nil {
		return nil, err
	}

	approved := 0
	denied := 0
	avgConfidence := 0.0
	avgResponseTime := 0

	for _, d := range decisions {
		if d.Decision == DecisionApprove {
			approved++
		} else {
			denied++
		}
		avgConfidence += d.Confidence
		avgResponseTime += d.ResponseTime
	}

	total := len(decisions)
	if total > 0 {
		avgConfidence /= float64(total)
		avgResponseTime /= total
	}

	return map[string]interface{}{
		"total_decisions":      total,
		"approved":             approved,
		"denied":               denied,
		"approval_rate":        float64(approved) / float64(total) * 100,
		"avg_confidence":       avgConfidence,
		"avg_response_time_ms": avgResponseTime,
		"enabled":              aa.config.Enabled,
		"model":                aa.config.Model,
	}, nil
}

// callClaudeAPI would call the actual Claude API (implementation placeholder)
func (aa *AIAgent) callClaudeAPI(ctx context.Context, prompt string) (*AIDecisionResponse, map[string]interface{}, error) {
	// TODO: Implement actual Claude API call using anthropic SDK
	// This would:
	// 1. Create a message with the prompt
	// 2. Parse the JSON response
	// 3. Extract token usage for cost tracking
	// 4. Handle errors and timeouts
	return nil, nil, fmt.Errorf("not implemented: Claude API integration")
}

// DisableForSession disables AI agent for a specific session
func (aa *AIAgent) DisableForSession(ctx context.Context, sessionID string) error {
	return aa.db.Model(&SessionApprovalPreference{}).
		Where("session_id = ?", sessionID).
		Update("use_ai_fallback", false).Error
}

// EnableForSession enables AI agent for a specific session
func (aa *AIAgent) EnableForSession(ctx context.Context, sessionID string) error {
	return aa.db.Model(&SessionApprovalPreference{}).
		Where("session_id = ?", sessionID).
		Update("use_ai_fallback", true).Error
}
