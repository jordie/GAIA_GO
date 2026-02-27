package rate_limiting

import (
	"context"
	"fmt"
	"time"

	"gorm.io/gorm"
)

// AppealStatus defines possible appeal statuses
type AppealStatus string

const (
	AppealPending    AppealStatus = "pending"
	AppealReviewing  AppealStatus = "reviewing"
	AppealApproved   AppealStatus = "approved"
	AppealDenied     AppealStatus = "denied"
	AppealExpired    AppealStatus = "expired"
	AppealWithdrawn  AppealStatus = "withdrawn"
)

// AppealPriority defines appeal priority level
type AppealPriority string

const (
	AppealLow      AppealPriority = "low"
	AppealMedium   AppealPriority = "medium"
	AppealHigh     AppealPriority = "high"
	AppealCritical AppealPriority = "critical"
)

// Appeal represents a user appeal against a violation
type Appeal struct {
	ID              int          `json:"id" gorm:"primaryKey"`
	UserID          int          `json:"user_id" gorm:"index"`
	ViolationID     int          `json:"violation_id" gorm:"index"`
	Status          AppealStatus `json:"status" gorm:"index"`
	Priority        AppealPriority `json:"priority"`
	Reason          string       `json:"reason"`
	Description     string       `json:"description"`
	Evidence        string       `json:"evidence"` // JSON array of file URLs
	ReputationLost  float64      `json:"reputation_lost"`
	RequestedAction string       `json:"requested_action"` // "restore", "reduce", "waive"
	ReviewedBy      *string      `json:"reviewed_by"`
	ReviewComment   *string      `json:"review_comment"`
	Resolution      *string      `json:"resolution"` // What action was taken
	ApprovedPoints  *float64     `json:"approved_points"` // How many points restored
	CreatedAt       time.Time    `json:"created_at" gorm:"index"`
	UpdatedAt       time.Time    `json:"updated_at"`
	ExpiresAt       time.Time    `json:"expires_at"`
	ResolvedAt      *time.Time   `json:"resolved_at"`
}

// AppealReason represents predefined appeal reasons
type AppealReason struct {
	ID          int    `json:"id" gorm:"primaryKey"`
	Code        string `json:"code" gorm:"unique"`
	Name        string `json:"name"`
	Description string `json:"description"`
	Priority    string `json:"priority"` // low, medium, high
	Enabled     bool   `json:"enabled" gorm:"default:true"`
	CreatedAt   time.Time `json:"created_at"`
}

// AppealMetrics represents appeal performance metrics
type AppealMetrics struct {
	TotalAppeals      int64          `json:"total_appeals"`
	PendingAppeals    int64          `json:"pending_appeals"`
	ApprovedAppeals   int64          `json:"approved_appeals"`
	DeniedAppeals     int64          `json:"denied_appeals"`
	ApprovalRate      float64        `json:"approval_rate"`
	AvgResolutionTime float64        `json:"avg_resolution_time_hours"`
	PointsRestored    float64        `json:"points_restored"`
	AppealsPerUser    map[int]int64  `json:"appeals_per_user"`
}

// AppealService manages user appeals against violations
type AppealService struct {
	db               *gorm.DB
	reputationMgr    *ReputationManager
	appealWindowDays int
	maxAppealsPerUser int
}

// NewAppealService creates a new appeal service
func NewAppealService(db *gorm.DB, rm *ReputationManager) *AppealService {
	as := &AppealService{
		db:               db,
		reputationMgr:    rm,
		appealWindowDays: 30,
		maxAppealsPerUser: 5,
	}

	// Initialize default appeal reasons
	as.initializeAppealReasons()

	return as
}

// initializeAppealReasons creates default appeal reason options
func (as *AppealService) initializeAppealReasons() {
	reasons := []AppealReason{
		{
			Code:        "false_positive",
			Name:        "False Positive",
			Description: "I believe this violation was recorded incorrectly",
			Priority:    "high",
		},
		{
			Code:        "system_error",
			Name:        "System Error",
			Description: "The violation was caused by a system or API error",
			Priority:    "high",
		},
		{
			Code:        "legitimate_use",
			Name:        "Legitimate Use",
			Description: "I was using the API correctly according to documentation",
			Priority:    "medium",
		},
		{
			Code:        "burst_needed",
			Name:        "Burst Was Necessary",
			Description: "The spike in requests was necessary for legitimate business reasons",
			Priority:    "medium",
		},
		{
			Code:        "shared_account",
			Name:        "Shared Account",
			Description: "Multiple users on shared account caused spike",
			Priority:    "low",
		},
		{
			Code:        "learning_curve",
			Name:        "Learning Curve",
			Description: "I was learning the API and didn't know better",
			Priority:    "low",
		},
		{
			Code:        "other",
			Name:        "Other Reason",
			Description: "Other reason (please describe)",
			Priority:    "medium",
		},
	}

	for _, reason := range reasons {
		as.db.FirstOrCreate(&reason, AppealReason{Code: reason.Code})
	}
}

