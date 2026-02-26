package rate_limiting

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupTestDB creates an in-memory SQLite database for testing
func setupTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	assert.NoError(t, err)

	// Auto-migrate tables
	err = db.AutoMigrate(&UserReputation{}, &ReputationEvent{}, &VIPUser{})
	assert.NoError(t, err)

	return db
}

// TestReputationManager_CreateUser tests user creation
func TestReputationManager_CreateUser(t *testing.T) {
	db := setupTestDB(t)
	rm := NewReputationManager(db)

	// Get reputation for new user
	rep := rm.GetUserReputation(123)

	// Should have default values
	assert.Equal(t, 123, rep.UserID)
	assert.Equal(t, 50.0, rep.ReputationScore)
	assert.Equal(t, "standard", rep.Tier)
	assert.Equal(t, 0, rep.TotalViolations)
	assert.Equal(t, 0, rep.TotalCleanRequests)
}

// TestReputationManager_RecordViolation tests violation recording
func TestReputationManager_RecordViolation(t *testing.T) {
	db := setupTestDB(t)
	rm := NewReputationManager(db)

	// Record first violation (severity 2)
	err := rm.RecordViolation(123, 2, "Rate limit exceeded")
	assert.NoError(t, err)

	// Check reputation was updated
	rep := rm.GetUserReputation(123)
	assert.Equal(t, 1, rep.TotalViolations)
	assert.Less(t, rep.ReputationScore, 50.0) // Score decreased
	assert.NotNil(t, rep.LastViolation)

	// Record second violation
	err = rm.RecordViolation(123, 2, "Rate limit exceeded again")
	assert.NoError(t, err)

	rep = rm.GetUserReputation(123)
	assert.Equal(t, 2, rep.TotalViolations)
	assert.Less(t, rep.ReputationScore, 40.0) // Score decreased further
}

// TestReputationManager_GetTierForScore tests tier assignment
func TestReputationManager_GetTierForScore(t *testing.T) {
	tests := []struct {
		score    float64
		expected string
	}{
		{5.0, "flagged"},
		{20.0, "flagged"},
		{30.0, "standard"},
		{50.0, "trusted"},
		{75.0, "premium"},
		{90.0, "premium"},
	}

	for _, tt := range tests {
		t.Run("Score_"+string(rune(tt.score)), func(t *testing.T) {
			tier := GetTierForScore(tt.score)
			assert.Equal(t, tt.expected, tier)
		})
	}
}

// TestReputationManager_GetAdaptiveMultiplier tests limit multiplier calculation
func TestReputationManager_GetAdaptiveMultiplier(t *testing.T) {
	tests := []struct {
		score      float64
		minMult    float64
		maxMult    float64
		description string
	}{
		{10.0, 0.4, 0.6, "Very low score"},
		{35.0, 0.7, 0.8, "Low score"},
		{50.0, 0.95, 1.05, "Neutral score"},
		{70.0, 0.95, 1.05, "Good score"},
		{85.0, 1.1, 1.3, "Excellent score"},
	}

	for _, tt := range tests {
		t.Run(tt.description, func(t *testing.T) {
			mult := GetAdaptiveMultiplier(tt.score)
			assert.GreaterOrEqual(t, mult, tt.minMult)
			assert.LessOrEqual(t, mult, tt.maxMult)
		})
	}
}

// TestReputationManager_RecordCleanRequest tests clean request recording
func TestReputationManager_RecordCleanRequest(t *testing.T) {
	db := setupTestDB(t)
	rm := NewReputationManager(db)

	// Get initial reputation
	rep := rm.GetUserReputation(123)
	initialScore := rep.ReputationScore

	// Record 10 clean requests
	for i := 0; i < 10; i++ {
		err := rm.RecordCleanRequest(123)
		assert.NoError(t, err)
	}

	// Check reputation improved
	rep = rm.GetUserReputation(123)
	assert.Equal(t, 10, rep.TotalCleanRequests)
	assert.GreaterOrEqual(t, rep.ReputationScore, initialScore)
}

// TestReputationManager_ApplyDecay tests reputation decay
func TestReputationManager_ApplyDecay(t *testing.T) {
	db := setupTestDB(t)
	rm := NewReputationManager(db)

	// Create user with high score
	rep := rm.GetUserReputation(123)
	db.Model(rep).Update("reputation_score", 90.0)

	// Apply decay
	err := rm.ApplyRepDecay(123)
	assert.NoError(t, err)

	// Score should have decreased towards 50
	rep = rm.GetUserReputation(123)
	assert.Equal(t, 89.0, rep.ReputationScore)

	// Apply decay to low score
	rep = rm.GetUserReputation(124)
	db.Model(rep).Update("reputation_score", 20.0)

	err = rm.ApplyRepDecay(124)
	assert.NoError(t, err)

	rep = rm.GetUserReputation(124)
	assert.Equal(t, 21.0, rep.ReputationScore)
}

