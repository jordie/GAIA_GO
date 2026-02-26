package claude_confirm

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"
	"gorm.io/gorm"
)

// ConfirmationService handles permission confirmation requests with pattern matching and AI fallback
type ConfirmationService struct {
	db              *gorm.DB
	patternMatcher  *PatternMatcher
	aiAgent         *AIAgent
	sessionPrefs    map[string]*SessionApprovalPreference // Cached session preferences
}

// NewConfirmationService creates a new confirmation service
func NewConfirmationService(db *gorm.DB, aiAgent *AIAgent) *ConfirmationService {
	return &ConfirmationService{
		db:             db,
		patternMatcher: NewPatternMatcher(db),
		aiAgent:        aiAgent,
		sessionPrefs:   make(map[string]*SessionApprovalPreference),
	}
}

// ProcessConfirmation handles a confirmation request
// Returns the decision and whether it was approved
func (cs *ConfirmationService) ProcessConfirmation(ctx context.Context, req *ConfirmationRequest) (DecisionType, string, error) {
	req.ID = uuid.New()
	req.Timestamp = time.Now()

	// Get session preferences
	prefs, err := cs.getSessionPreferences(ctx, req.SessionID)
	if err != nil {
		return DecisionDeny, "Failed to load session preferences", err
	}

	// Check if session has "allow all" enabled
	if prefs != nil && prefs.AllowAll {
		req.Decision = DecisionApprove
		req.ApprovedBy = "session_preference"
		req.ApprovedAt = timePtr(time.Now())
		cs.db.Create(req)
		return DecisionApprove, "Approved by session allow-all preference", nil
	}

	// Step 1: Try to match against learned patterns
	matchResult, err := cs.patternMatcher.Match(ctx, req)
	if err != nil {
		return DecisionDeny, "Pattern matching error", err
	}

	if matchResult != nil && matchResult.Score >= 0.7 { // High confidence threshold for pattern
		req.Decision = matchResult.Decision
		req.PatternID = &matchResult.Pattern.ID
		req.ApprovedBy = "pattern"
		req.DecisionReason = fmt.Sprintf("Pattern '%s' matched with %.1f%% confidence", matchResult.Pattern.Name, matchResult.Score*100)
		req.ApprovedAt = timePtr(time.Now())
		cs.db.Create(req)

		// Record pattern usage
		if err := cs.patternMatcher.RecordPatternUse(ctx, matchResult.Pattern.ID.String(), matchResult.Decision == DecisionApprove); err != nil {
			fmt.Printf("Warning: failed to record pattern use: %v\n", err)
		}

		return matchResult.Decision, req.DecisionReason, nil
	}

	// Step 2: Use AI agent for unmatched or low-confidence requests
	if cs.aiAgent != nil && cs.aiAgent.config.Enabled && (prefs == nil || prefs.UseAIFallback) {
		var matchedPatterns []*PatternMatchResult
		if matchResult != nil {
			matchedPatterns = append(matchedPatterns, matchResult)
		}

		aiDecision, err := cs.aiAgent.MakeDecision(ctx, req, matchedPatterns)
		if err != nil {
			// If AI fails, deny by default
			req.Decision = DecisionDeny
			req.ApprovedBy = "default_deny"
			req.DecisionReason = fmt.Sprintf("AI agent error: %v", err)
		} else {
			req.Decision = aiDecision.Decision
			req.ApprovedBy = "ai_agent"
			req.DecisionReason = aiDecision.Reasoning
		}
		req.ApprovedAt = timePtr(time.Now())
		cs.db.Create(req)

		return req.Decision, req.DecisionReason, nil
	}

	// Step 3: Default deny if no pattern matched and no AI agent
	req.Decision = DecisionDeny
	req.ApprovedBy = "default_deny"
	req.DecisionReason = "No matching pattern and AI agent disabled"
	req.ApprovedAt = timePtr(time.Now())
	cs.db.Create(req)

	return DecisionDeny, "No pattern matched and AI fallback not available", nil
}

// CreatePattern creates a new approval pattern
func (cs *ConfirmationService) CreatePattern(ctx context.Context, pattern *ApprovalPattern) error {
	pattern.ID = uuid.New()
	pattern.CreatedAt = time.Now()
	pattern.UpdatedAt = time.Now()
	return cs.db.Create(pattern).Error
}

// UpdatePattern updates an existing pattern
func (cs *ConfirmationService) UpdatePattern(ctx context.Context, patternID string, updates map[string]interface{}) error {
	return cs.db.Model(&ApprovalPattern{}).
		Where("id = ?", patternID).
		Updates(updates).Error
}

// GetPattern retrieves a pattern by ID
func (cs *ConfirmationService) GetPattern(ctx context.Context, patternID string) (*ApprovalPattern, error) {
	var pattern ApprovalPattern
	err := cs.db.First(&pattern, "id = ?", patternID).Error
	if err == gorm.ErrRecordNotFound {
		return nil, nil
	}
	return &pattern, err
}

