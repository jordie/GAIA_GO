package rate_limiting

import (
	"context"
	"fmt"
	"sort"
	"time"

	"gorm.io/gorm"
)

// PeerComparison represents how a user compares to their peers
type PeerComparison struct {
	UserID           int     `json:"user_id"`
	CurrentTier      string  `json:"current_tier"`
	Score            float64 `json:"score"`
	PeerAvgScore     float64 `json:"peer_avg_score"`
	PeerMedianScore  float64 `json:"peer_median_score"`
	PeerStdDev       float64 `json:"peer_std_dev"`
	PeerPercentile   float64 `json:"peer_percentile"`      // 0-100
	RankInTier       int     `json:"rank_in_tier"`
	TotalInTier      int     `json:"total_in_tier"`
	BetterThanPercent float64 `json:"better_than_percent"` // % of users with lower score
	TrendVsPeers     string  `json:"trend_vs_peers"`       // improving, declining, stable
	ScoreVsPeerAvg   float64 `json:"score_vs_peer_avg"`
}

// PeerStatistics represents aggregated peer statistics
type PeerStatistics struct {
	Tier             string             `json:"tier"`
	TotalUsers       int64              `json:"total_users"`
	AvgScore         float64            `json:"avg_score"`
	MedianScore      float64            `json:"median_score"`
	MinScore         float64            `json:"min_score"`
	MaxScore         float64            `json:"max_score"`
	StdDevScore      float64            `json:"std_dev_score"`
	Percentile10     float64            `json:"percentile_10"`
	Percentile25     float64            `json:"percentile_25"`
	Percentile75     float64            `json:"percentile_75"`
	Percentile90     float64            `json:"percentile_90"`
	DistributionBuckets map[string]int64 `json:"distribution_buckets"` // Score ranges
}

// PeerAnalyticsService provides peer comparison analytics
type PeerAnalyticsService struct {
	db *gorm.DB
}

// NewPeerAnalyticsService creates a new peer analytics service
func NewPeerAnalyticsService(db *gorm.DB) *PeerAnalyticsService {
	return &PeerAnalyticsService{db: db}
}

// GetUserPeerComparison returns how a user compares to their peers
func (pas *PeerAnalyticsService) GetUserPeerComparison(
	ctx context.Context,
	userID int,
) (*PeerComparison, error) {
	// Get user's current tier and score
	var user struct {
		Tier  string
		Score float64
	}

	result := pas.db.WithContext(ctx).
		Table("reputation_scores").
		Where("user_id = ?", userID).
		Select("tier, score").
		First(&user)

	if result.Error != nil {
		return nil, result.Error
	}

	// Get peer statistics for this tier
	peerStats, err := pas.GetTierStatistics(ctx, user.Tier)
	if err != nil {
		return nil, err
	}

	// Get all users in tier with scores
	var peerScores []float64
	pas.db.WithContext(ctx).
		Table("reputation_scores").
		Where("tier = ?", user.Tier).
		Select("score").
		Order("score DESC").
		Scan(&peerScores)

	// Calculate user's rank and percentile
	rank := 1
	for i, score := range peerScores {
		if score < user.Score {
			rank = i + 1
			break
		}
	}

	percentile := float64(rank) / float64(len(peerScores)) * 100
	betterThan := float64(len(peerScores)-rank) / float64(len(peerScores)) * 100

	// Calculate trend vs peers
	trend := pas.calculateTrendVsPeers(ctx, userID, peerStats.AvgScore)

	return &PeerComparison{
		UserID:           userID,
		CurrentTier:      user.Tier,
		Score:            user.Score,
		PeerAvgScore:     peerStats.AvgScore,
		PeerMedianScore:  peerStats.MedianScore,
		PeerStdDev:       peerStats.StdDevScore,
		PeerPercentile:   percentile,
		RankInTier:       rank,
		TotalInTier:      len(peerScores),
		BetterThanPercent: betterThan,
		TrendVsPeers:     trend,
		ScoreVsPeerAvg:   user.Score - peerStats.AvgScore,
	}, nil
}

