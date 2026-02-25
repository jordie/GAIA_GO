package stream

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Environment defines an isolated execution environment for agents
type Environment struct {
	Name        string              `json:"name"`
	Description string              `json:"description"`
	WorkingDir  string              `json:"working_dir"`
	User        string              `json:"user"`
	Constraints EnvironmentConstraints `json:"constraints"`
	FeedbackConfig FeedbackConfig   `json:"feedback_config"`
}

// EnvironmentConstraints define what operations are allowed
type EnvironmentConstraints struct {
	AllowWrite      bool     `json:"allow_write"`
	AllowDelete     bool     `json:"allow_delete"`
	AllowNetwork    bool     `json:"allow_network"`
	MaxFileSizeMB   int      `json:"max_file_size_mb"`
	RestrictedPaths []string `json:"restricted_paths"`
	AllowedCommands []string `json:"allowed_commands"`
	DeniedCommands  []string `json:"denied_commands"`
}

// FeedbackConfig defines feedback tracking settings
type FeedbackConfig struct {
	TrackOutcomes    bool `json:"track_outcomes"`
	AutoReportErrors bool `json:"auto_report_errors"`
	CollectMetrics   bool `json:"collect_metrics"`
}

// EnvironmentConfig holds all environment definitions
type EnvironmentConfig struct {
	Version            string        `json:"version"`
	Environments       []Environment `json:"environments"`
	DefaultEnvironment string        `json:"default_environment"`
}

// EnvironmentManager manages environment enforcement
type EnvironmentManager struct {
	config      *EnvironmentConfig
	environment *Environment
}

// LoadEnvironmentConfig loads environment configuration from JSON
func LoadEnvironmentConfig(configPath string) (*EnvironmentConfig, error) {
	data, err := os.ReadFile(configPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read environment config: %w", err)
	}

	var config EnvironmentConfig
	if err := json.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("failed to parse environment config: %w", err)
	}

	return &config, nil
}

// NewEnvironmentManager creates an environment manager
func NewEnvironmentManager(configPath, envName string) (*EnvironmentManager, error) {
	config, err := LoadEnvironmentConfig(configPath)
	if err != nil {
		return nil, err
	}

	// Find environment by name
	var env *Environment
	for i := range config.Environments {
		if config.Environments[i].Name == envName {
			env = &config.Environments[i]
			break
		}
	}

	if env == nil {
		// Use default environment
		for i := range config.Environments {
			if config.Environments[i].Name == config.DefaultEnvironment {
				env = &config.Environments[i]
				break
			}
		}
	}

	if env == nil {
		return nil, fmt.Errorf("environment not found: %s", envName)
	}

	fmt.Printf("[Environment] Loaded: %s - %s\n", env.Name, env.Description)
	fmt.Printf("[Environment] Working directory: %s\n", env.WorkingDir)
	fmt.Printf("[Environment] Constraints: write=%v, delete=%v, network=%v\n",
		env.Constraints.AllowWrite, env.Constraints.AllowDelete, env.Constraints.AllowNetwork)

	return &EnvironmentManager{
		config:      config,
		environment: env,
	}, nil
}

// GetEnvironment returns the current environment
func (em *EnvironmentManager) GetEnvironment() *Environment {
	return em.environment
}

// ValidateWorkingDirectory ensures agent is working in correct directory
func (em *EnvironmentManager) ValidateWorkingDirectory() error {
	currentDir, err := os.Getwd()
	if err != nil {
		return fmt.Errorf("failed to get working directory: %w", err)
	}

	// Resolve to absolute paths
	expectedDir, err := filepath.Abs(em.environment.WorkingDir)
	if err != nil {
		return fmt.Errorf("invalid environment working directory: %w", err)
	}

	currentDir, err = filepath.Abs(currentDir)
	if err != nil {
		return fmt.Errorf("failed to resolve current directory: %w", err)
	}

	if currentDir != expectedDir {
		return fmt.Errorf("wrong working directory: expected %s, got %s", expectedDir, currentDir)
	}

	return nil
}

// EnforceWorkingDirectory changes to the environment's working directory
func (em *EnvironmentManager) EnforceWorkingDirectory() error {
	if err := os.Chdir(em.environment.WorkingDir); err != nil {
		return fmt.Errorf("failed to change to working directory %s: %w", em.environment.WorkingDir, err)
	}

	fmt.Printf("[Environment] Set working directory: %s\n", em.environment.WorkingDir)
	return nil
}

