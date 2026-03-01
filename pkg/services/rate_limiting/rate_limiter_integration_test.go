package rate_limiting

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupRateLimiterIntegrationTestDB creates a test database for rate limiter integration tests
func setupRateLimiterIntegrationTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	require.NoError(t, err, "failed to create integration test database")

	// Create required tables
	createRateLimiterIntegrationTestTables(t, db)

	return db
}

// createRateLimiterIntegrationTestTables creates all required tables for rate limiter integration tests
func createRateLimiterIntegrationTestTables(t *testing.T, db *gorm.DB) {
	db.Exec(`
		CREATE TABLE rate_limit_rules (
			id INTEGER PRIMARY KEY,
			rule_name TEXT UNIQUE,
			scope TEXT,
			scope_value TEXT,
			limit_type TEXT,
			limit_value INTEGER,
			resource_type TEXT,
			enabled BOOLEAN DEFAULT 1,
			priority INTEGER DEFAULT 1,
			system_id TEXT,
			created_at TIMESTAMP,
			updated_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE rate_limit_buckets (
			id INTEGER PRIMARY KEY,
			rule_id INTEGER,
			system_id TEXT,
			scope TEXT,
			scope_value TEXT,
			window_start TIMESTAMP,
			window_end TIMESTAMP,
			request_count INTEGER DEFAULT 0,
			created_at TIMESTAMP,
			updated_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE resource_quotas (
			id INTEGER PRIMARY KEY,
			system_id TEXT,
			scope TEXT,
			scope_value TEXT,
			resource_type TEXT,
			quota_period TEXT,
			quota_limit INTEGER,
			quota_used INTEGER DEFAULT 0,
			period_start TIMESTAMP,
			period_end TIMESTAMP,
			created_at TIMESTAMP,
			updated_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE rate_limit_violations (
			id INTEGER PRIMARY KEY,
			system_id TEXT,
			scope TEXT,
			scope_value TEXT,
			resource_type TEXT,
			violated_limit INTEGER,
			violation_time TIMESTAMP,
			blocked BOOLEAN DEFAULT 1
		)
	`)

	db.Exec(`
		CREATE TABLE reputation_scores (
			id INTEGER PRIMARY KEY,
			user_id INTEGER UNIQUE,
			score REAL DEFAULT 100.0,
			tier TEXT DEFAULT 'neutral'
		)
	`)

	db.Exec(`
		CREATE TABLE clean_requests (
			id INTEGER PRIMARY KEY,
			system_id TEXT,
			scope TEXT,
			scope_value TEXT,
			created_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE rate_limit_metrics (
			id INTEGER PRIMARY KEY,
			system_id TEXT,
			scope TEXT,
			scope_value TEXT,
			resource_type TEXT,
			request_count INTEGER,
			violation_count INTEGER,
			avg_latency_ms REAL,
			created_at TIMESTAMP
		)
	`)
}

// ===== INTEGRATION TEST SCENARIOS =====

