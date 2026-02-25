package stream

import (
	"crypto/sha256"
	"fmt"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/architect/go_wrapper/data"
)

// Match represents an extracted pattern match
type Match struct {
	Type      string                 // Pattern type (error, metric, code_block, etc.)
	Pattern   string                 // Pattern name that matched
	Value     string                 // Extracted value
	Line      string                 // Original line
	LineNum   int                    // Line number in log
	Timestamp time.Time              // When extracted
	Metadata  map[string]interface{} // Additional context
}

// Extractor handles pattern matching and data extraction from log streams
type Extractor struct {
	codexPatterns   *CodexPatterns
	generalPatterns *GeneralPatterns
	matches         []Match
	mu              sync.RWMutex
	lineCount       int
	inCodeBlock     bool
	codeBlockLang   string
	codeBlockLines  []string
	broadcaster     *Broadcaster

	// Database persistence fields
	extractionStore *data.ExtractionStore
	sessionID       string
	agentName       string
	batchBuffer     []*data.ExtractionEvent
	batchSize       int
	lastFlush       time.Time
}

// NewExtractor creates a new extraction engine
func NewExtractor() *Extractor {
	return &Extractor{
		codexPatterns:   NewCodexPatterns(),
		generalPatterns: NewGeneralPatterns(),
		matches:         make([]Match, 0),
		codeBlockLines:  make([]string, 0),
		broadcaster:     NewBroadcaster(),
		batchBuffer:     make([]*data.ExtractionEvent, 0),
		batchSize:       100, // Flush every 100 extractions
		lastFlush:       time.Now(),
	}
}

// EnableDatabase configures database persistence for extractions
func (e *Extractor) EnableDatabase(store *data.ExtractionStore, agentName, sessionID string) {
	e.mu.Lock()
	defer e.mu.Unlock()

	e.extractionStore = store
	e.agentName = agentName
	e.sessionID = sessionID
}

// DisableDatabase turns off database persistence
func (e *Extractor) DisableDatabase() {
	e.mu.Lock()
	defer e.mu.Unlock()

	// Flush any pending events
	e.flushBatchLocked()

	e.extractionStore = nil
}

// Extract processes a line and extracts structured data
func (e *Extractor) Extract(line string) []Match {
	e.mu.Lock()
	defer e.mu.Unlock()

	e.lineCount++
	lineMatches := make([]Match, 0)

	// Trim whitespace
	trimmed := strings.TrimSpace(line)
	if trimmed == "" {
		return lineMatches
	}

	// Check for code block boundaries first
	if e.handleCodeBlock(line, &lineMatches) {
		// Store matches before returning
		e.matches = append(e.matches, lineMatches...)

		// Persist code block matches
		for _, match := range lineMatches {
			e.addToBatchBuffer(match)
			if match.Type == PatternTypeCodeBlock {
				e.saveCodeBlock(match)
			}
		}

		return lineMatches
	}

	// If inside code block, collect lines but don't extract patterns
	if e.inCodeBlock {
		e.codeBlockLines = append(e.codeBlockLines, line)
		return lineMatches
	}

	// Extract patterns in priority order
	lineMatches = append(lineMatches, e.extractErrors(trimmed)...)
	lineMatches = append(lineMatches, e.extractMetrics(trimmed)...)
	lineMatches = append(lineMatches, e.extractSession(trimmed)...)
	lineMatches = append(lineMatches, e.extractStateChanges(trimmed)...)
	lineMatches = append(lineMatches, e.extractFileOps(trimmed)...)
	lineMatches = append(lineMatches, e.extractInteraction(trimmed)...)

	// Store all matches
	e.matches = append(e.matches, lineMatches...)

	// Broadcast and persist each match
	for _, match := range lineMatches {
		if e.broadcaster != nil {
			e.broadcaster.BroadcastExtraction(match)
		}

		// Add to database batch buffer
		e.addToBatchBuffer(match)

		// Save code blocks separately
		if match.Type == PatternTypeCodeBlock {
			e.saveCodeBlock(match)
		}
	}

	return lineMatches
}

