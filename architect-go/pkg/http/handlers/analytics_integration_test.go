package handlers

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"architect-go/pkg/errors"
	"architect-go/pkg/models"
	"architect-go/pkg/repository"
	"architect-go/pkg/services"
)

// Integration Tests: Service + Handler + Repository Integration

func TestAnalytics_EventTimelineIntegration(t *testing.T) {
	// Setup
	mockEventRepo := &mockEventRepository{
		events: []models.Event{
			{ID: "1", Type: "created", Timestamp: time.Now(), UserID: "user1"},
			{ID: "2", Type: "updated", Timestamp: time.Now(), UserID: "user1"},
		},
	}

	eventService := services.NewEventAnalyticsService(mockEventRepo)
	errHandler := errors.NewErrorHandler(false, true)
	handler := &AnalyticsHandlers{
		eventAnalytics: eventService,
		errorHandler:   errHandler,
	}

	// Execute
	w := httptest.NewRecorder()
	r := httptest.NewRequest("GET", "/api/analytics/events/timeline?period=day&interval=hour", nil)

	handler.GetEventTimeline(w, r)

	// Verify
	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)

	if _, ok := resp["timeline"]; !ok {
		t.Error("expected timeline in response")
	}
}

func TestAnalytics_PresenceHeatmapIntegration(t *testing.T) {
	mockPresenceRepo := &mockPresenceRepository{
		presences: []models.Presence{
			{ID: "1", UserID: "user1", Status: "online", Timestamp: time.Now()},
			{ID: "2", UserID: "user2", Status: "away", Timestamp: time.Now()},
		},
	}

	presenceService := services.NewPresenceAnalyticsService(mockPresenceRepo)
	errHandler := errors.NewErrorHandler(false, true)
	handler := &AnalyticsHandlers{
		presenceAnalytics: presenceService,
		errorHandler:      errHandler,
	}

	w := httptest.NewRecorder()
	r := httptest.NewRequest("GET", "/api/analytics/presence/heatmap?days=30", nil)

	handler.GetPresenceHeatmap(w, r)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}
}

func TestAnalytics_ActivityTrendsIntegration(t *testing.T) {
	mockActivityRepo := &mockActivityRepository{
		activities: []models.Activity{
			{ID: "1", UserID: "user1", Action: "create", Timestamp: time.Now()},
			{ID: "2", UserID: "user2", Action: "update", Timestamp: time.Now()},
		},
	}

	activityService := services.NewActivityAnalyticsService(mockActivityRepo)
	errHandler := errors.NewErrorHandler(false, true)
	handler := &AnalyticsHandlers{
		activityAnalytics: activityService,
		errorHandler:      errHandler,
	}

	w := httptest.NewRecorder()
	r := httptest.NewRequest("GET", "/api/analytics/activity/trends?period=day&action=create", nil)

	handler.GetActivityTrends(w, r)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}
}

// Mock Repositories for Integration Tests

type mockPresenceRepository struct {
	presences []models.Presence
}

func (m *mockPresenceRepository) GetPresenceHistory(ctx context.Context, userID string, limit, offset int) ([]models.Presence, int64, error) {
	return m.presences, int64(len(m.presences)), nil
}

func (m *mockPresenceRepository) UpdatePresence(ctx context.Context, userID, status string, metadata map[string]interface{}) error {
	return nil
}

func (m *mockPresenceRepository) GetPresence(ctx context.Context, userID string) (*models.Presence, error) {
	return nil, nil
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

type mockUserRepository struct{}

func (m *mockUserRepository) GetUser(ctx context.Context, userID string) (*models.User, error) {
	return nil, nil
}

func (m *mockUserRepository) GetUsers(ctx context.Context, limit, offset int) ([]models.User, int64, error) {
	return nil, 0, nil
}

func (m *mockUserRepository) GetUserStats(ctx context.Context) (map[string]interface{}, error) {
	return map[string]interface{}{"total_users": 0}, nil
}

// E2E Tests

func TestAnalytics_E2E_EventAnalytics(t *testing.T) {
	mockEventRepo := &mockEventRepository{
		events: []models.Event{
			{ID: "1", Type: "created", Timestamp: time.Now(), UserID: "user1"},
			{ID: "2", Type: "updated", Timestamp: time.Now(), UserID: "user2"},
			{ID: "3", Type: "deleted", Timestamp: time.Now(), UserID: "user1"},
		},
	}

	eventService := services.NewEventAnalyticsService(mockEventRepo)
	errHandler := errors.NewErrorHandler(false, true)
	handler := &AnalyticsHandlers{
		eventAnalytics: eventService,
		errorHandler:   errHandler,
	}

	tests := []struct {
		endpoint string
		method   string
		name     string
	}{
		{"/api/analytics/events/timeline", "GET", "timeline"},
		{"/api/analytics/events/trends", "GET", "trends"},
		{"/api/analytics/events/by-type", "GET", "by-type"},
		{"/api/analytics/events/funnel", "GET", "funnel"},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			w := httptest.NewRecorder()
			r := httptest.NewRequest(test.method, test.endpoint, nil)

			if test.name == "timeline" {
				handler.GetEventTimeline(w, r)
			} else if test.name == "trends" {
				handler.GetEventTrends(w, r)
			} else if test.name == "by-type" {
				handler.GetEventsByType(w, r)
			} else if test.name == "funnel" {
				handler.GetFunnelAnalysis(w, r)
			}

			if w.Code != http.StatusOK {
				t.Errorf("expected status 200, got %d", w.Code)
			}
		})
	}
}

