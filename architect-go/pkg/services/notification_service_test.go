package services

import (
	"context"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"

	"architect-go/pkg/models"
)

// MockNotificationRepository mocks the NotificationRepository
type MockNotificationRepository struct {
	mock.Mock
}

func (m *MockNotificationRepository) Create(ctx context.Context, notification *models.Notification) error {
	args := m.Called(ctx, notification)
	return args.Error(0)
}

func (m *MockNotificationRepository) Get(ctx context.Context, id string) (*models.Notification, error) {
	args := m.Called(ctx, id)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*models.Notification), args.Error(1)
}

func (m *MockNotificationRepository) ListByUser(ctx context.Context, userID string, limit int, offset int) ([]*models.Notification, int64, error) {
	args := m.Called(ctx, userID, limit, offset)
	if args.Get(0) == nil {
		return nil, 0, args.Error(2)
	}
	return args.Get(0).([]*models.Notification), args.Get(1).(int64), args.Error(2)
}

func (m *MockNotificationRepository) ListUnread(ctx context.Context, userID string, limit int, offset int) ([]*models.Notification, int64, error) {
	args := m.Called(ctx, userID, limit, offset)
	if args.Get(0) == nil {
		return nil, 0, args.Error(2)
	}
	return args.Get(0).([]*models.Notification), args.Get(1).(int64), args.Error(2)
}

func (m *MockNotificationRepository) ListRecent(ctx context.Context, userID string, limit int) ([]*models.Notification, error) {
	args := m.Called(ctx, userID, limit)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]*models.Notification), args.Error(1)
}

func (m *MockNotificationRepository) Update(ctx context.Context, notification *models.Notification) error {
	args := m.Called(ctx, notification)
	return args.Error(0)
}

func (m *MockNotificationRepository) Delete(ctx context.Context, id string) error {
	args := m.Called(ctx, id)
	return args.Error(0)
}

func (m *MockNotificationRepository) MarkAsRead(ctx context.Context, id string) error {
	args := m.Called(ctx, id)
	return args.Error(0)
}

func (m *MockNotificationRepository) MarkAsUnread(ctx context.Context, id string) error {
	args := m.Called(ctx, id)
	return args.Error(0)
}

func (m *MockNotificationRepository) ListUnreadByUser(ctx context.Context, userID string, limit int, offset int) ([]*models.Notification, int64, error) {
	args := m.Called(ctx, userID, limit, offset)
	if args.Get(0) == nil {
		return nil, 0, args.Error(2)
	}
	return args.Get(0).([]*models.Notification), args.Get(1).(int64), args.Error(2)
}

func (m *MockNotificationRepository) GetByProject(ctx context.Context, projectID string, limit int, offset int) ([]*models.Notification, int64, error) {
	args := m.Called(ctx, projectID, limit, offset)
	if args.Get(0) == nil {
		return nil, 0, args.Error(2)
	}
	return args.Get(0).([]*models.Notification), args.Get(1).(int64), args.Error(2)
}

func (m *MockNotificationRepository) GetByType(ctx context.Context, notificationType string, limit int, offset int) ([]*models.Notification, int64, error) {
	args := m.Called(ctx, notificationType, limit, offset)
	if args.Get(0) == nil {
		return nil, 0, args.Error(2)
	}
	return args.Get(0).([]*models.Notification), args.Get(1).(int64), args.Error(2)
}

func (m *MockNotificationRepository) Search(ctx context.Context, query string, limit int, offset int) ([]*models.Notification, int64, error) {
	args := m.Called(ctx, query, limit, offset)
	if args.Get(0) == nil {
		return nil, 0, args.Error(2)
	}
	return args.Get(0).([]*models.Notification), args.Get(1).(int64), args.Error(2)
}

func (m *MockNotificationRepository) CreateDelivery(ctx context.Context, delivery map[string]interface{}) error {
	args := m.Called(ctx, delivery)
	return args.Error(0)
}

func (m *MockNotificationRepository) GetDeliveryHistory(ctx context.Context, notificationID string, limit int, offset int) ([]map[string]interface{}, int64, error) {
	args := m.Called(ctx, notificationID, limit, offset)
	if args.Get(0) == nil {
		return nil, 0, args.Error(2)
	}
	return args.Get(0).([]map[string]interface{}), args.Get(1).(int64), args.Error(2)
}