// handleCodeBlock detects and handles code block boundaries
func (e *Extractor) handleCodeBlock(line string, matches *[]Match) bool {
	trimmed := strings.TrimSpace(line)

	// Check for code block start
	if !e.inCodeBlock {
		if langMatch := e.codexPatterns.CodeBlockLang.FindStringSubmatch(trimmed); langMatch != nil {
			e.inCodeBlock = true
			e.codeBlockLang = langMatch[1]
			e.codeBlockLines = make([]string, 0)

			*matches = append(*matches, Match{
				Type:      PatternTypeCodeBlock,
				Pattern:   "code_block_start",
				Value:     e.codeBlockLang,
				Line:      line,
				LineNum:   e.lineCount,
				Timestamp: time.Now(),
				Metadata: map[string]interface{}{
					"language": e.codeBlockLang,
				},
			})
			return true
		} else if e.codexPatterns.CodeBlockStart.MatchString(trimmed) {
			e.inCodeBlock = true
			e.codeBlockLang = ""
			e.codeBlockLines = make([]string, 0)

			*matches = append(*matches, Match{
				Type:      PatternTypeCodeBlock,
				Pattern:   "code_block_start",
				Value:     "unknown",
				Line:      line,
				LineNum:   e.lineCount,
				Timestamp: time.Now(),
			})
			return true
		}
	}

	// Check for code block end
	if e.inCodeBlock && e.codexPatterns.CodeBlockEnd.MatchString(trimmed) {
		codeContent := strings.Join(e.codeBlockLines, "\n")
		e.inCodeBlock = false

		*matches = append(*matches, Match{
			Type:      PatternTypeCodeBlock,
			Pattern:   "code_block_end",
			Value:     codeContent,
			Line:      line,
			LineNum:   e.lineCount,
			Timestamp: time.Now(),
			Metadata: map[string]interface{}{
				"language":   e.codeBlockLang,
				"line_count": len(e.codeBlockLines),
				"content":    codeContent,
			},
		})

		e.codeBlockLines = make([]string, 0)
		e.codeBlockLang = ""
		return true
	}

	return false
}

// extractErrors extracts error messages and stack traces
func (e *Extractor) extractErrors(line string) []Match {
	matches := make([]Match, 0)

	// Error message
	if errorMatch := e.codexPatterns.ErrorMessage.FindStringSubmatch(line); errorMatch != nil {
		matches = append(matches, Match{
			Type:      PatternTypeError,
			Pattern:   "error",
			Value:     errorMatch[1],
			Line:      line,
			LineNum:   e.lineCount,
			Timestamp: time.Now(),
			Metadata: map[string]interface{}{
				"severity": "error",
			},
		})
	}

	// Warning
	if warnMatch := e.codexPatterns.Warning.FindStringSubmatch(line); warnMatch != nil {
		matches = append(matches, Match{
			Type:      PatternTypeError,
			Pattern:   "warning",
			Value:     warnMatch[1],
			Line:      line,
			LineNum:   e.lineCount,
			Timestamp: time.Now(),
			Metadata: map[string]interface{}{
				"severity": "warning",
			},
		})
	}

	// Stack trace
	if e.codexPatterns.ErrorStack.MatchString(line) {
		matches = append(matches, Match{
			Type:      PatternTypeError,
			Pattern:   "stack_trace",
			Value:     line,
			Line:      line,
			LineNum:   e.lineCount,
			Timestamp: time.Now(),
		})
	}

	return matches
}

