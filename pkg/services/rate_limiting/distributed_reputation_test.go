package rate_limiting

import (
	"context"
	"fmt"
	"testing"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupDistributedTestDB creates test database for distributed reputation tests
func setupDistributedTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to create test DB: %v", err)
	}

	// Auto-migrate models
	db.AutoMigrate(&ReputationEvent{}, &ReputationSync{}, &NodeReputation{})

	return db
}

// TestDistributedReputationManagerCreation tests manager initialization
func TestDistributedReputationManagerCreation(t *testing.T) {
	db := setupDistributedTestDB(t)
	drm := NewDistributedReputationManager(db, "node-1")
	defer drm.Close()

	if drm.localNodeID != "node-1" {
		t.Errorf("Expected node ID 'node-1', got %s", drm.localNodeID)
	}

	if len(drm.remoteNodes) != 0 {
		t.Errorf("Expected 0 remote nodes, got %d", len(drm.remoteNodes))
	}
}

// TestRegisterRemoteNode tests remote node registration
func TestRegisterRemoteNode(t *testing.T) {
	db := setupDistributedTestDB(t)
	drm := NewDistributedReputationManager(db, "node-1")
	defer drm.Close()

	err := drm.RegisterRemoteNode("node-2", "http://node-2:8080")
	if err != nil {
		t.Errorf("Failed to register remote node: %v", err)
	}

	drm.mu.RLock()
	endpoint, exists := drm.remoteNodes["node-2"]
	drm.mu.RUnlock()

	if !exists {
		t.Errorf("Remote node not registered")
	}

	if endpoint != "http://node-2:8080" {
		t.Errorf("Wrong endpoint: %s", endpoint)
	}

	// Verify sync tracking was created
	var sync ReputationSync
	if err := db.Where("node_id = ? AND remote_node_id = ?", "node-1", "node-2").First(&sync).Error; err != nil {
		t.Errorf("Sync tracking not created: %v", err)
	}
}

// TestRecordEvent tests recording a reputation event
func TestRecordEvent(t *testing.T) {
	db := setupDistributedTestDB(t)
	drm := NewDistributedReputationManager(db, "node-1")
	defer drm.Close()

	ctx := context.Background()

	event := &ReputationEvent{
		UserID:        1,
		EventType:     "violation",
		ScoreDelta:    -5.0,
		ReasonCode:    "rate_limit_exceeded",
		Severity:      2,
		SourceService: "api-gateway",
	}

	err := drm.RecordEvent(ctx, event)
	if err != nil {
		t.Errorf("Failed to record event: %v", err)
	}

	// Verify event was stored
	var stored ReputationEvent
	if err := db.Where("user_id = ? AND event_type = ?", 1, "violation").First(&stored).Error; err != nil {
		t.Errorf("Event not stored: %v", err)
	}

	if stored.NodeID != "node-1" {
		t.Errorf("Event has wrong node ID: %s", stored.NodeID)
	}
}

// TestEventDeduplication tests duplicate event detection
func TestEventDeduplication(t *testing.T) {
	db := setupDistributedTestDB(t)
	drm := NewDistributedReputationManager(db, "node-1")
	defer drm.Close()

	ctx := context.Background()

	event := &ReputationEvent{
		UserID:        1,
		EventType:     "violation",
		ScoreDelta:    -5.0,
		ReasonCode:    "rate_limit_exceeded",
		SourceService: "api-gateway",
		Timestamp:     time.Now(),
	}

	// Record first time
	err := drm.RecordEvent(ctx, event)
	if err != nil {
		t.Fatalf("First record failed: %v", err)
	}

	// Record again with same data (should be skipped)
	event.ID = 0 // Reset ID for reinsert attempt
	err = drm.RecordEvent(ctx, event)
	if err != nil {
		t.Fatalf("Second record failed: %v", err)
	}

	// Verify only one event stored
	var count int64
	db.Model(&ReputationEvent{}).Count(&count)
	if count != 1 {
		t.Errorf("Expected 1 event, got %d (deduplication failed)", count)
	}
}

// TestLocalOnlyEvents tests events that don't replicate
func TestLocalOnlyEvents(t *testing.T) {
	db := setupDistributedTestDB(t)
	drm := NewDistributedReputationManager(db, "node-1")
	defer drm.Close()

	ctx := context.Background()

	event := &ReputationEvent{
		UserID:        1,
		EventType:     "clean_request",
		ScoreDelta:    1.0,
		LocalOnly:     true,
		SourceService: "internal",
	}

	err := drm.RecordEvent(ctx, event)
	if err != nil {
		t.Errorf("Failed to record local-only event: %v", err)
	}

	// Buffer should be empty for local-only events
	drm.bufferMutex.Lock()
	if len(drm.eventBuffer) != 0 {
		t.Errorf("Local-only event was buffered for replication")
	}
	drm.bufferMutex.Unlock()
}