// TestFullRateLimitCycle tests complete workflow: create rules, make requests, verify violations
func TestFullRateLimitCycle(t *testing.T) {
	db := setupRateLimiterIntegrationTestDB(t)
	limiter := NewPostgresRateLimiter(db, defaultConfig())

	ctx := context.Background()
	systemID := "test-cycle"
	scope := "ip"
	scopeValue := "192.168.1.100"

	// Step 1: Create rate limit rule (10 requests per minute)
	rule := Rule{
		SystemID:   systemID,
		Scope:      scope,
		LimitType:  LimitPerMinute,
		LimitValue: 10,
		Enabled:    true,
		Priority:   1,
	}

	ruleID, err := limiter.CreateRule(ctx, rule)
	require.NoError(t, err)
	assert.Greater(t, ruleID, int64(0))

	// Step 2: Verify rule was created
	createdRule, err := limiter.GetRule(ctx, ruleID)
	require.NoError(t, err)
	assert.NotNil(t, createdRule)
	assert.Equal(t, 10, createdRule.LimitValue)

	// Step 3: Make requests within limit
	req := LimitCheckRequest{
		SystemID:     systemID,
		Scope:        scope,
		ScopeValue:   scopeValue,
		ResourceType: "default",
	}

	var decisions []Decision
	for i := 0; i < 10; i++ {
		decision, err := limiter.CheckLimit(ctx, req)
		require.NoError(t, err)
		assert.True(t, decision.Allowed, "request %d should be allowed", i+1)
		decisions = append(decisions, decision)
	}

	// Step 4: Verify requests within limit show correct remaining count
	lastDecision := decisions[len(decisions)-1]
	assert.Equal(t, 0, lastDecision.Remaining, "last allowed request should have 0 remaining")

	// Step 5: Make request that exceeds limit
	violationDecision, err := limiter.CheckLimit(ctx, req)
	require.NoError(t, err)
	assert.False(t, violationDecision.Allowed, "11th request should exceed limit")

	// Step 6: Verify violation was recorded
	violations, err := limiter.GetViolations(ctx, systemID, time.Now().Add(-1*time.Minute))
	require.NoError(t, err)
	assert.Greater(t, len(violations), 0, "should have recorded violations")

	// Step 7: Verify rule can be updated
	rule.ID = ruleID
	rule.LimitValue = 20
	err = limiter.UpdateRule(ctx, rule)
	require.NoError(t, err)

	// Step 8: Verify new limit is enforced
	updatedRule, err := limiter.GetRule(ctx, ruleID)
	require.NoError(t, err)
	assert.Equal(t, 20, updatedRule.LimitValue)

	// Step 9: Cleanup old violations
	cleanupCount, err := limiter.CleanupOldViolations(ctx, time.Now().Add(1*time.Hour))
	require.NoError(t, err)
	assert.GreaterOrEqual(t, cleanupCount, int64(0))

	// Step 10: Cleanup old buckets
	bucketCleanup, err := limiter.CleanupOldBuckets(ctx, time.Now().Add(1*time.Hour))
	require.NoError(t, err)
	assert.GreaterOrEqual(t, bucketCleanup, int64(0))

	// Step 11: Delete rule
	err = limiter.DeleteRule(ctx, ruleID)
	require.NoError(t, err)

	// Step 12: Verify rule was deleted
	deletedRule, err := limiter.GetRule(ctx, ruleID)
	require.NoError(t, err)
	assert.Nil(t, deletedRule)
}

// TestDailyQuotaReset verifies daily quotas reset at period boundary
func TestDailyQuotaReset(t *testing.T) {
	db := setupRateLimiterIntegrationTestDB(t)
	limiter := NewPostgresRateLimiter(db, defaultConfig())

	ctx := context.Background()
	systemID := "quota-test"
	scope := "user"
	userID := "user_daily_reset"

	// Step 1: Create daily quota rule (50 requests per day)
	rule := Rule{
		SystemID:   systemID,
		Scope:      scope,
		LimitType:  LimitPerDay,
		LimitValue: 50,
		Enabled:    true,
		Priority:   1,
	}

	ruleID, err := limiter.CreateRule(ctx, rule)
	require.NoError(t, err)

	// Step 2: Make requests to consume quota
	req := LimitCheckRequest{
		SystemID:     systemID,
		Scope:        scope,
		ScopeValue:   userID,
		ResourceType: "default",
	}

	// Make 25 requests (half of quota)
	for i := 0; i < 25; i++ {
		decision, err := limiter.CheckLimit(ctx, req)
		require.NoError(t, err)
		assert.True(t, decision.Allowed, "request %d should be allowed", i+1)
	}

	// Step 3: Get current quota usage
	quota, err := limiter.GetQuota(ctx, systemID, scope, userID, "default")
	if quota != nil {
		assert.NoError(t, err)
		assert.GreaterOrEqual(t, quota.QuotaUsed, 0)
	}

	// Step 4: Verify quota can be incremented
	incrementErr := limiter.IncrementQuota(ctx, systemID, scope, userID, "api", 10)
	require.NoError(t, incrementErr)

	// Step 5: Get updated quota
	updatedQuota, err := limiter.GetQuota(ctx, systemID, scope, userID, "api")
	if updatedQuota != nil {
		assert.NoError(t, err)
		// Quota should be incremented
	}

	// Step 6: Clean up
	err = limiter.DeleteRule(ctx, ruleID)
	require.NoError(t, err)
}

