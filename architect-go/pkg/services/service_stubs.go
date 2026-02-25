package services

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/google/uuid"

	"architect-go/pkg/cache"
	"architect-go/pkg/models"
	"architect-go/pkg/repository"
)

// UserServiceImpl implements UserService
type UserServiceImpl struct {
	repo  repository.UserRepository
	cache *cache.CacheManager
}

// NewUserService creates a new user service
func NewUserService(repo repository.UserRepository) UserService {
	return &UserServiceImpl{repo: repo}
}

// NewUserServiceWithCache creates a new user service with cache support
func NewUserServiceWithCache(repo repository.UserRepository, cm *cache.CacheManager) UserService {
	return &UserServiceImpl{repo: repo, cache: cm}
}

func (us *UserServiceImpl) CreateUser(ctx context.Context, req *CreateUserRequest) (*models.User, error) {
	// TODO: Hash password
	user := &models.User{
		ID:           uuid.New().String(),
		Username:     req.Username,
		Email:        req.Email,
		PasswordHash: req.Password,
		FullName:     req.FullName,
		Status:       "active",
	}

	if err := us.repo.Create(ctx, user); err != nil {
		return nil, fmt.Errorf("failed to create user: %w", err)
	}

	// Invalidate list cache
	if us.cache != nil {
		us.cache.Delete(cache.CacheKeyUserList())
	}

	return user, nil
}

func (us *UserServiceImpl) GetUser(ctx context.Context, id string) (*models.User, error) {
	// Try cache first
	if us.cache != nil {
		if val, ok := us.cache.Get(cache.CacheKeyUser(id)); ok {
			if user, ok := val.(*models.User); ok {
				return user, nil
			}
		}
	}

	// Fetch from repository
	user, err := us.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("failed to get user: %w", err)
	}

	// Store in cache
	if us.cache != nil && user != nil {
		us.cache.Set(cache.CacheKeyUser(id), user, cache.UserCacheTTL)
	}

	return user, nil
}

func (us *UserServiceImpl) GetByEmail(ctx context.Context, email string) (*models.User, error) {
	user, err := us.repo.GetByEmail(ctx, email)
	if err != nil {
		return nil, fmt.Errorf("failed to get user by email: %w", err)
	}
	return user, nil
}

func (us *UserServiceImpl) ListUsers(ctx context.Context, req *ListUsersRequest) ([]*models.User, int64, error) {
	// Try cache for unfiltered requests (no filters in ListUsersRequest)
	if us.cache != nil {
		if val, ok := us.cache.Get(cache.CacheKeyUserList()); ok {
			if entry, ok := val.(map[string]interface{}); ok {
				if users, ok := entry["users"].([]*models.User); ok {
					if total, ok := entry["total"].(int64); ok {
						return users, total, nil
					}
				}
			}
		}
	}

	users, total, err := us.repo.List(ctx, req.Limit, req.Offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list users: %w", err)
	}

	// Cache results
	if us.cache != nil {
		cacheEntry := map[string]interface{}{
			"users": users,
			"total": total,
		}
		us.cache.Set(cache.CacheKeyUserList(), cacheEntry, cache.ListCacheTTL)
	}

	return users, total, nil
}

func (us *UserServiceImpl) UpdateUser(ctx context.Context, id string, req *UpdateUserRequest) (*models.User, error) {
	user, err := us.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("user not found: %w", err)
	}

	if req.Email != "" {
		user.Email = req.Email
	}
	if req.FullName != "" {
		user.FullName = req.FullName
	}
	if req.Status != "" {
		user.Status = req.Status
	}

	if err := us.repo.Update(ctx, user); err != nil {
		return nil, fmt.Errorf("failed to update user: %w", err)
	}

	// Invalidate caches
	if us.cache != nil {
		us.cache.Delete(cache.CacheKeyUser(id))
		us.cache.Delete(cache.CacheKeyUserList())
	}

	return user, nil
}

func (us *UserServiceImpl) DeleteUser(ctx context.Context, id string) error {
	if err := us.repo.Delete(ctx, id); err != nil {
		return fmt.Errorf("failed to delete user: %w", err)
	}

	// Invalidate caches
	if us.cache != nil {
		us.cache.Delete(cache.CacheKeyUser(id))
		us.cache.Delete(cache.CacheKeyUserList())
	}

	return nil
}

