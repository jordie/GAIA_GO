package services

import (
	"context"
	"fmt"

	"github.com/google/uuid"

	"architect-go/pkg/cache"
	"architect-go/pkg/models"
	"architect-go/pkg/repository"
)

// ProjectServiceImpl implements ProjectService
type ProjectServiceImpl struct {
	repo  repository.ProjectRepository
	cache *cache.CacheManager
}

// NewProjectService creates a new project service
func NewProjectService(repo repository.ProjectRepository) ProjectService {
	return &ProjectServiceImpl{repo: repo}
}

// NewProjectServiceWithCache creates a new project service with cache support
func NewProjectServiceWithCache(repo repository.ProjectRepository, cm *cache.CacheManager) ProjectService {
	return &ProjectServiceImpl{repo: repo, cache: cm}
}

// CreateProject creates a new project
func (ps *ProjectServiceImpl) CreateProject(ctx context.Context, req *CreateProjectRequest) (*models.Project, error) {
	project := &models.Project{
		ID:          uuid.New().String(),
		Name:        req.Name,
		Description: req.Description,
		Status:      "active",
	}

	if req.Status != "" {
		project.Status = req.Status
	}

	if err := ps.repo.Create(ctx, project); err != nil {
		return nil, fmt.Errorf("failed to create project: %w", err)
	}

	// Invalidate list cache
	if ps.cache != nil {
		ps.cache.Delete(cache.CacheKeyProjectList())
	}

	return project, nil
}

// GetProject retrieves a project by ID
func (ps *ProjectServiceImpl) GetProject(ctx context.Context, id string) (*models.Project, error) {
	// Try cache first
	if ps.cache != nil {
		if val, ok := ps.cache.Get(cache.CacheKeyProject(id)); ok {
			if project, ok := val.(*models.Project); ok {
				return project, nil
			}
		}
	}

	// Fetch from repository
	project, err := ps.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("failed to get project: %w", err)
	}

	// Store in cache
	if ps.cache != nil && project != nil {
		ps.cache.Set(cache.CacheKeyProject(id), project, cache.ProjectCacheTTL)
	}

	return project, nil
}

// ListProjects retrieves projects with filters
func (ps *ProjectServiceImpl) ListProjects(ctx context.Context, req *ListProjectsRequest) ([]*models.Project, int64, error) {
	filters := make(map[string]interface{})
	hasFilters := false
	if req.Status != "" {
		filters["status"] = req.Status
		hasFilters = true
	}
	if req.Name != "" {
		filters["name"] = req.Name
		hasFilters = true
	}

	// Try cache for unfiltered requests
	if ps.cache != nil && !hasFilters {
		if val, ok := ps.cache.Get(cache.CacheKeyProjectList()); ok {
			if entry, ok := val.(map[string]interface{}); ok {
				if projects, ok := entry["projects"].([]*models.Project); ok {
					if total, ok := entry["total"].(int64); ok {
						return projects, total, nil
					}
				}
			}
		}
	}

	projects, total, err := ps.repo.List(ctx, filters, req.Limit, req.Offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list projects: %w", err)
	}

	// Cache unfiltered results
	if ps.cache != nil && !hasFilters {
		cacheEntry := map[string]interface{}{
			"projects": projects,
			"total":    total,
		}
		ps.cache.Set(cache.CacheKeyProjectList(), cacheEntry, cache.ListCacheTTL)
	}

	return projects, total, nil
}

// UpdateProject updates a project
func (ps *ProjectServiceImpl) UpdateProject(ctx context.Context, id string, req *UpdateProjectRequest) (*models.Project, error) {
	project, err := ps.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("project not found: %w", err)
	}

	if req.Name != "" {
		project.Name = req.Name
	}
	if req.Description != "" {
		project.Description = req.Description
	}
	if req.Status != "" {
		project.Status = req.Status
	}

	if err := ps.repo.Update(ctx, project); err != nil {
		return nil, fmt.Errorf("failed to update project: %w", err)
	}

	// Invalidate caches
	if ps.cache != nil {
		ps.cache.Delete(cache.CacheKeyProject(id))
		ps.cache.Delete(cache.CacheKeyProjectList())
	}

	return project, nil
}

// DeleteProject deletes a project
func (ps *ProjectServiceImpl) DeleteProject(ctx context.Context, id string) error {
	if err := ps.repo.Delete(ctx, id); err != nil {
		return fmt.Errorf("failed to delete project: %w", err)
	}

	// Invalidate caches
	if ps.cache != nil {
		ps.cache.Delete(cache.CacheKeyProject(id))
		ps.cache.Delete(cache.CacheKeyProjectList())
	}

	return nil
}

// GetProjectStats returns project statistics
func (ps *ProjectServiceImpl) GetProjectStats(ctx context.Context, id string) (map[string]interface{}, error) {
	project, err := ps.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("project not found: %w", err)
	}

	stats := map[string]interface{}{
		"id":         project.ID,
		"name":       project.Name,
		"status":     project.Status,
		"created_at": project.CreatedAt,
		"updated_at": project.UpdatedAt,
	}

	return stats, nil
}

// TaskServiceImpl implements TaskService
type TaskServiceImpl struct {
	repo  repository.TaskRepository
	cache *cache.CacheManager
}

// NewTaskService creates a new task service
func NewTaskService(repo repository.TaskRepository) TaskService {
	return &TaskServiceImpl{repo: repo}
}

