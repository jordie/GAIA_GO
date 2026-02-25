package services

import (
	"context"
	"testing"

	"architect-go/pkg/models"
	"architect-go/pkg/repository"
)

// mockActivityRepoForService for testing activity service
type mockActivityRepoForService struct {
	activities []models.Activity
}

func newMockActivityRepoForService() *mockActivityRepoForService {
	return &mockActivityRepoForService{
		activities: []models.Activity{},
	}
}

func (m *mockActivityRepoForService) LogActivity(ctx context.Context, activity *models.Activity) error {
	m.activities = append(m.activities, *activity)
	return nil
}

func (m *mockActivityRepoForService) GetUserActivity(ctx context.Context, userID string, limit, offset int) ([]models.Activity, error) {
	var result []models.Activity
	for _, a := range m.activities {
		if a.UserID == userID {
			result = append(result, a)
		}
	}
	return result, nil
}

func (m *mockActivityRepoForService) GetUserActivityCount(ctx context.Context, userID string) (int64, error) {
	count := 0
	for _, a := range m.activities {
		if a.UserID == userID {
			count++
		}
	}
	return int64(count), nil
}

func (m *mockActivityRepoForService) GetProjectActivity(ctx context.Context, resourceType, resourceID string, limit, offset int) ([]models.Activity, error) {
	var result []models.Activity
	for _, a := range m.activities {
		if a.ResourceType == resourceType && a.ResourceID == resourceID {
			result = append(result, a)
		}
	}
	return result, nil
}

func (m *mockActivityRepoForService) GetProjectActivityCount(ctx context.Context, resourceType, resourceID string) (int64, error) {
	count := 0
	for _, a := range m.activities {
		if a.ResourceType == resourceType && a.ResourceID == resourceID {
			count++
		}
	}
	return int64(count), nil
}

func (m *mockActivityRepoForService) FilterActivity(ctx context.Context, filters repository.ActivityFilters, limit, offset int) ([]models.Activity, error) {
	var result []models.Activity
	for _, a := range m.activities {
		if (filters.UserID == "" || a.UserID == filters.UserID) &&
			(filters.Action == "" || a.Action == filters.Action) &&
			(filters.ResourceType == "" || a.ResourceType == filters.ResourceType) {
			result = append(result, a)
		}
	}
	return result, nil
}

func (m *mockActivityRepoForService) FilterActivityCount(ctx context.Context, filters repository.ActivityFilters) (int64, error) {
	count := 0
	for _, a := range m.activities {
		if (filters.UserID == "" || a.UserID == filters.UserID) &&
			(filters.Action == "" || a.Action == filters.Action) &&
			(filters.ResourceType == "" || a.ResourceType == filters.ResourceType) {
			count++
		}
	}
	return int64(count), nil
}

func (m *mockActivityRepoForService) GetActivityStats(ctx context.Context, userID string) (map[string]int64, error) {
	stats := make(map[string]int64)
	for _, a := range m.activities {
		if a.UserID == userID {
			stats[a.Action]++
		}
	}
	return stats, nil
}

func (m *mockActivityRepoForService) GetRecentActivity(ctx context.Context, limit int) ([]models.Activity, error) {
	return m.activities, nil
}

func (m *mockActivityRepoForService) DeleteActivity(ctx context.Context, activityID string) error {
	return nil
}

func (m *mockActivityRepoForService) GetActivity(ctx context.Context, activityID string) (*models.Activity, error) {
	return nil, nil
}

func (m *mockActivityRepoForService) DeleteOldActivities(ctx context.Context, daysOld int) (int64, error) {
	return 0, nil
}

