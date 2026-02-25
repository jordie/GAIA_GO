package main

import (
	"fmt"
	"log"
	"time"

	"github.com/architect/go_wrapper/data"
)

func main() {
	// Open database stores
	extractionStore, err := data.NewExtractionStore("data/wrapper.db")
	if err != nil {
		log.Fatalf("Failed to create extraction store: %v", err)
	}
	defer extractionStore.Close()

	sessionStore, err := data.NewSessionStore("data/wrapper.db")
	if err != nil {
		log.Fatalf("Failed to create session store: %v", err)
	}
	defer sessionStore.Close()

	// Create test session
	agentName := "test-codex"
	sessionID := fmt.Sprintf("%s-%s", agentName, time.Now().Format("20060102-150405"))

	fmt.Printf("Creating test session: %s\n", sessionID)
	if err := sessionStore.CreateSession(agentName, sessionID, "dev"); err != nil {
		log.Fatalf("Failed to create session: %v", err)
	}

	// Create sample extraction events
	baseTime := time.Now().Add(-10 * time.Minute)
	events := []*data.ExtractionEvent{
		{
			AgentName:    agentName,
			SessionID:    sessionID,
			Timestamp:    baseTime,
			EventType:    "error",
			Pattern:      "error_detection",
			MatchedValue: "TypeError: Cannot read property 'length' of undefined",
			OriginalLine: "Error in processing user data",
			LineNumber:   42,
			RiskLevel:    "high",
		},
		{
			AgentName:    agentName,
			SessionID:    sessionID,
			Timestamp:    baseTime.Add(30 * time.Second),
			EventType:    "warning",
			Pattern:      "warning_detection",
			MatchedValue: "Warning: Deprecated API usage detected",
			OriginalLine: "Using old authentication method",
			LineNumber:   108,
			RiskLevel:    "medium",
		},
		{
			AgentName:    agentName,
			SessionID:    sessionID,
			Timestamp:    baseTime.Add(1 * time.Minute),
			EventType:    "error",
			Pattern:      "error_detection",
			MatchedValue: "ConnectionError: Unable to reach database",
			OriginalLine: "Database connection failed",
			LineNumber:   156,
			RiskLevel:    "high",
		},
		{
			AgentName:    agentName,
			SessionID:    sessionID,
			Timestamp:    baseTime.Add(90 * time.Second),
			EventType:    "metric",
			Pattern:      "metric_extraction",
			MatchedValue: "Response time: 234ms",
			OriginalLine: "Request completed in 234ms",
			LineNumber:   203,
			RiskLevel:    "low",
		},
		{
			AgentName:    agentName,
			SessionID:    sessionID,
			Timestamp:    baseTime.Add(2 * time.Minute),
			EventType:    "warning",
			Pattern:      "warning_detection",
			MatchedValue: "Warning: Memory usage high (85%)",
			OriginalLine: "System memory at 85%",
			LineNumber:   287,
			RiskLevel:    "medium",
		},
		{
			AgentName:    agentName,
			SessionID:    sessionID,
			Timestamp:    baseTime.Add(150 * time.Second),
			EventType:    "error",
			Pattern:      "error_detection",
			MatchedValue: "Error: API rate limit exceeded",
			OriginalLine: "Rate limit hit: 429 response",
			LineNumber:   312,
			RiskLevel:    "high",
		},
		{
			AgentName:    agentName,
			SessionID:    sessionID,
			Timestamp:    baseTime.Add(3 * time.Minute),
			EventType:    "metric",
			Pattern:      "metric_extraction",
			MatchedValue: "Throughput: 1523 req/sec",
			OriginalLine: "Current throughput: 1523",
			LineNumber:   389,
			RiskLevel:    "low",
		},
	}

	fmt.Printf("Saving %d extraction events...\n", len(events))
	if err := extractionStore.SaveExtractionBatch(events); err != nil {
		log.Fatalf("Failed to save extractions: %v", err)
	}

	// Add state changes
	fmt.Println("Recording state changes...")
	stateChanges := []*data.StateChange{
		{
			SessionID: sessionID,
			Timestamp: baseTime,
			State:     "starting",
		},
		{
			SessionID: sessionID,
			Timestamp: baseTime.Add(5 * time.Second),
			State:     "running",
		},
		{
			SessionID: sessionID,
			Timestamp: baseTime.Add(3*time.Minute + 30*time.Second),
			State:     "completed",
		},
	}

	for _, change := range stateChanges {
		if err := sessionStore.RecordStateChange(change); err != nil {
			log.Printf("Warning: Failed to record state change: %v", err)
		}
	}

	// Complete the session
	fmt.Println("Completing session...")
	stats := data.SessionStats{
		TotalLines:       450,
		TotalExtractions: len(events),
	}
	if err := sessionStore.CompleteSession(sessionID, 0, stats); err != nil {
		log.Fatalf("Failed to complete session: %v", err)
	}

	fmt.Println("\n✅ Test data created successfully!")
	fmt.Printf("Session ID: %s\n", sessionID)
	fmt.Printf("Agent: %s\n", agentName)
	fmt.Printf("Extractions: %d\n", len(events))
	fmt.Printf("State Changes: %d\n", len(stateChanges))
	fmt.Println("\nYou can now test the dashboard at: http://localhost:8151/database")
	fmt.Printf("Try searching for agent: %s\n", agentName)
}
