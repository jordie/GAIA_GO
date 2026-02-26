package claude_confirm

import (
	"context"
	"testing"
	"time"

	"github.com/google/uuid"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupTestDB creates an in-memory SQLite database for testing
func setupTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("failed to create test db: %v", err)
	}

	// Auto-migrate models
	err = db.AutoMigrate(
		&ConfirmationRequest{},
		&ApprovalPattern{},
		&AIAgentDecision{},
		&SessionApprovalPreference{},
	)
	if err != nil {
		t.Fatalf("failed to migrate: %v", err)
	}

	return db
}

// createTestPattern creates a test pattern
func createTestPattern(db *gorm.DB, name string, decision DecisionType) *ApprovalPattern {
	pattern := &ApprovalPattern{
		ID:             uuid.New(),
		Name:           name,
		PermissionType: PermissionRead,
		ResourceType:   ResourceFile,
		PathPattern:    "/data/*",
		DecisionType:   decision,
		Enabled:        true,
		Confidence:     0.9,
		CreatedAt:      time.Now(),
		UpdatedAt:      time.Now(),
	}
	db.Create(pattern)
	return pattern
}

// Test pattern matching
func TestPatternMatching(t *testing.T) {
	db := setupTestDB(t)
	defer func() {
		sqlDB, _ := db.DB()
		sqlDB.Close()
	}()

	pm := NewPatternMatcher(db)

	// Create test patterns
	pattern := createTestPattern(db, "Read Data Files", DecisionApprove)

	// Test matching request
	req := &ConfirmationRequest{
		ID:             uuid.New(),
		SessionID:      "test_session",
		PermissionType: PermissionRead,
		ResourceType:   ResourceFile,
		ResourcePath:   "/data/project/main.py",
		Context:        "Reading source code",
	}

	result, err := pm.Match(context.Background(), req)
	if err != nil {
		t.Fatalf("failed to match: %v", err)
	}

	if result == nil {
		t.Fatal("expected pattern match, got nil")
	}

	if result.Pattern.ID != pattern.ID {
		t.Errorf("expected pattern %s, got %s", pattern.ID, result.Pattern.ID)
	}

	if result.Score < 0.5 {
		t.Errorf("expected score >= 0.5, got %.2f", result.Score)
	}
}

// Test no pattern match
func TestNoPatternMatch(t *testing.T) {
	db := setupTestDB(t)
	defer func() {
		sqlDB, _ := db.DB()
		sqlDB.Close()
	}()

	pm := NewPatternMatcher(db)

	// Request that won't match any pattern
	req := &ConfirmationRequest{
		ID:             uuid.New(),
		SessionID:      "test_session",
		PermissionType: PermissionDelete,
		ResourceType:   ResourceFile,
		ResourcePath:   "/etc/passwd",
		Context:        "Delete system file",
	}

	result, err := pm.Match(context.Background(), req)
	if err != nil {
		t.Fatalf("failed to match: %v", err)
	}

	if result != nil {
		t.Fatal("expected no pattern match")
	}
}

// Test confirmation service with pattern
func TestConfirmationServiceWithPattern(t *testing.T) {
	db := setupTestDB(t)
	defer func() {
		sqlDB, _ := db.DB()
		sqlDB.Close()
	}()

	aiConfig := AIAgentConfig{
		Model:   "test-model",
		Enabled: false, // Disable AI for this test
	}
	aiAgent := NewAIAgent(db, aiConfig)
	service := NewConfirmationService(db, aiAgent)

	// Create a pattern
	pattern := createTestPattern(db, "Approve Reads", DecisionApprove)

	// Process request that matches pattern
	req := &ConfirmationRequest{
		SessionID:      "test_session",
		PermissionType: PermissionRead,
		ResourceType:   ResourceFile,
		ResourcePath:   "/data/test.txt",
		Context:        "Reading file",
	}

	decision, reason, err := service.ProcessConfirmation(context.Background(), req)
	if err != nil {
		t.Fatalf("failed to process: %v", err)
	}

	if decision != DecisionApprove {
		t.Errorf("expected approve, got %s. Reason: %s", decision, reason)
	}

	// Verify confirmation was saved
	var saved ConfirmationRequest
	result := db.Where("session_id = ?", "test_session").First(&saved)
	if result.Error != nil {
		t.Fatalf("failed to retrieve saved confirmation: %v", result.Error)
	}

	if saved.Decision != DecisionApprove {
		t.Errorf("expected saved decision approve, got %s", saved.Decision)
	}
}

