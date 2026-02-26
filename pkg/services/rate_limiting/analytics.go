package rate_limiting

import (
	"context"
	"fmt"
	"time"

	"gorm.io/gorm"
)

// Analytics Data Structures

// SystemStats represents system-wide statistics
type SystemStats struct {
	TotalUsers            int64
	ActiveUsersToday      int64
	TotalCommandsToday    int64
	AverageThrottleFactor float64
	HighUtilizationCount  int64
	QuotasExceededToday   int64
	P95ResponseTime       int64 // milliseconds
	SystemLoad            SystemLoadStatus
	Timestamp             time.Time
}

// UserStats represents per-user statistics
type UserStats struct {
	UserID              int64
	Username            string
	DailyUtilization    float64 // percentage
	WeeklyUtilization   float64
	MonthlyUtilization  float64
	CommandsExecuted    int64
	AverageDuration     int64   // milliseconds
	SuccessRate         float64 // percentage
	ThrottleFactor      float64
	LastCommand         *time.Time
	DaysActive          int64
	FavoriteCommandType string
}

// CommandTypeStats represents statistics for a command type
type CommandTypeStats struct {
	CommandType      string
	TotalExecutions  int64
	AverageDuration  int64   // milliseconds
	SuccessCount     int64
	FailureCount     int64
	SuccessRate      float64 // percentage
	TotalCPUUsage    float64
	TotalMemoryUsage int64
	UniqueUsers      int64
	LastExecuted     *time.Time
}

// TrendData represents trend data over time
type TrendData struct {
	Labels             []string      // Dates or time labels
	CommandCounts      []int64       // Number of commands per period
	ViolationCounts    []int64       // Quota violations per period
	AverageThrottle    []float64     // Average throttle factor per period
	AverageDuration    []int64       // Average execution duration per period
	SuccessRates       []float64     // Success rate per period
	UniqueUsers        []int64       // Unique users per period
	Period             string        // "daily", "weekly", "monthly"
	TimeRange          string        // e.g., "last_7_days"
}

// UserTrendData represents trend data for a specific user
type UserTrendData struct {
	UserID       int64
	Username     string
	Labels       []string // Date labels
	CommandCounts []int64  // Commands executed per day
	Violations   []int64   // Violations per day
	Duration     []int64   // Average duration per day
	Period       string
	TimeRange    string
}

// ViolationTrend represents violation trend data
type ViolationTrend struct {
	Date           time.Time
	TotalViolations int64
	UniqueUsers    int64
	ByCommandType  map[string]int64
	ByPeriod       map[string]int64 // daily, weekly, monthly
}

// HighUtilizationUser represents a user with high quota utilization
type HighUtilizationUser struct {
	UserID              int64
	Username            string
	DailyUtilization    float64
	WeeklyUtilization   float64
	MonthlyUtilization  float64
	DaysUntilReset      int
	PredictedViolation  bool   // Will exceed quota before reset
	RecommendedAction   string // "upgrade", "monitor", "warn"
}

// PredictedViolation represents a predicted quota violation
type PredictedViolation struct {
	UserID           int64
	Username         string
	CommandType      string
	Period           string // daily, weekly, monthly
	CurrentUsage     int64
	QuotaLimit       int64
	ProjectedUsage   int64
	DaysRemaining    int
	ViolationProb    float64 // 0.0-1.0
	RecommendedLimit int64
}

// AnomalyAlert represents an anomalous usage pattern
type AnomalyAlert struct {
	UserID        int64
	Username      string
	AnomalyType   string // "spike", "decline", "unusual_pattern"
	Severity      string // "low", "medium", "high"
	Description   string
	BaselineValue int64
	CurrentValue  int64
	Deviation     float64 // percentage from baseline
	FirstDetected time.Time
	Status        string // "new", "monitoring", "resolved"
}

// QuotaAnalytics provides analytical services for quotas
type QuotaAnalytics struct {
	db           *gorm.DB
	cache        map[string]interface{}
	cacheTTL     time.Time
	cacheMaxAge  time.Duration
}

// NewQuotaAnalytics creates a new analytics service
func NewQuotaAnalytics(db *gorm.DB) *QuotaAnalytics {
	return &QuotaAnalytics{
		db:          db,
		cache:       make(map[string]interface{}),
		cacheMaxAge: 5 * time.Minute,
	}
}

