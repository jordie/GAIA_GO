package rate_limiting

import (
	"context"
	"fmt"
	"math"
	"time"

	"gorm.io/datatypes"
	"gorm.io/gorm"
)

// PredictionType represents the type of ML prediction
type PredictionType string

const (
	PredictionTypeRecoveryTimeline   PredictionType = "recovery_timeline"
	PredictionTypeApprovalProbability PredictionType = "approval_probability"
	PredictionTypeLanguageQuality    PredictionType = "language_quality"
)

// Prediction represents an ML prediction record
type Prediction struct {
	ID               int64
	AppealID         *int
	UserID           int
	PredictionType   PredictionType
	PredictionValue  float64
	Confidence       float64 // 0.0-1.0
	SupportingFactors datatypes.JSONMap
	ModelVersion     string
	PredictedAt      time.Time
	ActualValue      *float64
	AccuracyCheckedAt *time.Time
	CreatedAt        time.Time
}

// RepuationRecoveryPrediction represents recovery timeline
type ReputationRecoveryPrediction struct {
	UserID              int     `json:"user_id"`
	CurrentScore        float64 `json:"current_score"`
	TargetScore         float64 `json:"target_score"`
	EstimatedDaysToTarget int    `json:"estimated_days_to_target"`
	WeeklyChangeRate    float64 `json:"weekly_change_rate"`
	ConfidenceLevel     float64 `json:"confidence_level"`
	RequiredActions     []string `json:"required_actions"`
}

// AppealProbability represents approval probability
type AppealProbability struct {
	AppealID          int     `json:"appeal_id"`
	ApprovalProbability float64 `json:"approval_probability"`
	DenialProbability  float64 `json:"denial_probability"`
	Confidence        float64 `json:"confidence"`
	KeyFactors        []string `json:"key_factors"`
	RecommendedStrategy string  `json:"recommended_strategy"`
}

// AutoAppealSuggestion represents auto-appeal recommendation
type AutoAppealSuggestion struct {
	UserID                 int
	ViolationID            int
	SuggestionReason       string
	Confidence             float64 // 0.0-1.0
	PredictedSuccessRate   float64
	SuggestedStrategy      string
	SupportingEvidence     []string
	SimilarSuccessCount    int
	GeneratedAt            time.Time
	UserAccepted           bool
	AppealCreatedFromSuggestion bool
	CreatedAt              time.Time
}

// MLPredictionService provides ML-based predictions
type MLPredictionService struct {
	db *gorm.DB
}

// NewMLPredictionService creates a new ML prediction service
func NewMLPredictionService(db *gorm.DB) *MLPredictionService {
	return &MLPredictionService{db: db}
}

// PredictReputationRecovery predicts recovery timeline for user
func (mps *MLPredictionService) PredictReputationRecovery(
	ctx context.Context,
	userID int,
) (*ReputationRecoveryPrediction, error) {
	// Get user's current score and trend
	var user struct {
		Score           float64
		Tier            string
		TrendDirection  string
		ProjectedScore  float64
	}

	mps.db.WithContext(ctx).
		Table("reputation_scores rs").
		Joins("LEFT JOIN user_analytics_summary uas ON rs.user_id = uas.user_id").
		Where("rs.user_id = ?", userID).
		Select("rs.score, rs.tier, uas.trend_direction, uas.projected_30day_score").
		Scan(&user)

	// Determine target score based on tier
	var targetScore float64
	switch user.Tier {
	case "flagged":
		targetScore = 20.0
	case "standard":
		targetScore = 80.0
	case "trusted":
		targetScore = 100.0
	default:
		targetScore = 50.0
	}

	// Calculate weekly change rate from trend
	var weeklyRate float64
	if user.TrendDirection == "improving" {
		weeklyRate = 2.5
	} else if user.TrendDirection == "declining" {
		weeklyRate = -2.0
	} else {
		weeklyRate = 0.5
	}

	// Estimate days to target
	var daysToTarget int
	if weeklyRate != 0 {
		weeksNeeded := (targetScore - user.Score) / weeklyRate
		daysToTarget = int(weeksNeeded * 7)
		if daysToTarget < 0 {
			daysToTarget = 0
		}
	} else {
		daysToTarget = 365 // 1 year if no change
	}

	// Determine confidence based on data points
	confidence := 0.7
	if user.ProjectedScore > 0 {
		confidence = 0.85
	}

	// Generate required actions
	actions := []string{
		"Maintain clean API usage without violations",
		"Monitor reputation trends regularly",
		"Review and comply with rate limiting policies",
	}

	if user.TrendDirection == "declining" {
		actions = append(actions, "Address recent violations immediately")
	}

	prediction := &ReputationRecoveryPrediction{
		UserID:              userID,
		CurrentScore:        user.Score,
		TargetScore:         targetScore,
		EstimatedDaysToTarget: daysToTarget,
		WeeklyChangeRate:    weeklyRate,
		ConfidenceLevel:     confidence,
		RequiredActions:     actions,
	}

	// Store prediction
	mps.storePrediction(
		ctx,
		nil,
		userID,
		PredictionTypeRecoveryTimeline,
		float64(daysToTarget),
		confidence,
		map[string]interface{}{
			"target_score": targetScore,
			"weekly_rate": weeklyRate,
			"trend": user.TrendDirection,
		},
	)

	return prediction, nil
}

