package rate_limiting

import (
	"testing"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupTestDB creates in-memory SQLite database for testing
func setupTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to create test DB: %v", err)
	}

	// Create tables
	db.AutoMigrate(&Notification{}, &NotificationPreferences{})

	return db
}

// TestNotificationCreation tests creating notifications
func TestNotificationCreation(t *testing.T) {
	db := setupTestDB(t)
	ns := NewNotificationService(db)
	defer ns.Close()

	userID := 1
	err := ns.NotifyTierChange(userID, "standard", "trusted", 85)
	if err != nil {
		t.Fatalf("Failed to create notification: %v", err)
	}

	// Allow time for async processing
	time.Sleep(100 * time.Millisecond)

	notifications, err := ns.GetNotifications(userID, false, 10)
	if err != nil {
		t.Fatalf("Failed to get notifications: %v", err)
	}

	if len(notifications) == 0 {
		t.Errorf("Expected notification to be created")
	}

	if len(notifications) > 0 && notifications[0].Type != NotificationTierChange {
		t.Errorf("Expected tier change notification, got %s", notifications[0].Type)
	}
}

// TestViolationNotification tests violation notifications
func TestViolationNotification(t *testing.T) {
	db := setupTestDB(t)
	ns := NewNotificationService(db)
	defer ns.Close()

	userID := 2
	err := ns.NotifyViolation(userID, "api_call", 2)
	if err != nil {
		t.Fatalf("Failed to create violation notification: %v", err)
	}

	time.Sleep(100 * time.Millisecond)

	notifications, err := ns.GetNotifications(userID, false, 10)
	if err != nil {
		t.Fatalf("Failed to get notifications: %v", err)
	}

	if len(notifications) == 0 {
		t.Errorf("Expected violation notification to be created")
	}

	if len(notifications) > 0 && notifications[0].Type != NotificationViolation {
		t.Errorf("Expected violation notification, got %s", notifications[0].Type)
	}
}

// TestMarkAsRead tests marking notifications as read
func TestMarkAsRead(t *testing.T) {
	db := setupTestDB(t)
	ns := NewNotificationService(db)
	defer ns.Close()

	userID := 3
	ns.NotifyTierChange(userID, "standard", "flagged", 15)

	time.Sleep(100 * time.Millisecond)

	notifications, _ := ns.GetNotifications(userID, false, 10)
	if len(notifications) == 0 {
		t.Fatalf("No notifications created")
	}

	notifID := notifications[0].ID
	err := ns.MarkAsRead(notifID)
	if err != nil {
		t.Fatalf("Failed to mark as read: %v", err)
	}

	updated, _ := ns.GetNotifications(userID, false, 10)
	if len(updated) > 0 && updated[0].Read != true {
		t.Errorf("Notification should be marked as read")
	}
}

// TestUnreadCount tests unread notification counting
func TestUnreadCount(t *testing.T) {
	db := setupTestDB(t)
	ns := NewNotificationService(db)
	defer ns.Close()

	userID := 4
	for i := 0; i < 5; i++ {
		ns.NotifyViolation(userID, "api", 1)
	}

	time.Sleep(200 * time.Millisecond)

	count, err := ns.GetUnreadCount(userID)
	if err != nil {
		t.Fatalf("Failed to get unread count: %v", err)
	}

	if count != 5 {
		t.Errorf("Expected 5 unread, got %d", count)
	}

	// Mark all as read
	ns.MarkAllAsRead(userID)

	count, _ = ns.GetUnreadCount(userID)
	if count != 0 {
		t.Errorf("Expected 0 unread after marking all read, got %d", count)
	}
}

// TestVIPNotifications tests VIP-related notifications
func TestVIPNotifications(t *testing.T) {
	db := setupTestDB(t)
	ns := NewNotificationService(db)
	defer ns.Close()

	userID := 5

	// Test VIP assigned
	err := ns.NotifyVIPAssigned(userID, "premium", nil)
	if err != nil {
		t.Fatalf("Failed to create VIP assigned notification: %v", err)
	}

	// Test VIP expiring
	expiresAt := time.Now().AddDate(0, 0, 7)
	err = ns.NotifyVIPExpiring(userID, "premium", expiresAt)
	if err != nil {
		t.Fatalf("Failed to create VIP expiring notification: %v", err)
	}

	// Test VIP expired
	err = ns.NotifyVIPExpired(userID, "premium")
	if err != nil {
		t.Fatalf("Failed to create VIP expired notification: %v", err)
	}

	time.Sleep(200 * time.Millisecond)

	notifications, _ := ns.GetNotifications(userID, false, 10)
	vipCount := 0
	for _, notif := range notifications {
		if notif.Type == NotificationVIPAssigned ||
			notif.Type == NotificationVIPExpiring ||
			notif.Type == NotificationVIPExpired {
			vipCount++
		}
	}

	if vipCount != 3 {
		t.Errorf("Expected 3 VIP notifications, got %d", vipCount)
	}
}

