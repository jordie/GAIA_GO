package manager

import (
	"fmt"
	"regexp"
	"strings"
	"time"
)

// LearningWorker analyzes unknown chunks and proposes new patterns
type LearningWorker struct {
	patternDB *PatternDatabase
	minOccurrences int // Minimum times a pattern must appear to be proposed
	testSampleSize int // Number of samples to test pattern against
}

// NewLearningWorker creates a new learning worker
func NewLearningWorker(patternDB *PatternDatabase) *LearningWorker {
	return &LearningWorker{
		patternDB:      patternDB,
		minOccurrences: 3,  // Need at least 3 occurrences
		testSampleSize: 10, // Test against 10 samples
	}
}

// AnalyzeUnknowns processes unanalyzed chunks and proposes patterns
func (lw *LearningWorker) AnalyzeUnknowns(limit int) (*LearningReport, error) {
	report := &LearningReport{
		StartTime:        time.Now(),
		ProposedPatterns: make([]ProposedPattern, 0),
		ChunksAnalyzed:   0,
	}

	// Get unanalyzed chunks
	chunks, err := lw.patternDB.GetUnanalyzedChunks(limit)
	if err != nil {
		return nil, fmt.Errorf("failed to get unanalyzed chunks: %w", err)
	}

	if len(chunks) == 0 {
		fmt.Println("[Learning] No unanalyzed chunks found")
		return report, nil
	}

	fmt.Printf("[Learning] Analyzing %d unknown chunks...\n", len(chunks))

	// Group similar chunks
	groups := lw.groupSimilarChunks(chunks)

	// Analyze each group
	for _, group := range groups {
		if len(group) < lw.minOccurrences {
			// Not enough occurrences, mark as analyzed but don't propose
			for _, chunk := range group {
				lw.patternDB.MarkChunkAnalyzed(chunk.ID, nil)
				report.ChunksAnalyzed++
			}
			continue
		}

		// Try to extract a pattern from this group
		proposed := lw.proposePattern(group)
		if proposed != nil {
			// Test the pattern
			testResult := lw.testPattern(proposed, chunks)

			if testResult.SuccessRate >= 0.7 { // 70% success rate threshold
				// Add pattern to database
				patternID, err := lw.patternDB.AddPattern(Pattern{
					Name:            proposed.Name,
					Regex:           proposed.Regex,
					Category:        proposed.Category,
					Confidence:      testResult.SuccessRate,
					Action:          proposed.Action,
					TargetWorker:    proposed.TargetWorker,
					ProposedBy:      "learning_worker",
					Tested:          true,
					TestSuccessRate: testResult.SuccessRate,
					Metadata:        proposed.Metadata,
				})

				if err == nil {
					proposed.ID = patternID
					proposed.TestResult = testResult
					report.ProposedPatterns = append(report.ProposedPatterns, *proposed)

					// Mark chunks as analyzed with the proposed pattern
					for _, chunk := range group {
						lw.patternDB.MarkChunkAnalyzed(chunk.ID, &patternID)
						report.ChunksAnalyzed++
					}

					fmt.Printf("[Learning] ✓ Proposed pattern: %s (success rate: %.2f%%)\n",
						proposed.Name, testResult.SuccessRate*100)
				}
			} else {
				// Pattern didn't pass testing, mark chunks as analyzed without pattern
				for _, chunk := range group {
					lw.patternDB.MarkChunkAnalyzed(chunk.ID, nil)
					report.ChunksAnalyzed++
				}

				fmt.Printf("[Learning] ✗ Pattern rejected: %s (success rate: %.2f%%)\n",
					proposed.Name, testResult.SuccessRate*100)
			}
		}
	}

	report.EndTime = time.Now()
	report.Duration = report.EndTime.Sub(report.StartTime)

	return report, nil
}

// groupSimilarChunks groups chunks with similar content
func (lw *LearningWorker) groupSimilarChunks(chunks []UnknownChunk) [][]UnknownChunk {
	groups := make([][]UnknownChunk, 0)

	for _, chunk := range chunks {
		foundGroup := false

		// Try to add to existing group
		for i := range groups {
			if lw.areSimilar(chunk.Content, groups[i][0].Content) {
				groups[i] = append(groups[i], chunk)
				foundGroup = true
				break
			}
		}

		// Create new group if not found
		if !foundGroup {
			groups = append(groups, []UnknownChunk{chunk})
		}
	}

	return groups
}

