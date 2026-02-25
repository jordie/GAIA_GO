package services

import (
	"fmt"
	"math"
	"math/rand"
	"strconv"

	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/math/models"
	"github.com/architect/educational-apps/internal/math/repository"
)

// GenerateProblem generates a math problem based on mode and difficulty
func GenerateProblem(userID uint, req models.GenerateProblemRequest) (*models.GenerateProblemResponse, error) {
	// Validate request
	if req.Mode == "" {
		req.Mode = "addition"
	}
	if req.Difficulty == "" {
		req.Difficulty = "easy"
	}
	if req.PracticeType == "" {
		req.PracticeType = "random"
	}

	// Handle review mode
	if req.PracticeType == "review" {
		return getReviewProblem(userID, req.Mode)
	}

	// Generate problem based on mode and difficulty
	var problem *models.MathProblem
	var err error

	if req.PracticeType == "smart" {
		problem, err = generateSmartProblem(userID, req.Mode, req.Difficulty)
	} else {
		problem, err = generateRandomProblem(req.Mode, req.Difficulty)
	}

	if err != nil {
		return nil, err
	}

	// Get hint based on fact family
	factFamily := classifyFactFamily(problem.Operand1, problem.Operand2, problem.Operator)
	hint := getStrategyHint(factFamily, problem.Operand1, problem.Operand2, req.Mode)

	// Format question
	question := fmt.Sprintf("%d %s %d", problem.Operand1, problem.Operator, problem.Operand2)

	return &models.GenerateProblemResponse{
		Question:   question,
		Answer:     strconv.Itoa(problem.CorrectAnswer),
		FactFamily: factFamily,
		Hint:       hint,
	}, nil
}

// generateRandomProblem generates a random problem
func generateRandomProblem(mode, difficulty string) (*models.MathProblem, error) {
	var minNum, maxNum int

	switch difficulty {
	case "easy":
		minNum, maxNum = 1, 10
	case "medium":
		minNum, maxNum = 10, 50
	case "hard":
		minNum, maxNum = 50, 100
	case "expert":
		minNum, maxNum = 100, 999
	default:
		return nil, errors.BadRequest("invalid difficulty")
	}

	num1 := rand.Intn(maxNum-minNum+1) + minNum
	num2 := rand.Intn(maxNum-minNum+1) + minNum
	var operator string
	var answer int

	switch mode {
	case "addition":
		operator = "+"
		answer = num1 + num2

	case "subtraction":
		operator = "-"
		// Ensure positive result
		if num1 < num2 {
			num1, num2 = num2, num1
		}
		answer = num1 - num2

	case "multiplication":
		operator = "*"
		if difficulty == "easy" {
			num1 = rand.Intn(9) + 1
			num2 = rand.Intn(9) + 1
		}
		answer = num1 * num2

	case "division":
		operator = "/"
		num2 = rand.Intn(9) + 1
		answer = rand.Intn(10) + 1
		num1 = num2 * answer

	default:
		return nil, errors.BadRequest("invalid mode")
	}

	problem := &models.MathProblem{
		Mode:           mode,
		Difficulty:     difficulty,
		Operand1:       num1,
		Operand2:       num2,
		Operator:       operator,
		CorrectAnswer:  answer,
	}

	return problem, nil
}

// generateSmartProblem generates problem focusing on weak areas
func generateSmartProblem(userID uint, mode, difficulty string) (*models.MathProblem, error) {
	// Get user's weak fact families
	mistakes, err := repository.GetMistakes(userID, mode)
	if err != nil || len(mistakes) == 0 {
		// Fall back to random if no mistakes
		return generateRandomProblem(mode, difficulty)
	}

	// Use first mistake's fact family
	mistake := mistakes[0]
	problem, err := generateProblemForFamily(mistake.FactFamily, mode, difficulty)
	if err != nil {
		return generateRandomProblem(mode, difficulty)
	}

	return problem, nil
}

