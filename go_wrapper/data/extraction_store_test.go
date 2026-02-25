package data

import (
	"crypto/sha256"
	"fmt"
	"os"
	"testing"
	"time"
)

func TestNewExtractionStore(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	if store.db == nil {
		t.Error("Database connection not initialized")
	}
}

func TestExtractionStore_SaveAndRetrieve(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create test extraction
	event := &ExtractionEvent{
		AgentName:      "test-agent",
		SessionID:      "session-001",
		Timestamp:      time.Now(),
		EventType:      "error",
		Pattern:        "error_detection",
		MatchedValue:   "TypeError: undefined",
		OriginalLine:   "Error occurred: TypeError: undefined is not a function",
		LineNumber:     42,
		Metadata:       map[string]interface{}{"severity": "high"},
		RiskLevel:      "high",
		AutoConfirmable: false,
	}

	// Save extraction
	if err := store.SaveExtraction(event); err != nil {
		t.Fatalf("Failed to save extraction: %v", err)
	}

	if event.ID == 0 {
		t.Error("ID not set after save")
	}

	// Retrieve extractions
	extractions, err := store.GetExtractionsByAgent("test-agent", 10)
	if err != nil {
		t.Fatalf("Failed to get extractions: %v", err)
	}

	if len(extractions) != 1 {
		t.Fatalf("Expected 1 extraction, got %d", len(extractions))
	}

	retrieved := extractions[0]
	if retrieved.AgentName != event.AgentName {
		t.Errorf("Agent name mismatch: got %s, want %s", retrieved.AgentName, event.AgentName)
	}
	if retrieved.EventType != event.EventType {
		t.Errorf("Event type mismatch: got %s, want %s", retrieved.EventType, event.EventType)
	}
	if retrieved.Pattern != event.Pattern {
		t.Errorf("Pattern mismatch: got %s, want %s", retrieved.Pattern, event.Pattern)
	}
}

func TestExtractionStore_SaveBatch(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create batch of extractions
	events := []*ExtractionEvent{}
	for i := 0; i < 10; i++ {
		event := &ExtractionEvent{
			AgentName:    "test-agent",
			SessionID:    "session-001",
			Timestamp:    time.Now().Add(time.Duration(i) * time.Second),
			EventType:    "log",
			Pattern:      "log_entry",
			MatchedValue: fmt.Sprintf("Log entry %d", i),
			OriginalLine: fmt.Sprintf("INFO: Log entry %d", i),
			LineNumber:   i,
			Metadata:     map[string]interface{}{"index": i},
		}
		events = append(events, event)
	}

	// Save batch
	start := time.Now()
	if err := store.SaveExtractionBatch(events); err != nil {
		t.Fatalf("Failed to save batch: %v", err)
	}
	duration := time.Since(start)

	t.Logf("Batch insert of 10 records took %v", duration)

	// Verify count
	extractions, err := store.GetExtractionsByAgent("test-agent", 100)
	if err != nil {
		t.Fatalf("Failed to get extractions: %v", err)
	}

	if len(extractions) != 10 {
		t.Errorf("Expected 10 extractions, got %d", len(extractions))
	}
}

func TestExtractionStore_GetByType(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create extractions of different types
	types := []string{"error", "warning", "info", "error", "info"}
	for i, eventType := range types {
		event := &ExtractionEvent{
			AgentName:    "test-agent",
			SessionID:    "session-001",
			Timestamp:    time.Now(),
			EventType:    eventType,
			Pattern:      "pattern_" + eventType,
			MatchedValue: fmt.Sprintf("Value %d", i),
			LineNumber:   i,
		}
		if err := store.SaveExtraction(event); err != nil {
			t.Fatalf("Failed to save extraction: %v", err)
		}
	}

	// Get only errors
	errors, err := store.GetExtractionsByType("test-agent", "error", 10)
	if err != nil {
		t.Fatalf("Failed to get errors: %v", err)
	}

	if len(errors) != 2 {
		t.Errorf("Expected 2 errors, got %d", len(errors))
	}

	for _, e := range errors {
		if e.EventType != "error" {
			t.Errorf("Expected error type, got %s", e.EventType)
		}
	}
}

func TestExtractionStore_GetByPattern(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create extractions with different patterns
	patterns := []string{"pattern_a", "pattern_b", "pattern_a", "pattern_c"}
	for i, pattern := range patterns {
		event := &ExtractionEvent{
			AgentName:    "test-agent",
			SessionID:    "session-001",
			Timestamp:    time.Now(),
			EventType:    "log",
			Pattern:      pattern,
			MatchedValue: fmt.Sprintf("Value %d", i),
			LineNumber:   i,
		}
		if err := store.SaveExtraction(event); err != nil {
			t.Fatalf("Failed to save extraction: %v", err)
		}
	}

	// Get pattern_a extractions
	results, err := store.GetExtractionsByPattern("test-agent", "pattern_a", 10)
	if err != nil {
		t.Fatalf("Failed to get by pattern: %v", err)
	}

	if len(results) != 2 {
		t.Errorf("Expected 2 pattern_a extractions, got %d", len(results))
	}

	for _, e := range results {
		if e.Pattern != "pattern_a" {
			t.Errorf("Expected pattern_a, got %s", e.Pattern)
		}
	}
}

