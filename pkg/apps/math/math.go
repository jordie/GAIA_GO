package math

import (
	"database/sql"
	"fmt"
	"math"
	"math/rand"
	"regexp"
	"strings"
)

// MathApp manages the math application
type MathApp struct {
	db *sql.DB
}

// NewMathApp creates a new math app instance
func NewMathApp(db *sql.DB) *MathApp {
	return &MathApp{
		db: db,
	}
}

// ============================================================================
// PROBLEM GENERATION
// ============================================================================

// Problem represents a math problem
type Problem struct {
	ID            string  `json:"id"`
	Operation     string  `json:"operation"`  // add, subtract, multiply, divide
	Difficulty    string  `json:"difficulty"` // easy, medium, hard
	Operand1      int     `json:"operand1"`
	Operand2      int     `json:"operand2"`
	Answer        float64 `json:"answer"`
	QuestionText  string  `json:"question_text"`
	AnswerType    string  `json:"answer_type"` // int, float
	TimeLimit     int     `json:"time_limit"`  // seconds
	HintAvailable bool    `json:"hint_available"`
	Hint          string  `json:"hint,omitempty"`
}

// GenerateProblem creates a new math problem based on difficulty and operation
func (app *MathApp) GenerateProblem(operation, difficulty string) *Problem {
	var operand1, operand2 int
	var answer float64

	// Set ranges based on difficulty
	switch difficulty {
	case "easy":
		operand1 = rand.Intn(10) + 1
		operand2 = rand.Intn(10) + 1
	case "medium":
		operand1 = rand.Intn(20) + 1
		operand2 = rand.Intn(20) + 1
	case "hard":
		operand1 = rand.Intn(50) + 1
		operand2 = rand.Intn(50) + 1
	default:
		operand1 = rand.Intn(10) + 1
		operand2 = rand.Intn(10) + 1
	}

	// Calculate answer based on operation
	switch operation {
	case "add":
		answer = float64(operand1 + operand2)
	case "subtract":
		answer = float64(operand1 - operand2)
	case "multiply":
		answer = float64(operand1 * operand2)
	case "divide":
		// Ensure no division by zero and clean division
		if operand2 == 0 {
			operand2 = 1
		}
		answer = float64(operand1) / float64(operand2)
	default:
		answer = float64(operand1 + operand2)
	}

	problem := &Problem{
		ID:            fmt.Sprintf("prob_%d", rand.Intn(1000000)),
		Operation:     operation,
		Difficulty:    difficulty,
		Operand1:      operand1,
		Operand2:      operand2,
		Answer:        answer,
		QuestionText:  app.generateQuestionText(operation, operand1, operand2),
		AnswerType:    "float",
		TimeLimit:     30,
		HintAvailable: true,
		Hint:          app.generateHint(operation, operand1, operand2),
	}

	return problem
}

// generateQuestionText creates human-readable question text
func (app *MathApp) generateQuestionText(operation string, op1, op2 int) string {
	switch operation {
	case "add":
		return fmt.Sprintf("What is %d + %d?", op1, op2)
	case "subtract":
		return fmt.Sprintf("What is %d - %d?", op1, op2)
	case "multiply":
		return fmt.Sprintf("What is %d × %d?", op1, op2)
	case "divide":
		return fmt.Sprintf("What is %d ÷ %d?", op1, op2)
	default:
		return fmt.Sprintf("What is %d + %d?", op1, op2)
	}
}

// generateHint creates a hint for the problem
func (app *MathApp) generateHint(operation string, op1, op2 int) string {
	switch operation {
	case "add":
		return fmt.Sprintf("Count up %d from %d", op2, op1)
	case "subtract":
		return fmt.Sprintf("Count down %d from %d", op2, op1)
	case "multiply":
		return fmt.Sprintf("Add %d groups of %d", op2, op1)
	case "divide":
		if op2 != 0 {
			return fmt.Sprintf("How many %ds fit into %d?", op2, op1)
		}
		return "Cannot divide by zero"
	default:
		return "No hint available"
	}
}

