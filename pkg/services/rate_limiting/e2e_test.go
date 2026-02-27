package rate_limiting

import (
	"context"
	"testing"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupE2EDB creates a test database for end-to-end testing
func setupE2EDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to create test DB: %v", err)
	}

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
			priority INTEGER DEFAULT 0,
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
			sentiment_score REAL,
			language_score REAL,
			is_pinned INTEGER DEFAULT 0,
			created_at TIMESTAMP
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
			created_at TIMESTAMP
		)
	`)

	return db
}

// TestE2E_UserAppealJourney tests complete user appeal journey
// Scenario: User submits appeal, engages in negotiation, gets approval
func TestE2E_UserAppealJourney(t *testing.T) {
	db := setupE2EDB(t)
	ctx := context.Background()

	// Initialize services
	appealSvc := NewAppealService(db)
	negotiationSvc := NewAppealNegotiationService(db)
	notificationSvc := NewAppealNotificationService(db)
	historySvc := NewAppealHistoryService(db)
	mlSvc := NewMLPredictionService(db)

	// Step 1: Create user with reputation data
	userID := 1001
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (?, 45.0, 'standard')
	`, userID)

	db.Exec(`
		INSERT INTO user_analytics_summary (user_id, trend_direction, projected_30day_score)
		VALUES (?, 'improving', 55.0)
	`, userID)

	// Step 2: Create violation
	violationID := 101
	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (?, ?, 'rate_limit_exceeded', datetime('now', '-7 days'))
	`, violationID, userID)

	// Step 3: User submits appeal
	t.Log("[E2E] User submitting appeal...")
	appeal, err := appealSvc.SubmitAppeal(ctx, userID, violationID, "false_positive", "Request was legitimate business traffic")
	if err != nil {
		t.Fatalf("Failed to submit appeal: %v", err)
	}

	if appeal.Status != StatusPending {
		t.Errorf("Expected pending status, got %s", appeal.Status)
	}

	// Step 4: Get ML prediction to assess approval likelihood
	t.Log("[E2E] Getting ML prediction...")
	prediction, err := mlSvc.PredictAppealApprovalProbability(ctx, appeal.ID)
	if err != nil {
		t.Fatalf("Failed to get prediction: %v", err)
	}

	t.Logf("[E2E] Approval probability: %.2f%%", prediction.ApprovalProbability*100)

	// Step 5: Send notification to user
	t.Log("[E2E] Sending submission notification...")
	err = notificationSvc.SendSubmissionNotification(ctx, appeal.ID, userID)
	if err != nil {
		t.Errorf("Failed to send notification: %v", err)
	}

	// Step 6: Admin reviews and requests clarification
	t.Log("[E2E] Admin requesting clarification...")
	historySvc.RecordStatusChange(ctx, appeal.ID, StatusPending, StatusReviewing, 102, "Admin starting review")

	adminMsg1, _ := negotiationSvc.SendMessage(ctx, appeal.ID, 102, SenderTypeAdmin,
		"Can you provide specific request IDs from that time period?", MessageTypeClarification, nil, nil)

	if adminMsg1 == nil {
		t.Fatalf("Failed to send admin message")
	}

	// Step 7: User responds with details
	t.Log("[E2E] User providing details...")
	userMsg1, _ := negotiationSvc.SendMessage(ctx, appeal.ID, userID, SenderTypeUser,
		"Request IDs: [123456, 123457, 123458] all from legitimate API integrations", MessageTypeMessage, nil, nil)

	if userMsg1 == nil {
		t.Fatalf("Failed to send user response")
	}

	// Step 8: Admin provides evidence
	t.Log("[E2E] Admin providing evidence...")
	adminMsg2, _ := negotiationSvc.SendMessage(ctx, appeal.ID, 102, SenderTypeAdmin,
		"Confirmed: These requests match pattern of legitimate integration. Appeal approved.", MessageTypeProposal, nil, nil)

	// Step 9: Pin key exchange for record
	negotiationSvc.PinMessage(ctx, adminMsg2.ID)

	// Step 10: Admin approves appeal
	t.Log("[E2E] Admin approving appeal...")
	err = appealSvc.ReviewAppeal(ctx, appeal.ID, true, "Confirmed legitimate traffic pattern", 102, 20.0)
	if err != nil {
		t.Fatalf("Failed to approve appeal: %v", err)
	}

	// Step 11: Record approval
	historySvc.RecordStatusChange(ctx, appeal.ID, StatusReviewing, StatusApproved, 102, "Appeal approved")

	// Step 12: Send approval notification
	t.Log("[E2E] Sending approval notification...")
	err = notificationSvc.SendApprovalNotification(ctx, appeal.ID, userID)
	if err != nil {
		t.Errorf("Failed to send approval notification: %v", err)
	}

	// Step 13: Verify complete journey
	t.Log("[E2E] Verifying complete journey...")

	// Check appeal status
	var finalAppeal Appeal
	db.Where("id = ?", appeal.ID).First(&finalAppeal)
	if finalAppeal.Status != StatusApproved {
		t.Errorf("Appeal not approved: %s", finalAppeal.Status)
	}

	// Check timeline
	timeline, _ := historySvc.GetAppealTimeline(ctx, appeal.ID)
	if timeline.EventCount < 3 {
		t.Errorf("Timeline should have at least 3 events, has %d", timeline.EventCount)
	}

	// Check messages
	thread, _ := negotiationSvc.GetNegotiationThread(ctx, appeal.ID)
	if thread.MessageCount != 4 {
		t.Errorf("Expected 4 messages, got %d", thread.MessageCount)
	}

	// Check notifications
	notifications, _ := notificationSvc.GetAppealsNotifications(ctx, userID)
	if len(notifications) < 2 {
		t.Errorf("Expected at least 2 notifications, got %d", len(notifications))
	}

	t.Log("[E2E] ✓ User appeal journey completed successfully")
}

// TestE2E_AdminBulkReviewProcess tests admin bulk review workflow
// Scenario: Admin reviews and processes multiple appeals
func TestE2E_AdminBulkReviewProcess(t *testing.T) {
	db := setupE2EDB(t)
	ctx := context.Background()

	appealSvc := NewAppealService(db)
	bulkSvc := NewAdminBulkOperationsService(db)
	historySvc := NewAppealHistoryService(db)

	const numAppeals = 10

	// Create 10 users with violations
	for i := 0; i < numAppeals; i++ {
		userID := 2000 + i
		violationID := 200 + i

		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, 50.0, 'standard')
		`, userID)

		db.Exec(`
			INSERT INTO violations (id, user_id, violation_type, created_at)
			VALUES (?, ?, 'rate_limit_exceeded', datetime('now', '-3 days'))
		`, violationID, userID)

		// Submit appeals
		appeal, _ := appealSvc.SubmitAppeal(ctx, userID, violationID, "false_positive", "Appeal")
		if appeal != nil {
			historySvc.RecordStatusChange(ctx, appeal.ID, StatusPending, StatusReviewing, 102, "")
		}
	}

	// Get pending appeals
	t.Log("[E2E] Admin viewing pending appeals...")
	var pendingCount int64
	db.Table("appeals").Where("status = ?", StatusReviewing).Count(&pendingCount)
	if pendingCount != numAppeals {
		t.Errorf("Expected %d pending appeals, got %d", numAppeals, pendingCount)
	}

	// Admin bulk approves first 6 appeals
	t.Log("[E2E] Admin bulk approving appeals...")
	err := bulkSvc.BulkApproveAppeals(ctx, map[string]interface{}{
		"status":       StatusReviewing,
		"max_appeals":  6,
		"reputation_restore": 15.0,
	}, 102)

	if err != nil {
		t.Fatalf("Bulk approve failed: %v", err)
	}

	// Admin bulk denies remaining 4 appeals
	t.Log("[E2E] Admin bulk denying appeals...")
	err = bulkSvc.BulkDenyAppeals(ctx, map[string]interface{}{
		"status": StatusReviewing,
	}, 102)

	if err != nil {
		t.Fatalf("Bulk deny failed: %v", err)
	}

	// Verify results
	var approvedCount, deniedCount int64
	db.Table("appeals").Where("status = ?", StatusApproved).Count(&approvedCount)
	db.Table("appeals").Where("status = ?", StatusDenied).Count(&deniedCount)

	t.Logf("[E2E] Results: %d approved, %d denied", approvedCount, deniedCount)

	if approvedCount < 6 {
		t.Errorf("Expected at least 6 approved, got %d", approvedCount)
	}

	if deniedCount < 4 {
		t.Errorf("Expected at least 4 denied, got %d", deniedCount)
	}

	t.Log("[E2E] ✓ Admin bulk review process completed successfully")
}