// NewTaskServiceWithCache creates a new task service with cache support
func NewTaskServiceWithCache(repo repository.TaskRepository, cm *cache.CacheManager) TaskService {
	return &TaskServiceImpl{repo: repo, cache: cm}
}

// CreateTask creates a new task
func (ts *TaskServiceImpl) CreateTask(ctx context.Context, req *CreateTaskRequest) (*models.Task, error) {
	task := &models.Task{
		ID:          uuid.New().String(),
		ProjectID:   req.ProjectID,
		Title:       req.Title,
		Description: req.Description,
		Status:      "pending",
		Priority:    req.Priority,
		AssignedTo:  req.AssignedTo,
	}

	if req.Status != "" {
		task.Status = req.Status
	}

	if err := ts.repo.Create(ctx, task); err != nil {
		return nil, fmt.Errorf("failed to create task: %w", err)
	}

	// Invalidate list cache
	if ts.cache != nil {
		ts.cache.Delete(cache.CacheKeyTaskList())
	}

	return task, nil
}

// GetTask retrieves a task by ID
func (ts *TaskServiceImpl) GetTask(ctx context.Context, id string) (*models.Task, error) {
	// Try cache first
	if ts.cache != nil {
		if val, ok := ts.cache.Get(cache.CacheKeyTask(id)); ok {
			if task, ok := val.(*models.Task); ok {
				return task, nil
			}
		}
	}

	// Fetch from repository
	task, err := ts.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("failed to get task: %w", err)
	}

	// Store in cache
	if ts.cache != nil && task != nil {
		ts.cache.Set(cache.CacheKeyTask(id), task, cache.TaskCacheTTL)
	}

	return task, nil
}

// ListTasks retrieves tasks with filters
func (ts *TaskServiceImpl) ListTasks(ctx context.Context, req *ListTasksRequest) ([]*models.Task, int64, error) {
	filters := make(map[string]interface{})
	hasFilters := false
	if req.ProjectID != "" {
		filters["project_id"] = req.ProjectID
		hasFilters = true
	}
	if req.Status != "" {
		filters["status"] = req.Status
		hasFilters = true
	}

	// Try cache for unfiltered requests
	if ts.cache != nil && !hasFilters {
		if val, ok := ts.cache.Get(cache.CacheKeyTaskList()); ok {
			if entry, ok := val.(map[string]interface{}); ok {
				if tasks, ok := entry["tasks"].([]*models.Task); ok {
					if total, ok := entry["total"].(int64); ok {
						return tasks, total, nil
					}
				}
			}
		}
	}

	tasks, total, err := ts.repo.List(ctx, filters, req.Limit, req.Offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list tasks: %w", err)
	}

	// Cache unfiltered results
	if ts.cache != nil && !hasFilters {
		cacheEntry := map[string]interface{}{
			"tasks": tasks,
			"total": total,
		}
		ts.cache.Set(cache.CacheKeyTaskList(), cacheEntry, cache.ListCacheTTL)
	}

	return tasks, total, nil
}

// UpdateTask updates a task
func (ts *TaskServiceImpl) UpdateTask(ctx context.Context, id string, req *UpdateTaskRequest) (*models.Task, error) {
	task, err := ts.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("task not found: %w", err)
	}

	if req.Title != "" {
		task.Title = req.Title
	}
	if req.Description != "" {
		task.Description = req.Description
	}
	if req.Status != "" {
		task.Status = req.Status
	}
	if req.Priority >= 0 {
		task.Priority = req.Priority
	}
	if req.AssignedTo != "" {
		task.AssignedTo = req.AssignedTo
	}

	if err := ts.repo.Update(ctx, task); err != nil {
		return nil, fmt.Errorf("failed to update task: %w", err)
	}

	// Invalidate caches
	if ts.cache != nil {
		ts.cache.Delete(cache.CacheKeyTask(id))
		ts.cache.Delete(cache.CacheKeyTaskList())
	}

	return task, nil
}

// DeleteTask deletes a task
func (ts *TaskServiceImpl) DeleteTask(ctx context.Context, id string) error {
	if err := ts.repo.Delete(ctx, id); err != nil {
		return fmt.Errorf("failed to delete task: %w", err)
	}

	// Invalidate caches
	if ts.cache != nil {
		ts.cache.Delete(cache.CacheKeyTask(id))
		ts.cache.Delete(cache.CacheKeyTaskList())
	}

	return nil
}

// BulkUpdateTasks updates multiple tasks
func (ts *TaskServiceImpl) BulkUpdateTasks(ctx context.Context, req *BulkUpdateTasksRequest) (int, error) {
	// TODO: Implement bulk update with proper transaction handling
	return 0, fmt.Errorf("not implemented")
}

// CompleteTask marks a task as complete
func (ts *TaskServiceImpl) CompleteTask(ctx context.Context, id string) (*models.Task, error) {
	task, err := ts.repo.Get(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("task not found: %w", err)
	}

	task.Status = "completed"

	if err := ts.repo.Update(ctx, task); err != nil {
		return nil, fmt.Errorf("failed to complete task: %w", err)
	}

	// Invalidate caches
	if ts.cache != nil {
		ts.cache.Delete(cache.CacheKeyTask(id))
		ts.cache.Delete(cache.CacheKeyTaskList())
	}

	return task, nil
}
