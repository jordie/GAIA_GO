package services

import (
	"context"
	"testing"
	"time"

	"architect-go/pkg/cache"
	"architect-go/pkg/events"
	"architect-go/pkg/models"
	"architect-go/pkg/repository"
)

// mockPresenceRepository for testing
type mockPresenceRepository struct {
	presences map[string]*models.Presence
	history   []models.Presence
}

func newMockPresenceRepository() *mockPresenceRepository {
	return &mockPresenceRepository{
		presences: make(map[string]*models.Presence),
		history:   []models.Presence{},
	}
}

func (m *mockPresenceRepository) CreateOrUpdatePresence(ctx context.Context, presence *models.Presence) error {
	m.presences[presence.UserID] = presence
	return nil
}

func (m *mockPresenceRepository) GetPresence(ctx context.Context, userID string) (*models.Presence, error) {
	return m.presences[userID], nil
}

func (m *mockPresenceRepository) GetOnlineUsers(ctx context.Context) ([]string, error) {
	var users []string
	for _, p := range m.presences {
		if p.Status == "online" {
			users = append(users, p.UserID)
		}
	}
	return users, nil
}

func (m *mockPresenceRepository) GetPresenceByStatus(ctx context.Context, status string) ([]string, error) {
	var users []string
	for _, p := range m.presences {
		if p.Status == status {
			users = append(users, p.UserID)
		}
	}
	return users, nil
}

func (m *mockPresenceRepository) UpdatePresenceStatus(ctx context.Context, userID, status string) error {
	if p, ok := m.presences[userID]; ok {
		p.Status = status
	}
	return nil
}

func (m *mockPresenceRepository) UpdateLastSeen(ctx context.Context, userID string) error {
	if p, ok := m.presences[userID]; ok {
		p.LastSeenAt = time.Now()
	}
	return nil
}

func (m *mockPresenceRepository) GetPresenceHistory(ctx context.Context, userID string, limit, offset int) ([]models.Presence, error) {
	return m.history, nil
}

func (m *mockPresenceRepository) GetPresenceHistoryCount(ctx context.Context, userID string) (int64, error) {
	return int64(len(m.history)), nil
}

func (m *mockPresenceRepository) SetOffline(ctx context.Context, userID string) error {
	return m.UpdatePresenceStatus(ctx, userID, "offline")
}

func (m *mockPresenceRepository) DeletePresence(ctx context.Context, userID string) error {
	delete(m.presences, userID)
	return nil
}

func (m *mockPresenceRepository) GetStalePresences(ctx context.Context, durationMinutes int) ([]string, error) {
	return []string{}, nil
}

// mockActivityRepository for testing
type mockActivityRepository struct{}

func (m *mockActivityRepository) LogActivity(ctx context.Context, activity *models.Activity) error {
	return nil
}

func (m *mockActivityRepository) GetUserActivity(ctx context.Context, userID string, limit, offset int) ([]models.Activity, error) {
	return []models.Activity{}, nil
}

func (m *mockActivityRepository) GetUserActivityCount(ctx context.Context, userID string) (int64, error) {
	return 0, nil
}

func (m *mockActivityRepository) GetProjectActivity(ctx context.Context, resourceType, resourceID string, limit, offset int) ([]models.Activity, error) {
	return []models.Activity{}, nil
}

func (m *mockActivityRepository) GetProjectActivityCount(ctx context.Context, resourceType, resourceID string) (int64, error) {
	return 0, nil
}

func (m *mockActivityRepository) FilterActivity(ctx context.Context, filters repository.ActivityFilters, limit, offset int) ([]models.Activity, error) {
	return []models.Activity{}, nil
}

func (m *mockActivityRepository) FilterActivityCount(ctx context.Context, filters repository.ActivityFilters) (int64, error) {
	return 0, nil
}

func (m *mockActivityRepository) GetActivityStats(ctx context.Context, userID string) (map[string]int64, error) {
	return make(map[string]int64), nil
}

func (m *mockActivityRepository) GetRecentActivity(ctx context.Context, limit int) ([]models.Activity, error) {
	return []models.Activity{}, nil
}

func (m *mockActivityRepository) DeleteActivity(ctx context.Context, activityID string) error {
	return nil
}

func (m *mockActivityRepository) GetActivity(ctx context.Context, activityID string) (*models.Activity, error) {
	return nil, nil
}

func (m *mockActivityRepository) DeleteOldActivities(ctx context.Context, daysOld int) (int64, error) {
	return 0, nil
}

// mockDispatcher for testing
type mockDispatcher struct {
	dispatchedEvents []events.Event
}

func newMockDispatcher() *mockDispatcher {
	return &mockDispatcher{
		dispatchedEvents: []events.Event{},
	}
}

func (m *mockDispatcher) Dispatch(event events.Event) {
	m.dispatchedEvents = append(m.dispatchedEvents, event)
}

