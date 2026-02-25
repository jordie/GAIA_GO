package services

import (
	"context"
	"testing"
	"time"

	"architect-go/pkg/models"
)

// Tests
// Note: mockEventRepository is defined in analytics_integration_test.go

func TestEventAnalyticsService_GetTimeline(t *testing.T) {
	mockRepo := &mockEventRepository{
		events: []models.Event{
			{ID: "1", Type: "created", Timestamp: time.Now()},
			{ID: "2", Type: "updated", Timestamp: time.Now()},
			{ID: "3", Type: "created", Timestamp: time.Now()},
		},
	}

	service := NewEventAnalyticsService(mockRepo)
	timeline, err := service.GetTimeline(context.Background(), time.Now().AddDate(0, 0, -30), time.Now(), "day")

	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}

	if len(timeline) == 0 {
		t.Error("expected timeline data, got empty")
	}
}

func TestEventAnalyticsService_GetByType(t *testing.T) {
	mockRepo := &mockEventRepository{
		events: []models.Event{
			{ID: "1", Type: "created", Timestamp: time.Now()},
			{ID: "2", Type: "updated", Timestamp: time.Now()},
			{ID: "3", Type: "created", Timestamp: time.Now()},
		},
	}

	service := NewEventAnalyticsService(mockRepo)
	events, err := service.GetByType(context.Background(), time.Now().AddDate(0, 0, -30), time.Now(), 100)

	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}

	if len(events) == 0 {
		t.Error("expected events grouped by type")
	}
}

func TestEventAnalyticsService_GetByUser(t *testing.T) {
	mockRepo := &mockEventRepository{
		events: []models.Event{
			{ID: "1", UserID: "user1", Type: "created", Timestamp: time.Now()},
			{ID: "2", UserID: "user2", Type: "updated", Timestamp: time.Now()},
			{ID: "3", UserID: "user1", Type: "created", Timestamp: time.Now()},
		},
	}

	service := NewEventAnalyticsService(mockRepo)
	events, err := service.GetByUser(context.Background(), time.Now().AddDate(0, 0, -30), time.Now(), 100)

	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}

	if len(events) == 0 {
		t.Error("expected events grouped by user")
	}
}

func TestEventAnalyticsService_GetFunnel(t *testing.T) {
	mockRepo := &mockEventRepository{
		events: []models.Event{
			{ID: "1", Type: "step1", Timestamp: time.Now()},
			{ID: "2", Type: "step2", Timestamp: time.Now()},
			{ID: "3", Type: "step1", Timestamp: time.Now()},
		},
	}

	service := NewEventAnalyticsService(mockRepo)
	funnel, err := service.GetFunnel(context.Background(), "test_funnel", time.Now().AddDate(0, 0, -30), time.Now())

	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}

	if funnel == nil {
		t.Error("expected funnel data")
	}

	if funnel.Name != "test_funnel" {
		t.Errorf("expected funnel name 'test_funnel', got %s", funnel.Name)
	}
}

func TestEventAnalyticsService_GetUserJourney(t *testing.T) {
	mockRepo := &mockEventRepository{
		events: []models.Event{
			{ID: "1", UserID: "user1", Type: "login", Timestamp: time.Now()},
			{ID: "2", UserID: "user1", Type: "view", Timestamp: time.Now().Add(1 * time.Hour)},
			{ID: "3", UserID: "user1", Type: "create", Timestamp: time.Now().Add(2 * time.Hour)},
		},
	}

	service := NewEventAnalyticsService(mockRepo)
	journey, err := service.GetUserJourney(context.Background(), "user1", time.Now().AddDate(0, 0, -30), time.Now())

	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}

	if len(journey) != 3 {
		t.Errorf("expected 3 journey events, got %d", len(journey))
	}
}

func TestEventAnalyticsService_GetSessionAnalysis(t *testing.T) {
	mockRepo := &mockEventRepository{
		events: []models.Event{
			{ID: "1", UserID: "user1", Type: "session_start", Timestamp: time.Now()},
			{ID: "2", UserID: "user2", Type: "session_start", Timestamp: time.Now()},
			{ID: "3", UserID: "user1", Type: "session_end", Timestamp: time.Now().Add(1 * time.Hour)},
		},
	}

	service := NewEventAnalyticsService(mockRepo)
	metrics, err := service.GetSessionAnalysis(context.Background(), time.Now().AddDate(0, 0, -30), time.Now())

	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}

	if metrics == nil {
		t.Error("expected metrics")
	}

	if metrics.ActiveUsers == 0 {
		t.Error("expected active users > 0")
	}
}

func TestEventAnalyticsService_GetAnomalies(t *testing.T) {
	mockRepo := &mockEventRepository{
		events: []models.Event{
			{ID: "1", Type: "error", Timestamp: time.Now()},
			{ID: "2", Type: "error", Timestamp: time.Now()},
		},
	}

	service := NewEventAnalyticsService(mockRepo)
	anomalies, err := service.GetAnomalies(context.Background(), time.Now().AddDate(0, 0, -30), time.Now(), "error_rate")

	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}

	if len(anomalies) == 0 {
		t.Error("expected anomalies detected")
	}
}

func TestEventAnalyticsService_GetForecast(t *testing.T) {
	mockRepo := &mockEventRepository{
		events: []models.Event{
			{ID: "1", Type: "event", Timestamp: time.Now()},
			{ID: "2", Type: "event", Timestamp: time.Now()},
		},
	}

	service := NewEventAnalyticsService(mockRepo)
	forecast, err := service.GetForecast(context.Background(), time.Now().AddDate(0, 0, -30), time.Now(), 7)

	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}

	if len(forecast) != 7 {
		t.Errorf("expected 7 forecast periods, got %d", len(forecast))
	}
}

func TestEventAnalyticsService_GetTopActions(t *testing.T) {
	mockRepo := &mockEventRepository{
		events: []models.Event{
			{ID: "1", Type: "create", Timestamp: time.Now()},
			{ID: "2", Type: "update", Timestamp: time.Now()},
			{ID: "3", Type: "create", Timestamp: time.Now()},
		},
	}

	service := NewEventAnalyticsService(mockRepo)
	actions, err := service.GetTopActions(context.Background(), time.Now().AddDate(0, 0, -30), time.Now(), 10)

	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}

	if len(actions) == 0 {
		t.Error("expected top actions")
	}
}

func TestEventAnalyticsService_GetRetention(t *testing.T) {
	mockRepo := &mockEventRepository{
		events: []models.Event{
			{ID: "1", Type: "login", Timestamp: time.Now()},
			{ID: "2", Type: "login", Timestamp: time.Now().Add(24 * time.Hour)},
			{ID: "3", Type: "login", Timestamp: time.Now().Add(48 * time.Hour)},
		},
	}

	service := NewEventAnalyticsService(mockRepo)
	retention, err := service.GetRetention(context.Background(), time.Now().AddDate(0, 0, -30))

	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}

	if len(retention) == 0 {
		t.Error("expected retention data")
	}
}
