package claude_confirm

import (
	"context"
	"fmt"
	"path/filepath"
	"strings"

	"gorm.io/gorm"
)

// PatternMatchResult represents the result of pattern matching
type PatternMatchResult struct {
	Pattern    *ApprovalPattern
	Score      float64       // 0.0-1.0: confidence score
	Reasons    []string      // Why this pattern matched
	Decision   DecisionType
	Confidence float64
}

// PatternMatcher matches confirmation requests against learned patterns
type PatternMatcher struct {
	db *gorm.DB
}

// NewPatternMatcher creates a new pattern matcher
func NewPatternMatcher(db *gorm.DB) *PatternMatcher {
	return &PatternMatcher{
		db: db,
	}
}

// Match finds the best matching pattern for a confirmation request
func (pm *PatternMatcher) Match(ctx context.Context, req *ConfirmationRequest) (*PatternMatchResult, error) {
	// Get all enabled patterns
	var patterns []ApprovalPattern
	if err := pm.db.Where("enabled = ?", true).Find(&patterns).Error; err != nil {
		return nil, fmt.Errorf("failed to get patterns: %w", err)
	}

	if len(patterns) == 0 {
		return nil, nil // No patterns to match
	}

	var bestMatch *PatternMatchResult
	bestScore := 0.0

	// Score each pattern
	for i := range patterns {
		pattern := &patterns[i]
		score := pm.scorePattern(pattern, req)

		if score > bestScore && score >= 0.5 { // Minimum 50% confidence threshold
			bestScore = score
			bestMatch = &PatternMatchResult{
				Pattern:    pattern,
				Score:      score,
				Decision:   pattern.DecisionType,
				Confidence: pattern.Confidence * score, // Combine pattern confidence with match score
			}

			// Add reasoning
			bestMatch.Reasons = pm.getMatchReasons(pattern, req, score)
		}
	}

	return bestMatch, nil
}

// scorePattern calculates a match score (0.0-1.0) for a pattern
func (pm *PatternMatcher) scorePattern(pattern *ApprovalPattern, req *ConfirmationRequest) float64 {
	score := 0.0
	maxScore := 0.0

	// 1. Permission type match (40% weight)
	maxScore += 0.4
	if pattern.PermissionType == req.PermissionType {
		score += 0.4
	}

	// 2. Resource type match (30% weight)
	maxScore += 0.3
	if pattern.ResourceType == req.ResourceType {
		score += 0.3
	}

	// 3. Path pattern match (20% weight)
	maxScore += 0.2
	if pm.matchPath(pattern.PathPattern, req.ResourcePath) {
		score += 0.2
	}

	// 4. Context keyword match (10% weight)
	maxScore += 0.1
	if pm.matchContext(pattern.ContextKeywords, req.Context) {
		score += 0.1
	}

	// Normalize score
	if maxScore > 0 {
		return score / maxScore
	}
	return 0.0
}

// matchPath checks if a path matches a glob pattern
func (pm *PatternMatcher) matchPath(pattern, path string) bool {
	// Handle empty patterns (match all)
	if pattern == "" || pattern == "*" {
		return true
	}

	// Simple glob matching: *, ?, [abc], etc.
	matched, err := filepath.Match(pattern, path)
	if err != nil {
		return false
	}
	return matched
}

// matchContext checks if any context keywords appear in the request context
func (pm *PatternMatcher) matchContext(keywords []string, context string) bool {
	if len(keywords) == 0 {
		return true // No keywords means match all
	}

	contextLower := strings.ToLower(context)
	matchedCount := 0

	for _, keyword := range keywords {
		if strings.Contains(contextLower, strings.ToLower(keyword)) {
			matchedCount++
		}
	}

	// Require at least 50% of keywords to match
	threshold := (len(keywords) + 1) / 2
	return matchedCount >= threshold
}

// getMatchReasons provides human-readable reasons for a match
func (pm *PatternMatcher) getMatchReasons(pattern *ApprovalPattern, req *ConfirmationRequest, score float64) []string {
	var reasons []string

	reasons = append(reasons, fmt.Sprintf("Pattern: %s", pattern.Name))
	reasons = append(reasons, fmt.Sprintf("Match confidence: %.1f%%", score*100))

	if pattern.PermissionType == req.PermissionType {
		reasons = append(reasons, fmt.Sprintf("Permission type matches: %s", req.PermissionType))
	}

	if pattern.ResourceType == req.ResourceType {
		reasons = append(reasons, fmt.Sprintf("Resource type matches: %s", req.ResourceType))
	}

	if pm.matchPath(pattern.PathPattern, req.ResourcePath) {
		reasons = append(reasons, fmt.Sprintf("Path matches pattern: %s", pattern.PathPattern))
	}

	if pm.matchContext(pattern.ContextKeywords, req.Context) {
		reasons = append(reasons, "Context keywords matched")
	}

	// Add pattern history
	totalAttempts := pattern.SuccessCount + pattern.FailureCount
	if totalAttempts > 0 {
		accuracy := float64(pattern.SuccessCount) / float64(totalAttempts) * 100
		reasons = append(reasons, fmt.Sprintf("Pattern accuracy: %.1f%% (%d/%d)", accuracy, pattern.SuccessCount, totalAttempts))
	}

	return reasons
}

// RecordPatternUse updates pattern stats after a decision
func (pm *PatternMatcher) RecordPatternUse(ctx context.Context, patternID string, wasSuccessful bool) error {
	if wasSuccessful {
		return pm.db.Model(&ApprovalPattern{}).
			Where("id = ?", patternID).
			Updates(map[string]interface{}{
				"success_count": gorm.Expr("success_count + ?", 1),
				"last_used":     gorm.Expr("CURRENT_TIMESTAMP"),
			}).Error
	}

	return pm.db.Model(&ApprovalPattern{}).
		Where("id = ?", patternID).
		Updates(map[string]interface{}{
			"failure_count": gorm.Expr("failure_count + ?", 1),
			"last_used":     gorm.Expr("CURRENT_TIMESTAMP"),
		}).Error
}

// GetTopPatterns returns the most successful patterns
func (pm *PatternMatcher) GetTopPatterns(ctx context.Context, limit int) ([]ApprovalPattern, error) {
	var patterns []ApprovalPattern
	err := pm.db.
		Order("success_count DESC, confidence DESC").
		Limit(limit).
		Find(&patterns).Error
	return patterns, err
}

// GetPatternStats returns statistics about a pattern's performance
func (pm *PatternMatcher) GetPatternStats(ctx context.Context, patternID string) (map[string]interface{}, error) {
	var pattern ApprovalPattern
	if err := pm.db.First(&pattern, "id = ?", patternID).Error; err != nil {
		return nil, err
	}

	totalAttempts := pattern.SuccessCount + pattern.FailureCount
	var accuracy float64
	if totalAttempts > 0 {
		accuracy = float64(pattern.SuccessCount) / float64(totalAttempts)
	}

	return map[string]interface{}{
		"pattern_id":      pattern.ID,
		"name":            pattern.Name,
		"total_attempts":  totalAttempts,
		"success_count":   pattern.SuccessCount,
		"failure_count":   pattern.FailureCount,
		"accuracy":        accuracy,
		"confidence":      pattern.Confidence,
		"last_used":       pattern.LastUsed,
		"permission_type": pattern.PermissionType,
		"resource_type":   pattern.ResourceType,
	}, nil
}