// GetTierStatistics returns statistics for all users in a tier
func (pas *PeerAnalyticsService) GetTierStatistics(
	ctx context.Context,
	tier string,
) (*PeerStatistics, error) {
	// Get aggregated stats from view or calculate
	var stats struct {
		TotalUsers int64
		AvgScore   float64
		MedianScore float64
		MinScore   float64
		MaxScore   float64
		StdDevScore float64
		Percentile10 float64
		Percentile25 float64
		Percentile75 float64
		Percentile90 float64
	}

	// Try to get from cached stats first
	result := pas.db.WithContext(ctx).
		Table("peer_reputation_stats").
		Where("tier = ? AND stat_date = CURRENT_DATE", tier).
		Select(
			"total_users, avg_score, median_score, min_score, max_score, stddev_score, "+
				"percentile_10, percentile_25, percentile_75, percentile_90",
		).
		First(&stats)

	if result.Error == nil {
		// Use cached stats
		distribution := pas.getBucketDistribution(ctx, tier)

		return &PeerStatistics{
			Tier:             tier,
			TotalUsers:       stats.TotalUsers,
			AvgScore:         stats.AvgScore,
			MedianScore:      stats.MedianScore,
			MinScore:         stats.MinScore,
			MaxScore:         stats.MaxScore,
			StdDevScore:      stats.StdDevScore,
			Percentile10:     stats.Percentile10,
			Percentile25:     stats.Percentile25,
			Percentile75:     stats.Percentile75,
			Percentile90:     stats.Percentile90,
			DistributionBuckets: distribution,
		}, nil
	}

	// Calculate on the fly if not cached
	return pas.calculateTierStatistics(ctx, tier)
}

// GetAllTiersStatistics returns statistics for all tiers
func (pas *PeerAnalyticsService) GetAllTiersStatistics(
	ctx context.Context,
) (map[string]*PeerStatistics, error) {
	tiers := []string{"flagged", "standard", "trusted", "vip"}
	stats := make(map[string]*PeerStatistics)

	for _, tier := range tiers {
		tierStats, err := pas.GetTierStatistics(ctx, tier)
		if err == nil {
			stats[tier] = tierStats
		}
	}

	return stats, nil
}

// UpdatePeerComparisons recalculates peer comparisons for all users
func (pas *PeerAnalyticsService) UpdatePeerComparisons(
	ctx context.Context,
) error {
	// Get all unique tiers
	var tiers []string
	pas.db.WithContext(ctx).
		Table("reputation_scores").
		Distinct("tier").
		Pluck("tier", &tiers)

	for _, tier := range tiers {
		if err := pas.updateTierComparisons(ctx, tier); err != nil {
			return fmt.Errorf("failed to update tier %s: %w", tier, err)
		}
	}

	return nil
}

// updateTierComparisons updates comparisons for users in a specific tier
func (pas *PeerAnalyticsService) updateTierComparisons(
	ctx context.Context,
	tier string,
) error {
	// Get all users in tier with scores
	var users []struct {
		UserID int
		Score  float64
	}

	pas.db.WithContext(ctx).
		Table("reputation_scores").
		Where("tier = ?", tier).
		Select("user_id, score").
		Order("score DESC").
		Scan(&users)

	// Get tier statistics
	peerStats, err := pas.GetTierStatistics(ctx, tier)
	if err != nil {
		return err
	}

	// Update each user
	for i, user := range users {
		percentile := float64(i+1) / float64(len(users)) * 100
		betterThan := float64(len(users)-i-1) / float64(len(users)) * 100

		trend := pas.calculateTrendVsPeers(ctx, user.UserID, peerStats.AvgScore)

		pas.db.WithContext(ctx).
			Table("user_peer_comparison").
			Where("user_id = ?", user.UserID).
			Updates(map[string]interface{}{
				"tier":              tier,
				"score":             user.Score,
				"peer_avg_score":    peerStats.AvgScore,
				"peer_percentile":   percentile,
				"rank_in_tier":      i + 1,
				"total_in_tier":     len(users),
				"better_than_percent": betterThan,
				"trend_vs_peers":    trend,
				"last_updated":      time.Now(),
			})
	}

	return nil
}

// calculateTierStatistics calculates statistics for a tier
func (pas *PeerAnalyticsService) calculateTierStatistics(
	ctx context.Context,
	tier string,
) (*PeerStatistics, error) {
	var scores []float64

	pas.db.WithContext(ctx).
		Table("reputation_scores").
		Where("tier = ?", tier).
		Pluck("score", &scores)

	if len(scores) == 0 {
		return &PeerStatistics{Tier: tier}, nil
	}

	sort.Float64s(scores)

	avg := calculateAverage(scores)
	median := calculatePercentile(scores, 50)
	stddev := calculateStdDev(scores)

	stats := &PeerStatistics{
		Tier:             tier,
		TotalUsers:       int64(len(scores)),
		AvgScore:         avg,
		MedianScore:      median,
		MinScore:         scores[0],
		MaxScore:         scores[len(scores)-1],
		StdDevScore:      stddev,
		Percentile10:     calculatePercentile(scores, 10),
		Percentile25:     calculatePercentile(scores, 25),
		Percentile75:     calculatePercentile(scores, 75),
		Percentile90:     calculatePercentile(scores, 90),
		DistributionBuckets: pas.getBucketDistribution(ctx, tier),
	}

	return stats, nil
}

