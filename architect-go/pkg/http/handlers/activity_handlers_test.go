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
	"architect-go/pkg/repository"
)

// mockActivityService implements ActivityService for testing
type mockActivityService struct {
	activities []models.Activity
}

func newMockActivityService() *mockActivityService {
	return &mockActivityService{
		activities: []models.Activity{},
	}
}

func (m *mockActivityService) LogActivity(ctx context.Context, userID, action, resourceType, resourceID string, metadata map[string]interface{}) error {
	activity := models.Activity{
		ID:           "act" + string(rune(len(m.activities)+1)),
		UserID:       userID,
		Action:       action,
		ResourceType: resourceType,
		ResourceID:   resourceID,
	}
	m.activities = append(m.activities, activity)
	return nil
}

func (m *mockActivityService) GetUserActivity(ctx context.Context, userID string, limit, offset int) ([]models.Activity, int64, error) {
	var result []models.Activity
	for _, a := range m.activities {
		if a.UserID == userID {
			result = append(result, a)
		}
	}
	total := int64(len(result))
	if offset < len(result) {
		end := offset + limit
		if end > len(result) {
			end = len(result)
		}
		result = result[offset:end]
	}
	return result, total, nil
}

func (m *mockActivityService) GetProjectActivity(ctx context.Context, resourceType, resourceID string, limit, offset int) ([]models.Activity, int64, error) {
	var result []models.Activity
	for _, a := range m.activities {
		if a.ResourceType == resourceType && a.ResourceID == resourceID {
			result = append(result, a)
		}
	}
	total := int64(len(result))
	return result, total, nil
}

func (m *mockActivityService) FilterActivity(ctx context.Context, filters repository.ActivityFilters, limit, offset int) ([]models.Activity, int64, error) {
	var result []models.Activity
	for _, a := range m.activities {
		if (filters.UserID == "" || a.UserID == filters.UserID) &&
			(filters.Action == "" || a.Action == filters.Action) {
			result = append(result, a)
		}
	}
	total := int64(len(result))
	return result, total, nil
}

func (m *mockActivityService) GetActivityStats(ctx context.Context, userID string) (map[string]int64, error) {
	stats := make(map[string]int64)
	for _, a := range m.activities {
		if a.UserID == userID {
			stats[a.Action]++
		}
	}
	return stats, nil
}

func (m *mockActivityService) GetRecentActivity(ctx context.Context, limit int) ([]models.Activity, error) {
	if len(m.activities) > limit {
		return m.activities[len(m.activities)-limit:], nil
	}
	return m.activities, nil
}

func (m *mockActivityService) DeleteActivity(ctx context.Context, activityID string) error {
	for i, a := range m.activities {
		if a.ID == activityID {
			m.activities = append(m.activities[:i], m.activities[i+1:]...)
			break
		}
	}
	return nil
}

func (m *mockActivityService) CleanupOldActivities(ctx context.Context, daysOld int) (int64, error) {
	return 0, nil
}

// Tests

func TestLogActivity_Success(t *testing.T) {
	mockSvc := newMockActivityService()
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewActivityHandlers(mockSvc, errHandler)

	body := map[string]interface{}{
		"user_id":       "user1",
		"action":        "project_created",
		"resource_type": "project",
		"resource_id":   "proj1",
	}
	bodyBytes, _ := json.Marshal(body)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("POST", "/api/activity", bytes.NewReader(bodyBytes))
	r.Header.Set("Content-Type", "application/json")

	handler.LogActivity(w, r)

	if w.Code != http.StatusCreated {
		t.Errorf("expected status 201, got %d", w.Code)
	}

	if len(mockSvc.activities) != 1 {
		t.Errorf("expected 1 activity, got %d", len(mockSvc.activities))
	}
}

func TestGetUserActivity_Success(t *testing.T) {
	mockSvc := newMockActivityService()
	mockSvc.activities = []models.Activity{
		{ID: "act1", UserID: "user1", Action: "create"},
		{ID: "act2", UserID: "user1", Action: "update"},
		{ID: "act3", UserID: "user2", Action: "create"},
	}
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewActivityHandlers(mockSvc, errHandler)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("GET", "/api/activity/user/user1", nil)
	r = setURLParam(r, "userID", "user1")

	handler.GetUserActivity(w, r)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)

	activities, ok := resp["activities"].([]interface{})
	if !ok || len(activities) != 2 {
		t.Errorf("expected 2 activities, got %v", resp)
	}
}

