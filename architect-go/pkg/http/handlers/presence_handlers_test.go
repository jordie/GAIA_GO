package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"architect-go/pkg/errors"
	"architect-go/pkg/models"
)

// mockPresenceService implements PresenceService for testing
type mockPresenceService struct {
	onlineUsers []string
	presence    map[string]*models.Presence
}

func newMockPresenceService() *mockPresenceService {
	return &mockPresenceService{
		presence: make(map[string]*models.Presence),
	}
}

func (m *mockPresenceService) UpdatePresence(ctx context.Context, userID, status string, metadata map[string]interface{}) error {
	if userID == "" {
		return errors.ValidationErrorf("MISSING_USER_ID", "User ID is required")
	}
	m.presence[userID] = &models.Presence{
		ID:     userID,
		UserID: userID,
		Status: status,
	}
	return nil
}

func (m *mockPresenceService) GetPresence(ctx context.Context, userID string) (*models.Presence, error) {
	if p, ok := m.presence[userID]; ok {
		return p, nil
	}
	return nil, errors.NotFoundErrorf("PRESENCE_NOT_FOUND", "Presence not found")
}

func (m *mockPresenceService) GetOnlineUsers(ctx context.Context) ([]string, error) {
	return m.onlineUsers, nil
}

func (m *mockPresenceService) GetPresenceByStatus(ctx context.Context, status string) ([]string, error) {
	var users []string
	for userID, p := range m.presence {
		if p.Status == status {
			users = append(users, userID)
		}
	}
	return users, nil
}

func (m *mockPresenceService) GetPresenceHistory(ctx context.Context, userID string, limit, offset int) ([]models.Presence, int64, error) {
	return []models.Presence{}, 0, nil
}

func (m *mockPresenceService) SetOffline(ctx context.Context, userID string) error {
	if p, ok := m.presence[userID]; ok {
		p.Status = "offline"
	}
	return nil
}

func (m *mockPresenceService) BroadcastPresenceChange(ctx context.Context, userID, oldStatus, newStatus string) error {
	return nil
}

func (m *mockPresenceService) HandleUserLogout(ctx context.Context, userID string) error {
	return nil
}

func (m *mockPresenceService) CleanupStalePresences(ctx context.Context, durationMinutes int) (int64, error) {
	return 0, nil
}

// Tests

func TestListOnlineUsers_Success(t *testing.T) {
	mockSvc := newMockPresenceService()
	mockSvc.onlineUsers = []string{"user1", "user2", "user3"}
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewPresenceHandlers(mockSvc, errHandler)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("GET", "/api/presence/online", nil)

	handler.ListOnlineUsers(w, r)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)

	users, ok := resp["users"].([]interface{})
	if !ok || len(users) != 3 {
		t.Errorf("expected 3 users, got %v", resp)
	}
}

func TestGetPresenceByStatus_Success(t *testing.T) {
	mockSvc := newMockPresenceService()
	mockSvc.presence["user1"] = &models.Presence{ID: "user1", UserID: "user1", Status: "online"}
	mockSvc.presence["user2"] = &models.Presence{ID: "user2", UserID: "user2", Status: "away"}
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewPresenceHandlers(mockSvc, errHandler)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("GET", "/api/presence?status=online", nil)

	handler.GetPresenceByStatus(w, r)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)

	if status, ok := resp["status"].(string); !ok || status != "online" {
		t.Errorf("expected status 'online', got %v", resp["status"])
	}
}

func TestGetUserPresence_Success(t *testing.T) {
	mockSvc := newMockPresenceService()
	mockSvc.presence["user1"] = &models.Presence{ID: "user1", UserID: "user1", Status: "online"}
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewPresenceHandlers(mockSvc, errHandler)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("GET", "/api/presence/user1", nil)
	r = setURLParam(r, "userID", "user1")

	handler.GetUserPresence(w, r)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var presence models.Presence
	json.Unmarshal(w.Body.Bytes(), &presence)

	if presence.UserID != "user1" {
		t.Errorf("expected user1, got %s", presence.UserID)
	}
}

func TestUpdatePresence_Success(t *testing.T) {
	mockSvc := newMockPresenceService()
	mockSvc.presence["user1"] = &models.Presence{ID: "user1", UserID: "user1", Status: "online"}
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewPresenceHandlers(mockSvc, errHandler)

	body := map[string]interface{}{
		"user_id": "user1",
		"status":  "away",
	}
	bodyBytes, _ := json.Marshal(body)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("POST", "/api/presence", bytes.NewReader(bodyBytes))
	r.Header.Set("Content-Type", "application/json")

	handler.UpdatePresence(w, r)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	presence := mockSvc.presence["user1"]
	if presence.Status != "away" {
		t.Errorf("expected status 'away', got %s", presence.Status)
	}
}

func TestSetUserOffline_Success(t *testing.T) {
	mockSvc := newMockPresenceService()
	mockSvc.presence["user1"] = &models.Presence{ID: "user1", UserID: "user1", Status: "online"}
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewPresenceHandlers(mockSvc, errHandler)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("DELETE", "/api/presence/user1", nil)
	r = setURLParam(r, "userID", "user1")

	handler.SetUserOffline(w, r)

	if w.Code != http.StatusNoContent {
		t.Errorf("expected status 204, got %d", w.Code)
	}

	presence := mockSvc.presence["user1"]
	if presence.Status != "offline" {
		t.Errorf("expected status 'offline', got %s", presence.Status)
	}
}

func TestGetPresenceHistory_Success(t *testing.T) {
	mockSvc := newMockPresenceService()
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewPresenceHandlers(mockSvc, errHandler)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("GET", "/api/presence/user1/history", nil)
	r = setURLParam(r, "userID", "user1")

	handler.GetPresenceHistory(w, r)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}
}

func TestUpdatePresence_InvalidStatus(t *testing.T) {
	mockSvc := newMockPresenceService()
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewPresenceHandlers(mockSvc, errHandler)

	body := map[string]interface{}{
		"user_id": "user1",
		"status":  "invalid_status",
	}
	bodyBytes, _ := json.Marshal(body)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("POST", "/api/presence", bytes.NewReader(bodyBytes))
	r.Header.Set("Content-Type", "application/json")

	handler.UpdatePresence(w, r)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected status 400, got %d", w.Code)
	}
}

func TestPresenceHandlers_WithDispatcher(t *testing.T) {
	mockSvc := newMockPresenceService()
	mockSvc.presence["user1"] = &models.Presence{ID: "user1", UserID: "user1", Status: "online"}
	errHandler := errors.NewErrorHandler(false, true)
	dispatcher := &mockEventDispatcher{}

	handler := NewPresenceHandlersWithDispatcher(mockSvc, errHandler, dispatcher)

	body := map[string]interface{}{
		"user_id": "user1",
		"status":  "away",
	}
	bodyBytes, _ := json.Marshal(body)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("POST", "/api/presence", bytes.NewReader(bodyBytes))
	r.Header.Set("Content-Type", "application/json")

	handler.UpdatePresence(w, r)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	// Verify events were dispatched
	if len(dispatcher.dispatchedEvents) == 0 {
		t.Errorf("expected events to be dispatched")
	}
}
