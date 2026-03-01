package rate_limiting

import (
	"context"
	"testing"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupNotificationTestDB creates test database for notification tests
func setupNotificationTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to create test DB: %v", err)
	}

	// Create tables
	db.Exec(`
		CREATE TABLE appeal_notifications (
			id INTEGER PRIMARY KEY,
			appeal_id INTEGER,
			user_id INTEGER,
			notification_type TEXT,
			channel TEXT,
			recipient TEXT,
			subject TEXT,
			body TEXT,
			status TEXT DEFAULT 'pending',
			error_message TEXT,
			sent_at TIMESTAMP,
			opened_at TIMESTAMP,
			clicked_at TIMESTAMP,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)
	`)

	return db
}

// TestNotificationServiceCreation tests service initialization
func TestNotificationServiceCreation(t *testing.T) {
	db := setupNotificationTestDB(t)
	ns := NewAppealNotificationService(db)

	if ns == nil {
		t.Errorf("Failed to create notification service")
	}

	if ns.templates == nil || len(ns.templates) == 0 {
		t.Errorf("Notification templates not initialized")
	}
}

// TestSendApprovalNotification tests approval notification sending
func TestSendApprovalNotification(t *testing.T) {
	db := setupNotificationTestDB(t)
	ns := NewAppealNotificationService(db)

	appeal := &Appeal{
		ID:          1,
		UserID:      100,
		ViolationID: 50,
		Status:      StatusApproved,
	}

	err := ns.SendApprovalNotification(
		context.Background(),
		appeal,
		"user@example.com",
		50.0,
		"Appeal confirmed as legitimate",
	)

	if err != nil {
		t.Errorf("Failed to send approval notification: %v", err)
	}

	// Verify notification was recorded
	var notif AppealNotificationRecord
	result := db.Table("appeal_notifications").
		Where("appeal_id = ? AND notification_type = ?", appeal.ID, AppealNotificationApproved).
		First(&notif)

	if result.Error != nil {
		t.Errorf("Notification not found in database: %v", result.Error)
	}

	if notif.Recipient != "user@example.com" {
		t.Errorf("Expected recipient 'user@example.com', got '%s'", notif.Recipient)
	}

	if notif.Status != StatusPending && notif.Status != StatusSent {
		t.Errorf("Expected pending/sent status, got %s", notif.Status)
	}
}

// TestSendDenialNotification tests denial notification sending
func TestSendDenialNotification(t *testing.T) {
	db := setupNotificationTestDB(t)
	ns := NewAppealNotificationService(db)

	appeal := &Appeal{
		ID:          2,
		UserID:      101,
		ViolationID: 51,
		Status:      StatusDenied,
	}

	err := ns.SendDenialNotification(
		context.Background(),
		appeal,
		"user2@example.com",
		"insufficient_evidence",
		"Provided evidence does not support appeal",
	)

	if err != nil {
		t.Errorf("Failed to send denial notification: %v", err)
	}

	var notif AppealNotificationRecord
	result := db.Table("appeal_notifications").
		Where("appeal_id = ? AND notification_type = ?", appeal.ID, NotificationDenied).
		First(&notif)

	if result.Error != nil {
		t.Errorf("Notification not found: %v", result.Error)
	}

	if notif.NotificationType != NotificationDenied {
		t.Errorf("Expected denial notification, got %s", notif.NotificationType)
	}
}

// TestSendSubmissionNotification tests submission confirmation
func TestSendSubmissionNotification(t *testing.T) {
	db := setupNotificationTestDB(t)
	ns := NewAppealNotificationService(db)

	appeal := &Appeal{
		ID:          3,
		UserID:      102,
		ViolationID: 52,
		Status:      StatusPending,
		CreatedAt:   time.Now(),
		ExpiresAt:   time.Now().AddDate(0, 0, 30),
	}

	err := ns.SendSubmissionNotification(
		context.Background(),
		appeal,
		"user3@example.com",
	)

	if err != nil {
		t.Errorf("Failed to send submission notification: %v", err)
	}

	var notif AppealNotificationRecord
	result := db.Table("appeal_notifications").
		Where("appeal_id = ? AND notification_type = ?", appeal.ID, NotificationSubmitted).
		First(&notif)

	if result.Error != nil {
		t.Errorf("Notification not found: %v", result.Error)
	}

	if notif.NotificationType != NotificationSubmitted {
		t.Errorf("Expected submission notification, got %s", notif.NotificationType)
	}
}

