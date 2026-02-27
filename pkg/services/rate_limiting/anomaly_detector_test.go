package rate_limiting

import (
	"context"
	"testing"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupAnomalyTestDB creates test database for anomaly tests
func setupAnomalyTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to create test DB: %v", err)
	}

	db.AutoMigrate(&AnomalyPattern{}, &UserBehaviorProfile{})
	return db
}

// TestAnomalyDetectorCreation tests creating anomaly detector
func TestAnomalyDetectorCreation(t *testing.T) {
	db := setupAnomalyTestDB(t)
	ad := NewAnomalyDetector(db)
	defer ad.Close()

	if ad.BurstThreshold != 2.0 {
		t.Errorf("Expected burst threshold 2.0, got %.1f", ad.BurstThreshold)
	}

	if !ad.active {
		t.Errorf("Expected detector to be active")
	}
}

// TestBurstDetection tests burst pattern detection
func TestBurstDetection(t *testing.T) {
	db := setupAnomalyTestDB(t)
	ad := NewAnomalyDetector(db)
	defer ad.Close()

	profile := &UserBehaviorProfile{
		UserID:             1,
		AvgRequestsPerHour: 100,
		StdDevRequests:     20,
		LastAnalyzed:       time.Now(),
		CreatedAt:          time.Now(),
	}
	db.Create(profile)

	// Normal rate: 100/hr = should not be burst
	recentRequests := 90
	isBurst := ad.detectBurst(1, recentRequests, profile)
	if isBurst {
		t.Errorf("Expected no burst for normal rate")
	}

	// Spike rate: 250/hr = 2.5x normal = should be burst
	recentRequests = 250
	isBurst = ad.detectBurst(1, recentRequests, profile)
	if !isBurst {
		t.Errorf("Expected burst for 2.5x rate")
	}
}

// TestUnusualTimeDetection tests unusual time pattern detection
func TestUnusualTimeDetection(t *testing.T) {
	db := setupAnomalyTestDB(t)
	ad := NewAnomalyDetector(db)
	defer ad.Close()

	profile := &UserBehaviorProfile{
		UserID:             2,
		AvgRequestsPerHour: 100,
		PeakHour:           12,
		LastAnalyzed:       time.Now(),
		CreatedAt:          time.Now(),
	}
	db.Create(profile)

	// At peak hour with normal rate: should not be anomaly
	recentRequests := 90
	isAnomaly := ad.detectUnusualTime(2, recentRequests, profile)
	if isAnomaly {
		t.Errorf("Expected no anomaly at peak hour with normal rate")
	}

	// At off-peak hour with spike: should be anomaly
	recentRequests = 300
	isAnomaly = ad.detectUnusualTime(2, recentRequests, profile)
	if !isAnomaly {
		t.Errorf("Expected anomaly for spike at off-peak hour")
	}
}

// TestResourceSpikeDetection tests resource spike detection
func TestResourceSpikeDetection(t *testing.T) {
	db := setupAnomalyTestDB(t)
	ad := NewAnomalyDetector(db)
	defer ad.Close()

	// Normal violations: 5 in an hour = not a spike
	violations := 5
	isSpike := ad.detectResourceSpike(violations)
	if isSpike {
		t.Errorf("Expected no spike for 5 violations")
	}

	// High violations: 15 in an hour = spike
	violations = 15
	isSpike = ad.detectResourceSpike(violations)
	if !isSpike {
		t.Errorf("Expected spike for 15 violations")
	}
}

// TestSeverityClassification tests severity level classification
func TestSeverityClassification(t *testing.T) {
	db := setupAnomalyTestDB(t)
	ad := NewAnomalyDetector(db)
	defer ad.Close()

	tests := []struct {
		score    float64
		expected string
	}{
		{10.0, "low"},
		{35.0, "low"},
		{45.0, "medium"},
		{65.0, "high"},
		{85.0, "critical"},
		{100.0, "critical"},
	}

	for _, test := range tests {
		severity := ad.getSeverity(test.score)
		if severity != test.expected {
			t.Errorf("Score %.0f: expected %s, got %s", test.score, test.expected, severity)
		}
	}
}

// TestConfidenceCalculation tests confidence calculation
func TestConfidenceCalculation(t *testing.T) {
	db := setupAnomalyTestDB(t)
	ad := NewAnomalyDetector(db)
	defer ad.Close()

	// No data: low confidence
	confidence := ad.calculateConfidence(0, 0)
	if confidence > 0.1 {
		t.Errorf("Expected low confidence for no data, got %.2f", confidence)
	}

	// Some data: moderate confidence
	confidence = ad.calculateConfidence(50, 5)
	if confidence < 0.4 || confidence > 0.7 {
		t.Errorf("Expected moderate confidence for 55 data points, got %.2f", confidence)
	}

	// Lots of data: high confidence
	confidence = ad.calculateConfidence(100, 50)
	if confidence < 0.9 {
		t.Errorf("Expected high confidence for 150 data points, got %.2f", confidence)
	}
}

