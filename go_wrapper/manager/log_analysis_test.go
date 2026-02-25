package manager

import (
	"os"
	"path/filepath"
	"testing"
)

// TestPatternLearningWithRealLogs tests pattern learning with actual agent logs
func TestPatternLearningWithRealLogs(t *testing.T) {
	// Find existing log files
	logFiles, err := findAgentLogs("../bin/logs/agents")
	if err != nil {
		t.Skipf("No agent logs found: %v", err)
	}

	if len(logFiles) == 0 {
		t.Skip("No agent logs available for testing")
	}

	// Initialize pattern database
	dbPath := "../data/patterns/test_patterns.db"
	os.Remove(dbPath) // Clean start
	os.MkdirAll(filepath.Dir(dbPath), 0755)

	db, err := NewPatternDatabase(dbPath)
	if err != nil {
		t.Fatalf("Failed to create database: %v", err)
	}
	defer db.Close()

	// Seed with initial patterns
	seedTestPatterns(db, t)

	// Process each log file
	for _, logFile := range logFiles {
		t.Run(filepath.Base(logFile), func(t *testing.T) {
			testLogProcessing(t, db, logFile)
		})
	}

	// Check database stats
	stats := db.GetStats()
	t.Logf("Final database stats: %+v", stats)

	if stats["total_patterns"].(int) == 0 {
		t.Error("No patterns in database")
	}
}

// TestSemanticExtraction tests semantic information extraction
func TestSemanticExtraction(t *testing.T) {
	logFiles, err := findAgentLogs("../bin/logs/agents")
	if err != nil {
		t.Skipf("No agent logs found: %v", err)
	}

	if len(logFiles) == 0 {
		t.Skip("No agent logs available for testing")
	}

	for _, logFile := range logFiles {
		t.Run(filepath.Base(logFile), func(t *testing.T) {
			testSemanticExtraction(t, logFile)
		})
	}
}

// TestLearningWorker tests the learning worker with real data
func TestLearningWorker(t *testing.T) {
	// Setup database
	dbPath := "../data/patterns/learning_test.db"
	os.Remove(dbPath)
	os.MkdirAll(filepath.Dir(dbPath), 0755)

	db, err := NewPatternDatabase(dbPath)
	if err != nil {
		t.Fatalf("Failed to create database: %v", err)
	}
	defer db.Close()

	// Seed with minimal patterns
	seedMinimalPatterns(db, t)

	// Find and process logs
	logFiles, err := findAgentLogs("../bin/logs/agents")
	if err != nil || len(logFiles) == 0 {
		t.Skip("No logs available")
	}

	// Process first log to generate unknowns
	reader := NewLogReader(logFiles[0], "test_agent", db)
	report, err := reader.ProcessLog()
	if err != nil {
		t.Fatalf("Failed to process log: %v", err)
	}

	t.Logf("Processed %d lines, %d unknowns", report.LinesRead, report.UnknownLines)

	// Run learning worker
	if report.UnknownLines > 0 {
		learner := NewLearningWorker(db)
		learningReport, err := learner.AnalyzeUnknowns(100)
		if err != nil {
			t.Fatalf("Learning failed: %v", err)
		}

		t.Logf("Learning report: %s", learningReport.Summary())

		// Check if patterns were proposed
		if len(learningReport.ProposedPatterns) > 0 {
			t.Logf("✓ Successfully proposed %d new patterns", len(learningReport.ProposedPatterns))
		}
	}
}

// Helper functions

func findAgentLogs(baseDir string) ([]string, error) {
	logs := make([]string, 0)

	err := filepath.Walk(baseDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil // Continue on error
		}

		if !info.IsDir() && filepath.Ext(path) == ".log" && filepath.Base(path) != "stderr.log" {
			logs = append(logs, path)
		}

		return nil
	})

	return logs, err
}

func seedTestPatterns(db *PatternDatabase, t *testing.T) {
	patterns := []Pattern{
		{
			Name:            "bash_command",
			Regex:           `⏺\s+Bash\((.+)\)`,
			Category:        "tool_use",
			Confidence:      0.95,
			Action:          "execute_bash",
			TargetWorker:    "bash_executor",
			ProposedBy:      "test_seed",
			Tested:          true,
			TestSuccessRate: 0.98,
		},
		{
			Name:            "read_file",
			Regex:           `⏺\s+Read\((.+)\)`,
			Category:        "tool_use",
			Confidence:      0.98,
			Action:          "read_file",
			TargetWorker:    "file_reader",
			ProposedBy:      "test_seed",
			Tested:          true,
			TestSuccessRate: 0.99,
		},
		{
			Name:            "thinking_state",
			Regex:           `✢.+…\s+\(thinking\)`,
			Category:        "state_change",
			Confidence:      0.92,
			Action:          "update_state",
			TargetWorker:    "state_tracker",
			ProposedBy:      "test_seed",
			Tested:          true,
			TestSuccessRate: 0.95,
		},
		{
			Name:            "permission_prompt",
			Regex:           `⏵⏵\s+(bypass|request)\s+permissions?`,
			Category:        "permission",
			Confidence:      0.96,
			Action:          "handle_permission",
			TargetWorker:    "permission_handler",
			ProposedBy:      "test_seed",
			Tested:          true,
			TestSuccessRate: 0.97,
		},
	}

	for _, pattern := range patterns {
		_, err := db.AddPattern(pattern)
		if err != nil {
			t.Logf("Warning: Failed to add pattern %s: %v", pattern.Name, err)
		}
	}
}

