package rate_limiting

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"gorm.io/datatypes"
	"gorm.io/gorm"
)

// BulkOperationType represents the type of bulk operation
type BulkOperationType string

const (
	BulkOperationApprove        BulkOperationType = "bulk_approve"
	BulkOperationDeny           BulkOperationType = "bulk_deny"
	BulkOperationPriorityAssign BulkOperationType = "bulk_priority_assign"
	BulkOperationExport         BulkOperationType = "bulk_export"
)

// BulkOperationStatus represents the status of a bulk operation
type BulkOperationStatus string

const (
	BulkStatusInProgress BulkOperationStatus = "in_progress"
	BulkStatusCompleted  BulkOperationStatus = "completed"
	BulkStatusFailed     BulkOperationStatus = "failed"
	BulkStatusCancelled  BulkOperationStatus = "cancelled"
)

// BulkOperation represents a bulk appeal operation
type BulkOperation struct {
	ID              int64
	OperationID     string
	AdminID         int
	OperationType   BulkOperationType
	FilterCriteria  datatypes.JSONMap
	TotalSelected   int
	TotalProcessed  int
	TotalSucceeded  int
	TotalFailed     int
	Status          BulkOperationStatus
	ErrorMessage    *string
	StartedAt       time.Time
	CompletedAt     *time.Time
	CreatedAt       time.Time
}

// AdminBulkOperationsService manages bulk admin operations on appeals
type AdminBulkOperationsService struct {
	db               *gorm.DB
	appealSvc        *AppealService
	notificationSvc  *AppealNotificationService
	historySvc       *AppealHistoryService
}

// NewAdminBulkOperationsService creates a new bulk operations service
func NewAdminBulkOperationsService(
	db *gorm.DB,
	appealSvc *AppealService,
	notificationSvc *AppealNotificationService,
	historySvc *AppealHistoryService,
) *AdminBulkOperationsService {
	return &AdminBulkOperationsService{
		db:              db,
		appealSvc:       appealSvc,
		notificationSvc: notificationSvc,
		historySvc:      historySvc,
	}
}

// BulkApproveAppeals approves multiple appeals matching criteria
func (abos *AdminBulkOperationsService) BulkApproveAppeals(
	ctx context.Context,
	adminID int,
	criteria map[string]interface{},
	approvedPoints float64,
	comment string,
) (*BulkOperation, error) {
	operation, err := abos.startBulkOperation(
		ctx,
		adminID,
		BulkOperationApprove,
		criteria,
	)
	if err != nil {
		return nil, err
	}

	// Get appeals matching criteria
	appeals, err := abos.getAppealsMatchingCriteria(ctx, criteria)
	if err != nil {
		abos.markBulkOperationFailed(ctx, operation.OperationID, err.Error())
		return nil, err
	}

	operation.TotalSelected = len(appeals)
	abos.updateBulkOperation(ctx, operation.OperationID, map[string]interface{}{
		"total_selected": len(appeals),
	})

	// Process each appeal
	for _, appeal := range appeals {
		if err := abos.approveAppeal(ctx, operation.OperationID, adminID, &appeal, approvedPoints, comment); err != nil {
			operation.TotalFailed++
		} else {
			operation.TotalSucceeded++
		}
		operation.TotalProcessed++
	}

	// Mark operation complete
	abos.markBulkOperationCompleted(ctx, operation.OperationID, operation.TotalSucceeded, operation.TotalFailed)

	return operation, nil
}

// BulkDenyAppeals denies multiple appeals matching criteria
func (abos *AdminBulkOperationsService) BulkDenyAppeals(
	ctx context.Context,
	adminID int,
	criteria map[string]interface{},
	rejectionReason string,
	comment string,
) (*BulkOperation, error) {
	operation, err := abos.startBulkOperation(
		ctx,
		adminID,
		BulkOperationDeny,
		criteria,
	)
	if err != nil {
		return nil, err
	}

	// Get appeals matching criteria
	appeals, err := abos.getAppealsMatchingCriteria(ctx, criteria)
	if err != nil {
		abos.markBulkOperationFailed(ctx, operation.OperationID, err.Error())
		return nil, err
	}

	operation.TotalSelected = len(appeals)
	abos.updateBulkOperation(ctx, operation.OperationID, map[string]interface{}{
		"total_selected": len(appeals),
	})

	// Process each appeal
	for _, appeal := range appeals {
		if err := abos.denyAppeal(ctx, operation.OperationID, adminID, &appeal, rejectionReason, comment); err != nil {
			operation.TotalFailed++
		} else {
			operation.TotalSucceeded++
		}
		operation.TotalProcessed++
	}

	// Mark operation complete
	abos.markBulkOperationCompleted(ctx, operation.OperationID, operation.TotalSucceeded, operation.TotalFailed)

	return operation, nil
}