// TestEventBuffering tests event buffering for replication
func TestEventBuffering(t *testing.T) {
	db := setupDistributedTestDB(t)
	drm := NewDistributedReputationManager(db, "node-1")
	defer drm.Close()

	ctx := context.Background()

	// Register remote node
	drm.RegisterRemoteNode("node-2", "http://node-2:8080")

	// Record multiple events
	for i := 0; i < 5; i++ {
		event := &ReputationEvent{
			UserID:        1,
			EventType:     "violation",
			ScoreDelta:    -1.0,
			SourceService: "api",
		}
		drm.RecordEvent(ctx, event)
		time.Sleep(10 * time.Millisecond)
	}

	// Buffer should have events
	drm.bufferMutex.Lock()
	bufferSize := len(drm.eventBuffer)
	drm.bufferMutex.Unlock()

	if bufferSize == 0 {
		t.Errorf("Events not buffered for replication")
	}
}

// TestNodeReputationConsensus tests getting consensus reputation
func TestNodeReputationConsensus(t *testing.T) {
	db := setupDistributedTestDB(t)
	drm := NewDistributedReputationManager(db, "node-1")
	defer drm.Close()

	ctx := context.Background()

	// Create reputation on multiple nodes
	reps := []NodeReputation{
		{
			UserID:          1,
			NodeID:          "node-1",
			Score:           75.0,
			Tier:            "trusted",
			IsAuthoritative: true,
			LastUpdated:     time.Now(),
			CreatedAt:       time.Now(),
		},
		{
			UserID:          1,
			NodeID:          "node-2",
			Score:           73.0,
			Tier:            "trusted",
			IsAuthoritative: false,
			LastUpdated:     time.Now().Add(-1 * time.Minute),
			CreatedAt:       time.Now().Add(-1 * time.Minute),
		},
		{
			UserID:          1,
			NodeID:          "node-3",
			Score:           76.0,
			Tier:            "trusted",
			IsAuthoritative: false,
			LastUpdated:     time.Now().Add(-2 * time.Minute),
			CreatedAt:       time.Now().Add(-2 * time.Minute),
		},
	}

	for _, rep := range reps {
		db.Create(&rep)
	}

	score, tier, confidence, err := drm.GetUserReputationConsensus(ctx, 1)
	if err != nil {
		t.Errorf("Failed to get consensus: %v", err)
	}

	// Should use authoritative score
	if score != 75.0 {
		t.Errorf("Expected score 75.0, got %f", score)
	}

	if tier != "trusted" {
		t.Errorf("Expected tier 'trusted', got %s", tier)
	}

	if confidence <= 0 || confidence > 1 {
		t.Errorf("Invalid confidence: %f", confidence)
	}
}

// TestMajorityConsensus tests consensus when no authoritative source
func TestMajorityConsensus(t *testing.T) {
	db := setupDistributedTestDB(t)
	drm := NewDistributedReputationManager(db, "node-1")
	defer drm.Close()

	ctx := context.Background()

	// Create non-authoritative reps
	reps := []NodeReputation{
		{
			UserID:          2,
			NodeID:          "node-1",
			Score:           50.0,
			Tier:            "standard",
			IsAuthoritative: false,
			LastUpdated:     time.Now(),
			CreatedAt:       time.Now(),
		},
		{
			UserID:          2,
			NodeID:          "node-2",
			Score:           51.0,
			Tier:            "standard",
			IsAuthoritative: false,
			LastUpdated:     time.Now(),
			CreatedAt:       time.Now(),
		},
		{
			UserID:          2,
			NodeID:          "node-3",
			Score:           45.0,
			Tier:            "flagged",
			IsAuthoritative: false,
			LastUpdated:     time.Now(),
			CreatedAt:       time.Now(),
		},
	}

	for _, rep := range reps {
		db.Create(&rep)
	}

	score, tier, _, err := drm.GetUserReputationConsensus(ctx, 2)
	if err != nil {
		t.Errorf("Failed to get consensus: %v", err)
	}

	// Should use average score
	expectedScore := (50.0 + 51.0 + 45.0) / 3.0
	if score < expectedScore-1 || score > expectedScore+1 {
		t.Errorf("Expected score ~%f, got %f", expectedScore, score)
	}

	// Should use majority tier
	if tier != "standard" {
		t.Errorf("Expected majority tier 'standard', got %s", tier)
	}
}

