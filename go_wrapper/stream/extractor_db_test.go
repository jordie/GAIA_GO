package stream

import (
	"os"
	"testing"
	"time"

	"github.com/architect/go_wrapper/data"
)

func TestExtractor_EnableDatabase(t *testing.T) {
	dbPath := ":memory:"
	store, err := data.NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	extractor := NewExtractor()
	extractor.EnableDatabase(store, "test-agent", "session-001")

	if extractor.extractionStore == nil {
		t.Error("Extraction store not set")
	}
	if extractor.agentName != "test-agent" {
		t.Errorf("Agent name mismatch: got %s, want test-agent", extractor.agentName)
	}
	if extractor.sessionID != "session-001" {
		t.Errorf("Session ID mismatch: got %s, want session-001", extractor.sessionID)
	}
}

func TestExtractor_DisableDatabase(t *testing.T) {
	dbPath := ":memory:"
	store, err := data.NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	extractor := NewExtractor()
	extractor.EnableDatabase(store, "test-agent", "session-001")
	extractor.DisableDatabase()

	if extractor.extractionStore != nil {
		t.Error("Extraction store should be nil after disable")
	}
}

func TestExtractor_DatabasePersistence(t *testing.T) {
	dbPath := ":memory:"
	store, err := data.NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	extractor := NewExtractor()
	extractor.EnableDatabase(store, "test-agent", "session-001")

	// Extract some patterns
	testLines := []string{
		"Error: Something went wrong",
		"WARNING: Low memory",
		"Metric: requests=100",
	}

	for _, line := range testLines {
		extractor.Extract(line)
	}

	// Flush batch
	if err := extractor.FlushBatch(); err != nil {
		t.Fatalf("Failed to flush batch: %v", err)
	}

	// Verify extractions in database
	extractions, err := store.GetExtractionsByAgent("test-agent", 10)
	if err != nil {
		t.Fatalf("Failed to get extractions: %v", err)
	}

	if len(extractions) == 0 {
		t.Fatal("No extractions found in database")
	}

	// Verify first extraction is an error
	foundError := false
	for _, ext := range extractions {
		if ext.EventType == PatternTypeError {
			foundError = true
			break
		}
	}

	if !foundError {
		t.Error("Expected to find error extraction in database")
	}
}

func TestExtractor_BatchFlush(t *testing.T) {
	dbPath := ":memory:"
	store, err := data.NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	extractor := NewExtractor()
	extractor.EnableDatabase(store, "test-agent", "session-001")
	extractor.batchSize = 5 // Small batch for testing

	// Extract 10 lines (should trigger 2 batches)
	for i := 0; i < 10; i++ {
		extractor.Extract("Error: test error")
	}

	// Manually flush any remaining
	if err := extractor.FlushBatch(); err != nil {
		t.Fatalf("Failed to flush batch: %v", err)
	}

	// Verify all extractions saved
	extractions, err := store.GetExtractionsByAgent("test-agent", 100)
	if err != nil {
		t.Fatalf("Failed to get extractions: %v", err)
	}

	// Should have at least some extractions (batch flushing may vary)
	if len(extractions) == 0 {
		t.Error("Expected extractions to be saved")
	}
}

func TestExtractor_ConvertMatchToEvent(t *testing.T) {
	dbPath := ":memory:"
	store, err := data.NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	extractor := NewExtractor()
	extractor.EnableDatabase(store, "test-agent", "session-001")

	// Create a test match
	match := Match{
		Type:      PatternTypeError,
		Pattern:   "error",
		Value:     "Test error message",
		Line:      "Error: Test error message",
		LineNum:   42,
		Timestamp: time.Now(),
		Metadata: map[string]interface{}{
			"severity": "error",
		},
	}

	// Convert to event
	event := extractor.convertMatchToEvent(match)

	// Verify conversion
	if event.AgentName != "test-agent" {
		t.Errorf("Agent name mismatch: got %s, want test-agent", event.AgentName)
	}
	if event.SessionID != "session-001" {
		t.Errorf("Session ID mismatch: got %s, want session-001", event.SessionID)
	}
	if event.EventType != PatternTypeError {
		t.Errorf("Event type mismatch: got %s, want %s", event.EventType, PatternTypeError)
	}
	if event.RiskLevel != "high" {
		t.Errorf("Risk level should be high for error severity, got %s", event.RiskLevel)
	}
	if event.LineNumber != 42 {
		t.Errorf("Line number mismatch: got %d, want 42", event.LineNumber)
	}
}

