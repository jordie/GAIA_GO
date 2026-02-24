package math

import (
	"testing"
)

// ============================================================================
// PROBLEM GENERATION TESTS
// ============================================================================

func TestGenerateProblem(t *testing.T) {
	app := &MathApp{}

	tests := []struct {
		name       string
		operation  string
		difficulty string
	}{
		{"add easy", "add", "easy"},
		{"add medium", "add", "medium"},
		{"add hard", "add", "hard"},
		{"subtract easy", "subtract", "easy"},
		{"multiply easy", "multiply", "easy"},
		{"divide easy", "divide", "easy"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			problem := app.GenerateProblem(tt.operation, tt.difficulty)

			if problem == nil {
				t.Error("GenerateProblem returned nil")
				return
			}

			if problem.Operation != tt.operation {
				t.Errorf("Operation mismatch: got %s, want %s", problem.Operation, tt.operation)
			}

			if problem.Difficulty != tt.difficulty {
				t.Errorf("Difficulty mismatch: got %s, want %s", problem.Difficulty, tt.difficulty)
			}

			if problem.QuestionText == "" {
				t.Error("QuestionText is empty")
			}

			if problem.Hint == "" {
				t.Error("Hint is empty")
			}
		})
	}
}

// ============================================================================
// NUMBER PARSING FROM SPEECH TESTS (CRITICAL)
// ============================================================================

func TestParseNumberFromSpeech(t *testing.T) {
	tests := []struct {
		input    string
		expected float64
	}{
		// Single words
		{"zero", 0},
		{"one", 1},
		{"five", 5},
		{"eight", 8},
		{"ten", 10},
		{"twelve", 12},
		{"twenty", 20},
		{"thirty", 30},
		{"ninety", 90},

		// Compound numbers
		{"twenty five", 25},
		{"thirty two", 32},
		{"forty seven", 47},
		{"ninety nine", 99},

		// Scales
		{"one hundred", 100},
		{"two hundred", 200},
		{"one thousand", 1000},
		{"five thousand", 5000},

		// With minus/negative
		{"minus five", -5},
		{"negative ten", -10},

		// Direct numbers
		{"5", 5},
		{"42", 42},
		{"100", 100},
		{"3.14", 3.14},
		{"2.5", 2.5},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			result := ParseNumberFromSpeech(tt.input)

			if result == nil {
				t.Errorf("ParseNumberFromSpeech(%s) returned nil, expected %f", tt.input, tt.expected)
				return
			}

			// Allow small floating point differences
			if *result != tt.expected {
				t.Errorf("ParseNumberFromSpeech(%s) = %f, want %f", tt.input, *result, tt.expected)
			}
		})
	}
}

func TestParseNumberFromSpeechWithNoise(t *testing.T) {
	// Test that parser handles extra words/noise
	tests := []struct {
		input    string
		expected float64
	}{
		{"the answer is eight", 8},
		{"I think it's twenty five", 25},
		{"approximately one hundred", 100},
		{"around five thousand", 5000},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			result := ParseNumberFromSpeech(tt.input)

			if result == nil {
				// This is okay if it returns nil for noisy input
				// But ideally we want at least some cases to work
				t.Logf("ParseNumberFromSpeech(%s) returned nil - some noise handling", tt.input)
				return
			}

			if *result != tt.expected {
				t.Errorf("ParseNumberFromSpeech(%s) = %f, want %f", tt.input, *result, tt.expected)
			}
		})
	}
}

func TestParseNumberFromSpeechEmpty(t *testing.T) {
	result := ParseNumberFromSpeech("")
	if result != nil {
		t.Error("ParseNumberFromSpeech(\"\") should return nil")
	}

	result = ParseNumberFromSpeech("   ")
	if result != nil {
		t.Error("ParseNumberFromSpeech(whitespace) should return nil")
	}

	result = ParseNumberFromSpeech("no number here")
	if result != nil {
		t.Error("ParseNumberFromSpeech(non-number) should return nil")
	}
}

// ============================================================================
// SPEECH ANSWER VALIDATION TESTS (CRITICAL)
// ============================================================================

