package repository

import (
	"context"
	"fmt"

	"gorm.io/gorm"

	"architect-go/pkg/models"
)

// WorkerRepositoryImpl implements WorkerRepository
type WorkerRepositoryImpl struct {
	db *gorm.DB
}

// NewWorkerRepository creates a new WorkerRepositoryImpl instance
func NewWorkerRepository(db *gorm.DB) WorkerRepository {
	return &WorkerRepositoryImpl{db: db}
}

func (r *WorkerRepositoryImpl) Create(ctx context.Context, worker *models.Worker) error {
	if err := r.db.WithContext(ctx).Create(worker).Error; err != nil {
		return fmt.Errorf("failed to create worker: %w", err)
	}
	return nil
}

func (r *WorkerRepositoryImpl) Get(ctx context.Context, id string) (*models.Worker, error) {
	var worker models.Worker
	if err := r.db.WithContext(ctx).First(&worker, "id = ?", id).Error; err != nil {
		return nil, fmt.Errorf("failed to get worker: %w", err)
	}
	return &worker, nil
}

func (r *WorkerRepositoryImpl) ListByType(ctx context.Context, workerType string) ([]*models.Worker, error) {
	var workers []*models.Worker
	if err := r.db.WithContext(ctx).Where("type = ?", workerType).Find(&workers).Error; err != nil {
		return nil, fmt.Errorf("failed to list workers: %w", err)
	}
	return workers, nil
}

func (r *WorkerRepositoryImpl) List(ctx context.Context, limit int, offset int) ([]*models.Worker, int64, error) {
	var workers []*models.Worker
	var total int64
	if err := r.db.WithContext(ctx).Model(&models.Worker{}).Count(&total).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to count workers: %w", err)
	}
	if err := r.db.WithContext(ctx).Limit(limit).Offset(offset).Find(&workers).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to list workers: %w", err)
	}
	return workers, total, nil
}

func (r *WorkerRepositoryImpl) Update(ctx context.Context, worker *models.Worker) error {
	if err := r.db.WithContext(ctx).Model(worker).Updates(worker).Error; err != nil {
		return fmt.Errorf("failed to update worker: %w", err)
	}
	return nil
}

func (r *WorkerRepositoryImpl) UpdateStatus(ctx context.Context, id string, status string) error {
	if err := r.db.WithContext(ctx).Model(&models.Worker{}).Where("id = ?", id).Update("status", status).Error; err != nil {
		return fmt.Errorf("failed to update worker status: %w", err)
	}
	return nil
}

func (r *WorkerRepositoryImpl) Delete(ctx context.Context, id string) error {
	if err := r.db.WithContext(ctx).Model(&models.Worker{}).Where("id = ?", id).Update("deleted_at", gorm.Expr("CURRENT_TIMESTAMP")).Error; err != nil {
		return fmt.Errorf("failed to delete worker: %w", err)
	}
	return nil
}

// WorkerQueueRepositoryImpl implements WorkerQueueRepository
type WorkerQueueRepositoryImpl struct {
	db *gorm.DB
}

// NewWorkerQueueRepository creates a new WorkerQueueRepositoryImpl instance
func NewWorkerQueueRepository(db *gorm.DB) WorkerQueueRepository {
	return &WorkerQueueRepositoryImpl{db: db}
}

func (r *WorkerQueueRepositoryImpl) Create(ctx context.Context, item *models.WorkerQueue) error {
	if err := r.db.WithContext(ctx).Create(item).Error; err != nil {
		return fmt.Errorf("failed to create queue item: %w", err)
	}
	return nil
}

func (r *WorkerQueueRepositoryImpl) Get(ctx context.Context, id string) (*models.WorkerQueue, error) {
	var item models.WorkerQueue
	if err := r.db.WithContext(ctx).First(&item, "id = ?", id).Error; err != nil {
		return nil, fmt.Errorf("failed to get queue item: %w", err)
	}
	return &item, nil
}

func (r *WorkerQueueRepositoryImpl) ListPending(ctx context.Context, workerType string, limit int) ([]*models.WorkerQueue, error) {
	var items []*models.WorkerQueue
	if err := r.db.WithContext(ctx).
		Where("worker_type = ? AND status = ?", workerType, "pending").
		Order("priority DESC, created_at ASC").
		Limit(limit).
		Find(&items).Error; err != nil {
		return nil, fmt.Errorf("failed to list pending items: %w", err)
	}
	return items, nil
}