// BulkAssignPriority assigns priority to multiple appeals
func (abos *AdminBulkOperationsService) BulkAssignPriority(
	ctx context.Context,
	adminID int,
	criteria map[string]interface{},
	newPriority AppealPriority,
) (*BulkOperation, error) {
	operation, err := abos.startBulkOperation(
		ctx,
		adminID,
		BulkOperationPriorityAssign,
		criteria,
	)
	if err != nil {
		return nil, err
	}

	// Get appeals matching criteria
	appeals, err := abos.getAppealsMatchingCriteria(ctx, criteria)
	if err != nil {
		abos.markBulkOperationFailed(ctx, operation.OperationID, err.Error())
		return nil, err
	}

	operation.TotalSelected = len(appeals)
	abos.updateBulkOperation(ctx, operation.OperationID, map[string]interface{}{
		"total_selected": len(appeals),
	})

	// Update priorities
	for _, appeal := range appeals {
		if err := abos.db.WithContext(ctx).
			Table("appeals").
			Where("id = ?", appeal.ID).
			Update("priority", newPriority).Error; err != nil {
			operation.TotalFailed++
		} else {
			operation.TotalSucceeded++
		}
		operation.TotalProcessed++
	}

	// Mark operation complete
	abos.markBulkOperationCompleted(ctx, operation.OperationID, operation.TotalSucceeded, operation.TotalFailed)

	return operation, nil
}

// GetBulkOperationStatus returns status of a bulk operation
func (abos *AdminBulkOperationsService) GetBulkOperationStatus(
	ctx context.Context,
	operationID string,
) (*BulkOperation, error) {
	var operation BulkOperation
	result := abos.db.WithContext(ctx).
		Table("bulk_appeal_operations").
		Where("operation_id = ?", operationID).
		First(&operation)

	return &operation, result.Error
}

// GetAdminBulkOperations returns all bulk operations for an admin
func (abos *AdminBulkOperationsService) GetAdminBulkOperations(
	ctx context.Context,
	adminID int,
	limit int,
	offset int,
) ([]BulkOperation, error) {
	var operations []BulkOperation
	result := abos.db.WithContext(ctx).
		Table("bulk_appeal_operations").
		Where("admin_id = ?", adminID).
		Order("started_at DESC").
		Limit(limit).
		Offset(offset).
		Scan(&operations)

	return operations, result.Error
}

// startBulkOperation creates and starts a bulk operation
func (abos *AdminBulkOperationsService) startBulkOperation(
	ctx context.Context,
	adminID int,
	operationType BulkOperationType,
	criteria map[string]interface{},
) (*BulkOperation, error) {
	operationID := fmt.Sprintf("bulk_%d_%d", adminID, time.Now().UnixNano())

	// Convert criteria to JSON
	criteriaJSON, _ := json.Marshal(criteria)
	criteriaMap := datatypes.JSONMap{}
	json.Unmarshal(criteriaJSON, &criteriaMap)

	operation := BulkOperation{
		OperationID:    operationID,
		AdminID:        adminID,
		OperationType:  operationType,
		FilterCriteria: criteriaMap,
		Status:         BulkStatusInProgress,
		StartedAt:      time.Now(),
		CreatedAt:      time.Now(),
	}

	result := abos.db.WithContext(ctx).
		Table("bulk_appeal_operations").
		Create(&operation)

	if result.Error != nil {
		return nil, result.Error
	}

	return &operation, nil
}

// getAppealsMatchingCriteria retrieves appeals matching filter criteria
func (abos *AdminBulkOperationsService) getAppealsMatchingCriteria(
	ctx context.Context,
	criteria map[string]interface{},
) ([]Appeal, error) {
	query := abos.db.WithContext(ctx).Table("appeals")

	// Apply filters
	if status, exists := criteria["status"].(string); exists {
		query = query.Where("status = ?", status)
	}

	if priority, exists := criteria["priority"].(string); exists {
		query = query.Where("priority = ?", priority)
	}

	if minDaysOld, exists := criteria["min_days_old"].(int); exists {
		cutoffDate := time.Now().AddDate(0, 0, -minDaysOld)
		query = query.Where("created_at < ?", cutoffDate)
	}

	if reason, exists := criteria["reason"].(string); exists {
		query = query.Where("reason = ?", reason)
	}

	if maxAppealsPerUser, exists := criteria["max_appeals_per_user"].(int); exists {
		// Subquery for users with <= max appeals
		query = query.Where("user_id IN (SELECT user_id FROM appeals GROUP BY user_id HAVING COUNT(*) <= ?)", maxAppealsPerUser)
	}

	var appeals []Appeal
	result := query.Scan(&appeals)

	return appeals, result.Error
}