func TestExtractionStore_GetBySession(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create extractions for different sessions
	sessions := []string{"session-001", "session-002", "session-001"}
	for i, sessionID := range sessions {
		event := &ExtractionEvent{
			AgentName:    "test-agent",
			SessionID:    sessionID,
			Timestamp:    time.Now(),
			EventType:    "log",
			Pattern:      "pattern",
			MatchedValue: fmt.Sprintf("Value %d", i),
			LineNumber:   i,
		}
		if err := store.SaveExtraction(event); err != nil {
			t.Fatalf("Failed to save extraction: %v", err)
		}
	}

	// Get session-001 extractions
	results, err := store.GetExtractionsBySession("session-001")
	if err != nil {
		t.Fatalf("Failed to get by session: %v", err)
	}

	if len(results) != 2 {
		t.Errorf("Expected 2 session-001 extractions, got %d", len(results))
	}

	// Verify they're in chronological order
	if len(results) == 2 {
		if results[0].Timestamp.After(results[1].Timestamp) {
			t.Error("Results not in chronological order")
		}
	}
}

func TestExtractionStore_GetStats(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create extractions with various types and risk levels
	testData := []struct {
		EventType string
		RiskLevel string
	}{
		{"error", "high"},
		{"error", "medium"},
		{"warning", "medium"},
		{"info", "low"},
		{"error", "high"},
	}

	for i, data := range testData {
		event := &ExtractionEvent{
			AgentName:    "test-agent",
			SessionID:    "session-001",
			Timestamp:    time.Now(),
			EventType:    data.EventType,
			Pattern:      "pattern",
			MatchedValue: fmt.Sprintf("Value %d", i),
			RiskLevel:    data.RiskLevel,
			LineNumber:   i,
		}
		if err := store.SaveExtraction(event); err != nil {
			t.Fatalf("Failed to save extraction: %v", err)
		}
	}

	// Get stats
	stats, err := store.GetExtractionStats("test-agent")
	if err != nil {
		t.Fatalf("Failed to get stats: %v", err)
	}

	if stats.TotalExtractions != 5 {
		t.Errorf("Expected 5 total extractions, got %d", stats.TotalExtractions)
	}

	if stats.ExtractionsByType["error"] != 3 {
		t.Errorf("Expected 3 errors, got %d", stats.ExtractionsByType["error"])
	}

	if stats.ExtractionsByType["warning"] != 1 {
		t.Errorf("Expected 1 warning, got %d", stats.ExtractionsByType["warning"])
	}

	if stats.ExtractionsByRisk["high"] != 2 {
		t.Errorf("Expected 2 high risk, got %d", stats.ExtractionsByRisk["high"])
	}
}

func TestCodeBlock_SaveAndRetrieve(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create test code block
	content := "function test() {\n  return 42;\n}"
	digest := fmt.Sprintf("%x", sha256.Sum256([]byte(content)))

	block := &CodeBlock{
		AgentName:  "test-agent",
		SessionID:  "session-001",
		Timestamp:  time.Now(),
		Language:   "javascript",
		Content:    content,
		LineStart:  10,
		LineEnd:    12,
		Context:    map[string]interface{}{"file": "test.js"},
		Parseable:  true,
		Digest:     digest,
	}

	// Save code block
	if err := store.SaveCodeBlock(block); err != nil {
		t.Fatalf("Failed to save code block: %v", err)
	}

	if block.ID == 0 {
		t.Error("ID not set after save")
	}

	// Retrieve code blocks
	blocks, err := store.GetCodeBlocks("test-agent", "javascript", 10)
	if err != nil {
		t.Fatalf("Failed to get code blocks: %v", err)
	}

	if len(blocks) != 1 {
		t.Fatalf("Expected 1 code block, got %d", len(blocks))
	}

	retrieved := blocks[0]
	if retrieved.Language != "javascript" {
		t.Errorf("Language mismatch: got %s, want javascript", retrieved.Language)
	}
	if retrieved.Content != content {
		t.Errorf("Content mismatch")
	}
	if retrieved.Digest != digest {
		t.Errorf("Digest mismatch")
	}
}

