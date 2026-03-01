package rate_limiting

import (
	"context"
	"testing"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupIntegrationTestDB creates a complete test database with all tables
func setupIntegrationTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to create test DB: %v", err)
	}

	// Create all necessary tables
	db.Exec(`
		CREATE TABLE reputation_scores (
			id INTEGER PRIMARY KEY,
			user_id INTEGER UNIQUE,
			score REAL,
			tier TEXT
		)
	`)

	db.Exec(`
		CREATE TABLE user_analytics_summary (
			id INTEGER PRIMARY KEY,
			user_id INTEGER UNIQUE,
			trend_direction TEXT,
			projected_30day_score REAL
		)
	`)

	db.Exec(`
		CREATE TABLE violations (
			id INTEGER PRIMARY KEY,
			user_id INTEGER,
			violation_type TEXT,
			created_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE appeals (
			id INTEGER PRIMARY KEY,
			user_id INTEGER,
			violation_id INTEGER,
			reason TEXT,
			status TEXT,
			priority INTEGER,
			created_at TIMESTAMP,
			resolved_at TIMESTAMP,
			approved_points REAL
		)
	`)

	db.Exec(`
		CREATE TABLE appeal_status_changes (
			id INTEGER PRIMARY KEY,
			appeal_id INTEGER,
			old_status TEXT,
			new_status TEXT,
			changed_by INTEGER,
			reason TEXT,
			metadata TEXT,
			created_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE appeal_negotiation_messages (
			id INTEGER PRIMARY KEY,
			appeal_id INTEGER,
			sender_id INTEGER,
			sender_type TEXT,
			message TEXT,
			message_type TEXT,
			metadata TEXT,
			sentiment_score REAL,
			language_score REAL,
			is_pinned INTEGER DEFAULT 0,
			created_at TIMESTAMP,
			updated_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE appeal_notifications (
			id INTEGER PRIMARY KEY,
			appeal_id INTEGER,
			user_id INTEGER,
			notification_type TEXT,
			channel TEXT,
			status TEXT,
			sent_at TIMESTAMP,
			opened_at TIMESTAMP,
			created_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE ml_predictions (
			id INTEGER PRIMARY KEY,
			appeal_id INTEGER,
			user_id INTEGER,
			prediction_type TEXT,
			prediction_value REAL,
			confidence REAL,
			model_version TEXT,
			predicted_at TIMESTAMP,
			actual_value REAL,
			accuracy_checked_at TIMESTAMP,
			created_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE auto_appeal_suggestions (
			id INTEGER PRIMARY KEY,
			user_id INTEGER,
			violation_id INTEGER,
			suggestion_reason TEXT,
			confidence REAL,
			predicted_success_rate REAL,
			user_accepted INTEGER DEFAULT 0,
			created_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE peer_reputation_stats (
			id INTEGER PRIMARY KEY,
			user_id INTEGER,
			tier TEXT,
			percentile REAL,
			avg_score REAL,
			created_at TIMESTAMP
		)
	`)

	return db
}