// TestSendExpirationNotification tests expiration notification
func TestSendExpirationNotification(t *testing.T) {
	db := setupNotificationTestDB(t)
	ns := NewAppealNotificationService(db)

	appeal := &Appeal{
		ID:          4,
		UserID:      103,
		ViolationID: 53,
		Status:      StatusExpired,
		ExpiresAt:   time.Now(),
	}

	err := ns.SendExpirationNotification(
		context.Background(),
		appeal,
		"user4@example.com",
	)

	if err != nil {
		t.Errorf("Failed to send expiration notification: %v", err)
	}

	var count int64
	db.Table("appeal_notifications").
		Where("appeal_id = ? AND notification_type = ?", appeal.ID, NotificationExpired).
		Count(&count)

	if count == 0 {
		t.Errorf("Expiration notification not found")
	}
}

// TestGetNotifications retrieves notifications for appeal
func TestGetNotifications(t *testing.T) {
	db := setupNotificationTestDB(t)
	ns := NewAppealNotificationService(db)

	appeal := &Appeal{ID: 5, UserID: 104, ViolationID: 54, Status: StatusPending}

	// Send multiple notifications
	ns.SendSubmissionNotification(context.Background(), appeal, "user@example.com")
	ns.SendApprovalNotification(context.Background(), appeal, "user@example.com", 50.0, "OK")

	notifs, err := ns.GetNotifications(context.Background(), 5)
	if err != nil {
		t.Errorf("Failed to get notifications: %v", err)
	}

	if len(notifs) != 2 {
		t.Errorf("Expected 2 notifications, got %d", len(notifs))
	}
}

// TestMarkAsRead marks notification as read
func TestAppealMarkAsRead(t *testing.T) {
	db := setupNotificationTestDB(t)
	ns := NewAppealNotificationService(db)

	appeal := &Appeal{ID: 6, UserID: 105, ViolationID: 55, Status: StatusPending}
	ns.SendSubmissionNotification(context.Background(), appeal, "user@example.com")

	// Get notification ID
	var notif AppealNotificationRecord
	db.Table("appeal_notifications").
		Where("appeal_id = ?", 6).
		First(&notif)

	// Mark as read
	err := ns.MarkAsRead(context.Background(), notif.ID)
	if err != nil {
		t.Errorf("Failed to mark as read: %v", err)
	}

	// Verify opened_at is set
	var updated Notification
	db.Table("appeal_notifications").
		Where("id = ?", notif.ID).
		First(&updated)

	if updated.OpenedAt == nil {
		t.Errorf("OpenedAt not set after MarkAsRead")
	}
}

// TestGetNotificationStats returns notification statistics
func TestGetNotificationStats(t *testing.T) {
	db := setupNotificationTestDB(t)
	ns := NewAppealNotificationService(db)

	// Create several notifications
	for i := 1; i <= 5; i++ {
		appeal := &Appeal{
			ID:     int32(i),
			UserID: 100 + i,
			Status: StatusPending,
		}
		ns.SendSubmissionNotification(context.Background(), appeal, "user@example.com")
	}

	stats, err := ns.GetNotificationStats(context.Background())
	if err != nil {
		t.Errorf("Failed to get stats: %v", err)
	}

	if totalNotif, exists := stats["total_notifications"]; exists {
		if totalNotif.(int64) < 5 {
			t.Errorf("Expected at least 5 notifications, got %v", totalNotif)
		}
	}
}

// TestNotificationChannels tests different notification channels
func TestNotificationChannels(t *testing.T) {
	channels := []NotificationChannel{
		ChannelEmail,
		ChannelInApp,
		ChannelSMS,
	}

	for _, channel := range channels {
		if channel == "" {
			t.Errorf("Notification channel is empty")
		}
	}
}

// TestNotificationTypes tests notification type enum
func TestNotificationTypes(t *testing.T) {
	types := []NotificationType{
		NotificationSubmitted,
		AppealNotificationApproved,
		NotificationDenied,
		NotificationExpired,
	}

	for _, notifType := range types {
		if notifType == "" {
			t.Errorf("Notification type is empty")
		}
	}
}

// BenchmarkSendNotification benchmarks notification sending
func BenchmarkSendNotification(b *testing.B) {
	db := setupNotificationTestDB(&testing.T{})
	ns := NewAppealNotificationService(db)

	appeal := &Appeal{
		ID:          100,
		UserID:      1000,
		ViolationID: 5000,
		Status:      StatusPending,
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		ns.SendApprovalNotification(
			context.Background(),
			appeal,
			"user@example.com",
			50.0,
			"Test",
		)
	}
}

// BenchmarkGetNotifications benchmarks notification retrieval
func BenchmarkAppealGetNotifications(b *testing.B) {
	db := setupNotificationTestDB(&testing.T{})
	ns := NewAppealNotificationService(db)

	appeal := &Appeal{ID: 101, UserID: 1001, Status: StatusPending}
	for i := 0; i < 10; i++ {
		ns.SendSubmissionNotification(context.Background(), appeal, "user@example.com")
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		ns.GetNotifications(context.Background(), 101)
	}
}
