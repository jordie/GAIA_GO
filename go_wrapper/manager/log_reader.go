package manager

import (
	"bufio"
	"fmt"
	"os"
	"regexp"
	"strings"
	"time"
)

// LogChunk represents a chunk of log data
type LogChunk struct {
	Content       string
	LineNumber    int
	ContextBefore []string // Previous N lines
	ContextAfter  []string // Next N lines
}

// LogReader reads wrapper logs in chunks and matches patterns
type LogReader struct {
	filePath       string
	patternDB      *PatternDatabase
	agentName      string
	contextLines   int // How many lines of context to capture
	compiledPatterns map[int]*regexp.Regexp // Cached compiled regexes
}

// NewLogReader creates a new log reader
func NewLogReader(filePath, agentName string, patternDB *PatternDatabase) *LogReader {
	return &LogReader{
		filePath:         filePath,
		patternDB:        patternDB,
		agentName:        agentName,
		contextLines:     3, // 3 lines before/after for context
		compiledPatterns: make(map[int]*regexp.Regexp),
	}
}

// ProcessLog reads the log file and processes each line
func (lr *LogReader) ProcessLog() (*ProcessingReport, error) {
	file, err := os.Open(lr.filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to open log file: %w", err)
	}
	defer file.Close()

	// Load and compile patterns
	patterns, err := lr.patternDB.GetAllPatterns()
	if err != nil {
		return nil, fmt.Errorf("failed to load patterns: %w", err)
	}

	for i := range patterns {
		compiled, err := regexp.Compile(patterns[i].Regex)
		if err != nil {
			fmt.Printf("[LogReader] Warning: Failed to compile pattern '%s': %v\n", patterns[i].Name, err)
			continue
		}
		lr.compiledPatterns[patterns[i].ID] = compiled
	}

	fmt.Printf("[LogReader] Loaded %d patterns for matching\n", len(lr.compiledPatterns))

	report := &ProcessingReport{
		StartTime:    time.Now(),
		LogFile:      lr.filePath,
		AgentName:    lr.agentName,
		Matches:      make([]PatternMatch, 0),
		Unknowns:     make([]UnknownChunk, 0),
		LinesRead:    0,
		MatchedLines: 0,
		UnknownLines: 0,
	}

	scanner := bufio.NewScanner(file)
	lineNumber := 0
	lineBuffer := make([]string, 0)

	for scanner.Scan() {
		lineNumber++
		line := scanner.Text()
		report.LinesRead++

		// Skip empty lines and log headers
		if strings.TrimSpace(line) == "" || strings.HasPrefix(line, "#") {
			lineBuffer = append(lineBuffer, line)
			if len(lineBuffer) > lr.contextLines*2 {
				lineBuffer = lineBuffer[1:]
			}
			continue
		}

		// Try to match against known patterns
		matched := false
		for _, pattern := range patterns {
			compiledPattern, exists := lr.compiledPatterns[pattern.ID]
			if !exists {
				continue
			}

			if compiledPattern.MatchString(line) {
				// Pattern matched!
				matched = true
				report.MatchedLines++

				match := PatternMatch{
					PatternID:   pattern.ID,
					PatternName: pattern.Name,
					Matched:     line,
					AgentName:   lr.agentName,
					LogFile:     lr.filePath,
					LineNumber:  lineNumber,
					Timestamp:   time.Now(),
				}

				// Record match in database
				matchID, err := lr.patternDB.RecordMatch(match)
				if err != nil {
					fmt.Printf("[LogReader] Warning: Failed to record match: %v\n", err)
				} else {
					match.ID = matchID
					report.Matches = append(report.Matches, match)
				}

				fmt.Printf("[Match] Line %d: %s → Pattern: %s\n", lineNumber, truncate(line, 60), pattern.Name)
				break // Only match first pattern
			}
		}

		// If no pattern matched, record as unknown
		if !matched {
			report.UnknownLines++

			// Capture context
			contextBefore := lr.getContext(lineBuffer, lr.contextLines)
			// contextAfter could be filled in future iterations, but for now we only have before

			chunk := UnknownChunk{
				Content:       line,
				ContextBefore: strings.Join(contextBefore, "\n"),
				ContextAfter:  "", // Can't know future yet
				AgentName:     lr.agentName,
				LogFile:       lr.filePath,
				LineNumber:    lineNumber,
				Timestamp:     time.Now(),
			}

			// Record unknown chunk
			chunkID, err := lr.patternDB.AddUnknownChunk(chunk)
			if err != nil {
				fmt.Printf("[LogReader] Warning: Failed to record unknown chunk: %v\n", err)
			} else {
				chunk.ID = chunkID
				report.Unknowns = append(report.Unknowns, chunk)
			}

			fmt.Printf("[Unknown] Line %d: %s\n", lineNumber, truncate(line, 80))
		}

		// Add to line buffer for context
		lineBuffer = append(lineBuffer, line)
		if len(lineBuffer) > lr.contextLines*2 {
			lineBuffer = lineBuffer[1:]
		}
	}

	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("error reading log file: %w", err)
	}

	report.EndTime = time.Now()
	report.Duration = report.EndTime.Sub(report.StartTime)

	return report, nil
}

// getContext extracts the last N lines from buffer
func (lr *LogReader) getContext(buffer []string, n int) []string {
	if len(buffer) <= n {
		return buffer
	}
	return buffer[len(buffer)-n:]
}

// ProcessingReport summarizes log processing results
type ProcessingReport struct {
	StartTime    time.Time
	EndTime      time.Time
	Duration     time.Duration
	LogFile      string
	AgentName    string
	LinesRead    int
	MatchedLines int
	UnknownLines int
	Matches      []PatternMatch
	Unknowns     []UnknownChunk
}

// Summary returns a formatted summary of the report
func (pr *ProcessingReport) Summary() string {
	matchRate := 0.0
	if pr.LinesRead > 0 {
		matchRate = float64(pr.MatchedLines) / float64(pr.LinesRead) * 100
	}

	summary := fmt.Sprintf("=== Log Processing Report ===\n")
	summary += fmt.Sprintf("Log File: %s\n", pr.LogFile)
	summary += fmt.Sprintf("Agent: %s\n", pr.AgentName)
	summary += fmt.Sprintf("Duration: %v\n\n", pr.Duration)
	summary += fmt.Sprintf("Lines Read: %d\n", pr.LinesRead)
	summary += fmt.Sprintf("Matched: %d (%.2f%%)\n", pr.MatchedLines, matchRate)
	summary += fmt.Sprintf("Unknown: %d (%.2f%%)\n\n", pr.UnknownLines, 100-matchRate)

	if len(pr.Matches) > 0 {
		summary += "Recent Matches:\n"
		for i, match := range pr.Matches {
			if i >= 5 {
				summary += fmt.Sprintf("  ... and %d more\n", len(pr.Matches)-5)
				break
			}
			summary += fmt.Sprintf("  Line %d: %s\n", match.LineNumber, match.PatternName)
		}
		summary += "\n"
	}

	if len(pr.Unknowns) > 0 {
		summary += "Recent Unknowns:\n"
		for i, chunk := range pr.Unknowns {
			if i >= 5 {
				summary += fmt.Sprintf("  ... and %d more\n", len(pr.Unknowns)-5)
				break
			}
			summary += fmt.Sprintf("  Line %d: %s\n", chunk.LineNumber, truncate(chunk.Content, 60))
		}
	}

	return summary
}

// truncate truncates a string to max length
func truncate(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen-3] + "..."
}