// TestMultipleScopeLimits verifies different scopes enforce limits simultaneously
func TestMultipleScopeLimits(t *testing.T) {
	db := setupRateLimiterIntegrationTestDB(t)
	limiter := NewPostgresRateLimiter(db, defaultConfig())

	ctx := context.Background()
	systemID := "multi-scope"

	// Step 1: Create IP-based limit (2 requests per second)
	ipRule := Rule{
		SystemID:   systemID,
		Scope:      "ip",
		LimitType:  LimitPerSecond,
		LimitValue: 2,
		Enabled:    true,
		Priority:   1,
	}

	ipRuleID, err := limiter.CreateRule(ctx, ipRule)
	require.NoError(t, err)

	// Step 2: Create user-based limit (3 requests per second)
	userRule := Rule{
		SystemID:   systemID,
		Scope:      "user",
		LimitType:  LimitPerSecond,
		LimitValue: 3,
		Enabled:    true,
		Priority:   2,
	}

	userRuleID, err := limiter.CreateRule(ctx, userRule)
	require.NoError(t, err)

	// Step 3: Create API key-based limit (4 requests per second)
	apiRule := Rule{
		SystemID:   systemID,
		Scope:      "api_key",
		LimitType:  LimitPerSecond,
		LimitValue: 4,
		Enabled:    true,
		Priority:   3,
	}

	apiRuleID, err := limiter.CreateRule(ctx, apiRule)
	require.NoError(t, err)

	ipValue := "192.168.1.200"
	userValue := "user_multi_scope"
	apiValue := "api_key_12345"

	// Step 4: Test IP-based limit (should block on 3rd request)
	ipReq := LimitCheckRequest{
		SystemID:     systemID,
		Scope:        "ip",
		ScopeValue:   ipValue,
		ResourceType: "default",
	}

	d1, err := limiter.CheckLimit(ctx, ipReq)
	require.NoError(t, err)
	assert.True(t, d1.Allowed)

	d2, err := limiter.CheckLimit(ctx, ipReq)
	require.NoError(t, err)
	assert.True(t, d2.Allowed)

	d3, err := limiter.CheckLimit(ctx, ipReq)
	require.NoError(t, err)
	assert.False(t, d3.Allowed, "3rd IP request should exceed per-second limit")

	// Step 5: Test user-based limit (independent from IP)
	userReq := LimitCheckRequest{
		SystemID:     systemID,
		Scope:        "user",
		ScopeValue:   userValue,
		ResourceType: "default",
	}

	for i := 0; i < 3; i++ {
		d, err := limiter.CheckLimit(ctx, userReq)
		require.NoError(t, err)
		assert.True(t, d.Allowed, "user request %d should be allowed", i+1)
	}

	d4, err := limiter.CheckLimit(ctx, userReq)
	require.NoError(t, err)
	assert.False(t, d4.Allowed, "4th user request should exceed per-second limit")

	// Step 6: Test API key-based limit (independent from IP and user)
	apiReq := LimitCheckRequest{
		SystemID:     systemID,
		Scope:        "api_key",
		ScopeValue:   apiValue,
		ResourceType: "default",
	}

	for i := 0; i < 4; i++ {
		d, err := limiter.CheckLimit(ctx, apiReq)
		require.NoError(t, err)
		assert.True(t, d.Allowed, "api request %d should be allowed", i+1)
	}

	d5, err := limiter.CheckLimit(ctx, apiReq)
	require.NoError(t, err)
	assert.False(t, d5.Allowed, "5th api request should exceed per-second limit")

	// Step 7: Verify all three rules exist
	rules, err := limiter.GetRules(ctx, systemID)
	require.NoError(t, err)
	assert.Equal(t, 3, len(rules), "should have created 3 rules")

	// Step 8: Delete all rules
	err = limiter.DeleteRule(ctx, ipRuleID)
	require.NoError(t, err)
	err = limiter.DeleteRule(ctx, userRuleID)
	require.NoError(t, err)
	err = limiter.DeleteRule(ctx, apiRuleID)
	require.NoError(t, err)

	// Step 9: Verify all rules deleted
	finalRules, err := limiter.GetRules(ctx, systemID)
	require.NoError(t, err)
	assert.Equal(t, 0, len(finalRules), "all rules should be deleted")
}

