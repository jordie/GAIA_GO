package rate_limiting

import (
	"context"
	"testing"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupAnalyticsTestDB creates test database
func setupAnalyticsTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to create test DB: %v", err)
	}

	db.AutoMigrate(&ReputationEvent{}, &AnomalyPattern{})

	return db
}

// TestAnalyticsServiceCreation tests service initialization
func TestAnalyticsServiceCreation(t *testing.T) {
	db := setupAnalyticsTestDB(t)
	as := NewAnalyticsService(db)

	if as == nil {
		t.Errorf("Failed to create analytics service")
	}
}

// TestGetReputationTrends tests trend analysis
func TestGetReputationTrends(t *testing.T) {
	db := setupAnalyticsTestDB(t)
	as := NewAnalyticsService(db)
	ctx := context.Background()

	// Create events over 7 days
	for i := 0; i < 7; i++ {
		date := time.Now().AddDate(0, 0, -i)
		event := &ReputationEvent{
			UserID:        1,
			NodeID:        "test",
			EventType:     "clean_request",
			ScoreDelta:    float64(5 - i), // Declining trend
			SourceService: "api",
			Timestamp:     date,
			CreatedAt:     date,
		}
		db.Create(event)
	}

	trends, err := as.GetReputationTrends(ctx, 1, 7)
	if err != nil {
		t.Errorf("Failed to get trends: %v", err)
	}

	if trends == nil {
		t.Errorf("Trends is nil")
	}

	if trends.TimePeriod != "7d" {
		t.Errorf("Expected 7d, got %s", trends.TimePeriod)
	}
}

// TestGetBehaviorPatterns tests pattern detection
func TestGetBehaviorPatterns(t *testing.T) {
	db := setupAnalyticsTestDB(t)
	as := NewAnalyticsService(db)
	ctx := context.Background()

	// Create burst patterns
	for i := 0; i < 3; i++ {
		pattern := &AnomalyPattern{
			UserID:      1,
			PatternType: "burst",
			Score:       75.0,
			Confidence:  0.9,
			StartTime:   time.Now().AddDate(0, 0, -i),
			Resolved:    false,
			CreatedAt:   time.Now().AddDate(0, 0, -i),
		}
		db.Create(pattern)
	}

	patterns, err := as.GetBehaviorPatterns(ctx, 1)
	if err != nil {
		t.Errorf("Failed to get patterns: %v", err)
	}

	found := false
	for _, p := range patterns {
		if p.PatternType == "burst" {
			found = true
			if p.Frequency != 3 {
				t.Errorf("Expected 3 bursts, got %d", p.Frequency)
			}
		}
	}

	if !found {
		t.Errorf("Burst pattern not found")
	}
}

// TestGetPersonalizedRecommendations tests recommendations
func TestGetPersonalizedRecommendations(t *testing.T) {
	db := setupAnalyticsTestDB(t)
	as := NewAnalyticsService(db)
	ctx := context.Background()

	// Create low reputation score
	event := &ReputationEvent{
		UserID:        1,
		NodeID:        "test",
		EventType:     "violation",
		ScoreDelta:    -15.0,
		SourceService: "api",
		Timestamp:     time.Now(),
		CreatedAt:     time.Now(),
	}
	db.Create(event)

	recommendations, err := as.GetPersonalizedRecommendations(ctx, 1)
	if err != nil {
		t.Errorf("Failed to get recommendations: %v", err)
	}

	if len(recommendations) == 0 {
		t.Errorf("No recommendations generated")
	}

	// Should include recommendation for low reputation
	found := false
	for _, r := range recommendations {
		if r.Priority == "high" && r.Description != "" {
			found = true
		}
	}

	if !found {
		t.Errorf("Expected high priority recommendation")
	}
}

// TestGetUsagePatterns tests usage pattern detection
func TestGetUsagePatterns(t *testing.T) {
	db := setupAnalyticsTestDB(t)
	as := NewAnalyticsService(db)
	ctx := context.Background()

	// Create events at different hours
	for hour := 9; hour < 17; hour++ {
		for i := 0; i < 5; i++ {
			date := time.Now().Add(-24 * time.Hour).Add(time.Duration(hour) * time.Hour)
			event := &ReputationEvent{
				UserID:        1,
				NodeID:        "test",
				EventType:     "clean_request",
				ScoreDelta:    1.0,
				SourceService: "api",
				Timestamp:     date,
				CreatedAt:     date,
			}
			db.Create(event)
		}
	}

	patterns, err := as.GetUsagePatterns(ctx, 1)
	if err != nil {
		t.Errorf("Failed to get usage patterns: %v", err)
	}

	if patterns["shift_pattern"] == nil {
		t.Errorf("Shift pattern not detected")
	}

	if patterns["peak_hour"] == nil {
		t.Errorf("Peak hour not detected")
	}
}