// GetSystemStats returns system-wide statistics
func (qa *QuotaAnalytics) GetSystemStats(ctx context.Context) (SystemStats, error) {
	stats := SystemStats{
		Timestamp: time.Now(),
	}

	// Count total users
	qa.db.WithContext(ctx).Table("users").Count(&stats.TotalUsers)

	// Count commands today
	today := time.Now().Truncate(24 * time.Hour)
	qa.db.WithContext(ctx).
		Table("command_executions").
		Where("executed_at >= ?", today).
		Count(&stats.TotalCommandsToday)

	// Count violations today
	qa.db.WithContext(ctx).
		Table("command_quota_usage").
		Where("period_start >= ?", today).
		Where("commands_executed > daily_limit").
		Count(&stats.QuotasExceededToday)

	// Count active users (executed commands today)
	qa.db.WithContext(ctx).
		Table("command_executions").
		Where("executed_at >= ?", today).
		Select("COUNT(DISTINCT user_id)").
		Scan(&stats.ActiveUsersToday)

	// Count high utilization users (>80% of daily quota)
	qa.db.WithContext(ctx).Raw(`
		SELECT COUNT(DISTINCT cqu.user_id)
		FROM command_quota_usage cqu
		JOIN command_quota_rules cqr ON cqu.command_type = cqr.command_type
		WHERE cqu.usage_period = 'daily' AND cqu.period_start = ?
		AND (cqu.commands_executed * 100.0 / cqr.daily_limit) > 80
	`, today).Scan(&stats.HighUtilizationCount)

	// Average throttle factor (placeholder - would need throttle event tracking)
	stats.AverageThrottleFactor = 1.0

	// P95 response time (placeholder)
	stats.P95ResponseTime = 0

	return stats, nil
}

// GetUserStats returns statistics for a specific user
func (qa *QuotaAnalytics) GetUserStats(ctx context.Context, userID int64) (UserStats, error) {
	stats := UserStats{
		UserID: userID,
	}

	// Get username
	qa.db.WithContext(ctx).
		Table("users").
		Where("id = ?", userID).
		Select("username").
		Scan(&stats.Username)

	// Get usage percentages
	today := time.Now().Truncate(24 * time.Hour)
	week := today.AddDate(0, 0, -7)
	month := today.AddDate(0, -1, 0)

	// Daily usage
	var dailyResult struct {
		Used  int64
		Limit int64
	}
	qa.db.WithContext(ctx).Raw(`
		SELECT COALESCE(SUM(commands_executed), 0) as used, COALESCE(SUM(daily_limit), 0) as limit
		FROM (
			SELECT cqu.commands_executed, cqr.daily_limit
			FROM command_quota_usage cqu
			JOIN command_quota_rules cqr ON cqu.command_type = cqr.command_type
			WHERE cqu.user_id = ? AND cqu.usage_period = 'daily' AND cqu.period_start = ?
		) t
	`, userID, today).Scan(&dailyResult)

	if dailyResult.Limit > 0 {
		stats.DailyUtilization = float64(dailyResult.Used) / float64(dailyResult.Limit) * 100
	}

	// Weekly usage
	var weeklyResult struct {
		Used  int64
		Limit int64
	}
	qa.db.WithContext(ctx).Raw(`
		SELECT COALESCE(SUM(commands_executed), 0) as used, COALESCE(SUM(weekly_limit), 0) as limit
		FROM (
			SELECT cqu.commands_executed, cqr.weekly_limit
			FROM command_quota_usage cqu
			JOIN command_quota_rules cqr ON cqu.command_type = cqr.command_type
			WHERE cqu.user_id = ? AND cqu.usage_period = 'weekly' AND cqu.period_start = ?
		) t
	`, userID, week).Scan(&weeklyResult)

	if weeklyResult.Limit > 0 {
		stats.WeeklyUtilization = float64(weeklyResult.Used) / float64(weeklyResult.Limit) * 100
	}

	// Monthly usage
	var monthlyResult struct {
		Used  int64
		Limit int64
	}
	qa.db.WithContext(ctx).Raw(`
		SELECT COALESCE(SUM(commands_executed), 0) as used, COALESCE(SUM(monthly_limit), 0) as limit
		FROM (
			SELECT cqu.commands_executed, cqr.monthly_limit
			FROM command_quota_usage cqu
			JOIN command_quota_rules cqr ON cqu.command_type = cqr.command_type
			WHERE cqu.user_id = ? AND cqu.usage_period = 'monthly' AND cqu.period_start = ?
		) t
	`, userID, month).Scan(&monthlyResult)

	if monthlyResult.Limit > 0 {
		stats.MonthlyUtilization = float64(monthlyResult.Used) / float64(monthlyResult.Limit) * 100
	}

	// Total commands executed
	qa.db.WithContext(ctx).
		Table("command_executions").
		Where("user_id = ?", userID).
		Count(&stats.CommandsExecuted)

	// Average duration
	qa.db.WithContext(ctx).
		Table("command_executions").
		Where("user_id = ?", userID).
		Select("AVG(duration_ms)").
		Scan(&stats.AverageDuration)

	// Success rate
	var successCount int64
	qa.db.WithContext(ctx).
		Table("command_executions").
		Where("user_id = ? AND exit_code = 0", userID).
		Count(&successCount)

	if stats.CommandsExecuted > 0 {
		stats.SuccessRate = float64(successCount) / float64(stats.CommandsExecuted) * 100
	}

	// Last command
	var lastExec time.Time
	qa.db.WithContext(ctx).
		Table("command_executions").
		Where("user_id = ?", userID).
		Order("executed_at DESC").
		Limit(1).
		Select("executed_at").
		Scan(&lastExec)

	if !lastExec.IsZero() {
		stats.LastCommand = &lastExec
	}

	// Days active
	qa.db.WithContext(ctx).Raw(`
		SELECT COUNT(DISTINCT DATE(executed_at))
		FROM command_executions
		WHERE user_id = ?
	`, userID).Scan(&stats.DaysActive)

	// Favorite command type
	qa.db.WithContext(ctx).Raw(`
		SELECT command_type
		FROM command_executions
		WHERE user_id = ?
		GROUP BY command_type
		ORDER BY COUNT(*) DESC
		LIMIT 1
	`, userID).Scan(&stats.FavoriteCommandType)

	return stats, nil
}