// TestNotificationPreferences tests preference management
func TestNotificationPreferences(t *testing.T) {
	db := setupTestDB(t)
	ns := NewNotificationService(db)
	defer ns.Close()

	userID := 6

	// Get default preferences
	prefs, err := ns.GetNotificationPreferences(userID)
	if err != nil {
		t.Fatalf("Failed to get preferences: %v", err)
	}

	if !prefs.EnableTierNotifications {
		t.Errorf("Expected tier notifications enabled by default")
	}

	// Update preferences
	updates := map[string]interface{}{
		"enable_tier_notifications": false,
		"aggregate_daily":           false,
	}

	err = ns.UpdateNotificationPreferences(userID, updates)
	if err != nil {
		t.Fatalf("Failed to update preferences: %v", err)
	}

	// Verify updates
	updated, _ := ns.GetNotificationPreferences(userID)
	if updated.EnableTierNotifications != false {
		t.Errorf("Expected tier notifications disabled after update")
	}
	if updated.AggregateDaily != false {
		t.Errorf("Expected aggregate daily disabled after update")
	}
}

// TestNotificationStats tests statistics calculation
func TestNotificationStats(t *testing.T) {
	db := setupTestDB(t)
	ns := NewNotificationService(db)
	defer ns.Close()

	userID := 7

	// Create various notifications
	ns.NotifyTierChange(userID, "standard", "flagged", 20)
	ns.NotifyViolation(userID, "api", 1)
	ns.NotifyViolation(userID, "api", 1)
	ns.NotifyFlagged(userID, "suspicious activity")
	ns.NotifyTrusted(userID)

	time.Sleep(200 * time.Millisecond)

	stats, err := ns.GetNotificationStats(userID)
	if err != nil {
		t.Fatalf("Failed to get stats: %v", err)
	}

	if stats["total"].(int64) != 5 {
		t.Errorf("Expected 5 total notifications, got %d", stats["total"])
	}

	if stats["violations"].(int64) != 2 {
		t.Errorf("Expected 2 violations, got %d", stats["violations"])
	}
}

// TestFlaggedNotification tests flagged tier notification
func TestFlaggedNotification(t *testing.T) {
	db := setupTestDB(t)
	ns := NewNotificationService(db)
	defer ns.Close()

	userID := 8
	err := ns.NotifyFlagged(userID, "multiple rate limit violations")
	if err != nil {
		t.Fatalf("Failed to create flagged notification: %v", err)
	}

	time.Sleep(100 * time.Millisecond)

	notifications, _ := ns.GetNotifications(userID, false, 10)
	if len(notifications) == 0 || notifications[0].Type != NotificationFlagged {
		t.Errorf("Expected flagged notification")
	}
}

// TestTrustedNotification tests trusted tier notification
func TestTrustedNotification(t *testing.T) {
	db := setupTestDB(t)
	ns := NewNotificationService(db)
	defer ns.Close()

	userID := 9
	err := ns.NotifyTrusted(userID)
	if err != nil {
		t.Fatalf("Failed to create trusted notification: %v", err)
	}

	time.Sleep(100 * time.Millisecond)

	notifications, _ := ns.GetNotifications(userID, false, 10)
	if len(notifications) == 0 || notifications[0].Type != NotificationTrusted {
		t.Errorf("Expected trusted notification")
	}
}

// TestAcknowledgeNotification tests acknowledging notifications
func TestAcknowledgeNotification(t *testing.T) {
	db := setupTestDB(t)
	ns := NewNotificationService(db)
	defer ns.Close()

	userID := 10
	ns.NotifyTierChange(userID, "standard", "trusted", 85)

	time.Sleep(100 * time.Millisecond)

	notifications, _ := ns.GetNotifications(userID, false, 10)
	notifID := notifications[0].ID

	err := ns.AcknowledgeNotification(notifID)
	if err != nil {
		t.Fatalf("Failed to acknowledge notification: %v", err)
	}

	updated, _ := ns.GetNotifications(userID, false, 10)
	if len(updated) > 0 {
		if updated[0].Read != true || updated[0].AcknowledgedAt == nil {
			t.Errorf("Notification should be read and acknowledged")
		}
	}
}

// BenchmarkNotificationCreation benchmarks notification creation
func BenchmarkNotificationCreation(b *testing.B) {
	db := setupTestDB(&testing.T{})
	ns := NewNotificationService(db)
	defer ns.Close()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		ns.NotifyTierChange(1, "standard", "trusted", 85)
	}
}

// BenchmarkGetNotifications benchmarks notification retrieval
func BenchmarkGetNotifications(b *testing.B) {
	db := setupTestDB(&testing.T{})
	ns := NewNotificationService(db)
	defer ns.Close()

	// Create some notifications
	for i := 0; i < 100; i++ {
		ns.NotifyViolation(1, "api", 1)
	}

	time.Sleep(200 * time.Millisecond)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		ns.GetNotifications(1, false, 50)
	}
}