func TestAnalytics_E2E_UserAnalytics(t *testing.T) {
	mockUserRepo := &mockUserRepository{}

	userService := services.NewUserAnalyticsService(mockUserRepo)
	errHandler := errors.NewErrorHandler(false, true)
	handler := &AnalyticsHandlers{
		userAnalytics: userService,
		errorHandler:  errHandler,
	}

	tests := []struct {
		endpoint string
		name     string
	}{
		{"/api/analytics/users/growth?period=month", "growth"},
		{"/api/analytics/users/retention", "retention"},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			w := httptest.NewRecorder()
			r := httptest.NewRequest("GET", test.endpoint, nil)

			if test.name == "growth" {
				handler.GetUserGrowth(w, r)
			} else if test.name == "retention" {
				handler.GetUserRetention(w, r)
			}

			if w.Code != http.StatusOK {
				t.Errorf("expected status 200, got %d", w.Code)
			}
		})
	}
}

// Load Tests

func BenchmarkAnalytics_EventTimeline(b *testing.B) {
	mockEventRepo := &mockEventRepository{
		events: generateMockEvents(1000),
	}

	eventService := services.NewEventAnalyticsService(mockEventRepo)
	errHandler := errors.NewErrorHandler(false, true)
	handler := &AnalyticsHandlers{
		eventAnalytics: eventService,
		errorHandler:   errHandler,
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		w := httptest.NewRecorder()
		r := httptest.NewRequest("GET", "/api/analytics/events/timeline", nil)
		handler.GetEventTimeline(w, r)
	}
}

func BenchmarkAnalytics_PresenceHeatmap(b *testing.B) {
	mockPresenceRepo := &mockPresenceRepository{
		presences: generateMockPresences(1000),
	}

	presenceService := services.NewPresenceAnalyticsService(mockPresenceRepo)
	errHandler := errors.NewErrorHandler(false, true)
	handler := &AnalyticsHandlers{
		presenceAnalytics: presenceService,
		errorHandler:      errHandler,
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		w := httptest.NewRecorder()
		r := httptest.NewRequest("GET", "/api/analytics/presence/heatmap", nil)
		handler.GetPresenceHeatmap(w, r)
	}
}

func BenchmarkAnalytics_Concurrent(b *testing.B) {
	mockEventRepo := &mockEventRepository{
		events: generateMockEvents(10000),
	}

	eventService := services.NewEventAnalyticsService(mockEventRepo)
	errHandler := errors.NewErrorHandler(false, true)
	handler := &AnalyticsHandlers{
		eventAnalytics: eventService,
		errorHandler:   errHandler,
	}

	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			w := httptest.NewRecorder()
			r := httptest.NewRequest("GET", "/api/analytics/events/trends", nil)
			handler.GetEventTrends(w, r)
		}
	})
}

func TestAnalytics_LoadTest_RPS(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping load test in short mode")
	}

	mockEventRepo := &mockEventRepository{
		events: generateMockEvents(10000),
	}

	eventService := services.NewEventAnalyticsService(mockEventRepo)
	errHandler := errors.NewErrorHandler(false, true)
	handler := &AnalyticsHandlers{
		eventAnalytics: eventService,
		errorHandler:   errHandler,
	}

	// Simulate 100 concurrent requests
	done := make(chan bool)
	start := time.Now()
	requestCount := 100

	for i := 0; i < requestCount; i++ {
		go func() {
			w := httptest.NewRecorder()
			r := httptest.NewRequest("GET", "/api/analytics/events/timeline", nil)
			handler.GetEventTimeline(w, r)
			done <- true
		}()
	}

	for i := 0; i < requestCount; i++ {
		<-done
	}

	elapsed := time.Since(start)
	rps := float64(requestCount) / elapsed.Seconds()

	t.Logf("Processed %d requests in %v (%.2f RPS)", requestCount, elapsed, rps)

	if rps < 100 {
		t.Logf("Warning: RPS is %.2f, expected at least 100", rps)
	}
}

// Helper functions

func generateMockEvents(count int) []models.Event {
	events := make([]models.Event, count)
	for i := 0; i < count; i++ {
		events[i] = models.Event{
			ID:        string(rune(i)),
			Type:      "test",
			Timestamp: time.Now(),
			UserID:    "user1",
		}
	}
	return events
}

func generateMockPresences(count int) []models.Presence {
	presences := make([]models.Presence, count)
	for i := 0; i < count; i++ {
		presences[i] = models.Presence{
			ID:        string(rune(i)),
			UserID:    "user1",
			Status:    "online",
			Timestamp: time.Now(),
		}
	}
	return presences
}