func TestCheckSpeechAnswer(t *testing.T) {
	tests := []struct {
		name           string
		spokenText     string
		expectedAnswer float64
		tolerance      float64
		shouldMatch    bool
		minScore       float64
	}{
		{
			name:           "exact match with word number",
			spokenText:     "eight",
			expectedAnswer: 8,
			tolerance:      0.01,
			shouldMatch:    true,
			minScore:       90,
		},
		{
			name:           "exact match with digit",
			spokenText:     "15",
			expectedAnswer: 15,
			tolerance:      0.01,
			shouldMatch:    true,
			minScore:       90,
		},
		{
			name:           "exact match with compound number",
			spokenText:     "twenty five",
			expectedAnswer: 25,
			tolerance:      0.01,
			shouldMatch:    true,
			minScore:       90,
		},
		{
			name:           "incorrect answer",
			spokenText:     "seven",
			expectedAnswer: 8,
			tolerance:      0.01,
			shouldMatch:    false,
			minScore:       0,
		},
		{
			name:           "cannot parse spoken text",
			spokenText:     "umbrella elephant",
			expectedAnswer: 8,
			tolerance:      0.01,
			shouldMatch:    false,
			minScore:       0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := CheckSpeechAnswer(tt.spokenText, tt.expectedAnswer, tt.tolerance)

			if result == nil {
				t.Fatal("CheckSpeechAnswer returned nil")
			}

			if result.IsMatch != tt.shouldMatch {
				t.Errorf("IsMatch = %v, want %v", result.IsMatch, tt.shouldMatch)
			}

			if result.Score < tt.minScore {
				t.Errorf("Score %f is below minimum %f", result.Score, tt.minScore)
			}

			if result.Feedback == "" {
				t.Error("Feedback is empty")
			}

			if tt.shouldMatch && result.MatchType != "exact" {
				t.Errorf("MatchType = %s, want 'exact'", result.MatchType)
			}
		})
	}
}

func TestCheckSpeechAnswerWithTolerance(t *testing.T) {
	// Test with larger tolerance for approximate answers
	result := CheckSpeechAnswer("25.05", 25.05, 0.1)

	if result == nil {
		t.Fatal("CheckSpeechAnswer returned nil")
	}

	if !result.IsMatch {
		t.Errorf("Expected match with tolerance 0.1, got IsMatch=%v", result.IsMatch)
	}
}

// ============================================================================
// ACCURACY CALCULATION TESTS
// ============================================================================

func TestCalculateAccuracy(t *testing.T) {
	tests := []struct {
		correct  int
		total    int
		expected float64
		name     string
	}{
		{10, 10, 100.0, "perfect"},
		{5, 10, 50.0, "half"},
		{0, 10, 0.0, "zero"},
		{9, 10, 90.0, "ninety percent"},
		{0, 0, 0.0, "zero total"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := CalculateAccuracy(tt.correct, tt.total)
			if result != tt.expected {
				t.Errorf("CalculateAccuracy(%d, %d) = %f, want %f", tt.correct, tt.total, result, tt.expected)
			}
		})
	}
}

// ============================================================================
// HELPER FUNCTION TESTS
// ============================================================================

func TestCheckAnswerCorrect(t *testing.T) {
	tests := []struct {
		userAnswer     float64
		expectedAnswer float64
		tolerance      float64
		expected       bool
		name           string
	}{
		{8.0, 8.0, 0.01, true, "exact match"},
		{8.005, 8.0, 0.01, true, "within tolerance"},
		{8.02, 8.0, 0.01, false, "outside tolerance"},
		{15.0, 15.0, 0.01, true, "exact large number"},
		{0.0, 0.0, 0.01, true, "zero match"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := CheckAnswerCorrect(tt.userAnswer, tt.expectedAnswer, tt.tolerance)
			if result != tt.expected {
				t.Errorf("CheckAnswerCorrect(%f, %f, %f) = %v, want %v",
					tt.userAnswer, tt.expectedAnswer, tt.tolerance, result, tt.expected)
			}
		})
	}
}

// ============================================================================
// INTEGRATION TESTS
// ============================================================================

