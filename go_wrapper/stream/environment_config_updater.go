package stream

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// EnvironmentChange represents a change to environment configuration
type EnvironmentChange struct {
	Timestamp      time.Time              `json:"timestamp"`
	Environment    string                 `json:"environment"`
	ChangedBy      string                 `json:"changed_by"`
	ChangeType     string                 `json:"change_type"` // constraint, config, metadata
	Field          string                 `json:"field"`
	OldValue       interface{}            `json:"old_value"`
	NewValue       interface{}            `json:"new_value"`
	Reason         string                 `json:"reason"`
	BroadcastTo    []string               `json:"broadcast_to"`
	AcknowledgedBy []string               `json:"acknowledged_by"`
}

// EnvironmentConfigUpdater manages environment configuration updates
type EnvironmentConfigUpdater struct {
	configPath    string
	config        *EnvironmentConfig
	changes       []EnvironmentChange
	mutex         sync.RWMutex
	changeLogPath string
}

// NewEnvironmentConfigUpdater creates a new config updater
func NewEnvironmentConfigUpdater(configPath string) (*EnvironmentConfigUpdater, error) {
	config, err := LoadEnvironmentConfig(configPath)
	if err != nil {
		return nil, fmt.Errorf("failed to load config: %w", err)
	}

	changeLogPath := filepath.Join(filepath.Dir(configPath), "environment_changes.jsonl")

	updater := &EnvironmentConfigUpdater{
		configPath:    configPath,
		config:        config,
		changes:       make([]EnvironmentChange, 0),
		changeLogPath: changeLogPath,
	}

	// Load existing changes
	if err := updater.loadChangeLog(); err != nil {
		fmt.Printf("[Config Updater] Warning: Failed to load change log: %v\n", err)
	}

	return updater, nil
}

// UpdateConstraint updates a constraint for an environment
func (ecu *EnvironmentConfigUpdater) UpdateConstraint(envName, field string, value interface{}, changedBy, reason string) error {
	ecu.mutex.Lock()
	defer ecu.mutex.Unlock()

	// Find environment
	var env *Environment
	for i := range ecu.config.Environments {
		if ecu.config.Environments[i].Name == envName {
			env = &ecu.config.Environments[i]
			break
		}
	}

	if env == nil {
		return fmt.Errorf("environment not found: %s", envName)
	}

	// Record old value and update
	var oldValue interface{}
	var newValue interface{} = value

	switch field {
	case "allow_write":
		oldValue = env.Constraints.AllowWrite
		if v, ok := value.(bool); ok {
			env.Constraints.AllowWrite = v
		} else {
			return fmt.Errorf("invalid value type for allow_write")
		}
	case "allow_delete":
		oldValue = env.Constraints.AllowDelete
		if v, ok := value.(bool); ok {
			env.Constraints.AllowDelete = v
		} else {
			return fmt.Errorf("invalid value type for allow_delete")
		}
	case "allow_network":
		oldValue = env.Constraints.AllowNetwork
		if v, ok := value.(bool); ok {
			env.Constraints.AllowNetwork = v
		} else {
			return fmt.Errorf("invalid value type for allow_network")
		}
	case "max_file_size_mb":
		oldValue = env.Constraints.MaxFileSizeMB
		if v, ok := value.(int); ok {
			env.Constraints.MaxFileSizeMB = v
		} else if v, ok := value.(float64); ok {
			env.Constraints.MaxFileSizeMB = int(v)
		} else {
			return fmt.Errorf("invalid value type for max_file_size_mb")
		}
	default:
		return fmt.Errorf("unknown constraint field: %s", field)
	}

	// Record change
	change := EnvironmentChange{
		Timestamp:      time.Now(),
		Environment:    envName,
		ChangedBy:      changedBy,
		ChangeType:     "constraint",
		Field:          field,
		OldValue:       oldValue,
		NewValue:       newValue,
		Reason:         reason,
		BroadcastTo:    make([]string, 0),
		AcknowledgedBy: make([]string, 0),
	}

	ecu.changes = append(ecu.changes, change)

	// Save changes
	if err := ecu.saveConfig(); err != nil {
		return fmt.Errorf("failed to save config: %w", err)
	}

	if err := ecu.logChange(change); err != nil {
		fmt.Printf("[Config Updater] Warning: Failed to log change: %v\n", err)
	}

	fmt.Printf("[Config Updater] ✓ Updated %s.%s: %v → %v (by %s)\n",
		envName, field, oldValue, newValue, changedBy)

	return nil
}