// PredictAppealApprovalProbability predicts approval probability
func (mps *MLPredictionService) PredictAppealApprovalProbability(
	ctx context.Context,
	appealID int,
) (*AppealProbability, error) {
	// Get appeal details
	var appeal struct {
		ID          int
		UserID      int
		Reason      string
		CreatedAt   time.Time
	}

	mps.db.WithContext(ctx).
		Table("appeals").
		Where("id = ?", appealID).
		Scan(&appeal)

	// Get user's appeal history
	var userStats struct {
		TotalAppeals   int64
		SuccessfulAppeals int64
		AvgResolveTime float64
	}

	mps.db.WithContext(ctx).
		Table("appeals").
		Where("user_id = ?", appeal.UserID).
		Select(
			"COUNT(*) as total_appeals, "+
				"COUNT(CASE WHEN status = 'approved' THEN 1 END) as successful_appeals, "+
				"AVG(EXTRACT(DAY FROM (resolved_at - created_at))) as avg_resolve_time",
		).
		Scan(&userStats)

	// Calculate approval probability based on factors
	baseProbability := 0.5

	// Factor 1: Appeal reason - some reasons more likely to be approved
	reasonFactors := map[string]float64{
		"false_positive":  0.15,
		"system_error":    0.20,
		"legitimate_use":  0.10,
		"shared_account":  0.05,
		"learning_curve":  0.08,
		"burst_needed":    0.03,
		"other":          0.02,
	}

	if factor, exists := reasonFactors[appeal.Reason]; exists {
		baseProbability += factor
	}

	// Factor 2: User's historical success rate
	if userStats.TotalAppeals > 0 {
		successRate := float64(userStats.SuccessfulAppeals) / float64(userStats.TotalAppeals)
		baseProbability += (successRate * 0.2)
	}

	// Factor 3: Time since appeal - recent appeals might have better context
	daysSinceCreated := time.Since(appeal.CreatedAt).Hours() / 24
	if daysSinceCreated < 1 {
		baseProbability += 0.05
	} else if daysSinceCreated > 7 {
		baseProbability -= 0.05
	}

	// Cap at 0.0 - 1.0
	if baseProbability < 0.0 {
		baseProbability = 0.0
	} else if baseProbability > 1.0 {
		baseProbability = 1.0
	}

	denialProbability := 1.0 - baseProbability
	confidence := 0.75
	if userStats.TotalAppeals > 5 {
		confidence = 0.85
	}

	// Key factors affecting probability
	factors := []string{
		fmt.Sprintf("Appeal reason: %s", appeal.Reason),
		fmt.Sprintf("User success rate: %.1f%%", float64(userStats.SuccessfulAppeals)/float64(userStats.TotalAppeals)*100),
	}

	if denialProbability > baseProbability {
		factors = append(factors, "Historical data suggests denial is more likely")
	} else {
		factors = append(factors, "Historical data suggests approval is more likely")
	}

	// Recommend strategy
	strategy := "Provide detailed evidence and clear explanation for why the violation was incorrect"
	if baseProbability > 0.7 {
		strategy = "Strong case - emphasize factual evidence and compliance with policies"
	} else if baseProbability < 0.4 {
		strategy = "Difficult case - consider requesting mediation or negotiation"
	}

	probability := &AppealProbability{
		AppealID:            appealID,
		ApprovalProbability: baseProbability,
		DenialProbability:   denialProbability,
		Confidence:          confidence,
		KeyFactors:          factors,
		RecommendedStrategy: strategy,
	}

	// Store prediction
	mps.storePrediction(
		ctx,
		&appealID,
		appeal.UserID,
		PredictionTypeApprovalProbability,
		baseProbability,
		confidence,
		map[string]interface{}{
			"reason": appeal.Reason,
			"user_success_rate": float64(userStats.SuccessfulAppeals) / float64(userStats.TotalAppeals),
		},
	)

	return probability, nil
}

