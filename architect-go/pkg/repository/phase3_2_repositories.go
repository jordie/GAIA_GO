package repository

import (
	"context"
	"fmt"
	"time"

	"architect-go/pkg/models"
	"gorm.io/gorm"
)

// ==================== EVENT LOG REPOSITORY ====================

type eventLogRepositoryImpl struct {
	db *gorm.DB
}

func NewEventLogRepository(db *gorm.DB) EventLogRepository {
	return &eventLogRepositoryImpl{db: db}
}

func (r *eventLogRepositoryImpl) Create(ctx context.Context, event *models.EventLog) error {
	return r.db.WithContext(ctx).Create(event).Error
}

func (r *eventLogRepositoryImpl) Get(ctx context.Context, id string) (*models.EventLog, error) {
	var event *models.EventLog
	err := r.db.WithContext(ctx).Where("id = ?", id).First(&event).Error
	return event, err
}

func (r *eventLogRepositoryImpl) List(ctx context.Context, filters map[string]interface{}, limit int, offset int) ([]*models.EventLog, int64, error) {
	var events []*models.EventLog
	var total int64
	query := r.db.WithContext(ctx)

	if eventType, ok := filters["event_type"].(string); ok && eventType != "" {
		query = query.Where("event_type = ?", eventType)
	}
	if source, ok := filters["source"].(string); ok && source != "" {
		query = query.Where("source = ?", source)
	}

	result := query.Offset(offset).Limit(limit).Find(&events)
	query.Model(&models.EventLog{}).Count(&total)

	return events, total, result.Error
}

func (r *eventLogRepositoryImpl) GetByType(ctx context.Context, eventType string, limit int, offset int) ([]*models.EventLog, int64, error) {
	var events []*models.EventLog
	var total int64

	r.db.WithContext(ctx).Where("event_type = ?", eventType).Count(&total)
	err := r.db.WithContext(ctx).Where("event_type = ?", eventType).Offset(offset).Limit(limit).Find(&events).Error

	return events, total, err
}

func (r *eventLogRepositoryImpl) GetByUser(ctx context.Context, userID string, limit int, offset int) ([]*models.EventLog, int64, error) {
	var events []*models.EventLog
	var total int64

	r.db.WithContext(ctx).Where("user_id = ?", userID).Count(&total)
	err := r.db.WithContext(ctx).Where("user_id = ?", userID).Offset(offset).Limit(limit).Find(&events).Error

	return events, total, err
}

func (r *eventLogRepositoryImpl) GetByProject(ctx context.Context, projectID string, limit int, offset int) ([]*models.EventLog, int64, error) {
	var events []*models.EventLog
	var total int64

	r.db.WithContext(ctx).Where("project_id = ?", projectID).Count(&total)
	err := r.db.WithContext(ctx).Where("project_id = ?", projectID).Offset(offset).Limit(limit).Find(&events).Error

	return events, total, err
}

func (r *eventLogRepositoryImpl) Search(ctx context.Context, query string, limit int, offset int) ([]*models.EventLog, int64, error) {
	var events []*models.EventLog
	var total int64

	r.db.WithContext(ctx).Where("message ILIKE ? OR event_type ILIKE ?", "%"+query+"%", "%"+query+"%").Count(&total)
	err := r.db.WithContext(ctx).Where("message ILIKE ? OR event_type ILIKE ?", "%"+query+"%", "%"+query+"%").Offset(offset).Limit(limit).Find(&events).Error

	return events, total, err
}

func (r *eventLogRepositoryImpl) Update(ctx context.Context, event *models.EventLog) error {
	return r.db.WithContext(ctx).Save(event).Error
}

func (r *eventLogRepositoryImpl) Delete(ctx context.Context, id string) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&models.EventLog{}).Error
}

func (r *eventLogRepositoryImpl) HardDelete(ctx context.Context, beforeDate string) (int64, error) {
	result := r.db.WithContext(ctx).Where("created_at < ?", beforeDate).Delete(&models.EventLog{})
	return result.RowsAffected, result.Error
}

