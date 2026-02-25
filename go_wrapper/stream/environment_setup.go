package stream

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// EnvironmentSetup handles automatic environment initialization
type EnvironmentSetup struct {
	environment *Environment
	agentName   string
	setupTime   time.Time
}

// EnvironmentStatus tracks the current state of an environment
type EnvironmentStatus struct {
	Name           string                 `json:"name"`
	Status         string                 `json:"status"` // ready, initializing, error
	ActiveAgents   []string               `json:"active_agents"`
	LastUpdated    time.Time              `json:"last_updated"`
	WorkingDirSize int64                  `json:"working_dir_size_bytes"`
	DatabasesReady bool                   `json:"databases_ready"`
	Metadata       map[string]interface{} `json:"metadata"`
}

// NewEnvironmentSetup creates a new environment setup manager
func NewEnvironmentSetup(env *Environment, agentName string) *EnvironmentSetup {
	return &EnvironmentSetup{
		environment: env,
		agentName:   agentName,
		setupTime:   time.Now(),
	}
}

// Initialize sets up the complete environment for an agent
func (es *EnvironmentSetup) Initialize() error {
	fmt.Printf("[Environment Setup] Initializing %s environment for agent %s\n",
		es.environment.Name, es.agentName)

	// Step 1: Create working directory
	if err := es.createWorkingDirectory(); err != nil {
		return fmt.Errorf("failed to create working directory: %w", err)
	}

	// Step 2: Create required subdirectories
	if err := es.createRequiredDirectories(); err != nil {
		return fmt.Errorf("failed to create subdirectories: %w", err)
	}

	// Step 3: Initialize databases
	if err := es.initializeDatabases(); err != nil {
		return fmt.Errorf("failed to initialize databases: %w", err)
	}

	// Step 4: Set up environment variables
	if err := es.setupEnvironmentVariables(); err != nil {
		return fmt.Errorf("failed to setup environment variables: %w", err)
	}

	// Step 5: Create .env file with environment info
	if err := es.createEnvFile(); err != nil {
		return fmt.Errorf("failed to create .env file: %w", err)
	}

	// Step 6: Update environment status
	if err := es.updateEnvironmentStatus("ready"); err != nil {
		return fmt.Errorf("failed to update status: %w", err)
	}

	fmt.Printf("[Environment Setup] ✓ Environment %s ready for %s\n",
		es.environment.Name, es.agentName)

	return nil
}

// createWorkingDirectory creates the environment's working directory
func (es *EnvironmentSetup) createWorkingDirectory() error {
	workingDir := es.environment.WorkingDir

	// Check if directory exists
	if _, err := os.Stat(workingDir); os.IsNotExist(err) {
		fmt.Printf("[Environment Setup] Creating working directory: %s\n", workingDir)

		// Create with proper permissions (0750 - owner rwx, group rx, others none)
		if err := os.MkdirAll(workingDir, 0750); err != nil {
			return fmt.Errorf("failed to create directory: %w", err)
		}

		fmt.Printf("[Environment Setup] ✓ Created %s\n", workingDir)
	} else {
		fmt.Printf("[Environment Setup] ✓ Working directory exists: %s\n", workingDir)
	}

	return nil
}

// createRequiredDirectories creates subdirectories needed by the environment
func (es *EnvironmentSetup) createRequiredDirectories() error {
	workingDir := es.environment.WorkingDir

	// Required subdirectories
	subdirs := []struct {
		path string
		perm os.FileMode
	}{
		{filepath.Join(workingDir, "data"), 0750},
		{filepath.Join(workingDir, "data", "feedback"), 0750},
		{filepath.Join(workingDir, "data", "patterns"), 0750},
		{filepath.Join(workingDir, "data", "training"), 0750},
		{filepath.Join(workingDir, "logs"), 0750},
		{filepath.Join(workingDir, "logs", "agents"), 0750},
		{filepath.Join(workingDir, "config"), 0750},
		{filepath.Join(workingDir, "tmp"), 0750},
	}

	for _, dir := range subdirs {
		if _, err := os.Stat(dir.path); os.IsNotExist(err) {
			if err := os.MkdirAll(dir.path, dir.perm); err != nil {
				return fmt.Errorf("failed to create %s: %w", dir.path, err)
			}
			fmt.Printf("[Environment Setup] ✓ Created %s\n", dir.path)
		}
	}

	return nil
}

