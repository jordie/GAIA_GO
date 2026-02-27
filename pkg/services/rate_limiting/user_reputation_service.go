package rate_limiting

import (
	"context"
	"fmt"
	"time"

	"gorm.io/gorm"
)

// UserReputationView represents the user-facing view of reputation
type UserReputationView struct {
	UserID              int       `json:"user_id"`
	Score               float64   `json:"score"`
	Tier                string    `json:"tier"`
	Multiplier          float64   `json:"multiplier"`
	NextTierScore       float64   `json:"next_tier_score"`
	NextTierDistance    float64   `json:"next_tier_distance"`
	TierProgress        float64   `json:"tier_progress"` // 0-1, progress to next tier
	LastUpdated         time.Time `json:"last_updated"`
	DaysToDecay         int       `json:"days_to_decay"` // Days until next decay
	VIPStatus           *VIPInfo  `json:"vip_status"`
	RateLimitInfo       *RateLimitInfo `json:"rate_limit_info"`
	RecentViolations    []ViolationSummary `json:"recent_violations"`
	RecentCleanRequests int       `json:"recent_clean_requests"`
}

// VIPInfo represents VIP tier information for user
type VIPInfo struct {
	Tier          string     `json:"tier"`
	Active        bool       `json:"active"`
	ExpiresAt     *time.Time `json:"expires_at"`
	DaysRemaining *int       `json:"days_remaining"`
	Multiplier    float64    `json:"multiplier"`
}

// RateLimitInfo represents current rate limit information
type RateLimitInfo struct {
	BaseLimit         int     `json:"base_limit"`
	ReputationMultiplier float64 `json:"reputation_multiplier"`
	ThrottleMultiplier   float64 `json:"throttle_multiplier"`
	FinalLimit        int     `json:"final_limit"`
	CurrentUsage      int     `json:"current_usage"`
	UsagePercent      float64 `json:"usage_percent"`
	TimeWindowSeconds int     `json:"time_window_seconds"`
}

// ViolationSummary represents a summary of a violation
type ViolationSummary struct {
	ID            int       `json:"id"`
	Timestamp     time.Time `json:"timestamp"`
	Severity      int       `json:"severity"`
	SeverityLabel string    `json:"severity_label"`
	ReasonCode    string    `json:"reason_code"`
	ResourceType  string    `json:"resource_type"`
	Description   string    `json:"description"`
	ReputationLost float64  `json:"reputation_lost"`
	CanAppeal      bool      `json:"can_appeal"`
}

// TierExplanation explains reputation tiers and what they mean
type TierExplanation struct {
	Tier              string  `json:"tier"`
	ScoreRange        string  `json:"score_range"`
	Multiplier        float64 `json:"multiplier"`
	Description       string  `json:"description"`
	Benefits          []string `json:"benefits"`
	Requirements      []string `json:"requirements"`
	ViolationPenalty  int     `json:"violation_penalty"`
}

// UserReputationService provides user-facing reputation data
type UserReputationService struct {
	db                 *gorm.DB
	reputationManager  *ReputationManager
	throttler          *AutoThrottler
	anomaly            *AnomalyDetector
	explanationCache   map[string]*TierExplanation
}

// NewUserReputationService creates a new user reputation service
func NewUserReputationService(db *gorm.DB, rm *ReputationManager, at *AutoThrottler, ad *AnomalyDetector) *UserReputationService {
	urs := &UserReputationService{
		db:                db,
		reputationManager: rm,
		throttler:        at,
		anomaly:          ad,
		explanationCache: make(map[string]*TierExplanation),
	}

	// Pre-populate tier explanations
	urs.initializeTierExplanations()

	return urs
}

