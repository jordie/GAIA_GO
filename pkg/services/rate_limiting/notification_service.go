package rate_limiting

import (
	"context"
	"fmt"
	"sync"
	"time"

	"gorm.io/gorm"
)

// NotificationType defines types of reputation notifications
type NotificationType string

const (
	NotificationTierChange    NotificationType = "tier_change"
	NotificationViolation     NotificationType = "violation"
	NotificationVIPAssigned   NotificationType = "vip_assigned"
	NotificationVIPExpiring   NotificationType = "vip_expiring"
	NotificationVIPExpired    NotificationType = "vip_expired"
	NotificationReputationLow NotificationType = "reputation_low"
	NotificationFlagged       NotificationType = "flagged"
	NotificationTrusted       NotificationType = "trusted"
)

// Notification represents a reputation system notification
type Notification struct {
	ID            int                `json:"id" gorm:"primaryKey"`
	UserID        int                `json:"user_id" gorm:"index"`
	Type          NotificationType   `json:"type" gorm:"index"`
	Title         string             `json:"title"`
	Message       string             `json:"message"`
	OldValue      string             `json:"old_value"`
	NewValue      string             `json:"new_value"`
	Read          bool               `json:"read"`
	SentAt        time.Time          `json:"sent_at"`
	AcknowledgedAt *time.Time         `json:"acknowledged_at"`
	CreatedAt     time.Time          `json:"created_at" gorm:"index"`
}

// NotificationChannel defines how notifications are delivered
type NotificationChannel string

const (
	ChannelEmail NotificationChannel = "email"
	ChannelSMS   NotificationChannel = "sms"
	ChannelInApp NotificationChannel = "in_app"
	ChannelSlack NotificationChannel = "slack"
)

// NotificationPreferences defines user notification settings
type NotificationPreferences struct {
	ID                    int                `json:"id" gorm:"primaryKey"`
	UserID                int                `json:"user_id" gorm:"uniqueIndex"`
	EnableTierNotifications bool              `json:"enable_tier_notifications" gorm:"default:true"`
	EnableViolationAlerts  bool              `json:"enable_violation_alerts" gorm:"default:true"`
	EnableVIPNotifications bool              `json:"enable_vip_notifications" gorm:"default:true"`
	PreferredChannels     string            `json:"preferred_channels"` // JSON array: email,in_app,slack
	NotifyOnViolation     bool              `json:"notify_on_violation" gorm:"default:false"`
	NotifyOnDecay         bool              `json:"notify_on_decay" gorm:"default:false"`
	AggregateDaily        bool              `json:"aggregate_daily" gorm:"default:true"`
	CreatedAt             time.Time         `json:"created_at"`
	UpdatedAt             time.Time         `json:"updated_at"`
}

// NotificationService manages reputation notifications
type NotificationService struct {
	db     *gorm.DB
	queue  chan *Notification
	mu     sync.RWMutex
	active bool
}

// NewNotificationService creates a notification service
func NewNotificationService(db *gorm.DB) *NotificationService {
	ns := &NotificationService{
		db:    db,
		queue: make(chan *Notification, 1000),
	}

	// Start background worker
	go ns.startWorker()

	return ns
}

// NotifyTierChange sends notification when tier changes
func (ns *NotificationService) NotifyTierChange(userID int, oldTier, newTier string, score int) error {
	title := fmt.Sprintf("Reputation Tier Changed: %s → %s", oldTier, newTier)
	message := fmt.Sprintf("Your reputation tier has changed from %s to %s (score: %d)", oldTier, newTier, score)

	if newTier == "flagged" {
		message += ". Your rate limits have been reduced due to multiple violations."
	} else if newTier == "trusted" {
		message += ". Congratulations! Your rate limits have been increased due to good behavior."
	}

	return ns.sendNotification(userID, NotificationTierChange, title, message, oldTier, newTier)
}

// NotifyViolation sends notification of rate limit violation
func (ns *NotificationService) NotifyViolation(userID int, resourceType string, severity int) error {
	title := "Rate Limit Violation Detected"
	severityLabel := "standard"
	if severity == 3 {
		severityLabel = "critical (login attempt)"
	} else if severity == 1 {
		severityLabel = "minor (API call)"
	}

	message := fmt.Sprintf("You exceeded the rate limit for %s (%s severity). Your reputation has been reduced.", resourceType, severityLabel)

	return ns.sendNotification(userID, NotificationViolation, title, message, "", "")
}

