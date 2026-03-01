package rate_limiting

import (
	"context"
	"fmt"
	"testing"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupBenchDB creates an optimized test database for benchmarking
func setupBenchDB(b *testing.B) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		b.Fatalf("Failed to create test DB: %v", err)
	}

	// Optimize for performance testing
	db.Exec("PRAGMA journal_mode=WAL")
	db.Exec("PRAGMA synchronous=NORMAL")
	db.Exec("PRAGMA cache_size=-100000")
	db.Exec("PRAGMA temp_store=MEMORY")

	// Create tables
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
			created_at TIMESTAMP,
			resolved_at TIMESTAMP,
			approved_points REAL
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
			created_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE appeal_status_changes (
			id INTEGER PRIMARY KEY,
			appeal_id INTEGER,
			old_status TEXT,
			new_status TEXT,
			changed_by INTEGER,
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

	db.Exec(`
		CREATE TABLE peer_reputation_stats (
			id INTEGER PRIMARY KEY,
			user_id INTEGER,
			tier TEXT,
			score REAL,
			created_at TIMESTAMP
		)
	`)

	return db
}

// BenchmarkAppealServiceSingleSubmission measures single appeal submission
func BenchmarkAppealServiceSingleSubmission(b *testing.B) {
	db := setupBenchDB(b)
	ctx := context.Background()
	appealSvc := NewAppealService(db)

	// Prepare: Create user and violation
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (1, 50.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (1, 1, 'rate_limit_exceeded', datetime('now', '-5 days'))
	`)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		appealSvc.SubmitAppeal(ctx, 1, 1, "false_positive", "Appeal text")
	}
}

// BenchmarkAppealServiceReview measures appeal review operation
func BenchmarkAppealServiceReview(b *testing.B) {
	db := setupBenchDB(b)
	ctx := context.Background()
	appealSvc := NewAppealService(db)

	// Prepare: Create appeal
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (2, 50.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (1, 2, 'rate_limit_exceeded', datetime('now', '-5 days'))
	`)

	appeal, _ := appealSvc.SubmitAppeal(ctx, 2, 1, "false_positive", "Appeal")

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		appealSvc.ReviewAppeal(ctx, appeal.ID, i%2 == 0, "Decision", 101, 10.0)
	}
}

// BenchmarkNegotiationServiceSendMessage measures message sending latency
func BenchmarkNegotiationServiceSendMessage(b *testing.B) {
	db := setupBenchDB(b)
	ctx := context.Background()
	appealSvc := NewAppealService(db)
	negotiationSvc := NewAppealNegotiationService(db)

	// Prepare
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (3, 50.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (1, 3, 'rate_limit_exceeded', datetime('now', '-5 days'))
	`)

	appeal, _ := appealSvc.SubmitAppeal(ctx, 3, 1, "false_positive", "Appeal")

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		negotiationSvc.SendMessage(ctx, appeal.ID, 3, SenderTypeUser, "Message", MessageTypeMessage, nil, nil)
	}
}

// BenchmarkNegotiationServiceGetThread measures thread retrieval latency
func BenchmarkNegotiationServiceGetThread(b *testing.B) {
	db := setupBenchDB(b)
	ctx := context.Background()
	appealSvc := NewAppealService(db)
	negotiationSvc := NewAppealNegotiationService(db)

	// Prepare: Create appeal with many messages
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (4, 50.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (1, 4, 'rate_limit_exceeded', datetime('now', '-5 days'))
	`)

	appeal, _ := appealSvc.SubmitAppeal(ctx, 4, 1, "false_positive", "Appeal")

	// Add 100 messages
	for i := 0; i < 100; i++ {
		negotiationSvc.SendMessage(ctx, appeal.ID, 4, SenderTypeUser, fmt.Sprintf("Message %d", i), MessageTypeMessage, nil, nil)
	}

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		negotiationSvc.GetNegotiationThread(ctx, appeal.ID)
	}
}

// BenchmarkMLPredictionServiceRecovery measures recovery prediction latency
func BenchmarkMLPredictionServiceRecovery(b *testing.B) {
	db := setupBenchDB(b)
	ctx := context.Background()
	mlSvc := NewMLPredictionService(db)

	// Prepare
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (5, 40.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO user_analytics_summary (user_id, trend_direction, projected_30day_score)
		VALUES (5, 'improving', 55.0)
	`)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		mlSvc.PredictReputationRecovery(ctx, 5)
	}
}

// BenchmarkMLPredictionServiceApprovalProbability measures approval probability latency
func BenchmarkMLPredictionServiceApprovalProbability(b *testing.B) {
	db := setupBenchDB(b)
	ctx := context.Background()
	appealSvc := NewAppealService(db)
	mlSvc := NewMLPredictionService(db)

	// Prepare
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (6, 50.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (1, 6, 'rate_limit_exceeded', datetime('now', '-5 days'))
	`)

	appeal, _ := appealSvc.SubmitAppeal(ctx, 6, 1, "false_positive", "Appeal")

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		mlSvc.PredictAppealApprovalProbability(ctx, appeal.ID)
	}
}

