package services

import (
	"context"

	"architect-go/pkg/models"
)

// ProjectService defines project business logic
type ProjectService interface {
	// Create creates a new project
	CreateProject(ctx context.Context, req *CreateProjectRequest) (*models.Project, error)

	// Get retrieves a project by ID
	GetProject(ctx context.Context, id string) (*models.Project, error)

	// List retrieves projects with filters
	ListProjects(ctx context.Context, req *ListProjectsRequest) ([]*models.Project, int64, error)

	// Update updates a project
	UpdateProject(ctx context.Context, id string, req *UpdateProjectRequest) (*models.Project, error)

	// Delete deletes a project
	DeleteProject(ctx context.Context, id string) error

	// GetProjectStats returns project statistics
	GetProjectStats(ctx context.Context, id string) (map[string]interface{}, error)
}

// TaskService defines task business logic
type TaskService interface {
	// Create creates a new task
	CreateTask(ctx context.Context, req *CreateTaskRequest) (*models.Task, error)

	// Get retrieves a task by ID
	GetTask(ctx context.Context, id string) (*models.Task, error)

	// List retrieves tasks with filters
	ListTasks(ctx context.Context, req *ListTasksRequest) ([]*models.Task, int64, error)

	// Update updates a task
	UpdateTask(ctx context.Context, id string, req *UpdateTaskRequest) (*models.Task, error)

	// Delete deletes a task
	DeleteTask(ctx context.Context, id string) error

	// BulkUpdate updates multiple tasks
	BulkUpdateTasks(ctx context.Context, req *BulkUpdateTasksRequest) (int, error)

	// CompleteTask marks a task as complete
	CompleteTask(ctx context.Context, id string) (*models.Task, error)
}

// UserService defines user business logic
type UserService interface {
	// Create creates a new user
	CreateUser(ctx context.Context, req *CreateUserRequest) (*models.User, error)

	// Get retrieves a user by ID
	GetUser(ctx context.Context, id string) (*models.User, error)

	// GetByEmail retrieves a user by email
	GetByEmail(ctx context.Context, email string) (*models.User, error)

	// List retrieves users with filters
	ListUsers(ctx context.Context, req *ListUsersRequest) ([]*models.User, int64, error)

	// Update updates a user
	UpdateUser(ctx context.Context, id string, req *UpdateUserRequest) (*models.User, error)

	// Delete deletes a user
	DeleteUser(ctx context.Context, id string) error

	// UpdatePassword updates user password
	UpdatePassword(ctx context.Context, id string, oldPassword string, newPassword string) error
}

// DashboardService defines dashboard business logic
type DashboardService interface {
	// GetDashboard retrieves dashboard data
	GetDashboard(ctx context.Context, userID string) (map[string]interface{}, error)

	// GetStatistics returns system statistics
	GetStatistics(ctx context.Context) (map[string]interface{}, error)

	// GetProjectMetrics returns project metrics
	GetProjectMetrics(ctx context.Context, projectID string) (map[string]interface{}, error)

	// GetUserActivity returns user activity
	GetUserActivity(ctx context.Context, userID string) ([]map[string]interface{}, error)
}

// WorkerService defines worker business logic
type WorkerService interface {
	// Register registers a worker
	RegisterWorker(ctx context.Context, req *RegisterWorkerRequest) (*models.Worker, error)

	// Heartbeat updates worker heartbeat
	Heartbeat(ctx context.Context, id string) error

	// GetWorker retrieves a worker by ID
	GetWorker(ctx context.Context, id string) (*models.Worker, error)

	// ListWorkers retrieves workers
	ListWorkers(ctx context.Context, req *ListWorkersRequest) ([]*models.Worker, int64, error)

	// UnregisterWorker unregisters a worker
	UnregisterWorker(ctx context.Context, id string) error

	// GetWorkerStats returns worker statistics
	GetWorkerStats(ctx context.Context, id string) (map[string]interface{}, error)
}

// Request DTOs
type CreateProjectRequest struct {
	Name        string `json:"name"`
	Description string `json:"description"`
	Status      string `json:"status"`
}

type UpdateProjectRequest struct {
	Name        string `json:"name,omitempty"`
	Description string `json:"description,omitempty"`
	Status      string `json:"status,omitempty"`
}

type ListProjectsRequest struct {
	Status string `json:"status,omitempty"`
	Name   string `json:"name,omitempty"`
	Limit  int    `json:"limit"`
	Offset int    `json:"offset"`
}

type CreateTaskRequest struct {
	ProjectID   string `json:"project_id"`
	Title       string `json:"title"`
	Description string `json:"description"`
	Status      string `json:"status"`
	Priority    int    `json:"priority"`
	AssignedTo  string `json:"assigned_to,omitempty"`
}

type UpdateTaskRequest struct {
	Title       string `json:"title,omitempty"`
	Description string `json:"description,omitempty"`
	Status      string `json:"status,omitempty"`
	Priority    int    `json:"priority,omitempty"`
	AssignedTo  string `json:"assigned_to,omitempty"`
}

type ListTasksRequest struct {
	ProjectID string `json:"project_id,omitempty"`
	Status    string `json:"status,omitempty"`
	Priority  int    `json:"priority,omitempty"`
	Limit     int    `json:"limit"`
	Offset    int    `json:"offset"`
}

type BulkUpdateTasksRequest struct {
	TaskIDs map[string]interface{} `json:"task_ids"`
	Status  string                 `json:"status,omitempty"`
	Assign  string                 `json:"assign_to,omitempty"`
}

type CreateUserRequest struct {
	Username string `json:"username"`
	Email    string `json:"email"`
	Password string `json:"password"`
	FullName string `json:"full_name,omitempty"`
}

type UpdateUserRequest struct {
	Email    string `json:"email,omitempty"`
	FullName string `json:"full_name,omitempty"`
	Status   string `json:"status,omitempty"`
}

type ListUsersRequest struct {
	Status string `json:"status,omitempty"`
	Limit  int    `json:"limit"`
	Offset int    `json:"offset"`
}

type RegisterWorkerRequest struct {
	Type     string                 `json:"type"`
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

type ListWorkersRequest struct {
	Type   string `json:"type,omitempty"`
	Status string `json:"status,omitempty"`
	Limit  int    `json:"limit"`
	Offset int    `json:"offset"`
}