func (r *eventLogRepositoryImpl) GetByTag(ctx context.Context, tag string, limit int, offset int) ([]*models.EventLog, int64, error) {
	var events []*models.EventLog
	var total int64

	// Note: This assumes tags are stored as JSONB array. Actual implementation may vary.
	r.db.WithContext(ctx).Where("tags @> ?", `["`+tag+`"]`).Count(&total)
	err := r.db.WithContext(ctx).Where("tags @> ?", `["`+tag+`"]`).Offset(offset).Limit(limit).Find(&events).Error

	return events, total, err
}

func (r *eventLogRepositoryImpl) GetStats(ctx context.Context, startDate, endDate string) (map[string]interface{}, error) {
	// Stub: should calculate event stats
	return map[string]interface{}{}, nil
}

// ==================== ERROR LOG REPOSITORY ====================

type errorLogRepositoryImpl struct {
	db *gorm.DB
}

func NewErrorLogRepository(db *gorm.DB) ErrorLogRepository {
	return &errorLogRepositoryImpl{db: db}
}

func (r *errorLogRepositoryImpl) Create(ctx context.Context, errorLog *models.ErrorLog) error {
	return r.db.WithContext(ctx).Create(errorLog).Error
}

func (r *errorLogRepositoryImpl) Get(ctx context.Context, id string) (*models.ErrorLog, error) {
	var errorLog *models.ErrorLog
	err := r.db.WithContext(ctx).Where("id = ?", id).First(&errorLog).Error
	return errorLog, err
}

func (r *errorLogRepositoryImpl) ListRecent(ctx context.Context, limit int) ([]*models.ErrorLog, error) {
	var errors []*models.ErrorLog
	err := r.db.WithContext(ctx).Order("timestamp DESC").Limit(limit).Find(&errors).Error
	return errors, err
}

func (r *errorLogRepositoryImpl) List(ctx context.Context, filters map[string]interface{}, limit int, offset int) ([]*models.ErrorLog, int64, error) {
	var errors []*models.ErrorLog
	var total int64
	query := r.db.WithContext(ctx)

	if errorType, ok := filters["error_type"].(string); ok && errorType != "" {
		query = query.Where("error_type = ?", errorType)
	}
	if source, ok := filters["source"].(string); ok && source != "" {
		query = query.Where("source = ?", source)
	}
	if severity, ok := filters["severity"].(string); ok && severity != "" {
		query = query.Where("severity = ?", severity)
	}
	if status, ok := filters["status"].(string); ok && status != "" {
		query = query.Where("status = ?", status)
	}

	query.Model(&models.ErrorLog{}).Count(&total)
	result := query.Offset(offset).Limit(limit).Find(&errors)

	return errors, total, result.Error
}

func (r *errorLogRepositoryImpl) Update(ctx context.Context, errorLog *models.ErrorLog) error {
	return r.db.WithContext(ctx).Save(errorLog).Error
}

func (r *errorLogRepositoryImpl) Delete(ctx context.Context, id string) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&models.ErrorLog{}).Error
}

func (r *errorLogRepositoryImpl) HardDelete(ctx context.Context, beforeDate string) (int64, error) {
	result := r.db.WithContext(ctx).Where("created_at < ?", beforeDate).Delete(&models.ErrorLog{})
	return result.RowsAffected, result.Error
}

func (r *errorLogRepositoryImpl) GetByType(ctx context.Context, errorType string, limit int, offset int) ([]*models.ErrorLog, int64, error) {
	var errors []*models.ErrorLog
	var total int64

	r.db.WithContext(ctx).Where("error_type = ?", errorType).Count(&total)
	err := r.db.WithContext(ctx).Where("error_type = ?", errorType).Offset(offset).Limit(limit).Find(&errors).Error

	return errors, total, err
}

func (r *errorLogRepositoryImpl) GetBySource(ctx context.Context, source string, limit int, offset int) ([]*models.ErrorLog, int64, error) {
	var errors []*models.ErrorLog
	var total int64

	r.db.WithContext(ctx).Where("source = ?", source).Count(&total)
	err := r.db.WithContext(ctx).Where("source = ?", source).Offset(offset).Limit(limit).Find(&errors).Error

	return errors, total, err
}

