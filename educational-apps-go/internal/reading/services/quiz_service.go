package services

import (
	"encoding/json"
	"strconv"

	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/reading/models"
	"github.com/architect/educational-apps/internal/reading/repository"
)

const PassThreshold = 0.70

// CreateQuiz creates a new quiz with questions
func CreateQuiz(req models.CreateQuizRequest) (uint, error) {
	quiz := &models.Quiz{
		Title:       req.Title,
		Description: req.Description,
		PassScore:   req.PassScore,
	}

	quizID, err := repository.CreateQuiz(quiz)
	if err != nil {
		return 0, err
	}

	// Add questions
	for _, q := range req.Questions {
		question := &models.Question{
			QuizID:        quizID,
			QuestionText:  q.QuestionText,
			QuestionType:  q.QuestionType,
			CorrectAnswer: q.CorrectAnswer,
			OptionA:       q.OptionA,
			OptionB:       q.OptionB,
			OptionC:       q.OptionC,
			OptionD:       q.OptionD,
		}

		if _, err := repository.AddQuestion(question); err != nil {
			return 0, err
		}
	}

	return quizID, nil
}

// GetQuiz retrieves a specific quiz
func GetQuiz(quizID uint) (*models.QuizDetailResponse, error) {
	quiz, err := repository.GetQuiz(quizID)
	if err != nil {
		return nil, err
	}

	if quiz == nil {
		return nil, errors.NotFound("quiz")
	}

	// Convert to response format
	response := &models.QuizDetailResponse{
		ID:          quiz.ID,
		Title:       quiz.Title,
		Description: quiz.Description,
		PassScore:   quiz.PassScore,
		CreatedAt:   quiz.CreatedAt,
		Questions:   make([]*models.QuestionDetailResponse, len(quiz.Questions)),
	}

	for i, q := range quiz.Questions {
		response.Questions[i] = &models.QuestionDetailResponse{
			ID:           q.ID,
			QuestionText: q.QuestionText,
			QuestionType: q.QuestionType,
			OptionA:      q.OptionA,
			OptionB:      q.OptionB,
			OptionC:      q.OptionC,
			OptionD:      q.OptionD,
		}
	}

	return response, nil
}

// ListQuizzes retrieves all quizzes
func ListQuizzes() ([]*models.QuizListResponse, error) {
	quizzes, err := repository.ListQuizzes()
	if err != nil {
		return nil, err
	}

	response := make([]*models.QuizListResponse, len(quizzes))
	for i, q := range quizzes {
		response[i] = &models.QuizListResponse{
			ID:            q.ID,
			Title:         q.Title,
			Description:   q.Description,
			QuestionCount: len(q.Questions),
			PassScore:     q.PassScore,
			CreatedAt:     q.CreatedAt,
		}
	}

	return response, nil
}

// SubmitQuiz processes quiz submission and calculates score
func SubmitQuiz(userID, quizID uint, req models.SubmitQuizRequest) (*models.QuizResultResponse, error) {
	// Get quiz and questions
	quiz, err := repository.GetQuiz(quizID)
	if err != nil {
		return nil, err
	}

	if quiz == nil {
		return nil, errors.NotFound("quiz")
	}

	questions := quiz.Questions
	if len(questions) == 0 {
		return nil, errors.BadRequest("quiz has no questions")
	}

	// Calculate score
	score := 0
	total := len(questions)
	questionResults := make([]*models.QuestionResult, len(questions))

	for i, question := range questions {
		userAnswer := req.Answers[strconv.Itoa(int(question.ID))]
		isCorrect := userAnswer == question.CorrectAnswer

		if isCorrect {
			score++
		}

		// Format answer text for display
		userAnswerText := userAnswer
		if question.QuestionType == "multiple_choice" {
			userAnswerText = getOptionText(&question, userAnswer)
		}

		correctAnswerText := question.CorrectAnswer
		if question.QuestionType == "multiple_choice" {
			correctAnswerText = getOptionText(&question, question.CorrectAnswer)
		}

		questionResults[i] = &models.QuestionResult{
			QuestionID:        question.ID,
			QuestionText:      question.QuestionText,
			UserAnswer:        userAnswer,
			CorrectAnswer:     question.CorrectAnswer,
			UserAnswerText:    userAnswerText,
			CorrectAnswerText: correctAnswerText,
			IsCorrect:         isCorrect,
		}
	}

	// Calculate percentage
	percentage := 0
	if total > 0 {
		percentage = (score * 100) / total
	}

	// Determine if passed
	passed := float64(score) >= float64(total)*PassThreshold

	// Save attempt
	answersJSON, _ := json.Marshal(req.Answers)
	attempt := &models.QuizAttempt{
		QuizID:     quizID,
		UserID:     userID,
		Score:      score,
		Total:      total,
		Percentage: percentage,
		Passed:     passed,
		Answers:    string(answersJSON),
	}

	attemptID, err := repository.SaveQuizAttempt(attempt)
	if err != nil {
		return nil, err
	}

	response := &models.QuizResultResponse{
		AttemptID:       attemptID,
		QuizID:          quizID,
		Score:           score,
		Total:           total,
		Percentage:      percentage,
		Passed:          passed,
		QuestionResults: questionResults,
	}

	return response, nil
}

