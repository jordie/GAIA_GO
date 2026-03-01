package rate_limiting

import (
	"context"
	"fmt"
	"strconv"
	"sync"
	"time"

	"gorm.io/gorm"
)

// RateLimiter is the main interface for rate limiting operations
type RateLimiter interface {
	// CheckLimit checks if a request is allowed
	CheckLimit(ctx context.Context, req LimitCheckRequest) (Decision, error)

	// GetUsage returns current usage statistics
	GetUsage(ctx context.Context, system, scope, value string) (Usage, error)

	// GetRules returns all rules for a system
	GetRules(ctx context.Context, system string) ([]Rule, error)

	// Rule management (admin)
	CreateRule(ctx context.Context, rule Rule) (int64, error)
	UpdateRule(ctx context.Context, rule Rule) error
	DeleteRule(ctx context.Context, ruleID int64) error
	GetRule(ctx context.Context, ruleID int64) (*Rule, error)

	// Quota management
	IncrementQuota(ctx context.Context, system, scope, value, resourceType string, amount int) error
	GetQuota(ctx context.Context, system, scope, value, resourceType string) (*Quota, error)

	// Violations (admin)
	GetViolations(ctx context.Context, system string, since time.Time) ([]Violation, error)
	GetViolationStats(ctx context.Context, system string) (map[string]interface{}, error)

	// Cleanup
	CleanupOldBuckets(ctx context.Context, before time.Time) (int64, error)
	CleanupOldViolations(ctx context.Context, before time.Time) (int64, error)
	CleanupOldMetrics(ctx context.Context, before time.Time) (int64, error)
}

// PostgresRateLimiter implements RateLimiter with PostgreSQL backend
type PostgresRateLimiter struct {
	db         *gorm.DB
	config     Config
	reputation *ReputationManager // Phase 2: Reputation system

	// Rule cache
	ruleCache map[string][]*Rule
	ruleLock  sync.RWMutex
	ruleTTL   time.Time
}

// NewPostgresRateLimiter creates a new PostgreSQL-backed rate limiter
func NewPostgresRateLimiter(db *gorm.DB, config Config) *PostgresRateLimiter {
	limiter := &PostgresRateLimiter{
		db:         db,
		config:     config,
		ruleCache:  make(map[string][]*Rule),
		reputation: NewReputationManager(db), // Phase 2: Initialize reputation manager
	}

	// Start background cleanup job
	go limiter.startCleanupJob()

	return limiter
}

// CheckLimit checks if a request is allowed
func (l *PostgresRateLimiter) CheckLimit(ctx context.Context, req LimitCheckRequest) (Decision, error) {
	decision := Decision{
		Allowed:           true,
		RetryAfterSeconds: l.config.DefaultRetryAfter,
	}

	// Get applicable rules (ordered by priority)
	rules, err := l.getRulesForCheck(ctx, req.SystemID)
	if err != nil {
		return decision, fmt.Errorf("failed to get rules: %w", err)
	}

	now := time.Now()

	// Check each rule
	for _, rule := range rules {
		if !rule.Enabled {
			continue
		}

		// Skip rules that don't match this scope
		if rule.Scope != req.Scope {
			continue
		}

		// Skip rules with specific scope values if not matching
		if rule.ScopeValue != "" && rule.ScopeValue != req.ScopeValue {
			continue
		}

		// Skip rules with specific resource types if not matching
		if rule.ResourceType != "" && rule.ResourceType != req.ResourceType {
			continue
		}

		// Phase 2: Adjust limit based on reputation
		adjustedLimit := rule.LimitValue
		if req.Scope == "user" && req.ScopeValue != "" {
			if userID, err := parseUserID(req.ScopeValue); err == nil {
				adjustedLimit = l.reputation.GetAdaptiveLimit(userID, rule.LimitValue)
				// Create modified rule with adjusted limit for checking
				rule = &Rule{
					ID:           rule.ID,
					SystemID:     rule.SystemID,
					Scope:        rule.Scope,
					ScopeValue:   rule.ScopeValue,
					ResourceType: rule.ResourceType,
					LimitType:    rule.LimitType,
					LimitValue:   adjustedLimit,
					Enabled:      rule.Enabled,
					Priority:     rule.Priority,
				}
			}
		}

		// Check the limit
		allowed, remaining, resetTime := l.checkRule(ctx, rule, req.ScopeValue, now)

		if !allowed {
			decision.Allowed = false
			decision.RuleID = rule.ID
			decision.Reason = fmt.Sprintf("Rate limit exceeded: %s (%d/%d)",
				rule.LimitType, l.config.DefaultRetryAfter, rule.LimitValue)
			decision.Limit = rule.LimitValue
			decision.Remaining = remaining
			decision.ResetTime = resetTime

			// Track violation
			if l.config.EnableViolationTracking {
				_ = l.recordViolation(ctx, req, rule)
			}

			return decision, nil
		}

		// Update remaining
		decision.Remaining = remaining
		decision.ResetTime = resetTime
	}

	// Phase 2: Record clean request (good behavior)
	if decision.Allowed {
		_ = l.recordCleanRequest(ctx, req)
	}

	// Record metrics
	if l.config.EnableMetrics {
		_ = l.recordMetric(ctx, req, decision)
	}

	return decision, nil
}