func (r *errorLogRepositoryImpl) GetBySeverity(ctx context.Context, severity string, limit int, offset int) ([]*models.ErrorLog, int64, error) {
	var errors []*models.ErrorLog
	var total int64

	r.db.WithContext(ctx).Where("severity = ?", severity).Count(&total)
	err := r.db.WithContext(ctx).Where("severity = ?", severity).Offset(offset).Limit(limit).Find(&errors).Error

	return errors, total, err
}

func (r *errorLogRepositoryImpl) GetByStatus(ctx context.Context, status string, limit int, offset int) ([]*models.ErrorLog, int64, error) {
	var errors []*models.ErrorLog
	var total int64

	r.db.WithContext(ctx).Where("status = ?", status).Count(&total)
	err := r.db.WithContext(ctx).Where("status = ?", status).Offset(offset).Limit(limit).Find(&errors).Error

	return errors, total, err
}

func (r *errorLogRepositoryImpl) Search(ctx context.Context, query string, limit int, offset int) ([]*models.ErrorLog, int64, error) {
	var errors []*models.ErrorLog
	var total int64

	r.db.WithContext(ctx).Where("message ILIKE ? OR error_type ILIKE ?", "%"+query+"%", "%"+query+"%").Count(&total)
	err := r.db.WithContext(ctx).Where("message ILIKE ? OR error_type ILIKE ?", "%"+query+"%", "%"+query+"%").Offset(offset).Limit(limit).Find(&errors).Error

	return errors, total, err
}

func (r *errorLogRepositoryImpl) GetStats(ctx context.Context, startDate, endDate string) (map[string]interface{}, error) {
	// Stub: should calculate error stats
	return map[string]interface{}{}, nil
}

func (r *errorLogRepositoryImpl) GetByTag(ctx context.Context, tag string, limit int, offset int) ([]*models.ErrorLog, int64, error) {
	var errors []*models.ErrorLog
	var total int64

	// Note: This assumes tags are stored as JSONB array. Actual implementation may vary.
	r.db.WithContext(ctx).Where("tags @> ?", `["`+tag+`"]`).Count(&total)
	err := r.db.WithContext(ctx).Where("tags @> ?", `["`+tag+`"]`).Offset(offset).Limit(limit).Find(&errors).Error

	return errors, total, err
}

func (r *errorLogRepositoryImpl) GetByProject(ctx context.Context, projectID string, limit int, offset int) ([]*models.ErrorLog, int64, error) {
	var errors []*models.ErrorLog
	var total int64

	r.db.WithContext(ctx).Where("project_id = ?", projectID).Count(&total)
	err := r.db.WithContext(ctx).Where("project_id = ?", projectID).Offset(offset).Limit(limit).Find(&errors).Error

	return errors, total, err
}

// ==================== WEBHOOK REPOSITORY ====================

type webhookRepositoryImpl struct {
	db *gorm.DB
}

func NewWebhookRepository(db *gorm.DB) WebhookRepository {
	return &webhookRepositoryImpl{db: db}
}

func (r *webhookRepositoryImpl) Create(ctx context.Context, webhook map[string]interface{}) error {
	return r.db.WithContext(ctx).Create(webhook).Error
}

func (r *webhookRepositoryImpl) Get(ctx context.Context, id string) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	err := r.db.WithContext(ctx).Where("id = ?", id).First(&result).Error
	return result, err
}

func (r *webhookRepositoryImpl) List(ctx context.Context, limit int, offset int) ([]map[string]interface{}, int64, error) {
	var webhooks []map[string]interface{}
	var total int64
	err := r.db.WithContext(ctx).Model(webhooks).Count(&total).Limit(limit).Offset(offset).Find(&webhooks).Error
	return webhooks, total, err
}

