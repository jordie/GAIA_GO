package rate_limiting

import (
	"testing"
	"time"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
)

// IntegrationTestDB creates a test database connection
func IntegrationTestDB(t *testing.T) *gorm.DB {
	// Use test database configuration
	dsn := "user=postgres password=postgres dbname=gaia_go_test host=localhost port=5432 sslmode=disable"
	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{})
	if err != nil {
		t.Skipf("Could not connect to test database: %v", err)
	}
	return db
}

// TestIntegrationReputationSystem tests end-to-end reputation functionality
func TestIntegrationReputationSystem(t *testing.T) {
	db := IntegrationTestDB(t)

	// Clean test data
	db.Table("reputation_events").Where("user_id >= ?", 10000).Delete(nil)
	db.Table("reputation_scores").Where("user_id >= ?", 10000).Delete(nil)

	rm := NewReputationManager(db)
	userID := 10001

	// Test 1: Create user with initial reputation
	t.Run("CreateUserReputation", func(t *testing.T) {
		rep, err := rm.GetUserReputation(userID)
		if err != nil {
			t.Fatalf("Failed to get user reputation: %v", err)
		}

		if rep.Score != 50 {
			t.Errorf("Expected initial score 50, got %d", rep.Score)
		}
		if rep.Tier != "standard" {
			t.Errorf("Expected tier 'standard', got %s", rep.Tier)
		}
		if rep.Multiplier != 1.0 {
			t.Errorf("Expected multiplier 1.0, got %f", rep.Multiplier)
		}
	})

	// Test 2: Record violations and check tier changes
	t.Run("RecordViolationsAndTierChange", func(t *testing.T) {
		// Record multiple violations (severity 3 = 9 points each)
		for i := 0; i < 5; i++ {
			err := rm.RecordViolation(userID, 3, "Test violation")
			if err != nil {
				t.Fatalf("Failed to record violation: %v", err)
			}
		}

		// After 5 violations of severity 3, score should be: 50 - (5 * 9) = 5
		rep, err := rm.GetUserReputation(userID)
		if err != nil {
			t.Fatalf("Failed to get user reputation: %v", err)
		}

		if rep.Score != 5 {
			t.Errorf("Expected score 5, got %d", rep.Score)
		}
		if rep.Tier != "flagged" {
			t.Errorf("Expected tier 'flagged', got %s", rep.Tier)
		}
		if rep.Multiplier != 0.5 {
			t.Errorf("Expected multiplier 0.5, got %f", rep.Multiplier)
		}
	})

	// Test 3: Check adaptive limit calculation
	t.Run("AdaptiveLimitCalculation", func(t *testing.T) {
		baseLimit := 1000
		adjustedLimit := rm.GetAdaptiveLimit(userID, baseLimit)

		expectedLimit := int(float64(baseLimit) * 0.5) // 500
		if adjustedLimit != expectedLimit {
			t.Errorf("Expected adjusted limit %d, got %d", expectedLimit, adjustedLimit)
		}
	})

	// Test 4: Set VIP tier
	t.Run("SetVIPTier", func(t *testing.T) {
		expiresAt := time.Now().AddDate(0, 0, 30)
		err := rm.SetVIPTier(userID, "premium", &expiresAt, "Testing VIP")
		if err != nil {
			t.Fatalf("Failed to set VIP tier: %v", err)
		}

		rep, err := rm.GetUserReputation(userID)
		if err != nil {
			t.Fatalf("Failed to get user reputation: %v", err)
		}

		if rep.VIPTier != "premium" {
			t.Errorf("Expected VIP tier 'premium', got %s", rep.VIPTier)
		}
		if rep.Multiplier != 2.0 {
			t.Errorf("Expected multiplier 2.0 for premium VIP, got %f", rep.Multiplier)
		}
	})

	// Test 5: VIP multiplier overrides reputation multiplier
	t.Run("VIPMultiplierOverride", func(t *testing.T) {
		baseLimit := 1000
		adjustedLimit := rm.GetAdaptiveLimit(userID, baseLimit)

		expectedLimit := int(float64(baseLimit) * 2.0) // 2000 (VIP premium)
		if adjustedLimit != expectedLimit {
			t.Errorf("Expected VIP-adjusted limit %d, got %d", expectedLimit, adjustedLimit)
		}
	})

	// Test 6: Remove VIP tier
	t.Run("RemoveVIPTier", func(t *testing.T) {
		err := rm.RemoveVIPTier(userID)
		if err != nil {
			t.Fatalf("Failed to remove VIP tier: %v", err)
		}

		rep, err := rm.GetUserReputation(userID)
		if err != nil {
			t.Fatalf("Failed to get user reputation: %v", err)
		}

		if rep.VIPTier != "" {
			t.Errorf("Expected empty VIP tier, got %s", rep.VIPTier)
		}
	})

	// Test 7: Record clean requests
	t.Run("RecordCleanRequests", func(t *testing.T) {
		initialRep, _ := rm.GetUserReputation(userID)
		initialScore := initialRep.Score

		// Record 10 clean requests
		for i := 0; i < 10; i++ {
			err := rm.RecordCleanRequest(userID)
			if err != nil {
				t.Fatalf("Failed to record clean request: %v", err)
			}
		}

		// Score should increase by 10
		finalRep, _ := rm.GetUserReputation(userID)
		if finalRep.Score != initialScore+10 {
			t.Errorf("Expected score %d, got %d", initialScore+10, finalRep.Score)
		}
	})

	// Test 8: Admin manual reputation override
	t.Run("AdminOverride", func(t *testing.T) {
		err := rm.SetUserReputation(userID, 75, "Admin manual adjustment")
		if err != nil {
			t.Fatalf("Failed to set reputation: %v", err)
		}

		rep, err := rm.GetUserReputation(userID)
		if err != nil {
			t.Fatalf("Failed to get user reputation: %v", err)
		}

		if rep.Score != 75 {
			t.Errorf("Expected score 75, got %d", rep.Score)
		}
		if rep.Tier != "trusted" {
			t.Errorf("Expected tier 'trusted', got %s", rep.Tier)
		}
	})

	// Test 9: Get reputation history
	t.Run("GetRepHistory", func(t *testing.T) {
		history, err := rm.GetRepHistory(userID, 7)
		if err != nil {
			t.Fatalf("Failed to get reputation history: %v", err)
		}

		if len(history) == 0 {
			t.Errorf("Expected history events, got none")
		}

		// Check that we have violation events
		hasViolation := false
		for _, event := range history {
			if event.EventType == "violation" {
				hasViolation = true
				break
			}
		}

		if !hasViolation {
			t.Errorf("Expected violation events in history")
		}
	})

	// Test 10: Get user events with filtering
	t.Run("GetUserEventsWithFilter", func(t *testing.T) {
		events, total, err := rm.GetUserEvents(userID, 20, "violation")
		if err != nil {
			t.Fatalf("Failed to get user events: %v", err)
		}

		if total == 0 {
			t.Errorf("Expected violation events, got none")
		}

		// All events should be violations
		for _, event := range events {
			if event.EventType != "violation" {
				t.Errorf("Expected violation event, got %s", event.EventType)
			}
		}
	})

	// Test 11: Get reputation statistics
	t.Run("GetRepStats", func(t *testing.T) {
		stats, err := rm.GetRepStats()
		if err != nil {
			t.Fatalf("Failed to get reputation stats: %v", err)
		}

		if stats["total_users"] == nil {
			t.Errorf("Expected total_users in stats")
		}

		// Check that our test user is counted
		totalUsers := stats["total_users"].(int)
		if totalUsers < 1 {
			t.Errorf("Expected at least 1 user in stats")
		}
	})

	// Test 12: Get all users with pagination
	t.Run("GetAllUsersWithPagination", func(t *testing.T) {
		users, total, err := rm.GetAllUsers(1, 10)
		if err != nil {
			t.Fatalf("Failed to get all users: %v", err)
		}

		if total == 0 {
			t.Errorf("Expected users in database")
		}

		if len(users) == 0 {
			t.Errorf("Expected paginated results")
		}

		// Verify our test user is in results
		foundTestUser := false
		for _, u := range users {
			if u.UserID == userID {
				foundTestUser = true
				if u.Score != 75 {
					t.Errorf("Expected test user score 75, got %d", u.Score)
				}
				break
			}
		}

		if !foundTestUser {
			t.Logf("Test user not in first page of results")
		}
	})

	// Test 13: Reputation decay
	t.Run("ReputationDecay", func(t *testing.T) {
		// Set score above neutral
		rm.SetUserReputation(userID, 90, "Setting up for decay test")

		rep, _ := rm.GetUserReputation(userID)
		if rep.Score != 90 {
			t.Errorf("Setup failed: expected score 90, got %d", rep.Score)
		}

		// Apply decay
		err := rm.ApplyRepDecay(userID)
		if err != nil {
			t.Fatalf("Failed to apply decay: %v", err)
		}

		// Score should decrease by 5 (decaying towards neutral 50)
		decayedRep, _ := rm.GetUserReputation(userID)
		if decayedRep.Score != 85 {
			t.Errorf("Expected score 85 after decay, got %d", decayedRep.Score)
		}
	})

	// Test 14: Cache invalidation
	t.Run("CacheInvalidation", func(t *testing.T) {
		// Get reputation (loads into cache)
		rep1, _ := rm.GetUserReputation(userID)

		// Update reputation directly in DB
		rm.SetUserReputation(userID, 95, "Testing cache")

		// Get reputation again (should get fresh from DB)
		rep2, _ := rm.GetUserReputation(userID)

		if rep1.Score == rep2.Score && rep2.Score != 95 {
			t.Errorf("Cache was not invalidated after update")
		}
	})

	// Test 15: Tier-specific multipliers
	t.Run("TierMultipliers", func(t *testing.T) {
		testCases := []struct {
			score      int
			expectTier string
			minMult    float64
			maxMult    float64
		}{
			{10, "flagged", 0.4, 0.6},
			{20, "flagged", 0.4, 0.6},
			{50, "standard", 0.9, 1.1},
			{80, "trusted", 1.4, 1.6},
			{95, "trusted", 1.6, 1.8},
		}

		for i, tc := range testCases {
			testUser := 20000 + i
			rm.SetUserReputation(testUser, tc.score, "Tier test")
			rep, _ := rm.GetUserReputation(testUser)

			if rep.Tier != tc.expectTier {
				t.Errorf("Score %d: expected tier %s, got %s", tc.score, tc.expectTier, rep.Tier)
			}

			if rep.Multiplier < tc.minMult || rep.Multiplier > tc.maxMult {
				t.Errorf("Score %d: multiplier %f not in range [%f, %f]",
					tc.score, rep.Multiplier, tc.minMult, tc.maxMult)
			}
		}
	})

	t.Logf("All integration tests completed successfully")
}

// BenchmarkReputationLookup benchmarks reputation lookup performance
func BenchmarkReputationLookup(b *testing.B) {
	db := IntegrationTestDB(&testing.T{})
	rm := NewReputationManager(db)
	userID := 30001

	// Create test user
	rm.GetUserReputation(userID)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		rm.GetUserReputation(userID)
	}
}

// BenchmarkViolationRecording benchmarks violation recording
func BenchmarkViolationRecording(b *testing.B) {
	db := IntegrationTestDB(&testing.T{})
	rm := NewReputationManager(db)
	userID := 30002

	// Create test user
	rm.GetUserReputation(userID)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		rm.RecordViolation(userID, 2, "Test violation")
	}
}

// BenchmarkAdaptiveLimitCalculation benchmarks limit adjustment
func BenchmarkAdaptiveLimitCalculation(b *testing.B) {
	db := IntegrationTestDB(&testing.T{})
	rm := NewReputationManager(db)
	userID := 30003

	// Create test user
	rm.GetUserReputation(userID)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		rm.GetAdaptiveLimit(userID, 1000)
	}
}
