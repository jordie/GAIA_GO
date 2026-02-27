package rate_limiting

import (
	"context"
	"fmt"
	"math"
	"time"

	"gorm.io/gorm"
)

// TrendPoint represents a single data point in a trend
type TrendPoint struct {
	Date       string  `json:"date"`
	Score      float64 `json:"score"`
	Tier       string  `json:"tier"`
	Violations int     `json:"violations"`
	Successful int     `json:"successful"`
	Change     float64 `json:"change"` // Change from previous point
}

// TrendAnalysis represents trend analysis data
type TrendAnalysis struct {
	TimePeriod   string       `json:"time_period"` // 7d, 30d, 90d
	Points       []TrendPoint `json:"points"`
	AvgScore     float64      `json:"avg_score"`
	MaxScore     float64      `json:"max_score"`
	MinScore     float64      `json:"min_score"`
	Trend        string       `json:"trend"` // improving, declining, stable
	Volatility   float64      `json:"volatility"` // Standard deviation
	ProjectedScore float64    `json:"projected_score"` // Estimated score in 30 days
}

// BehaviorPattern represents a detected behavior pattern
type BehaviorPattern struct {
	PatternType  string    `json:"pattern_type"` // burst, unusual_time, resource_spike, etc
	Frequency    int       `json:"frequency"` // How many times detected
	LastDetected time.Time `json:"last_detected"`
	Severity     int       `json:"severity"` // 1-5
	Impact       float64   `json:"impact"` // Reputation impact
	Recommendation string  `json:"recommendation"` // Advice to user
}

// Recommendation represents a personalized recommendation
type Recommendation struct {
	Priority    string `json:"priority"` // low, medium, high, critical
	Title       string `json:"title"`
	Description string `json:"description"`
	Action      string `json:"action"`
	ExpectedGain float64 `json:"expected_gain"` // Expected reputation gain
}

// AnalyticsService provides advanced analytics and insights
type AnalyticsService struct {
	db *gorm.DB
}

// NewAnalyticsService creates a new analytics service
func NewAnalyticsService(db *gorm.DB) *AnalyticsService {
	return &AnalyticsService{db: db}
}

// GetReputationTrends returns reputation trend analysis
func (as *AnalyticsService) GetReputationTrends(ctx context.Context, userID int, days int) (*TrendAnalysis, error) {
	if days != 7 && days != 30 && days != 90 {
		days = 30 // Default to 30 days
	}

	var points []TrendPoint
	startDate := time.Now().AddDate(0, 0, -days)

	// Get daily reputation data
	var events []struct {
		Date       string
		Score      float64
		Violations int
		Successful int
	}

	// Group events by day and calculate daily score
	as.db.WithContext(ctx).
		Raw(`
			SELECT
				DATE(created_at) as date,
				SUM(CASE WHEN score_delta > 0 THEN score_delta ELSE 0 END) as score,
				SUM(CASE WHEN event_type = 'violation' THEN 1 ELSE 0 END) as violations,
				SUM(CASE WHEN event_type IN ('clean_request', 'success') THEN 1 ELSE 0 END) as successful
			FROM reputation_events
			WHERE user_id = ? AND created_at > ?
			GROUP BY DATE(created_at)
			ORDER BY date ASC
		`, userID, startDate).
		Scan(&events)

	// Convert to trend points
	var scores []float64
	var prevScore float64

	for i, event := range events {
		score := prevScore + event.Score
		change := score - prevScore
		prevScore = score

		points = append(points, TrendPoint{
			Date:       event.Date,
			Score:      score,
			Violations: event.Violations,
			Successful: event.Successful,
			Change:     change,
		})

		scores = append(scores, score)
	}

	// Calculate statistics
	analysis := &TrendAnalysis{
		TimePeriod: fmt.Sprintf("%dd", days),
		Points:     points,
	}

	if len(scores) > 0 {
		analysis.AvgScore = calculateAverage(scores)
		analysis.MaxScore = calculateMax(scores)
		analysis.MinScore = calculateMin(scores)
		analysis.Volatility = calculateStdDev(scores)
		analysis.Trend = determineTrend(scores)
		analysis.ProjectedScore = projectScore(scores)
	}

	return analysis, nil
}

