package rate_limiting

import (
	"context"
	"testing"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupPeerTestDB creates test database for peer tests
func setupPeerTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to create test DB: %v", err)
	}

	db.Exec(`
		CREATE TABLE reputation_scores (
			id INTEGER PRIMARY KEY,
			user_id INTEGER UNIQUE,
			score REAL,
			tier TEXT
		)
	`)

	db.Exec(`
		CREATE TABLE peer_reputation_stats (
			id INTEGER PRIMARY KEY,
			stat_date DATE,
			tier TEXT,
			total_users INTEGER,
			avg_score REAL,
			median_score REAL,
			min_score REAL,
			max_score REAL,
			stddev_score REAL,
			percentile_10 REAL,
			percentile_25 REAL,
			percentile_75 REAL,
			percentile_90 REAL,
			created_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE user_peer_comparison (
			id INTEGER PRIMARY KEY,
			user_id INTEGER UNIQUE,
			tier TEXT,
			score REAL,
			peer_avg_score REAL,
			peer_percentile REAL,
			rank_in_tier INTEGER,
			total_in_tier INTEGER,
			better_than_percent REAL,
			trend_vs_peers TEXT,
			last_updated TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE user_analytics_summary (
			id INTEGER PRIMARY KEY,
			user_id INTEGER UNIQUE,
			trend_direction TEXT
		)
	`)

	return db
}

// TestPeerAnalyticsServiceCreation tests service initialization
func TestPeerAnalyticsServiceCreation(t *testing.T) {
	db := setupPeerTestDB(t)
	pas := NewPeerAnalyticsService(db)

	if pas == nil {
		t.Errorf("Failed to create peer analytics service")
	}
}

// TestGetUserPeerComparison tests user peer comparison
func TestGetUserPeerComparison(t *testing.T) {
	db := setupPeerTestDB(t)
	pas := NewPeerAnalyticsService(db)

	// Create users in standard tier
	scores := []float64{45.0, 55.0, 65.0, 75.0, 85.0}
	for i, score := range scores {
		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, ?, ?)
		`, i+1, score, "standard")
	}

	// Add analytics for trend
	db.Exec(`
		INSERT INTO user_analytics_summary (user_id, trend_direction)
		VALUES (1, 'improving')
	`)

	comparison, err := pas.GetUserPeerComparison(context.Background(), 1)
	if err != nil {
		t.Errorf("Failed to get peer comparison: %v", err)
	}

	if comparison == nil {
		t.Errorf("Comparison is nil")
	}

	if comparison.CurrentTier != "standard" {
		t.Errorf("Expected standard tier, got %s", comparison.CurrentTier)
	}

	if comparison.Score != 45.0 {
		t.Errorf("Expected score 45, got %f", comparison.Score)
	}
}

// TestGetTierStatistics tests tier statistics calculation
func TestGetTierStatistics(t *testing.T) {
	db := setupPeerTestDB(t)
	pas := NewPeerAnalyticsService(db)

	// Create users in trusted tier
	scores := []float64{80.0, 85.0, 90.0, 95.0, 100.0}
	for i, score := range scores {
		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, ?, ?)
		`, 100+i, score, "trusted")
	}

	stats, err := pas.GetTierStatistics(context.Background(), "trusted")
	if err != nil {
		t.Errorf("Failed to get tier statistics: %v", err)
	}

	if stats == nil {
		t.Errorf("Stats is nil")
	}

	if stats.TotalUsers != 5 {
		t.Errorf("Expected 5 users, got %d", stats.TotalUsers)
	}

	if stats.MinScore != 80.0 {
		t.Errorf("Expected min 80, got %f", stats.MinScore)
	}

	if stats.MaxScore != 100.0 {
		t.Errorf("Expected max 100, got %f", stats.MaxScore)
	}
}

// TestPercentileCalculation tests percentile calculation
func TestPercentileCalculation(t *testing.T) {
	scores := []float64{10, 20, 30, 40, 50, 60, 70, 80, 90, 100}

	p50 := calculatePercentile(scores, 50)
	if p50 < 45 || p50 > 55 {
		t.Errorf("P50 should be around 50, got %f", p50)
	}

	p25 := calculatePercentile(scores, 25)
	if p25 < 20 || p25 > 30 {
		t.Errorf("P25 should be around 25, got %f", p25)
	}

	p90 := calculatePercentile(scores, 90)
	if p90 < 85 || p90 > 95 {
		t.Errorf("P90 should be around 90, got %f", p90)
	}
}