func TestCodeBlock_Deduplication(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	content := "console.log('test');"
	digest := fmt.Sprintf("%x", sha256.Sum256([]byte(content)))

	// Save same code block twice
	for i := 0; i < 2; i++ {
		block := &CodeBlock{
			AgentName:  "test-agent",
			SessionID:  fmt.Sprintf("session-%03d", i),
			Timestamp:  time.Now(),
			Language:   "javascript",
			Content:    content,
			Digest:     digest,
		}

		// First save should succeed, second should be ignored (INSERT OR IGNORE)
		if err := store.SaveCodeBlock(block); err != nil {
			t.Fatalf("Failed to save code block %d: %v", i, err)
		}
	}

	// Should only have 1 block due to unique digest
	blocks, err := store.GetCodeBlocks("test-agent", "javascript", 10)
	if err != nil {
		t.Fatalf("Failed to get code blocks: %v", err)
	}

	if len(blocks) != 1 {
		t.Errorf("Expected 1 code block (deduplicated), got %d", len(blocks))
	}
}

func TestCodeBlock_FilterByLanguage(t *testing.T) {
	dbPath := ":memory:"
	store, err := NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create code blocks in different languages
	languages := []string{"python", "javascript", "go", "python"}
	for i, lang := range languages {
		content := fmt.Sprintf("code in %s %d", lang, i)
		digest := fmt.Sprintf("%x", sha256.Sum256([]byte(content)))

		block := &CodeBlock{
			AgentName:  "test-agent",
			SessionID:  "session-001",
			Timestamp:  time.Now(),
			Language:   lang,
			Content:    content,
			Digest:     digest,
		}

		if err := store.SaveCodeBlock(block); err != nil {
			t.Fatalf("Failed to save code block: %v", err)
		}
	}

	// Get only Python blocks
	pythonBlocks, err := store.GetCodeBlocks("test-agent", "python", 10)
	if err != nil {
		t.Fatalf("Failed to get Python blocks: %v", err)
	}

	if len(pythonBlocks) != 2 {
		t.Errorf("Expected 2 Python blocks, got %d", len(pythonBlocks))
	}

	for _, block := range pythonBlocks {
		if block.Language != "python" {
			t.Errorf("Expected python language, got %s", block.Language)
		}
	}

	// Get all blocks (no language filter)
	allBlocks, err := store.GetCodeBlocks("test-agent", "", 10)
	if err != nil {
		t.Fatalf("Failed to get all blocks: %v", err)
	}

	if len(allBlocks) != 4 {
		t.Errorf("Expected 4 total blocks, got %d", len(allBlocks))
	}
}

func TestExtractionStore_Persistence(t *testing.T) {
	// Create temporary database file
	dbPath := "/tmp/test_extraction_store.db"
	defer os.Remove(dbPath)

	// Create store and save data
	store1, err := NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}

	event := &ExtractionEvent{
		AgentName:    "test-agent",
		SessionID:    "session-001",
		Timestamp:    time.Now(),
		EventType:    "test",
		Pattern:      "test_pattern",
		MatchedValue: "test_value",
		LineNumber:   1,
	}

	if err := store1.SaveExtraction(event); err != nil {
		t.Fatalf("Failed to save extraction: %v", err)
	}

	store1.Close()

	// Reopen store and verify data persists
	store2, err := NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to reopen store: %v", err)
	}
	defer store2.Close()

	extractions, err := store2.GetExtractionsByAgent("test-agent", 10)
	if err != nil {
		t.Fatalf("Failed to get extractions: %v", err)
	}

	if len(extractions) != 1 {
		t.Errorf("Expected 1 extraction after reopen, got %d", len(extractions))
	}
}

func BenchmarkExtractionStore_SaveSingle(b *testing.B) {
	dbPath := ":memory:"
	store, err := NewExtractionStore(dbPath)
	if err != nil {
		b.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	event := &ExtractionEvent{
		AgentName:    "bench-agent",
		SessionID:    "session-001",
		Timestamp:    time.Now(),
		EventType:    "log",
		Pattern:      "pattern",
		MatchedValue: "value",
		LineNumber:   1,
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		event.LineNumber = i
		if err := store.SaveExtraction(event); err != nil {
			b.Fatalf("Failed to save: %v", err)
		}
	}
}

func BenchmarkExtractionStore_SaveBatch(b *testing.B) {
	dbPath := ":memory:"
	store, err := NewExtractionStore(dbPath)
	if err != nil {
		b.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	// Create batch of 100 events
	events := make([]*ExtractionEvent, 100)
	for i := range events {
		events[i] = &ExtractionEvent{
			AgentName:    "bench-agent",
			SessionID:    "session-001",
			Timestamp:    time.Now(),
			EventType:    "log",
			Pattern:      "pattern",
			MatchedValue: fmt.Sprintf("value-%d", i),
			LineNumber:   i,
		}
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		if err := store.SaveExtractionBatch(events); err != nil {
			b.Fatalf("Failed to save batch: %v", err)
		}
	}
}
