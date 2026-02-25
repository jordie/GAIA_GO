package main

import (
	"fmt"
	"log"
	"os"
	"time"

	"github.com/architect/go_wrapper/manager"
)

func main() {
	fmt.Println("=== Pattern Learning System Demo ===\n")

	// Initialize pattern database
	dbPath := "data/patterns/patterns.db"
	os.MkdirAll("data/patterns", 0755)

	db, err := manager.NewPatternDatabase(dbPath)
	if err != nil {
		log.Fatalf("Failed to initialize pattern database: %v", err)
	}
	defer db.Close()

	fmt.Printf("Pattern database initialized: %s\n\n", dbPath)

	// Seed with some initial patterns
	fmt.Println("--- Seeding Initial Patterns ---")
	seedPatterns(db)

	// Get stats before processing
	stats := db.GetStats()
	fmt.Printf("\nDatabase Stats (before processing):\n")
	fmt.Printf("  Total patterns: %d\n", stats["total_patterns"])
	fmt.Printf("  Tested patterns: %d\n", stats["tested_patterns"])
	fmt.Printf("  Total matches: %d\n", stats["total_matches"])
	fmt.Printf("  Unknown chunks: %d\n\n", stats["unknown_chunks"])

	// Process a log file
	if len(os.Args) < 2 {
		fmt.Println("Usage: pattern_learning_demo <log_file>")
		fmt.Println("\nNo log file specified, using demo mode...")
		demoMode(db)
		return
	}

	logFile := os.Args[1]

	fmt.Printf("--- Processing Log File ---\n")
	fmt.Printf("Log: %s\n\n", logFile)

	// Create log reader
	reader := manager.NewLogReader(logFile, "demo_agent", db)

	// Process the log
	report, err := reader.ProcessLog()
	if err != nil {
		log.Fatalf("Failed to process log: %v", err)
	}

	// Display processing report
	fmt.Println(report.Summary())

	// Get updated stats
	stats = db.GetStats()
	fmt.Printf("\nDatabase Stats (after processing):\n")
	fmt.Printf("  Total patterns: %d\n", stats["total_patterns"])
	fmt.Printf("  Tested patterns: %d\n", stats["tested_patterns"])
	fmt.Printf("  Total matches: %d\n", stats["total_matches"])
	fmt.Printf("  Unknown chunks: %d\n", stats["unknown_chunks"])
	fmt.Printf("  Unanalyzed chunks: %d\n\n", stats["unanalyzed_chunks"])

	// Run learning worker if there are unanalyzed chunks
	if stats["unanalyzed_chunks"].(int) > 0 {
		fmt.Println("--- Running Learning Worker ---\n")

		learner := manager.NewLearningWorker(db)
		learningReport, err := learner.AnalyzeUnknowns(100)
		if err != nil {
			log.Fatalf("Learning worker failed: %v", err)
		}

		// Display learning report
		fmt.Println(learningReport.Summary())

		// Get final stats
		stats = db.GetStats()
		fmt.Printf("Database Stats (after learning):\n")
		fmt.Printf("  Total patterns: %d\n", stats["total_patterns"])
		fmt.Printf("  Tested patterns: %d\n", stats["tested_patterns"])
		fmt.Printf("  Unknown chunks: %d\n", stats["unknown_chunks"])
		fmt.Printf("  Analyzed chunks: %d\n\n", stats["analyzed_chunks"])
	}

	fmt.Println("Demo complete!")
}