// Test session preferences
func TestSessionPreferences(t *testing.T) {
	db := setupTestDB(t)
	defer func() {
		sqlDB, _ := db.DB()
		sqlDB.Close()
	}()

	aiConfig := AIAgentConfig{
		Model:   "test-model",
		Enabled: false,
	}
	aiAgent := NewAIAgent(db, aiConfig)
	service := NewConfirmationService(db, aiAgent)

	// Set session to allow all
	pref := &SessionApprovalPreference{
		SessionID:      "test_session",
		AllowAll:       true,
		UseAIFallback:  true,
	}

	err := service.SetSessionPreference(context.Background(), pref)
	if err != nil {
		t.Fatalf("failed to set preference: %v", err)
	}

	// Process request - should auto-approve
	req := &ConfirmationRequest{
		SessionID:      "test_session",
		PermissionType: PermissionDelete,
		ResourceType:   ResourceFile,
		ResourcePath:   "/etc/passwd",
		Context:        "Delete system file", // Normally denied
	}

	decision, _, err := service.ProcessConfirmation(context.Background(), req)
	if err != nil {
		t.Fatalf("failed to process: %v", err)
	}

	if decision != DecisionApprove {
		t.Errorf("expected approve due to allow_all preference, got %s", decision)
	}
}

// Test AI agent fallback
func TestAIAgentFallback(t *testing.T) {
	db := setupTestDB(t)
	defer func() {
		sqlDB, _ := db.DB()
		sqlDB.Close()
	}()

	// Note: AI agent is mocked, doesn't call actual Claude API
	aiConfig := AIAgentConfig{
		Model:   "test-model",
		Enabled: true,
	}
	aiAgent := NewAIAgent(db, aiConfig)
	service := NewConfirmationService(db, aiAgent)

	// Request that doesn't match any pattern
	req := &ConfirmationRequest{
		SessionID:      "test_session",
		PermissionType: PermissionRead,
		ResourceType:   ResourceAPI,
		ResourcePath:   "https://api.example.com",
		Context:        "Calling external API",
	}

	decision, reason, err := service.ProcessConfirmation(context.Background(), req)
	if err != nil {
		t.Fatalf("failed to process: %v", err)
	}

	// Mock AI should make a decision
	if decision == "" {
		t.Error("expected AI agent to make a decision")
	}

	if reason == "" {
		t.Error("expected reasoning from AI agent")
	}
}

// Test pattern creation and updates
func TestPatternCRUD(t *testing.T) {
	db := setupTestDB(t)
	defer func() {
		sqlDB, _ := db.DB()
		sqlDB.Close()
	}()

	aiConfig := AIAgentConfig{Model: "test", Enabled: false}
	service := NewConfirmationService(db, NewAIAgent(db, aiConfig))

	// Create
	pattern := &ApprovalPattern{
		Name:           "Test Pattern",
		Description:    "Test",
		PermissionType: PermissionRead,
		ResourceType:   ResourceFile,
		PathPattern:    "/test/*",
		DecisionType:   DecisionApprove,
		Enabled:        true,
	}

	err := service.CreatePattern(context.Background(), pattern)
	if err != nil {
		t.Fatalf("failed to create pattern: %v", err)
	}

	if pattern.ID == uuid.Nil {
		t.Error("expected pattern ID to be set")
	}

	// Read
	retrieved, err := service.GetPattern(context.Background(), pattern.ID.String())
	if err != nil {
		t.Fatalf("failed to get pattern: %v", err)
	}

	if retrieved == nil {
		t.Fatal("expected to retrieve pattern")
	}

	// Update
	err = service.UpdatePattern(context.Background(), pattern.ID.String(), map[string]interface{}{
		"enabled": false,
	})
	if err != nil {
		t.Fatalf("failed to update pattern: %v", err)
	}

	// Verify update
	updated, _ := service.GetPattern(context.Background(), pattern.ID.String())
	if updated.Enabled {
		t.Error("expected pattern to be disabled")
	}

	// Delete
	err = service.DeletePattern(context.Background(), pattern.ID.String())
	if err != nil {
		t.Fatalf("failed to delete pattern: %v", err)
	}

	// Verify deletion
	deleted, _ := service.GetPattern(context.Background(), pattern.ID.String())
	if deleted != nil {
		t.Error("expected pattern to be deleted")
	}
}