// areSimilar checks if two strings are similar enough to group together
func (lw *LearningWorker) areSimilar(a, b string) bool {
	// Simple similarity: check if they share significant common structure

	// Extract common prefixes
	aPrefix := extractPrefix(a, 20)
	bPrefix := extractPrefix(b, 20)

	if aPrefix == bPrefix && aPrefix != "" {
		return true
	}

	// Extract common patterns (e.g., both have timestamps, both have error codes)
	aTokens := tokenize(a)
	bTokens := tokenize(b)

	commonTokens := 0
	for token := range aTokens {
		if _, exists := bTokens[token]; exists {
			commonTokens++
		}
	}

	// If 60% of tokens match, consider similar
	totalTokens := len(aTokens)
	if totalTokens == 0 {
		return false
	}

	similarity := float64(commonTokens) / float64(totalTokens)
	return similarity >= 0.6
}

// proposePattern attempts to extract a regex pattern from a group of similar chunks
func (lw *LearningWorker) proposePattern(group []UnknownChunk) *ProposedPattern {
	if len(group) == 0 {
		return nil
	}

	// Extract common structure
	commonStructure := lw.extractCommonStructure(group)
	if commonStructure == "" {
		return nil
	}

	// Generate pattern name
	name := lw.generatePatternName(group[0].Content)

	// Determine category based on content
	category := lw.categorizeContent(group[0].Content)

	// Determine action and target worker based on category
	action, targetWorker := lw.determineAction(category, group[0].Content)

	pattern := &ProposedPattern{
		Name:         name,
		Regex:        commonStructure,
		Category:     category,
		Occurrences:  len(group),
		Examples:     lw.extractExamples(group, 3),
		Action:       action,
		TargetWorker: targetWorker,
		Metadata: map[string]interface{}{
			"auto_generated": true,
			"source_chunks":  len(group),
		},
	}

	return pattern
}

// extractCommonStructure finds the common regex pattern in a group of chunks
func (lw *LearningWorker) extractCommonStructure(group []UnknownChunk) string {
	if len(group) == 0 {
		return ""
	}

	// Start with first example
	template := group[0].Content

	// Replace variable parts with regex patterns
	pattern := template

	// Replace common variable patterns
	pattern = replaceNumbers(pattern)
	pattern = replaceTimestamps(pattern)
	pattern = replacePaths(pattern)
	pattern = replaceWords(pattern)

	// Escape regex special characters
	pattern = regexp.QuoteMeta(pattern)

	// Restore our patterns
	pattern = strings.ReplaceAll(pattern, "\\[NUM\\]", "\\d+")
	pattern = strings.ReplaceAll(pattern, "\\[TIME\\]", "\\d{2}:\\d{2}:\\d{2}")
	pattern = strings.ReplaceAll(pattern, "\\[PATH\\]", "[\\w/\\.-]+")
	pattern = strings.ReplaceAll(pattern, "\\[WORD\\]", "\\w+")

	return pattern
}

// Helper functions for pattern extraction
func replaceNumbers(s string) string {
	re := regexp.MustCompile(`\d+`)
	return re.ReplaceAllString(s, "[NUM]")
}

func replaceTimestamps(s string) string {
	re := regexp.MustCompile(`\d{2}:\d{2}:\d{2}`)
	return re.ReplaceAllString(s, "[TIME]")
}

func replacePaths(s string) string {
	re := regexp.MustCompile(`[\w/\.-]+\.(go|py|js|json|md|txt|log)`)
	return re.ReplaceAllString(s, "[PATH]")
}

func replaceWords(s string) string {
	// Replace variable words (not common words like "the", "and", etc.)
	// This is simplified - in production, use a more sophisticated approach
	return s
}

func extractPrefix(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen]
}

func tokenize(s string) map[string]bool {
	tokens := make(map[string]bool)
	for _, word := range strings.Fields(s) {
		tokens[word] = true
	}
	return tokens
}

// categorizeContent determines the category of content
func (lw *LearningWorker) categorizeContent(content string) string {
	content = strings.ToLower(content)

	if strings.Contains(content, "error") || strings.Contains(content, "failed") {
		return "error"
	}
	if strings.Contains(content, "⏺") || strings.Contains(content, "bash") || strings.Contains(content, "edit") {
		return "tool_use"
	}
	if strings.Contains(content, "thinking") || strings.Contains(content, "processing") {
		return "state_change"
	}
	if strings.Contains(content, "✓") || strings.Contains(content, "completed") {
		return "success"
	}

	return "general"
}

// determineAction determines what action to take and which worker to dispatch to
func (lw *LearningWorker) determineAction(category, content string) (string, string) {
	switch category {
	case "error":
		return "log_error", "error_handler"
	case "tool_use":
		return "dispatch_tool", "tool_executor"
	case "state_change":
		return "update_state", "state_tracker"
	case "success":
		return "log_success", "metrics_collector"
	default:
		return "log", "general_logger"
	}
}

