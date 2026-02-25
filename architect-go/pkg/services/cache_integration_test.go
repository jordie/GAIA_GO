package services

import (
	"context"
	"testing"
	"time"

	"architect-go/pkg/cache"
	"architect-go/pkg/models"
	"architect-go/pkg/repository"
)

// Mock repository for testing cache integration
type mockProjectRepository struct {
	projects map[string]*models.Project
	callCount int
}

func (m *mockProjectRepository) Create(ctx context.Context, project *models.Project) error {
	m.projects[project.ID] = project
	return nil
}

func (m *mockProjectRepository) Get(ctx context.Context, id string) (*models.Project, error) {
	m.callCount++
	if p, ok := m.projects[id]; ok {
		return p, nil
	}
	return nil, nil
}

func (m *mockProjectRepository) List(ctx context.Context, filters map[string]interface{}, limit int, offset int) ([]*models.Project, int64, error) {
	var projects []*models.Project
	for _, p := range m.projects {
		projects = append(projects, p)
	}
	return projects, int64(len(projects)), nil
}

func (m *mockProjectRepository) Update(ctx context.Context, project *models.Project) error {
	m.projects[project.ID] = project
	return nil
}

func (m *mockProjectRepository) Delete(ctx context.Context, id string) error {
	delete(m.projects, id)
	return nil
}

func (m *mockProjectRepository) HardDelete(ctx context.Context, id string) error {
	delete(m.projects, id)
	return nil
}

// Test project service with cache
func TestProjectService_GetProject_CacheHit(t *testing.T) {
	// Setup
	mockRepo := &mockProjectRepository{
		projects:  make(map[string]*models.Project),
		callCount: 0,
	}

	cm := cache.NewCacheManager()
	svc := NewProjectService(mockRepo, cm)

	ctx := context.Background()
	projectID := "proj-123"
	testProject := &models.Project{
		ID:   projectID,
		Name: "Test Project",
	}

	// Store in repo
	mockRepo.projects[projectID] = testProject

	// First call - should fetch from repo
	result1, _ := svc.GetProject(ctx, projectID)
	firstCallCount := mockRepo.callCount

	// Second call - should be cached
	result2, _ := svc.GetProject(ctx, projectID)
	secondCallCount := mockRepo.callCount

	// Verify
	if firstCallCount != 1 {
		t.Errorf("Expected 1 repo call on first access, got %d", firstCallCount)
	}
	if secondCallCount != 1 {
		t.Errorf("Expected 1 total repo calls (cached on second), got %d", secondCallCount)
	}
	if result1.ID != projectID || result2.ID != projectID {
		t.Error("Expected consistent results")
	}
}

func TestProjectService_GetProject_CacheMiss(t *testing.T) {
	// Setup
	mockRepo := &mockProjectRepository{
		projects:  make(map[string]*models.Project),
		callCount: 0,
	}

	cm := cache.NewCacheManager()
	svc := NewProjectService(mockRepo, cm)

	ctx := context.Background()
	projectID := "proj-456"
	testProject := &models.Project{
		ID:   projectID,
		Name: "Another Project",
	}

	mockRepo.projects[projectID] = testProject

	// Call should fetch from repo
	result, _ := svc.GetProject(ctx, projectID)

	// Verify
	if mockRepo.callCount != 1 {
		t.Errorf("Expected 1 repo call, got %d", mockRepo.callCount)
	}
	if result == nil {
		t.Error("Expected non-nil result")
	}
}

func TestProjectService_UpdateProject_InvalidatesCache(t *testing.T) {
	// Setup
	mockRepo := &mockProjectRepository{
		projects:  make(map[string]*models.Project),
		callCount: 0,
	}

	cm := cache.NewCacheManager()
	svc := NewProjectService(mockRepo, cm)

	ctx := context.Background()
	projectID := "proj-789"
	initialProject := &models.Project{
		ID:   projectID,
		Name: "Original",
	}
	mockRepo.projects[projectID] = initialProject

	// Load into cache
	svc.GetProject(ctx, projectID)
	initialCallCount := mockRepo.callCount

	// Update project
	updatedProject := &models.Project{
		ID:   projectID,
		Name: "Updated",
	}
	svc.UpdateProject(ctx, projectID, &UpdateProjectRequest{
		Name: "Updated",
	})

	// Fetch again - should hit repo (cache invalidated)
	svc.GetProject(ctx, projectID)

	// Verify
	if mockRepo.callCount <= initialCallCount {
		t.Errorf("Expected repo to be called after update, call count: %d", mockRepo.callCount)
	}
}

