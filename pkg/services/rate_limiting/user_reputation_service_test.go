package rate_limiting

import (
	"context"
	"fmt"
	"testing"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupUserReputationTestDB creates test database
func setupUserReputationTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to create test DB: %v", err)
	}

	db.AutoMigrate(
		&ReputationEvent{},
		&UserBehaviorProfile{},
		&AnomalyPattern{},
	)

	return db
}

// TestUserReputationServiceCreation tests service initialization
func TestUserReputationServiceCreation(t *testing.T) {
	db := setupUserReputationTestDB(t)
	rm := NewReputationManager(db)
	at := NewAutoThrottler(db)
	ad := NewAnomalyDetector(db)

	urs := NewUserReputationService(db, rm, at, ad)
	defer rm.Close()
	defer at.Close()
	defer ad.Close()

	if urs == nil {
		t.Errorf("Failed to create user reputation service")
	}

	if len(urs.explanationCache) != 4 {
		t.Errorf("Expected 4 tier explanations, got %d", len(urs.explanationCache))
	}
}

// TestGetUserReputationView tests complete user view
func TestGetUserReputationView(t *testing.T) {
	db := setupUserReputationTestDB(t)
	rm := NewReputationManager(db)
	at := NewAutoThrottler(db)
	ad := NewAnomalyDetector(db)
	defer rm.Close()
	defer at.Close()
	defer ad.Close()

	urs := NewUserReputationService(db, rm, at, ad)
	ctx := context.Background()

	// Set user reputation
	rm.UpdateUserReputation(1, 75.0)

	view, err := urs.GetUserReputationView(ctx, 1)
	if err != nil {
		t.Errorf("Failed to get user view: %v", err)
	}

	if view.UserID != 1 {
		t.Errorf("Wrong user ID")
	}

	if view.Score != 75.0 {
		t.Errorf("Expected score 75.0, got %f", view.Score)
	}

	if view.Tier != "trusted" {
		t.Errorf("Expected tier 'trusted', got %s", view.Tier)
	}

	if view.Multiplier != 1.5 {
		t.Errorf("Expected multiplier 1.5, got %f", view.Multiplier)
	}

	if view.RateLimitInfo == nil {
		t.Errorf("RateLimitInfo is nil")
	}

	if view.RateLimitInfo.BaseLimit != 1000 {
		t.Errorf("Expected base limit 1000, got %d", view.RateLimitInfo.BaseLimit)
	}
}

// TestTierExplanations tests tier explanation retrieval
func TestTierExplanations(t *testing.T) {
	db := setupUserReputationTestDB(t)
	rm := NewReputationManager(db)
	at := NewAutoThrottler(db)
	ad := NewAnomalyDetector(db)
	defer rm.Close()
	defer at.Close()
	defer ad.Close()

	urs := NewUserReputationService(db, rm, at, ad)

	tests := []struct {
		tier       string
		multiplier float64
	}{
		{"flagged", 0.5},
		{"standard", 1.0},
		{"trusted", 1.5},
		{"premium_vip", 2.0},
	}

	for _, test := range tests {
		exp := urs.GetTierExplanation(test.tier)
		if exp == nil {
			t.Errorf("No explanation for tier %s", test.tier)
		}

		if exp.Multiplier != test.multiplier {
			t.Errorf("Tier %s: expected multiplier %f, got %f", test.tier, test.multiplier, exp.Multiplier)
		}
	}
}

// TestAllTierExplanations tests getting all tier explanations
func TestAllTierExplanations(t *testing.T) {
	db := setupUserReputationTestDB(t)
	rm := NewReputationManager(db)
	at := NewAutoThrottler(db)
	ad := NewAnomalyDetector(db)
	defer rm.Close()
	defer at.Close()
	defer ad.Close()

	urs := NewUserReputationService(db, rm, at, ad)

	all := urs.GetAllTierExplanations()
	if len(all) != 4 {
		t.Errorf("Expected 4 tier explanations, got %d", len(all))
	}

	tiers := make(map[string]bool)
	for _, exp := range all {
		tiers[exp.Tier] = true
	}

	expected := []string{"flagged", "standard", "trusted", "premium_vip"}
	for _, exp := range expected {
		if !tiers[exp] {
			t.Errorf("Missing tier explanation: %s", exp)
		}
	}
}