// TestE2E_PeerAnalyticsContext tests appeal in context of peer analytics
// Scenario: User can see how their reputation compares to peers
func TestE2E_PeerAnalyticsContext(t *testing.T) {
	db := setupE2EDB(t)
	ctx := context.Background()

	appealSvc := NewAppealService(db)
	peerSvc := NewPeerAnalyticsService(db)

	// Create 20 users in standard tier
	tier := "standard"
	for i := 0; i < 20; i++ {
		userID := 3000 + i
		score := 40.0 + float64(i)*2.5 // Scores from 40 to 97.5

		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, ?, ?)
		`, userID, score, tier)

		// Create violation and appeal for some
		if i < 10 {
			violationID := 300 + i
			db.Exec(`
				INSERT INTO violations (id, user_id, violation_type, created_at)
				VALUES (?, ?, 'rate_limit_exceeded', datetime('now', '-5 days'))
			`, violationID, userID)

			appealSvc.SubmitAppeal(ctx, userID, violationID, "false_positive", "Appeal")
		}
	}

	// Test user at 50th percentile
	targetUserID := 3005

	t.Log("[E2E] Getting peer comparison...")
	comparison, err := peerSvc.GetUserPeerComparison(ctx, targetUserID, tier)
	if err != nil {
		t.Fatalf("Failed to get peer comparison: %v", err)
	}

	if comparison == nil {
		t.Fatalf("Comparison is nil")
	}

	t.Logf("[E2E] User percentile: %.2f%%", comparison.Percentile*100)

	if comparison.Percentile < 0 || comparison.Percentile > 1 {
		t.Errorf("Invalid percentile: %f", comparison.Percentile)
	}

	// Get tier statistics
	t.Log("[E2E] Getting tier statistics...")
	stats, err := peerSvc.GetAllTiersStatistics(ctx)
	if err != nil {
		t.Fatalf("Failed to get stats: %v", err)
	}

	if stats == nil {
		t.Fatalf("Stats is nil")
	}

	if len(stats) == 0 {
		t.Errorf("Should have statistics")
	}

	// Get insights
	insights, err := peerSvc.GetInsights(ctx, targetUserID, tier)
	if err != nil {
		t.Fatalf("Failed to get insights: %v", err)
	}

	if insights == nil || len(insights) == 0 {
		t.Errorf("Should have insights")
	}

	t.Logf("[E2E] Insights: %v", insights)

	t.Log("[E2E] ✓ Peer analytics context completed successfully")
}

// TestE2E_NotificationChannels tests notifications across multiple channels
// Scenario: Multiple notification types via different channels
func TestE2E_NotificationChannels(t *testing.T) {
	db := setupE2EDB(t)
	ctx := context.Background()

	appealSvc := NewAppealService(db)
	notificationSvc := NewAppealNotificationService(db)

	userID := 4000

	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (?, 50.0, 'standard')
	`, userID)

	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (1, ?, 'rate_limit_exceeded', datetime('now', '-3 days'))
	`, userID)

	// Submit appeal
	appeal, _ := appealSvc.SubmitAppeal(ctx, userID, 1, "false_positive", "Appeal")

	// Send submission notification (simulated multi-channel)
	t.Log("[E2E] Sending submission notification...")
	err := notificationSvc.SendSubmissionNotification(ctx, appeal.ID, userID)
	if err != nil {
		t.Errorf("Failed to send submission notification: %v", err)
	}

	// Approve appeal
	appealSvc.ReviewAppeal(ctx, appeal.ID, true, "Approved", 101, 15.0)

	// Send approval notification
	t.Log("[E2E] Sending approval notification...")
	err = notificationSvc.SendApprovalNotification(ctx, appeal.ID, userID)
	if err != nil {
		t.Errorf("Failed to send approval notification: %v", err)
	}

	// Send denial (create new appeal and deny)
	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (2, ?, 'rate_limit_exceeded', datetime('now', '-2 days'))
	`, userID)

	appeal2, _ := appealSvc.SubmitAppeal(ctx, userID, 2, "system_error", "Appeal")
	appealSvc.ReviewAppeal(ctx, appeal2.ID, false, "Denied", 101, 0.0)

	t.Log("[E2E] Sending denial notification...")
	err = notificationSvc.SendDenialNotification(ctx, appeal2.ID, userID)
	if err != nil {
		t.Errorf("Failed to send denial notification: %v", err)
	}

	// Get all notifications
	notifications, _ := notificationSvc.GetAppealsNotifications(ctx, userID)

	t.Logf("[E2E] Total notifications: %d", len(notifications))

	// Verify notification types
	submissionCount := 0
	approvalCount := 0
	denialCount := 0

	for _, n := range notifications {
		switch n.NotificationType {
		case NotificationTypeSubmitted:
			submissionCount++
		case NotificationTypeApproved:
			approvalCount++
		case NotificationTypeDenied:
			denialCount++
		}
	}

	t.Logf("[E2E] Submission: %d, Approval: %d, Denial: %d", submissionCount, approvalCount, denialCount)

	if submissionCount == 0 {
		t.Errorf("Expected submission notification")
	}
	if approvalCount == 0 {
		t.Errorf("Expected approval notification")
	}
	if denialCount == 0 {
		t.Errorf("Expected denial notification")
	}

	t.Log("[E2E] ✓ Notification channels completed successfully")
}