// initializeTierExplanations sets up tier information for users
func (urs *UserReputationService) initializeTierExplanations() {
	urs.explanationCache["flagged"] = &TierExplanation{
		Tier:       "flagged",
		ScoreRange: "0-20",
		Multiplier: 0.5,
		Description: "Your account has been flagged due to repeated violations. Rate limits are severely reduced.",
		Benefits: []string{},
		Requirements: []string{
			"Stop violating rate limits",
			"Wait for reputation to improve",
			"Maintain clean requests for 7 days",
		},
		ViolationPenalty: 9,
	}

	urs.explanationCache["standard"] = &TierExplanation{
		Tier:       "standard",
		ScoreRange: "20-80",
		Multiplier: 1.0,
		Description: "Default tier for all users. Standard rate limits apply.",
		Benefits: []string{
			"Normal rate limits",
			"Access to all endpoints",
			"Reputation decay protection",
		},
		Requirements: []string{
			"Maintain reputation between 20-80",
			"Don't cause multiple violations",
		},
		ViolationPenalty: 6,
	}

	urs.explanationCache["trusted"] = &TierExplanation{
		Tier:       "trusted",
		ScoreRange: "80-100",
		Multiplier: 1.5,
		Description: "Trusted tier for reliable users. Rate limits are 50% higher.",
		Benefits: []string{
			"50% higher rate limits (1.5x)",
			"Priority processing",
			"Expanded access",
		},
		Requirements: []string{
			"Maintain reputation above 80",
			"Demonstrate consistent good behavior",
			"No violations in last 30 days",
		},
		ViolationPenalty: 3,
	}

	urs.explanationCache["premium_vip"] = &TierExplanation{
		Tier:       "premium_vip",
		ScoreRange: "80-100 + VIP",
		Multiplier: 2.0,
		Description: "VIP tier with maximum privileges. Rate limits doubled.",
		Benefits: []string{
			"2x rate limits (2.0x)",
			"Priority queue",
			"Dedicated support",
			"Custom configurations",
		},
		Requirements: []string{
			"Active VIP subscription",
			"Reputation above 80",
			"No unresolved violations",
		},
		ViolationPenalty: 3,
	}
}

// GetUserReputationView returns complete reputation information for a user
func (urs *UserReputationService) GetUserReputationView(ctx context.Context, userID int) (*UserReputationView, error) {
	// Get reputation data
	rep, err := urs.reputationManager.GetUserReputation(userID)
	if err != nil {
		return nil, fmt.Errorf("failed to get reputation: %w", err)
	}

	// Get VIP status
	vipStatus := urs.getVIPStatus(userID)

	// Calculate multiplier
	multiplier := getAdaptiveMultiplier(rep.Score)

	// Calculate tier progress
	_, nextScore := urs.getNextTier(rep.Tier, float64(rep.Score))
	progress := 0.0
	repScoreFloat := float64(rep.Score)
	if nextScore > 0 {
		progress = repScoreFloat / nextScore
		if progress > 1.0 {
			progress = 1.0
		}
	}

	// Get rate limit info
	rateLimitInfo := urs.getRateLimitInfo(userID, multiplier)

	// Get recent violations
	violations := urs.getRecentViolations(userID, 10)

	// Count recent clean requests
	cleanCount := urs.countCleanRequests(userID, 24*time.Hour)

	// Get days until next decay
	daysToDecay := 7 - (int(time.Now().Weekday()))
	if daysToDecay <= 0 {
		daysToDecay += 7
	}

	return &UserReputationView{
		UserID:              userID,
		Score:               repScoreFloat,
		Tier:                rep.Tier,
		Multiplier:          multiplier,
		NextTierScore:       nextScore,
		NextTierDistance:    nextScore - repScoreFloat,
		TierProgress:        progress,
		LastUpdated:         time.Now(),
		DaysToDecay:         daysToDecay,
		VIPStatus:           vipStatus,
		RateLimitInfo:       rateLimitInfo,
		RecentViolations:    violations,
		RecentCleanRequests: cleanCount,
	}, nil
}