// checkRule checks a single rule and updates buckets/quotas
func (l *PostgresRateLimiter) checkRule(ctx context.Context, rule *Rule, scopeValue string, now time.Time) (bool, int, time.Time) {
	switch rule.LimitType {
	case LimitPerSecond:
		return l.checkSlidingWindow(ctx, rule, scopeValue, now, 1*time.Second)
	case LimitPerMinute:
		return l.checkSlidingWindow(ctx, rule, scopeValue, now, 1*time.Minute)
	case LimitPerHour:
		return l.checkSlidingWindow(ctx, rule, scopeValue, now, 1*time.Hour)
	case LimitPerDay:
		return l.checkQuota(ctx, rule, scopeValue, now, 24*time.Hour)
	case LimitPerWeek:
		return l.checkQuota(ctx, rule, scopeValue, now, 7*24*time.Hour)
	case LimitPerMonth:
		return l.checkQuota(ctx, rule, scopeValue, now, 30*24*time.Hour)
	default:
		return true, rule.LimitValue, now.Add(1 * time.Hour)
	}
}

// checkSlidingWindow checks a sliding window rate limit
func (l *PostgresRateLimiter) checkSlidingWindow(ctx context.Context, rule *Rule, scopeValue string, now time.Time, window time.Duration) (bool, int, time.Time) {
	windowStart := now.Add(-window - l.config.ClockTolerance)
	windowEnd := now

	// Get or create bucket
	bucket := Bucket{
		RuleID:      rule.ID,
		SystemID:    rule.SystemID,
		Scope:       rule.Scope,
		ScopeValue:  scopeValue,
		WindowStart: windowStart.Truncate(1 * time.Second),
		WindowEnd:   windowEnd,
	}

	// Count requests in window
	var count int64
	err := l.db.WithContext(ctx).
		Table("rate_limit_buckets").
		Where("rule_id = ? AND scope_value = ? AND window_start <= ? AND window_end >= ?",
			rule.ID, scopeValue, windowEnd, windowStart).
		Select("COALESCE(SUM(request_count), 0)").
		Scan(&count).Error

	if err != nil {
		return true, rule.LimitValue, windowEnd
	}

	// Increment bucket
	result := l.db.WithContext(ctx).
		Table("rate_limit_buckets").
		Where("rule_id = ? AND scope_value = ? AND window_start = ?", rule.ID, scopeValue, bucket.WindowStart).
		Update("request_count", gorm.Expr("request_count + 1"))

	// Create new bucket if update didn't affect any rows or failed
	if result.Error != nil || result.RowsAffected == 0 {
		bucket.RequestCount = 1 // First request in this bucket
		l.db.WithContext(ctx).Table("rate_limit_buckets").Create(&bucket)
	}

	allowed := count < int64(rule.LimitValue)
	// Remaining should account for the current request being allowed
	remaining := int(int64(rule.LimitValue) - count - 1)
	if remaining < 0 {
		remaining = 0
	}

	resetTime := bucket.WindowStart.Add(window)

	return allowed, remaining, resetTime
}