func (us *UserServiceImpl) UpdatePassword(ctx context.Context, id string, oldPassword string, newPassword string) error {
	// TODO: Verify old password and hash new password
	user, err := us.repo.Get(ctx, id)
	if err != nil {
		return fmt.Errorf("user not found: %w", err)
	}

	user.PasswordHash = newPassword
	if err := us.repo.Update(ctx, user); err != nil {
		return fmt.Errorf("failed to update password: %w", err)
	}

	return nil
}

// DashboardServiceImpl implements DashboardService
type DashboardServiceImpl struct {
	repos *repository.Registry
}

// NewDashboardService creates a new dashboard service
func NewDashboardService(repos *repository.Registry) DashboardService {
	return &DashboardServiceImpl{repos: repos}
}

func (ds *DashboardServiceImpl) GetDashboard(ctx context.Context, userID string) (map[string]interface{}, error) {
	// TODO: Implement dashboard aggregation
	dashboard := map[string]interface{}{
		"user_id": userID,
		"widgets": []map[string]interface{}{},
	}
	return dashboard, nil
}

func (ds *DashboardServiceImpl) GetStatistics(ctx context.Context) (map[string]interface{}, error) {
	// TODO: Calculate statistics
	stats := map[string]interface{}{
		"total_projects": 0,
		"total_tasks":    0,
		"total_users":    0,
	}
	return stats, nil
}

func (ds *DashboardServiceImpl) GetProjectMetrics(ctx context.Context, projectID string) (map[string]interface{}, error) {
	// TODO: Calculate project metrics
	metrics := map[string]interface{}{
		"project_id": projectID,
		"tasks":      0,
		"completion": 0.0,
	}
	return metrics, nil
}

func (ds *DashboardServiceImpl) GetUserActivity(ctx context.Context, userID string) ([]map[string]interface{}, error) {
	// TODO: Retrieve user activity
	return []map[string]interface{}{}, nil
}

// WorkerServiceImpl implements WorkerService
type WorkerServiceImpl struct {
	repo repository.WorkerRepository
}

// NewWorkerService creates a new worker service
func NewWorkerService(repo repository.WorkerRepository) WorkerService {
	return &WorkerServiceImpl{repo: repo}
}

func (ws *WorkerServiceImpl) RegisterWorker(ctx context.Context, req *RegisterWorkerRequest) (*models.Worker, error) {
	metadata, _ := json.Marshal(req.Metadata)
	worker := &models.Worker{
		ID:       uuid.New().String(),
		Type:     req.Type,
		Status:   "idle",
		Metadata: metadata,
	}

	if err := ws.repo.Create(ctx, worker); err != nil {
		return nil, fmt.Errorf("failed to register worker: %w", err)
	}

	return worker, nil
}

func (ws *WorkerServiceImpl) Heartbeat(ctx context.Context, id string) error {
	if err := ws.repo.UpdateStatus(ctx, id, "active"); err != nil {
		return fmt.Errorf("failed to update worker status: %w", err)
	}
	return nil
}

func (ws *WorkerServiceImpl) GetWorker(ctx context.Context, id string) (*models.Worker, error) {
	worker, err := ws.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("failed to get worker: %w", err)
	}
	return worker, nil
}

func (ws *WorkerServiceImpl) ListWorkers(ctx context.Context, req *ListWorkersRequest) ([]*models.Worker, int64, error) {
	workers, total, err := ws.repo.List(ctx, req.Limit, req.Offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list workers: %w", err)
	}
	return workers, total, nil
}

func (ws *WorkerServiceImpl) UnregisterWorker(ctx context.Context, id string) error {
	if err := ws.repo.Delete(ctx, id); err != nil {
		return fmt.Errorf("failed to unregister worker: %w", err)
	}
	return nil
}

func (ws *WorkerServiceImpl) GetWorkerStats(ctx context.Context, id string) (map[string]interface{}, error) {
	worker, err := ws.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("worker not found: %w", err)
	}

	stats := map[string]interface{}{
		"id":     worker.ID,
		"type":   worker.Type,
		"status": worker.Status,
	}

	return stats, nil
}