// AddRestrictedPath adds a path to the restricted list
func (ecu *EnvironmentConfigUpdater) AddRestrictedPath(envName, path, changedBy, reason string) error {
	ecu.mutex.Lock()
	defer ecu.mutex.Unlock()

	// Find environment
	var env *Environment
	for i := range ecu.config.Environments {
		if ecu.config.Environments[i].Name == envName {
			env = &ecu.config.Environments[i]
			break
		}
	}

	if env == nil {
		return fmt.Errorf("environment not found: %s", envName)
	}

	// Check if path already restricted
	for _, p := range env.Constraints.RestrictedPaths {
		if p == path {
			return fmt.Errorf("path already restricted: %s", path)
		}
	}

	// Add path
	env.Constraints.RestrictedPaths = append(env.Constraints.RestrictedPaths, path)

	// Record change
	change := EnvironmentChange{
		Timestamp:      time.Now(),
		Environment:    envName,
		ChangedBy:      changedBy,
		ChangeType:     "constraint",
		Field:          "restricted_paths",
		OldValue:       nil,
		NewValue:       path,
		Reason:         reason,
		BroadcastTo:    make([]string, 0),
		AcknowledgedBy: make([]string, 0),
	}

	ecu.changes = append(ecu.changes, change)

	// Save
	if err := ecu.saveConfig(); err != nil {
		return err
	}

	if err := ecu.logChange(change); err != nil {
		fmt.Printf("[Config Updater] Warning: Failed to log change: %v\n", err)
	}

	fmt.Printf("[Config Updater] ✓ Added restricted path to %s: %s (by %s)\n",
		envName, path, changedBy)

	return nil
}

// AddDeniedCommand adds a command to the denied list
func (ecu *EnvironmentConfigUpdater) AddDeniedCommand(envName, command, changedBy, reason string) error {
	ecu.mutex.Lock()
	defer ecu.mutex.Unlock()

	// Find environment
	var env *Environment
	for i := range ecu.config.Environments {
		if ecu.config.Environments[i].Name == envName {
			env = &ecu.config.Environments[i]
			break
		}
	}

	if env == nil {
		return fmt.Errorf("environment not found: %s", envName)
	}

	// Check if command already denied
	for _, cmd := range env.Constraints.DeniedCommands {
		if cmd == command {
			return fmt.Errorf("command already denied: %s", command)
		}
	}

	// Add command
	env.Constraints.DeniedCommands = append(env.Constraints.DeniedCommands, command)

	// Record change
	change := EnvironmentChange{
		Timestamp:      time.Now(),
		Environment:    envName,
		ChangedBy:      changedBy,
		ChangeType:     "constraint",
		Field:          "denied_commands",
		OldValue:       nil,
		NewValue:       command,
		Reason:         reason,
		BroadcastTo:    make([]string, 0),
		AcknowledgedBy: make([]string, 0),
	}

	ecu.changes = append(ecu.changes, change)

	// Save
	if err := ecu.saveConfig(); err != nil {
		return err
	}

	if err := ecu.logChange(change); err != nil {
		fmt.Printf("[Config Updater] Warning: Failed to log change: %v\n", err)
	}

	fmt.Printf("[Config Updater] ✓ Added denied command to %s: %s (by %s)\n",
		envName, command, changedBy)

	return nil
}

// UpdateFeedbackConfig updates feedback configuration
func (ecu *EnvironmentConfigUpdater) UpdateFeedbackConfig(envName, field string, value bool, changedBy, reason string) error {
	ecu.mutex.Lock()
	defer ecu.mutex.Unlock()

	// Find environment
	var env *Environment
	for i := range ecu.config.Environments {
		if ecu.config.Environments[i].Name == envName {
			env = &ecu.config.Environments[i]
			break
		}
	}

	if env == nil {
		return fmt.Errorf("environment not found: %s", envName)
	}

	var oldValue interface{}

	switch field {
	case "track_outcomes":
		oldValue = env.FeedbackConfig.TrackOutcomes
		env.FeedbackConfig.TrackOutcomes = value
	case "auto_report_errors":
		oldValue = env.FeedbackConfig.AutoReportErrors
		env.FeedbackConfig.AutoReportErrors = value
	case "collect_metrics":
		oldValue = env.FeedbackConfig.CollectMetrics
		env.FeedbackConfig.CollectMetrics = value
	default:
		return fmt.Errorf("unknown feedback config field: %s", field)
	}

	// Record change
	change := EnvironmentChange{
		Timestamp:      time.Now(),
		Environment:    envName,
		ChangedBy:      changedBy,
		ChangeType:     "config",
		Field:          field,
		OldValue:       oldValue,
		NewValue:       value,
		Reason:         reason,
		BroadcastTo:    make([]string, 0),
		AcknowledgedBy: make([]string, 0),
	}

	ecu.changes = append(ecu.changes, change)

	// Save
	if err := ecu.saveConfig(); err != nil {
		return err
	}

	if err := ecu.logChange(change); err != nil {
		fmt.Printf("[Config Updater] Warning: Failed to log change: %v\n", err)
	}

	fmt.Printf("[Config Updater] ✓ Updated %s.%s: %v → %v (by %s)\n",
		envName, field, oldValue, value, changedBy)

	return nil
}