// GetCommandTypeStats returns statistics for a command type
func (qa *QuotaAnalytics) GetCommandTypeStats(ctx context.Context, cmdType string) (CommandTypeStats, error) {
	stats := CommandTypeStats{
		CommandType: cmdType,
	}

	// Total executions
	qa.db.WithContext(ctx).
		Table("command_executions").
		Where("command_type = ?", cmdType).
		Count(&stats.TotalExecutions)

	// Average duration
	qa.db.WithContext(ctx).
		Table("command_executions").
		Where("command_type = ?", cmdType).
		Select("AVG(duration_ms)").
		Scan(&stats.AverageDuration)

	// Success/failure counts
	qa.db.WithContext(ctx).
		Table("command_executions").
		Where("command_type = ? AND exit_code = 0", cmdType).
		Count(&stats.SuccessCount)

	qa.db.WithContext(ctx).
		Table("command_executions").
		Where("command_type = ? AND exit_code != 0", cmdType).
		Count(&stats.FailureCount)

	if stats.TotalExecutions > 0 {
		stats.SuccessRate = float64(stats.SuccessCount) / float64(stats.TotalExecutions) * 100
	}

	// Total CPU and memory usage
	var resourceResult struct {
		CPU    float64
		Memory int64
	}
	qa.db.WithContext(ctx).Raw(`
		SELECT
			COALESCE(SUM(cpu_usage_percent), 0) as cpu,
			COALESCE(SUM(memory_usage_mb), 0) as memory
		FROM command_executions
		WHERE command_type = ?
	`, cmdType).Scan(&resourceResult)
	stats.TotalCPUUsage = resourceResult.CPU
	stats.TotalMemoryUsage = resourceResult.Memory

	// Unique users
	qa.db.WithContext(ctx).
		Table("command_executions").
		Where("command_type = ?", cmdType).
		Select("COUNT(DISTINCT user_id)").
		Scan(&stats.UniqueUsers)

	// Last executed
	var lastExec time.Time
	qa.db.WithContext(ctx).
		Table("command_executions").
		Where("command_type = ?", cmdType).
		Order("executed_at DESC").
		Limit(1).
		Select("executed_at").
		Scan(&lastExec)

	if !lastExec.IsZero() {
		stats.LastExecuted = &lastExec
	}

	return stats, nil
}

// GetQuotaViolationTrends returns violation trends over time
func (qa *QuotaAnalytics) GetQuotaViolationTrends(ctx context.Context, days int) ([]ViolationTrend, error) {
	var trends []ViolationTrend

	startDate := time.Now().AddDate(0, 0, -days).Truncate(24 * time.Hour)

	// Query violation trends grouped by date
	qa.db.WithContext(ctx).Raw(`
		SELECT
			DATE(cqu.period_start) as date,
			COUNT(*) as total_violations,
			COUNT(DISTINCT user_id) as unique_users
		FROM command_quota_usage cqu
		WHERE cqu.period_start >= ?
			AND cqu.commands_executed > CASE
				WHEN cqu.usage_period = 'daily' THEN (
					SELECT daily_limit FROM command_quota_rules
					WHERE command_type = cqu.command_type LIMIT 1
				)
				ELSE 0
			END
		GROUP BY DATE(cqu.period_start)
		ORDER BY date DESC
	`, startDate).Scan(&trends)

	return trends, nil
}