// ============================================================================
// SPEECH-TO-TEXT SUPPORT (Number Parsing from Speech)
// ============================================================================

// ParseNumberFromSpeech extracts a number from spoken text
// Examples: "eight" -> 8, "twenty five" -> 25, "one hundred" -> 100
func ParseNumberFromSpeech(text string) *float64 {
	text = strings.ToLower(strings.TrimSpace(text))

	// Try direct parsing if it looks like a number
	if result := tryDirectNumberParse(text); result != nil {
		return result
	}

	// Parse written-out number words
	if result := parseNumberWords(text); result != nil {
		return result
	}

	return nil
}

// Number word maps
var (
	ones = map[string]float64{
		"zero":      0,
		"one":       1,
		"two":       2,
		"three":     3,
		"four":      4,
		"five":      5,
		"six":       6,
		"seven":     7,
		"eight":     8,
		"nine":      9,
		"ten":       10,
		"eleven":    11,
		"twelve":    12,
		"thirteen":  13,
		"fourteen":  14,
		"fifteen":   15,
		"sixteen":   16,
		"seventeen": 17,
		"eighteen":  18,
		"nineteen":  19,
	}

	tens = map[string]float64{
		"twenty":  20,
		"thirty":  30,
		"forty":   40,
		"fifty":   50,
		"sixty":   60,
		"seventy": 70,
		"eighty":  80,
		"ninety":  90,
	}

	scales = map[string]float64{
		"hundred":  100,
		"thousand": 1000,
		"million":  1000000,
	}
)

func tryDirectNumberParse(text string) *float64 {
	// Extract just numbers and decimal points
	re := regexp.MustCompile(`[-+]?\d+\.?\d*`)
	match := re.FindString(text)
	if match != "" {
		var num float64
		_, err := fmt.Sscanf(match, "%f", &num)
		if err == nil {
			return &num
		}
	}
	return nil
}

func parseNumberWords(text string) *float64 {
	words := strings.FieldsFunc(text, func(r rune) bool {
		return r == ' ' || r == '-'
	})

	if len(words) == 0 {
		return nil
	}

	// Handle negative numbers
	negative := false
	if words[0] == "minus" || words[0] == "negative" {
		negative = true
		words = words[1:]
	}

	var result float64
	var currentValue float64
	foundNumber := false

	for _, word := range words {
		// Check ones
		if val, ok := ones[word]; ok {
			currentValue += val
			foundNumber = true
		} else if val, ok := tens[word]; ok {
			currentValue += val
			foundNumber = true
		} else if val, ok := scales[word]; ok {
			currentValue *= val
			result += currentValue
			currentValue = 0
		} else if word == "point" {
			// Handle decimal numbers (e.g., "point zero five" = 0.05)
			result += currentValue
			currentValue = 0.1 // next digit will be tenths place
		}
	}

	result += currentValue

	if negative {
		result = -result
	}

	if foundNumber {
		return &result
	}

	return nil
}

// ============================================================================
// SPEECH ANSWER VALIDATION
// ============================================================================

// SpeechMatchResult represents the result of checking a spoken answer
type SpeechMatchResult struct {
	IsMatch        bool    `json:"match"`
	SpokenNumber   float64 `json:"spoken_number"`
	ExpectedNumber float64 `json:"expected_number"`
	MatchType      string  `json:"match_type"`
	Feedback       string  `json:"feedback"`
	Score          float64 `json:"score"`
}