// TestLogActivityAndRetrieve verifies activity logging and retrieval
func TestLogActivityAndRetrieve(t *testing.T) {
	ctx := context.Background()
	repo := newMockActivityRepoForService()
	service := NewActivityService(repo)

	// Log an activity
	err := service.LogActivity(ctx, "user1", "create", "task", "task-123", map[string]interface{}{"title": "New Task"})
	if err != nil {
		t.Fatalf("LogActivity failed: %v", err)
	}

	// Retrieve activities
	activities, count, err := service.GetUserActivity(ctx, "user1", 10, 0)
	if err != nil {
		t.Fatalf("GetUserActivity failed: %v", err)
	}

	if count != 1 {
		t.Errorf("Expected count 1, got %d", count)
	}

	if len(activities) != 1 {
		t.Errorf("Expected 1 activity, got %d", len(activities))
	}

	if activities[0].Action != "create" {
		t.Errorf("Expected action 'create', got '%s'", activities[0].Action)
	}
}

// TestFilterActivitiesByCriteria verifies activity filtering
func TestFilterActivitiesByCriteria(t *testing.T) {
	ctx := context.Background()
	repo := newMockActivityRepoForService()
	service := NewActivityService(repo)

	// Log multiple activities
	_ = service.LogActivity(ctx, "user1", "create", "task", "task-1", nil)
	_ = service.LogActivity(ctx, "user1", "update", "task", "task-1", nil)
	_ = service.LogActivity(ctx, "user2", "create", "project", "proj-1", nil)

	// Filter by user and action
	filters := repository.ActivityFilters{
		UserID: "user1",
		Action: "create",
	}

	activities, count, err := service.FilterActivity(ctx, filters, 10, 0)
	if err != nil {
		t.Fatalf("FilterActivity failed: %v", err)
	}

	if count != 1 {
		t.Errorf("Expected count 1, got %d", count)
	}

	if len(activities) != 1 {
		t.Errorf("Expected 1 activity, got %d", len(activities))
	}

	if activities[0].UserID != "user1" || activities[0].Action != "create" {
		t.Error("Filtered activity does not match criteria")
	}
}

// TestActivityStatistics verifies activity stats calculation
func TestActivityStatistics(t *testing.T) {
	ctx := context.Background()
	repo := newMockActivityRepoForService()
	service := NewActivityService(repo)

	// Log various activities
	_ = service.LogActivity(ctx, "user1", "create", "task", "task-1", nil)
	_ = service.LogActivity(ctx, "user1", "create", "task", "task-2", nil)
	_ = service.LogActivity(ctx, "user1", "update", "task", "task-1", nil)
	_ = service.LogActivity(ctx, "user1", "delete", "project", "proj-1", nil)

	// Get stats
	stats, err := service.GetActivityStats(ctx, "user1")
	if err != nil {
		t.Fatalf("GetActivityStats failed: %v", err)
	}

	if stats["create"] != 2 {
		t.Errorf("Expected 2 create actions, got %d", stats["create"])
	}

	if stats["update"] != 1 {
		t.Errorf("Expected 1 update action, got %d", stats["update"])
	}

	if stats["delete"] != 1 {
		t.Errorf("Expected 1 delete action, got %d", stats["delete"])
	}
}

// TestProjectActivityRetrieval verifies project/resource activity retrieval
func TestProjectActivityRetrieval(t *testing.T) {
	ctx := context.Background()
	repo := newMockActivityRepoForService()
	service := NewActivityService(repo)

	// Log activities for different resources
	_ = service.LogActivity(ctx, "user1", "create", "task", "task-1", nil)
	_ = service.LogActivity(ctx, "user2", "update", "task", "task-1", nil)
	_ = service.LogActivity(ctx, "user3", "view", "task", "task-1", nil)
	_ = service.LogActivity(ctx, "user1", "create", "task", "task-2", nil)

	// Get activities for specific resource
	activities, count, err := service.GetProjectActivity(ctx, "task", "task-1", 10, 0)
	if err != nil {
		t.Fatalf("GetProjectActivity failed: %v", err)
	}

	if count != 3 {
		t.Errorf("Expected count 3, got %d", count)
	}

	if len(activities) != 3 {
		t.Errorf("Expected 3 activities, got %d", len(activities))
	}
}