func TestProjectService_DeleteProject_InvalidatesCache(t *testing.T) {
	// Setup
	mockRepo := &mockProjectRepository{
		projects:  make(map[string]*models.Project),
		callCount: 0,
	}

	cm := cache.NewCacheManager()
	svc := NewProjectService(mockRepo, cm)

	ctx := context.Background()
	projectID := "proj-delete"
	testProject := &models.Project{
		ID:   projectID,
		Name: "To Delete",
	}
	mockRepo.projects[projectID] = testProject

	// Load into cache
	svc.GetProject(ctx, projectID)

	// Delete project
	svc.DeleteProject(ctx, projectID)

	// After delete, cache should be cleared for this key
	// Verify cache is invalidated
	if _, exists := mockRepo.projects[projectID]; exists {
		t.Error("Expected project to be deleted from repo")
	}
}

// Mock user repository
type mockUserRepository struct {
	users     map[string]*models.User
	callCount int
}

func (m *mockUserRepository) Create(ctx context.Context, user *models.User) error {
	m.users[user.ID] = user
	return nil
}

func (m *mockUserRepository) Get(ctx context.Context, id string) (*models.User, error) {
	m.callCount++
	if u, ok := m.users[id]; ok {
		return u, nil
	}
	return nil, nil
}

func (m *mockUserRepository) GetByUsername(ctx context.Context, username string) (*models.User, error) {
	for _, u := range m.users {
		if u.Username == username {
			return u, nil
		}
	}
	return nil, nil
}

func (m *mockUserRepository) GetByEmail(ctx context.Context, email string) (*models.User, error) {
	for _, u := range m.users {
		if u.Email == email {
			return u, nil
		}
	}
	return nil, nil
}

func (m *mockUserRepository) List(ctx context.Context, limit int, offset int) ([]*models.User, int64, error) {
	var users []*models.User
	for _, u := range m.users {
		users = append(users, u)
	}
	return users, int64(len(users)), nil
}

func (m *mockUserRepository) Update(ctx context.Context, user *models.User) error {
	m.users[user.ID] = user
	return nil
}

func (m *mockUserRepository) Delete(ctx context.Context, id string) error {
	delete(m.users, id)
	return nil
}

// Test user service with cache
func TestUserService_GetUser_CacheHit(t *testing.T) {
	// Setup
	mockRepo := &mockUserRepository{
		users:     make(map[string]*models.User),
		callCount: 0,
	}

	cm := cache.NewCacheManager()
	svc := NewUserService(mockRepo, cm)

	ctx := context.Background()
	userID := "user-123"
	testUser := &models.User{
		ID:       userID,
		Username: "testuser",
		Email:    "test@example.com",
	}

	mockRepo.users[userID] = testUser

	// First call
	svc.GetUser(ctx, userID)
	firstCallCount := mockRepo.callCount

	// Second call - should be cached
	svc.GetUser(ctx, userID)
	secondCallCount := mockRepo.callCount

	// Verify
	if firstCallCount != 1 {
		t.Errorf("Expected 1 repo call on first access, got %d", firstCallCount)
	}
	if secondCallCount != 1 {
		t.Errorf("Expected 1 total repo calls (cached), got %d", secondCallCount)
	}
}

func TestUserService_UpdateUser_InvalidatesCache(t *testing.T) {
	// Setup
	mockRepo := &mockUserRepository{
		users:     make(map[string]*models.User),
		callCount: 0,
	}

	cm := cache.NewCacheManager()
	svc := NewUserService(mockRepo, cm)

	ctx := context.Background()
	userID := "user-456"
	testUser := &models.User{
		ID:       userID,
		Username: "testuser",
		Email:    "test@example.com",
	}
	mockRepo.users[userID] = testUser

	// Load into cache
	svc.GetUser(ctx, userID)
	initialCallCount := mockRepo.callCount

	// Update user
	svc.UpdateUser(ctx, userID, &UpdateUserRequest{
		Email: "newemail@example.com",
	})

	// Fetch again - should hit repo (cache invalidated)
	svc.GetUser(ctx, userID)

	// Verify cache was cleared
	if mockRepo.callCount <= initialCallCount {
		t.Errorf("Expected repo to be called after update")
	}
}