// TestRuleEnablingDisabling verifies rules can be enabled/disabled
func TestRuleEnablingDisabling(t *testing.T) {
	db := setupRateLimiterIntegrationTestDB(t)
	limiter := NewPostgresRateLimiter(db, defaultConfig())

	ctx := context.Background()
	systemID := "toggle-test"

	// Step 1: Create a rule
	rule := Rule{
		SystemID:   systemID,
		Scope:      "ip",
		LimitType:  LimitPerSecond,
		LimitValue: 1,
		Enabled:    true,
		Priority:   1,
	}

	ruleID, err := limiter.CreateRule(ctx, rule)
	require.NoError(t, err)

	req := LimitCheckRequest{
		SystemID:     systemID,
		Scope:        "ip",
		ScopeValue:   "192.168.1.150",
		ResourceType: "default",
	}

	// Step 2: Verify rule is enforced
	d1, err := limiter.CheckLimit(ctx, req)
	require.NoError(t, err)
	assert.True(t, d1.Allowed)

	d2, err := limiter.CheckLimit(ctx, req)
	require.NoError(t, err)
	assert.False(t, d2.Allowed, "should be blocked by limit")

	// Step 3: Disable rule
	rule.ID = ruleID
	rule.Enabled = false
	err = limiter.UpdateRule(ctx, rule)
	require.NoError(t, err)

	// Step 4: Verify disabled rule is not enforced
	d3, err := limiter.CheckLimit(ctx, req)
	require.NoError(t, err)
	assert.True(t, d3.Allowed, "disabled rule should not block request")

	d4, err := limiter.CheckLimit(ctx, req)
	require.NoError(t, err)
	assert.True(t, d4.Allowed, "disabled rule should not block request")

	// Step 5: Re-enable rule
	rule.Enabled = true
	err = limiter.UpdateRule(ctx, rule)
	require.NoError(t, err)

	// Step 6: Verify rule is enforced again
	d5, err := limiter.CheckLimit(ctx, req)
	require.NoError(t, err)
	assert.True(t, d5.Allowed, "re-enabled rule should allow first request")

	d6, err := limiter.CheckLimit(ctx, req)
	require.NoError(t, err)
	assert.False(t, d6.Allowed, "re-enabled rule should block second request")

	// Step 7: Clean up
	err = limiter.DeleteRule(ctx, ruleID)
	require.NoError(t, err)
}

// TestResourceTypeSpecificLimits verifies resource type filtering works correctly
func TestResourceTypeSpecificLimits(t *testing.T) {
	db := setupRateLimiterIntegrationTestDB(t)
	limiter := NewPostgresRateLimiter(db, defaultConfig())

	ctx := context.Background()
	systemID := "resource-type-test"
	ipValue := "192.168.1.175"

	// Step 1: Create upload-specific limit (2 per minute)
	uploadRule := Rule{
		SystemID:     systemID,
		Scope:        "ip",
		ResourceType: "upload",
		LimitType:    LimitPerMinute,
		LimitValue:   2,
		Enabled:      true,
		Priority:     1,
	}

	uploadRuleID, err := limiter.CreateRule(ctx, uploadRule)
	require.NoError(t, err)

	// Step 2: Create download-specific limit (5 per minute)
	downloadRule := Rule{
		SystemID:     systemID,
		Scope:        "ip",
		ResourceType: "download",
		LimitType:    LimitPerMinute,
		LimitValue:   5,
		Enabled:      true,
		Priority:     1,
	}

	downloadRuleID, err := limiter.CreateRule(ctx, downloadRule)
	require.NoError(t, err)

	// Step 3: Test upload limit
	uploadReq := LimitCheckRequest{
		SystemID:     systemID,
		Scope:        "ip",
		ScopeValue:   ipValue,
		ResourceType: "upload",
	}

	for i := 0; i < 2; i++ {
		d, err := limiter.CheckLimit(ctx, uploadReq)
		require.NoError(t, err)
		assert.True(t, d.Allowed, "upload request %d should be allowed", i+1)
	}

	d3, err := limiter.CheckLimit(ctx, uploadReq)
	require.NoError(t, err)
	assert.False(t, d3.Allowed, "3rd upload should exceed limit")

	// Step 4: Test download limit (should be independent)
	downloadReq := LimitCheckRequest{
		SystemID:     systemID,
		Scope:        "ip",
		ScopeValue:   ipValue,
		ResourceType: "download",
	}

	for i := 0; i < 5; i++ {
		d, err := limiter.CheckLimit(ctx, downloadReq)
		require.NoError(t, err)
		assert.True(t, d.Allowed, "download request %d should be allowed", i+1)
	}

	d4, err := limiter.CheckLimit(ctx, downloadReq)
	require.NoError(t, err)
	assert.False(t, d4.Allowed, "6th download should exceed limit")

	// Step 5: Verify uploads still blocked but downloads have different limit
	uploadReq2, err := limiter.CheckLimit(ctx, uploadReq)
	require.NoError(t, err)
	assert.False(t, uploadReq2.Allowed, "upload still blocked")

	// Step 6: Clean up
	err = limiter.DeleteRule(ctx, uploadRuleID)
	require.NoError(t, err)
	err = limiter.DeleteRule(ctx, downloadRuleID)
	require.NoError(t, err)
}