// TestFullAppealLifecycle tests complete appeal workflow from submission to resolution
func TestFullAppealLifecycle(t *testing.T) {
	db := setupIntegrationTestDB(t)
	ctx := context.Background()

	// Initialize services
	appealSvc := NewAppealService(db)
	historySvc := NewAppealHistoryService(db)
	notificationSvc := NewAppealNotificationService(db)
	analyticsSvc := NewAnalyticsService(db)

	// Setup: Create user with reputation score
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (100, 40.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO user_analytics_summary (user_id, trend_direction, projected_30day_score)
		VALUES (100, 'improving', 50.0)
	`)

	// Step 1: Create a violation
	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (1, 100, 'rate_limit_exceeded', datetime('now', '-10 days'))
	`)

	// Step 2: Submit appeal
	appeal, err := appealSvc.SubmitAppeal(ctx, 100, 1, "false_positive", "The request was legitimate")
	if err != nil {
		t.Fatalf("Failed to submit appeal: %v", err)
	}

	if appeal.Status != StatusPending {
		t.Errorf("Appeal status should be pending, got %s", appeal.Status)
	}

	// Step 3: Record status change (to reviewing)
	err = historySvc.RecordStatusChange(ctx, appeal.ID, StatusPending, StatusReviewing, 101, "Admin started review")
	if err != nil {
		t.Errorf("Failed to record status change: %v", err)
	}

	// Step 4: Send notification
	err = notificationSvc.SendSubmissionNotification(ctx, appeal.ID, 100)
	if err != nil {
		t.Errorf("Failed to send notification: %v", err)
	}

	// Step 5: Approve appeal
	err = appealSvc.ReviewAppeal(ctx, appeal.ID, true, "Confirmed false positive", 101, 15.0)
	if err != nil {
		t.Errorf("Failed to approve appeal: %v", err)
	}

	// Verify approval
	var updatedAppeal Appeal
	db.Where("id = ?", appeal.ID).First(&updatedAppeal)
	if updatedAppeal.Status != StatusApproved {
		t.Errorf("Appeal should be approved, got %s", updatedAppeal.Status)
	}

	// Step 6: Record approval status change
	err = historySvc.RecordStatusChange(ctx, appeal.ID, StatusReviewing, StatusApproved, 101, "Appeal approved")
	if err != nil {
		t.Errorf("Failed to record approval: %v", err)
	}

	// Step 7: Send approval notification
	err = notificationSvc.SendApprovalNotification(ctx, appeal.ID, 100)
	if err != nil {
		t.Errorf("Failed to send approval notification: %v", err)
	}

	// Step 8: Get appeal timeline
	timeline, err := historySvc.GetAppealTimeline(ctx, appeal.ID)
	if err != nil {
		t.Errorf("Failed to get timeline: %v", err)
	}

	if timeline.EventCount != 3 { // pending->reviewing, reviewing->approved, notifications
		t.Errorf("Expected 3+ events in timeline, got %d", timeline.EventCount)
	}

	// Step 9: Get analytics for user
	trends, err := analyticsSvc.GetReputationTrends(ctx, 100, 7)
	if err != nil {
		t.Errorf("Failed to get trends: %v", err)
	}

	if trends == nil {
		t.Errorf("Trends should not be nil")
	}

	t.Log("✓ Full appeal lifecycle completed successfully")
}