// GetBehaviorPatterns returns detected behavior patterns
func (as *AnalyticsService) GetBehaviorPatterns(ctx context.Context, userID int) ([]BehaviorPattern, error) {
	var patterns []BehaviorPattern
	thirtyDaysAgo := time.Now().AddDate(0, 0, -30)

	// Detect burst patterns
	var bursts int64
	as.db.WithContext(ctx).
		Model(&AnomalyPattern{}).
		Where("user_id = ? AND pattern_type = 'burst' AND created_at > ?", userID, thirtyDaysAgo).
		Count(&bursts)

	if bursts > 0 {
		patterns = append(patterns, BehaviorPattern{
			PatternType:  "burst",
			Frequency:    int(bursts),
			LastDetected: time.Now(),
			Severity:     3,
			Impact:       -30.0,
			Recommendation: "Space out your requests more evenly throughout the day to avoid sudden spikes",
		})
	}

	// Detect unusual time patterns
	var unusualTimes int64
	as.db.WithContext(ctx).
		Model(&AnomalyPattern{}).
		Where("user_id = ? AND pattern_type = 'unusual_time' AND created_at > ?", userID, thirtyDaysAgo).
		Count(&unusualTimes)

	if unusualTimes > 0 {
		patterns = append(patterns, BehaviorPattern{
			PatternType:  "unusual_time",
			Frequency:    int(unusualTimes),
			LastDetected: time.Now(),
			Severity:     2,
			Impact:       -20.0,
			Recommendation: "Try to concentrate your API usage during normal business hours to stay within expected patterns",
		})
	}

	// Detect resource spike patterns
	var spikes int64
	as.db.WithContext(ctx).
		Model(&AnomalyPattern{}).
		Where("user_id = ? AND pattern_type = 'resource_spike' AND created_at > ?", userID, thirtyDaysAgo).
		Count(&spikes)

	if spikes > 0 {
		patterns = append(patterns, BehaviorPattern{
			PatternType:  "resource_spike",
			Frequency:    int(spikes),
			LastDetected: time.Now(),
			Severity:     4,
			Impact:       -25.0,
			Recommendation: "Optimize your resource usage and consider batch processing to reduce violation frequency",
		})
	}

	return patterns, nil
}

// GetPersonalizedRecommendations returns tailored improvement suggestions
func (as *AnalyticsService) GetPersonalizedRecommendations(ctx context.Context, userID int) ([]Recommendation, error) {
	var recommendations []Recommendation

	// Get current reputation
	var score float64
	var tier string
	as.db.WithContext(ctx).
		Table("reputation_scores").
		Where("user_id = ?", userID).
		Select("score, tier").
		Scan(&map[string]interface{}{"score": &score, "tier": &tier})

	// Get recent violations
	var violationCount int64
	as.db.WithContext(ctx).
		Model(&ReputationEvent{}).
		Where("user_id = ? AND event_type = 'violation' AND created_at > ?", userID, time.Now().AddDate(0, 0, -7)).
		Count(&violationCount)

	// Get clean requests
	var cleanCount int64
	as.db.WithContext(ctx).
		Model(&ReputationEvent{}).
		Where("user_id = ? AND event_type IN ('clean_request', 'success') AND created_at > ?", userID, time.Now().AddDate(0, 0, -7)).
		Count(&cleanCount)

	// Recommendation 1: Low reputation
	if score < 20 {
		recommendations = append(recommendations, Recommendation{
			Priority:    "critical",
			Title:       "Restore Your Account Standing",
			Description: "Your reputation is severely damaged. Focus on clean, compliant API usage.",
			Action:      "Make 1000+ clean requests without violations",
			ExpectedGain: 15.0,
		})
	} else if score < 50 {
		recommendations = append(recommendations, Recommendation{
			Priority:    "high",
			Title:       "Improve Your Reputation",
			Description: "You're approaching neutral reputation. Consistent good behavior can rebuild trust.",
			Action:      "Maintain clean usage for 14 consecutive days",
			ExpectedGain: 10.0,
		})
	}

	// Recommendation 2: Recent violations
	if violationCount > 0 {
		recommendations = append(recommendations, Recommendation{
			Priority:    "high",
			Title:       "Stop Recent Violations",
			Description: fmt.Sprintf("You had %d violations in the last 7 days. This is preventing reputation growth.", violationCount),
			Action:      "Audit your code for rate limiting issues and implement request throttling",
			ExpectedGain: 5.0 * float64(violationCount),
		})
	}

	// Recommendation 3: Low activity
	if cleanCount < 100 {
		recommendations = append(recommendations, Recommendation{
			Priority:    "medium",
			Title:       "Increase Legitimate API Usage",
			Description: "Low usage patterns make reputation scoring less reliable. More clean requests improve confidence.",
			Action:      "Increase API usage to 100+ clean requests per week",
			ExpectedGain: 3.0,
		})
	}

	// Recommendation 4: Path to next tier
	if tier == "flagged" {
		recommendations = append(recommendations, Recommendation{
			Priority:    "high",
			Title:       "Reach Standard Tier",
			Description: "You need a score of 20+ to reach Standard tier and restore normal rate limits.",
			Action:      "Focus on error-free API usage for next 30 days",
			ExpectedGain: 20.0 - score,
		})
	} else if tier == "standard" {
		recommendations = append(recommendations, Recommendation{
			Priority:    "medium",
			Title:       "Reach Trusted Tier",
			Description: "A score of 80+ qualifies you for Trusted tier with 1.5x rate limits.",
			Action:      "Maintain clean usage and demonstrate reliability",
			ExpectedGain: 80.0 - score,
		})
	} else if tier == "trusted" {
		recommendations = append(recommendations, Recommendation{
			Priority:    "low",
			Title:       "Consider VIP Status",
			Description: "With your strong reputation, VIP status offers 2x rate limits and priority support.",
			Action:      "Contact support about VIP subscription options",
			ExpectedGain: 0.0,
		})
	}

	// Recommendation 5: Consistency
	if violationCount == 0 && cleanCount > 500 {
		recommendations = append(recommendations, Recommendation{
			Priority:    "low",
			Title:       "Exceptional Usage Pattern",
			Description: "Your API usage is exemplary with no recent violations.",
			Action:      "Continue current patterns and consider mentoring others",
			ExpectedGain: 2.0,
		})
	}

	return recommendations, nil
}