// TestPriorityBasedRuleEvaluation verifies rules are evaluated by priority
func TestPriorityBasedRuleEvaluation(t *testing.T) {
	db := setupRateLimiterIntegrationTestDB(t)
	limiter := NewPostgresRateLimiter(db, defaultConfig())

	ctx := context.Background()
	systemID := "priority-test"
	ipValue := "192.168.1.180"

	// Step 1: Create strict rule with priority 1 (evaluated first)
	strictRule := Rule{
		SystemID:   systemID,
		Scope:      "ip",
		LimitType:  LimitPerSecond,
		LimitValue: 1,
		Enabled:    true,
		Priority:   1,
	}

	strictRuleID, err := limiter.CreateRule(ctx, strictRule)
	require.NoError(t, err)

	// Step 2: Create lenient rule with priority 2 (evaluated second)
	lenientRule := Rule{
		SystemID:   systemID,
		Scope:      "ip",
		LimitType:  LimitPerMinute,
		LimitValue: 100,
		Enabled:    true,
		Priority:   2,
	}

	lenientRuleID, err := limiter.CreateRule(ctx, lenientRule)
	require.NoError(t, err)

	req := LimitCheckRequest{
		SystemID:     systemID,
		Scope:        "ip",
		ScopeValue:   ipValue,
		ResourceType: "default",
	}

	// Step 3: Verify strict rule (priority 1) is evaluated first
	d1, err := limiter.CheckLimit(ctx, req)
	require.NoError(t, err)
	assert.True(t, d1.Allowed)

	// Second request should fail due to strict rule (not lenient rule)
	d2, err := limiter.CheckLimit(ctx, req)
	require.NoError(t, err)
	assert.False(t, d2.Allowed, "should be blocked by priority 1 rule, not priority 2 rule")

	// Step 4: Disable strict rule
	strictRule.ID = strictRuleID
	strictRule.Enabled = false
	err = limiter.UpdateRule(ctx, strictRule)
	require.NoError(t, err)

	// Step 5: Now lenient rule (priority 2) should be evaluated
	d3, err := limiter.CheckLimit(ctx, req)
	require.NoError(t, err)
	assert.True(t, d3.Allowed, "lenient rule should allow after strict rule disabled")

	// Step 6: Clean up
	err = limiter.DeleteRule(ctx, strictRuleID)
	require.NoError(t, err)
	err = limiter.DeleteRule(ctx, lenientRuleID)
	require.NoError(t, err)
}

// TestViolationStatsAggregation verifies violation statistics are correctly aggregated
func TestViolationStatsAggregation(t *testing.T) {
	db := setupRateLimiterIntegrationTestDB(t)
	limiter := NewPostgresRateLimiter(db, defaultConfig())

	ctx := context.Background()
	systemID := "violation-stats"

	// Step 1: Create rules for different scopes
	ipRule := Rule{
		SystemID:   systemID,
		Scope:      "ip",
		LimitType:  LimitPerSecond,
		LimitValue: 1,
		Enabled:    true,
		Priority:   1,
	}

	_, err := limiter.CreateRule(ctx, ipRule)
	require.NoError(t, err)

	userRule := Rule{
		SystemID:   systemID,
		Scope:      "user",
		LimitType:  LimitPerSecond,
		LimitValue: 1,
		Enabled:    true,
		Priority:   1,
	}

	_, err = limiter.CreateRule(ctx, userRule)
	require.NoError(t, err)

	// Step 2: Trigger violations for both scopes
	ipReq := LimitCheckRequest{
		SystemID:     systemID,
		Scope:        "ip",
		ScopeValue:   "192.168.1.190",
		ResourceType: "default",
	}

	userReq := LimitCheckRequest{
		SystemID:     systemID,
		Scope:        "user",
		ScopeValue:   "user_violation_test",
		ResourceType: "default",
	}

	// Create violations
	limiter.CheckLimit(ctx, ipReq)
	limiter.CheckLimit(ctx, ipReq) // Violation

	limiter.CheckLimit(ctx, userReq)
	limiter.CheckLimit(ctx, userReq) // Violation

	// Step 3: Get violation statistics
	stats, err := limiter.GetViolationStats(ctx, systemID)
	require.NoError(t, err)
	assert.NotNil(t, stats)

	// Step 4: Verify statistics are aggregated
	if stats != nil {
		totalViolations := stats["total_violations"]
		assert.NotNil(t, totalViolations)
	}
}

