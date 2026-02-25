package stream

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"os/user"
	"path/filepath"
	"strings"
)

// WorkerUser represents a Unix user for a worker agent
type WorkerUser struct {
	Username    string            `json:"username"`
	UID         string            `json:"uid"`
	GID         string            `json:"gid"`
	HomeDir     string            `json:"home_dir"`
	WorkspaceDir string           `json:"workspace_dir"`
	Role        string            `json:"role"` // worker, manager
	GitConfig   GitConfig         `json:"git_config"`
	SSHKeyPath  string            `json:"ssh_key_path"`
	Metadata    map[string]string `json:"metadata"`
}

// GitConfig stores git credentials for a user
type GitConfig struct {
	Name  string `json:"name"`
	Email string `json:"email"`
	Token string `json:"token,omitempty"` // Optional: for HTTPS operations
}

// UserManager manages worker and manager Unix users
type UserManager struct {
	configPath string
	users      map[string]*WorkerUser
}

// NewUserManager creates a new user manager
func NewUserManager(configPath string) (*UserManager, error) {
	um := &UserManager{
		configPath: configPath,
		users:      make(map[string]*WorkerUser),
	}

	// Load existing users if config exists
	if _, err := os.Stat(configPath); err == nil {
		if err := um.loadUsers(); err != nil {
			return nil, fmt.Errorf("failed to load users: %w", err)
		}
	}

	return um, nil
}

// CreateWorkerUser creates a new Unix user for a worker
func (um *UserManager) CreateWorkerUser(username, role string, gitConfig GitConfig) error {
	// Check if user already exists
	if _, exists := um.users[username]; exists {
		return fmt.Errorf("user already registered: %s", username)
	}

	// Check if Unix user exists
	existingUser, err := user.Lookup(username)
	if err == nil {
		// User exists, use existing info
		fmt.Printf("[User Manager] Unix user exists: %s (UID: %s)\n", username, existingUser.Uid)

		workerUser := &WorkerUser{
			Username:     username,
			UID:          existingUser.Uid,
			GID:          existingUser.Gid,
			HomeDir:      existingUser.HomeDir,
			WorkspaceDir: filepath.Join(existingUser.HomeDir, "workspace"),
			Role:         role,
			GitConfig:    gitConfig,
			SSHKeyPath:   filepath.Join(existingUser.HomeDir, ".ssh", "id_rsa"),
			Metadata:     make(map[string]string),
		}

		um.users[username] = workerUser

		// Setup workspace and git config
		if err := um.setupUserEnvironment(workerUser); err != nil {
			return fmt.Errorf("failed to setup environment: %w", err)
		}

		return um.saveUsers()
	}

	// Create new Unix user
	fmt.Printf("[User Manager] Creating Unix user: %s (role: %s)\n", username, role)

	// Create user with home directory
	cmd := exec.Command("sudo", "useradd", "-m", "-s", "/bin/bash", username)
	if output, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("failed to create user: %s - %v", string(output), err)
	}

	// Get user info
	newUser, err := user.Lookup(username)
	if err != nil {
		return fmt.Errorf("failed to lookup new user: %w", err)
	}

	workerUser := &WorkerUser{
		Username:     username,
		UID:          newUser.Uid,
		GID:          newUser.Gid,
		HomeDir:      newUser.HomeDir,
		WorkspaceDir: filepath.Join(newUser.HomeDir, "workspace"),
		Role:         role,
		GitConfig:    gitConfig,
		SSHKeyPath:   filepath.Join(newUser.HomeDir, ".ssh", "id_rsa"),
		Metadata:     make(map[string]string),
	}

	um.users[username] = workerUser

	// Setup user environment
	if err := um.setupUserEnvironment(workerUser); err != nil {
		return fmt.Errorf("failed to setup environment: %w", err)
	}

	fmt.Printf("[User Manager] ✓ Created user %s (UID: %s, Home: %s)\n",
		username, workerUser.UID, workerUser.HomeDir)

	return um.saveUsers()
}

// setupUserEnvironment configures workspace, git, and SSH for a user
func (um *UserManager) setupUserEnvironment(wu *WorkerUser) error {
	fmt.Printf("[User Manager] Setting up environment for %s\n", wu.Username)

	// Create workspace directory
	if err := um.runAsUser(wu.Username, "mkdir", "-p", wu.WorkspaceDir); err != nil {
		return fmt.Errorf("failed to create workspace: %w", err)
	}

	// Create .ssh directory
	sshDir := filepath.Join(wu.HomeDir, ".ssh")
	if err := um.runAsUser(wu.Username, "mkdir", "-p", sshDir); err != nil {
		return fmt.Errorf("failed to create .ssh dir: %w", err)
	}

	// Set .ssh permissions
	if err := um.runAsUser(wu.Username, "chmod", "700", sshDir); err != nil {
		return fmt.Errorf("failed to set .ssh permissions: %w", err)
	}

	// Configure git
	if err := um.setupGitConfig(wu); err != nil {
		return fmt.Errorf("failed to setup git: %w", err)
	}

	fmt.Printf("[User Manager] ✓ Environment ready for %s\n", wu.Username)
	return nil
}

