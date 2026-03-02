package rate_limiting

import (
	"context"
	"fmt"
	"net/smtp"
	"os"
	"time"

	"gorm.io/gorm"
)

// AppealNotificationType represents the type of notification
type AppealNotificationType string

const (
	AppealNotificationSubmitted AppealNotificationType = "submitted"
	AppealNotificationApproved  AppealNotificationType = "approved"
	AppealNotificationDenied    AppealNotificationType = "denied"
	AppealNotificationExpired   AppealNotificationType = "expired"
	AppealNotificationUpdate    AppealNotificationType = "status_update"
)

// AppealNotificationChannel represents the delivery channel
type AppealNotificationChannel string

const (
	AppealChannelEmail  AppealNotificationChannel = "email"
	AppealChannelInApp  AppealNotificationChannel = "in_app"
	AppealChannelSMS    AppealNotificationChannel = "sms"
)

// AppealNotificationStatus represents delivery status
type AppealNotificationStatus string

const (
	AppealStatusPending AppealNotificationStatus = "pending"
	AppealStatusSent    AppealNotificationStatus = "sent"
	AppealStatusFailed  AppealNotificationStatus = "failed"
	AppealStatusBounced AppealNotificationStatus = "bounced"
)

// AppealNotificationRecord represents a notification record
type AppealNotificationRecord struct {
	ID              int64
	AppealID        int
	UserID          int
	NotificationType AppealNotificationType
	Channel         AppealNotificationChannel
	Recipient       string
	Subject         string
	Body            string
	Status          AppealNotificationStatus
	ErrorMessage    *string
	SentAt          *time.Time
	OpenedAt        *time.Time
	ClickedAt       *time.Time
	CreatedAt       time.Time
}

// AppealNotificationTemplate represents an email template
type AppealNotificationTemplate struct {
	Subject      string
	BodyTemplate string
}

// AppealNotificationService handles appeal notifications
type AppealNotificationService struct {
	db              *gorm.DB
	smtpHost        string
	smtpPort        string
	smtpUsername    string
	smtpPassword    string
	fromEmail       string
	templates       map[AppealNotificationType]AppealNotificationTemplate
}

// NewAppealNotificationService creates a new notification service
func NewAppealNotificationService(db *gorm.DB) *AppealNotificationService {
	ans := &AppealNotificationService{
		db:           db,
		smtpHost:     os.Getenv("SMTP_HOST"),
		smtpPort:     os.Getenv("SMTP_PORT"),
		smtpUsername: os.Getenv("SMTP_USERNAME"),
		smtpPassword: os.Getenv("SMTP_PASSWORD"),
		fromEmail:    os.Getenv("NOTIFICATION_FROM_EMAIL"),
	}

	ans.templates = ans.initializeTemplates()
	return ans
}

// SendApprovalNotification sends notification for approved appeal
func (ans *AppealNotificationService) SendApprovalNotification(
	ctx context.Context,
	appeal *Appeal,
	userEmail string,
	approvedPoints float64,
	comment string,
) error {
	subject := fmt.Sprintf("Your Appeal #%d Has Been Approved", appeal.ID)
	body := fmt.Sprintf(`
Dear User,

Your appeal (ID: %d) for violation #%d has been approved.

Details:
- Violation ID: %d
- Appeal ID: %d
- Reputation Points Restored: %.1f
- Reviewer Notes: %s

Your reputation has been restored. Thank you for appealing and providing context
to help us improve our enforcement systems.

Best regards,
GAIA GO Reputation Team
`, appeal.ID, appeal.ViolationID, appeal.ViolationID, appeal.ID, approvedPoints, comment)

	return ans.sendNotification(
		ctx,
		appeal.ID,
		appeal.UserID,
		userEmail,
		AppealNotificationApproved,
		subject,
		body,
	)
}

// SendDenialNotification sends notification for denied appeal
func (ans *AppealNotificationService) SendDenialNotification(
	ctx context.Context,
	appeal *Appeal,
	userEmail string,
	rejectionReason string,
	comment string,
) error {
	subject := fmt.Sprintf("Your Appeal #%d Has Been Reviewed", appeal.ID)
	body := fmt.Sprintf(`
Dear User,

Your appeal (ID: %d) for violation #%d has been reviewed and was not approved at this time.

Details:
- Violation ID: %d
- Appeal ID: %d
- Rejection Reason: %s
- Reviewer Notes: %s

Appeals are reviewed based on evidence provided and policy compliance.
If you believe this decision is in error, you may review the violation details
and learn more about our reputation policies.

Best regards,
GAIA GO Reputation Team
`, appeal.ID, appeal.ViolationID, appeal.ViolationID, appeal.ID, rejectionReason, comment)

	return ans.sendNotification(
		ctx,
		appeal.ID,
		appeal.UserID,
		userEmail,
		AppealNotificationDenied,
		subject,
		body,
	)
}