// GetHighUtilizationUsers returns users with high quota utilization
func (qa *QuotaAnalytics) GetHighUtilizationUsers(ctx context.Context) ([]HighUtilizationUser, error) {
	var users []HighUtilizationUser

	today := time.Now().Truncate(24 * time.Hour)

	qa.db.WithContext(ctx).Raw(`
		SELECT
			u.id as user_id,
			u.username,
			COALESCE(
				(SUM(CASE WHEN cqu.usage_period = 'daily' THEN cqu.commands_executed ELSE 0 END) * 100.0 /
				 SUM(CASE WHEN cqu.usage_period = 'daily' THEN cqr.daily_limit ELSE 1 END)), 0
			) as daily_utilization,
			COALESCE(
				(SUM(CASE WHEN cqu.usage_period = 'weekly' THEN cqu.commands_executed ELSE 0 END) * 100.0 /
				 SUM(CASE WHEN cqu.usage_period = 'weekly' THEN cqr.weekly_limit ELSE 1 END)), 0
			) as weekly_utilization,
			COALESCE(
				(SUM(CASE WHEN cqu.usage_period = 'monthly' THEN cqu.commands_executed ELSE 0 END) * 100.0 /
				 SUM(CASE WHEN cqu.usage_period = 'monthly' THEN cqr.monthly_limit ELSE 1 END)), 0
			) as monthly_utilization
		FROM users u
		LEFT JOIN command_quota_usage cqu ON u.id = cqu.user_id
		LEFT JOIN command_quota_rules cqr ON cqu.command_type = cqr.command_type
		WHERE cqu.period_start >= ?
		GROUP BY u.id, u.username
		HAVING COALESCE(
			(SUM(CASE WHEN cqu.usage_period = 'daily' THEN cqu.commands_executed ELSE 0 END) * 100.0 /
			 SUM(CASE WHEN cqu.usage_period = 'daily' THEN cqr.daily_limit ELSE 1 END)), 0
		) > 80
		ORDER BY daily_utilization DESC
	`, today).Scan(&users)

	// Set recommended actions
	for i := range users {
		if users[i].DailyUtilization > 95 {
			users[i].RecommendedAction = "upgrade"
		} else if users[i].DailyUtilization > 80 {
			users[i].RecommendedAction = "warn"
		} else {
			users[i].RecommendedAction = "monitor"
		}
	}

	return users, nil
}

// GetPredictedViolations returns predicted quota violations
func (qa *QuotaAnalytics) GetPredictedViolations(ctx context.Context) ([]PredictedViolation, error) {
	var predictions []PredictedViolation

	// This is a simplified prediction based on current rate
	// In production, use ML models or exponential moving averages

	today := time.Now().Truncate(24 * time.Hour)
	timeRemaining := 24*time.Hour - time.Since(today)
	daysRemaining := int(timeRemaining.Hours() / 24)
	if daysRemaining == 0 {
		daysRemaining = 1
	}

	// Get users approaching daily limits
	qa.db.WithContext(ctx).Raw(`
		SELECT
			u.id as user_id,
			u.username,
			cqu.command_type,
			'daily' as period,
			cqu.commands_executed as current_usage,
			cqr.daily_limit as quota_limit,
			(cqu.commands_executed * ?) as projected_usage,
			? as days_remaining,
			CASE
				WHEN (cqu.commands_executed * ?) > cqr.daily_limit THEN 0.95
				WHEN (cqu.commands_executed * ?) > (cqr.daily_limit * 0.8) THEN 0.75
				ELSE 0.25
			END as violation_prob,
			CEIL(cqr.daily_limit * 1.2) as recommended_limit
		FROM users u
		JOIN command_quota_usage cqu ON u.id = cqu.user_id
		JOIN command_quota_rules cqr ON cqu.command_type = cqr.command_type
		WHERE cqu.usage_period = 'daily' AND cqu.period_start = ?
		AND cqu.commands_executed > (cqr.daily_limit * 0.7)
		ORDER BY violation_prob DESC
	`, daysRemaining, daysRemaining, daysRemaining, daysRemaining, today).Scan(&predictions)

	return predictions, nil
}

// GetUserTrends returns trend data for a specific user
func (qa *QuotaAnalytics) GetUserTrends(ctx context.Context, userID int64, days int) (UserTrendData, error) {
	trends := UserTrendData{
		UserID:    userID,
		Period:    "daily",
		TimeRange: fmt.Sprintf("last_%d_days", days),
	}

	// Get username
	qa.db.WithContext(ctx).
		Table("users").
		Where("id = ?", userID).
		Select("username").
		Scan(&trends.Username)

	// Get daily command counts
	qa.db.WithContext(ctx).Raw(`
		SELECT
			DATE(executed_at)::text as date,
			COUNT(*) as count
		FROM command_executions
		WHERE user_id = ? AND executed_at > NOW() - INTERVAL '1 day' * ?
		GROUP BY DATE(executed_at)
		ORDER BY date DESC
	`, userID, days).Scan(&trends.CommandCounts)

	return trends, nil
}

// ClearCache clears the analytics cache
func (qa *QuotaAnalytics) ClearCache() {
	qa.cache = make(map[string]interface{})
	qa.cacheTTL = time.Time{}
}
