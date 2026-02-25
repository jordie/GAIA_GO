package stream

import (
	"encoding/json"
	"fmt"
	"os"
	"sync"
	"time"
)

// ConfigurableExtractor uses JSON config for pattern matching
type ConfigurableExtractor struct {
	agentName      string
	config         *ExtractionConfig
	events         []ExtractedEvent
	eventCount     int
	lineBuffer     []string
	mu             sync.RWMutex
	trainingLog    *os.File
	trainingLogger *TrainingLogger
}

// NewConfigurableExtractor creates an extractor from config file
func NewConfigurableExtractor(agentName, configPath string) (*ConfigurableExtractor, error) {
	config, err := LoadExtractionConfig(configPath)
	if err != nil {
		return nil, err
	}

	extractor := &ConfigurableExtractor{
		agentName:  agentName,
		config:     config,
		events:     make([]ExtractedEvent, 0, config.Settings.EventBufferSize),
		lineBuffer: make([]string, 0, config.Settings.BufferSize),
	}

	// Initialize training logger if enabled
	if config.Settings.EnableTraining {
		if err := extractor.initTrainingLog(); err != nil {
			return nil, err
		}
	}

	return extractor, nil
}

// initTrainingLog sets up training data logging
func (ce *ConfigurableExtractor) initTrainingLog() error {
	os.MkdirAll(ce.config.Settings.TrainingDataPath, 0755)

	logPath := fmt.Sprintf("%s/%s-events-%s.jsonl",
		ce.config.Settings.TrainingDataPath,
		ce.agentName,
		time.Now().Format("2006-01-02-15-04-05"))

	var err error
	ce.trainingLog, err = os.Create(logPath)
	if err != nil {
		return fmt.Errorf("failed to create training log: %w", err)
	}

	// Also initialize structured training logger
	ce.trainingLogger, err = NewTrainingLogger(
		ce.agentName,
		fmt.Sprintf("session-%d", time.Now().Unix()),
		ce.config.Settings.TrainingDataPath,
	)
	if err != nil {
		return fmt.Errorf("failed to create training logger: %w", err)
	}

	return nil
}

// ProcessLine processes a line and extracts events using configured patterns
func (ce *ConfigurableExtractor) ProcessLine(line string) []ExtractedEvent {
	ce.mu.Lock()
	defer ce.mu.Unlock()

	// Add to buffer
	ce.lineBuffer = append(ce.lineBuffer, line)
	if len(ce.lineBuffer) > ce.config.Settings.BufferSize {
		ce.lineBuffer = ce.lineBuffer[1:]
	}

	events := make([]ExtractedEvent, 0)

	// Try each pattern in priority order
	for _, pattern := range ce.config.Patterns {
		if match := pattern.compiled.FindStringSubmatch(line); match != nil {
			event := ce.createEvent(&pattern, match, line)
			events = append(events, event)
			ce.recordEvent(event)

			// Log as training event if appropriate
			if ce.config.Settings.EnableTraining {
				ce.logTrainingEvent(&event, &pattern)
			}
		}
	}

	return events
}

// createEvent builds an ExtractedEvent from a pattern match
func (ce *ConfigurableExtractor) createEvent(pattern *ConfigurablePattern, match []string, line string) ExtractedEvent {
	ce.eventCount++

	// Extract fields using field map
	fields := make(map[string]string)
	for fieldName, groupIdx := range pattern.FieldMap {
		if groupIdx < len(match) {
			fields[fieldName] = match[groupIdx]
		}
	}

	// Build metadata
	metadata := make(map[string]interface{})
	metadata["pattern"] = pattern.Name
	metadata["auto_confirm"] = pattern.AutoConfirm
	metadata["risk_level"] = pattern.RiskLevel
	for k, v := range pattern.Metadata {
		metadata[k] = v
	}

	return ExtractedEvent{
		ID:        fmt.Sprintf("%s-event-%d", ce.agentName, ce.eventCount),
		Timestamp: time.Now().Format(time.RFC3339),
		AgentName: ce.agentName,
		EventType: pattern.EventType,
		Pattern:   pattern.Name,
		Matched:   line,
		Fields:    fields,
		Metadata:  metadata,
	}
}

// recordEvent stores event in memory buffer
func (ce *ConfigurableExtractor) recordEvent(event ExtractedEvent) {
	ce.events = append(ce.events, event)

	// Keep buffer size limited
	if len(ce.events) > ce.config.Settings.EventBufferSize {
		ce.events = ce.events[1:]
	}

	// Write to training log
	if ce.trainingLog != nil {
		data, _ := json.Marshal(event)
		fmt.Fprintf(ce.trainingLog, "%s\n", data)
	}
}