// SubmitAppeal creates a new appeal for a violation
func (as *AppealService) SubmitAppeal(ctx context.Context, userID int, violationID int, req struct {
	Reason          string
	Description     string
	Evidence        string
	RequestedAction string
}) (*Appeal, error) {
	// Check if violation exists and belongs to user
	var violation ReputationEvent
	if err := as.db.Where("id = ? AND user_id = ?", violationID, userID).
		First(&violation).Error; err != nil {
		return nil, fmt.Errorf("violation not found")
	}

	// Check if within appeal window (30 days)
	if time.Since(violation.Timestamp) > time.Duration(as.appealWindowDays)*24*time.Hour {
		return nil, fmt.Errorf("appeal window expired (30 days)")
	}

	// Check if already appealed
	var existing Appeal
	if err := as.db.Where("user_id = ? AND violation_id = ? AND status != ?",
		userID, violationID, AppealDenied).
		First(&existing).Error; err == nil {
		return nil, fmt.Errorf("violation already appealed")
	}

	// Check user hasn't exceeded max appeals
	var appealCount int64
	as.db.Model(&Appeal{}).
		Where("user_id = ? AND created_at > ?", userID, time.Now().AddDate(0, 0, -90)).
		Count(&appealCount)

	if appealCount >= int64(as.maxAppealsPerUser) {
		return nil, fmt.Errorf("maximum appeals per 90 days exceeded")
	}

	// Validate requested action
	if req.RequestedAction != "restore" && req.RequestedAction != "reduce" && req.RequestedAction != "waive" {
		return nil, fmt.Errorf("invalid requested action")
	}

	// Determine priority based on reason
	priority := AppealMedium
	if req.Reason == "false_positive" || req.Reason == "system_error" {
		priority = AppealHigh
	} else if req.Reason == "other" {
		priority = AppealLow
	}

	// Create appeal
	appeal := &Appeal{
		UserID:          userID,
		ViolationID:     violationID,
		Status:          AppealPending,
		Priority:        priority,
		Reason:          req.Reason,
		Description:     req.Description,
		Evidence:        req.Evidence,
		ReputationLost:  -violation.ScoreDelta,
		RequestedAction: req.RequestedAction,
		CreatedAt:       time.Now(),
		UpdatedAt:       time.Now(),
		ExpiresAt:       time.Now().AddDate(0, 0, as.appealWindowDays),
	}

	if err := as.db.Create(appeal).Error; err != nil {
		return nil, err
	}

	return appeal, nil
}

// GetUserAppeals returns all appeals for a user
func (as *AppealService) GetUserAppeals(ctx context.Context, userID int, status *AppealStatus) ([]Appeal, error) {
	var appeals []Appeal

	query := as.db.WithContext(ctx).Where("user_id = ?", userID)
	if status != nil {
		query = query.Where("status = ?", *status)
	}

	if err := query.Order("created_at DESC").Find(&appeals).Error; err != nil {
		return nil, err
	}

	return appeals, nil
}

// GetPendingAppeals returns appeals pending review
func (as *AppealService) GetPendingAppeals(ctx context.Context, limit int) ([]Appeal, error) {
	var appeals []Appeal

	if err := as.db.WithContext(ctx).
		Where("status IN ?", []AppealStatus{AppealPending, AppealReviewing}).
		Order("priority DESC, created_at ASC").
		Limit(limit).
		Find(&appeals).Error; err != nil {
		return nil, err
	}

	return appeals, nil
}

// ReviewAppeal reviews and resolves an appeal
func (as *AppealService) ReviewAppeal(ctx context.Context, appealID int, reviewedBy string, action AppealStatus, approvedPoints float64, comment string) error {
	if action != AppealApproved && action != AppealDenied {
		return fmt.Errorf("invalid action")
	}

	appeal := &Appeal{}
	if err := as.db.First(appeal, appealID).Error; err != nil {
		return err
	}

	// Update appeal status
	now := time.Now()
	updates := map[string]interface{}{
		"status":         action,
		"reviewed_by":    reviewedBy,
		"review_comment": comment,
		"resolved_at":    now,
		"updated_at":     now,
	}

	if action == AppealApproved {
		updates["approved_points"] = approvedPoints
		updates["resolution"] = "Points restored"
	} else {
		updates["resolution"] = "Appeal denied"
	}

	if err := as.db.Model(appeal).Updates(updates).Error; err != nil {
		return err
	}

	// If approved, restore reputation
	if action == AppealApproved {
		as.reputationMgr.UpdateUserReputation(appeal.UserID, approvedPoints)
	}

	return nil
}

