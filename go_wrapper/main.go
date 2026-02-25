package main

import (
	"bufio"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"

	"github.com/architect/go_wrapper/stream"
)

// promptForProject prompts the user to enter a project name
func promptForProject() string {
	fmt.Println("\n[Wrapper] No project specified.")
	fmt.Println("[Wrapper] You can set the project name by:")
	fmt.Println("  1. Creating a .project file in the current directory")
	fmt.Println("  2. Setting the PROJECT_NAME environment variable")
	fmt.Println("  3. Entering it now\n")

	reader := bufio.NewReader(os.Stdin)
	for {
		fmt.Print("Enter project name: ")
		input, err := reader.ReadString('\n')
		if err != nil {
			fmt.Fprintf(os.Stderr, "[ERROR] Failed to read input: %v\n", err)
			os.Exit(1)
		}

		projectName := strings.TrimSpace(input)
		if projectName != "" {
			// Save to .project file for future runs
			if err := os.WriteFile(".project", []byte(projectName+"\n"), 0644); err != nil {
				fmt.Fprintf(os.Stderr, "[WARN] Could not save .project file: %v\n", err)
			} else {
				fmt.Printf("[Wrapper] Saved project name to .project file\n")
			}
			return projectName
		}

		fmt.Println("[ERROR] Project name cannot be empty. Please try again.")
	}
}

// mustGetwd returns the current working directory or "unknown" if error
func mustGetwd() string {
	cwd, err := os.Getwd()
	if err != nil {
		return "unknown"
	}
	return cwd
}

func main() {
	// Parse arguments
	if len(os.Args) < 2 {
		fmt.Fprintf(os.Stderr, "Usage: %s <agent-name> [command] [args...]\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "\nExample:\n")
		fmt.Fprintf(os.Stderr, "  %s codex-1 codex\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "  %s test-agent yes hello\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "\nEnvironment Variables:\n")
		fmt.Fprintf(os.Stderr, "  WRAPPER_LOGS_DIR  - Override logs directory\n")
		fmt.Fprintf(os.Stderr, "  PROJECT_NAME      - Set project name\n")
		os.Exit(1)
	}

	agentName := os.Args[1]
	command := "codex" // Default command
	var args []string

	// Allow override of command
	if len(os.Args) > 2 {
		command = os.Args[2]
		if len(os.Args) > 3 {
			args = os.Args[3:]
		}
	}

	// Determine project name
	projectName := os.Getenv("PROJECT_NAME")
	if projectName == "" {
		// Check for .project file in current directory
		if projectData, err := os.ReadFile(".project"); err == nil {
			projectName = strings.TrimSpace(string(projectData))
		}
	}

	// If still no project name, prompt user
	if projectName == "" {
		projectName = promptForProject()
	}

	// Determine logs directory - use current working directory by default
	logsDir := os.Getenv("WRAPPER_LOGS_DIR")
	if logsDir == "" {
		// Default to ./logs/agents in current working directory
		cwd, err := os.Getwd()
		if err != nil {
			fmt.Fprintf(os.Stderr, "[ERROR] Could not get working directory: %v\n", err)
			os.Exit(1)
		}
		logsDir = filepath.Join(cwd, "logs", "agents", projectName)
	}

	// Create logs directory if it doesn't exist
	if err := os.MkdirAll(logsDir, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "[ERROR] Could not create logs directory: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("[Wrapper] Project: %s\n", projectName)
	fmt.Printf("[Wrapper] Agent: %s\n", agentName)
	fmt.Printf("[Wrapper] Command: %s %v\n", command, args)
	fmt.Printf("[Wrapper] Working directory: %s\n", mustGetwd())
	fmt.Printf("[Wrapper] Logs directory: %s\n\n", logsDir)

	// Create process wrapper
	wrapper := stream.NewProcessWrapper(agentName, logsDir, command, args...)

	// Handle signals for graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	go func() {
		sig := <-sigChan
		fmt.Printf("\n[Wrapper] Received signal: %v\n", sig)
		wrapper.Stop()
		os.Exit(130)
	}()

	// Start the process
	if err := wrapper.Start(); err != nil {
		fmt.Fprintf(os.Stderr, "[ERROR] Failed to start: %v\n", err)
		os.Exit(1)
	}

	// Wait for completion
	err := wrapper.Wait()

	// Print summary
	exitCode := wrapper.GetExitCode()
	stdoutLog, stderrLog := wrapper.GetLogPaths()

	fmt.Printf("\n[Wrapper] Process exited with code: %d\n", exitCode)
	if err != nil {
		fmt.Printf("[Wrapper] Error: %v\n", err)
	}
	fmt.Printf("[Wrapper] Logs saved:\n")
	fmt.Printf("  stdout: %s\n", stdoutLog)
	fmt.Printf("  stderr: %s\n", stderrLog)

	os.Exit(exitCode)
}
