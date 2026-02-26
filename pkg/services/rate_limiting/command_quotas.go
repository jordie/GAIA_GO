package rate_limiting

import (
	"context"
	"fmt"
	"time"

	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

// Command Types
const (
	CommandTypeShell    = "shell"
	CommandTypeCode     = "code"
	CommandTypeTest     = "test"
	CommandTypeReview   = "review"
	CommandTypeRefactor = "refactor"
)

// Quota Periods
const (
	QuotaPeriodDaily   = "daily"
	QuotaPeriodWeekly  = "weekly"
	QuotaPeriodMonthly = "monthly"
)

// CommandQuotaRule defines quota limits for a command type
type CommandQuotaRule struct {
	ID           int64
	UserID       *int64 // NULL = global default
	CommandType  string
	DailyLimit   int
	WeeklyLimit  int
	MonthlyLimit int
	EstimatedCPU int // Estimated CPU % per command
	EstimatedMem int // Estimated memory MB per command
	Enabled      bool
	CreatedAt    time.Time
	UpdatedAt    time.Time
}

// CommandExecution tracks executed commands
type CommandExecution struct {
	ID             int64
	UserID         int64
	SessionID      *string
	CommandType    string
	CommandHash    string // SHA256 of command
	DurationMs     int
	CPUUsagePercent float64
	MemoryUsageMB  int
	ExitCode       int
	ErrorMessage   *string
	ExecutedAt     time.Time
}

// CommandQuotaUsage tracks quota usage in a period
type CommandQuotaUsage struct {
	ID                 int64
	UserID             int64
	CommandType        string
	UsagePeriod        string // 'daily', 'weekly', 'monthly'
	PeriodStart        time.Time
	PeriodEnd          time.Time
	CommandsExecuted   int
	TotalCPUUsage      int
	TotalMemoryUsage   int
	CreatedAt          time.Time
	UpdatedAt          time.Time
}

// CommandQuotaRequest is a request to check if a command can be executed
type CommandQuotaRequest struct {
	UserID        int64
	SessionID     *string
	CommandType   string
	CommandSize   int  // Approx command string length
	EstimatedCPU  int  // Estimated CPU cost %
	EstimatedMem  int  // Estimated memory cost MB
}

// CommandQuotaStatus contains current quota usage information
type CommandQuotaStatus struct {
	Daily    PeriodStatus
	Weekly   PeriodStatus
	Monthly  PeriodStatus
	ThrottleFactor float64
	SystemLoad SystemLoadStatus
}

// PeriodStatus contains quota status for a period
type PeriodStatus struct {
	Period      string
	Limit       int
	Used        int
	Remaining   int
	PercentUsed float64
	ResetsAt    time.Time
}

// SystemLoadStatus contains current system load information
type SystemLoadStatus struct {
	CPUPercent    float64
	MemoryPercent float64
	ThrottleActive bool
}

// CommandQuotaDecision is the result of a quota check
type CommandQuotaDecision struct {
	Allowed              bool
	RemainingDaily       int
	RemainingWeekly      int
	RemainingMonthly     int
	EstimatedExecuteTime time.Duration
	ThrottleFactor       float64  // 1.0 = no throttle, 0.5 = half speed, 0.0 = blocked
	WarningMessage       string
	ResetTime            time.Time
}

// CommandQuotaService manages command execution quotas
type CommandQuotaService struct {
	db              *gorm.DB
	rateLimiter     RateLimiter
	resourceMonitor *ResourceMonitor
	quotaCache      map[string]*CommandQuotaRule
	cacheTTL        time.Time
}

// NewCommandQuotaService creates a new command quota service
func NewCommandQuotaService(db *gorm.DB, rateLimiter RateLimiter, resourceMonitor *ResourceMonitor) *CommandQuotaService {
	return &CommandQuotaService{
		db:              db,
		rateLimiter:     rateLimiter,
		resourceMonitor: resourceMonitor,
		quotaCache:      make(map[string]*CommandQuotaRule),
	}
}

// CheckCommandQuota checks if a command can be executed based on user quotas
func (cqs *CommandQuotaService) CheckCommandQuota(ctx context.Context, req CommandQuotaRequest) (CommandQuotaDecision, error) {
	decision := CommandQuotaDecision{
		Allowed:        true,
		ThrottleFactor: 1.0,
	}

	// Get user's quota rules
	rule, err := cqs.getQuotaRule(ctx, req.UserID, req.CommandType)
	if err != nil || rule == nil {
		// If no rule found, use defaults
		rule, err = cqs.getQuotaRule(ctx, 0, req.CommandType)
		if err != nil {
			return decision, fmt.Errorf("failed to get quota rules: %w", err)
		}
	}

	if rule == nil || !rule.Enabled {
		return decision, nil // No quota configured
	}

	// Check daily quota
	daily, err := cqs.getQuotaUsage(ctx, req.UserID, req.CommandType, QuotaPeriodDaily)
	if err != nil {
		return decision, fmt.Errorf("failed to check daily quota: %w", err)
	}

	if daily != nil && daily.CommandsExecuted >= rule.DailyLimit {
		decision.Allowed = false
		decision.ResetTime = daily.PeriodEnd
		decision.WarningMessage = fmt.Sprintf("Daily command quota exceeded (%d/%d). Resets at %s",
			daily.CommandsExecuted, rule.DailyLimit, daily.PeriodEnd.Format("15:04 MST"))
		return decision, nil
	}

	// Check weekly quota
	weekly, err := cqs.getQuotaUsage(ctx, req.UserID, req.CommandType, QuotaPeriodWeekly)
	if err != nil {
		return decision, fmt.Errorf("failed to check weekly quota: %w", err)
	}

	if weekly != nil && weekly.CommandsExecuted >= rule.WeeklyLimit {
		decision.Allowed = false
		decision.ResetTime = weekly.PeriodEnd
		decision.WarningMessage = fmt.Sprintf("Weekly command quota exceeded (%d/%d). Resets at %s",
			weekly.CommandsExecuted, rule.WeeklyLimit, weekly.PeriodEnd.Format("Monday 15:04"))
		return decision, nil
	}

	// Check monthly quota
	monthly, err := cqs.getQuotaUsage(ctx, req.UserID, req.CommandType, QuotaPeriodMonthly)
	if err != nil {
		return decision, fmt.Errorf("failed to check monthly quota: %w", err)
	}

	if monthly != nil && monthly.CommandsExecuted >= rule.MonthlyLimit {
		decision.Allowed = false
		decision.ResetTime = monthly.PeriodEnd
		decision.WarningMessage = fmt.Sprintf("Monthly command quota exceeded (%d/%d). Resets at %s",
			monthly.CommandsExecuted, rule.MonthlyLimit, monthly.PeriodEnd.Format("Jan 02"))
		return decision, nil
	}

	// Set remaining quotas
	if daily != nil {
		decision.RemainingDaily = rule.DailyLimit - daily.CommandsExecuted
	} else {
		decision.RemainingDaily = rule.DailyLimit
	}

	if weekly != nil {
		decision.RemainingWeekly = rule.WeeklyLimit - weekly.CommandsExecuted
	} else {
		decision.RemainingWeekly = rule.WeeklyLimit
	}

	if monthly != nil {
		decision.RemainingMonthly = rule.MonthlyLimit - monthly.CommandsExecuted
	} else {
		decision.RemainingMonthly = rule.MonthlyLimit
	}

	// Check system load and apply throttling
	if cqs.resourceMonitor != nil {
		decision.ThrottleFactor = cqs.resourceMonitor.GetThrottleMultiplier()
		if decision.ThrottleFactor < 1.0 {
			decision.WarningMessage = fmt.Sprintf("System load high. Running at %.0f%% speed",
				decision.ThrottleFactor*100)
		}
	}

	return decision, nil
}

// RecordCommandExecution records a command execution
func (cqs *CommandQuotaService) RecordCommandExecution(ctx context.Context, userID int64, cmdType string, duration time.Duration, cpuUsage float64, memUsage int) error {
	// Create execution record
	execution := CommandExecution{
		UserID:          userID,
		CommandType:     cmdType,
		DurationMs:      int(duration.Milliseconds()),
		CPUUsagePercent: cpuUsage,
		MemoryUsageMB:   memUsage,
		ExecutedAt:      time.Now(),
	}

	// Record in database
	if err := cqs.db.WithContext(ctx).Table("command_executions").Create(&execution).Error; err != nil {
		return fmt.Errorf("failed to record command execution: %w", err)
	}

	// Update quota usage for all periods
	now := time.Now()
	for _, period := range []string{QuotaPeriodDaily, QuotaPeriodWeekly, QuotaPeriodMonthly} {
		start, end := cqs.getPeriodBounds(now, period)
		if err := cqs.updateQuotaUsage(ctx, userID, cmdType, period, start, end); err != nil {
			// Log error but don't fail the entire operation
			fmt.Printf("Warning: failed to update %s quota: %v\n", period, err)
		}
	}

	return nil
}

// GetUserQuotaStatus returns current quota status for a user
func (cqs *CommandQuotaService) GetUserQuotaStatus(ctx context.Context, userID int64) (CommandQuotaStatus, error) {
	status := CommandQuotaStatus{}

	now := time.Now()

	// Get status for each period
	for _, period := range []string{QuotaPeriodDaily, QuotaPeriodWeekly, QuotaPeriodMonthly} {
		// Get aggregate usage across all command types
		var totalUsed int
		var rule CommandQuotaRule
		limit := 0

		// Sum usage across all command types
		if err := cqs.db.WithContext(ctx).
			Table("command_quota_usage").
			Where("user_id = ? AND usage_period = ? AND period_start <= ? AND period_end > ?",
				userID, period, now, now).
			Select("SUM(commands_executed)").
			Scan(&totalUsed).Error; err != nil {
			return status, fmt.Errorf("failed to get %s usage: %w", period, err)
		}

		// Get limit for this period from default rules
		switch period {
		case QuotaPeriodDaily:
			if err := cqs.db.WithContext(ctx).
				Where("user_id IS NULL AND command_type = ?", CommandTypeShell).
				First(&rule).Error; err == nil {
				limit = rule.DailyLimit
			}
			status.Daily = PeriodStatus{
				Period:      period,
				Limit:       limit,
				Used:        totalUsed,
				Remaining:   limit - totalUsed,
				PercentUsed: float64(totalUsed) / float64(limit) * 100,
				ResetsAt:    now.AddDate(0, 0, 1),
			}
		case QuotaPeriodWeekly:
			if err := cqs.db.WithContext(ctx).
				Where("user_id IS NULL AND command_type = ?", CommandTypeShell).
				First(&rule).Error; err == nil {
				limit = rule.WeeklyLimit
			}
			status.Weekly = PeriodStatus{
				Period:      period,
				Limit:       limit,
				Used:        totalUsed,
				Remaining:   limit - totalUsed,
				PercentUsed: float64(totalUsed) / float64(limit) * 100,
				ResetsAt:    now.AddDate(0, 0, 7-int(now.Weekday())),
			}
		case QuotaPeriodMonthly:
			if err := cqs.db.WithContext(ctx).
				Where("user_id IS NULL AND command_type = ?", CommandTypeShell).
				First(&rule).Error; err == nil {
				limit = rule.MonthlyLimit
			}
			status.Monthly = PeriodStatus{
				Period:      period,
				Limit:       limit,
				Used:        totalUsed,
				Remaining:   limit - totalUsed,
				PercentUsed: float64(totalUsed) / float64(limit) * 100,
				ResetsAt:    now.AddDate(0, 1, 0),
			}
		}
	}

	// Get system load
	if cqs.resourceMonitor != nil {
		status.ThrottleFactor = cqs.resourceMonitor.GetThrottleMultiplier()
		status.SystemLoad = SystemLoadStatus{
			CPUPercent:    cqs.resourceMonitor.GetSystemCPUPercent(),
			MemoryPercent: cqs.resourceMonitor.GetSystemMemoryPercent(),
			ThrottleActive: status.ThrottleFactor < 1.0,
		}
	}

	return status, nil
}

// Helper functions

func (cqs *CommandQuotaService) getQuotaRule(ctx context.Context, userID int64, cmdType string) (*CommandQuotaRule, error) {
	var rule CommandQuotaRule

	// Try user-specific rule first
	if userID > 0 {
		if err := cqs.db.WithContext(ctx).
			Where("user_id = ? AND command_type = ? AND enabled = true", userID, cmdType).
			First(&rule).Error; err == nil {
			return &rule, nil
		}
	}

	// Fall back to global default
	if err := cqs.db.WithContext(ctx).
		Where("user_id IS NULL AND command_type = ? AND enabled = true", cmdType).
		First(&rule).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, err
	}

	return &rule, nil
}

