package stream

import (
	"strings"
	"testing"
)

// Sample Codex output for testing
const sampleCodexOutput = `OpenAI Codex v0.93.0 (research preview)
--------
workdir: /Users/test/project
model: gpt-5.2-codex
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR]
reasoning effort: xhigh
reasoning summaries: auto
session id: 019c4185-215a-7972-bc9f-b8da4a842551
--------
user
What is 2+2?
mcp startup: no servers
codex
4
tokens used
1,377
`

const sampleCodeBlock = `Here's a Python function:

` + "```python" + `
def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
` + "```" + `

Done!`

const sampleErrors = `Error: File not found
Warning: Deprecated API usage
at function main.go:42:10
`

func TestExtractorBasic(t *testing.T) {
	extractor := NewExtractor()

	lines := strings.Split(sampleCodexOutput, "\n")
	for _, line := range lines {
		extractor.Extract(line)
	}

	stats := extractor.GetStats()
	totalMatches := stats["total_matches"].(int)

	if totalMatches == 0 {
		t.Errorf("Expected matches, got 0")
	}

	t.Logf("Extracted %d matches from %d lines", totalMatches, len(lines))
}

func TestExtractSession(t *testing.T) {
	extractor := NewExtractor()

	testCases := []struct {
		line    string
		pattern string
		want    string
	}{
		{"workdir: /Users/test/project", "workdir", "/Users/test/project"},
		{"model: gpt-5.2-codex", "model", "gpt-5.2-codex"},
		{"provider: openai", "provider", "openai"},
		{"session id: 019c4185-215a-7972-bc9f-b8da4a842551", "session_id", "019c4185-215a-7972-bc9f-b8da4a842551"},
	}

	for _, tc := range testCases {
		matches := extractor.Extract(tc.line)
		if len(matches) == 0 {
			t.Errorf("Expected match for %s, got none", tc.line)
			continue
		}

		found := false
		for _, m := range matches {
			if m.Pattern == tc.pattern && m.Value == tc.want {
				found = true
				break
			}
		}

		if !found {
			t.Errorf("Expected pattern %s with value %s, matches: %v", tc.pattern, tc.want, matches)
		}
	}
}

func TestExtractMetrics(t *testing.T) {
	extractor := NewExtractor()

	testCases := []struct {
		line    string
		pattern string
		want    string
	}{
		{"tokens used\n1,377", "tokens_used", "1377"},
		{"tokens used 2500", "tokens_used", "2500"},
		{"Time: 5.2s", "time_elapsed", "5.2"},
		{"Memory: 128MB", "memory_usage", "128"},
	}

	for _, tc := range testCases {
		matches := extractor.Extract(tc.line)
		found := false
		for _, m := range matches {
			if m.Pattern == tc.pattern && m.Value == tc.want {
				found = true
				t.Logf("✓ Matched %s: %s", tc.pattern, m.Value)
				break
			}
		}

		if !found {
			t.Logf("Pattern %s not matched in line: %s (got %d matches)", tc.pattern, tc.line, len(matches))
		}
	}
}

func TestExtractCodeBlock(t *testing.T) {
	extractor := NewExtractor()

	lines := strings.Split(sampleCodeBlock, "\n")
	for _, line := range lines {
		extractor.Extract(line)
	}

	codeBlocks := extractor.GetMatchesByType(PatternTypeCodeBlock)
	if len(codeBlocks) == 0 {
		t.Errorf("Expected code block matches, got none")
	}

	// Should have start and end markers
	var hasStart, hasEnd bool
	for _, m := range codeBlocks {
		if m.Pattern == "code_block_start" {
			hasStart = true
			if lang, ok := m.Metadata["language"].(string); ok && lang != "python" {
				t.Errorf("Expected language python, got %s", lang)
			}
		}
		if m.Pattern == "code_block_end" {
			hasEnd = true
			if content, ok := m.Metadata["content"].(string); ok {
				if !strings.Contains(content, "fibonacci") {
					t.Errorf("Expected code content to contain 'fibonacci'")
				}
			}
		}
	}

	if !hasStart {
		t.Errorf("Missing code_block_start marker")
	}
	if !hasEnd {
		t.Errorf("Missing code_block_end marker")
	}
}

func TestExtractErrors(t *testing.T) {
	extractor := NewExtractor()

	lines := strings.Split(sampleErrors, "\n")
	for _, line := range lines {
		extractor.Extract(line)
	}

	errors := extractor.GetMatchesByType(PatternTypeError)
	if len(errors) == 0 {
		t.Errorf("Expected error matches, got none")
	}

	// Should have error, warning, and stack trace
	patterns := make(map[string]bool)
	for _, m := range errors {
		patterns[m.Pattern] = true
		t.Logf("Found error: %s - %s", m.Pattern, m.Value)
	}

	if !patterns["error"] {
		t.Errorf("Missing error pattern")
	}
	if !patterns["warning"] {
		t.Errorf("Missing warning pattern")
	}
	if !patterns["stack_trace"] {
		t.Errorf("Missing stack_trace pattern")
	}
}

func TestExtractInteraction(t *testing.T) {
	extractor := NewExtractor()

	testCases := []struct {
		line    string
		pattern string
	}{
		{"user", "user_prompt"},
		{"codex", "codex_response"},
		{"mcp startup: no servers", "mcp_startup"},
	}

	for _, tc := range testCases {
		matches := extractor.Extract(tc.line)
		found := false
		for _, m := range matches {
			if m.Pattern == tc.pattern {
				found = true
				break
			}
		}

		if !found {
			t.Errorf("Expected pattern %s for line: %s", tc.pattern, tc.line)
		}
	}
}

func TestExtractorStats(t *testing.T) {
	extractor := NewExtractor()

	// Process full sample
	lines := strings.Split(sampleCodexOutput, "\n")
	for _, line := range lines {
		extractor.Extract(line)
	}

	stats := extractor.GetStats()

	if totalLines, ok := stats["total_lines"].(int); !ok || totalLines != len(lines) {
		t.Errorf("Expected %d total lines, got %v", len(lines), totalLines)
	}

	if totalMatches, ok := stats["total_matches"].(int); !ok || totalMatches == 0 {
		t.Errorf("Expected non-zero matches, got %v", totalMatches)
	}

	if matchesByType, ok := stats["matches_by_type"].(map[string]int); ok {
		t.Logf("Matches by type:")
		for typ, count := range matchesByType {
			t.Logf("  %s: %d", typ, count)
		}
	}
}

func TestExtractorClear(t *testing.T) {
	extractor := NewExtractor()

	// Extract some data
	extractor.Extract("workdir: /test")
	extractor.Extract("model: test-model")

	stats := extractor.GetStats()
	if stats["total_matches"].(int) == 0 {
		t.Errorf("Expected matches before clear")
	}

	// Clear
	extractor.Clear()

	stats = extractor.GetStats()
	if stats["total_matches"].(int) != 0 {
		t.Errorf("Expected 0 matches after clear, got %d", stats["total_matches"].(int))
	}
	if stats["total_lines"].(int) != 0 {
		t.Errorf("Expected 0 lines after clear, got %d", stats["total_lines"].(int))
	}
}

func BenchmarkExtractor(b *testing.B) {
	lines := strings.Split(sampleCodexOutput, "\n")

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		extractor := NewExtractor()
		for _, line := range lines {
			extractor.Extract(line)
		}
	}
}

func BenchmarkExtractorCodeBlock(b *testing.B) {
	lines := strings.Split(sampleCodeBlock, "\n")

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		extractor := NewExtractor()
		for _, line := range lines {
			extractor.Extract(line)
		}
	}
}