// TestProfileCreation tests behavior profile creation
func TestProfileCreation(t *testing.T) {
	db := setupAnomalyTestDB(t)
	ad := NewAnomalyDetector(db)
	defer ad.Close()

	profile, err := ad.getOrCreateProfile(1)
	if err != nil {
		t.Fatalf("Failed to create profile: %v", err)
	}

	if profile.UserID != 1 {
		t.Errorf("Expected user ID 1, got %d", profile.UserID)
	}

	if profile.AvgRequestsPerHour != 100 {
		t.Errorf("Expected default avg 100/hr, got %.0f", profile.AvgRequestsPerHour)
	}

	// Get same profile again
	profile2, _ := ad.getOrCreateProfile(1)
	if profile2.ID != profile.ID {
		t.Errorf("Expected same profile on second call")
	}
}

// TestAnomalyScoreCaching tests caching of anomaly scores
func TestAnomalyScoreCaching(t *testing.T) {
	db := setupAnomalyTestDB(t)
	ad := NewAnomalyDetector(db)
	defer ad.Close()

	userID := 10

	// First call calculates score
	score1 := ad.GetAnomalyScore(userID)
	if score1 == nil {
		t.Errorf("Expected anomaly score, got nil")
	}

	// Second call should return cached value
	score2 := ad.GetAnomalyScore(userID)
	if score2 == nil {
		t.Errorf("Expected cached anomaly score, got nil")
	}

	// Scores should match
	if score1.Score != score2.Score {
		t.Errorf("Expected same score from cache")
	}
}

// TestPatternResolution tests marking patterns as resolved
func TestPatternResolution(t *testing.T) {
	db := setupAnomalyTestDB(t)
	ad := NewAnomalyDetector(db)
	defer ad.Close()

	// Create a pattern
	pattern := AnomalyPattern{
		UserID:      2,
		PatternType: "high",
		Description: "Test pattern",
		Score:       75.0,
		Confidence:  0.8,
		StartTime:   time.Now(),
		Resolved:    false,
		CreatedAt:   time.Now(),
	}
	db.Create(&pattern)

	ctx := context.Background()

	// Resolve it
	err := ad.ResolvePattern(ctx, pattern.ID)
	if err != nil {
		t.Fatalf("Failed to resolve pattern: %v", err)
	}

	// Verify resolved
	var updated AnomalyPattern
	db.First(&updated, pattern.ID)
	if !updated.Resolved {
		t.Errorf("Expected pattern to be resolved")
	}
	if updated.EndTime == nil {
		t.Errorf("Expected end time to be set")
	}
}

// TestAnomalyStats tests statistics calculation
func TestAnomalyStats(t *testing.T) {
	db := setupAnomalyTestDB(t)
	ad := NewAnomalyDetector(db)
	defer ad.Close()

	ctx := context.Background()

	// Create some patterns
	for i := 1; i <= 5; i++ {
		pattern := AnomalyPattern{
			UserID:      i,
			PatternType: "high",
			Score:       float64(60 + i*5),
			StartTime:   time.Now(),
			Resolved:    i%2 == 0, // Half resolved
			CreatedAt:   time.Now(),
		}
		db.Create(&pattern)
	}

	stats, err := ad.GetAnomalyStats(ctx)
	if err != nil {
		t.Fatalf("Failed to get stats: %v", err)
	}

	if stats["total_patterns"].(int64) != 5 {
		t.Errorf("Expected 5 total patterns")
	}

	if stats["unresolved_count"].(int64) != 3 {
		t.Errorf("Expected 3 unresolved patterns")
	}
}

// TestGetPatterns tests pattern retrieval
func TestGetPatterns(t *testing.T) {
	db := setupAnomalyTestDB(t)
	ad := NewAnomalyDetector(db)
	defer ad.Close()

	userID := 20
	ctx := context.Background()

	// Create patterns
	for i := 1; i <= 3; i++ {
		pattern := AnomalyPattern{
			UserID:      userID,
			PatternType: "high",
			Score:       float64(60 + i*10),
			StartTime:   time.Now(),
			Resolved:    false,
			CreatedAt:   time.Now(),
		}
		db.Create(&pattern)
	}

	patterns, err := ad.GetAnomalyPatterns(ctx, userID, 10)
	if err != nil {
		t.Fatalf("Failed to get patterns: %v", err)
	}

	if len(patterns) != 3 {
		t.Errorf("Expected 3 patterns, got %d", len(patterns))
	}

	// All should be for the user
	for _, p := range patterns {
		if p.UserID != userID {
			t.Errorf("Expected user ID %d, got %d", userID, p.UserID)
		}
		if p.Resolved {
			t.Errorf("Expected unresolved patterns")
		}
	}
}

// BenchmarkAnomalyScore benchmarks anomaly score calculation
func BenchmarkAnomalyScore(b *testing.B) {
	db := setupAnomalyTestDB(&testing.T{})
	ad := NewAnomalyDetector(db)
	defer ad.Close()

	profile := &UserBehaviorProfile{
		UserID:             1,
		AvgRequestsPerHour: 100,
		CreatedAt:          time.Now(),
	}
	db.Create(profile)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		ad.GetAnomalyScore(1)
	}
}

// BenchmarkDetectBurst benchmarks burst detection
func BenchmarkDetectBurst(b *testing.B) {
	db := setupAnomalyTestDB(&testing.T{})
	ad := NewAnomalyDetector(db)
	defer ad.Close()

	profile := &UserBehaviorProfile{
		UserID:             1,
		AvgRequestsPerHour: 100,
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		ad.detectBurst(1, 250, profile)
	}
}
