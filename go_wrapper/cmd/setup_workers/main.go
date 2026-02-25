package main

import (
	"bufio"
	"flag"
	"fmt"
	"os"
	"strings"

	"github.com/architect/go_wrapper/stream"
)

func main() {
	configPath := flag.String("config", "config/worker_users.json", "Path to worker users config")
	interactive := flag.Bool("interactive", false, "Interactive mode for creating users")
	list := flag.Bool("list", false, "List existing users")
	setupRepo := flag.String("setup-repo", "", "Setup shared git repository")
	repoGroup := flag.String("group", "architect_workers", "Group name for shared repo")
	flag.Parse()

	// Initialize user manager
	userManager, err := stream.NewUserManager(*configPath)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}

	// List users
	if *list {
		listUsers(userManager)
		return
	}

	// Setup shared repository
	if *setupRepo != "" {
		setupSharedRepo(userManager, *setupRepo, *repoGroup)
		return
	}

	// Interactive mode
	if *interactive {
		runInteractive(userManager)
		return
	}

	// Default: Create standard workers and managers
	createStandardUsers(userManager)
}

func listUsers(um *stream.UserManager) {
	fmt.Println("=== Registered Users ===\n")

	workers := um.ListWorkers()
	fmt.Printf("Workers (%d):\n", len(workers))
	for _, w := range workers {
		fmt.Printf("  - %s (UID: %s)\n", w.Username, w.UID)
		fmt.Printf("    Home: %s\n", w.HomeDir)
		fmt.Printf("    Workspace: %s\n", w.WorkspaceDir)
		fmt.Printf("    Git: %s <%s>\n", w.GitConfig.Name, w.GitConfig.Email)
		fmt.Println()
	}

	managers := um.ListManagers()
	fmt.Printf("Managers (%d):\n", len(managers))
	for _, m := range managers {
		fmt.Printf("  - %s (UID: %s)\n", m.Username, m.UID)
		fmt.Printf("    Home: %s\n", m.HomeDir)
		fmt.Printf("    Git: %s <%s>\n", m.GitConfig.Name, m.GitConfig.Email)
		fmt.Println()
	}
}

func createStandardUsers(um *stream.UserManager) {
	fmt.Println("=== Setting Up Standard Workers & Managers ===\n")

	// Standard workers
	workers := []struct {
		username  string
		gitName   string
		gitEmail  string
	}{
		{"dev_worker1", "Dev Worker 1", "dev.worker1@architect.local"},
		{"dev_worker2", "Dev Worker 2", "dev.worker2@architect.local"},
		{"dev_worker3", "Dev Worker 3", "dev.worker3@architect.local"},
		{"concurrent_worker1", "Concurrent Worker 1", "concurrent.worker1@architect.local"},
		{"edu_worker1", "Education Worker 1", "edu.worker1@architect.local"},
	}

	for _, w := range workers {
		fmt.Printf("Creating worker: %s\n", w.username)

		gitConfig := stream.GitConfig{
			Name:  w.gitName,
			Email: w.gitEmail,
		}

		if err := um.CreateWorkerUser(w.username, "worker", gitConfig); err != nil {
			fmt.Printf("  ✗ Failed: %v\n", err)
		} else {
			fmt.Printf("  ✓ Created %s\n", w.username)
		}
	}

	// Standard managers
	managers := []struct {
		username  string
		gitName   string
		gitEmail  string
	}{
		{"architect_manager", "Architect Manager", "architect@architect.local"},
		{"wrapper_manager", "Wrapper Manager", "wrapper@architect.local"},
	}

	for _, m := range managers {
		fmt.Printf("Creating manager: %s\n", m.username)

		gitConfig := stream.GitConfig{
			Name:  m.gitName,
			Email: m.gitEmail,
		}

		if err := um.CreateWorkerUser(m.username, "manager", gitConfig); err != nil {
			fmt.Printf("  ✗ Failed: %v\n", err)
		} else {
			fmt.Printf("  ✓ Created %s\n", m.username)
		}
	}

	fmt.Println("\n=== Setup Complete ===")
	fmt.Println("\nTo setup shared git repository:")
	fmt.Println("  sudo ./bin/setup_workers --setup-repo /path/to/repo")
}

func runInteractive(um *stream.UserManager) {
	reader := bufio.NewReader(os.Stdin)

	fmt.Println("=== Interactive Worker/Manager Setup ===\n")

	// Get username
	fmt.Print("Username: ")
	username, _ := reader.ReadString('\n')
	username = strings.TrimSpace(username)

	if username == "" {
		fmt.Println("Error: Username required")
		return
	}

	// Get role
	fmt.Print("Role (worker/manager) [worker]: ")
	role, _ := reader.ReadString('\n')
	role = strings.TrimSpace(role)
	if role == "" {
		role = "worker"
	}

	// Get git name
	fmt.Print("Git Name: ")
	gitName, _ := reader.ReadString('\n')
	gitName = strings.TrimSpace(gitName)

	if gitName == "" {
		gitName = username
	}

	// Get git email
	fmt.Print("Git Email: ")
	gitEmail, _ := reader.ReadString('\n')
	gitEmail = strings.TrimSpace(gitEmail)

	if gitEmail == "" {
		gitEmail = fmt.Sprintf("%s@architect.local", username)
	}

	// Get git token (optional)
	fmt.Print("Git Token (optional, for HTTPS): ")
	gitToken, _ := reader.ReadString('\n')
	gitToken = strings.TrimSpace(gitToken)

	// Create user
	gitConfig := stream.GitConfig{
		Name:  gitName,
		Email: gitEmail,
		Token: gitToken,
	}

	fmt.Printf("\nCreating %s: %s\n", role, username)

	if err := um.CreateWorkerUser(username, role, gitConfig); err != nil {
		fmt.Printf("✗ Failed: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("✓ Created %s\n", username)
	fmt.Printf("  Git: %s <%s>\n", gitName, gitEmail)

	// Get user info
	user, _ := um.GetUser(username)
	fmt.Printf("  Home: %s\n", user.HomeDir)
	fmt.Printf("  Workspace: %s\n", user.WorkspaceDir)
}

func setupSharedRepo(um *stream.UserManager, repoPath, groupName string) {
	fmt.Printf("=== Setting Up Shared Git Repository ===\n\n")
	fmt.Printf("Repository: %s\n", repoPath)
	fmt.Printf("Group: %s\n\n", groupName)

	// Get all worker usernames
	workers := um.ListWorkers()
	if len(workers) == 0 {
		fmt.Println("Error: No workers registered")
		os.Exit(1)
	}

	usernames := make([]string, 0, len(workers))
	for _, w := range workers {
		usernames = append(usernames, w.Username)
	}

	fmt.Printf("Workers: %v\n\n", usernames)

	if err := um.SetupSharedGitRepo(repoPath, groupName, usernames); err != nil {
		fmt.Printf("✗ Failed: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("✓ Shared repository configured")
	fmt.Println("\nAll workers can now commit to the repository:")
	for _, username := range usernames {
		fmt.Printf("  - %s\n", username)
	}
}