// BenchmarkAnalyticsServiceTrends measures trend analysis latency
func BenchmarkAnalyticsServiceTrends(b *testing.B) {
	db := setupBenchDB(b)
	ctx := context.Background()
	analyticsSvc := NewAnalyticsService(db)

	// Prepare
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (7, 50.0, 'standard')
	`)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		analyticsSvc.GetReputationTrends(ctx, 7, 30)
	}
}

// BenchmarkHistoryServiceRecordChange measures status change recording
func BenchmarkHistoryServiceRecordChange(b *testing.B) {
	db := setupBenchDB(b)
	ctx := context.Background()
	appealSvc := NewAppealService(db)
	historySvc := NewAppealHistoryService(db)

	// Prepare
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (8, 50.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (1, 8, 'rate_limit_exceeded', datetime('now', '-5 days'))
	`)

	appeal, _ := appealSvc.SubmitAppeal(ctx, 8, 1, "false_positive", "Appeal")

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		status := StatusPending
		if i%2 == 0 {
			status = StatusReviewing
		}
		historySvc.RecordStatusChange(ctx, appeal.ID, status, StatusApproved, 101, "Change")
	}
}

// BenchmarkHistoryServiceTimeline measures timeline retrieval
func BenchmarkHistoryServiceTimeline(b *testing.B) {
	db := setupBenchDB(b)
	ctx := context.Background()
	appealSvc := NewAppealService(db)
	historySvc := NewAppealHistoryService(db)

	// Prepare: Create appeal with multiple status changes
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (9, 50.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (1, 9, 'rate_limit_exceeded', datetime('now', '-5 days'))
	`)

	appeal, _ := appealSvc.SubmitAppeal(ctx, 9, 1, "false_positive", "Appeal")

	for i := 0; i < 20; i++ {
		historySvc.RecordStatusChange(ctx, appeal.ID, StatusPending, StatusReviewing, 101, "")
	}

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		historySvc.GetAppealTimeline(ctx, appeal.ID)
	}
}

// BenchmarkPeerAnalyticsComparison measures peer comparison calculation
func BenchmarkPeerAnalyticsComparison(b *testing.B) {
	db := setupBenchDB(b)
	ctx := context.Background()
	peerSvc := NewPeerAnalyticsService(db)

	// Prepare: Create 100 users for peer comparison
	for i := 0; i < 100; i++ {
		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, ?, 'standard')
		`, 9000+i, 40.0+float64(i)*0.6)
	}

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		userID := 9000 + (i % 100)
		peerSvc.GetUserPeerComparison(ctx, userID, "standard")
	}
}

// BenchmarkNotificationServiceSend measures notification sending
func BenchmarkNotificationServiceSend(b *testing.B) {
	db := setupBenchDB(b)
	ctx := context.Background()
	appealSvc := NewAppealService(db)
	notificationSvc := NewAppealNotificationService(db)

	// Prepare
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (10, 50.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO violations (id, user_id, violation_type, created_at)
		VALUES (1, 10, 'rate_limit_exceeded', datetime('now', '-5 days'))
	`)

	appeal, _ := appealSvc.SubmitAppeal(ctx, 10, 1, "false_positive", "Appeal")

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		if i%2 == 0 {
			notificationSvc.SendSubmissionNotification(ctx, appeal.ID, 10)
		} else {
			notificationSvc.SendApprovalNotification(ctx, appeal.ID, 10)
		}
	}
}

// BenchmarkCompleteWorkflowSequential measures complete appeal workflow
func BenchmarkCompleteWorkflowSequential(b *testing.B) {
	db := setupBenchDB(b)
	ctx := context.Background()

	appealSvc := NewAppealService(db)
	negotiationSvc := NewAppealNegotiationService(db)
	historySvc := NewAppealHistoryService(db)
	notificationSvc := NewAppealNotificationService(db)
	mlSvc := NewMLPredictionService(db)

	// Prepare: Create 100 users
	for i := 0; i < 100; i++ {
		userID := 20000 + i
		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, 50.0, 'standard')
		`, userID)

		db.Exec(`
			INSERT INTO user_analytics_summary (user_id, trend_direction, projected_30day_score)
			VALUES (?, 'improving', 60.0)
		`, userID)

		db.Exec(`
			INSERT INTO violations (id, user_id, violation_type, created_at)
			VALUES (?, ?, 'rate_limit_exceeded', datetime('now', '-5 days'))
		`, 20000+i, userID)
	}

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		userID := 20000 + (i % 100)
		violationID := 20000 + (i % 100)

		// Submit appeal
		appeal, _ := appealSvc.SubmitAppeal(ctx, userID, violationID, "false_positive", "Appeal")

		if appeal != nil {
			// Record status
			historySvc.RecordStatusChange(ctx, appeal.ID, StatusPending, StatusReviewing, 101, "")

			// Send messages
			negotiationSvc.SendMessage(ctx, appeal.ID, userID, SenderTypeUser, "Question?", MessageTypeQuestion, nil, nil)
			negotiationSvc.SendMessage(ctx, appeal.ID, 101, SenderTypeAdmin, "Response", MessageTypeMessage, nil, nil)

			// Get prediction
			mlSvc.PredictAppealApprovalProbability(ctx, appeal.ID)

			// Approve
			appealSvc.ReviewAppeal(ctx, appeal.ID, true, "Approved", 101, 15.0)

			// Get timeline
			historySvc.GetAppealTimeline(ctx, appeal.ID)

			// Notify
			notificationSvc.SendApprovalNotification(ctx, appeal.ID, userID)
		}
	}
}

