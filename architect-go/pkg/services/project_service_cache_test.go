package services

import (
	"context"
	"errors"
	"testing"

	"architect-go/pkg/cache"
	"architect-go/pkg/models"
)

// mockProjectRepository implements ProjectRepository for testing
type mockProjectRepository struct {
	getCallCount    int
	createCallCount int
	updateCallCount int
	deleteCallCount int
	listCallCount   int
	projects        map[string]*models.Project
}

func (m *mockProjectRepository) Get(ctx context.Context, id string) (*models.Project, error) {
	m.getCallCount++
	if p, ok := m.projects[id]; ok {
		return p, nil
	}
	return nil, errors.New("not found")
}

func (m *mockProjectRepository) Create(ctx context.Context, project *models.Project) error {
	m.createCallCount++
	if m.projects == nil {
		m.projects = make(map[string]*models.Project)
	}
	m.projects[project.ID] = project
	return nil
}

func (m *mockProjectRepository) Update(ctx context.Context, project *models.Project) error {
	m.updateCallCount++
	m.projects[project.ID] = project
	return nil
}

func (m *mockProjectRepository) Delete(ctx context.Context, id string) error {
	m.deleteCallCount++
	delete(m.projects, id)
	return nil
}

func (m *mockProjectRepository) List(ctx context.Context, filters map[string]interface{}, limit, offset int) ([]*models.Project, int64, error) {
	m.listCallCount++
	var projects []*models.Project
	for _, p := range m.projects {
		projects = append(projects, p)
	}
	return projects, int64(len(projects)), nil
}

func (m *mockProjectRepository) HardDelete(ctx context.Context, id string) error {
	delete(m.projects, id)
	return nil
}

// TestProjectCacheHit tests that cache returns stored project
func TestProjectCacheHit(t *testing.T) {
	repo := &mockProjectRepository{
		projects: map[string]*models.Project{
			"p1": {ID: "p1", Name: "Project 1", Status: "active"},
		},
	}
	cm := cache.NewCacheManager()
	svc := NewProjectServiceWithCache(repo, cm)

	ctx := context.Background()

	// First call should hit repository
	p1, err := svc.GetProject(ctx, "p1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if repo.getCallCount != 1 {
		t.Errorf("expected 1 repo call, got %d", repo.getCallCount)
	}

	// Second call should hit cache
	p2, err := svc.GetProject(ctx, "p1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if repo.getCallCount != 1 {
		t.Errorf("expected still 1 repo call after cache hit, got %d", repo.getCallCount)
	}

	if p1.ID != p2.ID {
		t.Error("cached project differs from original")
	}
}

// TestProjectCacheMiss tests that cache miss calls repository
func TestProjectCacheMiss(t *testing.T) {
	repo := &mockProjectRepository{
		projects: map[string]*models.Project{
			"p1": {ID: "p1", Name: "Project 1", Status: "active"},
		},
	}
	cm := cache.NewCacheManager()
	svc := NewProjectServiceWithCache(repo, cm)

	ctx := context.Background()

	// Different project ID should not use cache
	_, err := svc.GetProject(ctx, "p1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	_, err = svc.GetProject(ctx, "p2") // Different ID
	if err == nil {
		t.Error("expected error for non-existent project")
	}
	if repo.getCallCount != 2 {
		t.Errorf("expected 2 repo calls for different IDs, got %d", repo.getCallCount)
	}
}

// TestProjectCreateInvalidatesCache tests that CreateProject invalidates list cache
func TestProjectCreateInvalidatesCache(t *testing.T) {
	repo := &mockProjectRepository{projects: make(map[string]*models.Project)}
	cm := cache.NewCacheManager()
	svc := NewProjectServiceWithCache(repo, cm)

	ctx := context.Background()

	// Prime cache
	svc.ListProjects(ctx, &ListProjectsRequest{Limit: 10})
	if repo.listCallCount != 1 {
		t.Errorf("expected 1 initial list call, got %d", repo.listCallCount)
	}

	// Create should invalidate
	svc.CreateProject(ctx, &CreateProjectRequest{Name: "New Project"})

	// Next list should call repo again
	svc.ListProjects(ctx, &ListProjectsRequest{Limit: 10})
	if repo.listCallCount != 2 {
		t.Errorf("expected 2 list calls after create, got %d", repo.listCallCount)
	}
}

// TestProjectUpdateInvalidatesCache tests that UpdateProject invalidates both caches
func TestProjectUpdateInvalidatesCache(t *testing.T) {
	p1 := &models.Project{ID: "p1", Name: "Project 1", Status: "active"}
	repo := &mockProjectRepository{
		projects: map[string]*models.Project{"p1": p1},
	}
	cm := cache.NewCacheManager()
	svc := NewProjectServiceWithCache(repo, cm)

	ctx := context.Background()

	// Prime both caches
	svc.GetProject(ctx, "p1")        // Item cache
	svc.ListProjects(ctx, &ListProjectsRequest{Limit: 10}) // List cache

	// Update should invalidate both
	svc.UpdateProject(ctx, "p1", &UpdateProjectRequest{Name: "Updated"})

	// Next get should call repo
	svc.GetProject(ctx, "p1")
	if repo.getCallCount != 3 {
		// 1 = initial cache prime, 2 = inside UpdateProject, 3 = after invalidation
		t.Errorf("expected 3 get calls after update, got %d", repo.getCallCount)
	}

	// Next list should call repo
	svc.ListProjects(ctx, &ListProjectsRequest{Limit: 10})
	if repo.listCallCount != 2 {
		t.Errorf("expected 2 list calls after update, got %d", repo.listCallCount)
	}
}

// TestProjectDeleteInvalidatesCache tests that DeleteProject invalidates both caches
func TestProjectDeleteInvalidatesCache(t *testing.T) {
	repo := &mockProjectRepository{
		projects: map[string]*models.Project{
			"p1": {ID: "p1", Name: "Project 1", Status: "active"},
		},
	}
	cm := cache.NewCacheManager()
	svc := NewProjectServiceWithCache(repo, cm)

	ctx := context.Background()

	// Prime caches
	svc.GetProject(ctx, "p1")
	svc.ListProjects(ctx, &ListProjectsRequest{Limit: 10})

	// Delete should invalidate
	svc.DeleteProject(ctx, "p1")

	// List should call repo again
	svc.ListProjects(ctx, &ListProjectsRequest{Limit: 10})
	if repo.listCallCount != 2 {
		t.Errorf("expected 2 list calls after delete, got %d", repo.listCallCount)
	}
}

// TestProjectCacheNilSafe tests that service works when cache is nil
func TestProjectCacheNilSafe(t *testing.T) {
	repo := &mockProjectRepository{
		projects: map[string]*models.Project{
			"p1": {ID: "p1", Name: "Project 1", Status: "active"},
		},
	}
	svc := NewProjectService(repo) // No cache

	ctx := context.Background()

	p, err := svc.GetProject(ctx, "p1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if p.ID != "p1" {
		t.Error("expected project p1")
	}

	// Should work multiple times without issues
	p2, err := svc.GetProject(ctx, "p1")
	if err != nil {
		t.Fatalf("unexpected error on second call: %v", err)
	}
	if p2.ID != "p1" {
		t.Error("expected project p1 on second call")
	}
}