// NotifyVIPAssigned sends notification when VIP tier is assigned
func (ns *NotificationService) NotifyVIPAssigned(userID int, tier string, expiresAt *time.Time) error {
	title := fmt.Sprintf("VIP Tier Assigned: %s", tier)
	message := fmt.Sprintf("You have been assigned VIP tier: %s with 2.0x rate limits", tier)

	if expiresAt != nil {
		daysUntil := time.Until(*expiresAt).Hours() / 24
		message += fmt.Sprintf(". This tier expires in %.0f days.", daysUntil)
	}

	return ns.sendNotification(userID, NotificationVIPAssigned, title, message, "", tier)
}

// NotifyVIPExpiring sends notification when VIP is about to expire
func (ns *NotificationService) NotifyVIPExpiring(userID int, tier string, expiresAt time.Time) error {
	daysUntil := time.Until(expiresAt).Hours() / 24
	title := "VIP Tier Expiring Soon"
	message := fmt.Sprintf("Your %s VIP tier expires in %.0f days. Contact support to renew.", tier, daysUntil)

	return ns.sendNotification(userID, NotificationVIPExpiring, title, message, tier, "expiring")
}

// NotifyVIPExpired sends notification when VIP expires
func (ns *NotificationService) NotifyVIPExpired(userID int, tier string) error {
	title := "VIP Tier Expired"
	message := fmt.Sprintf("Your %s VIP tier has expired. You now have standard rate limits.", tier)

	return ns.sendNotification(userID, NotificationVIPExpired, title, message, tier, "expired")
}

// NotifyFlagged sends notification when user is flagged
func (ns *NotificationService) NotifyFlagged(userID int, reason string) error {
	title := "Account Flagged for Review"
	message := fmt.Sprintf("Your account has been flagged due to multiple rate limit violations. Reason: %s. Your rate limits have been reduced to 50%% of normal.", reason)

	return ns.sendNotification(userID, NotificationFlagged, title, message, "", "flagged")
}

// NotifyTrusted sends notification when user reaches trusted tier
func (ns *NotificationService) NotifyTrusted(userID int) error {
	title := "Congratulations: Trusted Tier Reached"
	message := "Your account has reached the Trusted tier due to consistent good behavior. Your rate limits have been increased to 150%% of normal. Keep it up!"

	return ns.sendNotification(userID, NotificationTrusted, title, message, "", "trusted")
}

// sendNotification queues a notification
func (ns *NotificationService) sendNotification(userID int, notifType NotificationType, title, message, oldValue, newValue string) error {
	notification := &Notification{
		UserID:    userID,
		Type:      notifType,
		Title:     title,
		Message:   message,
		OldValue:  oldValue,
		NewValue:  newValue,
		Read:      false,
		SentAt:    time.Now(),
		CreatedAt: time.Now(),
	}

	// Queue for async processing
	select {
	case ns.queue <- notification:
		return nil
	default:
		// Queue full, save directly
		return ns.saveNotification(notification)
	}
}

// saveNotification saves notification to database
func (ns *NotificationService) saveNotification(notif *Notification) error {
	return ns.db.Create(notif).Error
}

// GetNotifications retrieves user notifications
func (ns *NotificationService) GetNotifications(userID int, unreadOnly bool, limit int) ([]Notification, error) {
	var notifications []Notification
	query := ns.db.Where("user_id = ?", userID)

	if unreadOnly {
		query = query.Where("read = ?", false)
	}

	err := query.
		Order("created_at DESC").
		Limit(limit).
		Find(&notifications).Error

	return notifications, err
}

// MarkAsRead marks notification as read
func (ns *NotificationService) MarkAsRead(notificationID int) error {
	return ns.db.Model(&Notification{}).
		Where("id = ?", notificationID).
		Update("read", true).Error
}

// MarkAllAsRead marks all user notifications as read
func (ns *NotificationService) MarkAllAsRead(userID int) error {
	return ns.db.Model(&Notification{}).
		Where("user_id = ?", userID).
		Update("read", true).Error
}

// AcknowledgeNotification marks notification as acknowledged
func (ns *NotificationService) AcknowledgeNotification(notificationID int) error {
	now := time.Now()
	return ns.db.Model(&Notification{}).
		Where("id = ?", notificationID).
		Updates(map[string]interface{}{
			"read":              true,
			"acknowledged_at":   now,
		}).Error
}