// calculateTrendVsPeers determines if user is improving/declining vs peers
func (pas *PeerAnalyticsService) calculateTrendVsPeers(
	ctx context.Context,
	userID int,
	peerAvgScore float64,
) string {
	// Get user's trend from analytics
	var trend string
	pas.db.WithContext(ctx).
		Table("user_analytics_summary").
		Where("user_id = ?", userID).
		Pluck("trend_direction", &trend)

	if trend == "" {
		return "stable"
	}

	return trend
}

// getBucketDistribution returns score distribution in buckets
func (pas *PeerAnalyticsService) getBucketDistribution(
	ctx context.Context,
	tier string,
) map[string]int64 {
	buckets := map[string]int64{
		"0-10":     0,
		"10-20":    0,
		"20-30":    0,
		"30-40":    0,
		"40-50":    0,
		"50-60":    0,
		"60-70":    0,
		"70-80":    0,
		"80-90":    0,
		"90-100":   0,
	}

	var scores []struct {
		Score float64
	}

	pas.db.WithContext(ctx).
		Table("reputation_scores").
		Where("tier = ?", tier).
		Select("score").
		Scan(&scores)

	for _, s := range scores {
		bucket := int(s.Score / 10) * 10
		if bucket > 90 {
			bucket = 90
		}
		bucketLabel := fmt.Sprintf("%d-%d", bucket, bucket+10)
		if bucket == 90 {
			bucketLabel = "90-100"
		}
		if count, exists := buckets[bucketLabel]; exists {
			buckets[bucketLabel] = count + 1
		}
	}

	return buckets
}

// calculatePercentile calculates percentile value in sorted array
func calculatePercentile(scores []float64, percentile float64) float64 {
	if len(scores) == 0 {
		return 0
	}

	index := (percentile / 100) * float64(len(scores)-1)
	lower := int(index)
	upper := lower + 1

	if upper >= len(scores) {
		return scores[len(scores)-1]
	}

	weight := index - float64(lower)
	return scores[lower]*(1-weight) + scores[upper]*weight
}

// GetInsights returns actionable insights for a user based on peer comparison
func (pas *PeerAnalyticsService) GetInsights(
	ctx context.Context,
	userID int,
) ([]string, error) {
	comparison, err := pas.GetUserPeerComparison(ctx, userID)
	if err != nil {
		return nil, err
	}

	insights := make([]string, 0)

	// Percentile-based insights
	if comparison.PeerPercentile >= 90 {
		insights = append(insights, fmt.Sprintf(
			"You're in the top 10%% of %s users with a score of %.1f (peer avg: %.1f)",
			comparison.CurrentTier, comparison.Score, comparison.PeerAvgScore,
		))
	} else if comparison.PeerPercentile >= 75 {
		insights = append(insights, fmt.Sprintf(
			"You're in the top 25%% of %s users. Your score is %.1f points above peer average.",
			comparison.CurrentTier, comparison.ScoreVsPeerAvg,
		))
	} else if comparison.PeerPercentile < 25 {
		insights = append(insights, fmt.Sprintf(
			"Your score (%.1f) is below the peer average (%.1f). Focus on clean API usage to improve.",
			comparison.Score, comparison.PeerAvgScore,
		))
	}

	// Trend-based insights
	if comparison.TrendVsPeers == "improving" {
		insights = append(insights, "Great news! Your reputation is improving faster than your peers.")
	} else if comparison.TrendVsPeers == "declining" {
		insights = append(insights, "Your reputation is declining. Review recent violations and improve compliance.")
	}

	// Next tier insights
	if comparison.CurrentTier == "flagged" {
		insights = append(insights, "Focus on reaching 20 points to advance to Standard tier and restore normal rate limits.")
	} else if comparison.CurrentTier == "standard" {
		insights = append(insights, "Work toward 80 points to reach Trusted tier and get 1.5x rate limits.")
	}

	return insights, nil
}