// TestMultipleAppealsWorkflow tests handling multiple concurrent appeals
func TestMultipleAppealsWorkflow(t *testing.T) {
	db := setupIntegrationTestDB(t)
	ctx := context.Background()

	appealSvc := NewAppealService(db)
	notificationSvc := NewAppealNotificationService(db)

	// Setup: Create user with violations
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (200, 50.0, 'standard')
	`)

	// Create 5 violations
	for i := 1; i <= 5; i++ {
		db.Exec(`
			INSERT INTO violations (id, user_id, violation_type, created_at)
			VALUES (?, 200, 'rate_limit_exceeded', datetime('now', '-? days'))
		`, i, (10-i))
	}

	// Submit multiple appeals
	appealIDs := make([]int, 0)
	for i := 1; i <= 5; i++ {
		appeal, err := appealSvc.SubmitAppeal(ctx, 200, i, "false_positive", "Legitimate traffic")
		if err != nil {
			t.Fatalf("Failed to submit appeal %d: %v", i, err)
		}
		appealIDs = append(appealIDs, appeal.ID)
	}

	// Verify all appeals created
	if len(appealIDs) != 5 {
		t.Errorf("Expected 5 appeals, got %d", len(appealIDs))
	}

	// Approve first 3
	for i := 0; i < 3; i++ {
		err := appealSvc.ReviewAppeal(ctx, appealIDs[i], true, "Approved", 101, 10.0)
		if err != nil {
			t.Fatalf("Failed to approve appeal %d: %v", i, err)
		}

		// Send notification
		notificationSvc.SendApprovalNotification(ctx, appealIDs[i], 200)
	}

	// Deny last 2
	for i := 3; i < 5; i++ {
		err := appealSvc.ReviewAppeal(ctx, appealIDs[i], false, "Denied", 101, 0.0)
		if err != nil {
			t.Fatalf("Failed to deny appeal %d: %v", i, err)
		}

		// Send notification
		notificationSvc.SendDenialNotification(ctx, appealIDs[i], 200)
	}

	// Verify results
	var approvedCount, deniedCount int64
	db.Table("appeals").Where("user_id = 200 AND status = ?", StatusApproved).Count(&approvedCount)
	db.Table("appeals").Where("user_id = 200 AND status = ?", StatusDenied).Count(&deniedCount)

	if approvedCount != 3 {
		t.Errorf("Expected 3 approved appeals, got %d", approvedCount)
	}

	if deniedCount != 2 {
		t.Errorf("Expected 2 denied appeals, got %d", deniedCount)
	}

	t.Log("✓ Multiple appeals workflow completed successfully")
}

// TestAppealWithNegotiation tests appeal with back-and-forth negotiation
func TestAppealWithNegotiation(t *testing.T) {
	db := setupIntegrationTestDB(t)
	ctx := context.Background()

	appealSvc := NewAppealService(db)
	negotiationSvc := NewAppealNegotiationService(db)
	historySvc := NewAppealHistoryService(db)

	// Setup
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (300, 35.0, 'flagged')
	`)

	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (100, 300, 'rate_limit_exceeded', datetime('now', '-5 days'))
	`)

	// Submit appeal
	appeal, err := appealSvc.SubmitAppeal(ctx, 300, 100, "system_error", "System error caused spike")
	if err != nil {
		t.Fatalf("Failed to submit appeal: %v", err)
	}

	// Record status change
	historySvc.RecordStatusChange(ctx, appeal.ID, StatusPending, StatusReviewing, 101, "Under review")

	// User sends message
	msg1, err := negotiationSvc.SendMessage(ctx, appeal.ID, 300, SenderTypeUser, "Can you review the logs?", MessageTypeQuestion, nil, nil)
	if err != nil {
		t.Fatalf("Failed to send user message: %v", err)
	}

	if msg1 == nil {
		t.Fatalf("Message should not be nil")
	}

	// Admin responds
	msg2, err := negotiationSvc.SendMessage(ctx, appeal.ID, 101, SenderTypeAdmin, "Checking the logs now", MessageTypeMessage, nil, nil)
	if err != nil {
		t.Fatalf("Failed to send admin message: %v", err)
	}

	// Admin sends clarification request
	msg3, err := negotiationSvc.SendMessage(ctx, appeal.ID, 101, SenderTypeAdmin, "What time did the spike occur?", MessageTypeClarification, nil, nil)
	if err != nil {
		t.Fatalf("Failed to send clarification: %v", err)
	}

	// User provides more details
	msg4, err := negotiationSvc.SendMessage(ctx, appeal.ID, 300, SenderTypeUser, "Between 14:00 and 14:30 UTC", MessageTypeMessage, nil, nil)
	if err != nil {
		t.Fatalf("Failed to send user detail: %v", err)
	}

	// Get thread
	thread, err := negotiationSvc.GetNegotiationThread(ctx, appeal.ID)
	if err != nil {
		t.Fatalf("Failed to get thread: %v", err)
	}

	if thread.MessageCount != 4 {
		t.Errorf("Expected 4 messages, got %d", thread.MessageCount)
	}

	if thread.UserMessages != 2 {
		t.Errorf("Expected 2 user messages, got %d", thread.UserMessages)
	}

	if thread.AdminMessages != 2 {
		t.Errorf("Expected 2 admin messages, got %d", thread.AdminMessages)
	}

	// Pin important message
	err = negotiationSvc.PinMessage(ctx, msg3.ID)
	if err != nil {
		t.Errorf("Failed to pin message: %v", err)
	}

	// Get pinned messages
	pinned, err := negotiationSvc.GetPinnedMessages(ctx, appeal.ID)
	if err != nil {
		t.Errorf("Failed to get pinned messages: %v", err)
	}

	if len(pinned) != 1 {
		t.Errorf("Expected 1 pinned message, got %d", len(pinned))
	}

	// Approve appeal based on negotiation
	err = appealSvc.ReviewAppeal(ctx, appeal.ID, true, "Confirmed system error from logs", 101, 20.0)
	if err != nil {
		t.Errorf("Failed to approve appeal: %v", err)
	}

	historySvc.RecordStatusChange(ctx, appeal.ID, StatusReviewing, StatusApproved, 101, "Approved after review")

	t.Log("✓ Appeal with negotiation workflow completed successfully")
}

// TestPredictionInformsDecision tests ML predictions guiding appeal decisions
func TestPredictionInformsDecision(t *testing.T) {
	db := setupIntegrationTestDB(t)
	ctx := context.Background()

	appealSvc := NewAppealService(db)
	mlSvc := NewMLPredictionService(db)

	// Setup: User with good appeal history
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (400, 45.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO user_analytics_summary (user_id, trend_direction, projected_30day_score)
		VALUES (400, 'improving', 60.0)
	`)

	// Create violations
	for i := 1; i <= 3; i++ {
		db.Exec(`
			INSERT INTO violations (id, user_id, violation_type, created_at)
			VALUES (?, 400, 'rate_limit_exceeded', datetime('now', '-? days'))
		`, i, (10-i))
	}

	// Create successful appeals for same user
	for i := 1; i <= 3; i++ {
		db.Exec(`
			INSERT INTO appeals (id, user_id, violation_id, reason, status, created_at)
			VALUES (?, 400, ?, 'false_positive', 'approved', datetime('now', '-30 days'))
		`, i, i)
	}

	// Get recovery prediction
	recovery, err := mlSvc.PredictReputationRecovery(ctx, 400)
	if err != nil {
		t.Fatalf("Failed to predict recovery: %v", err)
	}

	if recovery.ConfidenceLevel <= 0 || recovery.ConfidenceLevel > 1 {
		t.Errorf("Invalid confidence level: %f", recovery.ConfidenceLevel)
	}

	// Submit new appeal
	violation := 100
	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (?, 400, 'rate_limit_exceeded', datetime('now', '-2 days'))
	`, violation)

	appeal, _ := appealSvc.SubmitAppeal(ctx, 400, violation, "system_error", "System error spike")

	// Get approval probability
	probability, err := mlSvc.PredictAppealApprovalProbability(ctx, appeal.ID)
	if err != nil {
		t.Fatalf("Failed to predict probability: %v", err)
	}

	// User with good history should have higher approval probability
	if probability.ApprovalProbability < 0.5 {
		t.Logf("Warning: Expected higher approval probability for user with good history, got %f", probability.ApprovalProbability)
	}

	// Verify confidence sum
	totalProb := probability.ApprovalProbability + probability.DenialProbability
	if totalProb < 0.99 || totalProb > 1.01 {
		t.Errorf("Probabilities should sum to 1.0, got %f", totalProb)
	}

	t.Log("✓ ML prediction workflow completed successfully")
}

// TestAppealDeduplication tests duplicate appeal prevention
func TestAppealDeduplication(t *testing.T) {
	db := setupIntegrationTestDB(t)
	ctx := context.Background()

	appealSvc := NewAppealService(db)

	// Setup
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (500, 60.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (1, 500, 'rate_limit_exceeded', datetime('now', '-5 days'))
	`)

	// Submit first appeal
	appeal1, err := appealSvc.SubmitAppeal(ctx, 500, 1, "false_positive", "First appeal")
	if err != nil {
		t.Fatalf("Failed to submit first appeal: %v", err)
	}

	// Try to submit duplicate appeal
	appeal2, err := appealSvc.SubmitAppeal(ctx, 500, 1, "false_positive", "Duplicate appeal")
	if err == nil {
		t.Errorf("Should have rejected duplicate appeal")
	}

	if appeal2 != nil {
		t.Errorf("Should not return appeal for duplicate submission")
	}

	// Verify only one appeal exists
	var count int64
	db.Table("appeals").Where("user_id = 500 AND violation_id = 1").Count(&count)
	if count != 1 {
		t.Errorf("Expected 1 appeal, got %d", count)
	}

	t.Log("✓ Appeal deduplication working correctly")
}