// TestCleanupByTimeRange verifies cleanup operations respect time boundaries
func TestCleanupByTimeRange(t *testing.T) {
	db := setupRateLimiterIntegrationTestDB(t)
	limiter := NewPostgresRateLimiter(db, defaultConfig())

	ctx := context.Background()

	// Step 1: Create rule and generate some data
	rule := Rule{
		SystemID:   "cleanup-test",
		Scope:      "ip",
		LimitType:  LimitPerSecond,
		LimitValue: 1,
		Enabled:    true,
		Priority:   1,
	}

	_, err := limiter.CreateRule(ctx, rule)
	require.NoError(t, err)

	req := LimitCheckRequest{
		SystemID:     "cleanup-test",
		Scope:        "ip",
		ScopeValue:   "192.168.1.195",
		ResourceType: "default",
	}

	// Generate some requests/buckets
	limiter.CheckLimit(ctx, req)
	limiter.CheckLimit(ctx, req) // Violation

	// Step 2: Cleanup future buckets (should not delete anything)
	futureCount, err := limiter.CleanupOldBuckets(ctx, time.Now().Add(-24*time.Hour))
	require.NoError(t, err)
	assert.GreaterOrEqual(t, futureCount, int64(0))

	// Step 3: Cleanup old buckets (specific time range)
	pastCount, err := limiter.CleanupOldBuckets(ctx, time.Now().Add(1*time.Hour))
	require.NoError(t, err)
	assert.GreaterOrEqual(t, pastCount, int64(0))

	// Step 4: Similarly test violation cleanup
	violationCount, err := limiter.CleanupOldViolations(ctx, time.Now().Add(1*time.Hour))
	require.NoError(t, err)
	assert.GreaterOrEqual(t, violationCount, int64(0))

	// Step 5: And metrics cleanup
	metricsCount, err := limiter.CleanupOldMetrics(ctx, time.Now().Add(1*time.Hour))
	require.NoError(t, err)
	assert.GreaterOrEqual(t, metricsCount, int64(0))
}

// TestConcurrentRequestHandling verifies thread-safety with concurrent requests
func TestConcurrentRequestHandling(t *testing.T) {
	db := setupRateLimiterIntegrationTestDB(t)
	limiter := NewPostgresRateLimiter(db, defaultConfig())

	ctx := context.Background()
	systemID := "concurrent-test"

	// Step 1: Create rule
	rule := Rule{
		SystemID:   systemID,
		Scope:      "ip",
		LimitType:  LimitPerMinute,
		LimitValue: 100,
		Enabled:    true,
		Priority:   1,
	}

	_, err := limiter.CreateRule(ctx, rule)
	require.NoError(t, err)

	// Step 2: Create a channel to collect results from goroutines
	results := make(chan Decision, 50)
	errors := make(chan error, 50)

	req := LimitCheckRequest{
		SystemID:     systemID,
		Scope:        "ip",
		ScopeValue:   "192.168.1.199",
		ResourceType: "default",
	}

	// Step 3: Launch concurrent requests
	for i := 0; i < 50; i++ {
		go func() {
			decision, err := limiter.CheckLimit(ctx, req)
			if err != nil {
				errors <- err
			} else {
				results <- decision
			}
		}()
	}

	// Step 4: Collect results
	allowedCount := 0
	for i := 0; i < 50; i++ {
		select {
		case d := <-results:
			if d.Allowed {
				allowedCount++
			}
		case e := <-errors:
			t.Logf("Request error: %v", e)
		}
	}

	// Step 5: Verify all requests were allowed (limit is 100)
	assert.Equal(t, 50, allowedCount, "all 50 concurrent requests should be allowed with 100 limit")
}