// SuggestAutoAppeal generates auto-appeal suggestions for user
func (mps *MLPredictionService) SuggestAutoAppeal(
	ctx context.Context,
	userID int,
) ([]AutoAppealSuggestion, error) {
	// Get user's recent violations
	var violations []struct {
		ID             int
		ViolationID    int
		CreatedAt      time.Time
		ReputationLost float64
	}

	mps.db.WithContext(ctx).
		Table("violations").
		Where("user_id = ? AND created_at > ?", userID, time.Now().AddDate(0, 0, -30)).
		Order("created_at DESC").
		Limit(5).
		Scan(&violations)

	suggestions := make([]AutoAppealSuggestion, 0)

	for _, v := range violations {
		// Check if already appealed
		var appealCount int64
		mps.db.WithContext(ctx).
			Table("appeals").
			Where("user_id = ? AND violation_id = ?", userID, v.ViolationID).
			Count(&appealCount)

		if appealCount > 0 {
			continue // Already appealed
		}

		// Get similar violations that had successful appeals
		var similarSuccesses int64
		mps.db.WithContext(ctx).
			Table("appeals a").
			Joins("LEFT JOIN violations v ON a.violation_id = v.id").
			Where("a.user_id != ? AND a.status = 'approved' AND v.error_type = ?", userID, v.ID).
			Count(&similarSuccesses)

		// Calculate confidence based on similar successes
		confidence := 0.5
		if similarSuccesses >= 5 {
			confidence = 0.85
		} else if similarSuccesses >= 3 {
			confidence = 0.75
		} else if similarSuccesses >= 1 {
			confidence = 0.65
		}

		if confidence < 0.60 {
			continue // Too low confidence
		}

		reason := "high_confidence_fp"
		if similarSuccesses > 0 {
			reason = "pattern_match"
		}

		strategy := "Emphasize legitimate use case and compliance efforts"
		if similarSuccesses > 5 {
			strategy = "Reference similar successful appeals and patterns"
		}

		suggestion := AutoAppealSuggestion{
			UserID:                userID,
			ViolationID:           v.ViolationID,
			SuggestionReason:      reason,
			Confidence:            confidence,
			PredictedSuccessRate:  confidence,
			SuggestedStrategy:     strategy,
			SupportingEvidence:    []string{"Similar violations have been successfully appealed"},
			SimilarSuccessCount:   int(similarSuccesses),
			GeneratedAt:           time.Now(),
			CreatedAt:             time.Now(),
		}

		suggestions = append(suggestions, suggestion)

		// Store in database
		mps.db.WithContext(ctx).
			Table("auto_appeal_suggestions").
			Create(&suggestion)
	}

	return suggestions, nil
}

// GetModelPerformance returns ML model performance metrics
func (mps *MLPredictionService) GetModelPerformance(
	ctx context.Context,
	predictionType PredictionType,
) (map[string]interface{}, error) {
	var stats struct {
		TotalPredictions int64
		VerifiedCount    int64
		AvgConfidence    float64
		AccuracyPercent  float64
	}

	mps.db.WithContext(ctx).
		Table("ml_predictions").
		Where("prediction_type = ? AND created_at > ?", predictionType, time.Now().AddDate(0, -3, 0)).
		Select(
			"COUNT(*) as total_predictions, "+
				"COUNT(CASE WHEN actual_value IS NOT NULL THEN 1 END) as verified_count, "+
				"AVG(confidence) as avg_confidence",
		).
		Scan(&stats)

	// Calculate accuracy
	if stats.VerifiedCount > 0 {
		var accurateCount int64
		mps.db.WithContext(ctx).
			Table("ml_predictions").
			Where("prediction_type = ? AND actual_value IS NOT NULL", predictionType).
			Where("ABS(prediction_value - actual_value) < 0.1").
			Count(&accurateCount)

		stats.AccuracyPercent = float64(accurateCount) / float64(stats.VerifiedCount) * 100
	}

	return map[string]interface{}{
		"prediction_type":    predictionType,
		"total_predictions":  stats.TotalPredictions,
		"verified_predictions": stats.VerifiedCount,
		"avg_confidence":     math.Round(stats.AvgConfidence*100) / 100,
		"accuracy_percent":   math.Round(stats.AccuracyPercent*100) / 100,
		"data_quality":       determineDataQuality(stats.VerifiedCount, stats.TotalPredictions),
	}, nil
}

// storePrediction stores a prediction in the database
func (mps *MLPredictionService) storePrediction(
	ctx context.Context,
	appealID *int,
	userID int,
	predictionType PredictionType,
	value float64,
	confidence float64,
	factors map[string]interface{},
) error {
	factorsJSON := datatypes.JSONMap{}
	if factors != nil {
		// Would convert factors to JSON in real implementation
	}

	prediction := Prediction{
		AppealID:          appealID,
		UserID:            userID,
		PredictionType:    predictionType,
		PredictionValue:   value,
		Confidence:        confidence,
		SupportingFactors: factorsJSON,
		ModelVersion:      "v1.0",
		PredictedAt:       time.Now(),
		CreatedAt:         time.Now(),
	}

	return mps.db.WithContext(ctx).
		Table("ml_predictions").
		Create(&prediction).Error
}

// determineDataQuality assesses prediction model data quality
func determineDataQuality(verified, total int64) string {
	if total == 0 {
		return "insufficient_data"
	}

	ratio := float64(verified) / float64(total)
	if ratio >= 0.7 {
		return "high"
	} else if ratio >= 0.4 {
		return "medium"
	}
	return "low"
}
