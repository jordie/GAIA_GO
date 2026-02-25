package repository

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jgirmay/GAIA_GO/pkg/models"
	"gorm.io/gorm"
)

// DistributedTaskRepositoryImpl implements DistributedTaskRepository
type DistributedTaskRepositoryImpl struct {
	db *gorm.DB
}

// NewDistributedTaskRepository creates a new distributed task repository
func NewDistributedTaskRepository(db *gorm.DB) DistributedTaskRepository {
	return &DistributedTaskRepositoryImpl{db: db}
}

// Create creates a new task
func (r *DistributedTaskRepositoryImpl) Create(ctx context.Context, task *models.DistributedTask) error {
	return r.db.WithContext(ctx).Create(task).Error
}

// GetByID retrieves a task by ID
func (r *DistributedTaskRepositoryImpl) GetByID(ctx context.Context, id uuid.UUID) (*models.DistributedTask, error) {
	var task models.DistributedTask
	err := r.db.WithContext(ctx).Where("id = ?", id).First(&task).Error
	if err != nil {
		return nil, err
	}
	return &task, nil
}

// List retrieves all tasks
func (r *DistributedTaskRepositoryImpl) List(ctx context.Context) ([]*models.DistributedTask, error) {
	var tasks []*models.DistributedTask
	err := r.db.WithContext(ctx).Find(&tasks).Error
	return tasks, err
}

// ListByStatus retrieves tasks with a specific status
func (r *DistributedTaskRepositoryImpl) ListByStatus(ctx context.Context, status string) ([]*models.DistributedTask, error) {
	var tasks []*models.DistributedTask
	err := r.db.WithContext(ctx).Where("status = ?", status).Find(&tasks).Error
	return tasks, err
}

// ListPending retrieves pending tasks ordered by priority
func (r *DistributedTaskRepositoryImpl) ListPending(ctx context.Context, limit int) ([]*models.DistributedTask, error) {
	var tasks []*models.DistributedTask
	err := r.db.WithContext(ctx).
		Where("status = ?", "pending").
		Order("priority DESC, created_at ASC").
		Limit(limit).
		Find(&tasks).Error
	return tasks, err
}

// ListByLesson retrieves tasks for a lesson
func (r *DistributedTaskRepositoryImpl) ListByLesson(ctx context.Context, lessonID uuid.UUID) ([]*models.DistributedTask, error) {
	var tasks []*models.DistributedTask
	err := r.db.WithContext(ctx).Where("lesson_id = ?", lessonID).Find(&tasks).Error
	return tasks, err
}

// ListBySession retrieves tasks assigned to a session
func (r *DistributedTaskRepositoryImpl) ListBySession(ctx context.Context, sessionID uuid.UUID) ([]*models.DistributedTask, error) {
	var tasks []*models.DistributedTask
	err := r.db.WithContext(ctx).Where("claimed_by = ?", sessionID).Find(&tasks).Error
	return tasks, err
}

// Update updates an existing task
func (r *DistributedTaskRepositoryImpl) Update(ctx context.Context, task *models.DistributedTask) error {
	task.UpdatedAt = time.Now()
	return r.db.WithContext(ctx).Save(task).Error
}

// Delete deletes a task
func (r *DistributedTaskRepositoryImpl) Delete(ctx context.Context, id uuid.UUID) error {
	return r.db.WithContext(ctx).Delete(&models.DistributedTask{}, "id = ?", id).Error
}

// Claim claims a task for execution
func (r *DistributedTaskRepositoryImpl) Claim(ctx context.Context, id uuid.UUID, sessionID uuid.UUID, expiresAt time.Time) error {
	return r.db.WithContext(ctx).Model(&models.DistributedTask{}, "id = ?", id).
		Updates(map[string]interface{}{
			"status":           "assigned",
			"claimed_by":       sessionID,
			"claimed_at":       time.Now(),
			"claim_expires_at": expiresAt,
			"updated_at":       time.Now(),
		}).Error
}

// Complete marks a task as completed
func (r *DistributedTaskRepositoryImpl) Complete(ctx context.Context, id uuid.UUID, result interface{}) error {
	return r.db.WithContext(ctx).Model(&models.DistributedTask{}, "id = ?", id).
		Updates(map[string]interface{}{
			"status":     "completed",
			"result":     result,
			"updated_at": time.Now(),
		}).Error
}

// Fail marks a task as failed
func (r *DistributedTaskRepositoryImpl) Fail(ctx context.Context, id uuid.UUID, errorMsg string) error {
	return r.db.WithContext(ctx).Model(&models.DistributedTask{}, "id = ?", id).
		Updates(map[string]interface{}{
			"status":          "failed",
			"error_message":   errorMsg,
			"updated_at":      time.Now(),
			"claim_expires_at": nil,
		}).Error
}

// Retry increments retry count and resets status to pending
func (r *DistributedTaskRepositoryImpl) Retry(ctx context.Context, id uuid.UUID) error {
	return r.db.WithContext(ctx).Model(&models.DistributedTask{}, "id = ?", id).
		Updates(map[string]interface{}{
			"status":           "pending",
			"retry_count":      gorm.Expr("retry_count + 1"),
			"claimed_by":       nil,
			"claimed_at":       nil,
			"claim_expires_at": nil,
			"error_message":    "",
			"updated_at":       time.Now(),
		}).Error
}

// GetByIdempotencyKey retrieves a task by idempotency key
func (r *DistributedTaskRepositoryImpl) GetByIdempotencyKey(ctx context.Context, key string) (*models.DistributedTask, error) {
	var task models.DistributedTask
	err := r.db.WithContext(ctx).Where("idempotency_key = ?", key).First(&task).Error
	if err != nil {
		return nil, err
	}
	return &task, nil
}

// CleanupExpiredClaims resets expired claims
func (r *DistributedTaskRepositoryImpl) CleanupExpiredClaims(ctx context.Context) error {
	return r.db.WithContext(ctx).
		Model(&models.DistributedTask{}).
		Where("claim_expires_at IS NOT NULL").
		Where("claim_expires_at < ?", time.Now()).
		Updates(map[string]interface{}{
			"status":           "pending",
			"claimed_by":       nil,
			"claimed_at":       nil,
			"claim_expires_at": nil,
			"updated_at":       time.Now(),
		}).Error
}

// ReassignFailedSessionTasks reassigns tasks from a failed session
func (r *DistributedTaskRepositoryImpl) ReassignFailedSessionTasks(ctx context.Context, sessionID uuid.UUID) error {
	return r.db.WithContext(ctx).
		Model(&models.DistributedTask{}).
		Where("claimed_by = ?", sessionID).
		Where("status IN ?", []string{"assigned", "in_progress"}).
		Updates(map[string]interface{}{
			"status":           "pending",
			"claimed_by":       nil,
			"claimed_at":       nil,
			"claim_expires_at": nil,
			"updated_at":       time.Now(),
		}).Error
}