// GetNotificationPreferences gets user notification preferences
func (ns *NotificationService) GetNotificationPreferences(userID int) (*NotificationPreferences, error) {
	prefs := &NotificationPreferences{}
	err := ns.db.Where("user_id = ?", userID).First(prefs).Error

	if err == gorm.ErrRecordNotFound {
		// Create default preferences
		prefs = &NotificationPreferences{
			UserID:                     userID,
			EnableTierNotifications:    true,
			EnableViolationAlerts:      true,
			EnableVIPNotifications:     true,
			PreferredChannels:          `["in_app","email"]`,
			NotifyOnViolation:          false,
			NotifyOnDecay:              false,
			AggregateDaily:             true,
			CreatedAt:                  time.Now(),
			UpdatedAt:                  time.Now(),
		}

		if err := ns.db.Create(prefs).Error; err != nil {
			return nil, err
		}

		return prefs, nil
	}

	return prefs, err
}

// UpdateNotificationPreferences updates user notification preferences
func (ns *NotificationService) UpdateNotificationPreferences(userID int, prefs map[string]interface{}) error {
	prefs["updated_at"] = time.Now()
	return ns.db.Model(&NotificationPreferences{}).
		Where("user_id = ?", userID).
		Updates(prefs).Error
}

// GetUnreadCount returns count of unread notifications
func (ns *NotificationService) GetUnreadCount(userID int) (int64, error) {
	var count int64
	err := ns.db.Model(&Notification{}).
		Where("user_id = ? AND read = ?", userID, false).
		Count(&count).Error
	return count, err
}

// GetNotificationStats returns notification statistics
func (ns *NotificationService) GetNotificationStats(userID int) (map[string]interface{}, error) {
	var stats struct {
		Total       int64
		Unread      int64
		TierChanges int64
		Violations  int64
		VIPEvents   int64
	}

	ns.db.Model(&Notification{}).
		Where("user_id = ?", userID).
		Count(&stats.Total)

	ns.db.Model(&Notification{}).
		Where("user_id = ? AND read = ?", userID, false).
		Count(&stats.Unread)

	ns.db.Model(&Notification{}).
		Where("user_id = ? AND type IN ?", userID, []NotificationType{
			NotificationTierChange,
		}).
		Count(&stats.TierChanges)

	ns.db.Model(&Notification{}).
		Where("user_id = ? AND type = ?", userID, NotificationViolation).
		Count(&stats.Violations)

	ns.db.Model(&Notification{}).
		Where("user_id = ? AND type IN ?", userID, []NotificationType{
			NotificationVIPAssigned,
			NotificationVIPExpiring,
			NotificationVIPExpired,
		}).
		Count(&stats.VIPEvents)

	return map[string]interface{}{
		"total":         stats.Total,
		"unread":        stats.Unread,
		"tier_changes":  stats.TierChanges,
		"violations":    stats.Violations,
		"vip_events":    stats.VIPEvents,
	}, nil
}

// startWorker starts background worker for processing notifications
func (ns *NotificationService) startWorker() {
	ns.mu.Lock()
	ns.active = true
	ns.mu.Unlock()

	for notification := range ns.queue {
		if notification == nil {
			break
		}

		// Save notification
		ns.saveNotification(notification)

		// Send via configured channels (email, Slack, etc.)
		// TODO: Implement actual delivery
		ns.deliverNotification(notification)
	}

	ns.mu.Lock()
	ns.active = false
	ns.mu.Unlock()
}

// deliverNotification sends notification via configured channels
func (ns *NotificationService) deliverNotification(notif *Notification) {
	prefs, err := ns.GetNotificationPreferences(notif.UserID)
	if err != nil {
		return
	}

	// Parse preferred channels from JSON
	// TODO: Parse prefs.PreferredChannels and deliver accordingly

	// Example deliveries (would be implemented):
	// - Email: Send via SMTP
	// - SMS: Send via Twilio/similar
	// - Slack: Send via Slack webhook
	// - In-app: Already saved to database
}

// CleanupOldNotifications removes old notifications
func (ns *NotificationService) CleanupOldNotifications(before time.Time) (int64, error) {
	result := ns.db.Where("created_at < ?", before).Delete(&Notification{})
	return result.RowsAffected, result.Error
}

// Close stops the notification service
func (ns *NotificationService) Close() error {
	ns.mu.Lock()
	defer ns.mu.Unlock()

	if ns.active {
		close(ns.queue)
	}

	return nil
}