// extractExamples extracts example strings from group
func (lw *LearningWorker) extractExamples(group []UnknownChunk, count int) []string {
	examples := make([]string, 0)
	for i, chunk := range group {
		if i >= count {
			break
		}
		examples = append(examples, chunk.Content)
	}
	return examples
}

// generatePatternName generates a descriptive name for the pattern
func (lw *LearningWorker) generatePatternName(example string) string {
	// Extract key words
	words := strings.Fields(example)

	// Take first few significant words
	name := "pattern"
	for _, word := range words {
		cleaned := strings.Trim(word, "[](){}:,.")
		if len(cleaned) > 3 && !isCommonWord(cleaned) {
			name += "_" + strings.ToLower(cleaned)
			break
		}
	}

	// Add timestamp to ensure uniqueness
	name += fmt.Sprintf("_%d", time.Now().Unix())

	return name
}

func isCommonWord(word string) bool {
	common := map[string]bool{
		"the": true, "and": true, "for": true, "with": true, "from": true,
		"this": true, "that": true, "have": true, "been": true,
	}
	return common[strings.ToLower(word)]
}

// testPattern tests a proposed pattern against sample data
func (lw *LearningWorker) testPattern(proposed *ProposedPattern, testSamples []UnknownChunk) *TestResult {
	compiled, err := regexp.Compile(proposed.Regex)
	if err != nil {
		return &TestResult{
			SuccessRate: 0.0,
			Passed:      0,
			Failed:      len(testSamples),
			Error:       err.Error(),
		}
	}

	passed := 0
	failed := 0

	// Test against examples it should match
	for _, example := range proposed.Examples {
		if compiled.MatchString(example) {
			passed++
		} else {
			failed++
		}
	}

	// Test that it doesn't over-match
	testCount := 0
	for _, sample := range testSamples {
		if testCount >= lw.testSampleSize {
			break
		}

		// Should not match unrelated content
		shouldMatch := false
		for _, example := range proposed.Examples {
			if lw.areSimilar(sample.Content, example) {
				shouldMatch = true
				break
			}
		}

		matches := compiled.MatchString(sample.Content)

		if shouldMatch && matches {
			passed++
		} else if !shouldMatch && !matches {
			passed++
		} else {
			failed++
		}

		testCount++
	}

	total := passed + failed
	successRate := 0.0
	if total > 0 {
		successRate = float64(passed) / float64(total)
	}

	return &TestResult{
		SuccessRate: successRate,
		Passed:      passed,
		Failed:      failed,
		TestSamples: testCount,
	}
}

// ProposedPattern represents a pattern proposed by the learning worker
type ProposedPattern struct {
	ID           int
	Name         string
	Regex        string
	Category     string
	Occurrences  int
	Examples     []string
	Action       string
	TargetWorker string
	Metadata     map[string]interface{}
	TestResult   *TestResult
}

// TestResult represents the result of testing a pattern
type TestResult struct {
	SuccessRate float64
	Passed      int
	Failed      int
	TestSamples int
	Error       string
}

// LearningReport summarizes the learning worker's analysis
type LearningReport struct {
	StartTime        time.Time
	EndTime          time.Time
	Duration         time.Duration
	ChunksAnalyzed   int
	ProposedPatterns []ProposedPattern
}

// Summary returns a formatted summary of the report
func (lr *LearningReport) Summary() string {
	summary := fmt.Sprintf("=== Learning Worker Report ===\n")
	summary += fmt.Sprintf("Duration: %v\n", lr.Duration)
	summary += fmt.Sprintf("Chunks Analyzed: %d\n", lr.ChunksAnalyzed)
	summary += fmt.Sprintf("Patterns Proposed: %d\n\n", len(lr.ProposedPatterns))

	if len(lr.ProposedPatterns) > 0 {
		summary += "New Patterns:\n"
		for _, pattern := range lr.ProposedPatterns {
			summary += fmt.Sprintf("  ✓ %s (category: %s, success: %.2f%%)\n",
				pattern.Name, pattern.Category, pattern.TestResult.SuccessRate*100)
			summary += fmt.Sprintf("    Regex: %s\n", pattern.Regex)
			summary += fmt.Sprintf("    Action: %s → %s\n", pattern.Action, pattern.TargetWorker)
			if len(pattern.Examples) > 0 {
				summary += fmt.Sprintf("    Example: %s\n", truncate(pattern.Examples[0], 60))
			}
			summary += "\n"
		}
	}

	return summary
}
