package main

import (
	"flag"
	"fmt"
	"log"
	"os"

	"github.com/architect/go_wrapper/manager"
)

func main() {
	// Parse flags
	host := flag.String("host", "0.0.0.0", "Host to bind to")
	port := flag.Int("port", 8163, "Port to listen on (default: 8163 for MANAGER)")
	flag.Parse()

	fmt.Printf("Go Wrapper Manager\n")
	fmt.Printf("==================\n")
	fmt.Printf("Host: %s\n", *host)
	fmt.Printf("Port: %d\n", *port)
	fmt.Printf("\n")
	fmt.Printf("Purpose:\n")
	fmt.Printf("  - Task distribution to agents (claude, gemini, codex)\n")
	fmt.Printf("  - Development goal alignment\n")
	fmt.Printf("  - Training data collection for auto-confirmation\n")
	fmt.Printf("\n")
	fmt.Printf("Endpoints:\n")
	fmt.Printf("  POST /api/manager/tasks         - Create task\n")
	fmt.Printf("  GET  /api/manager/tasks         - List tasks\n")
	fmt.Printf("  POST /api/manager/tasks/assign  - Assign task\n")
	fmt.Printf("  GET  /api/manager/agents        - List agents\n")
	fmt.Printf("  POST /api/manager/agents/register - Register agent\n")
	fmt.Printf("  GET  /api/manager/status        - Status\n")
	fmt.Printf("  POST /api/manager/assigner/sync - Sync with architect assigner\n")
	fmt.Printf("\n")
	fmt.Printf("Starting manager...\n")

	mgr := manager.NewManager(*host, *port)
	if err := mgr.Start(); err != nil {
		log.Fatalf("Manager error: %v", err)
		os.Exit(1)
	}
}