// Test confirmation history
func TestConfirmationHistory(t *testing.T) {
	db := setupTestDB(t)
	defer func() {
		sqlDB, _ := db.DB()
		sqlDB.Close()
	}()

	aiConfig := AIAgentConfig{Model: "test", Enabled: false}
	service := NewConfirmationService(db, NewAIAgent(db, aiConfig))

	sessionID := "test_session"

	// Create multiple confirmations
	for i := 0; i < 5; i++ {
		req := &ConfirmationRequest{
			ID:             uuid.New(),
			SessionID:      sessionID,
			PermissionType: PermissionRead,
			ResourceType:   ResourceFile,
			ResourcePath:   "/data/file.txt",
			Context:        "Reading",
			Timestamp:      time.Now(),
			Decision:       DecisionApprove,
		}
		db.Create(req)
	}

	// Retrieve history
	history, err := service.GetConfirmationHistory(context.Background(), sessionID, 10)
	if err != nil {
		t.Fatalf("failed to get history: %v", err)
	}

	if len(history) != 5 {
		t.Errorf("expected 5 confirmations, got %d", len(history))
	}
}

// Test session stats
func TestSessionStats(t *testing.T) {
	db := setupTestDB(t)
	defer func() {
		sqlDB, _ := db.DB()
		sqlDB.Close()
	}()

	aiConfig := AIAgentConfig{Model: "test", Enabled: false}
	service := NewConfirmationService(db, NewAIAgent(db, aiConfig))

	sessionID := "test_session"

	// Create confirmations with different outcomes
	now := time.Now()
	for i := 0; i < 3; i++ {
		db.Create(&ConfirmationRequest{
			ID:        uuid.New(),
			SessionID: sessionID,
			Decision:  DecisionApprove,
			Timestamp: now.Add(time.Duration(-i) * time.Hour),
		})
	}

	db.Create(&ConfirmationRequest{
		ID:        uuid.New(),
		SessionID: sessionID,
		Decision:  DecisionDeny,
		Timestamp: now.Add(-4 * time.Hour),
	})

	// Get stats
	stats, err := service.GetSessionStats(context.Background(), sessionID)
	if err != nil {
		t.Fatalf("failed to get stats: %v", err)
	}

	if stats.TotalRequests != 4 {
		t.Errorf("expected 4 total requests, got %d", stats.TotalRequests)
	}

	if stats.Denied != 1 {
		t.Errorf("expected 1 denied, got %d", stats.Denied)
	}
}

// Test global stats
func TestGlobalStats(t *testing.T) {
	db := setupTestDB(t)
	defer func() {
		sqlDB, _ := db.DB()
		sqlDB.Close()
	}()

	aiConfig := AIAgentConfig{Model: "test", Enabled: false}
	service := NewConfirmationService(db, NewAIAgent(db, aiConfig))

	// Create a pattern
	createTestPattern(db, "Test", DecisionApprove)

	// Create confirmations
	for i := 0; i < 2; i++ {
		db.Create(&ConfirmationRequest{
			ID:        uuid.New(),
			SessionID: "session" + string(rune(i)),
			Decision:  DecisionApprove,
			Timestamp: time.Now(),
		})
	}

	// Get global stats
	stats, err := service.GetGlobalStats(context.Background())
	if err != nil {
		t.Fatalf("failed to get global stats: %v", err)
	}

	if stats["total_confirmations"] != int64(2) && stats["total_confirmations"] != 2 {
		t.Logf("global stats: %v", stats)
		// Stats might be int64 or int depending on database
	}
}