// GetQuizResults retrieves results from a quiz attempt
func GetQuizResults(attemptID uint) (*models.QuizResultResponse, error) {
	attempt, err := repository.GetQuizAttempt(attemptID)
	if err != nil {
		return nil, err
	}

	if attempt == nil {
		return nil, errors.NotFound("quiz attempt")
	}

	// Get questions to match with results
	questions, err := repository.GetQuestions(attempt.QuizID)
	if err != nil {
		return nil, err
	}

	// Parse stored answers
	var storedAnswers map[string]string
	json.Unmarshal([]byte(attempt.Answers), &storedAnswers)

	// Reconstruct question results
	questionResults := make([]*models.QuestionResult, len(questions))
	for i, question := range questions {
		userAnswer := storedAnswers[strconv.Itoa(int(question.ID))]
		isCorrect := userAnswer == question.CorrectAnswer

		questionResults[i] = &models.QuestionResult{
			QuestionID:        question.ID,
			QuestionText:      question.QuestionText,
			UserAnswer:        userAnswer,
			CorrectAnswer:     question.CorrectAnswer,
			UserAnswerText:    getOptionText(question, userAnswer),
			CorrectAnswerText: getOptionText(question, question.CorrectAnswer),
			IsCorrect:         isCorrect,
		}
	}

	response := &models.QuizResultResponse{
		AttemptID:       attemptID,
		QuizID:          attempt.QuizID,
		Score:           attempt.Score,
		Total:           attempt.Total,
		Percentage:      attempt.Percentage,
		Passed:          attempt.Passed,
		QuestionResults: questionResults,
	}

	return response, nil
}

// getOptionText converts option letter to text
func getOptionText(question *models.Question, optionLetter string) string {
	switch optionLetter {
	case "a":
		return question.OptionA
	case "b":
		return question.OptionB
	case "c":
		return question.OptionC
	case "d":
		return question.OptionD
	case "true":
		return "True"
	case "false":
		return "False"
	default:
		return "Not answered"
	}
}

// GetUserQuizStats retrieves quiz statistics for a user
func GetUserQuizStats(userID uint) (map[string]interface{}, error) {
	attempts, err := repository.GetUserQuizAttempts(userID, 100)
	if err != nil {
		return nil, err
	}

	stats := make(map[string]interface{})
	stats["total_attempts"] = len(attempts)

	if len(attempts) == 0 {
		stats["average_score"] = 0.0
		stats["pass_rate"] = 0.0
		stats["total_passed"] = 0
		return stats, nil
	}

	totalScore := 0
	passCount := 0

	for _, attempt := range attempts {
		totalScore += attempt.Score
		if attempt.Passed {
			passCount++
		}
	}

	stats["average_score"] = float64(totalScore) / float64(len(attempts))
	stats["pass_rate"] = float64(passCount) / float64(len(attempts)) * 100
	stats["total_passed"] = passCount

	return stats, nil
}