// TestNextTierCalculation tests tier progression calculation
func TestNextTierCalculation(t *testing.T) {
	db := setupUserReputationTestDB(t)
	rm := NewReputationManager(db)
	at := NewAutoThrottler(db)
	ad := NewAnomalyDetector(db)
	defer rm.Close()
	defer at.Close()
	defer ad.Close()

	urs := NewUserReputationService(db, rm, at, ad)

	tests := []struct {
		current     string
		currentScore float64
		expectedNext string
		expectedScore float64
	}{
		{"flagged", 10.0, "standard", 20.0},
		{"standard", 50.0, "trusted", 80.0},
		{"trusted", 85.0, "premium_vip", 100.0},
	}

	for _, test := range tests {
		next, score := urs.getNextTier(test.current, test.currentScore)
		if next != test.expectedNext {
			t.Errorf("Current %s: expected next %s, got %s", test.current, test.expectedNext, next)
		}

		if score != test.expectedScore {
			t.Errorf("Current %s: expected score %f, got %f", test.current, test.expectedScore, score)
		}
	}
}

// TestReputationFAQ tests FAQ content
func TestReputationFAQ(t *testing.T) {
	db := setupUserReputationTestDB(t)
	rm := NewReputationManager(db)
	at := NewAutoThrottler(db)
	ad := NewAnomalyDetector(db)
	defer rm.Close()
	defer at.Close()
	defer ad.Close()

	urs := NewUserReputationService(db, rm, at, ad)

	faq := urs.GetReputationFAQ()
	if len(faq) == 0 {
		t.Errorf("FAQ is empty")
	}

	for _, item := range faq {
		if _, ok := item["question"]; !ok {
			t.Errorf("FAQ item missing 'question'")
		}

		if _, ok := item["answer"]; !ok {
			t.Errorf("FAQ item missing 'answer'")
		}

		if item["question"].(string) == "" {
			t.Errorf("Empty question in FAQ")
		}

		if item["answer"].(string) == "" {
			t.Errorf("Empty answer in FAQ")
		}
	}
}

// TestTierProgress tests tier progress calculation
func TestTierProgress(t *testing.T) {
	db := setupUserReputationTestDB(t)
	rm := NewReputationManager(db)
	at := NewAutoThrottler(db)
	ad := NewAnomalyDetector(db)
	defer rm.Close()
	defer at.Close()
	defer ad.Close()

	urs := NewUserReputationService(db, rm, at, ad)
	ctx := context.Background()

	// Test flagged user working toward standard
	rm.UpdateUserReputation(1, 10.0)
	view, err := urs.GetUserReputationView(ctx, 1)
	if err != nil {
		t.Fatalf("Failed to get view: %v", err)
	}

	if view.NextTierScore != 20.0 {
		t.Errorf("Expected next tier 20.0, got %f", view.NextTierScore)
	}

	expectedProgress := 10.0 / 20.0
	if view.TierProgress < expectedProgress-0.01 || view.TierProgress > expectedProgress+0.01 {
		t.Errorf("Expected progress ~%f, got %f", expectedProgress, view.TierProgress)
	}

	// Test standard user working toward trusted
	rm.UpdateUserReputation(2, 50.0)
	view2, err := urs.GetUserReputationView(ctx, 2)
	if err != nil {
		t.Fatalf("Failed to get view: %v", err)
	}

	if view2.NextTierScore != 80.0 {
		t.Errorf("Expected next tier 80.0, got %f", view2.NextTierScore)
	}

	expectedProgress2 := 50.0 / 80.0
	if view2.TierProgress < expectedProgress2-0.01 || view2.TierProgress > expectedProgress2+0.01 {
		t.Errorf("Expected progress ~%f, got %f", expectedProgress2, view2.TierProgress)
	}
}

// TestViolationSummary tests recent violation retrieval
func TestViolationSummary(t *testing.T) {
	db := setupUserReputationTestDB(t)
	rm := NewReputationManager(db)
	at := NewAutoThrottler(db)
	ad := NewAnomalyDetector(db)
	defer rm.Close()
	defer at.Close()
	defer ad.Close()

	urs := NewUserReputationService(db, rm, at, ad)

	// Record some violations
	for i := 0; i < 3; i++ {
		event := &ReputationEvent{
			UserID:        1,
			NodeID:        "test",
			EventType:     "violation",
			ScoreDelta:    -5.0,
			Severity:      2,
			ReasonCode:    "rate_limit_exceeded",
			SourceService: "api",
			Timestamp:     time.Now(),
			CreatedAt:     time.Now(),
		}
		db.Create(event)
	}

	violations := urs.getRecentViolations(1, 10)
	if len(violations) != 3 {
		t.Errorf("Expected 3 violations, got %d", len(violations))
	}

	for _, v := range violations {
		if v.SeverityLabel != "moderate" {
			t.Errorf("Expected moderate severity, got %s", v.SeverityLabel)
		}

		if !v.CanAppeal {
			t.Errorf("Recent violation should be appealable")
		}
	}
}

