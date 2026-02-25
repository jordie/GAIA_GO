package services

import (
	"context"
	"errors"
	"testing"

	"architect-go/pkg/cache"
	"architect-go/pkg/models"
)

// mockTaskRepository implements TaskRepository for testing
type mockTaskRepository struct {
	getCallCount    int
	createCallCount int
	updateCallCount int
	deleteCallCount int
	listCallCount   int
	tasks           map[string]*models.Task
}

func (m *mockTaskRepository) Get(ctx context.Context, id string) (*models.Task, error) {
	m.getCallCount++
	if t, ok := m.tasks[id]; ok {
		return t, nil
	}
	return nil, errors.New("not found")
}

func (m *mockTaskRepository) Create(ctx context.Context, task *models.Task) error {
	m.createCallCount++
	if m.tasks == nil {
		m.tasks = make(map[string]*models.Task)
	}
	m.tasks[task.ID] = task
	return nil
}

func (m *mockTaskRepository) Update(ctx context.Context, task *models.Task) error {
	m.updateCallCount++
	m.tasks[task.ID] = task
	return nil
}

func (m *mockTaskRepository) Delete(ctx context.Context, id string) error {
	m.deleteCallCount++
	delete(m.tasks, id)
	return nil
}

func (m *mockTaskRepository) List(ctx context.Context, filters map[string]interface{}, limit, offset int) ([]*models.Task, int64, error) {
	m.listCallCount++
	var tasks []*models.Task
	for _, t := range m.tasks {
		tasks = append(tasks, t)
	}
	return tasks, int64(len(tasks)), nil
}

func (m *mockTaskRepository) ListByProject(ctx context.Context, projectID string, limit, offset int) ([]*models.Task, int64, error) {
	var tasks []*models.Task
	for _, t := range m.tasks {
		if t.ProjectID == projectID {
			tasks = append(tasks, t)
		}
	}
	return tasks, int64(len(tasks)), nil
}

// TestTaskCacheHit tests that cache returns stored task
func TestTaskCacheHit(t *testing.T) {
	repo := &mockTaskRepository{
		tasks: map[string]*models.Task{
			"t1": {ID: "t1", Title: "Task 1", Status: "pending"},
		},
	}
	cm := cache.NewCacheManager()
	svc := NewTaskServiceWithCache(repo, cm)

	ctx := context.Background()

	// First call should hit repository
	task1, err := svc.GetTask(ctx, "t1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if repo.getCallCount != 1 {
		t.Errorf("expected 1 repo call, got %d", repo.getCallCount)
	}

	// Second call should hit cache
	task2, err := svc.GetTask(ctx, "t1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if repo.getCallCount != 1 {
		t.Errorf("expected still 1 repo call after cache hit, got %d", repo.getCallCount)
	}

	if task1.ID != task2.ID {
		t.Error("cached task differs from original")
	}
}