// BenchmarkLargeThreadMessageRetrieval measures performance with large threads
func BenchmarkLargeThreadMessageRetrieval(b *testing.B) {
	db := setupBenchDB(b)
	ctx := context.Background()
	negotiationSvc := NewAppealNegotiationService(db)

	// Prepare: Create appeal with 1000 messages
	db.Exec(`
		INSERT INTO appeals (id, user_id, violation_id, reason, status, created_at)
		VALUES (1, 100, 1, 'false_positive', 'reviewing', datetime('now'))
	`)

	for i := 0; i < 1000; i++ {
		db.Exec(`
			INSERT INTO appeal_negotiation_messages
			(appeal_id, sender_id, sender_type, message, message_type, created_at)
			VALUES (1, ?, ?, ?, 'message', datetime('now', '-? seconds'))
		`, 100+(i%2), []string{"user", "admin"}[i%2], fmt.Sprintf("Message %d", i), i)
	}

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		negotiationSvc.GetNegotiationThread(ctx, 1)
	}
}

// BenchmarkConcurrentPeerStatistics measures concurrent peer lookup performance
func BenchmarkConcurrentPeerStatistics(b *testing.B) {
	db := setupBenchDB(b)
	ctx := context.Background()
	peerSvc := NewPeerAnalyticsService(db)

	// Prepare: Create 1000 users
	for i := 0; i < 1000; i++ {
		db.Exec(`
			INSERT INTO reputation_scores (user_id, score, tier)
			VALUES (?, ?, 'standard')
		`, 30000+i, 40.0+float64(i%60)*1.0)
	}

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		userID := 30000 + (i % 1000)
		peerSvc.GetUserPeerComparison(ctx, userID, "standard")
	}
}

// BenchmarkDatabaseQueryEfficiency measures raw query performance
func BenchmarkDatabaseQueryEfficiency(b *testing.B) {
	db := setupBenchDB(b)

	// Prepare: Create 10000 appeals
	for i := 0; i < 10000; i++ {
		userID := 40000 + (i % 100)
		if i%100 == 0 {
			db.Exec(`
				INSERT INTO reputation_scores (user_id, score, tier)
				VALUES (?, 50.0, 'standard')
			`, userID)
		}

		status := "pending"
		if i%3 == 0 {
			status = "approved"
		} else if i%5 == 0 {
			status = "denied"
		}

		db.Exec(`
			INSERT INTO appeals (id, user_id, violation_id, reason, status, created_at)
			VALUES (?, ?, ?, 'false_positive', ?, datetime('now', '-? days'))
		`, i, userID, i, status, i%30)
	}

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		var count int64
		db.Table("appeals").Where("status = ?", "pending").Count(&count)
	}
}

// BenchmarkAnalyticsCalculations measures statistical calculations
func BenchmarkAnalyticsCalculations(b *testing.B) {
	db := setupBenchDB(b)
	ctx := context.Background()
	analyticsSvc := NewAnalyticsService(db)

	// Prepare: Create user with analytics data
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (50000, 50.0, 'standard')
	`)

	for i := 0; i < 10; i++ {
		db.Exec(`
			INSERT INTO appeals (id, user_id, violation_id, reason, status, created_at)
			VALUES (?, 50000, ?, 'false_positive', ?, datetime('now', '-? days'))
		`, i, i, []string{"pending", "approved", "denied"}[i%3], i)
	}

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		analyticsSvc.GetReputationTrends(ctx, 50000, 30)
		analyticsSvc.GetBehaviorPatterns(ctx, 50000)
		analyticsSvc.GenerateRecommendations(ctx, 50000)
	}
}