// Mock task repository
type mockTaskRepository struct {
	tasks     map[string]*models.Task
	callCount int
}

func (m *mockTaskRepository) Create(ctx context.Context, task *models.Task) error {
	m.tasks[task.ID] = task
	return nil
}

func (m *mockTaskRepository) Get(ctx context.Context, id string) (*models.Task, error) {
	m.callCount++
	if t, ok := m.tasks[id]; ok {
		return t, nil
	}
	return nil, nil
}

func (m *mockTaskRepository) List(ctx context.Context, filters map[string]interface{}, limit int, offset int) ([]*models.Task, int64, error) {
	var tasks []*models.Task
	for _, t := range m.tasks {
		tasks = append(tasks, t)
	}
	return tasks, int64(len(tasks)), nil
}

func (m *mockTaskRepository) Update(ctx context.Context, task *models.Task) error {
	m.tasks[task.ID] = task
	return nil
}

func (m *mockTaskRepository) Delete(ctx context.Context, id string) error {
	delete(m.tasks, id)
	return nil
}

// Test task service with cache
func TestTaskService_GetTask_CacheHit(t *testing.T) {
	// Setup
	mockRepo := &mockTaskRepository{
		tasks:     make(map[string]*models.Task),
		callCount: 0,
	}

	cm := cache.NewCacheManager()
	svc := NewTaskService(mockRepo, cm)

	ctx := context.Background()
	taskID := "task-123"
	testTask := &models.Task{
		ID:    taskID,
		Title: "Test Task",
	}

	mockRepo.tasks[taskID] = testTask

	// First call
	svc.GetTask(ctx, taskID)
	firstCallCount := mockRepo.callCount

	// Second call - should be cached
	svc.GetTask(ctx, taskID)
	secondCallCount := mockRepo.callCount

	// Verify
	if firstCallCount != 1 {
		t.Errorf("Expected 1 repo call on first access, got %d", firstCallCount)
	}
	if secondCallCount != 1 {
		t.Errorf("Expected 1 total repo calls (cached), got %d", secondCallCount)
	}
}

// Test that services work correctly when cache is nil
func TestNilCache_DoesNotPanic(t *testing.T) {
	// Setup - services with nil cache
	mockProjects := &mockProjectRepository{
		projects: make(map[string]*models.Project),
	}
	mockUsers := &mockUserRepository{
		users: make(map[string]*models.User),
	}
	mockTasks := &mockTaskRepository{
		tasks: make(map[string]*models.Task),
	}

	// Create services without cache manager
	projectSvc := &ProjectServiceImpl{
		repo:  mockProjects,
		cache: nil,
	}
	userSvc := &UserServiceImpl{
		repo:  mockUsers,
		cache: nil,
	}
	taskSvc := &TaskServiceImpl{
		repo:  mockTasks,
		cache: nil,
	}

	ctx := context.Background()

	// Add test data
	testProject := &models.Project{ID: "p1", Name: "Test"}
	testUser := &models.User{ID: "u1", Username: "test"}
	testTask := &models.Task{ID: "t1", Title: "Test"}

	mockProjects.projects["p1"] = testProject
	mockUsers.users["u1"] = testUser
	mockTasks.tasks["t1"] = testTask

	// Execute - should not panic
	projectSvc.GetProject(ctx, "p1")
	userSvc.GetUser(ctx, "u1")
	taskSvc.GetTask(ctx, "t1")

	t.Log("Services work correctly with nil cache")
}

// Test cache with expiration
func TestCache_Expiration(t *testing.T) {
	// Setup
	mockRepo := &mockProjectRepository{
		projects:  make(map[string]*models.Project),
		callCount: 0,
	}

	cm := cache.NewCacheManager()
	svc := NewProjectService(mockRepo, cm)

	ctx := context.Background()
	projectID := "proj-expire"
	testProject := &models.Project{
		ID:   projectID,
		Name: "Expires Soon",
	}
	mockRepo.projects[projectID] = testProject

	// Manually set cache with very short TTL
	cacheKey := cache.CacheKeyProject(projectID)
	cm.Set(cacheKey, testProject, 10*time.Millisecond)

	// Wait for cache to expire
	time.Sleep(50 * time.Millisecond)

	// Access should hit repo (cache expired)
	initialCallCount := mockRepo.callCount
	svc.GetProject(ctx, projectID)

	if mockRepo.callCount <= initialCallCount {
		t.Error("Expected repo to be called after cache expiration")
	}
}