// setupGitConfig configures git for the user
func (um *UserManager) setupGitConfig(wu *WorkerUser) error {
	// Set git user name
	if err := um.runAsUserInDir(wu.Username, wu.HomeDir, "git", "config", "--global", "user.name", wu.GitConfig.Name); err != nil {
		return fmt.Errorf("failed to set git name: %w", err)
	}

	// Set git user email
	if err := um.runAsUserInDir(wu.Username, wu.HomeDir, "git", "config", "--global", "user.email", wu.GitConfig.Email); err != nil {
		return fmt.Errorf("failed to set git email: %w", err)
	}

	// Configure credential helper if token provided
	if wu.GitConfig.Token != "" {
		// Store token in git credential store
		credHelper := "store"
		if err := um.runAsUserInDir(wu.Username, wu.HomeDir, "git", "config", "--global", "credential.helper", credHelper); err != nil {
			return fmt.Errorf("failed to set credential helper: %w", err)
		}

		fmt.Printf("[User Manager] ✓ Git configured for %s (%s)\n",
			wu.Username, wu.GitConfig.Email)
	}

	return nil
}

// runAsUser executes a command as a specific user
func (um *UserManager) runAsUser(username string, command string, args ...string) error {
	cmdArgs := []string{"-u", username, command}
	cmdArgs = append(cmdArgs, args...)

	cmd := exec.Command("sudo", cmdArgs...)
	if output, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("command failed: %s - %v", string(output), err)
	}

	return nil
}

// runAsUserInDir executes a command as a user in a specific directory
func (um *UserManager) runAsUserInDir(username, dir, command string, args ...string) error {
	// Create a shell command that changes directory and runs the command
	fullCmd := fmt.Sprintf("cd %s && %s %s", dir, command, strings.Join(args, " "))

	cmd := exec.Command("sudo", "-u", username, "bash", "-c", fullCmd)
	if output, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("command failed: %s - %v", string(output), err)
	}

	return nil
}

// GetUser returns a worker user by username
func (um *UserManager) GetUser(username string) (*WorkerUser, error) {
	user, exists := um.users[username]
	if !exists {
		return nil, fmt.Errorf("user not found: %s", username)
	}
	return user, nil
}

// ListUsers returns all registered users
func (um *UserManager) ListUsers() []*WorkerUser {
	users := make([]*WorkerUser, 0, len(um.users))
	for _, u := range um.users {
		users = append(users, u)
	}
	return users
}

// ListWorkers returns only worker users
func (um *UserManager) ListWorkers() []*WorkerUser {
	workers := make([]*WorkerUser, 0)
	for _, u := range um.users {
		if u.Role == "worker" {
			workers = append(workers, u)
		}
	}
	return workers
}

// ListManagers returns only manager users
func (um *UserManager) ListManagers() []*WorkerUser {
	managers := make([]*WorkerUser, 0)
	for _, u := range um.users {
		if u.Role == "manager" {
			managers = append(managers, u)
		}
	}
	return managers
}

// SetupSharedGitRepo configures a shared git repository that workers can access
func (um *UserManager) SetupSharedGitRepo(repoPath, groupName string, workers []string) error {
	fmt.Printf("[User Manager] Setting up shared git repo: %s\n", repoPath)

	// Create group if it doesn't exist
	cmd := exec.Command("sudo", "groupadd", "-f", groupName)
	cmd.Run() // Ignore error if group exists

	// Add workers to group
	for _, worker := range workers {
		if err := um.runAsUser("root", "usermod", "-a", "-G", groupName, worker); err != nil {
			fmt.Printf("[User Manager] Warning: Failed to add %s to group: %v\n", worker, err)
		}
	}

	// Set repository permissions
	// Owner: current user, Group: worker group, Mode: 775
	if err := exec.Command("sudo", "chgrp", "-R", groupName, repoPath).Run(); err != nil {
		return fmt.Errorf("failed to set group: %w", err)
	}

	if err := exec.Command("sudo", "chmod", "-R", "g+rwX", repoPath).Run(); err != nil {
		return fmt.Errorf("failed to set permissions: %w", err)
	}

	// Set SGID bit so new files inherit group
	if err := exec.Command("sudo", "chmod", "g+s", repoPath).Run(); err != nil {
		return fmt.Errorf("failed to set SGID: %w", err)
	}

	fmt.Printf("[User Manager] ✓ Shared repo configured for group %s\n", groupName)
	return nil
}

// loadUsers loads user configuration from JSON
func (um *UserManager) loadUsers() error {
	data, err := os.ReadFile(um.configPath)
	if err != nil {
		return err
	}

	var users map[string]*WorkerUser
	if err := json.Unmarshal(data, &users); err != nil {
		return err
	}

	um.users = users
	return nil
}

// saveUsers saves user configuration to JSON
func (um *UserManager) saveUsers() error {
	// Create config directory if needed
	configDir := filepath.Dir(um.configPath)
	if err := os.MkdirAll(configDir, 0750); err != nil {
		return fmt.Errorf("failed to create config dir: %w", err)
	}

	data, err := json.MarshalIndent(um.users, "", "  ")
	if err != nil {
		return err
	}

	// Create backup
	if _, err := os.Stat(um.configPath); err == nil {
		backupPath := um.configPath + ".backup"
		os.Rename(um.configPath, backupPath)
	}

	if err := os.WriteFile(um.configPath, data, 0640); err != nil {
		return err
	}

	return nil
}

// VerifyUserExists checks if a Unix user exists
func VerifyUserExists(username string) bool {
	_, err := user.Lookup(username)
	return err == nil
}

// GetCurrentUser returns the current Unix user
func GetCurrentUser() (*user.User, error) {
	return user.Current()
}

// CanSudo checks if the current user can use sudo
func CanSudo() bool {
	cmd := exec.Command("sudo", "-n", "true")
	return cmd.Run() == nil
}
