package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"architect-go/pkg/config"
	"architect-go/pkg/database"
	httpserver "architect-go/pkg/http"
)

func main() {
	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	log.Printf("Starting Architect Dashboard Go Application")
	log.Printf("Server: %s:%d", cfg.Server.Host, cfg.Server.Port)
	log.Printf("Database: %s", cfg.Database.Host)

	// Initialize database
	log.Println("Initializing database...")
	db, err := database.New(cfg)
	if err != nil {
		log.Fatalf("Failed to initialize database: %v", err)
	}

	// Create database manager
	dbManager, err := database.NewManager(db.GetDB(), cfg)
	if err != nil {
		log.Fatalf("Failed to create database manager: %v", err)
	}

	// Start database manager
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	if err := dbManager.Start(ctx); err != nil {
		cancel()
		log.Fatalf("Failed to start database manager: %v", err)
	}
	cancel()

	// Run migrations
	log.Println("Running database migrations...")
	migrationResult := dbManager.RunMigrations()
	if !migrationResult.Success {
		log.Fatalf("Migration failed: %v", migrationResult.Error)
	}
	log.Printf("Migrations completed in %v", migrationResult.Duration)

	// Create HTTP server
	log.Println("Creating HTTP server...")
	server := httpserver.NewServer(cfg, dbManager)

	// Start HTTP server
	log.Println("Starting HTTP server...")
	if err := server.Start(); err != nil {
		log.Fatalf("Failed to start HTTP server: %v", err)
	}

	log.Printf("✅ Application started successfully")
	log.Printf("Server listening on http://%s:%d", cfg.Server.Host, cfg.Server.Port)
	log.Printf("Health check: http://%s:%d/health", cfg.Server.Host, cfg.Server.Port)
	log.Printf("Metrics: http://%s:%d/metrics", cfg.Server.Host, cfg.Server.Port)

	// Setup graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	// Wait for shutdown signal
	<-sigChan
	log.Println("\n⏹ Shutdown signal received")

	// Graceful shutdown with timeout
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer shutdownCancel()

	// Shutdown HTTP server
	log.Println("Stopping HTTP server...")
	if err := server.Stop(shutdownCtx); err != nil {
		log.Printf("Error stopping HTTP server: %v", err)
	}

	// Shutdown database manager
	log.Println("Stopping database manager...")
	if err := dbManager.Stop(); err != nil {
		log.Printf("Error stopping database manager: %v", err)
	}

	log.Println("✅ Application stopped cleanly")
}