// seedPatterns adds some initial patterns to the database
func seedPatterns(db *manager.PatternDatabase) {
	patterns := []manager.Pattern{
		{
			Name:            "bash_command",
			Regex:           `⏺ Bash\((.+)\)`,
			Category:        "tool_use",
			Confidence:      0.95,
			Action:          "execute_bash",
			TargetWorker:    "bash_executor",
			ProposedBy:      "manual",
			Tested:          true,
			TestSuccessRate: 0.98,
			Metadata:        map[string]interface{}{"safe": false},
		},
		{
			Name:            "read_file",
			Regex:           `⏺ Read\((.+)\)`,
			Category:        "tool_use",
			Confidence:      0.98,
			Action:          "read_file",
			TargetWorker:    "file_reader",
			ProposedBy:      "manual",
			Tested:          true,
			TestSuccessRate: 0.99,
			Metadata:        map[string]interface{}{"safe": true},
		},
		{
			Name:            "edit_file",
			Regex:           `⏺ Edit\((.+)\)`,
			Category:        "tool_use",
			Confidence:      0.96,
			Action:          "edit_file",
			TargetWorker:    "file_editor",
			ProposedBy:      "manual",
			Tested:          true,
			TestSuccessRate: 0.97,
			Metadata:        map[string]interface{}{"safe": false},
		},
		{
			Name:            "error_exit_code",
			Regex:           `Error: Exit code (\d+)`,
			Category:        "error",
			Confidence:      0.99,
			Action:          "log_error",
			TargetWorker:    "error_handler",
			ProposedBy:      "manual",
			Tested:          true,
			TestSuccessRate: 1.0,
		},
		{
			Name:            "thinking_state",
			Regex:           `✢ .+… \(thinking\)`,
			Category:        "state_change",
			Confidence:      0.92,
			Action:          "update_state",
			TargetWorker:    "state_tracker",
			ProposedBy:      "manual",
			Tested:          true,
			TestSuccessRate: 0.95,
		},
	}

	for _, pattern := range patterns {
		id, err := db.AddPattern(pattern)
		if err != nil {
			fmt.Printf("  ✗ Failed to add pattern '%s': %v\n", pattern.Name, err)
		} else {
			fmt.Printf("  ✓ Added pattern: %s (ID: %d)\n", pattern.Name, id)
		}
	}
}

// demoMode runs a demonstration with synthetic data
func demoMode(db *manager.PatternDatabase) {
	fmt.Println("\n--- Demo Mode: Generating Synthetic Log ---\n")

	// Create a temporary log file with synthetic data
	logFile := "/tmp/demo_agent_log.txt"
	content := `# stdout log - 2026-02-09T17:00:00-08:00
# Agent: demo_agent

⏺ Bash(ls -lh)
total 48K
-rw-r--r-- 1 user user 1.2K main.go

⏺ Read(config.json)
Reading file: config.json

⏺ Edit(app.py)
Editing file: app.py

Error: Exit code 1
Command failed with error

✢ Sublimating… (thinking)

⏺ Bash(go build ./...)
Building project...

Something unexpected happened here
This line doesn't match any pattern
Another unknown line with [timestamp] 17:00:05

✓ Task completed successfully

File processing finished at 17:00:10
Results saved to output.txt
`

	if err := os.WriteFile(logFile, []byte(content), 0644); err != nil {
		log.Fatalf("Failed to create demo log: %v", err)
	}

	fmt.Printf("Created demo log: %s\n\n", logFile)

	// Process the log
	reader := manager.NewLogReader(logFile, "demo_agent", db)
	report, err := reader.ProcessLog()
	if err != nil {
		log.Fatalf("Failed to process log: %v", err)
	}

	fmt.Println(report.Summary())

	// Run learning worker
	stats := db.GetStats()
	if stats["unanalyzed_chunks"].(int) > 0 {
		fmt.Println("--- Running Learning Worker ---\n")

		learner := manager.NewLearningWorker(db)
		learningReport, err := learner.AnalyzeUnknowns(100)
		if err != nil {
			log.Fatalf("Learning worker failed: %v", err)
		}

		fmt.Println(learningReport.Summary())
	}

	// Simulate processing again with learned patterns
	time.Sleep(1 * time.Second)
	fmt.Println("--- Re-processing Log with Learned Patterns ---\n")

	reader2 := manager.NewLogReader(logFile, "demo_agent", db)
	report2, err := reader2.ProcessLog()
	if err != nil {
		log.Fatalf("Failed to re-process log: %v", err)
	}

	fmt.Println(report2.Summary())

	// Show improvement
	improvement := float64(report2.MatchedLines-report.MatchedLines) / float64(report.LinesRead) * 100
	fmt.Printf("\n✓ Match rate improved by %.2f%% after learning!\n", improvement)
}
