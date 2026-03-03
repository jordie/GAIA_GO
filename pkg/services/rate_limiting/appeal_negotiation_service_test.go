package rate_limiting

import (
	"context"
	"testing"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupNegotiationTestDB creates test database
func setupNegotiationTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to create test DB: %v", err)
	}

	db.Exec(`
		CREATE TABLE appeals (
			id INTEGER PRIMARY KEY,
			user_id INTEGER,
			violation_id INTEGER,
			status TEXT DEFAULT 'pending',
			priority TEXT,
			reason TEXT,
			description TEXT,
			evidence TEXT,
			reputation_lost REAL,
			requested_action TEXT,
			reviewed_by TEXT,
			review_comment TEXT,
			resolution TEXT,
			approved_points REAL,
			created_at TIMESTAMP,
			updated_at TIMESTAMP,
			expires_at TIMESTAMP,
			resolved_at TIMESTAMP
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

	return db
}

// TestNegotiationServiceCreation tests service initialization
func TestNegotiationServiceCreation(t *testing.T) {
	db := setupNegotiationTestDB(t)
	ns := NewAppealNegotiationService(db)

	if ns == nil {
		t.Errorf("Failed to create negotiation service")
	}
}

// TestSendMessage sends a negotiation message
func TestSendMessage(t *testing.T) {
	db := setupNegotiationTestDB(t)
	ns := NewAppealNegotiationService(db)

	// Create test appeal
	appeal := &Appeal{ID: 1, UserID: 100, Status: AppealPending, CreatedAt: time.Now()}
	db.Table("appeals").Create(appeal)

	msg, err := ns.SendMessage(
		context.Background(),
		1,
		100,
		SenderTypeUser,
		"I believe this violation was incorrect",
		MessageTypeMessage,
		nil,
		nil,
	)

	if err != nil {
		t.Errorf("Failed to send message: %v", err)
	}

	if msg == nil {
		t.Errorf("Message is nil")
	}

	if msg.Message != "I believe this violation was incorrect" {
		t.Errorf("Message content mismatch")
	}
}

// TestGetNegotiationThread retrieves conversation thread
func TestGetNegotiationThread(t *testing.T) {
	db := setupNegotiationTestDB(t)
	ns := NewAppealNegotiationService(db)

	appeal := &Appeal{ID: 2, UserID: 101, Status: AppealPending, CreatedAt: time.Now()}
	db.Table("appeals").Create(appeal)

	// Send multiple messages
	for i := 0; i < 3; i++ {
		ns.SendMessage(
			context.Background(),
			2,
			100+i,
			SenderTypeUser,
			"Message "+string(rune('0'+i)),
			MessageTypeMessage,
			nil,
			nil,
		)
	}

	thread, err := ns.GetNegotiationThread(context.Background(), 2)
	if err != nil {
		t.Errorf("Failed to get thread: %v", err)
	}

	if thread == nil {
		t.Errorf("Thread is nil")
	}

	if thread.MessageCount != 3 {
		t.Errorf("Expected 3 messages, got %d", thread.MessageCount)
	}
}

// TestGetUserConversations retrieves user's conversations
func TestGetUserConversations(t *testing.T) {
	db := setupNegotiationTestDB(t)
	ns := NewAppealNegotiationService(db)

	// Create appeals and messages
	for i := 1; i <= 2; i++ {
		appeal := &Appeal{
			ID:     i,
			UserID: 200,
			Status: AppealPending,
			CreatedAt: time.Now(),
		}
		db.Table("appeals").Create(appeal)

		ns.SendMessage(
			context.Background(),
			i,
			200,
			SenderTypeUser,
			"User message",
			MessageTypeMessage,
			nil,
			nil,
		)
	}

	conversations, err := ns.GetUserConversations(context.Background(), 200, 10, 0)
	if err != nil {
		t.Errorf("Failed to get conversations: %v", err)
	}

	if len(conversations) < 2 {
		t.Errorf("Expected at least 2 conversations, got %d", len(conversations))
	}
}

// TestPinMessage pins a message
func TestPinMessage(t *testing.T) {
	db := setupNegotiationTestDB(t)
	ns := NewAppealNegotiationService(db)

	appeal := &Appeal{ID: 3, UserID: 201, Status: AppealPending, CreatedAt: time.Now()}
	db.Table("appeals").Create(appeal)

	msg, _ := ns.SendMessage(
		context.Background(),
		3,
		201,
		SenderTypeUser,
		"Important message",
		MessageTypeMessage,
		nil,
		nil,
	)

	err := ns.PinMessage(context.Background(), msg.ID)
	if err != nil {
		t.Errorf("Failed to pin message: %v", err)
	}

	// Verify pinned
	var count int64
	db.Table("appeal_negotiation_messages").
		Where("id = ? AND is_pinned = ?", msg.ID, true).
		Count(&count)

	if count != 1 {
		t.Errorf("Message not pinned")
	}
}

// TestGetPinnedMessages retrieves pinned messages
func TestGetPinnedMessages(t *testing.T) {
	db := setupNegotiationTestDB(t)
	ns := NewAppealNegotiationService(db)

	appeal := &Appeal{ID: 4, UserID: 202, Status: AppealPending, CreatedAt: time.Now()}
	db.Table("appeals").Create(appeal)

	msg1, _ := ns.SendMessage(context.Background(), 4, 202, SenderTypeUser, "Important", MessageTypeMessage, nil, nil)
	_, _ = ns.SendMessage(context.Background(), 4, 202, SenderTypeUser, "Other", MessageTypeMessage, nil, nil)

	ns.PinMessage(context.Background(), msg1.ID)

	pinned, err := ns.GetPinnedMessages(context.Background(), 4)
	if err != nil {
		t.Errorf("Failed to get pinned messages: %v", err)
	}

	if len(pinned) != 1 {
		t.Errorf("Expected 1 pinned message, got %d", len(pinned))
	}
}

// TestAnalyzeConversationTone analyzes sentiment
func TestAnalyzeConversationTone(t *testing.T) {
	db := setupNegotiationTestDB(t)
	ns := NewAppealNegotiationService(db)

	appeal := &Appeal{ID: 5, UserID: 203, Status: AppealPending, CreatedAt: time.Now()}
	db.Table("appeals").Create(appeal)

	ns.SendMessage(context.Background(), 5, 203, SenderTypeUser, "Message", MessageTypeMessage, nil, nil)

	analysis, err := ns.AnalyzeConversationTone(context.Background(), 5)
	if err != nil {
		t.Errorf("Failed to analyze tone: %v", err)
	}

	if analysis == nil {
		t.Errorf("Analysis is nil")
	}

	if _, exists := analysis["conversation_health"]; !exists {
		t.Errorf("conversation_health not in analysis")
	}
}

// TestGetNegotiationMetrics retrieves statistics
func TestGetNegotiationMetrics(t *testing.T) {
	db := setupNegotiationTestDB(t)
	ns := NewAppealNegotiationService(db)

	appeal := &Appeal{ID: 6, UserID: 204, Status: AppealPending, CreatedAt: time.Now()}
	db.Table("appeals").Create(appeal)

	ns.SendMessage(context.Background(), 6, 204, SenderTypeUser, "Message", MessageTypeMessage, nil, nil)

	metrics, err := ns.GetNegotiationMetrics(context.Background())
	if err != nil {
		t.Errorf("Failed to get metrics: %v", err)
	}

	if metrics == nil {
		t.Errorf("Metrics is nil")
	}

	if _, exists := metrics["total_negotiations"]; !exists {
		t.Errorf("total_negotiations not in metrics")
	}
}

// TestMessageTypes tests all message types
func TestMessageTypes(t *testing.T) {
	types := []MessageType{
		MessageTypeMessage,
		MessageTypeQuestion,
		MessageTypeClarification,
		MessageTypeProposal,
	}

	for _, msgType := range types {
		if msgType == "" {
			t.Errorf("Message type is empty")
		}
	}
}

// TestSenderTypes tests all sender types
func TestSenderTypes(t *testing.T) {
	types := []SenderType{
		SenderTypeUser,
		SenderTypeAdmin,
	}

	for _, senderType := range types {
		if senderType == "" {
			t.Errorf("Sender type is empty")
		}
	}
}

// BenchmarkSendMessage benchmarks message sending
func BenchmarkSendMessage(b *testing.B) {
	db := setupNegotiationTestDB(&testing.T{})
	ns := NewAppealNegotiationService(db)

	appeal := &Appeal{ID: 100, UserID: 1000, Status: AppealPending, CreatedAt: time.Now()}
	db.Table("appeals").Create(appeal)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		ns.SendMessage(
			context.Background(),
			100,
			1000+i,
			SenderTypeUser,
			"Test message",
			MessageTypeMessage,
			nil,
			nil,
		)
	}
}

// BenchmarkGetNegotiationThread benchmarks thread retrieval
func BenchmarkGetNegotiationThread(b *testing.B) {
	db := setupNegotiationTestDB(&testing.T{})
	ns := NewAppealNegotiationService(db)

	appeal := &Appeal{ID: 101, UserID: 1001, Status: AppealPending, CreatedAt: time.Now()}
	db.Table("appeals").Create(appeal)

	for i := 0; i < 10; i++ {
		ns.SendMessage(context.Background(), 101, 1001, SenderTypeUser, "Message", MessageTypeMessage, nil, nil)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		ns.GetNegotiationThread(context.Background(), 101)
	}
}
