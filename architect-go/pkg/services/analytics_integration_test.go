package services

import (
	"context"
	"testing"
	"time"

	"architect-go/pkg/metrics"
	"architect-go/pkg/models"
	"architect-go/pkg/repository"
)

// Service Integration Tests

func TestEventAnalytics_CompleteWorkflow(t *testing.T) {
	mockRepo := &mockEventRepository{
		events: []models.Event{
			{ID: "1", Type: "login", UserID: "user1", Timestamp: time.Now()},
			{ID: "2", Type: "create_project", UserID: "user1", Timestamp: time.Now()},
			{ID: "3", Type: "add_task", UserID: "user1", Timestamp: time.Now().Add(1 * time.Hour)},
			{ID: "4", Type: "complete_task", UserID: "user1", Timestamp: time.Now().Add(2 * time.Hour)},
		},
	}

	service := NewEventAnalyticsService(mockRepo)

	// Test timeline
	timeline, err := service.GetTimeline(context.Background(), time.Now().AddDate(0, 0, -1), time.Now(), "hour")
	if err != nil {
		t.Errorf("GetTimeline failed: %v", err)
	}
	if len(timeline) == 0 {
		t.Error("expected timeline data")
	}

	// Test user journey
	journey, err := service.GetUserJourney(context.Background(), "user1", time.Now().AddDate(0, 0, -1), time.Now())
	if err != nil {
		t.Errorf("GetUserJourney failed: %v", err)
	}
	if len(journey) != 4 {
		t.Errorf("expected 4 journey events, got %d", len(journey))
	}

	// Test session analysis
	metrics, err := service.GetSessionAnalysis(context.Background(), time.Now().AddDate(0, 0, -1), time.Now())
	if err != nil {
		t.Errorf("GetSessionAnalysis failed: %v", err)
	}
	if metrics.ActiveUsers == 0 {
		t.Error("expected active users > 0")
	}
}

func TestActivityAnalytics_CompleteWorkflow(t *testing.T) {
	mockRepo := &mockActivityRepository{
		activities: []models.Activity{
			{ID: "1", UserID: "user1", Action: "create_project", ResourceType: "project", ResourceID: "p1", Timestamp: time.Now()},
			{ID: "2", UserID: "user2", Action: "create_task", ResourceType: "task", ResourceID: "t1", Timestamp: time.Now()},
			{ID: "3", UserID: "user1", Action: "update_project", ResourceType: "project", ResourceID: "p1", Timestamp: time.Now().Add(1 * time.Hour)},
		},
	}

	service := NewActivityAnalyticsService(mockRepo)

	// Test trends
	data, _, err := service.GetActivityTrends(context.Background(), "day", "create_project")
	if err != nil {
		t.Errorf("GetActivityTrends failed: %v", err)
	}
	if len(data) == 0 {
		t.Error("expected trend data")
	}

	// Test top users
	users, err := service.GetTopUsers(context.Background(), 30, 10)
	if err != nil {
		t.Errorf("GetTopUsers failed: %v", err)
	}
	if len(users) == 0 {
		t.Error("expected top users data")
	}
}

func TestUserAnalytics_CompleteWorkflow(t *testing.T) {
	mockRepo := &mockUserRepository2{}

	service := NewUserAnalyticsService(mockRepo)

	// Test growth
	growth, err := service.GetUserGrowth(context.Background(), "month")
	if err != nil {
		t.Errorf("GetUserGrowth failed: %v", err)
	}
	if growth["total_users"] == nil {
		t.Error("expected total_users in growth")
	}

	// Test retention
	retention, err := service.GetUserRetention(context.Background(), time.Now())
	if err != nil {
		t.Errorf("GetUserRetention failed: %v", err)
	}
	if retention["cohort_size"] == nil {
		t.Error("expected cohort_size in retention")
	}

	// Test churn
	churn, err := service.GetUserChurn(context.Background(), 30)
	if err != nil {
		t.Errorf("GetUserChurn failed: %v", err)
	}
	if churn["churn_rate"] == nil {
		t.Error("expected churn_rate in churn")
	}
}

func TestPerformanceAnalytics_CompleteWorkflow(t *testing.T) {
	mockMetrics := &metrics.Metrics{}
	service := NewPerformanceAnalyticsService(mockMetrics)

	// Test request metrics
	reqMetrics, err := service.GetRequestMetrics(context.Background(), "hour")
	if err != nil {
		t.Errorf("GetRequestMetrics failed: %v", err)
	}
	if reqMetrics["total_requests"] == nil {
		t.Error("expected total_requests in metrics")
	}

	// Test system metrics
	sysMetrics, err := service.GetSystemMetrics(context.Background())
	if err != nil {
		t.Errorf("GetSystemMetrics failed: %v", err)
	}
	if sysMetrics["cpu_usage"] == nil {
		t.Error("expected cpu_usage in system metrics")
	}

	// Test database metrics
	dbMetrics, err := service.GetDatabaseMetrics(context.Background())
	if err != nil {
		t.Errorf("GetDatabaseMetrics failed: %v", err)
	}
	if dbMetrics["connections_active"] == nil {
		t.Error("expected connections_active in db metrics")
	}
}