// TestTaskCacheMiss tests that cache miss calls repository
func TestTaskCacheMiss(t *testing.T) {
	repo := &mockTaskRepository{
		tasks: map[string]*models.Task{
			"t1": {ID: "t1", Title: "Task 1", Status: "pending"},
		},
	}
	cm := cache.NewCacheManager()
	svc := NewTaskServiceWithCache(repo, cm)

	ctx := context.Background()

	// First call
	_, err := svc.GetTask(ctx, "t1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Different task ID should not use cache
	_, err = svc.GetTask(ctx, "t2")
	if err == nil {
		t.Error("expected error for non-existent task")
	}
	if repo.getCallCount != 2 {
		t.Errorf("expected 2 repo calls for different IDs, got %d", repo.getCallCount)
	}
}

// TestTaskCreateInvalidatesCache tests that CreateTask invalidates list cache
func TestTaskCreateInvalidatesCache(t *testing.T) {
	repo := &mockTaskRepository{tasks: make(map[string]*models.Task)}
	cm := cache.NewCacheManager()
	svc := NewTaskServiceWithCache(repo, cm)

	ctx := context.Background()

	// Prime cache
	svc.ListTasks(ctx, &ListTasksRequest{Limit: 10})
	if repo.listCallCount != 1 {
		t.Errorf("expected 1 initial list call, got %d", repo.listCallCount)
	}

	// Create should invalidate
	svc.CreateTask(ctx, &CreateTaskRequest{Title: "New Task", ProjectID: "p1"})

	// Next list should call repo again
	svc.ListTasks(ctx, &ListTasksRequest{Limit: 10})
	if repo.listCallCount != 2 {
		t.Errorf("expected 2 list calls after create, got %d", repo.listCallCount)
	}
}

// TestTaskUpdateInvalidatesCache tests that UpdateTask invalidates both caches
func TestTaskUpdateInvalidatesCache(t *testing.T) {
	task1 := &models.Task{ID: "t1", Title: "Task 1", Status: "pending", ProjectID: "p1"}
	repo := &mockTaskRepository{
		tasks: map[string]*models.Task{"t1": task1},
	}
	cm := cache.NewCacheManager()
	svc := NewTaskServiceWithCache(repo, cm)

	ctx := context.Background()

	// Prime both caches
	svc.GetTask(ctx, "t1") // Item cache
	svc.ListTasks(ctx, &ListTasksRequest{Limit: 10})

	// Update should invalidate both
	svc.UpdateTask(ctx, "t1", &UpdateTaskRequest{Title: "Updated"})

	// Next get should call repo
	svc.GetTask(ctx, "t1")
	if repo.getCallCount != 3 {
		// 1 = initial cache prime, 2 = inside UpdateTask, 3 = after invalidation
		t.Errorf("expected 3 get calls after update, got %d", repo.getCallCount)
	}

	// Next list should call repo
	svc.ListTasks(ctx, &ListTasksRequest{Limit: 10})
	if repo.listCallCount != 2 {
		t.Errorf("expected 2 list calls after update, got %d", repo.listCallCount)
	}
}

// TestTaskDeleteInvalidatesCache tests that DeleteTask invalidates both caches
func TestTaskDeleteInvalidatesCache(t *testing.T) {
	repo := &mockTaskRepository{
		tasks: map[string]*models.Task{
			"t1": {ID: "t1", Title: "Task 1", Status: "pending", ProjectID: "p1"},
		},
	}
	cm := cache.NewCacheManager()
	svc := NewTaskServiceWithCache(repo, cm)

	ctx := context.Background()

	// Prime caches
	svc.GetTask(ctx, "t1")
	svc.ListTasks(ctx, &ListTasksRequest{Limit: 10})

	// Delete should invalidate
	svc.DeleteTask(ctx, "t1")

	// List should call repo again
	svc.ListTasks(ctx, &ListTasksRequest{Limit: 10})
	if repo.listCallCount != 2 {
		t.Errorf("expected 2 list calls after delete, got %d", repo.listCallCount)
	}
}

// TestTaskCompleteInvalidatesCache tests that CompleteTask invalidates caches
func TestTaskCompleteInvalidatesCache(t *testing.T) {
	repo := &mockTaskRepository{
		tasks: map[string]*models.Task{
			"t1": {ID: "t1", Title: "Task 1", Status: "pending", ProjectID: "p1"},
		},
	}
	cm := cache.NewCacheManager()
	svc := NewTaskServiceWithCache(repo, cm)

	ctx := context.Background()

	// Prime caches
	svc.GetTask(ctx, "t1")
	svc.ListTasks(ctx, &ListTasksRequest{Limit: 10})

	// Complete should invalidate
	svc.CompleteTask(ctx, "t1")

	// List should call repo again
	svc.ListTasks(ctx, &ListTasksRequest{Limit: 10})
	if repo.listCallCount != 2 {
		t.Errorf("expected 2 list calls after complete, got %d", repo.listCallCount)
	}
}

// TestTaskCacheNilSafe tests that service works when cache is nil
func TestTaskCacheNilSafe(t *testing.T) {
	repo := &mockTaskRepository{
		tasks: map[string]*models.Task{
			"t1": {ID: "t1", Title: "Task 1", Status: "pending", ProjectID: "p1"},
		},
	}
	svc := NewTaskService(repo) // No cache

	ctx := context.Background()

	task, err := svc.GetTask(ctx, "t1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if task.ID != "t1" {
		t.Error("expected task t1")
	}

	// Should work multiple times without issues
	task2, err := svc.GetTask(ctx, "t1")
	if err != nil {
		t.Fatalf("unexpected error on second call: %v", err)
	}
	if task2.ID != "t1" {
		t.Error("expected task t1 on second call")
	}
}