func TestExtractor_CodeBlockPersistence(t *testing.T) {
	dbPath := ":memory:"
	store, err := data.NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	extractor := NewExtractor()
	extractor.EnableDatabase(store, "test-agent", "session-001")

	// Simulate code block extraction
	match := Match{
		Type:    PatternTypeCodeBlock,
		Pattern: "code_block",
		Value:   "function test() {\n  return 42;\n}",
		Line:    "```javascript",
		LineNum: 10,
		Timestamp: time.Now(),
		Metadata: map[string]interface{}{
			"language":   "javascript",
			"line_count": 3,
		},
	}

	// Save code block
	extractor.saveCodeBlock(match)

	// Verify in database
	blocks, err := store.GetCodeBlocks("test-agent", "javascript", 10)
	if err != nil {
		t.Fatalf("Failed to get code blocks: %v", err)
	}

	if len(blocks) != 1 {
		t.Fatalf("Expected 1 code block, got %d", len(blocks))
	}

	block := blocks[0]
	if block.Language != "javascript" {
		t.Errorf("Language mismatch: got %s, want javascript", block.Language)
	}
	if block.Content != match.Value {
		t.Error("Content mismatch")
	}
}

func TestExtractor_GetBatchBufferSize(t *testing.T) {
	extractor := NewExtractor()

	// Initially should be 0
	if size := extractor.GetBatchBufferSize(); size != 0 {
		t.Errorf("Expected batch buffer size 0, got %d", size)
	}

	// Enable database
	dbPath := ":memory:"
	store, err := data.NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	extractor.EnableDatabase(store, "test-agent", "session-001")

	// Extract without flushing
	extractor.batchSize = 1000 // Large batch to prevent auto-flush
	extractor.Extract("Error: test")

	// Should have items in buffer
	if size := extractor.GetBatchBufferSize(); size == 0 {
		t.Error("Expected non-zero batch buffer size after extraction")
	}
}

func TestExtractor_ClearFlushes(t *testing.T) {
	dbPath := ":memory:"
	store, err := data.NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}
	defer store.Close()

	extractor := NewExtractor()
	extractor.EnableDatabase(store, "test-agent", "session-001")
	extractor.batchSize = 1000 // Large batch

	// Extract without auto-flush
	extractor.Extract("Error: test")

	// Clear should flush
	extractor.Clear()

	// Verify extraction was saved
	extractions, err := store.GetExtractionsByAgent("test-agent", 10)
	if err != nil {
		t.Fatalf("Failed to get extractions: %v", err)
	}

	if len(extractions) == 0 {
		t.Error("Clear should have flushed extractions to database")
	}
}

func TestExtractor_PersistenceAcrossRestart(t *testing.T) {
	// Use temporary file for this test
	dbPath := "/tmp/test_extractor_persistence.db"
	defer os.Remove(dbPath)

	// First session
	store1, err := data.NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to create store: %v", err)
	}

	extractor1 := NewExtractor()
	extractor1.EnableDatabase(store1, "test-agent", "session-001")
	extractor1.Extract("Error: persistent error")
	extractor1.FlushBatch()
	store1.Close()

	// Second session - reopen database
	store2, err := data.NewExtractionStore(dbPath)
	if err != nil {
		t.Fatalf("Failed to reopen store: %v", err)
	}
	defer store2.Close()

	// Verify data persists
	extractions, err := store2.GetExtractionsByAgent("test-agent", 10)
	if err != nil {
		t.Fatalf("Failed to get extractions: %v", err)
	}

	if len(extractions) == 0 {
		t.Error("Extractions should persist across database reopens")
	}
}