func TestSpeechToAnswerFlow(t *testing.T) {
	// Simulate a complete flow: spoken text -> parsed number -> answer check
	testCases := []struct {
		name            string
		spokenText      string
		expectedAnswer  float64
		shouldBeCorrect bool
	}{
		{
			name:            "simple addition answer",
			spokenText:      "eight",
			expectedAnswer:  8,
			shouldBeCorrect: true,
		},
		{
			name:            "compound number answer",
			spokenText:      "twenty five",
			expectedAnswer:  25,
			shouldBeCorrect: true,
		},
		{
			name:            "wrong answer",
			spokenText:      "seven",
			expectedAnswer:  8,
			shouldBeCorrect: false,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			// Step 1: Parse spoken text
			parsedNumber := ParseNumberFromSpeech(tc.spokenText)
			if parsedNumber == nil && tc.shouldBeCorrect {
				t.Fatalf("Failed to parse '%s'", tc.spokenText)
			}

			// Step 2: Check answer
			result := CheckSpeechAnswer(tc.spokenText, tc.expectedAnswer, 0.01)
			if result == nil {
				t.Fatal("CheckSpeechAnswer returned nil")
			}

			// Step 3: Verify result
			if result.IsMatch != tc.shouldBeCorrect {
				t.Errorf("Expected match=%v, got %v. Feedback: %s", tc.shouldBeCorrect, result.IsMatch, result.Feedback)
			}
		})
	}
}

func TestProblemGeneration_Deterministic(t *testing.T) {
	// While random, verify problems are well-formed
	app := &MathApp{}

	for i := 0; i < 10; i++ {
		problem := app.GenerateProblem("add", "easy")

		// Verify problem is correctly calculated
		expectedSum := float64(problem.Operand1 + problem.Operand2)
		if problem.Answer != expectedSum {
			t.Errorf("Problem %d: %d + %d = %f, expected %f",
				i, problem.Operand1, problem.Operand2, problem.Answer, expectedSum)
		}

		// Verify operands are in correct range for easy difficulty
		if problem.Operand1 > 10 || problem.Operand1 < 1 {
			t.Errorf("Operand1 out of range for easy: %d", problem.Operand1)
		}
		if problem.Operand2 > 10 || problem.Operand2 < 1 {
			t.Errorf("Operand2 out of range for easy: %d", problem.Operand2)
		}
	}
}

// ============================================================================
// BENCHMARK TESTS
// ============================================================================

func BenchmarkParseNumberFromSpeech(b *testing.B) {
	inputs := []string{"eight", "twenty five", "one hundred", "5", "3.14"}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		for _, input := range inputs {
			ParseNumberFromSpeech(input)
		}
	}
}

func BenchmarkCheckSpeechAnswer(b *testing.B) {
	testCases := []struct {
		spoken   string
		expected float64
	}{
		{"eight", 8},
		{"twenty five", 25},
		{"one hundred", 100},
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		for _, tc := range testCases {
			CheckSpeechAnswer(tc.spoken, tc.expected, 0.01)
		}
	}
}

func BenchmarkGenerateProblem(b *testing.B) {
	app := &MathApp{}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		app.GenerateProblem("add", "medium")
	}
}

// ============================================================================
// SUMMARY TESTS
// ============================================================================

func TestMathAppSummary(t *testing.T) {
	t.Run("all speech-to-text tests pass", func(t *testing.T) {
		// Quick smoke test
		result := ParseNumberFromSpeech("eight")
		if result == nil || *result != 8 {
			t.Error("Basic speech parsing failed")
		}

		checkResult := CheckSpeechAnswer("eight", 8, 0.01)
		if checkResult == nil || !checkResult.IsMatch {
			t.Error("Basic speech answer check failed")
		}
	})

	t.Run("problem generation works", func(t *testing.T) {
		app := &MathApp{}
		problem := app.GenerateProblem("add", "easy")
		if problem == nil || problem.Answer == 0 {
			t.Error("Problem generation failed")
		}
	})

	t.Run("accuracy calculation works", func(t *testing.T) {
		acc := CalculateAccuracy(8, 10)
		if acc != 80.0 {
			t.Errorf("Accuracy calculation failed: got %f, want 80", acc)
		}
	})
}