func seedMinimalPatterns(db *PatternDatabase, t *testing.T) {
	patterns := []Pattern{
		{
			Name:            "bash_command",
			Regex:           `⏺\s+Bash\((.+)\)`,
			Category:        "tool_use",
			Confidence:      0.95,
			ProposedBy:      "minimal_seed",
			Tested:          true,
			TestSuccessRate: 0.98,
		},
	}

	for _, pattern := range patterns {
		db.AddPattern(pattern)
	}
}

func testLogProcessing(t *testing.T, db *PatternDatabase, logFile string) {
	reader := NewLogReader(logFile, filepath.Base(filepath.Dir(logFile)), db)

	report, err := reader.ProcessLog()
	if err != nil {
		t.Errorf("Failed to process log: %v", err)
		return
	}

	t.Logf("Log: %s", filepath.Base(logFile))
	t.Logf("  Lines read: %d", report.LinesRead)
	t.Logf("  Matched: %d (%.2f%%)", report.MatchedLines, float64(report.MatchedLines)/float64(report.LinesRead)*100)
	t.Logf("  Unknown: %d (%.2f%%)", report.UnknownLines, float64(report.UnknownLines)/float64(report.LinesRead)*100)

	if report.LinesRead == 0 {
		t.Error("No lines read from log file")
	}

	// Display some matches
	if len(report.Matches) > 0 {
		t.Logf("  Sample matches:")
		for i, match := range report.Matches {
			if i >= 3 {
				break
			}
			t.Logf("    Line %d: %s", match.LineNumber, match.PatternName)
		}
	}

	// Display some unknowns
	if len(report.Unknowns) > 0 {
		t.Logf("  Sample unknowns:")
		for i, unknown := range report.Unknowns {
			if i >= 3 {
				break
			}
			t.Logf("    Line %d: %s", unknown.LineNumber, truncate(unknown.Content, 60))
		}
	}
}

func testSemanticExtraction(t *testing.T, logFile string) {
	extractor := NewSemanticExtractor()

	file, err := os.Open(logFile)
	if err != nil {
		t.Errorf("Failed to open log: %v", err)
		return
	}
	defer file.Close()

	// Read and process each line
	lineNumber := 0
	content, _ := os.ReadFile(logFile)
	lines := string(content)

	for _, line := range splitLines(lines) {
		lineNumber++
		extractor.ProcessLine(line, lineNumber)
	}

	state := extractor.GetState()

	t.Logf("\n%s", state.Summary())

	// Assertions
	if state.AgentState == "" {
		t.Error("Agent state not detected")
	}

	t.Logf("Final state: %s", state.AgentState)
	t.Logf("Tasks found: %d", len(state.TaskList))
	t.Logf("Errors found: %d", len(state.Errors))
	t.Logf("Completed items: %d", len(state.CompletedItems))
	t.Logf("Blocked items: %d", len(state.BlockedItems))
}

func splitLines(s string) []string {
	lines := make([]string, 0)
	current := ""

	for _, char := range s {
		if char == '\n' {
			lines = append(lines, current)
			current = ""
		} else {
			current += string(char)
		}
	}

	if current != "" {
		lines = append(lines, current)
	}

	return lines
}

// Benchmark tests

func BenchmarkPatternMatching(b *testing.B) {
	dbPath := "../data/patterns/bench_test.db"
	os.Remove(dbPath)
	os.MkdirAll(filepath.Dir(dbPath), 0755)

	db, _ := NewPatternDatabase(dbPath)
	defer db.Close()

	// Seed patterns
	seedTestPatterns(db, &testing.T{})

	// Find a log file
	logFiles, _ := findAgentLogs("../bin/logs/agents")
	if len(logFiles) == 0 {
		b.Skip("No logs available")
	}

	reader := NewLogReader(logFiles[0], "bench_agent", db)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		reader.ProcessLog()
	}
}

func BenchmarkSemanticExtraction(b *testing.B) {
	logFiles, _ := findAgentLogs("../bin/logs/agents")
	if len(logFiles) == 0 {
		b.Skip("No logs available")
	}

	content, _ := os.ReadFile(logFiles[0])
	lines := splitLines(string(content))

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		extractor := NewSemanticExtractor()
		for lineNum, line := range lines {
			extractor.ProcessLine(line, lineNum)
		}
	}
}