// logTrainingEvent logs event to training logger for ML training
func (ce *ConfigurableExtractor) logTrainingEvent(event *ExtractedEvent, pattern *ConfigurablePattern) {
	if ce.trainingLogger == nil {
		return
	}

	trainingEvent := &TrainingEvent{
		EventType: event.EventType,
		ToolName:  event.Fields["tool"],
		Metadata:  event.Metadata,
		Success:   true,
	}

	// Add permission tracking for non-auto-confirm patterns
	if !pattern.AutoConfirm {
		trainingEvent.EventType = "permission"
		trainingEvent.PermissionType = event.Fields["action"]
		trainingEvent.AutoConfirmable = false
		trainingEvent.RiskLevel = pattern.RiskLevel
	}

	ce.trainingLogger.LogEvent(trainingEvent)
}

// GetEvents returns recent events
func (ce *ConfigurableExtractor) GetEvents(limit int) []ExtractedEvent {
	ce.mu.RLock()
	defer ce.mu.RUnlock()

	if limit <= 0 || limit > len(ce.events) {
		limit = len(ce.events)
	}

	start := len(ce.events) - limit
	if start < 0 {
		start = 0
	}

	return ce.events[start:]
}

// GetEventsByType returns events filtered by type
func (ce *ConfigurableExtractor) GetEventsByType(eventType string) []ExtractedEvent {
	ce.mu.RLock()
	defer ce.mu.RUnlock()

	filtered := make([]ExtractedEvent, 0)
	for _, event := range ce.events {
		if event.EventType == eventType {
			filtered = append(filtered, event)
		}
	}
	return filtered
}

// GetAutoConfirmableEvents returns events that can be auto-confirmed
func (ce *ConfigurableExtractor) GetAutoConfirmableEvents() []ExtractedEvent {
	ce.mu.RLock()
	defer ce.mu.RUnlock()

	filtered := make([]ExtractedEvent, 0)
	for _, event := range ce.events {
		if ac, ok := event.Metadata["auto_confirm"].(bool); ok && ac {
			filtered = append(filtered, event)
		}
	}
	return filtered
}

// GetStats returns extraction statistics
func (ce *ConfigurableExtractor) GetStats() map[string]interface{} {
	ce.mu.RLock()
	defer ce.mu.RUnlock()

	eventsByType := make(map[string]int)
	autoConfirmCount := 0
	riskLevelCount := make(map[string]int)

	for _, event := range ce.events {
		eventsByType[event.EventType]++

		if ac, ok := event.Metadata["auto_confirm"].(bool); ok && ac {
			autoConfirmCount++
		}

		if risk, ok := event.Metadata["risk_level"].(string); ok {
			riskLevelCount[risk]++
		}
	}

	stats := map[string]interface{}{
		"agent_name":        ce.agentName,
		"total_events":      ce.eventCount,
		"events_in_memory":  len(ce.events),
		"events_by_type":    eventsByType,
		"auto_confirmable":  autoConfirmCount,
		"risk_level_dist":   riskLevelCount,
		"patterns_loaded":   len(ce.config.Patterns),
		"training_enabled":  ce.config.Settings.EnableTraining,
	}

	// Add training logger stats if available
	if ce.trainingLogger != nil {
		stats["training_stats"] = ce.trainingLogger.GetStats()
	}

	return stats
}

// GetConfig returns the current configuration
func (ce *ConfigurableExtractor) GetConfig() *ExtractionConfig {
	return ce.config
}

// ReloadConfig reloads patterns from config file
func (ce *ConfigurableExtractor) ReloadConfig(configPath string) error {
	config, err := LoadExtractionConfig(configPath)
	if err != nil {
		return err
	}

	ce.mu.Lock()
	defer ce.mu.Unlock()

	ce.config = config
	return nil
}

// Close flushes and closes resources
func (ce *ConfigurableExtractor) Close() error {
	ce.mu.Lock()
	defer ce.mu.Unlock()

	var errs []error

	if ce.trainingLog != nil {
		if err := ce.trainingLog.Close(); err != nil {
			errs = append(errs, err)
		}
	}

	if ce.trainingLogger != nil {
		if err := ce.trainingLogger.Close(); err != nil {
			errs = append(errs, err)
		}
	}

	if len(errs) > 0 {
		return fmt.Errorf("errors closing extractor: %v", errs)
	}

	return nil
}