// TestReputationManager_GetAdaptiveLimit tests adaptive limit calculation
func TestReputationManager_GetAdaptiveLimit(t *testing.T) {
	db := setupTestDB(t)
	rm := NewReputationManager(db)

	baseLimit := 1000

	// User with good reputation should get higher limit
	rep := rm.GetUserReputation(123)
	db.Model(rep).Update("reputation_score", 85.0)

	limit := rm.GetAdaptiveLimit(123, baseLimit)
	assert.GreaterOrEqual(t, limit, baseLimit) // At least base limit

	// User with poor reputation should get lower limit
	rep = rm.GetUserReputation(124)
	db.Model(rep).Update("reputation_score", 15.0)

	limit = rm.GetAdaptiveLimit(124, baseLimit)
	assert.Less(t, limit, baseLimit) // Less than base limit
}

// TestReputationManager_SetVIPTier tests VIP tier assignment
func TestReputationManager_SetVIPTier(t *testing.T) {
	db := setupTestDB(t)
	rm := NewReputationManager(db)

	// Assign VIP tier
	err := rm.SetVIPTier(123, "premium", 1.5)
	assert.NoError(t, err)

	// Get adaptive limit - should use VIP multiplier
	baseLimit := 1000
	limit := rm.GetAdaptiveLimit(123, baseLimit)
	assert.Equal(t, 1500, limit) // 1000 * 1.5
}

// TestReputationManager_RemoveVIPTier tests VIP tier removal
func TestReputationManager_RemoveVIPTier(t *testing.T) {
	db := setupTestDB(t)
	rm := NewReputationManager(db)

	// Assign VIP tier
	err := rm.SetVIPTier(123, "premium", 1.5)
	assert.NoError(t, err)

	// Remove VIP tier
	err = rm.RemoveVIPTier(123)
	assert.NoError(t, err)

	// Limit should now be based on reputation, not VIP
	rep := rm.GetUserReputation(123)
	baseLimit := 1000
	limit := rm.GetAdaptiveLimit(123, baseLimit)

	// Should be different from VIP multiplied limit
	assert.Less(t, limit, 1500)
}

// TestReputationManager_IsUserFlagged tests flag detection
func TestReputationManager_IsUserFlagged(t *testing.T) {
	flagged := IsUserFlagged(25.0)
	assert.True(t, flagged)

	notFlagged := IsUserFlagged(50.0)
	assert.False(t, notFlagged)
}

// TestReputationManager_IsUserSuspended tests suspension detection
func TestReputationManager_IsUserSuspended(t *testing.T) {
	suspended := IsUserSuspended(5.0)
	assert.True(t, suspended)

	notSuspended := IsUserSuspended(25.0)
	assert.False(t, notSuspended)
}

// TestReputationManager_GetRepHistory tests history retrieval
func TestReputationManager_GetRepHistory(t *testing.T) {
	db := setupTestDB(t)
	rm := NewReputationManager(db)

	// Record some violations
	rm.RecordViolation(123, 2, "Test violation 1")
	time.Sleep(100 * time.Millisecond)
	rm.RecordViolation(123, 1, "Test violation 2")

	// Get history from last 7 days
	history, err := rm.GetRepHistory(123, 7)
	assert.NoError(t, err)
	assert.Greater(t, len(history), 0)
	assert.Equal(t, "violation", history[0].EventType)
}

// TestReputationManager_CacheInvalidation tests cache invalidation
func TestReputationManager_CacheInvalidation(t *testing.T) {
	db := setupTestDB(t)
	rm := NewReputationManager(db)

	// Load reputation (should be cached)
	rep1 := rm.GetUserReputation(123)
	cachedScore := rep1.ReputationScore

	// Record violation (should invalidate cache)
	rm.RecordViolation(123, 2, "Test")

	// Load again (should be fresh from DB)
	rep2 := rm.GetUserReputation(123)
	assert.NotEqual(t, cachedScore, rep2.ReputationScore)
	assert.Less(t, rep2.ReputationScore, cachedScore)
}

// BenchmarkReputationManager_GetUserReputation benchmarks reputation lookup
func BenchmarkReputationManager_GetUserReputation(b *testing.B) {
	db := setupTestDB(&testing.T{})
	rm := NewReputationManager(db)

	// Pre-populate some users
	for i := 1; i <= 100; i++ {
		rm.GetUserReputation(i)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		rm.GetUserReputation(i % 100)
	}
}

// BenchmarkReputationManager_RecordViolation benchmarks violation recording
func BenchmarkReputationManager_RecordViolation(b *testing.B) {
	db := setupTestDB(&testing.T{})
	rm := NewReputationManager(db)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		rm.RecordViolation(i%100, 2, "Benchmark violation")
	}
}

// BenchmarkReputationManager_GetAdaptiveLimit benchmarks limit calculation
func BenchmarkReputationManager_GetAdaptiveLimit(b *testing.B) {
	db := setupTestDB(&testing.T{})
	rm := NewReputationManager(db)

	for i := 1; i <= 100; i++ {
		rm.GetUserReputation(i)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		rm.GetAdaptiveLimit(i%100, 1000)
	}
}
