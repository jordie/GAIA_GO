package repository

import (
	"context"
	"fmt"
	"time"

	"github.com/jgirmay/GAIA_GO/pkg/models"
	"gorm.io/gorm"
)

// DistributedLockRepositoryImpl implements DistributedLockRepository
type DistributedLockRepositoryImpl struct {
	db *gorm.DB
}

// NewDistributedLockRepository creates a new distributed lock repository
func NewDistributedLockRepository(db *gorm.DB) DistributedLockRepository {
	return &DistributedLockRepositoryImpl{db: db}
}

// Acquire acquires a lock (or renews if already held)
func (r *DistributedLockRepositoryImpl) Acquire(ctx context.Context, lockKey string, ownerID string, ttl time.Duration) (bool, error) {
	now := time.Now()
	expiresAt := now.Add(ttl)

	// Try to create new lock
	lock := &models.DistributedLock{
		LockKey:    lockKey,
		OwnerID:    ownerID,
		AcquiredAt: now,
		ExpiresAt:  expiresAt,
	}

	result := r.db.WithContext(ctx).Create(lock)
	if result.Error == nil {
		return true, nil
	}

	// Check if it's a constraint violation (duplicate key)
	if result.Error.Error() == "UNIQUE constraint failed: distributed_locks.lock_key" ||
		result.Error.Error() == "pq: duplicate key value violates unique constraint \"distributed_locks_pkey\"" {
		// Lock already exists
	} else {
		return false, result.Error
	}

	// Lock exists, check if we own it or if it's expired
	var existing models.DistributedLock
	if err := r.db.WithContext(ctx).Where("lock_key = ?", lockKey).First(&existing).Error; err != nil {
		return false, err
	}

	if existing.OwnerID == ownerID {
		// We already own it, renew it
		return true, r.db.WithContext(ctx).Model(&models.DistributedLock{}).Where("lock_key = ?", lockKey).
			Updates(map[string]interface{}{
				"acquired_at":   now,
				"expires_at":    expiresAt,
				"renewed_count": gorm.Expr("renewed_count + 1"),
			}).Error
	}

	if existing.ExpiresAt.Before(now) {
		// Lock is expired, claim it
		return true, r.db.WithContext(ctx).Model(&models.DistributedLock{}).Where("lock_key = ?", lockKey).
			Updates(map[string]interface{}{
				"owner_id":      ownerID,
				"acquired_at":   now,
				"expires_at":    expiresAt,
				"renewed_count": 0,
			}).Error
	}

	// Lock is held by someone else and not expired
	return false, nil
}

// Release releases a lock
func (r *DistributedLockRepositoryImpl) Release(ctx context.Context, lockKey string, ownerID string) (bool, error) {
	result := r.db.WithContext(ctx).
		Where("lock_key = ?", lockKey).
		Where("owner_id = ?", ownerID).
		Delete(&models.DistributedLock{})

	if result.Error != nil {
		return false, result.Error
	}

	return result.RowsAffected > 0, nil
}

// IsLocked checks if a lock is currently held
func (r *DistributedLockRepositoryImpl) IsLocked(ctx context.Context, lockKey string) (bool, error) {
	var lock models.DistributedLock
	err := r.db.WithContext(ctx).
		Where("lock_key = ?", lockKey).
		Where("expires_at > ?", time.Now()).
		First(&lock).Error

	if err == gorm.ErrRecordNotFound {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return true, nil
}

// GetOwner gets the current lock owner
func (r *DistributedLockRepositoryImpl) GetOwner(ctx context.Context, lockKey string) (string, error) {
	var lock models.DistributedLock
	err := r.db.WithContext(ctx).
		Where("lock_key = ?", lockKey).
		Where("expires_at > ?", time.Now()).
		First(&lock).Error

	if err == gorm.ErrRecordNotFound {
		return "", fmt.Errorf("lock not found or expired")
	}
	if err != nil {
		return "", err
	}
	return lock.OwnerID, nil
}

// CleanupExpired removes expired locks
func (r *DistributedLockRepositoryImpl) CleanupExpired(ctx context.Context) error {
	return r.db.WithContext(ctx).
		Where("expires_at < ?", time.Now()).
		Delete(&models.DistributedLock{}).Error
}

// GetAll retrieves all locks
func (r *DistributedLockRepositoryImpl) GetAll(ctx context.Context) ([]*models.DistributedLock, error) {
	var locks []*models.DistributedLock
	err := r.db.WithContext(ctx).Find(&locks).Error
	return locks, err
}