// TestUpdatePresenceAndCache verifies presence update and caching
func TestUpdatePresenceAndCache(t *testing.T) {
	ctx := context.Background()
	presenceRepo := newMockPresenceRepository()
	activityRepo := &mockActivityRepository{}
	cm := cache.NewCacheManager()
	dispatcher := newMockDispatcher()

	service := NewPresenceServiceWithCache(presenceRepo, activityRepo, cm, dispatcher)

	// Update presence
	err := service.UpdatePresence(ctx, "user1", "online", map[string]interface{}{"device": "web"})
	if err != nil {
		t.Fatalf("UpdatePresence failed: %v", err)
	}

	// Verify presence was created
	presence, err := service.GetPresence(ctx, "user1")
	if err != nil {
		t.Fatalf("GetPresence failed: %v", err)
	}

	if presence == nil {
		t.Fatal("Expected presence to exist")
	}

	if presence.Status != "online" {
		t.Errorf("Expected status 'online', got '%s'", presence.Status)
	}

	// Verify cache was used
	presence2, err := service.GetPresence(ctx, "user1")
	if err != nil {
		t.Fatalf("GetPresence (cached) failed: %v", err)
	}

	if presence2 == nil {
		t.Fatal("Expected cached presence to exist")
	}

	if presence2.Status != "online" {
		t.Errorf("Expected cached status 'online', got '%s'", presence2.Status)
	}
}

// TestPresenceHistoryRetrieval verifies presence history retrieval with pagination
func TestPresenceHistoryRetrieval(t *testing.T) {
	ctx := context.Background()
	presenceRepo := newMockPresenceRepository()
	activityRepo := &mockActivityRepository{}
	cm := cache.NewCacheManager()
	dispatcher := newMockDispatcher()

	service := NewPresenceServiceWithCache(presenceRepo, activityRepo, cm, dispatcher)

	// Add some history
	for i := 0; i < 5; i++ {
		presenceRepo.history = append(presenceRepo.history, models.Presence{
			ID:     "presence-" + string(rune(i)),
			UserID: "user1",
		})
	}

	// Get history
	history, count, err := service.GetPresenceHistory(ctx, "user1", 2, 0)
	if err != nil {
		t.Fatalf("GetPresenceHistory failed: %v", err)
	}

	if count != 5 {
		t.Errorf("Expected count 5, got %d", count)
	}

	if len(history) != 5 {
		t.Errorf("Expected 5 history items, got %d", len(history))
	}
}

// TestBroadcastOnStatusChange verifies broadcast event on status change
func TestBroadcastOnStatusChange(t *testing.T) {
	ctx := context.Background()
	presenceRepo := newMockPresenceRepository()
	activityRepo := &mockActivityRepository{}
	cm := cache.NewCacheManager()
	dispatcher := newMockDispatcher()

	service := NewPresenceServiceWithCache(presenceRepo, activityRepo, cm, dispatcher)

	// Create initial presence
	_ = service.UpdatePresence(ctx, "user1", "online", nil)

	dispatchedCount := len(dispatcher.dispatchedEvents)

	// Change status
	_ = service.UpdatePresence(ctx, "user1", "away", nil)

	// Verify event was dispatched
	if len(dispatcher.dispatchedEvents) != dispatchedCount+1 {
		t.Errorf("Expected 1 new dispatched event, got %d new events", len(dispatcher.dispatchedEvents)-dispatchedCount)
	}

	// Verify event details
	lastEvent := dispatcher.dispatchedEvents[len(dispatcher.dispatchedEvents)-1]
	if lastEvent.Type != "presence.changed" {
		t.Errorf("Expected event type 'presence.changed', got '%s'", lastEvent.Type)
	}

	if data, ok := lastEvent.Data.(map[string]interface{}); ok {
		if userID, ok := data["user_id"].(string); !ok || userID != "user1" {
			t.Errorf("Expected user_id 'user1', got %v", data["user_id"])
		}
	} else {
		t.Fatal("Expected event data to be map[string]interface{}")
	}
}

// TestSetOffline verifies offline status setting
func TestSetOffline(t *testing.T) {
	ctx := context.Background()
	presenceRepo := newMockPresenceRepository()
	activityRepo := &mockActivityRepository{}

	service := NewPresenceService(presenceRepo, activityRepo)

	// Create initial presence
	_ = service.UpdatePresence(ctx, "user1", "online", nil)

	// Set offline
	err := service.SetOffline(ctx, "user1")
	if err != nil {
		t.Fatalf("SetOffline failed: %v", err)
	}

	// Verify status
	presence, _ := service.GetPresence(ctx, "user1")
	if presence == nil || presence.Status != "offline" {
		t.Errorf("Expected status 'offline', got %v", presence)
	}
}