func (cqs *CommandQuotaService) getQuotaUsage(ctx context.Context, userID int64, cmdType string, period string) (*CommandQuotaUsage, error) {
	now := time.Now()
	start, _ := cqs.getPeriodBounds(now, period)

	var usage CommandQuotaUsage
	err := cqs.db.WithContext(ctx).
		Where("user_id = ? AND command_type = ? AND usage_period = ? AND period_start = ?",
			userID, cmdType, period, start).
		First(&usage).Error

	if err == gorm.ErrRecordNotFound {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	return &usage, nil
}

func (cqs *CommandQuotaService) updateQuotaUsage(ctx context.Context, userID int64, cmdType string, period string, start time.Time, end time.Time) error {
	usage := CommandQuotaUsage{
		UserID:         userID,
		CommandType:    cmdType,
		UsagePeriod:    period,
		PeriodStart:    start,
		PeriodEnd:      end,
		CommandsExecuted: 1,
	}

	// Insert or update (increment counter)
	return cqs.db.WithContext(ctx).
		Table("command_quota_usage").
		Where("user_id = ? AND command_type = ? AND usage_period = ? AND period_start = ?",
			userID, cmdType, period, start).
		Clauses(clause.OnConflict{
			UpdateAll: true,
		}).
		Create(&usage).Error
}

func (cqs *CommandQuotaService) getPeriodBounds(now time.Time, period string) (time.Time, time.Time) {
	switch period {
	case QuotaPeriodDaily:
		start := now.Truncate(24 * time.Hour)
		return start, start.AddDate(0, 0, 1)
	case QuotaPeriodWeekly:
		// Week starts on Sunday
		start := now.AddDate(0, 0, -int(now.Weekday())).Truncate(24 * time.Hour)
		return start, start.AddDate(0, 0, 7)
	case QuotaPeriodMonthly:
		start := now.AddDate(0, 0, -now.Day()+1).Truncate(24 * time.Hour)
		return start, start.AddDate(0, 1, 0)
	}
	return now, now.Add(24 * time.Hour)
}