// initializeDatabases sets up SQLite databases with proper permissions
func (es *EnvironmentSetup) initializeDatabases() error {
	workingDir := es.environment.WorkingDir
	dataDir := filepath.Join(workingDir, "data")

	// Database files to initialize
	databases := []struct {
		name        string
		description string
	}{
		{"feedback", "Feedback tracking database"},
		{"patterns", "Pattern learning database"},
		{"training", "Training data database"},
		{"extraction", "Extraction events database"},
	}

	for _, db := range databases {
		dbDir := filepath.Join(dataDir, db.name)
		dbFile := filepath.Join(dbDir, fmt.Sprintf("%s_%s.db", es.environment.Name, db.name))

		// Create directory if needed
		if err := os.MkdirAll(dbDir, 0750); err != nil {
			return fmt.Errorf("failed to create db directory %s: %w", dbDir, err)
		}

		// Check if database exists
		if _, err := os.Stat(dbFile); os.IsNotExist(err) {
			// Create empty database file with restricted permissions
			file, err := os.OpenFile(dbFile, os.O_CREATE|os.O_WRONLY, 0640)
			if err != nil {
				return fmt.Errorf("failed to create database %s: %w", dbFile, err)
			}
			file.Close()

			fmt.Printf("[Environment Setup] ✓ Created %s (%s)\n", filepath.Base(dbFile), db.description)
		}
	}

	return nil
}

// setupEnvironmentVariables configures environment-specific variables
func (es *EnvironmentSetup) setupEnvironmentVariables() error {
	// Set environment variables for this process
	envVars := map[string]string{
		"ARCHITECT_ENV":         es.environment.Name,
		"ARCHITECT_AGENT":       es.agentName,
		"ARCHITECT_WORKING_DIR": es.environment.WorkingDir,
		"ARCHITECT_DATA_DIR":    filepath.Join(es.environment.WorkingDir, "data"),
		"ARCHITECT_LOGS_DIR":    filepath.Join(es.environment.WorkingDir, "logs"),
		"ARCHITECT_CONFIG_DIR":  filepath.Join(es.environment.WorkingDir, "config"),
	}

	for key, value := range envVars {
		if err := os.Setenv(key, value); err != nil {
			return fmt.Errorf("failed to set %s: %w", key, err)
		}
	}

	fmt.Printf("[Environment Setup] ✓ Configured %d environment variables\n", len(envVars))
	return nil
}

// createEnvFile creates a .env file with environment information
func (es *EnvironmentSetup) createEnvFile() error {
	envFile := filepath.Join(es.environment.WorkingDir, ".architect_env")

	content := fmt.Sprintf(`# Architect Environment Configuration
# Generated: %s
# Agent: %s
# Environment: %s

ARCHITECT_ENV=%s
ARCHITECT_AGENT=%s
ARCHITECT_WORKING_DIR=%s
ARCHITECT_DATA_DIR=%s/data
ARCHITECT_LOGS_DIR=%s/logs
ARCHITECT_CONFIG_DIR=%s/config

# Constraints
ARCHITECT_ALLOW_WRITE=%t
ARCHITECT_ALLOW_DELETE=%t
ARCHITECT_ALLOW_NETWORK=%t
ARCHITECT_MAX_FILE_SIZE_MB=%d

# Feedback Configuration
ARCHITECT_TRACK_OUTCOMES=%t
ARCHITECT_AUTO_REPORT_ERRORS=%t
ARCHITECT_COLLECT_METRICS=%t
`,
		time.Now().Format(time.RFC3339),
		es.agentName,
		es.environment.Name,
		es.environment.Name,
		es.agentName,
		es.environment.WorkingDir,
		es.environment.WorkingDir,
		es.environment.WorkingDir,
		es.environment.WorkingDir,
		es.environment.Constraints.AllowWrite,
		es.environment.Constraints.AllowDelete,
		es.environment.Constraints.AllowNetwork,
		es.environment.Constraints.MaxFileSizeMB,
		es.environment.FeedbackConfig.TrackOutcomes,
		es.environment.FeedbackConfig.AutoReportErrors,
		es.environment.FeedbackConfig.CollectMetrics,
	)

	if err := os.WriteFile(envFile, []byte(content), 0640); err != nil {
		return fmt.Errorf("failed to write .env file: %w", err)
	}

	fmt.Printf("[Environment Setup] ✓ Created %s\n", filepath.Base(envFile))
	return nil
}