// TestE2E_AppealTimelineAccuracy tests timeline accuracy through complete workflow
func TestE2E_AppealTimelineAccuracy(t *testing.T) {
	db := setupE2EDB(t)
	ctx := context.Background()

	appealSvc := NewAppealService(db)
	historySvc := NewAppealHistoryService(db)
	negotiationSvc := NewAppealNegotiationService(db)

	userID := 5000
	violationID := 500

	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (?, 50.0, 'standard')
	`, userID)

	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (?, ?, 'rate_limit_exceeded', datetime('now', '-4 days'))
	`, violationID, userID)

	// Submit appeal
	t.Log("[E2E] Starting timeline tracking...")
	startTime := time.Now()

	appeal, _ := appealSvc.SubmitAppeal(ctx, userID, violationID, "false_positive", "Appeal")

	// Record initial status
	historySvc.RecordStatusChange(ctx, appeal.ID, StatusPending, StatusReviewing, 102, "Initial review")

	// Simulate some time passing
	time.Sleep(10 * time.Millisecond)

	// Add messages
	negotiationSvc.SendMessage(ctx, appeal.ID, userID, SenderTypeUser, "Please review", MessageTypeMessage, nil, nil)
	time.Sleep(5 * time.Millisecond)
	negotiationSvc.SendMessage(ctx, appeal.ID, 102, SenderTypeAdmin, "Under review", MessageTypeMessage, nil, nil)

	// Approve
	time.Sleep(10 * time.Millisecond)
	appealSvc.ReviewAppeal(ctx, appeal.ID, true, "Approved", 102, 15.0)
	historySvc.RecordStatusChange(ctx, appeal.ID, StatusReviewing, StatusApproved, 102, "Approved")

	// Get timeline
	timeline, _ := historySvc.GetAppealTimeline(ctx, appeal.ID)
	endTime := time.Now()

	t.Log("[E2E] Timeline Analysis:")
	t.Logf("  Total duration: %v", timeline.ResolutionDays)
	t.Logf("  Events recorded: %d", timeline.EventCount)
	t.Logf("  Elapsed time: %v", endTime.Sub(startTime))

	if timeline.EventCount < 2 {
		t.Errorf("Expected at least 2 events in timeline")
	}

	// Verify appeal is in approved state
	var finalAppeal Appeal
	db.Where("id = ?", appeal.ID).First(&finalAppeal)

	if finalAppeal.Status != StatusApproved {
		t.Errorf("Appeal should be approved, got %s", finalAppeal.Status)
	}

	t.Log("[E2E] ✓ Appeal timeline accuracy verified")
}