// TestGetAllTiersStatistics tests statistics for all tiers
func TestGetAllTiersStatistics(t *testing.T) {
	db := setupPeerTestDB(t)
	pas := NewPeerAnalyticsService(db)

	// Create users in multiple tiers
	tiers := []string{"flagged", "standard", "trusted", "vip"}
	for tierIdx, tier := range tiers {
		for i := 0; i < 3; i++ {
			userID := tierIdx*100 + i
			score := 20.0 + float64(tierIdx)*20 + float64(i)
			db.Exec(`
				INSERT INTO reputation_scores (user_id, score, tier)
				VALUES (?, ?, ?)
			`, userID, score, tier)
		}
	}

	stats, err := pas.GetAllTiersStatistics(context.Background())
	if err != nil {
		t.Errorf("Failed to get all tier statistics: %v", err)
	}

	if len(stats) == 0 {
		t.Errorf("No tier statistics returned")
	}

	for _, tier := range tiers {
		if stat, exists := stats[tier]; exists && stat != nil {
			if stat.TotalUsers != 3 {
				t.Errorf("Tier %s: expected 3 users, got %d", tier, stat.TotalUsers)
			}
		}
	}
}

// TestUpdatePeerComparisons updates comparisons for all users
func TestUpdatePeerComparisons(t *testing.T) {
	db := setupPeerTestDB(t)
	pas := NewPeerAnalyticsService(db)

	// Create test users
	for i := 1; i <= 5; i++ {
		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, ?, ?)
		`, i, float64(i*10), "standard")
	}

	err := pas.UpdatePeerComparisons(context.Background())
	if err != nil {
		t.Errorf("Failed to update peer comparisons: %v", err)
	}

	// Verify updates were recorded
	var count int64
	db.Table("user_peer_comparison").Count(&count)

	if count != 5 {
		t.Errorf("Expected 5 peer comparisons, got %d", count)
	}
}

// TestGetInsights returns insights for user
func TestGetInsights(t *testing.T) {
	db := setupPeerTestDB(t)
	pas := NewPeerAnalyticsService(db)

	// Create top-tier user
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (?, ?, ?)
	`, 1, 95.0, "trusted")

	// Add trend
	db.Exec(`
		INSERT INTO user_analytics_summary (user_id, trend_direction)
		VALUES (?, ?)
	`, 1, "improving")

	// Create peers
	for i := 2; i <= 5; i++ {
		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, ?, ?)
		`, i, float64(50+i*5), "trusted")
	}

	insights, err := pas.GetInsights(context.Background(), 1)
	if err != nil {
		t.Errorf("Failed to get insights: %v", err)
	}

	if len(insights) == 0 {
		t.Errorf("No insights generated")
	}

	found := false
	for _, insight := range insights {
		if len(insight) > 0 {
			found = true
			break
		}
	}

	if !found {
		t.Errorf("Insights are empty strings")
	}
}

// TestBucketDistribution tests score distribution in buckets
func TestBucketDistribution(t *testing.T) {
	db := setupPeerTestDB(t)
	pas := NewPeerAnalyticsService(db)

	// Create users with varied scores
	scores := []float64{15, 25, 35, 45, 55, 65, 75, 85, 95}
	for i, score := range scores {
		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, ?, ?)
		`, i+1, score, "standard")
	}

	buckets := pas.getBucketDistribution(context.Background(), "standard")

	if len(buckets) == 0 {
		t.Errorf("No buckets returned")
	}

	totalCount := int64(0)
	for _, count := range buckets {
		totalCount += count
	}

	if totalCount != 9 {
		t.Errorf("Expected 9 total in buckets, got %d", totalCount)
	}
}

// TestPeerPercentileRanking tests percentile ranking
func TestPeerPercentileRanking(t *testing.T) {
	db := setupPeerTestDB(t)
	pas := NewPeerAnalyticsService(db)

	// Create 10 users with scores 10-100
	for i := 1; i <= 10; i++ {
		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, ?, ?)
		`, i, float64(i*10), "standard")
	}

	// Get comparison for middle user (50 score)
	comparison, err := pas.GetUserPeerComparison(context.Background(), 5)
	if err != nil {
		t.Errorf("Failed to get comparison: %v", err)
	}

	// User with score 50 should be in middle percentile
	if comparison.PeerPercentile < 30 || comparison.PeerPercentile > 70 {
		t.Errorf("Expected percentile around 50, got %f", comparison.PeerPercentile)
	}
}

// BenchmarkGetUserPeerComparison benchmarks peer comparison
func BenchmarkGetUserPeerComparison(b *testing.B) {
	db := setupPeerTestDB(&testing.T{})
	pas := NewPeerAnalyticsService(db)

	for i := 1; i <= 100; i++ {
		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, ?, ?)
		`, i, float64(50+i%30), "standard")
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		pas.GetUserPeerComparison(context.Background(), 1)
	}
}

// BenchmarkGetAllTiersStatistics benchmarks tier statistics
func BenchmarkGetAllTiersStatistics(b *testing.B) {
	db := setupPeerTestDB(&testing.T{})
	pas := NewPeerAnalyticsService(db)

	for i := 1; i <= 200; i++ {
		tier := []string{"flagged", "standard", "trusted", "vip"}[i%4]
		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, ?, ?)
		`, i, float64(50+i%40), tier)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		pas.GetAllTiersStatistics(context.Background())
	}
}
