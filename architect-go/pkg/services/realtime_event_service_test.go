package services

import (
	"context"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
)

// MockRealTimeRepository mocks the RealTimeRepository
type MockRealTimeRepository struct {
	mock.Mock
}

func (m *MockRealTimeRepository) CreateSubscription(ctx context.Context, userID string, channel string) error {
	args := m.Called(ctx, userID, channel)
	return args.Error(0)
}

func (m *MockRealTimeRepository) RemoveSubscription(ctx context.Context, userID string, channel string) error {
	args := m.Called(ctx, userID, channel)
	return args.Error(0)
}

func (m *MockRealTimeRepository) GetUserSubscriptions(ctx context.Context, userID string) ([]string, error) {
	args := m.Called(ctx, userID)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]string), args.Error(1)
}

func (m *MockRealTimeRepository) GetChannelSubscribers(ctx context.Context, channel string) ([]string, error) {
	args := m.Called(ctx, channel)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]string), args.Error(1)
}

func (m *MockRealTimeRepository) StoreMessage(ctx context.Context, message map[string]interface{}) error {
	args := m.Called(ctx, message)
	return args.Error(0)
}

func (m *MockRealTimeRepository) GetPendingMessages(ctx context.Context, userID string, limit int) ([]map[string]interface{}, error) {
	args := m.Called(ctx, userID, limit)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]map[string]interface{}), args.Error(1)
}

func (m *MockRealTimeRepository) RemoveMessage(ctx context.Context, messageID string) error {
	args := m.Called(ctx, messageID)
	return args.Error(0)
}

func (m *MockRealTimeRepository) CreatePresenceRecord(ctx context.Context, userID string, status string) error {
	args := m.Called(ctx, userID, status)
	return args.Error(0)
}

func (m *MockRealTimeRepository) GetPresence(ctx context.Context, userID string) (map[string]interface{}, error) {
	args := m.Called(ctx, userID)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(map[string]interface{}), args.Error(1)
}

func (m *MockRealTimeRepository) GetOnlineUsers(ctx context.Context) ([]string, error) {
	args := m.Called(ctx)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]string), args.Error(1)
}

// TestRealTimeEventService_SubscribeToChannel tests channel subscription
func TestRealTimeEventService_SubscribeToChannel(t *testing.T) {
	mockRepo := new(MockRealTimeRepository)
	ctx := context.Background()

	mockRepo.On("CreateSubscription", ctx, "user-1", "notifications").Return(nil)

	service := NewRealTimeEventService(mockRepo)
	err := service.SubscribeToChannel(ctx, "user-1", "notifications")

	assert.NoError(t, err)
	mockRepo.AssertCalled(t, "CreateSubscription", ctx, "user-1", "notifications")
}

// TestRealTimeEventService_GetUserSubscriptions tests subscription retrieval
func TestRealTimeEventService_GetUserSubscriptions(t *testing.T) {
	mockRepo := new(MockRealTimeRepository)
	ctx := context.Background()

	subscriptions := []string{"notifications", "messages", "alerts"}

	mockRepo.On("GetUserSubscriptions", ctx, "user-1").Return(subscriptions, nil)

	service := NewRealTimeEventService(mockRepo)
	result, err := service.GetUserSubscriptions(ctx, "user-1")

	assert.NoError(t, err)
	assert.Equal(t, 3, len(result))
	mockRepo.AssertCalled(t, "GetUserSubscriptions", ctx, "user-1")
}

// TestRealTimeEventService_PublishToChannel tests channel publishing
func TestRealTimeEventService_PublishToChannel(t *testing.T) {
	mockRepo := new(MockRealTimeRepository)
	ctx := context.Background()

	subscribers := []string{"user-1", "user-2"}
	mockRepo.On("GetChannelSubscribers", ctx, "notifications").Return(subscribers, nil)
	mockRepo.On("StoreMessage", ctx, mock.MatchedBy(func(m map[string]interface{}) bool {
		return m["channel"] == "notifications" && m["event"] == "user.online"
	})).Return(nil)

	service := NewRealTimeEventService(mockRepo)
	err := service.PublishToChannel(ctx, "notifications", "user.online", map[string]interface{}{"user_id": "user-1"})

	assert.NoError(t, err)
	mockRepo.AssertCalled(t, "GetChannelSubscribers", ctx, "notifications")
	mockRepo.AssertCalled(t, "StoreMessage", ctx, mock.AnythingOfType("map[string]interface {}"))
}

// TestRealTimeEventService_BroadcastEvent tests event broadcasting
func TestRealTimeEventService_BroadcastEvent(t *testing.T) {
	mockRepo := new(MockRealTimeRepository)
	ctx := context.Background()

	mockRepo.On("StoreMessage", ctx, mock.MatchedBy(func(m map[string]interface{}) bool {
		return m["event"] == "system.alert"
	})).Return(nil)

	service := NewRealTimeEventService(mockRepo)
	err := service.BroadcastEvent(ctx, "system.alert", map[string]interface{}{"message": "System maintenance"})

	assert.NoError(t, err)
	mockRepo.AssertCalled(t, "StoreMessage", ctx, mock.AnythingOfType("map[string]interface {}"))
}

// TestRealTimeEventService_GetChannelSubscribers tests subscriber retrieval
func TestRealTimeEventService_GetChannelSubscribers(t *testing.T) {
	mockRepo := new(MockRealTimeRepository)
	ctx := context.Background()

	subscribers := []string{"user-1", "user-2", "user-3"}

	mockRepo.On("GetChannelSubscribers", ctx, "notifications").Return(subscribers, nil)

	service := NewRealTimeEventService(mockRepo)
	result, err := service.GetChannelSubscribers(ctx, "notifications")

	assert.NoError(t, err)
	assert.Equal(t, 3, len(result))
	mockRepo.AssertCalled(t, "GetChannelSubscribers", ctx, "notifications")
}

// TestRealTimeEventService_GetOnlineUsers tests online users retrieval
func TestRealTimeEventService_GetOnlineUsers(t *testing.T) {
	mockRepo := new(MockRealTimeRepository)
	ctx := context.Background()

	onlineUsers := []string{"user-1", "user-2"}

	mockRepo.On("GetOnlineUsers", ctx).Return(onlineUsers, nil)

	service := NewRealTimeEventService(mockRepo)
	result, err := service.GetOnlineUsers(ctx)

	assert.NoError(t, err)
	assert.Equal(t, 2, len(result))
	mockRepo.AssertCalled(t, "GetOnlineUsers", ctx)
}