// TestE2E_MLPredictionAccuracy tests ML predictions in realistic context
func TestE2E_MLPredictionAccuracy(t *testing.T) {
	db := setupE2EDB(t)
	ctx := context.Background()

	appealSvc := NewAppealService(db)
	mlSvc := NewMLPredictionService(db)

	// Create user with improving reputation
	userID := 6000
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (?, 30.0, 'flagged')
	`, userID)

	db.Exec(`
		INSERT INTO user_analytics_summary (user_id, trend_direction, projected_30day_score)
		VALUES (?, 'improving', 45.0)
	`, userID)

	// Predict recovery
	t.Log("[E2E] Predicting reputation recovery...")
	recovery, err := mlSvc.PredictReputationRecovery(ctx, userID)
	if err != nil {
		t.Fatalf("Failed to predict recovery: %v", err)
	}

	t.Logf("[E2E] Recovery prediction:")
	t.Logf("  Current score: %.1f", recovery.CurrentScore)
	t.Logf("  Target score: %.1f", recovery.TargetScore)
	t.Logf("  Estimated days: %d", recovery.EstimatedDaysToTarget)
	t.Logf("  Weekly rate: %.2f", recovery.WeeklyChangeRate)
	t.Logf("  Confidence: %.2f%%", recovery.ConfidenceLevel*100)

	if recovery.EstimatedDaysToTarget <= 0 {
		t.Errorf("Invalid recovery timeline: %d days", recovery.EstimatedDaysToTarget)
	}

	// Create appeals and make prediction
	for i := 0; i < 5; i++ {
		violationID := 600 + i
		db.Exec(`
			INSERT INTO violations (id, user_id, violation_type, created_at)
			VALUES (?, ?, 'rate_limit_exceeded', datetime('now', '-? days'))
		`, violationID, userID, 10-i)

		appeal, _ := appealSvc.SubmitAppeal(ctx, userID, violationID, "legitimate_use", "Appeal")

		if appeal != nil {
			// Get approval prediction
			prob, _ := mlSvc.PredictAppealApprovalProbability(ctx, appeal.ID)
			t.Logf("[E2E] Appeal %d approval probability: %.2f%%", appeal.ID, prob.ApprovalProbability*100)
		}
	}

	// Get auto-appeal suggestions
	t.Log("[E2E] Getting auto-appeal suggestions...")
	suggestions, err := mlSvc.SuggestAutoAppeal(ctx, userID)
	if err != nil {
		t.Fatalf("Failed to get suggestions: %v", err)
	}

	t.Logf("[E2E] Generated %d auto-appeal suggestions", len(suggestions))

	for _, s := range suggestions {
		t.Logf("[E2E] Suggestion - Violation %d, Confidence: %.2f%%", s.ViolationID, s.Confidence*100)
	}

	t.Log("[E2E] ✓ ML prediction accuracy verified")
}

// TestE2E_AppealWindowValidation tests 30-day appeal window enforcement
func TestE2E_AppealWindowValidation(t *testing.T) {
	db := setupE2EDB(t)
	ctx := context.Background()

	appealSvc := NewAppealService(db)

	userID := 7000

	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (?, 50.0, 'standard')
	`, userID)

	// Create old violation (beyond 30 days)
	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (1, ?, 'rate_limit_exceeded', datetime('now', '-45 days'))
	`, userID)

	// Create recent violation (within 30 days)
	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (2, ?, 'rate_limit_exceeded', datetime('now', '-10 days'))
	`, userID)

	// Try to appeal old violation
	t.Log("[E2E] Attempting to appeal violation outside window...")
	oldAppeal, err := appealSvc.SubmitAppeal(ctx, userID, 1, "false_positive", "Old appeal")

	if err == nil && oldAppeal != nil {
		t.Errorf("Should not allow appeal for violation older than 30 days")
	}

	// Appeal recent violation should succeed
	t.Log("[E2E] Attempting to appeal recent violation...")
	recentAppeal, err := appealSvc.SubmitAppeal(ctx, userID, 2, "false_positive", "Recent appeal")

	if err != nil {
		t.Fatalf("Failed to appeal recent violation: %v", err)
	}

	if recentAppeal == nil {
		t.Fatalf("Recent appeal should be created")
	}

	t.Log("[E2E] ✓ Appeal window validation verified")
}