// TestResolveUserReputation tests conflict resolution
func TestResolveUserReputation(t *testing.T) {
	db := setupDistributedTestDB(t)
	drm := NewDistributedReputationManager(db, "node-1")
	defer drm.Close()

	ctx := context.Background()

	// Create conflicting reputations
	now := time.Now()
	reps := []NodeReputation{
		{
			UserID:          3,
			NodeID:          "node-1",
			Score:           80.0,
			Tier:            "trusted",
			IsAuthoritative: true,
			LastUpdated:     now,
			CreatedAt:       now,
		},
		{
			UserID:          3,
			NodeID:          "node-2",
			Score:           40.0,
			Tier:            "flagged",
			IsAuthoritative: false,
			LastUpdated:     now.Add(-5 * time.Minute), // Older
			CreatedAt:       now.Add(-5 * time.Minute),
		},
	}

	for _, rep := range reps {
		db.Create(&rep)
	}

	// Resolve conflicts
	err := drm.ResolveUserReputation(ctx, 3)
	if err != nil {
		t.Errorf("Failed to resolve conflicts: %v", err)
	}

	// Node-2 should be updated to match node-1
	var updated NodeReputation
	db.Where("user_id = ? AND node_id = ?", 3, "node-2").First(&updated)

	if updated.Score != 80.0 {
		t.Errorf("Score not updated: expected 80.0, got %f", updated.Score)
	}

	if updated.Tier != "trusted" {
		t.Errorf("Tier not updated: expected 'trusted', got %s", updated.Tier)
	}
}

// TestGetSyncStatus tests retrieving sync status
func TestGetSyncStatus(t *testing.T) {
	db := setupDistributedTestDB(t)
	drm := NewDistributedReputationManager(db, "node-1")
	defer drm.Close()

	ctx := context.Background()

	// Register multiple nodes
	drm.RegisterRemoteNode("node-2", "http://node-2:8080")
	drm.RegisterRemoteNode("node-3", "http://node-3:8080")

	status, err := drm.GetSyncStatus(ctx)
	if err != nil {
		t.Errorf("Failed to get sync status: %v", err)
	}

	if status["node_id"] != "node-1" {
		t.Errorf("Wrong node ID in status")
	}

	if status["total_nodes"].(int) != 2 {
		t.Errorf("Expected 2 remote nodes in status")
	}
}

// TestGetReplicationStats tests replication statistics
func TestGetReplicationStats(t *testing.T) {
	db := setupDistributedTestDB(t)
	drm := NewDistributedReputationManager(db, "node-1")
	defer drm.Close()

	ctx := context.Background()

	// Record some events
	for i := 0; i < 3; i++ {
		event := &ReputationEvent{
			UserID:        1,
			EventType:     "violation",
			ScoreDelta:    -1.0,
			SourceService: "api",
		}
		drm.RecordEvent(ctx, event)
	}

	stats, err := drm.GetReplicationStats(ctx)
	if err != nil {
		t.Errorf("Failed to get replication stats: %v", err)
	}

	if stats["total_events"].(int64) != 3 {
		t.Errorf("Expected 3 events in stats")
	}
}

// TestConflictResolver tests timestamp-based conflict resolution
func TestConflictResolver(t *testing.T) {
	resolver := &TimestampResolver{}

	t1 := time.Now()
	t2 := time.Now().Add(1 * time.Second)

	// Test tier conflict - newer wins
	result := resolver.ResolveTierConflict("flagged", "trusted", t1, t2)
	if result != "trusted" {
		t.Errorf("Expected 'trusted' (newer), got %s", result)
	}

	// Test score conflict - newer wins
	score := resolver.ResolveScoreConflict(40.0, 80.0, t1, t2)
	if score != 80.0 {
		t.Errorf("Expected 80.0 (newer), got %f", score)
	}

	// Test when older is the choice
	result2 := resolver.ResolveTierConflict("trusted", "flagged", t2, t1)
	if result2 != "trusted" {
		t.Errorf("Expected 'trusted' (newer), got %s", result2)
	}
}

// BenchmarkRecordEvent benchmarks event recording
func BenchmarkRecordEvent(b *testing.B) {
	db := setupDistributedTestDB(&testing.T{})
	drm := NewDistributedReputationManager(db, "node-1")
	defer drm.Close()

	ctx := context.Background()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		event := &ReputationEvent{
			UserID:        i % 1000,
			EventType:     "violation",
			ScoreDelta:    -1.0,
			SourceService: "api",
		}
		drm.RecordEvent(ctx, event)
	}
}

// BenchmarkGetConsensus benchmarks consensus calculation
func BenchmarkGetConsensus(b *testing.B) {
	db := setupDistributedTestDB(&testing.T{})
	drm := NewDistributedReputationManager(db, "node-1")
	defer drm.Close()

	// Pre-populate reputation data
	for i := 0; i < 100; i++ {
		for n := 0; n < 3; n++ {
			rep := NodeReputation{
				UserID:          i,
				NodeID:          fmt.Sprintf("node-%d", n),
				Score:           float64(50 + n*5),
				Tier:            "standard",
				IsAuthoritative: n == 0,
				LastUpdated:     time.Now(),
				CreatedAt:       time.Now(),
			}
			db.Create(&rep)
		}
	}

	ctx := context.Background()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		drm.GetUserReputationConsensus(ctx, i%100)
	}
}