func TestGetProjectActivity_Success(t *testing.T) {
	mockSvc := newMockActivityService()
	mockSvc.activities = []models.Activity{
		{ID: "act1", ResourceType: "project", ResourceID: "proj1"},
		{ID: "act2", ResourceType: "project", ResourceID: "proj1"},
		{ID: "act3", ResourceType: "project", ResourceID: "proj2"},
	}
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewActivityHandlers(mockSvc, errHandler)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("GET", "/api/activity/resource/project/proj1", nil)
	// Set both params
	rctx := setURLParamMultiple(r, map[string]string{
		"resourceType": "project",
		"resourceID":   "proj1",
	})

	handler.GetProjectActivity(w, rctx)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)

	activities, ok := resp["activities"].([]interface{})
	if !ok || len(activities) != 2 {
		t.Errorf("expected 2 activities, got %v", resp)
	}
}

func TestFilterActivity_Success(t *testing.T) {
	mockSvc := newMockActivityService()
	mockSvc.activities = []models.Activity{
		{ID: "act1", UserID: "user1", Action: "create"},
		{ID: "act2", UserID: "user1", Action: "update"},
		{ID: "act3", UserID: "user2", Action: "create"},
	}
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewActivityHandlers(mockSvc, errHandler)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("GET", "/api/activity?user_id=user1&action=create", nil)

	handler.FilterActivity(w, r)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)

	activities, ok := resp["activities"].([]interface{})
	if !ok || len(activities) != 1 {
		t.Errorf("expected 1 activity, got %v", resp)
	}
}

func TestGetActivityStats_Success(t *testing.T) {
	mockSvc := newMockActivityService()
	mockSvc.activities = []models.Activity{
		{ID: "act1", UserID: "user1", Action: "create"},
		{ID: "act2", UserID: "user1", Action: "create"},
		{ID: "act3", UserID: "user1", Action: "update"},
	}
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewActivityHandlers(mockSvc, errHandler)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("GET", "/api/activity/stats/user1", nil)
	r = setURLParam(r, "userID", "user1")

	handler.GetActivityStats(w, r)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)

	_, ok := resp["stats"].(map[string]interface{})
	if !ok {
		t.Errorf("expected stats in response, got %v", resp)
	}
}

func TestGetRecentActivity_Success(t *testing.T) {
	mockSvc := newMockActivityService()
	mockSvc.activities = []models.Activity{
		{ID: "act1", UserID: "user1", Action: "create"},
		{ID: "act2", UserID: "user2", Action: "update"},
	}
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewActivityHandlers(mockSvc, errHandler)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("GET", "/api/activity/recent", nil)

	handler.GetRecentActivity(w, r)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}
}

func TestDeleteActivity_Success(t *testing.T) {
	mockSvc := newMockActivityService()
	mockSvc.activities = []models.Activity{
		{ID: "act1", UserID: "user1", Action: "create"},
	}
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewActivityHandlers(mockSvc, errHandler)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("DELETE", "/api/activity/act1", nil)
	r = setURLParam(r, "activityID", "act1")

	handler.DeleteActivity(w, r)

	if w.Code != http.StatusNoContent {
		t.Errorf("expected status 204, got %d", w.Code)
	}

	if len(mockSvc.activities) != 0 {
		t.Errorf("expected 0 activities after delete, got %d", len(mockSvc.activities))
	}
}

func TestActivityHandlers_WithDispatcher(t *testing.T) {
	mockSvc := newMockActivityService()
	errHandler := errors.NewErrorHandler(false, true)
	dispatcher := &mockEventDispatcher{}

	handler := NewActivityHandlersWithDispatcher(mockSvc, errHandler, dispatcher)

	body := map[string]interface{}{
		"user_id":       "user1",
		"action":        "project_created",
		"resource_type": "project",
		"resource_id":   "proj1",
	}
	bodyBytes, _ := json.Marshal(body)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("POST", "/api/activity", bytes.NewReader(bodyBytes))
	r.Header.Set("Content-Type", "application/json")

	handler.LogActivity(w, r)

	if w.Code != http.StatusCreated {
		t.Errorf("expected status 201, got %d", w.Code)
	}

	// Verify events were dispatched
	if len(dispatcher.dispatchedEvents) == 0 {
		t.Errorf("expected events to be dispatched")
	}
}

func TestLogActivity_MissingUserID(t *testing.T) {
	mockSvc := newMockActivityService()
	errHandler := errors.NewErrorHandler(false, true)

	handler := NewActivityHandlers(mockSvc, errHandler)

	body := map[string]interface{}{
		"action": "create",
	}
	bodyBytes, _ := json.Marshal(body)

	w := httptest.NewRecorder()
	r := httptest.NewRequest("POST", "/api/activity", bytes.NewReader(bodyBytes))
	r.Header.Set("Content-Type", "application/json")

	handler.LogActivity(w, r)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected status 400, got %d", w.Code)
	}
}