// saveConfig saves the updated configuration to disk
func (ecu *EnvironmentConfigUpdater) saveConfig() error {
	data, err := json.MarshalIndent(ecu.config, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal config: %w", err)
	}

	// Create backup of current config
	backupPath := ecu.configPath + ".backup"
	if _, err := os.Stat(ecu.configPath); err == nil {
		if err := os.Rename(ecu.configPath, backupPath); err != nil {
			fmt.Printf("[Config Updater] Warning: Failed to create backup: %v\n", err)
		}
	}

	// Write new config
	if err := os.WriteFile(ecu.configPath, data, 0640); err != nil {
		// Restore backup if write fails
		if _, err := os.Stat(backupPath); err == nil {
			os.Rename(backupPath, ecu.configPath)
		}
		return fmt.Errorf("failed to write config: %w", err)
	}

	// Remove backup on success
	os.Remove(backupPath)

	return nil
}

// logChange appends a change to the change log
func (ecu *EnvironmentConfigUpdater) logChange(change EnvironmentChange) error {
	data, err := json.Marshal(change)
	if err != nil {
		return err
	}

	// Append to log file
	file, err := os.OpenFile(ecu.changeLogPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0640)
	if err != nil {
		return err
	}
	defer file.Close()

	if _, err := file.WriteString(string(data) + "\n"); err != nil {
		return err
	}

	return nil
}

// loadChangeLog loads existing changes from the log
func (ecu *EnvironmentConfigUpdater) loadChangeLog() error {
	data, err := os.ReadFile(ecu.changeLogPath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil // No log file yet
		}
		return err
	}

	// Parse JSONL format
	lines := []byte{}
	for _, b := range data {
		if b == '\n' {
			if len(lines) > 0 {
				var change EnvironmentChange
				if err := json.Unmarshal(lines, &change); err == nil {
					ecu.changes = append(ecu.changes, change)
				}
				lines = []byte{}
			}
		} else {
			lines = append(lines, b)
		}
	}

	return nil
}

// GetRecentChanges returns recent changes for an environment
func (ecu *EnvironmentConfigUpdater) GetRecentChanges(envName string, limit int) []EnvironmentChange {
	ecu.mutex.RLock()
	defer ecu.mutex.RUnlock()

	recent := make([]EnvironmentChange, 0)
	count := 0

	// Reverse iterate to get most recent first
	for i := len(ecu.changes) - 1; i >= 0 && count < limit; i-- {
		if ecu.changes[i].Environment == envName {
			recent = append(recent, ecu.changes[i])
			count++
		}
	}

	return recent
}

// BroadcastChange sends a change notification to specified agents
func (ecu *EnvironmentConfigUpdater) BroadcastChange(change EnvironmentChange, agents []string) error {
	notificationDir := filepath.Join(filepath.Dir(ecu.configPath), "notifications")
	if err := os.MkdirAll(notificationDir, 0750); err != nil {
		return fmt.Errorf("failed to create notifications dir: %w", err)
	}

	change.BroadcastTo = agents

	for _, agent := range agents {
		notificationFile := filepath.Join(notificationDir, fmt.Sprintf("%s_notifications.jsonl", agent))

		data, err := json.Marshal(change)
		if err != nil {
			return err
		}

		file, err := os.OpenFile(notificationFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0640)
		if err != nil {
			return err
		}
		file.WriteString(string(data) + "\n")
		file.Close()
	}

	fmt.Printf("[Config Updater] ✓ Broadcast change to %d agents\n", len(agents))
	return nil
}

// GetActiveAgents returns list of agents currently using an environment
func (ecu *EnvironmentConfigUpdater) GetActiveAgents(envName string) ([]string, error) {
	// Find environment
	var env *Environment
	for _, e := range ecu.config.Environments {
		if e.Name == envName {
			env = &e
			break
		}
	}

	if env == nil {
		return nil, fmt.Errorf("environment not found: %s", envName)
	}

	statusFile := filepath.Join(env.WorkingDir, "data", "status", fmt.Sprintf("%s_status.json", envName))

	data, err := os.ReadFile(statusFile)
	if err != nil {
		if os.IsNotExist(err) {
			return []string{}, nil
		}
		return nil, err
	}

	var status EnvironmentStatus
	if err := json.Unmarshal(data, &status); err != nil {
		return nil, err
	}

	return status.ActiveAgents, nil
}

// GetConfig returns the current configuration
func (ecu *EnvironmentConfigUpdater) GetConfig() *EnvironmentConfig {
	ecu.mutex.RLock()
	defer ecu.mutex.RUnlock()
	return ecu.config
}
