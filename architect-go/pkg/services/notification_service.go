package services

import (
	"context"

	"architect-go/pkg/models"
)

// NotificationService defines notification management business logic
type NotificationService interface {
	// CreateNotification creates a new notification
	CreateNotification(ctx context.Context, req *CreateNotificationRequest) (*models.Notification, error)

	// GetNotification retrieves a notification by ID
	GetNotification(ctx context.Context, id string) (*models.Notification, error)

	// ListNotifications retrieves user's notifications with pagination
	ListNotifications(ctx context.Context, userID string, limit, offset int) ([]*models.Notification, int64, error)

	// ListUnreadNotifications retrieves unread notifications for user
	ListUnreadNotifications(ctx context.Context, userID string, limit, offset int) ([]*models.Notification, int64, error)

	// ListRecentNotifications retrieves recent notifications
	ListRecentNotifications(ctx context.Context, userID string, limit int) ([]*models.Notification, error)

	// SendNotification sends a notification to users
	SendNotification(ctx context.Context, req *SendNotificationRequest) error

	// SendBulkNotifications sends notifications to multiple users
	SendBulkNotifications(ctx context.Context, notificationID string, userIDs []string) error

	// UpdateNotification updates notification metadata
	UpdateNotification(ctx context.Context, id string, req *CreateNotificationRequest) (*models.Notification, error)

	// DeleteNotification deletes a notification
	DeleteNotification(ctx context.Context, id string) error

	// MarkAsRead marks a notification as read
	MarkAsRead(ctx context.Context, id string) error

	// MarkAllAsRead marks all user's notifications as read
	MarkAllAsRead(ctx context.Context, userID string) error

	// MarkAsUnread marks a notification as unread
	MarkAsUnread(ctx context.Context, id string) error

	// DismissNotification dismisses a notification
	DismissNotification(ctx context.Context, id string) error

	// DismissAllNotifications dismisses all notifications for user
	DismissAllNotifications(ctx context.Context, userID string) error

	// GetUserPreferences retrieves user notification preferences
	GetUserPreferences(ctx context.Context, userID string) (*NotificationPreferencesRequest, error)

	// UpdateUserPreferences updates notification preferences
	UpdateUserPreferences(ctx context.Context, userID string, req *NotificationPreferencesRequest) error

	// ResetPreferencesToDefaults resets preferences to default values
	ResetPreferencesToDefaults(ctx context.Context, userID string) error

	// GetPreferenceCategories returns available preference categories
	GetPreferenceCategories(ctx context.Context) ([]string, error)

	// GetNotificationSettings retrieves notification settings
	GetNotificationSettings(ctx context.Context, userID string) (map[string]interface{}, error)

	// CreateNotificationSetting creates new notification setting
	CreateNotificationSetting(ctx context.Context, userID string, setting map[string]interface{}) (string, error)

	// UpdateNotificationSetting updates a notification setting
	UpdateNotificationSetting(ctx context.Context, userID string, settingID string, setting map[string]interface{}) error

	// DeleteNotificationSetting deletes a notification setting
	DeleteNotificationSetting(ctx context.Context, userID string, settingID string) error

	// GetAvailableChannels returns available notification channels
	GetAvailableChannels(ctx context.Context) ([]string, error)

	// GetChannelStatus retrieves status of a notification channel
	GetChannelStatus(ctx context.Context, channel string) (map[string]interface{}, error)

	// TestChannel sends test notification through a channel
	TestChannel(ctx context.Context, channel string, userID string) error

	// GetAvailableTemplates returns available notification templates
	GetAvailableTemplates(ctx context.Context) ([]*models.NotificationTemplate, error)

	// GetTemplateByID retrieves a specific notification template
	GetTemplateByID(ctx context.Context, templateID string) (*models.NotificationTemplate, error)

	// CreateTemplate creates new notification template
	CreateTemplate(ctx context.Context, req *TemplateRequest) (*models.NotificationTemplate, error)

	// UpdateTemplate updates a notification template
	UpdateTemplate(ctx context.Context, templateID string, req *TemplateRequest) (*models.NotificationTemplate, error)

	// DeleteTemplate deletes a notification template
	DeleteTemplate(ctx context.Context, templateID string) error

	// PreviewTemplate renders a template with sample data
	PreviewTemplate(ctx context.Context, templateID string, data map[string]interface{}) (string, error)

	// GetDeliveryStatus retrieves delivery status of a notification
	GetDeliveryStatus(ctx context.Context, notificationID string) ([]NotificationDeliveryResponse, error)

	// GetDeliveryHistory retrieves delivery history for user
	GetDeliveryHistory(ctx context.Context, userID string, limit, offset int) ([]NotificationDeliveryResponse, int64, error)

	// GetNotificationStats returns notification statistics
	GetNotificationStats(ctx context.Context, userID string) (map[string]interface{}, error)

	// GetProjectNotifications retrieves notifications for a project
	GetProjectNotifications(ctx context.Context, projectID string, limit, offset int) ([]*models.Notification, int64, error)

	// GetUserNotifications retrieves notifications for a user
	GetUserNotifications(ctx context.Context, userID string, limit, offset int) ([]*models.Notification, int64, error)

	// GetNotificationsByType retrieves notifications of a specific type
	GetNotificationsByType(ctx context.Context, notificationType string, limit, offset int) ([]*models.Notification, int64, error)

	// GetNotificationsByPriority retrieves notifications by priority
	GetNotificationsByPriority(ctx context.Context, priority string, limit, offset int) ([]*models.Notification, int64, error)

	// ExportNotifications exports notifications in specified format
	ExportNotifications(ctx context.Context, format string) (*EventExportResponse, error)

	// SearchNotifications performs full-text search on notifications
	SearchNotifications(ctx context.Context, query string, limit, offset int) ([]*models.Notification, int64, error)

	// RetryDelivery retries delivery of a failed notification
	RetryDelivery(ctx context.Context, deliveryID string) error

	// ScheduleNotification schedules notification for later delivery
	ScheduleNotification(ctx context.Context, req *ScheduleNotificationRequest) (string, error)

	// GetScheduledNotifications retrieves scheduled notifications
	GetScheduledNotifications(ctx context.Context, userID string, limit, offset int) ([]*models.Notification, int64, error)

	// UpdateScheduledNotification updates a scheduled notification
	UpdateScheduledNotification(ctx context.Context, notificationID string, req *ScheduleNotificationRequest) error

	// CancelScheduledNotification cancels a scheduled notification
	CancelScheduledNotification(ctx context.Context, notificationID string) error

	// CreateRule creates notification rule for automation
	CreateRule(ctx context.Context, req *NotificationRuleRequest) (string, error)

	// GetRules retrieves notification rules
	GetRules(ctx context.Context, userID string, limit, offset int) ([]map[string]interface{}, int64, error)

	// UpdateRule updates notification rule
	UpdateRule(ctx context.Context, userID string, ruleID string, req *NotificationRuleRequest) error

	// DeleteRule deletes notification rule
	DeleteRule(ctx context.Context, userID string, ruleID string) error

	// GetDigestNotification retrieves digest notification for user
	GetDigestNotification(ctx context.Context, userID string, period string) (*models.Notification, error)

	// SubscribeToTopic subscribes user to notification topic
	SubscribeToTopic(ctx context.Context, userID string, topic string) error

	// UnsubscribeFromTopic unsubscribes user from topic
	UnsubscribeFromTopic(ctx context.Context, userID string, topic string) error

	// GetUserTopics retrieves topics user is subscribed to
	GetUserTopics(ctx context.Context, userID string) ([]string, error)
}