// SendSubmissionNotification sends confirmation when appeal is submitted
func (ans *AppealNotificationService) SendSubmissionNotification(
	ctx context.Context,
	appeal *Appeal,
	userEmail string,
) error {
	subject := fmt.Sprintf("We Received Your Appeal #%d", appeal.ID)
	body := fmt.Sprintf(`
Dear User,

Thank you for submitting your appeal for violation #%d.

Appeal Details:
- Appeal ID: %d
- Submitted: %s
- Status: Pending Review
- Expires: %s

Your appeal will be reviewed by our team. We aim to review appeals within 48 business hours.
You will receive an email notification once your appeal has been reviewed.

You can check the status of your appeal at any time in your reputation dashboard.

Best regards,
GAIA GO Reputation Team
`, appeal.ViolationID, appeal.ID, appeal.CreatedAt.Format("2006-01-02 15:04:05"), appeal.ExpiresAt.Format("2006-01-02"))

	return ans.sendNotification(
		ctx,
		appeal.ID,
		appeal.UserID,
		userEmail,
		AppealNotificationSubmitted,
		subject,
		body,
	)
}

// SendExpirationNotification sends notification when appeal expires
func (ans *AppealNotificationService) SendExpirationNotification(
	ctx context.Context,
	appeal *Appeal,
	userEmail string,
) error {
	subject := fmt.Sprintf("Your Appeal #%d Has Expired", appeal.ID)
	body := fmt.Sprintf(`
Dear User,

Your appeal (ID: %d) for violation #%d has expired and can no longer be reviewed.

Appeal Details:
- Appeal ID: %d
- Violation ID: %d
- Expiration Date: %s

Appeals must be submitted within 30 days of the violation. If you believe the violation
is in error, please review our appeals policy for future violations.

Best regards,
GAIA GO Reputation Team
`, appeal.ID, appeal.ViolationID, appeal.ID, appeal.ViolationID, appeal.ExpiresAt.Format("2006-01-02"))

	return ans.sendNotification(
		ctx,
		appeal.ID,
		appeal.UserID,
		userEmail,
		AppealNotificationExpired,
		subject,
		body,
	)
}

// sendNotification sends a notification and records it in the database
func (ans *AppealNotificationService) sendNotification(
	ctx context.Context,
	appealID int,
	userID int,
	recipient string,
	notificationType AppealNotificationType,
	subject string,
	body string,
) error {
	// Record notification in database
	notification := AppealNotificationRecord{
		AppealID:         appealID,
		UserID:           userID,
		NotificationType: notificationType,
		Channel:          AppealChannelEmail,
		Recipient:        recipient,
		Subject:          subject,
		Body:             body,
		Status:           AppealStatusPending,
		CreatedAt:        time.Now(),
	}

	// Save to database
	result := ans.db.WithContext(ctx).Table("appeal_notifications").Create(&notification)
	if result.Error != nil {
		return fmt.Errorf("failed to save notification: %w", result.Error)
	}

	// Send email if configured
	if ans.smtpHost != "" && ans.fromEmail != "" {
		if err := ans.sendEmailNotification(ctx, recipient, subject, body); err != nil {
			// Update notification as failed but don't return error
			ans.db.WithContext(ctx).Table("appeal_notifications").
				Where("id = ?", notification.ID).
				Updates(map[string]interface{}{
					"status":        AppealStatusFailed,
					"error_message": err.Error(),
				})
			return nil // Non-blocking failure
		}

		// Mark as sent
		now := time.Now()
		ans.db.WithContext(ctx).Table("appeal_notifications").
			Where("id = ?", notification.ID).
			Updates(map[string]interface{}{
				"status":  AppealStatusSent,
				"sent_at": now,
			})
	}

	return nil
}

// sendEmailNotification sends an email via SMTP
func (ans *AppealNotificationService) sendEmailNotification(
	ctx context.Context,
	to string,
	subject string,
	body string,
) error {
	if ans.smtpHost == "" || ans.fromEmail == "" {
		return nil // Skip if not configured
	}

	// Format message
	message := fmt.Sprintf("Subject: %s\r\n\r\n%s", subject, body)

	// Send via SMTP
	auth := smtp.PlainAuth("", ans.smtpUsername, ans.smtpPassword, ans.smtpHost)
	addr := fmt.Sprintf("%s:%s", ans.smtpHost, ans.smtpPort)

	return smtp.SendMail(addr, auth, ans.fromEmail, []string{to}, []byte(message))
}