// TestTrendDetermination tests trend analysis logic
func TestTrendDetermination(t *testing.T) {
	// Test improving trend
	improving := []float64{10, 15, 20, 25, 30, 35, 40}
	trend := determineTrend(improving)
	if trend != "improving" {
		t.Errorf("Expected improving, got %s", trend)
	}

	// Test declining trend
	declining := []float64{40, 35, 30, 25, 20, 15, 10}
	trend = determineTrend(declining)
	if trend != "declining" {
		t.Errorf("Expected declining, got %s", trend)
	}

	// Test stable trend
	stable := []float64{25, 25, 26, 24, 25, 26, 25}
	trend = determineTrend(stable)
	if trend != "stable" {
		t.Errorf("Expected stable, got %s", trend)
	}
}

// TestScoreProjection tests score projection
func TestScoreProjection(t *testing.T) {
	// Scores improving at steady rate
	scores := []float64{40, 45, 50, 55, 60, 65, 70}
	projected := projectScore(scores)

	// Should be around 100 (70 + 5*6 days = 100)
	if projected < 90 || projected > 110 {
		t.Errorf("Expected projection around 100, got %f", projected)
	}

	// Test max cap at 100
	veryHigh := []float64{95, 96, 97, 98, 99, 100, 100}
	projected = projectScore(veryHigh)

	if projected > 100 {
		t.Errorf("Projection should not exceed 100, got %f", projected)
	}
}

// TestCalculateStatistics tests statistics calculations
func TestCalculateStatistics(t *testing.T) {
	values := []float64{10, 20, 30, 40, 50}

	avg := calculateAverage(values)
	if avg != 30 {
		t.Errorf("Expected average 30, got %f", avg)
	}

	max := calculateMax(values)
	if max != 50 {
		t.Errorf("Expected max 50, got %f", max)
	}

	min := calculateMin(values)
	if min != 10 {
		t.Errorf("Expected min 10, got %f", min)
	}

	stdDev := calculateStdDev(values)
	if stdDev < 14 || stdDev > 16 {
		t.Errorf("Expected stddev around 15, got %f", stdDev)
	}
}

// TestNoDataHandling tests handling of empty data
func TestNoDataHandling(t *testing.T) {
	db := setupAnalyticsTestDB(t)
	as := NewAnalyticsService(db)
	ctx := context.Background()

	// User with no events
	trends, err := as.GetReputationTrends(ctx, 999, 30)
	if err != nil {
		t.Errorf("Should not error on missing user: %v", err)
	}

	if trends == nil {
		t.Errorf("Should return valid trend object")
	}

	patterns, err := as.GetBehaviorPatterns(ctx, 999)
	if err != nil {
		t.Errorf("Should not error on missing user: %v", err)
	}

	if len(patterns) != 0 {
		t.Errorf("Should return empty patterns for user with no data")
	}
}

// TestRecommendationPriority tests recommendation prioritization
func TestRecommendationPriority(t *testing.T) {
	db := setupAnalyticsTestDB(t)
	as := NewAnalyticsService(db)
	ctx := context.Background()

	// Create high violation count
	for i := 0; i < 5; i++ {
		event := &ReputationEvent{
			UserID:        1,
			NodeID:        "test",
			EventType:     "violation",
			ScoreDelta:    -9.0,
			SourceService: "api",
			Timestamp:     time.Now().AddDate(0, 0, -i),
			CreatedAt:     time.Now().AddDate(0, 0, -i),
		}
		db.Create(event)
	}

	recommendations, err := as.GetPersonalizedRecommendations(ctx, 1)
	if err != nil {
		t.Fatalf("Failed to get recommendations: %v", err)
	}

	// Should have high priority recommendations
	highPriorityFound := false
	for _, r := range recommendations {
		if r.Priority == "high" {
			highPriorityFound = true
		}
	}

	if !highPriorityFound {
		t.Errorf("Expected high priority recommendations for user with violations")
	}
}

// BenchmarkGetReputationTrends benchmarks trend calculation
func BenchmarkGetReputationTrends(b *testing.B) {
	db := setupAnalyticsTestDB(&testing.T{})
	as := NewAnalyticsService(db)
	ctx := context.Background()

	// Create 30 days of events
	for day := 0; day < 30; day++ {
		for i := 0; i < 10; i++ {
			date := time.Now().AddDate(0, 0, -day)
			event := &ReputationEvent{
				UserID:        1,
				NodeID:        "test",
				EventType:     "clean_request",
				ScoreDelta:    1.0,
				SourceService: "api",
				Timestamp:     date,
				CreatedAt:     date,
			}
			db.Create(event)
		}
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		as.GetReputationTrends(ctx, 1, 30)
	}
}

// BenchmarkGetRecommendations benchmarks recommendation generation
func BenchmarkGetRecommendations(b *testing.B) {
	db := setupAnalyticsTestDB(&testing.T{})
	as := NewAnalyticsService(db)
	ctx := context.Background()

	// Create some events
	for i := 0; i < 50; i++ {
		event := &ReputationEvent{
			UserID:        1,
			NodeID:        "test",
			EventType:     "violation",
			ScoreDelta:    -5.0,
			SourceService: "api",
			Timestamp:     time.Now().AddDate(0, 0, -i%30),
			CreatedAt:     time.Now().AddDate(0, 0, -i%30),
		}
		db.Create(event)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		as.GetPersonalizedRecommendations(ctx, 1)
	}
}