func (r *webhookRepositoryImpl) GetByIntegration(ctx context.Context, integrationID string, limit int, offset int) ([]map[string]interface{}, int64, error) {
	var webhooks []map[string]interface{}
	var total int64
	err := r.db.WithContext(ctx).Where("integration_id = ?", integrationID).Count(&total).Limit(limit).Offset(offset).Find(&webhooks).Error
	return webhooks, total, err
}

func (r *webhookRepositoryImpl) Update(ctx context.Context, webhook map[string]interface{}) error {
	return r.db.WithContext(ctx).Save(webhook).Error
}

func (r *webhookRepositoryImpl) Delete(ctx context.Context, id string) error {
	return r.db.WithContext(ctx).Table("webhooks").Where("id = ?", id).Delete(nil).Error
}

func (r *webhookRepositoryImpl) CreateDelivery(ctx context.Context, delivery map[string]interface{}) error {
	return r.db.WithContext(ctx).Create(delivery).Error
}

func (r *webhookRepositoryImpl) GetDeliveryHistory(ctx context.Context, webhookID string, limit int, offset int) ([]map[string]interface{}, int64, error) {
	var deliveries []map[string]interface{}
	var total int64
	err := r.db.WithContext(ctx).Where("webhook_id = ?", webhookID).Count(&total).Limit(limit).Offset(offset).Find(&deliveries).Error
	return deliveries, total, err
}

func (r *webhookRepositoryImpl) GetFailedDeliveries(ctx context.Context, limit int, offset int) ([]map[string]interface{}, int64, error) {
	var deliveries []map[string]interface{}
	var total int64
	err := r.db.WithContext(ctx).Where("status != ?", "success").Count(&total).Limit(limit).Offset(offset).Find(&deliveries).Error
	return deliveries, total, err
}

// ==================== AUDIT LOG REPOSITORY ====================

type auditLogRepositoryImpl struct {
	db *gorm.DB
}

func NewAuditLogRepository(db *gorm.DB) AuditLogRepository {
	return &auditLogRepositoryImpl{db: db}
}

func (r *auditLogRepositoryImpl) Create(ctx context.Context, auditLog map[string]interface{}) error {
	return r.db.WithContext(ctx).Create(auditLog).Error
}

func (r *auditLogRepositoryImpl) Get(ctx context.Context, id string) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	err := r.db.WithContext(ctx).Where("id = ?", id).First(&result).Error
	return result, err
}

func (r *auditLogRepositoryImpl) List(ctx context.Context, limit int, offset int) ([]map[string]interface{}, int64, error) {
	var logs []map[string]interface{}
	var total int64
	err := r.db.WithContext(ctx).Model(logs).Count(&total).Order("created_at DESC").Limit(limit).Offset(offset).Find(&logs).Error
	return logs, total, err
}

func (r *auditLogRepositoryImpl) GetByUser(ctx context.Context, userID string, limit int, offset int) ([]map[string]interface{}, int64, error) {
	var logs []map[string]interface{}
	var total int64
	err := r.db.WithContext(ctx).Where("user_id = ?", userID).Count(&total).Order("created_at DESC").Limit(limit).Offset(offset).Find(&logs).Error
	return logs, total, err
}

func (r *auditLogRepositoryImpl) GetByAction(ctx context.Context, action string, limit int, offset int) ([]map[string]interface{}, int64, error) {
	var logs []map[string]interface{}
	var total int64
	err := r.db.WithContext(ctx).Where("action = ?", action).Count(&total).Order("created_at DESC").Limit(limit).Offset(offset).Find(&logs).Error
	return logs, total, err
}

func (r *auditLogRepositoryImpl) GetByResource(ctx context.Context, resourceType string, resourceID string, limit int, offset int) ([]map[string]interface{}, int64, error) {
	var logs []map[string]interface{}
	var total int64
	err := r.db.WithContext(ctx).Where("resource = ? AND resource_id = ?", resourceType, resourceID).Count(&total).Order("created_at DESC").Limit(limit).Offset(offset).Find(&logs).Error
	return logs, total, err
}