// GetNotifications retrieves notifications for an appeal
func (ans *AppealNotificationService) GetNotifications(
	ctx context.Context,
	appealID int,
) ([]AppealNotificationRecord, error) {
	var notifications []AppealNotificationRecord
	result := ans.db.WithContext(ctx).
		Table("appeal_notifications").
		Where("appeal_id = ?", appealID).
		Order("created_at DESC").
		Scan(&notifications)

	return notifications, result.Error
}

// MarkAsRead marks a notification as read (opened)
func (ans *AppealNotificationService) MarkAsRead(
	ctx context.Context,
	notificationID int64,
) error {
	now := time.Now()
	return ans.db.WithContext(ctx).
		Table("appeal_notifications").
		Where("id = ?", notificationID).
		Update("opened_at", now).Error
}

// GetNotificationStats returns notification statistics
func (ans *AppealNotificationService) GetNotificationStats(
	ctx context.Context,
) (map[string]interface{}, error) {
	var stats struct {
		TotalNotifications  int64
		SentCount          int64
		FailedCount        int64
		OpenedCount        int64
		SubmitNotifications int64
		ApprovalNotifications int64
		DenialNotifications int64
		ExpirationNotifications int64
	}

	ans.db.WithContext(ctx).
		Table("appeal_notifications").
		Select("COUNT(*) as total_notifications").
		Scan(&stats.TotalNotifications)

	ans.db.WithContext(ctx).
		Table("appeal_notifications").
		Where("status = ?", AppealStatusSent).
		Count(&stats.SentCount)

	ans.db.WithContext(ctx).
		Table("appeal_notifications").
		Where("status = ?", AppealStatusFailed).
		Count(&stats.FailedCount)

	ans.db.WithContext(ctx).
		Table("appeal_notifications").
		Where("opened_at IS NOT NULL").
		Count(&stats.OpenedCount)

	ans.db.WithContext(ctx).
		Table("appeal_notifications").
		Where("notification_type = ?", AppealNotificationSubmitted).
		Count(&stats.SubmitNotifications)

	ans.db.WithContext(ctx).
		Table("appeal_notifications").
		Where("notification_type = ?", AppealNotificationApproved).
		Count(&stats.ApprovalNotifications)

	ans.db.WithContext(ctx).
		Table("appeal_notifications").
		Where("notification_type = ?", AppealNotificationDenied).
		Count(&stats.DenialNotifications)

	ans.db.WithContext(ctx).
		Table("appeal_notifications").
		Where("notification_type = ?", AppealNotificationExpired).
		Count(&stats.ExpirationNotifications)

	return map[string]interface{}{
		"total_notifications":          stats.TotalNotifications,
		"sent_count":                   stats.SentCount,
		"failed_count":                 stats.FailedCount,
		"opened_count":                 stats.OpenedCount,
		"submitted_notifications":      stats.SubmitNotifications,
		"approval_notifications":       stats.ApprovalNotifications,
		"denial_notifications":         stats.DenialNotifications,
		"expiration_notifications":     stats.ExpirationNotifications,
		"delivery_rate_percent":        float64(stats.SentCount) / float64(stats.TotalNotifications) * 100,
		"open_rate_percent":            float64(stats.OpenedCount) / float64(stats.SentCount) * 100,
	}, nil
}

// initializeTemplates sets up default notification templates
func (ans *AppealNotificationService) initializeTemplates() map[AppealNotificationType]AppealNotificationTemplate {
	return map[AppealNotificationType]AppealNotificationTemplate{
		AppealNotificationSubmitted: {
			Subject:      "Appeal Received - ID: {{.AppealID}}",
			BodyTemplate: "Your appeal has been received and will be reviewed shortly.",
		},
		AppealNotificationApproved: {
			Subject:      "Appeal Approved - ID: {{.AppealID}}",
			BodyTemplate: "Your appeal has been approved. {{.ApprovedPoints}} reputation points have been restored.",
		},
		AppealNotificationDenied: {
			Subject:      "Appeal Reviewed - ID: {{.AppealID}}",
			BodyTemplate: "Your appeal has been reviewed. Reason: {{.RejectionReason}}",
		},
		AppealNotificationExpired: {
			Subject:      "Appeal Expired - ID: {{.AppealID}}",
			BodyTemplate: "Your appeal has expired and is no longer under review.",
		},
	}
}