// TestNotificationDeliveryWorkflow tests complete notification workflow
func TestNotificationDeliveryWorkflow(t *testing.T) {
	db := setupIntegrationTestDB(t)
	ctx := context.Background()

	appealSvc := NewAppealService(db)
	notificationSvc := NewAppealNotificationService(db)

	// Setup
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (600, 50.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (1, 600, 'rate_limit_exceeded', datetime('now', '-5 days'))
	`)

	// Submit appeal and send notification
	appeal, _ := appealSvc.SubmitAppeal(ctx, 600, 1, "false_positive", "Appeal text")
	notificationSvc.SendSubmissionNotification(ctx, appeal.ID, 600)

	// Approve and notify
	appealSvc.ReviewAppeal(ctx, appeal.ID, true, "Approved", 101, 10.0)
	notificationSvc.SendApprovalNotification(ctx, appeal.ID, 600)

	// Get notifications
	notifications, err := notificationSvc.GetAppealsNotifications(ctx, 600)
	if err != nil {
		t.Errorf("Failed to get notifications: %v", err)
	}

	if len(notifications) < 2 {
		t.Errorf("Expected at least 2 notifications, got %d", len(notifications))
	}

	// Mark first notification as read
	if len(notifications) > 0 {
		err := notificationSvc.MarkAsRead(ctx, notifications[0].ID)
		if err != nil {
			t.Errorf("Failed to mark notification as read: %v", err)
		}
	}

	// Get stats
	stats, err := notificationSvc.GetNotificationStats(ctx)
	if err != nil {
		t.Errorf("Failed to get stats: %v", err)
	}

	if stats == nil {
		t.Errorf("Stats should not be nil")
	}

	t.Log("✓ Notification delivery workflow completed successfully")
}

// TestAnalyticsAcrossAppealLifecycle tests analytics at different stages
func TestAnalyticsAcrossAppealLifecycle(t *testing.T) {
	db := setupIntegrationTestDB(t)
	ctx := context.Background()

	appealSvc := NewAppealService(db)
	analyticsSvc := NewAnalyticsService(db)
	historySvc := NewAppealHistoryService(db)

	// Setup
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (700, 40.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO user_analytics_summary (user_id, trend_direction, projected_30day_score)
		VALUES (700, 'improving', 55.0)
	`)

	// Create 10 violations
	for i := 1; i <= 10; i++ {
		db.Exec(`
			INSERT INTO violations (id, user_id, violation_type, created_at)
			VALUES (?, 700, 'rate_limit_exceeded', datetime('now', '-? days'))
		`, i, (30-i*3))
	}

	// Submit 10 appeals with mixed outcomes
	for i := 1; i <= 10; i++ {
		appeal, _ := appealSvc.SubmitAppeal(ctx, 700, i, "false_positive", "Appeal text")
		historySvc.RecordStatusChange(ctx, appeal.ID, StatusPending, StatusReviewing, 101, "")

		// Approve half, deny half
		if i <= 5 {
			appealSvc.ReviewAppeal(ctx, appeal.ID, true, "Approved", 101, 10.0)
			historySvc.RecordStatusChange(ctx, appeal.ID, StatusReviewing, StatusApproved, 101, "")
		} else {
			appealSvc.ReviewAppeal(ctx, appeal.ID, false, "Denied", 101, 0.0)
			historySvc.RecordStatusChange(ctx, appeal.ID, StatusReviewing, StatusDenied, 101, "")
		}
	}

	// Get trends
	trends, err := analyticsSvc.GetReputationTrends(ctx, 700, 30)
	if err != nil {
		t.Errorf("Failed to get trends: %v", err)
	}

	if trends == nil {
		t.Errorf("Trends should not be nil")
	}

	// Get patterns
	patterns, err := analyticsSvc.GetBehaviorPatterns(ctx, 700)
	if err != nil {
		t.Errorf("Failed to get patterns: %v", err)
	}

	if patterns == nil {
		t.Errorf("Patterns should not be nil")
	}

	// Get recommendations
	recommendations, err := analyticsSvc.GenerateRecommendations(ctx, 700)
	if err != nil {
		t.Errorf("Failed to get recommendations: %v", err)
	}

	if recommendations == nil || len(recommendations) == 0 {
		t.Errorf("Should have recommendations")
	}

	// Get appeal stats
	stats, err := analyticsSvc.GetUserAppealStatistics(ctx, 700)
	if err != nil {
		t.Errorf("Failed to get appeal stats: %v", err)
	}

	if stats == nil {
		t.Errorf("Stats should not be nil")
	}

	t.Log("✓ Analytics across appeal lifecycle completed successfully")
}