func (r *auditLogRepositoryImpl) Search(ctx context.Context, query string, limit int, offset int) ([]map[string]interface{}, int64, error) {
	var logs []map[string]interface{}
	var total int64
	searchQuery := fmt.Sprintf("%%%s%%", query)
	err := r.db.WithContext(ctx).Where("action ILIKE ? OR resource ILIKE ?", searchQuery, searchQuery).Count(&total).Order("created_at DESC").Limit(limit).Offset(offset).Find(&logs).Error
	return logs, total, err
}

func (r *auditLogRepositoryImpl) GetStats(ctx context.Context, startDate, endDate string) (map[string]interface{}, error) {
	stats := make(map[string]interface{})
	// Stub: should calculate audit stats
	return stats, nil
}

func (r *auditLogRepositoryImpl) Archive(ctx context.Context, beforeDate string) (int64, error) {
	result := r.db.WithContext(ctx).Where("created_at < ?", beforeDate).Update("archived", true)
	return result.RowsAffected, result.Error
}

func (r *auditLogRepositoryImpl) Purge(ctx context.Context, beforeDate string) (int64, error) {
	result := r.db.WithContext(ctx).Where("created_at < ?", beforeDate).Delete(&models.AuditLog{})
	return result.RowsAffected, result.Error
}

func (r *auditLogRepositoryImpl) VerifyIntegrity(ctx context.Context) (map[string]interface{}, error) {
	// Stub: should verify audit log integrity
	return map[string]interface{}{}, nil
}

// ==================== REAL-TIME REPOSITORY ====================

type realtimeRepositoryImpl struct {
	db *gorm.DB
}

func NewRealTimeRepository(db *gorm.DB) RealTimeRepository {
	return &realtimeRepositoryImpl{db: db}
}

func (r *realtimeRepositoryImpl) CreateSubscription(ctx context.Context, userID string, channel string) error {
	subscription := map[string]interface{}{
		"user_id": userID,
		"channel": channel,
	}
	return r.db.WithContext(ctx).Create(subscription).Error
}

func (r *realtimeRepositoryImpl) RemoveSubscription(ctx context.Context, userID string, channel string) error {
	return r.db.WithContext(ctx).Table("subscriptions").Where("user_id = ? AND channel = ?", userID, channel).Delete(nil).Error
}

func (r *realtimeRepositoryImpl) GetUserSubscriptions(ctx context.Context, userID string) ([]string, error) {
	var channels []string
	err := r.db.WithContext(ctx).Where("user_id = ?", userID).Pluck("channel", &channels).Error
	return channels, err
}

func (r *realtimeRepositoryImpl) GetChannelSubscribers(ctx context.Context, channel string) ([]string, error) {
	var userIDs []string
	err := r.db.WithContext(ctx).Where("channel = ?", channel).Pluck("user_id", &userIDs).Error
	return userIDs, err
}

func (r *realtimeRepositoryImpl) StoreMessage(ctx context.Context, message map[string]interface{}) error {
	return r.db.WithContext(ctx).Create(message).Error
}

func (r *realtimeRepositoryImpl) GetPendingMessages(ctx context.Context, userID string, limit int) ([]map[string]interface{}, error) {
	var messages []map[string]interface{}
	err := r.db.WithContext(ctx).Where("user_id = ? AND status = ?", userID, "pending").Limit(limit).Find(&messages).Error
	return messages, err
}

func (r *realtimeRepositoryImpl) RemoveMessage(ctx context.Context, messageID string) error {
	return r.db.WithContext(ctx).Table("messages").Where("id = ?", messageID).Delete(nil).Error
}

func (r *realtimeRepositoryImpl) CreatePresenceRecord(ctx context.Context, userID string, status string) error {
	presence := map[string]interface{}{
		"user_id": userID,
		"status":  status,
	}
	return r.db.WithContext(ctx).Save(presence).Error
}

func (r *realtimeRepositoryImpl) GetPresence(ctx context.Context, userID string) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	err := r.db.WithContext(ctx).Where("user_id = ?", userID).First(&result).Error
	return result, err
}

