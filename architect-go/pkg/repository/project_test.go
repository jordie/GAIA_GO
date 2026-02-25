package repository

import (
	"context"
	"testing"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"

	"architect-go/pkg/models"
)

// setupTestDB creates an in-memory SQLite database for testing
func setupTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("failed to connect to test database: %v", err)
	}

	// Auto migrate models
	db.AutoMigrate(&models.Project{}, &models.User{})

	return db
}

func TestProjectRepository_CreateAndGet(t *testing.T) {
	db := setupTestDB(t)
	repo := NewProjectRepository(db)

	project := &models.Project{
		ID:          "proj-123",
		Name:        "Test Project",
		Description: "A test project",
		Status:      "active",
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	}

	// Create
	err := repo.Create(context.Background(), project)
	if err != nil {
		t.Fatalf("failed to create project: %v", err)
	}

	// Get
	retrieved, err := repo.Get(context.Background(), "proj-123")
	if err != nil {
		t.Fatalf("failed to get project: %v", err)
	}

	if retrieved.Name != "Test Project" {
		t.Errorf("expected Name 'Test Project', got %s", retrieved.Name)
	}

	if retrieved.Status != "active" {
		t.Errorf("expected Status 'active', got %s", retrieved.Status)
	}
}

func TestProjectRepository_Get_NotFound(t *testing.T) {
	db := setupTestDB(t)
	repo := NewProjectRepository(db)

	_, err := repo.Get(context.Background(), "nonexistent")
	if err == nil {
		t.Fatalf("expected error for non-existent project")
	}

	if err.Error() != "project not found" {
		t.Errorf("expected 'project not found' error, got: %v", err)
	}
}

func TestProjectRepository_List_NoFilter(t *testing.T) {
	db := setupTestDB(t)
	repo := NewProjectRepository(db)

	// Create multiple projects
	projects := []*models.Project{
		{ID: "p1", Name: "Project 1", Status: "active", CreatedAt: time.Now(), UpdatedAt: time.Now()},
		{ID: "p2", Name: "Project 2", Status: "active", CreatedAt: time.Now(), UpdatedAt: time.Now()},
		{ID: "p3", Name: "Project 3", Status: "archived", CreatedAt: time.Now(), UpdatedAt: time.Now()},
	}

	for _, p := range projects {
		repo.Create(context.Background(), p)
	}

	// List all
	results, total, err := repo.List(context.Background(), map[string]interface{}{}, 10, 0)
	if err != nil {
		t.Fatalf("failed to list projects: %v", err)
	}

	if len(results) != 3 {
		t.Errorf("expected 3 projects, got %d", len(results))
	}

	if total != 3 {
		t.Errorf("expected total 3, got %d", total)
	}
}

func TestProjectRepository_List_StatusFilter(t *testing.T) {
	db := setupTestDB(t)
	repo := NewProjectRepository(db)

	projects := []*models.Project{
		{ID: "p1", Name: "Project 1", Status: "active", CreatedAt: time.Now(), UpdatedAt: time.Now()},
		{ID: "p2", Name: "Project 2", Status: "active", CreatedAt: time.Now(), UpdatedAt: time.Now()},
		{ID: "p3", Name: "Project 3", Status: "archived", CreatedAt: time.Now(), UpdatedAt: time.Now()},
	}

	for _, p := range projects {
		repo.Create(context.Background(), p)
	}

	// Filter by status
	results, total, err := repo.List(context.Background(), map[string]interface{}{"status": "active"}, 10, 0)
	if err != nil {
		t.Fatalf("failed to list projects: %v", err)
	}

	if len(results) != 2 {
		t.Errorf("expected 2 active projects, got %d", len(results))
	}

	if total != 2 {
		t.Errorf("expected total 2, got %d", total)
	}
}

func TestProjectRepository_List_Pagination(t *testing.T) {
	db := setupTestDB(t)
	repo := NewProjectRepository(db)

	// Create 5 projects
	for i := 1; i <= 5; i++ {
		p := &models.Project{
			ID:        "p" + string(rune(i+'0')),
			Name:      "Project " + string(rune(i+'0')),
			Status:    "active",
			CreatedAt: time.Now(),
			UpdatedAt: time.Now(),
		}
		repo.Create(context.Background(), p)
	}

	// Page 1: limit=2, offset=0
	results, total, err := repo.List(context.Background(), map[string]interface{}{}, 2, 0)
	if err != nil {
		t.Fatalf("failed to list: %v", err)
	}

	if len(results) != 2 {
		t.Errorf("expected 2 results, got %d", len(results))
	}

	if total != 5 {
		t.Errorf("expected total 5, got %d", total)
	}

	// Page 2: limit=2, offset=2
	results2, total2, err := repo.List(context.Background(), map[string]interface{}{}, 2, 2)
	if err != nil {
		t.Fatalf("failed to list: %v", err)
	}

	if len(results2) != 2 {
		t.Errorf("expected 2 results on page 2, got %d", len(results2))
	}

	if total2 != 5 {
		t.Errorf("expected total 5 on page 2, got %d", total2)
	}
}

func TestProjectRepository_Update(t *testing.T) {
	db := setupTestDB(t)
	repo := NewProjectRepository(db)

	project := &models.Project{
		ID:     "proj-123",
		Name:   "Original Name",
		Status: "active",
	}

	repo.Create(context.Background(), project)

	// Update
	project.Name = "Updated Name"
	project.Status = "archived"
	err := repo.Update(context.Background(), project)
	if err != nil {
		t.Fatalf("failed to update: %v", err)
	}

	// Verify
	retrieved, _ := repo.Get(context.Background(), "proj-123")
	if retrieved.Name != "Updated Name" {
		t.Errorf("expected name 'Updated Name', got %s", retrieved.Name)
	}

	if retrieved.Status != "archived" {
		t.Errorf("expected status 'archived', got %s", retrieved.Status)
	}
}