// TestNotificationService_CreateNotification tests notification creation
func TestNotificationService_CreateNotification(t *testing.T) {
	mockRepo := new(MockNotificationRepository)
	ctx := context.Background()

	mockRepo.On("Create", ctx, mock.MatchedBy(func(n *models.Notification) bool {
		return n.Title == "Test" && n.Type == "alert"
	})).Return(nil)

	service := NewNotificationService(mockRepo)
	req := &CreateNotificationRequest{
		Recipients:       []string{"user-1"},
		Title:            "Test",
		Message:          "Test message",
		NotificationType: "alert",
		Channels:         []string{"email"},
		Priority:         "high",
	}

	result, err := service.CreateNotification(ctx, req)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Equal(t, "Test", result.Title)
	mockRepo.AssertCalled(t, "Create", ctx, mock.AnythingOfType("*models.Notification"))
}

// TestNotificationService_MarkAsRead tests marking notifications as read
func TestNotificationService_MarkAsRead(t *testing.T) {
	mockRepo := new(MockNotificationRepository)
	ctx := context.Background()

	mockRepo.On("MarkAsRead", ctx, "notif-1").Return(nil)

	service := NewNotificationService(mockRepo)
	err := service.MarkAsRead(ctx, "notif-1")

	assert.NoError(t, err)
	mockRepo.AssertCalled(t, "MarkAsRead", ctx, "notif-1")
}

// TestNotificationService_ListUnreadNotifications tests unread notification listing
func TestNotificationService_ListUnreadNotifications(t *testing.T) {
	mockRepo := new(MockNotificationRepository)
	ctx := context.Background()

	notifications := []*models.Notification{
		{ID: "notif-1"},
		{ID: "notif-2"},
	}

	mockRepo.On("ListUnreadByUser", ctx, "user-1", 10, 0).Return(notifications, int64(2), nil)

	service := NewNotificationService(mockRepo)
	results, total, err := service.ListUnreadNotifications(ctx, "user-1", 10, 0)

	assert.NoError(t, err)
	assert.Equal(t, int64(2), total)
	assert.Equal(t, 2, len(results))
	mockRepo.AssertCalled(t, "ListUnreadByUser", ctx, "user-1", 10, 0)
}

// TestNotificationService_SendNotification tests sending notifications
func TestNotificationService_SendNotification(t *testing.T) {
	mockRepo := new(MockNotificationRepository)
	ctx := context.Background()

	sourceNotif := &models.Notification{
		ID:      "notif-1",
		Title:   "Alert",
		Message: "Alert message",
		Type:    "alert",
	}

	mockRepo.On("Get", ctx, "notif-1").Return(sourceNotif, nil)
	mockRepo.On("Create", ctx, mock.MatchedBy(func(n *models.Notification) bool {
		return n.Status == "sent"
	})).Return(nil)

	service := NewNotificationService(mockRepo)
	req := &SendNotificationRequest{
		NotificationID: "notif-1",
		UserIDs:        []string{"user-1"},
		Channels:       []string{"push"},
	}

	err := service.SendNotification(ctx, req)

	assert.NoError(t, err)
	mockRepo.AssertCalled(t, "Get", ctx, "notif-1")
	mockRepo.AssertCalled(t, "Create", ctx, mock.AnythingOfType("*models.Notification"))
}

// TestNotificationService_DismissNotification tests dismissing notifications
func TestNotificationService_DismissNotification(t *testing.T) {
	mockRepo := new(MockNotificationRepository)
	ctx := context.Background()

	notification := &models.Notification{
		ID:     "notif-1",
		Status: "pending",
	}

	mockRepo.On("Get", ctx, "notif-1").Return(notification, nil)
	mockRepo.On("Update", ctx, mock.MatchedBy(func(n *models.Notification) bool {
		return n.Status == "dismissed"
	})).Return(nil)

	service := NewNotificationService(mockRepo)
	err := service.DismissNotification(ctx, "notif-1")

	assert.NoError(t, err)
	mockRepo.AssertCalled(t, "Get", ctx, "notif-1")
	mockRepo.AssertCalled(t, "Update", ctx, mock.AnythingOfType("*models.Notification"))
}

// TestNotificationService_SendBulkNotifications tests bulk notification sending
func TestNotificationService_SendBulkNotifications(t *testing.T) {
	mockRepo := new(MockNotificationRepository)
	ctx := context.Background()

	notification := &models.Notification{
		ID:      "notif-1",
		Title:   "Bulk Alert",
		Message: "Alert message",
		Type:    "alert",
	}

	mockRepo.On("Get", ctx, "notif-1").Return(notification, nil)
	mockRepo.On("Create", ctx, mock.AnythingOfType("*models.Notification")).Return(nil)

	service := NewNotificationService(mockRepo)
	userIDs := []string{"user-1", "user-2", "user-3"}
	err := service.SendBulkNotifications(ctx, "notif-1", userIDs)

	assert.NoError(t, err)
	mockRepo.AssertCalled(t, "Get", ctx, "notif-1")
}
