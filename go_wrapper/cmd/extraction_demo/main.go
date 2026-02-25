package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/architect/go_wrapper/api"
	"github.com/architect/go_wrapper/stream"
)

func main() {
	if len(os.Args) < 3 {
		fmt.Println("Usage: extraction_demo <agent_name> <config_path>")
		fmt.Println("Example: extraction_demo dev_worker2 config/extraction_patterns.json")
		os.Exit(1)
	}

	agentName := os.Args[1]
	configPath := os.Args[2]

	// Create configurable extractor
	extractor, err := stream.NewConfigurableExtractor(agentName, configPath)
	if err != nil {
		log.Fatalf("Failed to create extractor: %v", err)
	}
	defer extractor.Close()

	fmt.Printf("Extraction layer initialized for agent: %s\n", agentName)
	fmt.Printf("Patterns loaded: %d\n", len(extractor.GetConfig().Patterns))
	fmt.Printf("Training mode: %v\n", extractor.GetConfig().Settings.EnableTraining)

	// Create API server
	extractionAPI := api.NewExtractionAPI()
	extractionAPI.RegisterExtractor(agentName, extractor)

	// Setup HTTP routes
	mux := http.NewServeMux()
	extractionAPI.SetupRoutes(mux)

	// Add health check
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, "OK")
	})

	// Start HTTP server in background
	go func() {
		addr := ":8154" // Extraction API port
		fmt.Printf("Extraction API listening on %s\n", addr)
		fmt.Println("\nAvailable endpoints:")
		fmt.Println("  GET  /api/extraction/agents")
		fmt.Println("  GET  /api/extraction/events?agent=<name>&limit=100&type=<type>")
		fmt.Println("  GET  /api/extraction/stats?agent=<name>")
		fmt.Println("  GET  /api/extraction/patterns?agent=<name>")
		fmt.Println("  POST /api/extraction/patterns/add?agent=<name>")
		fmt.Println("  POST /api/extraction/patterns/remove?agent=<name>&pattern=<name>")
		fmt.Println("  POST /api/extraction/config/reload?agent=<name>&config=<path>")
		fmt.Println("  GET  /api/extraction/auto-confirm?agent=<name>")
		fmt.Println("  GET  /health")

		if err := http.ListenAndServe(addr, mux); err != nil {
			log.Printf("HTTP server error: %v", err)
		}
	}()

	// Demo: Process some sample lines
	fmt.Println("\n--- Processing sample agent output ---")
	sampleLines := []string{
		"⏺ Bash(ls -lh)",
		"⏵⏵ bypass permissions on (shift+tab to cycle) · 9 files +50 -0",
		"✢ Sublimating… (thinking)",
		"Error: Exit code 1",
		"✻ Baked for 2m 9s",
		"Type your message or @path/to/file",
		"token usage: 42,058/200,000; 157,942 remaining",
		"⏺ Edit(manager/manager.go)",
		"⏺ Write(stream/extractor.go)",
	}

	for _, line := range sampleLines {
		events := extractor.ProcessLine(line)
		if len(events) > 0 {
			fmt.Printf("\nLine: %s\n", line)
			for _, event := range events {
				fmt.Printf("  → Event: %s (type=%s, pattern=%s)\n",
					event.ID, event.EventType, event.Pattern)
				fmt.Printf("     Fields: %v\n", event.Fields)
				fmt.Printf("     Auto-confirm: %v\n", event.Metadata["auto_confirm"])
				fmt.Printf("     Risk: %v\n", event.Metadata["risk_level"])
			}
		}
	}

	// Display stats
	fmt.Println("\n--- Extraction Statistics ---")
	stats := extractor.GetStats()
	for key, value := range stats {
		fmt.Printf("  %s: %v\n", key, value)
	}

	// Wait for interrupt
	fmt.Println("\nPress Ctrl+C to exit...")
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan

	fmt.Println("\nShutting down...")
}