// checkQuota checks a quota-based limit
func (l *PostgresRateLimiter) checkQuota(ctx context.Context, rule *Rule, scopeValue string, now time.Time, period time.Duration) (bool, int, time.Time) {
	periodStart := now.Truncate(period)
	periodEnd := periodStart.Add(period)

	// Get or create quota
	quota := Quota{
		SystemID:     rule.SystemID,
		Scope:        rule.Scope,
		ScopeValue:   scopeValue,
		ResourceType: rule.ResourceType,
		QuotaPeriod:  rule.LimitType,
		QuotaLimit:   rule.LimitValue,
		PeriodStart:  periodStart,
		PeriodEnd:    periodEnd,
	}

	// Check if within quota
	var existing Quota
	err := l.db.WithContext(ctx).Table("resource_quotas").
		Where("system_id = ? AND scope = ? AND scope_value = ? AND resource_type = ? AND period_start = ?",
			quota.SystemID, quota.Scope, quota.ScopeValue, quota.ResourceType, periodStart).
		First(&existing).Error

	if err == gorm.ErrRecordNotFound {
		// Create new quota
		l.db.WithContext(ctx).Table("resource_quotas").Create(&quota)
		return true, rule.LimitValue - 1, periodEnd
	}

	// Increment existing quota
	l.db.WithContext(ctx).Table("resource_quotas").
		Where("id = ?", existing.ID).
		Update("quota_used", gorm.Expr("quota_used + 1"))

	allowed := existing.QuotaUsed < rule.LimitValue
	remaining := rule.LimitValue - existing.QuotaUsed - 1
	if remaining < 0 {
		remaining = 0
	}

	return allowed, remaining, periodEnd
}

// getRulesForCheck gets cached rules for a system
func (l *PostgresRateLimiter) getRulesForCheck(ctx context.Context, systemID string) ([]*Rule, error) {
	l.ruleLock.RLock()
	if rules, ok := l.ruleCache[systemID]; ok && time.Now().Before(l.ruleTTL) {
		l.ruleLock.RUnlock()
		return rules, nil
	}
	l.ruleLock.RUnlock()

	// Load rules from database
	var rules []*Rule
	err := l.db.WithContext(ctx).
		Table("rate_limit_rules").
		Where("system_id IN (?, ?) AND enabled = true", systemID, SystemGlobal).
		Order("priority ASC").
		Scan(&rules).Error

	if err != nil {
		return nil, err
	}

	// Update cache
	l.ruleLock.Lock()
	l.ruleCache[systemID] = rules
	l.ruleTTL = time.Now().Add(l.config.RuleCacheTTL)
	l.ruleLock.Unlock()

	return rules, nil
}

// recordViolation records a rate limit violation
func (l *PostgresRateLimiter) recordViolation(ctx context.Context, req LimitCheckRequest, rule *Rule) error {
	violation := Violation{
		SystemID:      req.SystemID,
		RuleID:        &rule.ID,
		Scope:         req.Scope,
		ScopeValue:    req.ScopeValue,
		ResourceType:  req.ResourceType,
		ViolatedLimit: rule.LimitValue,
		ViolationTime: time.Now(),
		RequestPath:   req.RequestPath,
		RequestMethod: req.Method,
		Blocked:       true,
	}

	if ua, ok := req.Headers["user-agent"]; ok {
		violation.UserAgent = ua
	}

	// Record violation in rate limit tracking
	err := l.db.WithContext(ctx).Table("rate_limit_violations").Create(&violation).Error

	// Phase 2: Record violation in reputation system
	if err == nil && req.Scope == "user" && req.ScopeValue != "" {
		if userID, parseErr := parseUserID(req.ScopeValue); parseErr == nil {
			// Determine severity based on resource type
			severity := 2 // Default
			if req.ResourceType == "login" {
				severity = 3 // Higher severity for login attempts
			} else if req.ResourceType == "api_call" {
				severity = 1 // Lower severity for API calls
			}

			description := fmt.Sprintf("Rate limit violation: %s on %s", rule.LimitType, req.RequestPath)
			_ = l.reputation.RecordViolation(userID, severity, description)
		}
	}

	return err
}