// approveAppeal approves a single appeal
func (abos *AdminBulkOperationsService) approveAppeal(
	ctx context.Context,
	operationID string,
	adminID int,
	appeal *Appeal,
	approvedPoints float64,
	comment string,
) error {
	// Update appeal
	if err := abos.db.WithContext(ctx).
		Table("appeals").
		Where("id = ?", appeal.ID).
		Updates(map[string]interface{}{
			"status":           AppealApproved,
			"reviewed_by":      fmt.Sprintf("bulk_admin_%d", adminID),
			"review_comment":   comment,
			"approved_points":  approvedPoints,
			"resolved_at":      time.Now(),
			"updated_at":       time.Now(),
		}).Error; err != nil {
		return err
	}

	// Record status change
	return abos.historySvc.RecordStatusChange(
		ctx,
		appeal.ID,
		appeal.Status,
		AppealApproved,
		fmt.Sprintf("bulk_operation_%s", operationID),
		fmt.Sprintf("Approved via bulk operation: %s", comment),
		map[string]interface{}{
			"operation_id":     operationID,
			"approved_points":  approvedPoints,
		},
	)
}

// denyAppeal denies a single appeal
func (abos *AdminBulkOperationsService) denyAppeal(
	ctx context.Context,
	operationID string,
	adminID int,
	appeal *Appeal,
	rejectionReason string,
	comment string,
) error {
	// Update appeal
	if err := abos.db.WithContext(ctx).
		Table("appeals").
		Where("id = ?", appeal.ID).
		Updates(map[string]interface{}{
			"status":         AppealDenied,
			"reviewed_by":    fmt.Sprintf("bulk_admin_%d", adminID),
			"review_comment": comment,
			"resolution":     rejectionReason,
			"resolved_at":    time.Now(),
			"updated_at":     time.Now(),
		}).Error; err != nil {
		return err
	}

	// Record status change
	return abos.historySvc.RecordStatusChange(
		ctx,
		appeal.ID,
		appeal.Status,
		AppealDenied,
		fmt.Sprintf("bulk_operation_%s", operationID),
		fmt.Sprintf("Denied via bulk operation: %s", comment),
		map[string]interface{}{
			"operation_id":       operationID,
			"rejection_reason":   rejectionReason,
		},
	)
}

// updateBulkOperation updates operation fields
func (abos *AdminBulkOperationsService) updateBulkOperation(
	ctx context.Context,
	operationID string,
	updates map[string]interface{},
) error {
	return abos.db.WithContext(ctx).
		Table("bulk_appeal_operations").
		Where("operation_id = ?", operationID).
		Updates(updates).Error
}

// markBulkOperationCompleted marks operation as completed
func (abos *AdminBulkOperationsService) markBulkOperationCompleted(
	ctx context.Context,
	operationID string,
	totalSucceeded int,
	totalFailed int,
) error {
	now := time.Now()
	return abos.db.WithContext(ctx).
		Table("bulk_appeal_operations").
		Where("operation_id = ?", operationID).
		Updates(map[string]interface{}{
			"status":           BulkStatusCompleted,
			"total_succeeded":  totalSucceeded,
			"total_failed":     totalFailed,
			"completed_at":     now,
		}).Error
}

// markBulkOperationFailed marks operation as failed
func (abos *AdminBulkOperationsService) markBulkOperationFailed(
	ctx context.Context,
	operationID string,
	errorMessage string,
) error {
	now := time.Now()
	return abos.db.WithContext(ctx).
		Table("bulk_appeal_operations").
		Where("operation_id = ?", operationID).
		Updates(map[string]interface{}{
			"status":        BulkStatusFailed,
			"error_message": errorMessage,
			"completed_at":  now,
		}).Error
}

// GetBulkOperationStats returns statistics for bulk operations
func (abos *AdminBulkOperationsService) GetBulkOperationStats(
	ctx context.Context,
) (map[string]interface{}, error) {
	var stats struct {
		TotalOperations  int64
		CompletedCount   int64
		SuccessfulCount  int64
		FailedCount      int64
		TotalAppealsProcessed int64
		AvgSuccessRate   float64
	}

	abos.db.WithContext(ctx).
		Table("bulk_appeal_operations").
		Count(&stats.TotalOperations)

	abos.db.WithContext(ctx).
		Table("bulk_appeal_operations").
		Where("status = ?", BulkStatusCompleted).
		Count(&stats.CompletedCount)

	abos.db.WithContext(ctx).
		Table("bulk_appeal_operations").
		Where("status = ?", BulkStatusFailed).
		Count(&stats.FailedCount)

	abos.db.WithContext(ctx).
		Table("bulk_appeal_operations").
		Select("SUM(total_processed) as total").
		Scan(&stats.TotalAppealsProcessed)

	// Calculate average success rate
	abos.db.WithContext(ctx).
		Table("bulk_appeal_operations").
		Where("status = ?", BulkStatusCompleted).
		Select("AVG(CAST(total_succeeded as FLOAT) / CAST(total_processed as FLOAT) * 100) as rate").
		Scan(&stats.AvgSuccessRate)

	return map[string]interface{}{
		"total_operations":        stats.TotalOperations,
		"completed_operations":    stats.CompletedCount,
		"failed_operations":       stats.FailedCount,
		"total_appeals_processed": stats.TotalAppealsProcessed,
		"avg_success_rate_percent": stats.AvgSuccessRate,
	}, nil
}