// extractMetrics extracts performance metrics
func (e *Extractor) extractMetrics(line string) []Match {
	matches := make([]Match, 0)

	// Tokens used
	if tokensMatch := e.codexPatterns.TokensUsed.FindStringSubmatch(line); tokensMatch != nil {
		// Remove commas from number
		tokensStr := strings.ReplaceAll(tokensMatch[1], ",", "")
		matches = append(matches, Match{
			Type:      PatternTypeMetric,
			Pattern:   "tokens_used",
			Value:     tokensStr,
			Line:      line,
			LineNum:   e.lineCount,
			Timestamp: time.Now(),
			Metadata: map[string]interface{}{
				"unit": "tokens",
			},
		})
	}

	// Time elapsed
	if timeMatch := e.codexPatterns.TimeElapsed.FindStringSubmatch(line); timeMatch != nil {
		matches = append(matches, Match{
			Type:      PatternTypeMetric,
			Pattern:   "time_elapsed",
			Value:     timeMatch[1],
			Line:      line,
			LineNum:   e.lineCount,
			Timestamp: time.Now(),
			Metadata: map[string]interface{}{
				"unit": timeMatch[2],
			},
		})
	}

	// Memory usage
	if memMatch := e.codexPatterns.MemoryUsage.FindStringSubmatch(line); memMatch != nil {
		matches = append(matches, Match{
			Type:      PatternTypeMetric,
			Pattern:   "memory_usage",
			Value:     memMatch[1],
			Line:      line,
			LineNum:   e.lineCount,
			Timestamp: time.Now(),
			Metadata: map[string]interface{}{
				"unit": memMatch[2],
			},
		})
	}

	return matches
}

// extractSession extracts session metadata
func (e *Extractor) extractSession(line string) []Match {
	matches := make([]Match, 0)

	patterns := map[string]*regexp.Regexp{
		"session_id": e.codexPatterns.SessionID,
		"workdir":    e.codexPatterns.Workdir,
		"model":      e.codexPatterns.Model,
		"provider":   e.codexPatterns.Provider,
		"approval":   e.codexPatterns.Approval,
		"sandbox":    e.codexPatterns.Sandbox,
		"reasoning":  e.codexPatterns.Reasoning,
	}

	for name, pattern := range patterns {
		if match := pattern.FindStringSubmatch(line); match != nil {
			matches = append(matches, Match{
				Type:      PatternTypeSession,
				Pattern:   name,
				Value:     match[1],
				Line:      line,
				LineNum:   e.lineCount,
				Timestamp: time.Now(),
			})
		}
	}

	return matches
}

// extractStateChanges extracts task state transitions
func (e *Extractor) extractStateChanges(line string) []Match {
	matches := make([]Match, 0)

	// Task started
	if startMatch := e.codexPatterns.TaskStarted.FindStringSubmatch(line); startMatch != nil {
		matches = append(matches, Match{
			Type:      PatternTypeStateChange,
			Pattern:   "task_started",
			Value:     startMatch[1],
			Line:      line,
			LineNum:   e.lineCount,
			Timestamp: time.Now(),
			Metadata: map[string]interface{}{
				"state": "started",
			},
		})
	}

	// Task completed
	if completeMatch := e.codexPatterns.TaskCompleted.FindStringSubmatch(line); completeMatch != nil {
		matches = append(matches, Match{
			Type:      PatternTypeStateChange,
			Pattern:   "task_completed",
			Value:     completeMatch[1],
			Line:      line,
			LineNum:   e.lineCount,
			Timestamp: time.Now(),
			Metadata: map[string]interface{}{
				"state": "completed",
			},
		})
	}

	// Task failed
	if failMatch := e.codexPatterns.TaskFailed.FindStringSubmatch(line); failMatch != nil {
		matches = append(matches, Match{
			Type:      PatternTypeStateChange,
			Pattern:   "task_failed",
			Value:     failMatch[1],
			Line:      line,
			LineNum:   e.lineCount,
			Timestamp: time.Now(),
			Metadata: map[string]interface{}{
				"state": "failed",
			},
		})
	}

	return matches
}