// getVIPStatus returns VIP information for a user
func (urs *UserReputationService) getVIPStatus(userID int) *VIPInfo {
	var vip struct {
		Tier      string
		ExpiresAt *time.Time
	}

	if err := urs.db.Table("vip_assignments").
		Select("tier, expires_at").
		Where("user_id = ? AND expires_at > ?", userID, time.Now()).
		First(&vip).Error; err != nil {
		return nil
	}

	daysRemaining := 0
	if vip.ExpiresAt != nil {
		daysRemaining = int(time.Until(*vip.ExpiresAt).Hours() / 24)
	}

	var multiplier float64 = 1.5
	if vip.Tier == "premium" {
		multiplier = 2.0
	}

	return &VIPInfo{
		Tier:          vip.Tier,
		Active:        vip.ExpiresAt != nil && vip.ExpiresAt.After(time.Now()),
		ExpiresAt:     vip.ExpiresAt,
		DaysRemaining: &daysRemaining,
		Multiplier:    multiplier,
	}
}

// getNextTier determines next tier and its score requirement
func (urs *UserReputationService) getNextTier(currentTier string, currentScore float64) (string, float64) {
	switch currentTier {
	case "flagged":
		return "standard", 20.0
	case "standard":
		return "trusted", 80.0
	case "trusted":
		return "premium_vip", 100.0
	default:
		return currentTier, currentScore
	}
}

// getRateLimitInfo calculates current rate limit information
func (urs *UserReputationService) getRateLimitInfo(userID int, repMultiplier float64) *RateLimitInfo {
	baseLimit := 1000 // Base limit per minute
	throttleMultiplier := urs.throttler.GetThrottleMultiplier()

	finalLimit := int(float64(baseLimit) * repMultiplier * throttleMultiplier)

	// Get current usage (simplified - in production would track actual usage)
	var currentUsage int64
	urs.db.Table("rate_limit_buckets").
		Where("scope = ? AND scope_value = ? AND window_end > ?",
			"user", fmt.Sprintf("%d", userID), time.Now().Add(-1*time.Minute)).
		Select("SUM(request_count)").
		Scan(&currentUsage)

	usagePercent := 0.0
	if finalLimit > 0 {
		usagePercent = float64(currentUsage) / float64(finalLimit)
	}

	return &RateLimitInfo{
		BaseLimit:            baseLimit,
		ReputationMultiplier: repMultiplier,
		ThrottleMultiplier:   throttleMultiplier,
		FinalLimit:           finalLimit,
		CurrentUsage:         int(currentUsage),
		UsagePercent:         usagePercent,
		TimeWindowSeconds:    60,
	}
}

// getRecentViolations returns recent violations for a user
func (urs *UserReputationService) getRecentViolations(userID int, limit int) []ViolationSummary {
	var events []ReputationEvent
	urs.db.Where("user_id = ? AND event_type = ?", userID, "violation").
		Order("timestamp DESC").
		Limit(limit).
		Find(&events)

	summaries := make([]ViolationSummary, 0, len(events))
	for _, event := range events {
		sevLabel := "minor"
		if event.Severity == 2 {
			sevLabel = "moderate"
		} else if event.Severity == 3 {
			sevLabel = "severe"
		}

		// Check if can appeal (within 30 days)
		canAppeal := time.Since(event.Timestamp) < 30*24*time.Hour

		summaries = append(summaries, ViolationSummary{
			ID:            event.ID,
			Timestamp:     event.Timestamp,
			Severity:      event.Severity,
			SeverityLabel: sevLabel,
			ReasonCode:    event.ReasonCode,
			ResourceType:  event.EventType,
			Description:   event.ReasonCode,
			ReputationLost: -event.ScoreDelta,
			CanAppeal:     canAppeal,
		})
	}

	return summaries
}

// countCleanRequests counts successful requests in time window
func (urs *UserReputationService) countCleanRequests(userID int, window time.Duration) int {
	var count int64
	urs.db.Table("rate_limit_buckets").
		Where("scope = ? AND scope_value = ? AND window_end > ?",
			"user", fmt.Sprintf("%d", userID), time.Now().Add(-window)).
		Select("SUM(request_count)").
		Scan(&count)
	return int(count)
}

