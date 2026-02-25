package main

import (
	"flag"
	"fmt"
	"log"
	"os"

	"github.com/architect/go_wrapper/api"
)

func main() {
	// Parse flags
	host := flag.String("host", "0.0.0.0", "Host to bind to")
	port := flag.Int("port", 8151, "Port to listen on (default: 8151 for DEV)")
	dbPath := flag.String("db", "", "Database path (enables Query and Replay APIs)")
	clusterID := flag.String("cluster", "", "Enable cluster mode with node ID")
	flag.Parse()

	fmt.Printf("Go Wrapper API Server\n")
	fmt.Printf("=====================\n")
	fmt.Printf("Host: %s\n", *host)
	fmt.Printf("Port: %d\n", *port)
	if *dbPath != "" {
		fmt.Printf("Database: %s\n", *dbPath)
	}
	if *clusterID != "" {
		fmt.Printf("Cluster Node: %s\n", *clusterID)
	}
	fmt.Printf("\n")
	fmt.Printf("Endpoints:\n")
	fmt.Printf("  GET  /api/health           - Server health\n")
	fmt.Printf("  GET  /api/agents           - List agents\n")
	fmt.Printf("  POST /api/agents           - Create agent\n")
	fmt.Printf("  GET  /api/agents/:name     - Get agent details\n")
	fmt.Printf("  DELETE /api/agents/:name   - Stop agent\n")
	if *dbPath != "" {
		fmt.Printf("  GET  /api/query/*          - Query database\n")
		fmt.Printf("  GET  /api/replay/*         - Replay sessions\n")
	}
	if *clusterID != "" {
		fmt.Printf("  GET  /api/cluster/*        - Cluster management\n")
	}
	fmt.Printf("\n")
	fmt.Printf("Starting server...\n")

	server := api.NewServer(*host, *port)

	// Enable database if path provided
	if *dbPath != "" {
		if err := server.EnableDatabase(*dbPath); err != nil {
			log.Fatalf("Failed to enable database: %v", err)
			os.Exit(1)
		}
	}

	// Enable cluster if node ID provided
	if *clusterID != "" {
		if err := server.EnableCluster(*clusterID); err != nil {
			log.Fatalf("Failed to enable cluster: %v", err)
			os.Exit(1)
		}
	}

	if err := server.Start(); err != nil {
		log.Fatalf("Server error: %v", err)
		os.Exit(1)
	}
}
