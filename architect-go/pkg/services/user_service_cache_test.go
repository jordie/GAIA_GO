package services

import (
	"context"
	"errors"
	"testing"

	"architect-go/pkg/cache"
	"architect-go/pkg/models"
)

// mockUserRepository implements UserRepository for testing
type mockUserRepository struct {
	getCallCount    int
	createCallCount int
	updateCallCount int
	deleteCallCount int
	listCallCount   int
	users           map[string]*models.User
}

func (m *mockUserRepository) Get(ctx context.Context, id string) (*models.User, error) {
	m.getCallCount++
	if u, ok := m.users[id]; ok {
		return u, nil
	}
	return nil, errors.New("not found")
}

func (m *mockUserRepository) Create(ctx context.Context, user *models.User) error {
	m.createCallCount++
	if m.users == nil {
		m.users = make(map[string]*models.User)
	}
	m.users[user.ID] = user
	return nil
}

func (m *mockUserRepository) Update(ctx context.Context, user *models.User) error {
	m.updateCallCount++
	m.users[user.ID] = user
	return nil
}

func (m *mockUserRepository) Delete(ctx context.Context, id string) error {
	m.deleteCallCount++
	delete(m.users, id)
	return nil
}

func (m *mockUserRepository) List(ctx context.Context, limit, offset int) ([]*models.User, int64, error) {
	m.listCallCount++
	var users []*models.User
	for _, u := range m.users {
		users = append(users, u)
	}
	return users, int64(len(users)), nil
}

func (m *mockUserRepository) GetByUsername(ctx context.Context, username string) (*models.User, error) {
	return nil, errors.New("not found")
}

func (m *mockUserRepository) GetByEmail(ctx context.Context, email string) (*models.User, error) {
	return nil, errors.New("not found")
}

// TestUserCacheHit tests that cache returns stored user
func TestUserCacheHit(t *testing.T) {
	repo := &mockUserRepository{
		users: map[string]*models.User{
			"u1": {ID: "u1", Username: "user1", Email: "user1@test.com", Status: "active"},
		},
	}
	cm := cache.NewCacheManager()
	svc := NewUserServiceWithCache(repo, cm)

	ctx := context.Background()

	// First call should hit repository
	user1, err := svc.GetUser(ctx, "u1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if repo.getCallCount != 1 {
		t.Errorf("expected 1 repo call, got %d", repo.getCallCount)
	}

	// Second call should hit cache
	user2, err := svc.GetUser(ctx, "u1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if repo.getCallCount != 1 {
		t.Errorf("expected still 1 repo call after cache hit, got %d", repo.getCallCount)
	}

	if user1.ID != user2.ID {
		t.Error("cached user differs from original")
	}
}

// TestUserCacheMiss tests that cache miss calls repository
func TestUserCacheMiss(t *testing.T) {
	repo := &mockUserRepository{
		users: map[string]*models.User{
			"u1": {ID: "u1", Username: "user1", Email: "user1@test.com", Status: "active"},
		},
	}
	cm := cache.NewCacheManager()
	svc := NewUserServiceWithCache(repo, cm)

	ctx := context.Background()

	// First call
	_, err := svc.GetUser(ctx, "u1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Different user ID should not use cache
	_, err = svc.GetUser(ctx, "u2")
	if err == nil {
		t.Error("expected error for non-existent user")
	}
	if repo.getCallCount != 2 {
		t.Errorf("expected 2 repo calls for different IDs, got %d", repo.getCallCount)
	}
}

// TestUserCreateInvalidatesCache tests that CreateUser invalidates list cache
func TestUserCreateInvalidatesCache(t *testing.T) {
	repo := &mockUserRepository{users: make(map[string]*models.User)}
	cm := cache.NewCacheManager()
	svc := NewUserServiceWithCache(repo, cm)

	ctx := context.Background()

	// Prime cache
	svc.ListUsers(ctx, &ListUsersRequest{Limit: 10})
	if repo.listCallCount != 1 {
		t.Errorf("expected 1 initial list call, got %d", repo.listCallCount)
	}

	// Create should invalidate
	svc.CreateUser(ctx, &CreateUserRequest{Username: "newuser", Email: "new@test.com", Password: "pass"})

	// Next list should call repo again
	svc.ListUsers(ctx, &ListUsersRequest{Limit: 10})
	if repo.listCallCount != 2 {
		t.Errorf("expected 2 list calls after create, got %d", repo.listCallCount)
	}
}

// TestUserUpdateInvalidatesCache tests that UpdateUser invalidates both caches
func TestUserUpdateInvalidatesCache(t *testing.T) {
	user1 := &models.User{ID: "u1", Username: "user1", Email: "user1@test.com", Status: "active"}
	repo := &mockUserRepository{
		users: map[string]*models.User{"u1": user1},
	}
	cm := cache.NewCacheManager()
	svc := NewUserServiceWithCache(repo, cm)

	ctx := context.Background()

	// Prime both caches
	svc.GetUser(ctx, "u1") // Item cache
	svc.ListUsers(ctx, &ListUsersRequest{Limit: 10})

	// Update should invalidate both
	svc.UpdateUser(ctx, "u1", &UpdateUserRequest{Email: "updated@test.com"})

	// Next get should call repo
	svc.GetUser(ctx, "u1")
	if repo.getCallCount != 3 {
		// 1 = initial cache prime, 2 = inside UpdateUser, 3 = after invalidation
		t.Errorf("expected 3 get calls after update, got %d", repo.getCallCount)
	}

	// Next list should call repo
	svc.ListUsers(ctx, &ListUsersRequest{Limit: 10})
	if repo.listCallCount != 2 {
		t.Errorf("expected 2 list calls after update, got %d", repo.listCallCount)
	}
}

// TestUserDeleteInvalidatesCache tests that DeleteUser invalidates both caches
func TestUserDeleteInvalidatesCache(t *testing.T) {
	repo := &mockUserRepository{
		users: map[string]*models.User{
			"u1": {ID: "u1", Username: "user1", Email: "user1@test.com", Status: "active"},
		},
	}
	cm := cache.NewCacheManager()
	svc := NewUserServiceWithCache(repo, cm)

	ctx := context.Background()

	// Prime caches
	svc.GetUser(ctx, "u1")
	svc.ListUsers(ctx, &ListUsersRequest{Limit: 10})

	// Delete should invalidate
	svc.DeleteUser(ctx, "u1")

	// List should call repo again
	svc.ListUsers(ctx, &ListUsersRequest{Limit: 10})
	if repo.listCallCount != 2 {
		t.Errorf("expected 2 list calls after delete, got %d", repo.listCallCount)
	}
}

// TestUserCacheNilSafe tests that service works when cache is nil
func TestUserCacheNilSafe(t *testing.T) {
	repo := &mockUserRepository{
		users: map[string]*models.User{
			"u1": {ID: "u1", Username: "user1", Email: "user1@test.com", Status: "active"},
		},
	}
	svc := NewUserService(repo) // No cache

	ctx := context.Background()

	user, err := svc.GetUser(ctx, "u1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if user.ID != "u1" {
		t.Error("expected user u1")
	}

	// Should work multiple times without issues
	user2, err := svc.GetUser(ctx, "u1")
	if err != nil {
		t.Fatalf("unexpected error on second call: %v", err)
	}
	if user2.ID != "u1" {
		t.Error("expected user u1 on second call")
	}
}