func (r *realtimeRepositoryImpl) GetOnlineUsers(ctx context.Context) ([]string, error) {
	var userIDs []string
	err := r.db.WithContext(ctx).Where("status != ?", "offline").Pluck("user_id", &userIDs).Error
	return userIDs, err
}

// ==================== INTEGRATION HEALTH REPOSITORY ====================

type integrationHealthRepositoryImpl struct {
	db *gorm.DB
}

func NewIntegrationHealthRepository(db *gorm.DB) IntegrationHealthRepository {
	return &integrationHealthRepositoryImpl{db: db}
}

func (r *integrationHealthRepositoryImpl) CreateHealthCheck(ctx context.Context, healthCheck map[string]interface{}) error {
	return r.db.WithContext(ctx).Create(healthCheck).Error
}

func (r *integrationHealthRepositoryImpl) GetLatestHealthCheck(ctx context.Context, integrationID string) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	err := r.db.WithContext(ctx).Where("integration_id = ?", integrationID).Order("created_at DESC").First(&result).Error
	return result, err
}

func (r *integrationHealthRepositoryImpl) GetHealthCheckHistory(ctx context.Context, integrationID string, limit int, offset int) ([]map[string]interface{}, int64, error) {
	var checks []map[string]interface{}
	var total int64
	err := r.db.WithContext(ctx).Where("integration_id = ?", integrationID).Count(&total).Order("created_at DESC").Limit(limit).Offset(offset).Find(&checks).Error
	return checks, total, err
}

func (r *integrationHealthRepositoryImpl) CreateIncident(ctx context.Context, incident map[string]interface{}) error {
	return r.db.WithContext(ctx).Create(incident).Error
}

func (r *integrationHealthRepositoryImpl) GetIncident(ctx context.Context, incidentID string) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	err := r.db.WithContext(ctx).Where("id = ?", incidentID).First(&result).Error
	return result, err
}

func (r *integrationHealthRepositoryImpl) ListIncidents(ctx context.Context, integrationID string, limit int, offset int) ([]map[string]interface{}, int64, error) {
	var incidents []map[string]interface{}
	var total int64
	err := r.db.WithContext(ctx).Where("integration_id = ?", integrationID).Count(&total).Order("created_at DESC").Limit(limit).Offset(offset).Find(&incidents).Error
	return incidents, total, err
}

func (r *integrationHealthRepositoryImpl) UpdateIncident(ctx context.Context, incident map[string]interface{}) error {
	return r.db.WithContext(ctx).Save(incident).Error
}

func (r *integrationHealthRepositoryImpl) GetActiveIncidents(ctx context.Context) ([]map[string]interface{}, error) {
	var incidents []map[string]interface{}
	err := r.db.WithContext(ctx).Where("status != ?", "resolved").Find(&incidents).Error
	return incidents, err
}

func (r *integrationHealthRepositoryImpl) CreateAlert(ctx context.Context, alert map[string]interface{}) error {
	return r.db.WithContext(ctx).Create(alert).Error
}

func (r *integrationHealthRepositoryImpl) GetAlerts(ctx context.Context, limit int, offset int) ([]map[string]interface{}, int64, error) {
	var alerts []map[string]interface{}
	var total int64
	err := r.db.WithContext(ctx).Model(alerts).Count(&total).Limit(limit).Offset(offset).Find(&alerts).Error
	return alerts, total, err
}

func (r *integrationHealthRepositoryImpl) GetMetrics(ctx context.Context, integrationID string) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	// Stub: should query metrics for integration
	return result, nil
}

func (r *integrationHealthRepositoryImpl) CreateMetric(ctx context.Context, metric map[string]interface{}) error {
	return r.db.WithContext(ctx).Create(metric).Error
}

// ==================== NOTIFICATION REPOSITORY ====================

type notificationRepositoryImpl struct {
	db *gorm.DB
}

func NewNotificationRepository(db *gorm.DB) NotificationRepository {
	return &notificationRepositoryImpl{db: db}
}

func (r *notificationRepositoryImpl) Create(ctx context.Context, notification *models.Notification) error {
	return r.db.WithContext(ctx).Create(notification).Error
}