// extractFileOps extracts file operations
func (e *Extractor) extractFileOps(line string) []Match {
	matches := make([]Match, 0)

	filePatterns := map[string]*regexp.Regexp{
		"file_created":  e.codexPatterns.FileCreated,
		"file_modified": e.codexPatterns.FileModified,
		"file_deleted":  e.codexPatterns.FileDeleted,
		"file_read":     e.codexPatterns.FileRead,
	}

	for name, pattern := range filePatterns {
		if match := pattern.FindStringSubmatch(line); match != nil {
			matches = append(matches, Match{
				Type:      PatternTypeFileOp,
				Pattern:   name,
				Value:     match[1],
				Line:      line,
				LineNum:   e.lineCount,
				Timestamp: time.Now(),
				Metadata: map[string]interface{}{
					"filename": match[1],
				},
			})
		}
	}

	return matches
}

// extractInteraction extracts user/codex interaction markers
func (e *Extractor) extractInteraction(line string) []Match {
	matches := make([]Match, 0)

	// User prompt marker
	if e.codexPatterns.UserPrompt.MatchString(line) {
		matches = append(matches, Match{
			Type:      PatternTypePrompt,
			Pattern:   "user_prompt",
			Value:     "user",
			Line:      line,
			LineNum:   e.lineCount,
			Timestamp: time.Now(),
		})
	}

	// Codex response marker
	if e.codexPatterns.CodexResponse.MatchString(line) {
		matches = append(matches, Match{
			Type:      PatternTypeResponse,
			Pattern:   "codex_response",
			Value:     "codex",
			Line:      line,
			LineNum:   e.lineCount,
			Timestamp: time.Now(),
		})
	}

	// MCP startup
	if mcpMatch := e.codexPatterns.MCPStartup.FindStringSubmatch(line); mcpMatch != nil {
		matches = append(matches, Match{
			Type:      PatternTypeSession,
			Pattern:   "mcp_startup",
			Value:     mcpMatch[1],
			Line:      line,
			LineNum:   e.lineCount,
			Timestamp: time.Now(),
		})
	}

	return matches
}

// GetMatches returns all extracted matches
func (e *Extractor) GetMatches() []Match {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return append([]Match{}, e.matches...)
}

// GetMatchesByType returns matches filtered by type
func (e *Extractor) GetMatchesByType(matchType string) []Match {
	e.mu.RLock()
	defer e.mu.RUnlock()

	filtered := make([]Match, 0)
	for _, m := range e.matches {
		if m.Type == matchType {
			filtered = append(filtered, m)
		}
	}
	return filtered
}

// GetStats returns extraction statistics
func (e *Extractor) GetStats() map[string]interface{} {
	e.mu.RLock()
	defer e.mu.RUnlock()

	typeCount := make(map[string]int)
	for _, m := range e.matches {
		typeCount[m.Type]++
	}

	return map[string]interface{}{
		"total_lines":     e.lineCount,
		"total_matches":   len(e.matches),
		"matches_by_type": typeCount,
		"in_code_block":   e.inCodeBlock,
	}
}

// Clear resets the extractor state
func (e *Extractor) Clear() {
	e.mu.Lock()
	defer e.mu.Unlock()

	// Flush any pending extractions to database
	e.flushBatchLocked()

	e.matches = make([]Match, 0)
	e.lineCount = 0
	e.inCodeBlock = false
	e.codeBlockLang = ""
	e.codeBlockLines = make([]string, 0)
	e.batchBuffer = make([]*data.ExtractionEvent, 0)
}

// GetBroadcaster returns the broadcaster for this extractor
func (e *Extractor) GetBroadcaster() *Broadcaster {
	return e.broadcaster
}

// FormatMatch returns a human-readable string for a match
func FormatMatch(m Match) string {
	return fmt.Sprintf("[%s] %s: %s (line %d)",
		m.Type, m.Pattern, m.Value, m.LineNum)
}