// TestConcurrentOperationsSafety tests thread-safe operations
func TestConcurrentOperationsSafety(t *testing.T) {
	db := setupIntegrationTestDB(t)
	ctx := context.Background()

	appealSvc := NewAppealService(db)
	negotiationSvc := NewAppealNegotiationService(db)

	// Setup
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (800, 50.0, 'standard')
	`)

	// Create multiple violations
	for i := 1; i <= 5; i++ {
		db.Exec(`
			INSERT INTO violations (id, user_id, violation_type, created_at)
			VALUES (?, 800, 'rate_limit_exceeded', datetime('now', '-? days'))
		`, i, (10-i))
	}

	// Submit appeals concurrently
	done := make(chan bool, 5)
	errors := make(chan error, 5)

	for i := 1; i <= 5; i++ {
		go func(violationID int) {
			appeal, err := appealSvc.SubmitAppeal(ctx, 800, violationID, "false_positive", "Appeal")
			if err != nil {
				errors <- err
			}

			// Send concurrent messages
			if appeal != nil {
				for j := 0; j < 3; j++ {
					_, msgErr := negotiationSvc.SendMessage(ctx, appeal.ID, 800, SenderTypeUser, "Message", MessageTypeMessage, nil, nil)
					if msgErr != nil {
						errors <- msgErr
					}
				}
			}

			done <- true
		}(i)
	}

	// Wait for completion
	for i := 0; i < 5; i++ {
		<-done
	}

	// Check for errors
	select {
	case err := <-errors:
		t.Errorf("Concurrent operation failed: %v", err)
	default:
	}

	// Verify all appeals created
	var appealCount int64
	db.Table("appeals").Where("user_id = 800").Count(&appealCount)
	if appealCount != 5 {
		t.Errorf("Expected 5 appeals, got %d", appealCount)
	}

	// Verify all messages created
	var messageCount int64
	db.Table("appeal_negotiation_messages").Count(&messageCount)
	if messageCount != 15 { // 5 appeals * 3 messages each
		t.Errorf("Expected 15 messages, got %d", messageCount)
	}

	t.Log("✓ Concurrent operations safety verified")
}

// BenchmarkFullAppealWorkflow benchmarks complete appeal workflow
func BenchmarkFullAppealWorkflow(b *testing.B) {
	db := setupIntegrationTestDB(&testing.T{})
	ctx := context.Background()

	appealSvc := NewAppealService(db)
	notificationSvc := NewAppealNotificationService(db)
	negotiationSvc := NewAppealNegotiationService(db)
	historySvc := NewAppealHistoryService(db)

	// Setup
	for i := 0; i < 100; i++ {
		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, ?, 'standard')
		`, 1000+i, 50.0)

		db.Exec(`
			INSERT INTO violations (id, user_id, violation_type, created_at)
			VALUES (?, ?, 'rate_limit_exceeded', datetime('now', '-5 days'))
		`, 1000+i, 1000+i)
	}

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		userID := 1000 + (i % 100)
		violationID := 1000 + (i % 100)

		// Submit appeal
		appeal, _ := appealSvc.SubmitAppeal(ctx, userID, violationID, "false_positive", "Appeal")

		if appeal != nil {
			// Record status change
			historySvc.RecordStatusChange(ctx, appeal.ID, StatusPending, StatusReviewing, 101, "")

			// Send messages
			negotiationSvc.SendMessage(ctx, appeal.ID, userID, SenderTypeUser, "Question?", MessageTypeQuestion, nil, nil)
			negotiationSvc.SendMessage(ctx, appeal.ID, 101, SenderTypeAdmin, "Response", MessageTypeMessage, nil, nil)

			// Send notifications
			notificationSvc.SendSubmissionNotification(ctx, appeal.ID, userID)

			// Review and approve
			appealSvc.ReviewAppeal(ctx, appeal.ID, true, "Approved", 101, 10.0)
			notificationSvc.SendApprovalNotification(ctx, appeal.ID, userID)
		}
	}
}

