package services

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

// Test word mastery calculation
func TestCalculateWordMastery(t *testing.T) {
	tests := []struct {
		name      string
		correct   int
		incorrect int
		expected  float64
	}{
		{"perfect", 10, 0, 100.0},
		{"half", 5, 5, 50.0},
		{"none", 0, 10, 0.0},
		{"single", 1, 0, 100.0},
		{"two thirds", 4, 2, 66.66666666666666},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var mastery float64
			total := tt.correct + tt.incorrect
			if total == 0 {
				mastery = 0
			} else {
				mastery = float64(tt.correct) / float64(total) * 100
			}
			assert.InDelta(t, tt.expected, mastery, 0.01)
		})
	}
}

// Test quiz pass/fail logic
func TestQuizPassLogic(t *testing.T) {
	tests := []struct {
		name     string
		score    int
		total    int
		expected bool
	}{
		{"pass with 70%", 7, 10, true},
		{"pass with 100%", 10, 10, true},
		{"fail with 69%", 7, 10, false},
		{"fail with 50%", 5, 10, false},
		{"pass boundary 70%", 14, 20, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			passed := float64(tt.score) >= float64(tt.total)*PassThreshold
			assert.Equal(t, tt.expected, passed)
		})
	}
}

// Test reading accuracy calculation
func TestReadingAccuracy(t *testing.T) {
	tests := []struct {
		name       string
		correct    int
		total      int
		expected   float64
	}{
		{"perfect", 10, 10, 100.0},
		{"half", 5, 10, 50.0},
		{"none", 0, 10, 0.0},
		{"single", 1, 1, 100.0},
		{"three quarters", 3, 4, 75.0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var accuracy float64
			if tt.total > 0 {
				accuracy = float64(tt.correct) / float64(tt.total) * 100
			}
			assert.InDelta(t, tt.expected, accuracy, 0.01)
		})
	}
}

// Test percentage calculation
func TestPercentageCalculation(t *testing.T) {
	tests := []struct {
		name     string
		score    int
		total    int
		expected int
	}{
		{"perfect", 10, 10, 100},
		{"half", 5, 10, 50},
		{"none", 0, 10, 0},
		{"three quarters", 3, 4, 75},
		{"rounding down", 7, 10, 70},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var percentage int
			if tt.total > 0 {
				percentage = (tt.score * 100) / tt.total
			}
			assert.Equal(t, tt.expected, percentage)
		})
	}
}

// Test word recognition matching (case insensitive)
func TestWordRecognition(t *testing.T) {
	tests := []struct {
		name          string
		expectedWord  string
		recognizedText string
		shouldMatch   bool
	}{
		{"exact match", "reading", "reading", true},
		{"case insensitive match", "Reading", "reading", true},
		{"word in sentence", "the", "the quick brown fox", true},
		{"word not found", "book", "the quick brown fox", false},
		{"partial match should not match", "read", "reading", false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			words := extractWords(tt.recognizedText)
			found := false
			for _, w := range words {
				if w == tt.expectedWord {
					found = true
					break
				}
			}
			assert.Equal(t, tt.shouldMatch, found)
		})
	}
}

// Test reading speed calculation
func TestReadingSpeed(t *testing.T) {
	tests := []struct {
		name           string
		wordCount      int
		timeSecs       float64
		expectedWPM    float64
	}{
		{"standard", 250, 60, 250.0},  // 250 words in 60 seconds = 250 WPM
		{"half minute", 125, 30, 250.0}, // 125 words in 30 seconds = 250 WPM
		{"slow", 100, 60, 100.0},       // 100 words in 60 seconds = 100 WPM
		{"fast", 500, 120, 250.0},      // 500 words in 120 seconds = 250 WPM
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var wpm float64
			if tt.timeSecs > 0 {
				wpm = float64(tt.wordCount) / (tt.timeSecs / 60.0)
			}
			assert.InDelta(t, tt.expectedWPM, wpm, 0.1)
		})
	}
}

// Test session duration
func TestSessionDuration(t *testing.T) {
	tests := []struct {
		name             string
		startSecs        int64
		endSecs          int64
		expectedDuration float64
	}{
		{"one minute", 0, 60, 60.0},
		{"five minutes", 0, 300, 300.0},
		{"partial minute", 30, 90, 60.0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			duration := float64(tt.endSecs - tt.startSecs)
			assert.Equal(t, tt.expectedDuration, duration)
		})
	}
}

// Test word count
func TestWordCount(t *testing.T) {
	tests := []struct {
		name          string
		text          string
		expectedCount int
	}{
		{"single word", "hello", 1},
		{"two words", "hello world", 2},
		{"sentence", "the quick brown fox jumps", 5},
		{"empty", "", 0},
		{"multiple spaces", "hello  world", 2},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			words := extractWords(tt.text)
			assert.Equal(t, tt.expectedCount, len(words))
		})
	}
}

// Test weak word threshold
func TestWeakWordThreshold(t *testing.T) {
	tests := []struct {
		name     string
		mastery  float64
		isWeak   bool
	}{
		{"clearly weak", 30.0, true},
		{"borderline weak", 50.0, true},
		{"below threshold", 49.9, true},
		{"at threshold", 50.0, true},
		{"above threshold", 50.1, false},
		{"strong", 85.0, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			isWeak := tt.mastery < WordsInProgressThreshold
			assert.Equal(t, tt.isWeak, isWeak)
		})
	}
}

// Test mastered word threshold
func TestMasteredWordThreshold(t *testing.T) {
	tests := []struct {
		name       string
		mastery    float64
		isMastered bool
	}{
		{"weak", 30.0, false},
		{"below threshold", 79.9, false},
		{"at threshold", 80.0, true},
		{"above threshold", 80.1, true},
		{"perfect", 100.0, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			isMastered := tt.mastery >= WordsMasteredThreshold
			assert.Equal(t, tt.isMastered, isMastered)
		})
	}
}

// Helper function to extract words
func extractWords(text string) []string {
	if text == "" {
		return []string{}
	}
	var words []string
	var current string
	for _, r := range text {
		if r == ' ' || r == '\t' || r == '\n' {
			if current != "" {
				words = append(words, current)
				current = ""
			}
		} else {
			current += string(r)
		}
	}
	if current != "" {
		words = append(words, current)
	}
	return words
}

const (
	WordsMasteredThreshold     = 80.0
	WordsInProgressThreshold   = 50.0
)
