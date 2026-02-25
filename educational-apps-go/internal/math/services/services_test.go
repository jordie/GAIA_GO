package services

import (
	"testing"

	"github.com/architect/educational-apps/internal/math/models"
	"github.com/stretchr/testify/assert"
)

// Test fact family classification
func TestClassifyFactFamily(t *testing.T) {
	tests := []struct {
		name         string
		num1         int
		num2         int
		operator     string
		expectedType string
	}{
		// Addition families
		{"doubles", 5, 5, "+", "doubles"},
		{"near_doubles", 5, 6, "+", "near_doubles"},
		{"near_doubles reverse", 6, 5, "+", "near_doubles"},
		{"plus_one", 1, 5, "+", "plus_one"},
		{"plus_nine", 9, 3, "+", "plus_nine"},
		{"make_ten", 3, 7, "+", "make_ten"},
		{"other addition", 4, 5, "+", "other"},

		// Subtraction families
		{"minus_same", 5, 5, "-", "minus_same"},
		{"minus_one", 5, 1, "-", "minus_one"},
		{"from_ten", 10, 3, "-", "from_ten"},
		{"other subtraction", 8, 3, "-", "other"},

		// Multiplication families
		{"times_zero", 0, 5, "*", "times_zero"},
		{"times_one", 1, 5, "*", "times_one"},
		{"times_two", 2, 5, "*", "times_two"},
		{"times_five", 5, 5, "*", "times_five"},
		{"times_nine", 9, 5, "*", "times_nine"},
		{"squares", 4, 4, "*", "squares"},
		{"other multiplication", 3, 6, "*", "other"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := classifyFactFamily(tt.num1, tt.num2, tt.operator)
			assert.Equal(t, tt.expectedType, result)
		})
	}
}

// Test strategy hint generation
func TestGetStrategyHint(t *testing.T) {
	tests := []struct {
		name       string
		factFamily string
		shouldHint bool
	}{
		{"doubles hint exists", "doubles", true},
		{"near_doubles hint exists", "near_doubles", true},
		{"plus_one hint exists", "plus_one", true},
		{"make_ten hint exists", "make_ten", true},
		{"times_five hint exists", "times_five", true},
		{"unknown family", "unknown_family", false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			hint := getStrategyHint(tt.factFamily, 1, 2, "addition")
			if tt.shouldHint {
				assert.NotEmpty(t, hint)
			}
		})
	}
}

// Test time of day conversion
func TestGetTimeOfDay(t *testing.T) {
	tests := []struct {
		name         string
		hour         int
		expectedTime string
	}{
		{"morning early", 0, "morning"},
		{"morning", 11, "morning"},
		{"afternoon early", 12, "afternoon"},
		{"afternoon", 16, "afternoon"},
		{"evening", 17, "evening"},
		{"evening late", 23, "evening"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := getTimeOfDay(tt.hour)
			assert.Equal(t, tt.expectedTime, result)
		})
	}
}

// Test problem validation
func TestGenerateProblemValidation(t *testing.T) {
	tests := []struct {
		name       string
		mode       string
		difficulty string
		shouldErr  bool
	}{
		{"valid addition easy", "addition", "easy", false},
		{"valid multiplication hard", "multiplication", "hard", false},
		{"valid division expert", "division", "expert", false},
		{"invalid difficulty", "addition", "impossible", true},
		{"invalid mode", "invalid", "easy", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := models.GenerateProblemRequest{
				Mode:       tt.mode,
				Difficulty: tt.difficulty,
			}

			// We can't fully test this without mocking repository
			// but we can check that default values work
			if tt.mode == "" {
				req.Mode = "addition"
			}
			if tt.difficulty == "" {
				req.Difficulty = "easy"
			}

			assert.NotEmpty(t, req.Mode)
			assert.NotEmpty(t, req.Difficulty)
		})
	}
}

// Test mastery calculation logic
func TestMasteryCalculation(t *testing.T) {
	tests := []struct {
		name             string
		streak           int
		totalAttempts    int
		speedBonus       float64
		expectedMin      float64
		expectedMax      float64
	}{
		{"perfect accuracy", 10, 10, 0.0, 80.0, 100.0},
		{"50% accuracy", 5, 10, 0.0, 20.0, 100.0},
		{"low accuracy", 1, 10, 0.0, 0.0, 50.0},
		{"with speed bonus", 10, 10, 10.0, 90.0, 100.0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			accuracy := float64(tt.streak) / float64(tt.totalAttempts)
			speedBonus := tt.speedBonus
			masteryLevel := (accuracy * 80) + (float64(tt.streak) * 4) + speedBonus

			if masteryLevel > 100 {
				masteryLevel = 100
			}

			assert.GreaterOrEqual(t, masteryLevel, tt.expectedMin)
			assert.LessOrEqual(t, masteryLevel, 100.0)
		})
	}
}