func TestErrorAnalytics_CompleteWorkflow(t *testing.T) {
	mockErrorRepo := &mockErrorRepository{}

	service := NewErrorAnalyticsService(mockErrorRepo)

	// Test error metrics
	metrics, err := service.GetErrorMetrics(context.Background(), "hour")
	if err != nil {
		t.Errorf("GetErrorMetrics failed: %v", err)
	}
	if metrics["total_errors"] == nil {
		t.Error("expected total_errors in metrics")
	}

	// Test top errors
	topErrors, err := service.GetTopErrors(context.Background(), 10)
	if err != nil {
		t.Errorf("GetTopErrors failed: %v", err)
	}
	if len(topErrors) == 0 {
		t.Error("expected top errors")
	}

	// Test critical errors
	critical, err := service.GetCriticalErrors(context.Background())
	if err != nil {
		t.Errorf("GetCriticalErrors failed: %v", err)
	}
	if len(critical) == 0 {
		t.Error("expected critical errors")
	}
}

// Mock repositories for service tests

type mockEventRepository struct {
	events []models.Event
}

func (m *mockEventRepository) GetEventsByDateRange(ctx context.Context, startDate, endDate time.Time) ([]models.Event, error) {
	return m.events, nil
}

func (m *mockEventRepository) GetEventsByCohort(ctx context.Context, cohortDate time.Time) ([]models.Event, error) {
	return m.events, nil
}

func (m *mockEventRepository) GetEventsByUserAndDateRange(ctx context.Context, userID string, startDate, endDate time.Time) ([]models.Event, error) {
	var result []models.Event
	for _, e := range m.events {
		if e.UserID == userID {
			result = append(result, e)
		}
	}
	return result, nil
}

func (m *mockEventRepository) CreateEvent(ctx context.Context, event *models.Event) error {
	return nil
}

func (m *mockEventRepository) GetEvent(ctx context.Context, eventID string) (*models.Event, error) {
	return nil, nil
}

func (m *mockEventRepository) GetEvents(ctx context.Context, filters repository.EventFilters, limit, offset int) ([]models.Event, int64, error) {
	return m.events, int64(len(m.events)), nil
}

type mockActivityRepository struct {
	activities []models.Activity
}

func (m *mockActivityRepository) GetActivities(ctx context.Context, filters repository.ActivityFilters, limit, offset int) ([]models.Activity, int64, error) {
	return m.activities, int64(len(m.activities)), nil
}

func (m *mockActivityRepository) CreateActivity(ctx context.Context, activity *models.Activity) error {
	return nil
}

func (m *mockActivityRepository) DeleteActivity(ctx context.Context, activityID string) error {
	return nil
}

type mockUserRepository2 struct{}

func (m *mockUserRepository2) GetUser(ctx context.Context, userID string) (*models.User, error) {
	return nil, nil
}

func (m *mockUserRepository2) GetUsers(ctx context.Context, limit, offset int) ([]models.User, int64, error) {
	return nil, 0, nil
}

func (m *mockUserRepository2) GetUserStats(ctx context.Context) (map[string]interface{}, error) {
	return map[string]interface{}{"total_users": 0}, nil
}

type mockErrorRepository struct{}

func (m *mockErrorRepository) GetErrors(ctx context.Context, filters map[string]interface{}, limit, offset int) ([]map[string]interface{}, error) {
	return []map[string]interface{}{}, nil
}

func (m *mockErrorRepository) GetTopErrors(ctx context.Context, limit int) ([]map[string]interface{}, error) {
	return []map[string]interface{}{}, nil
}

func (m *mockErrorRepository) GetCriticalErrors(ctx context.Context) ([]map[string]interface{}, error) {
	return []map[string]interface{}{}, nil
}

// Stress test

func TestAnalytics_StressTest_ConcurrentAccess(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping stress test in short mode")
	}

	mockRepo := &mockEventRepository{
		events: generateTestEvents(10000),
	}

	service := NewEventAnalyticsService(mockRepo)

	// Simulate concurrent analytics requests
	done := make(chan bool)
	errors := make(chan error, 100)

	for i := 0; i < 100; i++ {
		go func() {
			_, err := service.GetTimeline(context.Background(), time.Now().AddDate(0, 0, -30), time.Now(), "day")
			if err != nil {
				errors <- err
			}
			done <- true
		}()
	}

	for i := 0; i < 100; i++ {
		<-done
	}

	close(errors)
	for err := range errors {
		if err != nil {
			t.Errorf("concurrent access error: %v", err)
		}
	}
}

func generateTestEvents(count int) []models.Event {
	events := make([]models.Event, count)
	for i := 0; i < count; i++ {
		events[i] = models.Event{
			ID:        string(rune(i)),
			Type:      "test_event",
			UserID:    "test_user",
			Timestamp: time.Now().Add(-time.Duration(i) * time.Second),
		}
	}
	return events
}