// ListPatterns returns all approval patterns
func (cs *ConfirmationService) ListPatterns(ctx context.Context, enabled *bool, limit int) ([]ApprovalPattern, error) {
	var patterns []ApprovalPattern
	query := cs.db

	if enabled != nil {
		query = query.Where("enabled = ?", *enabled)
	}

	err := query.
		Order("success_count DESC, confidence DESC").
		Limit(limit).
		Find(&patterns).Error

	return patterns, err
}

// DeletePattern deletes a pattern
func (cs *ConfirmationService) DeletePattern(ctx context.Context, patternID string) error {
	return cs.db.Delete(&ApprovalPattern{}, "id = ?", patternID).Error
}

// GetConfirmationHistory returns past confirmation decisions
func (cs *ConfirmationService) GetConfirmationHistory(ctx context.Context, sessionID string, limit int) ([]ConfirmationRequest, error) {
	var confirmations []ConfirmationRequest
	err := cs.db.
		Where("session_id = ?", sessionID).
		Order("timestamp DESC").
		Limit(limit).
		Find(&confirmations).Error
	return confirmations, err
}

// GetSessionStats returns statistics for a session
func (cs *ConfirmationService) GetSessionStats(ctx context.Context, sessionID string) (*ApprovalStats, error) {
	var confirmations []ConfirmationRequest
	if err := cs.db.Where("session_id = ?", sessionID).Find(&confirmations).Error; err != nil {
		return nil, err
	}

	stats := &ApprovalStats{
		TotalRequests: len(confirmations),
	}

	totalTime := 0

	for _, c := range confirmations {
		switch c.ApprovedBy {
		case "pattern":
			stats.ApprovedByPattern++
		case "ai_agent":
			stats.ApprovedByAI++
		case "user":
			stats.ApprovedByUser++
		}

		if c.Decision == DecisionDeny {
			stats.Denied++
		}

		if c.ApprovedAt != nil {
			totalTime += int(c.ApprovedAt.Sub(c.Timestamp).Milliseconds())
		}
	}

	if stats.TotalRequests > 0 {
		stats.AverageResponseTime = totalTime / stats.TotalRequests
	}

	return stats, nil
}

// SetSessionPreference updates approval preferences for a session
func (cs *ConfirmationService) SetSessionPreference(ctx context.Context, pref *SessionApprovalPreference) error {
	pref.UpdatedAt = time.Now()

	// Update cache
	cs.sessionPrefs[pref.SessionID] = pref

	// Check if preference exists
	var existing SessionApprovalPreference
	result := cs.db.Where("session_id = ?", pref.SessionID).First(&existing)

	if result.Error == gorm.ErrRecordNotFound {
		// Create new
		pref.ID = uuid.New()
		pref.CreatedAt = time.Now()
		return cs.db.Create(pref).Error
	}

	// Update existing
	return cs.db.Model(&existing).Updates(pref).Error
}

// GetSessionPreference retrieves approval preferences for a session
func (cs *ConfirmationService) GetSessionPreference(ctx context.Context, sessionID string) (*SessionApprovalPreference, error) {
	return cs.getSessionPreferences(ctx, sessionID)
}

// getSessionPreferences retrieves with caching
func (cs *ConfirmationService) getSessionPreferences(ctx context.Context, sessionID string) (*SessionApprovalPreference, error) {
	// Check cache first
	if pref, ok := cs.sessionPrefs[sessionID]; ok {
		return pref, nil
	}

	// Load from database
	var pref SessionApprovalPreference
	result := cs.db.Where("session_id = ?", sessionID).First(&pref)

	if result.Error == gorm.ErrRecordNotFound {
		return nil, nil // No preference set (not an error)
	}

	if result.Error != nil {
		return nil, result.Error
	}

	// Cache it
	cs.sessionPrefs[sessionID] = &pref
	return &pref, nil
}

// GetGlobalStats returns statistics about the entire confirmation system
func (cs *ConfirmationService) GetGlobalStats(ctx context.Context) (map[string]interface{}, error) {
	var totalConfirmations int64
	var approvedCount int64
	var deniedCount int64

	cs.db.Model(&ConfirmationRequest{}).Count(&totalConfirmations)
	cs.db.Model(&ConfirmationRequest{}).Where("decision = ?", DecisionApprove).Count(&approvedCount)
	cs.db.Model(&ConfirmationRequest{}).Where("decision = ?", DecisionDeny).Count(&deniedCount)

	// Get pattern performance
	var patterns []ApprovalPattern
	cs.db.Find(&patterns)

	bestPatterns := cs.patternMatcher.GetTopPatterns(ctx, 5)

	aiStats, _ := cs.aiAgent.GetAgentStats(ctx)

	return map[string]interface{}{
		"total_confirmations":  totalConfirmations,
		"approved":             approvedCount,
		"denied":               deniedCount,
		"approval_rate":        float64(approvedCount) / float64(totalConfirmations) * 100,
		"total_patterns":       len(patterns),
		"top_patterns":         bestPatterns,
		"ai_agent_stats":       aiStats,
		"timestamp":            time.Now(),
	}, nil
}

// Helper function to create time pointers
func timePtr(t time.Time) *time.Time {
	return &t
}