// updateEnvironmentStatus updates the status file
func (es *EnvironmentSetup) updateEnvironmentStatus(status string) error {
	statusDir := filepath.Join(es.environment.WorkingDir, "data", "status")
	if err := os.MkdirAll(statusDir, 0750); err != nil {
		return fmt.Errorf("failed to create status directory: %w", err)
	}

	statusFile := filepath.Join(statusDir, fmt.Sprintf("%s_status.json", es.environment.Name))

	// Load existing status or create new
	var envStatus EnvironmentStatus
	if data, err := os.ReadFile(statusFile); err == nil {
		if err := json.Unmarshal(data, &envStatus); err != nil {
			// If unmarshal fails, create new status
			envStatus = EnvironmentStatus{
				Name:         es.environment.Name,
				ActiveAgents: make([]string, 0),
				Metadata:     make(map[string]interface{}),
			}
		}
	} else {
		envStatus = EnvironmentStatus{
			Name:         es.environment.Name,
			ActiveAgents: make([]string, 0),
			Metadata:     make(map[string]interface{}),
		}
	}

	// Update status
	envStatus.Status = status
	envStatus.LastUpdated = time.Now()
	envStatus.DatabasesReady = true

	// Add agent if not already in list
	found := false
	for _, agent := range envStatus.ActiveAgents {
		if agent == es.agentName {
			found = true
			break
		}
	}
	if !found {
		envStatus.ActiveAgents = append(envStatus.ActiveAgents, es.agentName)
	}

	// Calculate working directory size
	if size, err := getDirSize(es.environment.WorkingDir); err == nil {
		envStatus.WorkingDirSize = size
	}

	// Save status
	data, err := json.MarshalIndent(envStatus, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal status: %w", err)
	}

	if err := os.WriteFile(statusFile, data, 0640); err != nil {
		return fmt.Errorf("failed to write status file: %w", err)
	}

	return nil
}

// GetStatus returns the current environment status
func (es *EnvironmentSetup) GetStatus() (*EnvironmentStatus, error) {
	statusFile := filepath.Join(es.environment.WorkingDir, "data", "status",
		fmt.Sprintf("%s_status.json", es.environment.Name))

	data, err := os.ReadFile(statusFile)
	if err != nil {
		return nil, fmt.Errorf("failed to read status file: %w", err)
	}

	var status EnvironmentStatus
	if err := json.Unmarshal(data, &status); err != nil {
		return nil, fmt.Errorf("failed to parse status: %w", err)
	}

	return &status, nil
}

// Cleanup marks the agent as inactive in the environment
func (es *EnvironmentSetup) Cleanup() error {
	statusFile := filepath.Join(es.environment.WorkingDir, "data", "status",
		fmt.Sprintf("%s_status.json", es.environment.Name))

	// Load status
	var envStatus EnvironmentStatus
	if data, err := os.ReadFile(statusFile); err == nil {
		if err := json.Unmarshal(data, &envStatus); err != nil {
			return nil // Ignore cleanup errors
		}
	} else {
		return nil // No status file, nothing to clean
	}

	// Remove agent from active list
	newActiveAgents := make([]string, 0)
	for _, agent := range envStatus.ActiveAgents {
		if agent != es.agentName {
			newActiveAgents = append(newActiveAgents, agent)
		}
	}
	envStatus.ActiveAgents = newActiveAgents
	envStatus.LastUpdated = time.Now()

	// Save updated status
	data, err := json.MarshalIndent(envStatus, "", "  ")
	if err != nil {
		return nil // Ignore cleanup errors
	}

	os.WriteFile(statusFile, data, 0640)
	fmt.Printf("[Environment Setup] ✓ Cleaned up agent %s from %s environment\n",
		es.agentName, es.environment.Name)

	return nil
}

// getDirSize calculates the total size of a directory
func getDirSize(path string) (int64, error) {
	var size int64
	err := filepath.Walk(path, func(_ string, info os.FileInfo, err error) error {
		if err != nil {
			return nil // Skip errors
		}
		if !info.IsDir() {
			size += info.Size()
		}
		return nil
	})
	return size, err
}
