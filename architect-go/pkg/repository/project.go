package repository

import (
	"context"
	"fmt"

	"gorm.io/gorm"

	"architect-go/pkg/models"
)

// ProjectRepositoryImpl implements ProjectRepository using GORM
type ProjectRepositoryImpl struct {
	db *gorm.DB
}

// NewProjectRepository creates a new ProjectRepositoryImpl instance
func NewProjectRepository(db *gorm.DB) ProjectRepository {
	return &ProjectRepositoryImpl{db: db}
}

// Create inserts a new project
func (r *ProjectRepositoryImpl) Create(ctx context.Context, project *models.Project) error {
	if err := r.db.WithContext(ctx).Create(project).Error; err != nil {
		return fmt.Errorf("failed to create project: %w", err)
	}
	return nil
}

// Get retrieves a project by ID
func (r *ProjectRepositoryImpl) Get(ctx context.Context, id string) (*models.Project, error) {
	var project models.Project
	if err := r.db.WithContext(ctx).First(&project, "id = ?", id).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, fmt.Errorf("project not found")
		}
		return nil, fmt.Errorf("failed to get project: %w", err)
	}
	return &project, nil
}

// List retrieves all projects with optional filters
func (r *ProjectRepositoryImpl) List(ctx context.Context, filters map[string]interface{}, limit int, offset int) ([]*models.Project, int64, error) {
	var projects []*models.Project
	var total int64

	query := r.db.WithContext(ctx)

	// Apply filters
	if status, ok := filters["status"]; ok {
		query = query.Where("status = ?", status)
	}

	if name, ok := filters["name"]; ok {
		query = query.Where("name ILIKE ?", "%"+name.(string)+"%")
	}

	// Get total count
	if err := query.Model(&models.Project{}).Count(&total).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to count projects: %w", err)
	}

	// Get paginated results
	if err := query.Limit(limit).Offset(offset).Order("created_at DESC").Find(&projects).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to list projects: %w", err)
	}

	return projects, total, nil
}

// Update updates an existing project
func (r *ProjectRepositoryImpl) Update(ctx context.Context, project *models.Project) error {
	if err := r.db.WithContext(ctx).Model(project).Updates(project).Error; err != nil {
		return fmt.Errorf("failed to update project: %w", err)
	}
	return nil
}

// Delete soft deletes a project
func (r *ProjectRepositoryImpl) Delete(ctx context.Context, id string) error {
	if err := r.db.WithContext(ctx).Model(&models.Project{}).Where("id = ?", id).Update("deleted_at", gorm.Expr("CURRENT_TIMESTAMP")).Error; err != nil {
		return fmt.Errorf("failed to delete project: %w", err)
	}
	return nil
}

// HardDelete permanently deletes a project
func (r *ProjectRepositoryImpl) HardDelete(ctx context.Context, id string) error {
	if err := r.db.WithContext(ctx).Unscoped().Delete(&models.Project{}, "id = ?", id).Error; err != nil {
		return fmt.Errorf("failed to hard delete project: %w", err)
	}
	return nil
}

// TaskRepositoryImpl implements TaskRepository
type TaskRepositoryImpl struct {
	db *gorm.DB
}

// NewTaskRepository creates a new TaskRepositoryImpl instance
func NewTaskRepository(db *gorm.DB) TaskRepository {
	return &TaskRepositoryImpl{db: db}
}

// Create inserts a new task
func (r *TaskRepositoryImpl) Create(ctx context.Context, task *models.Task) error {
	if err := r.db.WithContext(ctx).Create(task).Error; err != nil {
		return fmt.Errorf("failed to create task: %w", err)
	}
	return nil
}

// Get retrieves a task by ID
func (r *TaskRepositoryImpl) Get(ctx context.Context, id string) (*models.Task, error) {
	var task models.Task
	if err := r.db.WithContext(ctx).First(&task, "id = ?", id).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, fmt.Errorf("task not found")
		}
		return nil, fmt.Errorf("failed to get task: %w", err)
	}
	return &task, nil
}

// ListByProject retrieves tasks for a project
func (r *TaskRepositoryImpl) ListByProject(ctx context.Context, projectID string, limit int, offset int) ([]*models.Task, int64, error) {
	var tasks []*models.Task
	var total int64

	query := r.db.WithContext(ctx).Where("project_id = ?", projectID)

	if err := query.Model(&models.Task{}).Count(&total).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to count tasks: %w", err)
	}

	if err := query.Limit(limit).Offset(offset).Order("priority DESC, created_at DESC").Find(&tasks).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to list tasks: %w", err)
	}

	return tasks, total, nil
}