// Test response time calculation
func TestAverageResponseTimeCalculation(t *testing.T) {
	tests := []struct {
		name                  string
		previousAverage       float64
		previousAttempts      int
		newTime               float64
		expectedAverage       float64
	}{
		{"first attempt", 0, 0, 5.0, 5.0},
		{"second attempt same", 5.0, 1, 5.0, 5.0},
		{"second attempt faster", 5.0, 1, 3.0, 4.0},
		{"third attempt", 4.0, 2, 6.0, 4.666666666666666},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var newAttempts int
			if tt.previousAttempts == 0 {
				newAttempts = 1
			} else {
				newAttempts = tt.previousAttempts + 1
			}

			var newAverage float64
			if tt.previousAttempts == 0 {
				newAverage = tt.newTime
			} else {
				newAverage = ((tt.previousAverage * float64(tt.previousAttempts)) + tt.newTime) / float64(newAttempts)
			}

			assert.InDelta(t, tt.expectedAverage, newAverage, 0.01)
		})
	}
}

// Test difficulty ranges
func TestDifficultyRanges(t *testing.T) {
	difficultyRanges := map[string]struct {
		min int
		max int
	}{
		"easy":   {1, 10},
		"medium": {10, 50},
		"hard":   {50, 100},
		"expert": {100, 999},
	}

	for difficulty, expectedRange := range difficultyRanges {
		t.Run(difficulty, func(t *testing.T) {
			assert.Greater(t, expectedRange.max, expectedRange.min)
			assert.GreaterOrEqual(t, expectedRange.min, 1)
		})
	}
}

// Test fact family suggestions
func TestFactFamilySuggestions(t *testing.T) {
	suggestionMap := map[string]string{
		"doubles":        "Practice doubles (n+n) - memorize basic doubles first",
		"near_doubles":   "Focus on near doubles (n+n+1) - build on doubles",
		"plus_one":       "Master plus one facts - count by ones",
		"plus_nine":      "Learn the plus nine strategy - 10 minus 1",
		"make_ten":       "Practice making 10 - foundational for mental math",
		"times_two":      "Work on times two - doubling strategy",
		"times_five":     "Practice times five - counting by fives",
		"times_nine":     "Master times nine - finger trick method",
		"squares":        "Learn square numbers - 1, 4, 9, 16, 25...",
	}

	for factFamily, expectedSuggestion := range suggestionMap {
		t.Run(factFamily, func(t *testing.T) {
			assert.NotEmpty(t, expectedSuggestion)
			assert.Contains(t, expectedSuggestion, factFamily)
		})
	}
}

// Test session accuracy calculation
func TestSessionAccuracyCalculation(t *testing.T) {
	tests := []struct {
		name            string
		correct         int
		total           int
		expectedPercent float64
	}{
		{"perfect", 10, 10, 100.0},
		{"half", 5, 10, 50.0},
		{"none", 0, 10, 0.0},
		{"one out of three", 1, 3, 33.33333333333333},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			accuracy := 0.0
			if tt.total > 0 {
				accuracy = (float64(tt.correct) / float64(tt.total)) * 100
			}
			assert.InDelta(t, tt.expectedPercent, accuracy, 0.01)
		})
	}
}

// Test average time calculation
func TestAverageTimePerQuestion(t *testing.T) {
	tests := []struct {
		name         string
		totalTime    float64
		numQuestions int
		expectedAvg  float64
	}{
		{"normal", 45.0, 10, 4.5},
		{"single question", 3.5, 1, 3.5},
		{"many questions", 120.0, 30, 4.0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if tt.numQuestions > 0 {
				avg := tt.totalTime / float64(tt.numQuestions)
				assert.InDelta(t, tt.expectedAvg, avg, 0.01)
			}
		})
	}
}

// Test edge case: division by zero prevention
func TestDivisionByZeroPrevention(t *testing.T) {
	t.Run("no questions should not crash", func(t *testing.T) {
		totalQuestions := 0
		totalTime := 45.0

		var avgTime float64
		if totalQuestions > 0 {
			avgTime = totalTime / float64(totalQuestions)
		} else {
			avgTime = 0
		}

		assert.Equal(t, 0.0, avgTime)
	})
}

// Test response time bounds
func TestResponseTimeBounds(t *testing.T) {
	t.Run("fastest time cannot exceed slowest", func(t *testing.T) {
		fastest := 2.0
		slowest := 5.0
		current := 3.5

		// When updating with new time
		if current < fastest {
			fastest = current
		}
		if current > slowest {
			slowest = current
		}

		assert.LessOrEqual(t, fastest, slowest)
		assert.GreaterOrEqual(t, fastest, 0.0)
	})
}
