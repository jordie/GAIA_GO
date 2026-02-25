package stream

import (
	"encoding/json"
	"fmt"
	"os"
	"regexp"
	"sort"
)

// ConfigurablePattern represents a pattern loaded from JSON config
type ConfigurablePattern struct {
	Name        string            `json:"name"`
	EventType   string            `json:"event_type"`
	Regex       string            `json:"regex"`
	FieldMap    map[string]int    `json:"field_map"`
	Priority    int               `json:"priority"`
	AutoConfirm bool              `json:"auto_confirm"`
	RiskLevel   string            `json:"risk_level"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
	compiled    *regexp.Regexp    // Compiled regex (not exported to JSON)
}

// ExtractionSettings configures extractor behavior
type ExtractionSettings struct {
	BufferSize       int    `json:"buffer_size"`
	EventBufferSize  int    `json:"event_buffer_size"`
	EnableTraining   bool   `json:"enable_training"`
	TrainingDataPath string `json:"training_data_path"`
}

// ExtractionConfig holds the full configuration
type ExtractionConfig struct {
	Version  string                 `json:"version"`
	Settings ExtractionSettings     `json:"settings"`
	Patterns []ConfigurablePattern  `json:"patterns"`
}

// ExtractedEvent represents a structured event from pattern matching
type ExtractedEvent struct {
	ID        string                 `json:"id"`
	Timestamp string                 `json:"timestamp"`
	AgentName string                 `json:"agent_name"`
	EventType string                 `json:"event_type"`
	Pattern   string                 `json:"pattern"`
	Matched   string                 `json:"matched"`
	Fields    map[string]string      `json:"fields"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
}

// LoadExtractionConfig loads patterns from JSON file
func LoadExtractionConfig(path string) (*ExtractionConfig, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read config: %w", err)
	}

	var config ExtractionConfig
	if err := json.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("failed to parse config: %w", err)
	}

	// Compile all patterns
	for i := range config.Patterns {
		pattern := &config.Patterns[i]
		compiled, err := regexp.Compile(pattern.Regex)
		if err != nil {
			return nil, fmt.Errorf("failed to compile pattern '%s': %w", pattern.Name, err)
		}
		pattern.compiled = compiled
	}

	// Sort patterns by priority (highest first)
	sort.Slice(config.Patterns, func(i, j int) bool {
		return config.Patterns[i].Priority > config.Patterns[j].Priority
	})

	return &config, nil
}

// SaveExtractionConfig saves config to JSON file
func SaveExtractionConfig(config *ExtractionConfig, path string) error {
	data, err := json.MarshalIndent(config, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal config: %w", err)
	}
	return os.WriteFile(path, data, 0644)
}

// AddPattern adds a new pattern to the config and recompiles
func (c *ExtractionConfig) AddPattern(pattern ConfigurablePattern) error {
	compiled, err := regexp.Compile(pattern.Regex)
	if err != nil {
		return fmt.Errorf("invalid regex: %w", err)
	}
	pattern.compiled = compiled
	c.Patterns = append(c.Patterns, pattern)

	// Re-sort by priority
	sort.Slice(c.Patterns, func(i, j int) bool {
		return c.Patterns[i].Priority > c.Patterns[j].Priority
	})

	return nil
}

// RemovePattern removes a pattern by name
func (c *ExtractionConfig) RemovePattern(name string) bool {
	for i, pattern := range c.Patterns {
		if pattern.Name == name {
			c.Patterns = append(c.Patterns[:i], c.Patterns[i+1:]...)
			return true
		}
	}
	return false
}

// GetPattern retrieves a pattern by name
func (c *ExtractionConfig) GetPattern(name string) *ConfigurablePattern {
	for i := range c.Patterns {
		if c.Patterns[i].Name == name {
			return &c.Patterns[i]
		}
	}
	return nil
}

// ListPatterns returns all pattern names sorted by priority
func (c *ExtractionConfig) ListPatterns() []string {
	names := make([]string, len(c.Patterns))
	for i, pattern := range c.Patterns {
		names[i] = pattern.Name
	}
	return names
}

// GetAutoConfirmPatterns returns patterns that can be auto-confirmed
func (c *ExtractionConfig) GetAutoConfirmPatterns() []ConfigurablePattern {
	autoConfirm := make([]ConfigurablePattern, 0)
	for _, pattern := range c.Patterns {
		if pattern.AutoConfirm {
			autoConfirm = append(autoConfirm, pattern)
		}
	}
	return autoConfirm
}

// GetPatternsByRiskLevel returns patterns filtered by risk level
func (c *ExtractionConfig) GetPatternsByRiskLevel(level string) []ConfigurablePattern {
	filtered := make([]ConfigurablePattern, 0)
	for _, pattern := range c.Patterns {
		if pattern.RiskLevel == level {
			filtered = append(filtered, pattern)
		}
	}
	return filtered
}
