package main

import (
	"fmt"
	"log"
	"os"
	"time"

	"github.com/architect/go_wrapper/stream"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: environment_demo <environment>")
		fmt.Println("Environments: dev, staging, prod, sandbox")
		os.Exit(1)
	}

	environment := os.Args[1]

	fmt.Printf("=== Environment & Feedback Demo ===\n")
	fmt.Printf("Testing environment: %s\n\n", environment)

	// Load environment configuration
	envManager, err := stream.NewEnvironmentManager("config/environments.json", environment)
	if err != nil {
		log.Fatalf("Failed to load environment: %v", err)
	}

	fmt.Printf("Environment loaded: %s\n", envManager.GetEnvironment().Name)
	fmt.Printf("Description: %s\n", envManager.GetEnvironment().Description)
	fmt.Printf("Working directory: %s\n", envManager.GetEnvironment().WorkingDir)
	fmt.Println()

	// Create feedback tracker
	feedback, err := stream.NewFeedbackTracker("demo_agent", environment, "data/feedback")
	if err != nil {
		log.Fatalf("Failed to create feedback tracker: %v", err)
	}
	defer feedback.Close()

	// Test various operations and record feedback
	fmt.Println("--- Testing Operations ---\n")

	// Test 1: Validate working directory
	fmt.Println("1. Validating working directory...")
	if err := envManager.ValidateWorkingDirectory(); err != nil {
		fmt.Printf("   ✗ Failed: %v\n", err)
		feedback.RecordFailure("validation", "working_directory", err.Error(), 0, nil)
	} else {
		fmt.Printf("   ✓ Working directory is correct\n")
		feedback.RecordSuccess("validation", "working_directory", "path_validation", 0, nil)
	}
	fmt.Println()

	// Test 2: Validate commands
	testCommands := []string{
		"ls -lh",
		"git status",
		"sudo rm -rf /",
		"curl https://example.com",
		"python3 script.py",
	}

	fmt.Println("2. Testing command validation...")
	for _, cmd := range testCommands {
		start := time.Now()
		if err := envManager.ValidateCommand(cmd); err != nil {
			fmt.Printf("   ✗ %s - BLOCKED: %v\n", cmd, err)
			feedback.RecordBlocked(cmd, err.Error(), "high")
		} else {
			duration := time.Since(start)
			fmt.Printf("   ✓ %s - ALLOWED\n", cmd)
			feedback.RecordSuccess("command_validation", cmd, "command_check", duration, nil)
		}
	}
	fmt.Println()

	// Test 3: Validate paths
	testPaths := []string{
		"/tmp/test.txt",
		"/System/Library/test",
		"/Users/jgirmay/Desktop/test",
		"./local_file.txt",
	}

	fmt.Println("3. Testing path validation...")
	for _, path := range testPaths {
		start := time.Now()
		if err := envManager.ValidatePath(path); err != nil {
			fmt.Printf("   ✗ %s - RESTRICTED: %v\n", path, err)
			feedback.RecordBlocked(path, err.Error(), "high")
		} else {
			duration := time.Since(start)
			fmt.Printf("   ✓ %s - ACCESSIBLE\n", path)
			feedback.RecordSuccess("path_validation", path, "path_check", duration, nil)
		}
	}
	fmt.Println()

	// Test 4: Validate write operations
	fmt.Println("4. Testing write operation validation...")
	testWritePath := "/tmp/test_write.txt"
	start := time.Now()
	if err := envManager.ValidateWrite(testWritePath); err != nil {
		fmt.Printf("   ✗ Write to %s - DENIED: %v\n", testWritePath, err)
		feedback.RecordBlocked("write:"+testWritePath, err.Error(), "medium")
	} else {
		duration := time.Since(start)
		fmt.Printf("   ✓ Write to %s - ALLOWED\n", testWritePath)
		feedback.RecordSuccess("write_validation", testWritePath, "write_check", duration, nil)
	}
	fmt.Println()

	// Test 5: Validate delete operations
	fmt.Println("5. Testing delete operation validation...")
	testDeletePath := "/tmp/test_delete.txt"
	start = time.Now()
	if err := envManager.ValidateDelete(testDeletePath); err != nil {
		fmt.Printf("   ✗ Delete %s - DENIED: %v\n", testDeletePath, err)
		feedback.RecordBlocked("delete:"+testDeletePath, err.Error(), "high")
	} else {
		duration := time.Since(start)
		fmt.Printf("   ✓ Delete %s - ALLOWED\n", testDeletePath)
		feedback.RecordSuccess("delete_validation", testDeletePath, "delete_check", duration, nil)
	}
	fmt.Println()

	// Test 6: Validate network operations
	fmt.Println("6. Testing network operation validation...")
	start = time.Now()
	if err := envManager.ValidateNetwork(); err != nil {
		fmt.Printf("   ✗ Network access - DENIED: %v\n", err)
		feedback.RecordBlocked("network_access", err.Error(), "medium")
	} else {
		duration := time.Since(start)
		fmt.Printf("   ✓ Network access - ALLOWED\n")
		feedback.RecordSuccess("network_validation", "network_check", "network_check", duration, nil)
	}
	fmt.Println()

	// Display environment summary
	fmt.Println("--- Environment Constraints Summary ---")
	constraints := envManager.GetConstraintsSummary()
	for key, value := range constraints {
		fmt.Printf("  %s: %v\n", key, value)
	}
	fmt.Println()

	// Display feedback statistics
	fmt.Println("--- Feedback Statistics ---")
	stats := feedback.GetStats()
	fmt.Printf("Total outcomes: %d\n", stats.TotalOutcomes)
	fmt.Printf("Success rate: %.2f%%\n", stats.SuccessRate)
	fmt.Println("\nBy task type:")
	for taskType, count := range stats.ByTaskType {
		fmt.Printf("  %s: %d\n", taskType, count)
	}

	if len(stats.TopSuccesses) > 0 {
		fmt.Println("\nSuccessful patterns:")
		for _, success := range stats.TopSuccesses {
			fmt.Printf("  %s: %d times\n", success.Pattern, success.Count)
		}
	}

	if len(stats.BlockedOperations) > 0 {
		fmt.Println("\nBlocked operations:")
		for _, blocked := range stats.BlockedOperations {
			fmt.Printf("  %s\n", blocked)
		}
	}
	fmt.Println()

	// Generate full report
	fmt.Println(feedback.GenerateReport())

	fmt.Println("Demo complete!")
}