// recordMetric records rate limit metrics
func (l *PostgresRateLimiter) recordMetric(ctx context.Context, req LimitCheckRequest, decision Decision) error {
	metric := Metric{
		SystemID:          req.SystemID,
		Scope:             req.Scope,
		ScopeValue:        req.ScopeValue,
		Timestamp:         time.Now(),
		RequestsProcessed: 1,
	}

	if decision.Allowed {
		metric.RequestsAllowed = 1
	} else {
		metric.RequestsBlocked = 1
	}

	// Insert metric - async/batched in Phase 11.4
	return l.db.WithContext(ctx).Table("rate_limit_metrics").Create(&metric).Error
}

// startCleanupJob starts the background cleanup job
func (l *PostgresRateLimiter) startCleanupJob() {
	ticker := time.NewTicker(l.config.BucketCleanupInterval)
	defer ticker.Stop()

	ctx := context.Background()

	for range ticker.C {
		before := time.Now().Add(-l.config.ViolationRetention)
		l.CleanupOldBuckets(ctx, before)
		l.CleanupOldViolations(ctx, before.Add(l.config.ViolationRetention - l.config.BucketCleanupInterval))
		l.CleanupOldMetrics(ctx, time.Now().Add(-l.config.MetricsRetention))
	}
}

// CreateRule creates a new rate limit rule
func (l *PostgresRateLimiter) CreateRule(ctx context.Context, rule Rule) (int64, error) {
	now := time.Now()
	rule.CreatedAt = now
	rule.UpdatedAt = now

	// Auto-generate rule name if empty
	if rule.RuleName == "" {
		rule.RuleName = fmt.Sprintf("%s_%s_%d_%d", rule.SystemID, rule.Scope, rule.LimitValue, now.UnixNano())
	}

	result := l.db.WithContext(ctx).Table("rate_limit_rules").Create(&rule)
	if result.Error != nil {
		return 0, result.Error
	}

	// Invalidate cache
	l.ruleLock.Lock()
	delete(l.ruleCache, rule.SystemID)
	l.ruleLock.Unlock()

	return rule.ID, nil
}

// UpdateRule updates an existing rule
func (l *PostgresRateLimiter) UpdateRule(ctx context.Context, rule Rule) error {
	rule.UpdatedAt = time.Now()

	result := l.db.WithContext(ctx).Table("rate_limit_rules").
		Where("id = ?", rule.ID).
		Updates(&rule)

	if result.Error != nil {
		return result.Error
	}

	// Invalidate cache
	l.ruleLock.Lock()
	delete(l.ruleCache, rule.SystemID)
	l.ruleLock.Unlock()

	return nil
}

// DeleteRule deletes a rule by ID
func (l *PostgresRateLimiter) DeleteRule(ctx context.Context, ruleID int64) error {
	// Get the rule first to find system ID for cache invalidation
	var rule Rule
	if err := l.db.WithContext(ctx).Table("rate_limit_rules").Where("id = ?", ruleID).First(&rule).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil // Already deleted
		}
		return err
	}

	result := l.db.WithContext(ctx).Table("rate_limit_rules").Where("id = ?", ruleID).Delete(nil)
	if result.Error != nil {
		return result.Error
	}

	// Invalidate cache
	l.ruleLock.Lock()
	delete(l.ruleCache, rule.SystemID)
	l.ruleLock.Unlock()

	return nil
}

// GetRule retrieves a rule by ID
func (l *PostgresRateLimiter) GetRule(ctx context.Context, ruleID int64) (*Rule, error) {
	var rule Rule
	err := l.db.WithContext(ctx).Table("rate_limit_rules").Where("id = ?", ruleID).First(&rule).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, err
	}
	return &rule, nil
}

// GetRules returns all rules for a system
func (l *PostgresRateLimiter) GetRules(ctx context.Context, system string) ([]Rule, error) {
	var rules []Rule
	err := l.db.WithContext(ctx).
		Table("rate_limit_rules").
		Where("system_id IN (?, ?)", system, SystemGlobal).
		Order("priority ASC").
		Scan(&rules).Error
	return rules, err
}

// GetUsage returns current usage statistics
func (l *PostgresRateLimiter) GetUsage(ctx context.Context, system, scope, value string) (Usage, error) {
	usage := Usage{
		Scope:      scope,
		ScopeValue: value,
	}

	// Get current quota info
	var quota Quota
	now := time.Now()
	err := l.db.WithContext(ctx).Table("resource_quotas").
		Where("system_id = ? AND scope = ? AND scope_value = ? AND period_start <= ? AND period_end > ?",
			system, scope, value, now, now).
		First(&quota).Error

	if err == nil {
		usage.QuotaLimit = quota.QuotaLimit
		usage.QuotaUsed = quota.QuotaUsed
		usage.QuotaPeriod = quota.QuotaPeriod
		usage.ResetTime = quota.PeriodEnd
	}

	return usage, nil
}