func TestProjectRepository_Delete_SoftDelete(t *testing.T) {
	db := setupTestDB(t)
	repo := NewProjectRepository(db)

	project := &models.Project{
		ID:   "proj-123",
		Name: "Test",
	}

	repo.Create(context.Background(), project)

	// Delete (soft)
	err := repo.Delete(context.Background(), "proj-123")
	if err != nil {
		t.Fatalf("failed to delete: %v", err)
	}

	// Verify Get returns not found
	_, err = repo.Get(context.Background(), "proj-123")
	if err == nil {
		t.Errorf("expected not found error after soft delete")
	}

	// Verify row still exists in DB (unscoped)
	var count int64
	db.Unscoped().Model(&models.Project{}).Where("id = ?", "proj-123").Count(&count)
	if count != 1 {
		t.Errorf("expected soft-deleted row to exist in DB, found %d rows", count)
	}
}

func TestProjectRepository_HardDelete(t *testing.T) {
	db := setupTestDB(t)
	repo := NewProjectRepository(db)

	project := &models.Project{
		ID:   "proj-123",
		Name: "Test",
	}

	repo.Create(context.Background(), project)

	// Hard delete
	err := repo.HardDelete(context.Background(), "proj-123")
	if err != nil {
		t.Fatalf("failed to hard delete: %v", err)
	}

	// Verify row is gone from DB
	var count int64
	db.Unscoped().Model(&models.Project{}).Where("id = ?", "proj-123").Count(&count)
	if count != 0 {
		t.Errorf("expected hard-deleted row to be gone, found %d rows", count)
	}
}

func TestUserRepository_GetByUsername(t *testing.T) {
	db := setupTestDB(t)
	repo := NewUserRepository(db)

	user := &models.User{
		ID:       "user-123",
		Username: "testuser",
		Email:    "test@example.com",
		Status:   "active",
	}

	repo.Create(context.Background(), user)

	// Get by username
	retrieved, err := repo.GetByUsername(context.Background(), "testuser")
	if err != nil {
		t.Fatalf("failed to get user by username: %v", err)
	}

	if retrieved.ID != "user-123" {
		t.Errorf("expected ID user-123, got %s", retrieved.ID)
	}
}

func TestUserRepository_GetByUsername_NotFound(t *testing.T) {
	db := setupTestDB(t)
	repo := NewUserRepository(db)

	_, err := repo.GetByUsername(context.Background(), "nonexistent")
	if err == nil {
		t.Fatalf("expected error for non-existent username")
	}

	if err.Error() != "user not found" {
		t.Errorf("expected 'user not found' error, got: %v", err)
	}
}

func TestUserRepository_GetByEmail(t *testing.T) {
	db := setupTestDB(t)
	repo := NewUserRepository(db)

	user := &models.User{
		ID:       "user-123",
		Username: "testuser",
		Email:    "test@example.com",
		Status:   "active",
	}

	repo.Create(context.Background(), user)

	// Get by email
	retrieved, err := repo.GetByEmail(context.Background(), "test@example.com")
	if err != nil {
		t.Fatalf("failed to get user by email: %v", err)
	}

	if retrieved.Username != "testuser" {
		t.Errorf("expected username testuser, got %s", retrieved.Username)
	}
}

func TestUserRepository_GetByEmail_NotFound(t *testing.T) {
	db := setupTestDB(t)
	repo := NewUserRepository(db)

	_, err := repo.GetByEmail(context.Background(), "nonexistent@example.com")
	if err == nil {
		t.Fatalf("expected error for non-existent email")
	}
}

func TestUserRepository_CreateAndGet(t *testing.T) {
	db := setupTestDB(t)
	repo := NewUserRepository(db)

	user := &models.User{
		ID:       "user-123",
		Username: "testuser",
		Email:    "test@example.com",
		Status:   "active",
	}

	err := repo.Create(context.Background(), user)
	if err != nil {
		t.Fatalf("failed to create user: %v", err)
	}

	retrieved, err := repo.Get(context.Background(), "user-123")
	if err != nil {
		t.Fatalf("failed to get user: %v", err)
	}

	if retrieved.Username != "testuser" {
		t.Errorf("expected username testuser, got %s", retrieved.Username)
	}
}

func TestUserRepository_Update(t *testing.T) {
	db := setupTestDB(t)
	repo := NewUserRepository(db)

	user := &models.User{
		ID:       "user-123",
		Username: "testuser",
		Email:    "old@example.com",
	}

	repo.Create(context.Background(), user)

	user.Email = "new@example.com"
	err := repo.Update(context.Background(), user)
	if err != nil {
		t.Fatalf("failed to update: %v", err)
	}

	retrieved, _ := repo.Get(context.Background(), "user-123")
	if retrieved.Email != "new@example.com" {
		t.Errorf("expected email new@example.com, got %s", retrieved.Email)
	}
}

func TestUserRepository_Delete(t *testing.T) {
	db := setupTestDB(t)
	repo := NewUserRepository(db)

	user := &models.User{
		ID:       "user-123",
		Username: "testuser",
	}

	repo.Create(context.Background(), user)

	err := repo.Delete(context.Background(), "user-123")
	if err != nil {
		t.Fatalf("failed to delete: %v", err)
	}

	_, err = repo.Get(context.Background(), "user-123")
	if err == nil {
		t.Errorf("expected not found error after delete")
	}
}
