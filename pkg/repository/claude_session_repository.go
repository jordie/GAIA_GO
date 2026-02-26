package repository

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/jgirmay/GAIA_GO/pkg/models"
	"gorm.io/gorm"
)

// ClaudeSessionRepositoryImpl implements ClaudeSessionRepository
type ClaudeSessionRepositoryImpl struct {
	db *gorm.DB
}

// NewClaudeSessionRepository creates a new Claude session repository
func NewClaudeSessionRepository(db *gorm.DB) ClaudeSessionRepository {
	return &ClaudeSessionRepositoryImpl{db: db}
}

// Create creates a new session
func (r *ClaudeSessionRepositoryImpl) Create(ctx context.Context, session *models.ClaudeSession) error {
	return r.db.WithContext(ctx).Create(session).Error
}

// GetByName retrieves a session by name
func (r *ClaudeSessionRepositoryImpl) GetByName(ctx context.Context, sessionName string) (*models.ClaudeSession, error) {
	var session models.ClaudeSession
	err := r.db.WithContext(ctx).Where("session_name = ?", sessionName).First(&session).Error
	if err != nil {
		return nil, err
	}
	return &session, nil
}

// GetByID retrieves a session by ID
func (r *ClaudeSessionRepositoryImpl) GetByID(ctx context.Context, id uuid.UUID) (*models.ClaudeSession, error) {
	var session models.ClaudeSession
	err := r.db.WithContext(ctx).Where("id = ?", id).First(&session).Error
	if err != nil {
		return nil, err
	}
	return &session, nil
}

// List retrieves all sessions
func (r *ClaudeSessionRepositoryImpl) List(ctx context.Context) ([]*models.ClaudeSession, error) {
	var sessions []*models.ClaudeSession
	err := r.db.WithContext(ctx).Find(&sessions).Error
	return sessions, err
}

// ListByStatus retrieves sessions with a specific status
func (r *ClaudeSessionRepositoryImpl) ListByStatus(ctx context.Context, status string) ([]*models.ClaudeSession, error) {
	var sessions []*models.ClaudeSession
	err := r.db.WithContext(ctx).Where("status = ?", status).Find(&sessions).Error
	return sessions, err
}

// ListByTier retrieves sessions by tier
func (r *ClaudeSessionRepositoryImpl) ListByTier(ctx context.Context, tier string) ([]*models.ClaudeSession, error) {
	var sessions []*models.ClaudeSession
	err := r.db.WithContext(ctx).Where("tier = ?", tier).Find(&sessions).Error
	return sessions, err
}

// Update updates an existing session
func (r *ClaudeSessionRepositoryImpl) Update(ctx context.Context, session *models.ClaudeSession) error {
	session.UpdatedAt = time.Now()
	return r.db.WithContext(ctx).Save(session).Error
}

// Delete deletes a session
func (r *ClaudeSessionRepositoryImpl) Delete(ctx context.Context, id uuid.UUID) error {
	return r.db.WithContext(ctx).Delete(&models.ClaudeSession{}, "id = ?", id).Error
}

// UpdateStatus updates session status
func (r *ClaudeSessionRepositoryImpl) UpdateStatus(ctx context.Context, id uuid.UUID, status string) error {
	return r.db.WithContext(ctx).Model(&models.ClaudeSession{}).Where("id = ?", id).
		Update("status", status).
		Update("updated_at", time.Now()).Error
}

// UpdateHealthStatus updates health status and resets failures if healthy
func (r *ClaudeSessionRepositoryImpl) UpdateHealthStatus(ctx context.Context, id uuid.UUID, health string) error {
	updates := map[string]interface{}{
		"health_status": health,
		"updated_at":    time.Now(),
	}

	if health == "healthy" {
		updates["consecutive_failures"] = 0
	}

	return r.db.WithContext(ctx).Model(&models.ClaudeSession{}).Where("id = ?", id).
		Updates(updates).Error
}

// RecordHeartbeat records a heartbeat
func (r *ClaudeSessionRepositoryImpl) RecordHeartbeat(ctx context.Context, id uuid.UUID) error {
	return r.db.WithContext(ctx).Model(&models.ClaudeSession{}).Where("id = ?", id).
		Update("last_heartbeat", time.Now()).
		Update("updated_at", time.Now()).Error
}

// IncrementTaskCount increments current task count
func (r *ClaudeSessionRepositoryImpl) IncrementTaskCount(ctx context.Context, id uuid.UUID, count int) error {
	return r.db.WithContext(ctx).Model(&models.ClaudeSession{}).Where("id = ?", id).
		Update("current_task_count", gorm.Expr("current_task_count + ?", count)).
		Update("updated_at", time.Now()).Error
}

// GetActiveSessions retrieves sessions active in the last 30 seconds
func (r *ClaudeSessionRepositoryImpl) GetActiveSessions(ctx context.Context) ([]*models.ClaudeSession, error) {
	var sessions []*models.ClaudeSession
	thirtySecondsAgo := time.Now().Add(-30 * time.Second)
	err := r.db.WithContext(ctx).
		Where("last_heartbeat > ?", thirtySecondsAgo).
		Where("status != ?", "offline").
		Find(&sessions).Error
	return sessions, err
}

// GetHealthySessions retrieves sessions with healthy status
func (r *ClaudeSessionRepositoryImpl) GetHealthySessions(ctx context.Context) ([]*models.ClaudeSession, error) {
	var sessions []*models.ClaudeSession
	err := r.db.WithContext(ctx).
		Where("health_status = ?", "healthy").
		Where("consecutive_failures = ?", 0).
		Find(&sessions).Error
	return sessions, err
}

// GetAvailableSessions retrieves sessions that can take new tasks
func (r *ClaudeSessionRepositoryImpl) GetAvailableSessions(ctx context.Context) ([]*models.ClaudeSession, error) {
	var sessions []*models.ClaudeSession
	thirtySecondsAgo := time.Now().Add(-30 * time.Second)
	err := r.db.WithContext(ctx).
		Where("last_heartbeat > ?", thirtySecondsAgo).
		Where("health_status = ?", "healthy").
		Where("current_task_count < max_concurrent_tasks").
		Where("status != ?", "offline").
		Find(&sessions).Error
	return sessions, err
}
