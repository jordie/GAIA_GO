// Package repository provides data access layer abstractions and registry
package repository

import (
	"fmt"
	"sync"

	"gorm.io/gorm"
)

// Registry provides centralized access to all repositories
type Registry struct {
	// Existing repositories (documented for reference)
	// ProjectRepository, TaskRepository, etc. (20 repositories)

	// Phase 9 Consolidation repositories
	ClaudeSessionRepository        ClaudeSessionRepository
	LessonRepository               LessonRepository
	DistributedTaskRepository      DistributedTaskRepository
	DistributedLockRepository      DistributedLockRepository
	SessionAffinityRepository      SessionAffinityRepository
	UsabilityMetricsRepository     UsabilityMetricsRepository
	FrustrationEventRepository     FrustrationEventRepository
	SatisfactionRatingRepository   SatisfactionRatingRepository
	TeacherDashboardAlertRepository TeacherDashboardAlertRepository

	// Database connection
	db *gorm.DB

	// Sync
	mu sync.RWMutex
}

// NewRegistry creates a new repository registry
func NewRegistry(db *gorm.DB) *Registry {
	return &Registry{
		db: db,
	}
}

// Initialize initializes all repositories
func (r *Registry) Initialize() error {
	r.mu.Lock()
	defer r.mu.Unlock()

	// Phase 9 Consolidation repositories
	r.ClaudeSessionRepository = NewClaudeSessionRepository(r.db)
	r.LessonRepository = NewLessonRepository(r.db)
	r.DistributedTaskRepository = NewDistributedTaskRepository(r.db)
	r.DistributedLockRepository = NewDistributedLockRepository(r.db)
	r.SessionAffinityRepository = NewSessionAffinityRepository(r.db)
	r.UsabilityMetricsRepository = NewUsabilityMetricsRepository(r.db)
	r.FrustrationEventRepository = NewFrustrationEventRepository(r.db)
	r.SatisfactionRatingRepository = NewSatisfactionRatingRepository(r.db)
	r.TeacherDashboardAlertRepository = NewTeacherDashboardAlertRepository(r.db)

	return nil
}

// GetDB returns the database connection
func (r *Registry) GetDB() *gorm.DB {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.db
}

// Close closes the registry and all resources
func (r *Registry) Close() error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if r.db != nil {
		sqlDB, err := r.db.DB()
		if err != nil {
			return fmt.Errorf("failed to get database connection: %w", err)
		}
		if err := sqlDB.Close(); err != nil {
			return fmt.Errorf("failed to close database connection: %w", err)
		}
	}

	return nil
}

// RegistryProvider provides interface for registry dependency injection
type RegistryProvider interface {
	GetRegistry() *Registry
	CloseRegistry() error
}

// RegistryProviderImpl implements RegistryProvider
type RegistryProviderImpl struct {
	registry *Registry
	mu       sync.RWMutex
}

// NewRegistryProvider creates a new registry provider
func NewRegistryProvider(registry *Registry) RegistryProvider {
	return &RegistryProviderImpl{
		registry: registry,
	}
}

// GetRegistry returns the registry
func (rp *RegistryProviderImpl) GetRegistry() *Registry {
	rp.mu.RLock()
	defer rp.mu.RUnlock()
	return rp.registry
}

// CloseRegistry closes the registry
func (rp *RegistryProviderImpl) CloseRegistry() error {
	rp.mu.Lock()
	defer rp.mu.Unlock()
	return rp.registry.Close()
}