// WithdrawAppeal allows user to withdraw their appeal
func (as *AppealService) WithdrawAppeal(ctx context.Context, userID int, appealID int) error {
	appeal := &Appeal{}
	if err := as.db.Where("id = ? AND user_id = ?", appealID, userID).
		First(appeal).Error; err != nil {
		return fmt.Errorf("appeal not found")
	}

	if appeal.Status != AppealPending && appeal.Status != AppealReviewing {
		return fmt.Errorf("cannot withdraw appeal in %s status", appeal.Status)
	}

	now := time.Now()
	return as.db.Model(appeal).Updates(map[string]interface{}{
		"status":      AppealWithdrawn,
		"updated_at":  now,
		"resolved_at": now,
	}).Error
}

// GetAppealReasons returns available appeal reasons
func (as *AppealService) GetAppealReasons(ctx context.Context) ([]AppealReason, error) {
	var reasons []AppealReason

	if err := as.db.WithContext(ctx).
		Where("enabled = ?", true).
		Find(&reasons).Error; err != nil {
		return nil, err
	}

	return reasons, nil
}

// GetAppealMetrics returns appeal statistics
func (as *AppealService) GetAppealMetrics(ctx context.Context) (*AppealMetrics, error) {
	metrics := &AppealMetrics{
		AppealsPerUser: make(map[int]int64),
	}

	// Total appeals
	as.db.Model(&Appeal{}).Count(&metrics.TotalAppeals)

	// By status
	as.db.Model(&Appeal{}).Where("status = ?", AppealPending).Count(&metrics.PendingAppeals)
	as.db.Model(&Appeal{}).Where("status = ?", AppealApproved).Count(&metrics.ApprovedAppeals)
	as.db.Model(&Appeal{}).Where("status = ?", AppealDenied).Count(&metrics.DeniedAppeals)

	// Approval rate
	if metrics.ApprovedAppeals+metrics.DeniedAppeals > 0 {
		metrics.ApprovalRate = float64(metrics.ApprovedAppeals) / float64(metrics.ApprovedAppeals+metrics.DeniedAppeals)
	}

	// Average resolution time
	var avgTime float64
	as.db.Model(&Appeal{}).
		Where("resolved_at IS NOT NULL").
		Select("AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600)").
		Scan(&avgTime)
	metrics.AvgResolutionTime = avgTime

	// Points restored
	as.db.Model(&Appeal{}).
		Where("status = ?", AppealApproved).
		Select("COALESCE(SUM(approved_points), 0)").
		Scan(&metrics.PointsRestored)

	// Appeals per user
	var userAppeals []struct {
		UserID int
		Count  int64
	}
	as.db.Model(&Appeal{}).
		Select("user_id, COUNT(*) as count").
		Group("user_id").
		Scan(&userAppeals)

	for _, ua := range userAppeals {
		metrics.AppealsPerUser[ua.UserID] = ua.Count
	}

	return metrics, nil
}

// GetAppealStats returns statistics for a user
func (as *AppealService) GetAppealStats(ctx context.Context, userID int) (map[string]interface{}, error) {
	var totalAppeals, approvedAppeals, deniedAppeals, pendingAppeals int64

	as.db.Model(&Appeal{}).Where("user_id = ?", userID).Count(&totalAppeals)
	as.db.Model(&Appeal{}).Where("user_id = ? AND status = ?", userID, AppealApproved).Count(&approvedAppeals)
	as.db.Model(&Appeal{}).Where("user_id = ? AND status = ?", userID, AppealDenied).Count(&deniedAppeals)
	as.db.Model(&Appeal{}).Where("user_id = ? AND status IN ?", userID, []AppealStatus{AppealPending, AppealReviewing}).Count(&pendingAppeals)

	var totalPointsRestored float64
	as.db.Model(&Appeal{}).
		Where("user_id = ? AND status = ?", userID, AppealApproved).
		Select("COALESCE(SUM(approved_points), 0)").
		Scan(&totalPointsRestored)

	approvalRate := 0.0
	if approvedAppeals+deniedAppeals > 0 {
		approvalRate = float64(approvedAppeals) / float64(approvedAppeals+deniedAppeals)
	}

	return map[string]interface{}{
		"total_appeals":        totalAppeals,
		"approved_appeals":     approvedAppeals,
		"denied_appeals":       deniedAppeals,
		"pending_appeals":      pendingAppeals,
		"approval_rate":        approvalRate,
		"total_points_restored": totalPointsRestored,
	}, nil
}

// ExpireOldAppeals marks old appeals as expired
func (as *AppealService) ExpireOldAppeals(ctx context.Context) (int64, error) {
	result := as.db.WithContext(ctx).
		Model(&Appeal{}).
		Where("status = ? AND expires_at < ?", AppealPending, time.Now()).
		Update("status", AppealExpired)

	return result.RowsAffected, result.Error
}