// BenchmarkConcurrentAppeals benchmarks concurrent appeal submissions
func BenchmarkConcurrentAppeals(b *testing.B) {
	db := setupIntegrationTestDB(&testing.T{})
	ctx := context.Background()

	appealSvc := NewAppealService(db)

	// Setup
	for i := 0; i < 1000; i++ {
		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, ?, 'standard')
		`, 2000+i, 50.0)

		db.Exec(`
			INSERT INTO violations (id, user_id, violation_type, created_at)
			VALUES (?, ?, 'rate_limit_exceeded', datetime('now', '-5 days'))
		`, 2000+i, 2000+i)
	}

	b.ResetTimer()

	done := make(chan bool, 10)

	for i := 0; i < b.N; i++ {
		go func(userID int) {
			violationID := userID
			appealSvc.SubmitAppeal(ctx, userID, violationID, "false_positive", "Appeal")
			done <- true
		}(2000 + (i % 1000))

		if (i+1)%10 == 0 {
			for j := 0; j < 10; j++ {
				<-done
			}
		}
	}
}

// BenchmarkNegotiationThreadRetrieval benchmarks getting large negotiation threads
func BenchmarkNegotiationThreadRetrieval(b *testing.B) {
	db := setupIntegrationTestDB(&testing.T{})
	ctx := context.Background()

	negotiationSvc := NewAppealNegotiationService(db)

	// Setup: Create appeal with many messages
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (3000, 50.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (1, 3000, 'rate_limit_exceeded', datetime('now', '-5 days'))
	`)

	db.Exec(`
		INSERT INTO appeals (id, user_id, violation_id, reason, status, created_at)
		VALUES (1, 3000, 1, 'false_positive', 'reviewing', datetime('now'))
	`)

	// Create 1000 messages
	for i := 0; i < 1000; i++ {
		senderType := "user"
		if i%2 == 0 {
			senderType = "admin"
		}

		db.Exec(`
			INSERT INTO appeal_negotiation_messages
			(appeal_id, sender_id, sender_type, message, message_type, created_at)
			VALUES (1, ?, ?, ?, 'message', datetime('now', '-? seconds'))
		`, 3000+(i%2), senderType, "Message "+string(rune('0'+(i%10))), i)
	}

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		negotiationSvc.GetNegotiationThread(ctx, 1)
	}
}
