// Package claude_confirm provides Claude interaction permission and auto-approval pattern management
package claude_confirm

import (
	"time"

	"github.com/google/uuid"
)

// PermissionType represents the type of permission being requested
type PermissionType string

const (
	PermissionRead    PermissionType = "read"
	PermissionWrite   PermissionType = "write"
	PermissionExecute PermissionType = "execute"
	PermissionDelete  PermissionType = "delete"
	PermissionNetwork PermissionType = "network"
)

// ResourceType represents the type of resource being accessed
type ResourceType string

const (
	ResourceFile       ResourceType = "file"
	ResourceDirectory  ResourceType = "directory"
	ResourceDatabase   ResourceType = "database"
	ResourceCommand    ResourceType = "command"
	ResourceAPI        ResourceType = "api"
	ResourceFilesystem ResourceType = "filesystem"
)

// DecisionType represents the type of decision made
type DecisionType string

const (
	DecisionApprove DecisionType = "approve"
	DecisionDeny    DecisionType = "deny"
	DecisionDefer   DecisionType = "defer"
)

// ConfirmationRequest represents a permission request from Claude Code
type ConfirmationRequest struct {
	ID            uuid.UUID      `gorm:"primaryKey" json:"id"`
	SessionID     string         `json:"session_id"`
	PermissionType PermissionType `json:"permission_type"`
	ResourceType  ResourceType   `json:"resource_type"`
	ResourcePath  string         `json:"resource_path"`
	Context       string         `json:"context"`        // Description of what Claude is trying to do
	Timestamp     time.Time      `json:"timestamp"`
	Decision      DecisionType   `json:"decision"`
	DecisionReason string        `json:"decision_reason"` // Why it was approved/denied
	ApprovedAt    *time.Time     `json:"approved_at"`
	ApprovedBy    string         `json:"approved_by"`   // "pattern", "ai_agent", "user"
	PatternID     *uuid.UUID     `json:"pattern_id"`    // Which pattern matched (if any)
}

// TableName sets the table name for GORM
func (ConfirmationRequest) TableName() string {
	return "claude_confirmations"
}

// ApprovalPattern represents a learned pattern for auto-approval
type ApprovalPattern struct {
	ID              uuid.UUID     `gorm:"primaryKey" json:"id"`
	Name            string        `json:"name"` // User-friendly name for the pattern
	Description     string        `json:"description"`
	PermissionType  PermissionType `json:"permission_type"`
	ResourceType    ResourceType   `json:"resource_type"`
	PathPattern     string        `json:"path_pattern"` // Glob pattern (e.g., /data/*, ~/projects/*)
	ContextKeywords []string      `gorm:"serializer:json" json:"context_keywords"` // Keywords that trigger this pattern
	Enabled         bool          `json:"enabled"`
	DecisionType    DecisionType  `json:"decision_type"`   // approve or deny
	Confidence      float64       `json:"confidence"`      // 0.0-1.0: how confident we are in this pattern
	SuccessCount    int           `json:"success_count"`   // How many times this pattern led to correct decisions
	FailureCount    int           `json:"failure_count"`   // How many times this pattern was wrong
	LastUsed        *time.Time    `json:"last_used"`
	CreatedAt       time.Time     `json:"created_at"`
	UpdatedAt       time.Time     `json:"updated_at"`
}

// TableName sets the table name for GORM
func (ApprovalPattern) TableName() string {
	return "approval_patterns"
}

// AIAgentDecision represents a decision made by the AI agent fallback
type AIAgentDecision struct {
	ID                uuid.UUID           `gorm:"primaryKey" json:"id"`
	ConfirmationID    uuid.UUID           `json:"confirmation_id"`
	Decision          DecisionType        `json:"decision"`
	Confidence        float64             `json:"confidence"`       // 0.0-1.0
	Reasoning         string              `json:"reasoning"`        // Why the AI made this decision
	MatchedPatterns   []uuid.UUID         `gorm:"serializer:json" json:"matched_patterns"`
	TokensUsed        int                 `json:"tokens_used"`
	CostUSD           float64             `json:"cost_usd"`
	ResponseTime      int                 `json:"response_time_ms"`
	Model             string              `json:"model"`            // Which Claude model was used
	CreatedAt         time.Time           `json:"created_at"`
	UpdatedAt         time.Time           `json:"updated_at"`
}

// TableName sets the table name for GORM
func (AIAgentDecision) TableName() string {
	return "ai_agent_decisions"
}

// SessionApprovalPreference represents user preferences for a specific session
type SessionApprovalPreference struct {
	ID           uuid.UUID  `gorm:"primaryKey" json:"id"`
	SessionID    string     `json:"session_id"`
	SessionName  string     `json:"session_name"` // e.g., "basic_edu", "rando_inspector"
	AllowAll     bool       `json:"allow_all"`    // Allow all operations without confirmation
	PatternIDs   []uuid.UUID `gorm:"serializer:json" json:"pattern_ids"` // Specific patterns to apply
	UseAIFallback bool      `json:"use_ai_fallback"`                    // Use AI agent for unmatched requests
	CreatedAt    time.Time  `json:"created_at"`
	UpdatedAt    time.Time  `json:"updated_at"`
}

// TableName sets the table name for GORM
func (SessionApprovalPreference) TableName() string {
	return "session_approval_preferences"
}

// ApprovalStats tracks pattern performance
type ApprovalStats struct {
	TotalRequests       int
	ApprovedByPattern   int
	ApprovedByAI        int
	ApprovedByUser      int
	Denied              int
	PatternAccuracy     float64 // % of pattern decisions that were correct
	AIAccuracy          float64 // % of AI decisions that were correct
	AverageResponseTime int     // milliseconds
}