// generateProblemForFamily generates specific problem for a fact family
func generateProblemForFamily(factFamily, mode, difficulty string) (*models.MathProblem, error) {
	var num1, num2, answer int
	var operator string

	switch mode {
	case "addition":
		operator = "+"
		switch factFamily {
		case "doubles":
			n := rand.Intn(9) + 1
			num1, num2 = n, n
			answer = n + n
		case "near_doubles":
			n := rand.Intn(9) + 1
			num1, num2 = n, n+1
			answer = num1 + num2
		case "plus_one":
			num1 = 1
			num2 = rand.Intn(19) + 1
			answer = num1 + num2
		case "plus_nine":
			num1 = 9
			num2 = rand.Intn(9) + 1
			answer = num1 + num2
		case "make_ten":
			pairs := [][2]int{{1, 9}, {2, 8}, {3, 7}, {4, 6}, {5, 5}}
			pair := pairs[rand.Intn(len(pairs))]
			num1, num2 = pair[0], pair[1]
			answer = 10
		default:
			minNum, maxNum := 1, 10
			num1 = rand.Intn(maxNum-minNum+1) + minNum
			num2 = rand.Intn(maxNum-minNum+1) + minNum
			answer = num1 + num2
		}

	case "multiplication":
		operator = "*"
		switch factFamily {
		case "times_two":
			num1 = 2
			num2 = rand.Intn(11) + 1
			answer = num1 * num2
		case "times_five":
			num1 = 5
			num2 = rand.Intn(11) + 1
			answer = num1 * num2
		case "times_nine":
			num1 = 9
			num2 = rand.Intn(9) + 1
			answer = num1 * num2
		case "squares":
			n := rand.Intn(9) + 1
			num1, num2 = n, n
			answer = num1 * num2
		default:
			num1 = rand.Intn(9) + 1
			num2 = rand.Intn(9) + 1
			answer = num1 * num2
		}

	default:
		return generateRandomProblem(mode, difficulty)
	}

	return &models.MathProblem{
		Mode:           mode,
		Difficulty:     difficulty,
		Operand1:       num1,
		Operand2:       num2,
		Operator:       operator,
		CorrectAnswer:  answer,
	}, nil
}

// getReviewProblem gets a problem from past mistakes
func getReviewProblem(userID uint, mode string) (*models.GenerateProblemResponse, error) {
	mistakes, err := repository.GetMistakes(userID, mode)
	if err != nil || len(mistakes) == 0 {
		return nil, errors.NotFound("review questions")
	}

	// Pick random mistake
	mistake := mistakes[rand.Intn(len(mistakes))]

	hint := fmt.Sprintf("You've missed this %d time(s). Take your time!", mistake.ErrorCount)

	return &models.GenerateProblemResponse{
		Question:   mistake.Question,
		Answer:     mistake.CorrectAnswer,
		FactFamily: mistake.FactFamily,
		Hint:       hint,
		IsReview:   true,
		ErrorCount: mistake.ErrorCount,
	}, nil
}

// classifyFactFamily classifies a problem into a fact family
func classifyFactFamily(num1, num2 int, operator string) string {
	switch operator {
	case "+":
		if num1 == num2 {
			return "doubles"
		}
		if math.Abs(float64(num1-num2)) == 1 {
			return "near_doubles"
		}
		if num1 == 1 || num2 == 1 {
			return "plus_one"
		}
		if num1 == 9 || num2 == 9 {
			return "plus_nine"
		}
		if num1+num2 == 10 {
			return "make_ten"
		}
		return "other"

	case "-":
		if num1 == num2 {
			return "minus_same"
		}
		if num2 == 1 {
			return "minus_one"
		}
		if num1 == 10 {
			return "from_ten"
		}
		return "other"

	case "*":
		if num1 == 0 || num2 == 0 {
			return "times_zero"
		}
		if num1 == 1 || num2 == 1 {
			return "times_one"
		}
		if num1 == 2 || num2 == 2 {
			return "times_two"
		}
		if num1 == 5 || num2 == 5 {
			return "times_five"
		}
		if num1 == 9 || num2 == 9 {
			return "times_nine"
		}
		if num1 == num2 {
			return "squares"
		}
		return "other"

	default:
		return "other"
	}
}

// getStrategyHint provides learning strategy hints
func getStrategyHint(factFamily string, num1, num2 int, mode string) string {
	hints := map[string]string{
		"doubles":        "Double facts are easy to remember! Think of pairs.",
		"near_doubles":   "This is close to a double. Just add or subtract 1!",
		"plus_one":       "Just count up by one!",
		"plus_two":       "Count up by two, or add one twice!",
		"plus_nine":      "Add 10, then subtract 1!",
		"plus_ten":       "Adding 10 just changes the tens place!",
		"make_ten":       "These two numbers make 10 together!",
		"minus_same":     "Any number minus itself equals zero!",
		"minus_one":      "Just count down by one!",
		"from_ten":       "Think about what makes 10 with this number.",
		"times_zero":     "Any number times zero equals zero!",
		"times_one":      "Any number times one equals itself!",
		"times_two":      "Double the number!",
		"times_five":     "Count by 5s or think of nickels!",
		"times_nine":     "Use the finger trick or multiply by 10 and subtract once!",
		"squares":        "Square numbers form a pattern: 1, 4, 9, 16, 25...",
		"other":          "",
	}

	if hint, ok := hints[factFamily]; ok {
		return hint
	}
	return ""
}