// GetTierExplanation returns explanation for a tier
func (urs *UserReputationService) GetTierExplanation(tier string) *TierExplanation {
	if exp, exists := urs.explanationCache[tier]; exists {
		return exp
	}
	return nil
}

// GetAllTierExplanations returns explanations for all tiers
func (urs *UserReputationService) GetAllTierExplanations() []*TierExplanation {
	tiers := []*TierExplanation{
		urs.explanationCache["flagged"],
		urs.explanationCache["standard"],
		urs.explanationCache["trusted"],
		urs.explanationCache["premium_vip"],
	}
	return tiers
}

// GetReputationFAQ returns frequently asked questions about reputation
func (urs *UserReputationService) GetReputationFAQ() []map[string]string {
	return []map[string]string{
		{
			"question": "What is my reputation score?",
			"answer":   "Your reputation score ranges from 0-100. Higher scores indicate more reliable behavior. Score above 80 qualifies you for the Trusted tier with 1.5x higher rate limits.",
		},
		{
			"question": "How can I improve my reputation?",
			"answer":   "Make clean requests within your rate limits. Each successful request adds to your reputation. Avoid violations which can result in 3-9 point deductions depending on severity.",
		},
		{
			"question": "How often does my reputation decay?",
			"answer":   "Reputation decays weekly on Monday mornings (UTC). The decay slowly brings your score towards the neutral point of 50. Flagged users (score < 20) decay faster to encourage improvement.",
		},
		{
			"question": "What happens if I violate rate limits?",
			"answer":   "Violations result in reputation loss (3-9 points depending on severity) and reduced rate limits. Repeated violations can result in being flagged, cutting your rate limit in half.",
		},
		{
			"question": "Can I appeal a violation?",
			"answer":   "Yes, you can appeal violations within 30 days of occurrence. Legitimate appeals may be reviewed and reversed by our support team.",
		},
		{
			"question": "What is the VIP tier?",
			"answer":   "VIP is a premium tier with 2x rate limits. It's granted through subscription and requires maintaining reputation above 80. VIP benefits expire after the subscription period.",
		},
		{
			"question": "Does system load affect my rate limit?",
			"answer":   "Yes, during high system load, rate limits are automatically reduced for all users (throttle multiplier < 1.0). This is temporary and returns to normal when load decreases.",
		},
		{
			"question": "How are rate limits calculated?",
			"answer":   "Final Limit = Base × Reputation Multiplier × Throttle Multiplier. For example: 1000 × 1.5 (trusted) × 0.6 (medium load) = 900 requests per minute.",
		},
	}
}

// GetReputationTrends returns reputation trend data
func (urs *UserReputationService) GetReputationTrends(ctx context.Context, userID int, days int) ([]map[string]interface{}, error) {
	var trends []map[string]interface{}

	// Get daily reputation snapshots (simplified - in production would have dedicated table)
	startDate := time.Now().AddDate(0, 0, -days)

	var events []ReputationEvent
	if err := urs.db.Where("user_id = ? AND created_at > ?", userID, startDate).
		Order("created_at ASC").
		Find(&events).Error; err != nil {
		return nil, err
	}

	// Group events by day and calculate daily scores
	dailyScores := make(map[string]float64)
	for _, event := range events {
		dateKey := event.CreatedAt.Format("2006-01-02")
		dailyScores[dateKey] += event.ScoreDelta
	}

	// Build trend data
	for i := 0; i < days; i++ {
		date := time.Now().AddDate(0, 0, -i)
		dateKey := date.Format("2006-01-02")

		trends = append(trends, map[string]interface{}{
			"date":   dateKey,
			"delta":  dailyScores[dateKey],
			"events": len(events), // Simplified - would count per day
		})
	}

	return trends, nil
}
