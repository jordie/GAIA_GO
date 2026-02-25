package main

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/architect/go_wrapper/stream"
)

func main() {
	fmt.Println("=== Environment Setup & Config Update Demo ===\n")

	// Demo 1: Environment Setup
	demoEnvironmentSetup()

	// Demo 2: Config Updates
	demoConfigUpdates()

	// Demo 3: Broadcasting Changes
	demoBroadcasting()

	// Demo 4: Environment Status
	demoEnvironmentStatus()
}

func demoEnvironmentSetup() {
	fmt.Println("### Demo 1: Automatic Environment Setup ###\n")

	// Load environments
	configPath := "config/environments.json"
	config, err := stream.LoadEnvironmentConfig(configPath)
	if err != nil {
		fmt.Printf("Error loading config: %v\n", err)
		return
	}

	// Setup each environment for a test agent
	testAgent := "config_demo_agent"

	for _, env := range config.Environments {
		fmt.Printf("\n--- Setting up %s environment ---\n", env.Name)

		setup := stream.NewEnvironmentSetup(&env, testAgent)

		if err := setup.Initialize(); err != nil {
			fmt.Printf("✗ Failed to setup %s: %v\n", env.Name, err)
			continue
		}

		// Get status
		status, err := setup.GetStatus()
		if err != nil {
			fmt.Printf("Warning: Failed to get status: %v\n", err)
		} else {
			fmt.Printf("Status: %s\n", status.Status)
			fmt.Printf("Active agents: %v\n", status.ActiveAgents)
			fmt.Printf("Working dir size: %.2f MB\n", float64(status.WorkingDirSize)/(1024*1024))
			fmt.Printf("Databases ready: %v\n", status.DatabasesReady)
		}

		// Check .env file
		envFile := filepath.Join(env.WorkingDir, ".architect_env")
		if _, err := os.Stat(envFile); err == nil {
			fmt.Printf("✓ .env file created: %s\n", envFile)
		}
	}
}

func demoConfigUpdates() {
	fmt.Println("\n### Demo 2: Dynamic Config Updates ###\n")

	configPath := "config/environments.json"
	updater, err := stream.NewEnvironmentConfigUpdater(configPath)
	if err != nil {
		fmt.Printf("Error creating updater: %v\n", err)
		return
	}

	// Update dev environment constraints
	fmt.Println("--- Updating dev environment constraints ---")

	if err := updater.UpdateConstraint("dev", "max_file_size_mb", 150, "config_demo", "Increase limit for large datasets"); err != nil {
		fmt.Printf("✗ Failed to update constraint: %v\n", err)
	} else {
		fmt.Println("✓ Updated max_file_size_mb to 150")
	}

	// Add restricted path
	if err := updater.AddRestrictedPath("dev", "/tmp/sensitive", "config_demo", "Protect sensitive temp files"); err != nil {
		fmt.Printf("Warning: %v\n", err)
	} else {
		fmt.Println("✓ Added restricted path: /tmp/sensitive")
	}

	// Add denied command
	if err := updater.AddDeniedCommand("dev", "shutdown", "config_demo", "Prevent accidental shutdowns"); err != nil {
		fmt.Printf("Warning: %v\n", err)
	} else {
		fmt.Println("✓ Added denied command: shutdown")
	}

	// Update feedback config
	if err := updater.UpdateFeedbackConfig("staging", "collect_metrics", true, "config_demo", "Enable metrics collection"); err != nil {
		fmt.Printf("✗ Failed to update feedback config: %v\n", err)
	} else {
		fmt.Println("✓ Updated staging feedback config")
	}

	// Show recent changes
	fmt.Println("\n--- Recent changes to dev environment ---")
	changes := updater.GetRecentChanges("dev", 5)
	for i, change := range changes {
		fmt.Printf("%d. [%s] %s.%s: %v → %v (by %s)\n",
			i+1, change.ChangeType, change.Environment, change.Field,
			change.OldValue, change.NewValue, change.ChangedBy)
		if change.Reason != "" {
			fmt.Printf("   Reason: %s\n", change.Reason)
		}
	}
}

func demoBroadcasting() {
	fmt.Println("\n### Demo 3: Broadcasting Changes to Agents ###\n")

	configPath := "config/environments.json"
	updater, err := stream.NewEnvironmentConfigUpdater(configPath)
	if err != nil {
		fmt.Printf("Error creating updater: %v\n", err)
		return
	}

	// Get active agents for dev environment
	agents, err := updater.GetActiveAgents("dev")
	if err != nil {
		fmt.Printf("Error getting active agents: %v\n", err)
	} else {
		fmt.Printf("Active agents in dev environment: %v\n", agents)
	}

	// Create a sample change
	change := stream.EnvironmentChange{
		Environment: "dev",
		ChangedBy:   "config_demo",
		ChangeType:  "constraint",
		Field:       "max_file_size_mb",
		OldValue:    100,
		NewValue:    150,
		Reason:      "Increased for large dataset processing",
	}

	// Broadcast to active agents
	if len(agents) > 0 {
		if err := updater.BroadcastChange(change, agents); err != nil {
			fmt.Printf("✗ Failed to broadcast: %v\n", err)
		} else {
			fmt.Printf("✓ Broadcast change to %d agents\n", len(agents))
		}
	} else {
		fmt.Println("No active agents to broadcast to")
	}

	// Check notification files
	notificationDir := "config/notifications"
	if entries, err := os.ReadDir(notificationDir); err == nil {
		fmt.Printf("\nNotification files created:\n")
		for _, entry := range entries {
			if !entry.IsDir() {
				fmt.Printf("  - %s\n", entry.Name())
			}
		}
	}
}

func demoEnvironmentStatus() {
	fmt.Println("\n### Demo 4: Environment Status Tracking ###\n")

	configPath := "config/environments.json"
	config, err := stream.LoadEnvironmentConfig(configPath)
	if err != nil {
		fmt.Printf("Error loading config: %v\n", err)
		return
	}

	for _, env := range config.Environments {
		fmt.Printf("\n--- %s Environment Status ---\n", env.Name)

		setup := stream.NewEnvironmentSetup(&env, "status_demo")

		status, err := setup.GetStatus()
		if err != nil {
			fmt.Printf("Status: Not initialized\n")
			continue
		}

		fmt.Printf("Status: %s\n", status.Status)
		fmt.Printf("Active agents: %d\n", len(status.ActiveAgents))
		if len(status.ActiveAgents) > 0 {
			for i, agent := range status.ActiveAgents {
				fmt.Printf("  %d. %s\n", i+1, agent)
			}
		}
		fmt.Printf("Working dir size: %.2f MB\n", float64(status.WorkingDirSize)/(1024*1024))
		fmt.Printf("Databases ready: %v\n", status.DatabasesReady)
		fmt.Printf("Last updated: %s\n", status.LastUpdated.Format("2006-01-02 15:04:05"))

		if len(status.Metadata) > 0 {
			fmt.Printf("Metadata:\n")
			for key, value := range status.Metadata {
				fmt.Printf("  %s: %v\n", key, value)
			}
		}
	}

	fmt.Println("\n=== Demo Complete ===")
}