// TestOldViolationCannotAppeal tests that old violations cannot be appealed
func TestOldViolationCannotAppeal(t *testing.T) {
	db := setupUserReputationTestDB(t)
	rm := NewReputationManager(db)
	at := NewAutoThrottler(db)
	ad := NewAnomalyDetector(db)
	defer rm.Close()
	defer at.Close()
	defer ad.Close()

	urs := NewUserReputationService(db, rm, at, ad)

	// Record old violation (31 days ago)
	oldTime := time.Now().Add(-31 * 24 * time.Hour)
	event := &ReputationEvent{
		UserID:        1,
		NodeID:        "test",
		EventType:     "violation",
		ScoreDelta:    -5.0,
		Severity:      1,
		ReasonCode:    "rate_limit_exceeded",
		SourceService: "api",
		Timestamp:     oldTime,
		CreatedAt:     oldTime,
	}
	db.Create(event)

	violations := urs.getRecentViolations(1, 10)
	if len(violations) != 1 {
		t.Fatalf("Expected 1 violation")
	}

	if violations[0].CanAppeal {
		t.Errorf("Old violation should not be appealable")
	}
}

// TestRateLimitCalculation tests rate limit info calculation
func TestRateLimitCalculation(t *testing.T) {
	db := setupUserReputationTestDB(t)
	rm := NewReputationManager(db)
	at := NewAutoThrottler(db)
	ad := NewAnomalyDetector(db)
	defer rm.Close()
	defer at.Close()
	defer ad.Close()

	urs := NewUserReputationService(db, rm, at, ad)

	// Test for trusted user (1.5x)
	info := urs.getRateLimitInfo(1, 1.5)

	if info.BaseLimit != 1000 {
		t.Errorf("Expected base limit 1000, got %d", info.BaseLimit)
	}

	if info.ReputationMultiplier != 1.5 {
		t.Errorf("Expected rep multiplier 1.5, got %f", info.ReputationMultiplier)
	}

	expectedFinal := int(float64(1000) * 1.5 * info.ThrottleMultiplier)
	if info.FinalLimit != expectedFinal {
		t.Errorf("Expected final limit %d, got %d", expectedFinal, info.FinalLimit)
	}
}

// TestMultiplierVariations tests different reputation multipliers
func TestMultiplierVariations(t *testing.T) {
	db := setupUserReputationTestDB(t)
	rm := NewReputationManager(db)
	at := NewAutoThrottler(db)
	ad := NewAnomalyDetector(db)
	defer rm.Close()
	defer at.Close()
	defer ad.Close()

	urs := NewUserReputationService(db, rm, at, ad)
	ctx := context.Background()

	tests := []struct {
		score       float64
		expectedTier string
		minMultiplier float64
		maxMultiplier float64
	}{
		{10.0, "flagged", 0.4, 0.6},
		{50.0, "standard", 0.9, 1.1},
		{85.0, "trusted", 1.4, 1.6},
		{100.0, "trusted", 1.4, 1.6},
	}

	for i, test := range tests {
		userID := i + 1
		rm.UpdateUserReputation(userID, test.score)

		view, err := urs.GetUserReputationView(ctx, userID)
		if err != nil {
			t.Fatalf("Failed to get view for user %d: %v", userID, err)
		}

		if view.Tier != test.expectedTier {
			t.Errorf("Score %f: expected tier %s, got %s", test.score, test.expectedTier, view.Tier)
		}

		if view.Multiplier < test.minMultiplier || view.Multiplier > test.maxMultiplier {
			t.Errorf("Score %f: expected multiplier %f-%f, got %f", test.score, test.minMultiplier, test.maxMultiplier, view.Multiplier)
		}
	}
}

// BenchmarkGetUserReputationView benchmarks user view retrieval
func BenchmarkGetUserReputationView(b *testing.B) {
	db := setupUserReputationTestDB(&testing.T{})
	rm := NewReputationManager(db)
	at := NewAutoThrottler(db)
	ad := NewAnomalyDetector(db)
	defer rm.Close()
	defer at.Close()
	defer ad.Close()

	urs := NewUserReputationService(db, rm, at, ad)
	ctx := context.Background()

	// Setup user data
	rm.UpdateUserReputation(1, 75.0)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		urs.GetUserReputationView(ctx, 1)
	}
}

// BenchmarkTierExplanationLookup benchmarks explanation retrieval
func BenchmarkTierExplanationLookup(b *testing.B) {
	db := setupUserReputationTestDB(&testing.T{})
	rm := NewReputationManager(db)
	at := NewAutoThrottler(db)
	ad := NewAnomalyDetector(db)
	defer rm.Close()
	defer at.Close()
	defer ad.Close()

	urs := NewUserReputationService(db, rm, at, ad)
	tiers := []string{"flagged", "standard", "trusted", "premium_vip"}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		urs.GetTierExplanation(tiers[i%len(tiers)])
	}
}