// IncrementQuota increments quota usage
func (l *PostgresRateLimiter) IncrementQuota(ctx context.Context, system, scope, value, resourceType string, amount int) error {
	now := time.Now()
	result := l.db.WithContext(ctx).Table("resource_quotas").
		Where("system_id = ? AND scope = ? AND scope_value = ? AND resource_type = ? AND period_start <= ? AND period_end > ?",
			system, scope, value, resourceType, now, now).
		Update("quota_used", gorm.Expr("quota_used + ?", amount))

	return result.Error
}

// GetQuota retrieves quota information
func (l *PostgresRateLimiter) GetQuota(ctx context.Context, system, scope, value, resourceType string) (*Quota, error) {
	var quota Quota
	now := time.Now()
	err := l.db.WithContext(ctx).Table("resource_quotas").
		Where("system_id = ? AND scope = ? AND scope_value = ? AND resource_type = ? AND period_start <= ? AND period_end > ?",
			system, scope, value, resourceType, now, now).
		First(&quota).Error

	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, err
	}

	return &quota, nil
}

// GetViolations returns violations for a system since a specific time
func (l *PostgresRateLimiter) GetViolations(ctx context.Context, system string, since time.Time) ([]Violation, error) {
	var violations []Violation
	err := l.db.WithContext(ctx).Table("rate_limit_violations").
		Where("system_id = ? AND violation_time >= ?", system, since).
		Order("violation_time DESC").
		Scan(&violations).Error
	return violations, err
}

// GetViolationStats returns violation statistics
func (l *PostgresRateLimiter) GetViolationStats(ctx context.Context, system string) (map[string]interface{}, error) {
	stats := make(map[string]interface{})

	// Total violations
	var total int64
	l.db.WithContext(ctx).Table("rate_limit_violations").
		Where("system_id = ?", system).
		Count(&total)
	stats["total_violations"] = total

	// Violations by scope
	var byScope []map[string]interface{}
	l.db.WithContext(ctx).Table("rate_limit_violations").
		Select("scope, COUNT(*) as count").
		Where("system_id = ?", system).
		Group("scope").
		Scan(&byScope)
	stats["by_scope"] = byScope

	return stats, nil
}

func (l *PostgresRateLimiter) CleanupOldBuckets(ctx context.Context, before time.Time) (int64, error) {
	result := l.db.WithContext(ctx).Table("rate_limit_buckets").Where("window_end < ?", before).Delete(nil)
	return result.RowsAffected, result.Error
}

func (l *PostgresRateLimiter) CleanupOldViolations(ctx context.Context, before time.Time) (int64, error) {
	result := l.db.WithContext(ctx).Table("rate_limit_violations").Where("violation_time < ?", before).Delete(nil)
	return result.RowsAffected, result.Error
}

func (l *PostgresRateLimiter) CleanupOldMetrics(ctx context.Context, before time.Time) (int64, error) {
	result := l.db.WithContext(ctx).Table("rate_limit_metrics").Where("timestamp < ?", before).Delete(nil)
	return result.RowsAffected, result.Error
}

// Helper functions

// parseUserID converts a scope value (string) to a user ID (integer)
func parseUserID(scopeValue string) (int, error) {
	userID, err := strconv.Atoi(scopeValue)
	if err != nil {
		return 0, fmt.Errorf("invalid user ID format: %w", err)
	}
	return userID, nil
}

// recordCleanRequest tracks allowed requests in the reputation system
// This builds positive reputation for good behavior
func (l *PostgresRateLimiter) recordCleanRequest(ctx context.Context, req LimitCheckRequest) error {
	if req.Scope != "user" || req.ScopeValue == "" {
		return nil
	}

	userID, err := parseUserID(req.ScopeValue)
	if err != nil {
		return nil // Skip if not a valid user ID
	}

	// Record clean request in reputation system
	return l.reputation.RecordCleanRequest(userID)
}