func (r *WorkerQueueRepositoryImpl) List(ctx context.Context, filters map[string]interface{}, limit int, offset int) ([]*models.WorkerQueue, int64, error) {
	var items []*models.WorkerQueue
	var total int64
	query := r.db.WithContext(ctx)

	if workerType, ok := filters["worker_type"]; ok {
		query = query.Where("worker_type = ?", workerType)
	}
	if status, ok := filters["status"]; ok {
		query = query.Where("status = ?", status)
	}

	if err := query.Model(&models.WorkerQueue{}).Count(&total).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to count items: %w", err)
	}
	if err := query.Limit(limit).Offset(offset).Order("priority DESC, created_at ASC").Find(&items).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to list items: %w", err)
	}
	return items, total, nil
}

func (r *WorkerQueueRepositoryImpl) Update(ctx context.Context, item *models.WorkerQueue) error {
	if err := r.db.WithContext(ctx).Model(item).Updates(item).Error; err != nil {
		return fmt.Errorf("failed to update queue item: %w", err)
	}
	return nil
}

func (r *WorkerQueueRepositoryImpl) UpdateStatus(ctx context.Context, id string, status string) error {
	if err := r.db.WithContext(ctx).Model(&models.WorkerQueue{}).Where("id = ?", id).Update("status", status).Error; err != nil {
		return fmt.Errorf("failed to update queue item status: %w", err)
	}
	return nil
}

func (r *WorkerQueueRepositoryImpl) Delete(ctx context.Context, id string) error {
	if err := r.db.WithContext(ctx).Model(&models.WorkerQueue{}).Where("id = ?", id).Update("deleted_at", gorm.Expr("CURRENT_TIMESTAMP")).Error; err != nil {
		return fmt.Errorf("failed to delete queue item: %w", err)
	}
	return nil
}

// SessionRepositoryImpl implements SessionRepository
type SessionRepositoryImpl struct {
	db *gorm.DB
}

// NewSessionRepository creates a new SessionRepositoryImpl instance
func NewSessionRepository(db *gorm.DB) SessionRepository {
	return &SessionRepositoryImpl{db: db}
}

func (r *SessionRepositoryImpl) Create(ctx context.Context, session *models.Session) error {
	if err := r.db.WithContext(ctx).Create(session).Error; err != nil {
		return fmt.Errorf("failed to create session: %w", err)
	}
	return nil
}

func (r *SessionRepositoryImpl) Get(ctx context.Context, id string) (*models.Session, error) {
	var session models.Session
	if err := r.db.WithContext(ctx).First(&session, "id = ?", id).Error; err != nil {
		return nil, fmt.Errorf("failed to get session: %w", err)
	}
	return &session, nil
}

func (r *SessionRepositoryImpl) GetByToken(ctx context.Context, token string) (*models.Session, error) {
	var session models.Session
	if err := r.db.WithContext(ctx).First(&session, "token = ?", token).Error; err != nil {
		return nil, fmt.Errorf("failed to get session by token: %w", err)
	}
	return &session, nil
}

func (r *SessionRepositoryImpl) ListByUser(ctx context.Context, userID string) ([]*models.Session, error) {
	var sessions []*models.Session
	if err := r.db.WithContext(ctx).Where("user_id = ?", userID).Find(&sessions).Error; err != nil {
		return nil, fmt.Errorf("failed to list sessions: %w", err)
	}
	return sessions, nil
}

func (r *SessionRepositoryImpl) Update(ctx context.Context, session *models.Session) error {
	if err := r.db.WithContext(ctx).Model(session).Updates(session).Error; err != nil {
		return fmt.Errorf("failed to update session: %w", err)
	}
	return nil
}

func (r *SessionRepositoryImpl) Delete(ctx context.Context, id string) error {
	if err := r.db.WithContext(ctx).Delete(&models.Session{}, "id = ?", id).Error; err != nil {
		return fmt.Errorf("failed to delete session: %w", err)
	}
	return nil
}

func (r *SessionRepositoryImpl) DeleteExpired(ctx context.Context) error {
	if err := r.db.WithContext(ctx).Delete(&models.Session{}, "expires_at < NOW()").Error; err != nil {
		return fmt.Errorf("failed to delete expired sessions: %w", err)
	}
	return nil
}