func (r *notificationRepositoryImpl) Get(ctx context.Context, id string) (*models.Notification, error) {
	var notification *models.Notification
	err := r.db.WithContext(ctx).Where("id = ?", id).First(&notification).Error
	return notification, err
}

func (r *notificationRepositoryImpl) ListByUser(ctx context.Context, userID string, limit int, offset int) ([]*models.Notification, int64, error) {
	var notifications []*models.Notification
	var total int64
	query := r.db.WithContext(ctx).Model(&models.Notification{})
	if userID != "" {
		query = query.Where("user_id = ?", userID)
	}
	if err := query.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	err := query.Offset(offset).Limit(limit).Find(&notifications).Error
	return notifications, total, err
}

func (r *notificationRepositoryImpl) ListUnread(ctx context.Context, userID string, limit int, offset int) ([]*models.Notification, int64, error) {
	var notifications []*models.Notification
	var total int64
	query := r.db.WithContext(ctx).Model(&models.Notification{}).Where("read_at IS NULL")
	if userID != "" {
		query = query.Where("user_id = ?", userID)
	}
	if err := query.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	err := query.Offset(offset).Limit(limit).Find(&notifications).Error
	return notifications, total, err
}

func (r *notificationRepositoryImpl) ListRecent(ctx context.Context, userID string, limit int) ([]*models.Notification, error) {
	var notifications []*models.Notification
	err := r.db.WithContext(ctx).Where("user_id = ?", userID).Order("created_at DESC").Limit(limit).Find(&notifications).Error
	return notifications, err
}

func (r *notificationRepositoryImpl) Update(ctx context.Context, notification *models.Notification) error {
	return r.db.WithContext(ctx).Save(notification).Error
}

func (r *notificationRepositoryImpl) Delete(ctx context.Context, id string) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&models.Notification{}).Error
}

func (r *notificationRepositoryImpl) MarkAsRead(ctx context.Context, id string) error {
	now := time.Now()
	return r.db.WithContext(ctx).Model(&models.Notification{}).Where("id = ?", id).Update("read_at", &now).Error
}

func (r *notificationRepositoryImpl) MarkAsUnread(ctx context.Context, id string) error {
	return r.db.WithContext(ctx).Model(&models.Notification{}).Where("id = ?", id).Update("read_at", nil).Error
}

func (r *notificationRepositoryImpl) ListUnreadByUser(ctx context.Context, userID string, limit int, offset int) ([]*models.Notification, int64, error) {
	return r.ListUnread(ctx, userID, limit, offset)
}

func (r *notificationRepositoryImpl) GetByProject(ctx context.Context, projectID string, limit int, offset int) ([]*models.Notification, int64, error) {
	var notifications []*models.Notification
	var total int64
	q := r.db.WithContext(ctx).Model(&models.Notification{}).Where("project_id = ?", projectID)
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	err := q.Offset(offset).Limit(limit).Find(&notifications).Error
	return notifications, total, err
}

func (r *notificationRepositoryImpl) GetByType(ctx context.Context, notificationType string, limit int, offset int) ([]*models.Notification, int64, error) {
	var notifications []*models.Notification
	var total int64
	q := r.db.WithContext(ctx).Model(&models.Notification{}).Where("type = ?", notificationType)
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	err := q.Offset(offset).Limit(limit).Find(&notifications).Error
	return notifications, total, err
}

func (r *notificationRepositoryImpl) Search(ctx context.Context, query string, limit int, offset int) ([]*models.Notification, int64, error) {
	var notifications []*models.Notification
	var total int64
	q := r.db.WithContext(ctx).Model(&models.Notification{}).Where("title LIKE ? OR message LIKE ?", "%"+query+"%", "%"+query+"%")
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	err := q.Offset(offset).Limit(limit).Find(&notifications).Error
	return notifications, total, err
}

func (r *notificationRepositoryImpl) CreateDelivery(ctx context.Context, delivery map[string]interface{}) error {
	return r.db.WithContext(ctx).Create(delivery).Error
}