// ValidatePath checks if a path is allowed by environment constraints
func (em *EnvironmentManager) ValidatePath(path string) error {
	absPath, err := filepath.Abs(path)
	if err != nil {
		return fmt.Errorf("invalid path: %w", err)
	}

	// Check against restricted paths
	for _, restricted := range em.environment.Constraints.RestrictedPaths {
		if restricted == "*" {
			return fmt.Errorf("path access denied: environment is read-only")
		}

		if strings.HasPrefix(absPath, restricted) {
			return fmt.Errorf("path access denied: %s is restricted", absPath)
		}
	}

	return nil
}

// ValidateCommand checks if a command is allowed
func (em *EnvironmentManager) ValidateCommand(command string) error {
	// Check denied commands first (takes precedence)
	for _, denied := range em.environment.Constraints.DeniedCommands {
		if strings.Contains(command, denied) {
			return fmt.Errorf("command denied: contains prohibited pattern '%s'", denied)
		}
	}

	// Check allowed commands
	if len(em.environment.Constraints.AllowedCommands) > 0 {
		allowed := false
		for _, allowedCmd := range em.environment.Constraints.AllowedCommands {
			if allowedCmd == "*" {
				allowed = true
				break
			}

			// Check if command starts with allowed command
			cmdParts := strings.Fields(command)
			if len(cmdParts) > 0 && strings.HasPrefix(cmdParts[0], allowedCmd) {
				allowed = true
				break
			}
		}

		if !allowed {
			return fmt.Errorf("command not allowed: %s", command)
		}
	}

	return nil
}

// ValidateWrite checks if write operation is allowed
func (em *EnvironmentManager) ValidateWrite(path string) error {
	if !em.environment.Constraints.AllowWrite {
		return fmt.Errorf("write operations not allowed in %s environment", em.environment.Name)
	}

	return em.ValidatePath(path)
}

// ValidateDelete checks if delete operation is allowed
func (em *EnvironmentManager) ValidateDelete(path string) error {
	if !em.environment.Constraints.AllowDelete {
		return fmt.Errorf("delete operations not allowed in %s environment", em.environment.Name)
	}

	return em.ValidatePath(path)
}

// ValidateNetwork checks if network operations are allowed
func (em *EnvironmentManager) ValidateNetwork() error {
	if !em.environment.Constraints.AllowNetwork {
		return fmt.Errorf("network operations not allowed in %s environment", em.environment.Name)
	}

	return nil
}

// ValidateFileSize checks if file size is within limits
func (em *EnvironmentManager) ValidateFileSize(sizeBytes int64) error {
	maxBytes := int64(em.environment.Constraints.MaxFileSizeMB) * 1024 * 1024

	if sizeBytes > maxBytes {
		return fmt.Errorf("file size %d MB exceeds limit of %d MB",
			sizeBytes/1024/1024, em.environment.Constraints.MaxFileSizeMB)
	}

	return nil
}

// GetWorkingDirectory returns the environment's working directory
func (em *EnvironmentManager) GetWorkingDirectory() string {
	return em.environment.WorkingDir
}

// GetEnvironmentName returns the environment name
func (em *EnvironmentManager) GetEnvironmentName() string {
	return em.environment.Name
}

// ShouldTrackFeedback returns whether feedback tracking is enabled
func (em *EnvironmentManager) ShouldTrackFeedback() bool {
	return em.environment.FeedbackConfig.TrackOutcomes
}

// ShouldAutoReportErrors returns whether auto error reporting is enabled
func (em *EnvironmentManager) ShouldAutoReportErrors() bool {
	return em.environment.FeedbackConfig.AutoReportErrors
}

// GetConstraintsSummary returns a summary of environment constraints
func (em *EnvironmentManager) GetConstraintsSummary() map[string]interface{} {
	return map[string]interface{}{
		"environment":       em.environment.Name,
		"working_dir":       em.environment.WorkingDir,
		"allow_write":       em.environment.Constraints.AllowWrite,
		"allow_delete":      em.environment.Constraints.AllowDelete,
		"allow_network":     em.environment.Constraints.AllowNetwork,
		"max_file_size_mb":  em.environment.Constraints.MaxFileSizeMB,
		"restricted_paths":  len(em.environment.Constraints.RestrictedPaths),
		"allowed_commands":  len(em.environment.Constraints.AllowedCommands),
		"denied_commands":   len(em.environment.Constraints.DeniedCommands),
	}
}