// CheckSpeechAnswer validates if a spoken answer matches the expected answer
func CheckSpeechAnswer(spokenText string, expectedAnswer float64, tolerance float64) *SpeechMatchResult {
	result := &SpeechMatchResult{
		ExpectedNumber: expectedAnswer,
		IsMatch:        false,
		Score:          0,
	}

	// Parse the spoken text to extract a number
	spokenNumber := ParseNumberFromSpeech(spokenText)
	if spokenNumber == nil {
		result.Feedback = fmt.Sprintf("I couldn't understand the number. I heard: '%s'. Please try again.", spokenText)
		return result
	}

	result.SpokenNumber = *spokenNumber

	// Check for exact match
	if math.Abs(*spokenNumber-expectedAnswer) < tolerance {
		result.IsMatch = true
		result.MatchType = "exact"
		result.Score = 100
		result.Feedback = fmt.Sprintf("Correct! %g is the right answer!", expectedAnswer)
		return result
	}

	// Check for close match (within 10%)
	percentError := math.Abs(*spokenNumber-expectedAnswer) / math.Abs(expectedAnswer) * 100
	if percentError < 10 && expectedAnswer != 0 {
		result.IsMatch = false
		result.MatchType = "close"
		result.Score = 70
		result.Feedback = fmt.Sprintf("Close! You said %g but the answer is %g.", *spokenNumber, expectedAnswer)
		return result
	}

	// No match
	result.MatchType = "incorrect"
	result.Score = 0
	result.Feedback = fmt.Sprintf("Not quite. You said %g but the correct answer is %g.", *spokenNumber, expectedAnswer)
	return result
}

// ============================================================================
// RESULT CALCULATION
// ============================================================================

// CalculateAccuracy computes the accuracy percentage
func CalculateAccuracy(correctAnswers, totalQuestions int) float64 {
	if totalQuestions == 0 {
		return 0
	}
	return float64(correctAnswers*100) / float64(totalQuestions)
}

// CalculateAverageTime computes average time per problem
func CalculateAverageTime(totalTime, totalQuestions int) float64 {
	if totalQuestions == 0 {
		return 0
	}
	return float64(totalTime) / float64(totalQuestions)
}

// ============================================================================
// XP AND LEVELING
// ============================================================================

// CalculateMathXP calculates XP earned from a practice session
func CalculateMathXP(accuracy, difficulty string) int {
	baseXP := 10

	// Difficulty multiplier
	difficultyBonus := map[string]int{
		"easy":   1,
		"medium": 2,
		"hard":   3,
	}

	bonus := difficultyBonus[difficulty]
	if bonus == 0 {
		bonus = 1
	}

	// Accuracy bonus
	accuracyBonus := 0
	switch {
	case accuracy >= "95%":
		accuracyBonus = 25
	case accuracy >= "90%":
		accuracyBonus = 20
	case accuracy >= "80%":
		accuracyBonus = 10
	}

	return baseXP + (bonus * 5) + accuracyBonus
}

// InitDB initializes the math app database tables
func (app *MathApp) InitDB() error {
	_, err := app.db.Exec(`
		CREATE TABLE IF NOT EXISTS math_problems (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			user_id INTEGER,
			operation TEXT NOT NULL,
			difficulty TEXT NOT NULL,
			operand1 INTEGER NOT NULL,
			operand2 INTEGER NOT NULL,
			answer REAL NOT NULL,
			question_text TEXT,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			FOREIGN KEY (user_id) REFERENCES users(id)
		);

		CREATE TABLE IF NOT EXISTS math_results (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			user_id INTEGER,
			operation TEXT NOT NULL,
			difficulty TEXT NOT NULL,
			total_questions INTEGER NOT NULL,
			correct_answers INTEGER NOT NULL,
			accuracy REAL NOT NULL,
			average_time REAL NOT NULL,
			total_time INTEGER NOT NULL,
			mode TEXT DEFAULT 'practice',
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			FOREIGN KEY (user_id) REFERENCES users(id)
		);

		CREATE TABLE IF NOT EXISTS math_stats (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			user_id INTEGER UNIQUE,
			total_problems_solved INTEGER DEFAULT 0,
			average_accuracy REAL DEFAULT 0,
			best_accuracy REAL DEFAULT 0,
			total_time_spent INTEGER DEFAULT 0,
			last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			FOREIGN KEY (user_id) REFERENCES users(id)
		);

		CREATE INDEX IF NOT EXISTS idx_math_results_user_id ON math_results(user_id);
		CREATE INDEX IF NOT EXISTS idx_math_problems_user_id ON math_problems(user_id);
	`)
	return err
}