func (r *notificationRepositoryImpl) GetDeliveryHistory(ctx context.Context, notificationID string, limit int, offset int) ([]map[string]interface{}, int64, error) {
	var deliveries []map[string]interface{}
	var total int64
	err := r.db.WithContext(ctx).Where("notification_id = ?", notificationID).Count(&total).Offset(offset).Limit(limit).Find(&deliveries).Error
	return deliveries, total, err
}

// ==================== INTEGRATION REPOSITORY ====================

type integrationRepositoryImpl struct {
	db *gorm.DB
}

func NewIntegrationRepository(db *gorm.DB) IntegrationRepository {
	return &integrationRepositoryImpl{db: db}
}

func (r *integrationRepositoryImpl) Create(ctx context.Context, integration *models.Integration) error {
	return r.db.WithContext(ctx).Create(integration).Error
}

func (r *integrationRepositoryImpl) Get(ctx context.Context, id string) (*models.Integration, error) {
	var integration *models.Integration
	err := r.db.WithContext(ctx).Where("id = ?", id).First(&integration).Error
	return integration, err
}

func (r *integrationRepositoryImpl) List(ctx context.Context, limit int, offset int) ([]*models.Integration, int64, error) {
	var integrations []*models.Integration
	var total int64
	err := r.db.WithContext(ctx).Model(&models.Integration{}).Count(&total).Offset(offset).Limit(limit).Find(&integrations).Error
	return integrations, total, err
}

func (r *integrationRepositoryImpl) ListByType(ctx context.Context, integrationType string, limit int, offset int) ([]*models.Integration, int64, error) {
	var integrations []*models.Integration
	var total int64
	err := r.db.WithContext(ctx).Where("type = ?", integrationType).Count(&total).Offset(offset).Limit(limit).Find(&integrations).Error
	return integrations, total, err
}

func (r *integrationRepositoryImpl) ListByProvider(ctx context.Context, provider string, limit int, offset int) ([]*models.Integration, int64, error) {
	var integrations []*models.Integration
	var total int64
	err := r.db.WithContext(ctx).Where("provider = ?", provider).Count(&total).Offset(offset).Limit(limit).Find(&integrations).Error
	return integrations, total, err
}

func (r *integrationRepositoryImpl) ListEnabled(ctx context.Context, limit int, offset int) ([]*models.Integration, int64, error) {
	var integrations []*models.Integration
	var total int64
	err := r.db.WithContext(ctx).Where("enabled = ?", true).Count(&total).Offset(offset).Limit(limit).Find(&integrations).Error
	return integrations, total, err
}

func (r *integrationRepositoryImpl) Update(ctx context.Context, integration *models.Integration) error {
	return r.db.WithContext(ctx).Save(integration).Error
}

func (r *integrationRepositoryImpl) Delete(ctx context.Context, id string) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&models.Integration{}).Error
}

func (r *integrationRepositoryImpl) GetByType(ctx context.Context, integrationType string) ([]*models.Integration, error) {
	var integrations []*models.Integration
	err := r.db.WithContext(ctx).Where("type = ?", integrationType).Find(&integrations).Error
	return integrations, err
}

func (r *integrationRepositoryImpl) GetByProvider(ctx context.Context, provider string) ([]*models.Integration, error) {
	var integrations []*models.Integration
	err := r.db.WithContext(ctx).Where("provider = ?", provider).Find(&integrations).Error
	return integrations, err
}

func (r *integrationRepositoryImpl) GetEnabled(ctx context.Context) ([]*models.Integration, error) {
	var integrations []*models.Integration
	err := r.db.WithContext(ctx).Where("enabled = ?", true).Find(&integrations).Error
	return integrations, err
}

func (r *integrationRepositoryImpl) CreateSyncRecord(ctx context.Context, syncRecord map[string]interface{}) error {
	return r.db.WithContext(ctx).Create(syncRecord).Error
}

func (r *integrationRepositoryImpl) GetSyncStatus(ctx context.Context, integrationID string) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	err := r.db.WithContext(ctx).Where("integration_id = ?", integrationID).First(&result).Error
	return result, err
}