// List retrieves all tasks with optional filters
func (r *TaskRepositoryImpl) List(ctx context.Context, filters map[string]interface{}, limit int, offset int) ([]*models.Task, int64, error) {
	var tasks []*models.Task
	var total int64

	query := r.db.WithContext(ctx)

	if status, ok := filters["status"]; ok {
		query = query.Where("status = ?", status)
	}

	if projectID, ok := filters["project_id"]; ok {
		query = query.Where("project_id = ?", projectID)
	}

	if priority, ok := filters["priority"]; ok {
		query = query.Where("priority = ?", priority)
	}

	if err := query.Model(&models.Task{}).Count(&total).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to count tasks: %w", err)
	}

	if err := query.Limit(limit).Offset(offset).Order("priority DESC, created_at DESC").Find(&tasks).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to list tasks: %w", err)
	}

	return tasks, total, nil
}

// Update updates an existing task
func (r *TaskRepositoryImpl) Update(ctx context.Context, task *models.Task) error {
	if err := r.db.WithContext(ctx).Model(task).Updates(task).Error; err != nil {
		return fmt.Errorf("failed to update task: %w", err)
	}
	return nil
}

// Delete soft deletes a task
func (r *TaskRepositoryImpl) Delete(ctx context.Context, id string) error {
	if err := r.db.WithContext(ctx).Model(&models.Task{}).Where("id = ?", id).Update("deleted_at", gorm.Expr("CURRENT_TIMESTAMP")).Error; err != nil {
		return fmt.Errorf("failed to delete task: %w", err)
	}
	return nil
}

// UserRepositoryImpl implements UserRepository
type UserRepositoryImpl struct {
	db *gorm.DB
}

// NewUserRepository creates a new UserRepositoryImpl instance
func NewUserRepository(db *gorm.DB) UserRepository {
	return &UserRepositoryImpl{db: db}
}

// Create inserts a new user
func (r *UserRepositoryImpl) Create(ctx context.Context, user *models.User) error {
	if err := r.db.WithContext(ctx).Create(user).Error; err != nil {
		return fmt.Errorf("failed to create user: %w", err)
	}
	return nil
}

// Get retrieves a user by ID
func (r *UserRepositoryImpl) Get(ctx context.Context, id string) (*models.User, error) {
	var user models.User
	if err := r.db.WithContext(ctx).First(&user, "id = ?", id).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, fmt.Errorf("user not found")
		}
		return nil, fmt.Errorf("failed to get user: %w", err)
	}
	return &user, nil
}

// GetByUsername retrieves a user by username
func (r *UserRepositoryImpl) GetByUsername(ctx context.Context, username string) (*models.User, error) {
	var user models.User
	if err := r.db.WithContext(ctx).First(&user, "username = ?", username).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, fmt.Errorf("user not found")
		}
		return nil, fmt.Errorf("failed to get user: %w", err)
	}
	return &user, nil
}

// GetByEmail retrieves a user by email
func (r *UserRepositoryImpl) GetByEmail(ctx context.Context, email string) (*models.User, error) {
	var user models.User
	if err := r.db.WithContext(ctx).First(&user, "email = ?", email).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, fmt.Errorf("user not found")
		}
		return nil, fmt.Errorf("failed to get user: %w", err)
	}
	return &user, nil
}

// List retrieves all users
func (r *UserRepositoryImpl) List(ctx context.Context, limit int, offset int) ([]*models.User, int64, error) {
	var users []*models.User
	var total int64

	query := r.db.WithContext(ctx)

	if err := query.Model(&models.User{}).Count(&total).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to count users: %w", err)
	}

	if err := query.Limit(limit).Offset(offset).Order("created_at DESC").Find(&users).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to list users: %w", err)
	}

	return users, total, nil
}

// Update updates an existing user
func (r *UserRepositoryImpl) Update(ctx context.Context, user *models.User) error {
	if err := r.db.WithContext(ctx).Model(user).Updates(user).Error; err != nil {
		return fmt.Errorf("failed to update user: %w", err)
	}
	return nil
}

// Delete soft deletes a user
func (r *UserRepositoryImpl) Delete(ctx context.Context, id string) error {
	if err := r.db.WithContext(ctx).Model(&models.User{}).Where("id = ?", id).Update("deleted_at", gorm.Expr("CURRENT_TIMESTAMP")).Error; err != nil {
		return fmt.Errorf("failed to delete user: %w", err)
	}
	return nil
}