// GetUsagePatterns returns hourly usage patterns
func (as *AnalyticsService) GetUsagePatterns(ctx context.Context, userID int) (map[string]interface{}, error) {
	var hourly []struct {
		Hour     int
		Requests int64
	}

	// Get hourly distribution for last 7 days
	as.db.WithContext(ctx).
		Raw(`
			SELECT
				EXTRACT(HOUR FROM created_at)::int as hour,
				COUNT(*) as requests
			FROM reputation_events
			WHERE user_id = ? AND created_at > ?
			GROUP BY EXTRACT(HOUR FROM created_at)
			ORDER BY hour ASC
		`, userID, time.Now().AddDate(0, 0, -7)).
		Scan(&hourly)

	// Find peak hours
	peakHour := 0
	maxRequests := int64(0)
	for _, h := range hourly {
		if h.Requests > maxRequests {
			maxRequests = h.Requests
			peakHour = h.Hour
		}
	}

	// Detect shift work (peak hours not in 9-5)
	dayShift := 0
	nightShift := 0

	for _, h := range hourly {
		if h.Hour >= 9 && h.Hour < 17 {
			dayShift += int(h.Requests)
		} else if h.Hour >= 20 || h.Hour < 6 {
			nightShift += int(h.Requests)
		}
	}

	var shift string
	if nightShift > dayShift {
		shift = "night"
	} else if dayShift > nightShift {
		shift = "day"
	} else {
		shift = "mixed"
	}

	return map[string]interface{}{
		"hourly_distribution": hourly,
		"peak_hour":          peakHour,
		"shift_pattern":      shift,
		"day_requests":       dayShift,
		"night_requests":     nightShift,
	}, nil
}

// Helper functions

func calculateAverage(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	sum := 0.0
	for _, v := range values {
		sum += v
	}
	return sum / float64(len(values))
}

func calculateMax(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	max := values[0]
	for _, v := range values {
		if v > max {
			max = v
		}
	}
	return max
}

func calculateMin(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	min := values[0]
	for _, v := range values {
		if v < min {
			min = v
		}
	}
	return min
}

func calculateStdDev(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}

	mean := calculateAverage(values)
	sumSquares := 0.0

	for _, v := range values {
		diff := v - mean
		sumSquares += diff * diff
	}

	variance := sumSquares / float64(len(values))
	return math.Sqrt(variance)
}

func determineTrend(scores []float64) string {
	if len(scores) < 2 {
		return "stable"
	}

	// Compare first half to second half
	midpoint := len(scores) / 2
	firstHalfAvg := calculateAverage(scores[:midpoint])
	secondHalfAvg := calculateAverage(scores[midpoint:])

	change := secondHalfAvg - firstHalfAvg
	changePercent := (change / firstHalfAvg) * 100

	if changePercent > 5 {
		return "improving"
	} else if changePercent < -5 {
		return "declining"
	}
	return "stable"
}

func projectScore(scores []float64) float64 {
	if len(scores) < 7 {
		return calculateAverage(scores)
	}

	// Linear regression to project next 30 days
	lastWeek := scores[len(scores)-7:]
	avgLastWeek := calculateAverage(lastWeek)

	// Trend direction
	change := lastWeek[6] - lastWeek[0]
	dailyChange := change / 7.0

	// Project 30 days
	projected := avgLastWeek + (dailyChange * 30)

	// Cap at reasonable bounds
	if projected > 100 {
		projected = 100
	}
	if projected < 0 {
		projected = 0
	}

	return projected
}