// convertMatchToEvent converts a Match to an ExtractionEvent for database storage
func (e *Extractor) convertMatchToEvent(match Match) *data.ExtractionEvent {
	// Determine risk level based on pattern type and severity
	riskLevel := "low"
	if match.Type == PatternTypeError {
		if severity, ok := match.Metadata["severity"].(string); ok {
			if severity == "error" || severity == "critical" {
				riskLevel = "high"
			} else if severity == "warning" {
				riskLevel = "medium"
			}
		}
	}

	// Determine if auto-confirmable based on pattern type
	autoConfirmable := false
	if match.Type == PatternTypeMetric || match.Type == PatternTypeResponse {
		autoConfirmable = true
	}

	// Extract code block language if applicable
	codeBlockLang := ""
	if match.Type == PatternTypeCodeBlock {
		if lang, ok := match.Metadata["language"].(string); ok {
			codeBlockLang = lang
		}
	}

	return &data.ExtractionEvent{
		AgentName:       e.agentName,
		SessionID:       e.sessionID,
		Timestamp:       match.Timestamp,
		EventType:       match.Type,
		Pattern:         match.Pattern,
		MatchedValue:    match.Value,
		OriginalLine:    match.Line,
		LineNumber:      match.LineNum,
		Metadata:        match.Metadata,
		CodeBlockLang:   codeBlockLang,
		RiskLevel:       riskLevel,
		AutoConfirmable: autoConfirmable,
	}
}

// addToBatchBuffer adds an extraction to the batch buffer and flushes if needed
func (e *Extractor) addToBatchBuffer(match Match) {
	if e.extractionStore == nil {
		return
	}

	event := e.convertMatchToEvent(match)
	e.batchBuffer = append(e.batchBuffer, event)

	// Flush if batch is full or timeout exceeded
	if len(e.batchBuffer) >= e.batchSize || time.Since(e.lastFlush) > 5*time.Second {
		e.flushBatchLocked()
	}
}

// flushBatchLocked flushes the batch buffer (caller must hold lock)
func (e *Extractor) flushBatchLocked() error {
	if e.extractionStore == nil || len(e.batchBuffer) == 0 {
		return nil
	}

	if err := e.extractionStore.SaveExtractionBatch(e.batchBuffer); err != nil {
		return fmt.Errorf("failed to save extraction batch: %w", err)
	}

	// Clear buffer and update flush time
	e.batchBuffer = e.batchBuffer[:0]
	e.lastFlush = time.Now()

	return nil
}

// FlushBatch flushes any pending extractions to database (thread-safe)
func (e *Extractor) FlushBatch() error {
	e.mu.Lock()
	defer e.mu.Unlock()

	return e.flushBatchLocked()
}

// saveCodeBlock saves a code block to the database
func (e *Extractor) saveCodeBlock(match Match) {
	if e.extractionStore == nil {
		return
	}

	// Get code block content
	content := match.Value
	if content == "" {
		return
	}

	// Calculate digest for deduplication
	digest := fmt.Sprintf("%x", sha256.Sum256([]byte(content)))

	// Get language
	language := ""
	if lang, ok := match.Metadata["language"].(string); ok {
		language = lang
	}

	// Get line range
	lineStart := match.LineNum
	lineEnd := match.LineNum
	if lines, ok := match.Metadata["line_count"].(int); ok {
		lineEnd = lineStart + lines - 1
	}

	block := &data.CodeBlock{
		AgentName: e.agentName,
		SessionID: e.sessionID,
		Timestamp: match.Timestamp,
		Language:  language,
		Content:   content,
		LineStart: lineStart,
		LineEnd:   lineEnd,
		Context:   match.Metadata,
		Parseable: true, // Assume parseable unless proven otherwise
		Digest:    digest,
	}

	if err := e.extractionStore.SaveCodeBlock(block); err != nil {
		// Log error but don't fail extraction
		fmt.Printf("Warning: Failed to save code block: %v\n", err)
	}
}

// GetBatchBufferSize returns the current size of the batch buffer
func (e *Extractor) GetBatchBufferSize() int {
	e.mu.RLock()
	defer e.mu.RUnlock()

	return len(e.batchBuffer)
}
