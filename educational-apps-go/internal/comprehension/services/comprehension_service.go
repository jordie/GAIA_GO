package services

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/comprehension/models"
	"github.com/architect/educational-apps/internal/comprehension/repository"
)

// CheckAnswer validates an answer based on question type
func CheckAnswer(userID uint, req models.CheckAnswerRequest) (*models.CheckAnswerResponse, error) {
	// Get the question
	question, err := repository.GetQuestion(req.QuestionID)
	if err != nil {
		return nil, err
	}

	if question == nil {
		return nil, errors.NotFound("question")
	}

	// Route to appropriate validator based on question type
	var response *models.CheckAnswerResponse

	switch question.QuestionType {
	case "word_tap":
		response = CheckWordTap(question, req.SelectedWords, req.TargetType)
	case "fill_blank":
		response = CheckFillBlank(question, req.Answer)
	case "multiple_choice":
		response = CheckMultipleChoice(question, req.Answer, req.SelectedIndex)
	case "text_entry":
		response = CheckTextEntry(question, req.UserInput)
	case "analogy":
		response = CheckAnalogy(question, req.Answer)
	case "sentence_order":
		response = CheckSentenceOrder(question, req.UserInput)
	case "true_false":
		response = CheckTrueFalse(question, req.Answer)
	case "matching":
		response = CheckMatching(question, req.UserInput)
	default:
		return nil, errors.BadRequest(fmt.Sprintf("unsupported question type: %s", question.QuestionType))
	}

	// Save progress
	userAnswer, _ := json.Marshal(req)
	progress := &models.UserProgress{
		UserID:       userID,
		QuestionID:   req.QuestionID,
		QuestionType: question.QuestionType,
		Subject:      question.Subject,
		Difficulty:   question.Difficulty,
		Correct:      response.Correct,
		Score:        response.Score,
		MaxScore:     response.MaxScore,
		UserAnswer:   userAnswer,
		CompletedAt:  time.Now(),
	}

	if _, err := repository.SaveUserProgress(progress); err != nil {
		// Log error but don't fail - progress saving is best effort
		fmt.Printf("Failed to save progress: %v\n", err)
	}

	// Update user stats
	updateUserStats(userID, question, response.Correct, response.Score)

	return response, nil
}

// CheckWordTap validates word tapping questions
// User selects words that match a category (nouns, verbs, adjectives)
func CheckWordTap(question *models.Question, selectedWords map[string]string, targetType string) *models.CheckAnswerResponse {
	response := &models.CheckAnswerResponse{
		MaxScore:  20,
		Feedback:  make(map[string]interface{}),
	}

	// Get word_labels from content
	wordLabels, ok := question.Content["word_labels"].(map[string]interface{})
	if !ok {
		response.Correct = false
		response.Score = 0
		return response
	}

	correct := 0
	incorrect := 0
	missed := 0
	selectedCount := 0

	// Check selected words
	for word, selectedType := range selectedWords {
		expectedType, exists := wordLabels[word].(string)
		if !exists {
			incorrect++
			selectedCount++
			continue
		}

		if strings.ToLower(selectedType) == strings.ToLower(expectedType) {
			correct++
		} else {
			incorrect++
		}
		selectedCount++
	}

	// Count missed words
	for word, expectedTypeInterface := range wordLabels {
		expectedType, _ := expectedTypeInterface.(string)
		if strings.ToLower(expectedType) == strings.ToLower(targetType) {
			if _, wasSelected := selectedWords[word]; !wasSelected {
				missed++
			}
		}
	}

	// Calculate score
	score := (correct * 10) - (incorrect * 5) + (20 * correct / (correct + missed + incorrect))
	if score < 0 {
		score = 0
	}
	if correct == selectedCount && missed == 0 {
		score = 20 // Perfect score
	}

	response.Correct = incorrect == 0 && missed == 0
	response.Score = score
	response.Feedback = map[string]interface{}{
		"correct":   correct,
		"incorrect": incorrect,
		"missed":    missed,
		"accuracy":  float64(correct) / float64(correct+missed+incorrect),
	}

	return response
}

// CheckFillBlank validates fill-in-the-blank questions
func CheckFillBlank(question *models.Question, answer string) *models.CheckAnswerResponse {
	response := &models.CheckAnswerResponse{
		MaxScore: 10,
	}

	// Get correct answer
	correctAnswerInterface, ok := question.Content["correct_answer"]
	if !ok {
		response.Correct = false
		response.Score = 0
		return response
	}

	// Handle multiple accepted answers
	var correctAnswers []string
	switch v := correctAnswerInterface.(type) {
	case string:
		correctAnswers = []string{v}
	case []interface{}:
		for _, ans := range v {
			if str, ok := ans.(string); ok {
				correctAnswers = append(correctAnswers, strings.ToLower(str))
			}
		}
	default:
		correctAnswers = []string{fmt.Sprintf("%v", correctAnswerInterface)}
	}

	// Case-insensitive comparison
	answerLower := strings.ToLower(strings.TrimSpace(answer))
	response.Correct = false
	for _, ca := range correctAnswers {
		if answerLower == strings.ToLower(ca) {
			response.Correct = true
			break
		}
	}

	if response.Correct {
		response.Score = 10
	} else {
		response.Score = 0
	}

	response.CorrectAnswer = correctAnswerInterface
	response.UserAnswer = answer

	return response
}

// CheckMultipleChoice validates multiple choice questions
func CheckMultipleChoice(question *models.Question, answer string, selectedIndex int) *models.CheckAnswerResponse {
	response := &models.CheckAnswerResponse{
		MaxScore: 10,
	}

	// Get correct answer
	correctAnsInterface, ok := question.Content["correct_answer"]
	if !ok {
		response.Correct = false
		response.Score = 0
		return response
	}

	var correctAnswer string
	if str, ok := correctAnsInterface.(string); ok {
		correctAnswer = str
	} else {
		correctAnswer = fmt.Sprintf("%v", correctAnsInterface)
	}

	// Check if answer matches
	response.Correct = (answer != "" && strings.EqualFold(answer, correctAnswer)) ||
		(selectedIndex > 0 && selectedIndex-1 == parseIndex(correctAnswer))

	if response.Correct {
		response.Score = 10
	} else {
		response.Score = 0
	}

	response.CorrectAnswer = correctAnswer
	response.UserAnswer = answer

	// Include explanation if available
	if explanation, ok := question.Content["explanation"].(string); ok {
		response.Explanation = explanation
	}

	return response
}

// CheckTextEntry validates text entry questions
func CheckTextEntry(question *models.Question, userInput string) *models.CheckAnswerResponse {
	response := &models.CheckAnswerResponse{
		MaxScore: 10,
	}

	// Get correct answers
	correctAnswersInterface, ok := question.Content["correct_answers"]
	if !ok {
		response.Correct = false
		response.Score = 0
		return response
	}

	var correctAnswers []string
	switch v := correctAnswersInterface.(type) {
	case []interface{}:
		for _, ans := range v {
			if str, ok := ans.(string); ok {
				correctAnswers = append(correctAnswers, str)
			}
		}
	case string:
		correctAnswers = []string{v}
	}

	// Case sensitivity option
	caseSensitive := false
	if cs, ok := question.Content["case_sensitive"].(bool); ok {
		caseSensitive = cs
	}

	userInputTrimmed := strings.TrimSpace(userInput)
	response.Correct = false

	for _, ca := range correctAnswers {
		if caseSensitive {
			if userInputTrimmed == ca {
				response.Correct = true
				break
			}
		} else {
			if strings.EqualFold(userInputTrimmed, ca) {
				response.Correct = true
				break
			}
		}
	}

	if response.Correct {
		response.Score = 10
	} else {
		response.Score = 0
	}

	response.CorrectAnswer = correctAnswersInterface
	response.UserAnswer = userInput

	return response
}

// CheckAnalogy validates analogy questions
func CheckAnalogy(question *models.Question, answer string) *models.CheckAnswerResponse {
	response := &models.CheckAnswerResponse{
		MaxScore: 10,
	}

	// Get correct answer
	correctAnswerInterface, ok := question.Content["correct_answer"]
	if !ok {
		response.Correct = false
		response.Score = 0
		return response
	}

	correctAnswer := fmt.Sprintf("%v", correctAnswerInterface)

	// Text matching
	answerLower := strings.ToLower(strings.TrimSpace(answer))
	response.Correct = answerLower == strings.ToLower(correctAnswer)

	if response.Correct {
		response.Score = 10
	} else {
		response.Score = 0
	}

	response.CorrectAnswer = correctAnswerInterface
	response.UserAnswer = answer

	// Include relationship if available
	if relationship, ok := question.Content["relationship"].(string); ok {
		response.Feedback = map[string]interface{}{
			"relationship": relationship,
		}
	}

	return response
}

// CheckSentenceOrder validates sentence ordering questions
func CheckSentenceOrder(question *models.Question, userOrder string) *models.CheckAnswerResponse {
	response := &models.CheckAnswerResponse{
		MaxScore: 10,
	}

	// Get correct order
	correctOrderInterface, ok := question.Content["correct_order"]
	if !ok {
		response.Correct = false
		response.Score = 0
		return response
	}

	var correctOrder []string
	if orderStr, ok := correctOrderInterface.(string); ok {
		correctOrder = strings.Split(orderStr, " ")
	} else if orderSlice, ok := correctOrderInterface.([]interface{}); ok {
		for _, item := range orderSlice {
			correctOrder = append(correctOrder, fmt.Sprintf("%v", item))
		}
	}

	// Parse user order
	userOrderNorm := strings.Fields(userOrder)

	// Exact matching
	response.Correct = len(userOrderNorm) == len(correctOrder)
	if response.Correct {
		for i, word := range userOrderNorm {
			if word != correctOrder[i] {
				response.Correct = false
				break
			}
		}
	}

	if response.Correct {
		response.Score = 10
	} else {
		response.Score = 0
	}

	response.CorrectAnswer = strings.Join(correctOrder, " ")
	response.UserAnswer = userOrder

	return response
}

// CheckTrueFalse validates true/false questions
func CheckTrueFalse(question *models.Question, answer string) *models.CheckAnswerResponse {
	response := &models.CheckAnswerResponse{
		MaxScore: 10,
	}

	// Get correct answer
	correctAnswerInterface, ok := question.Content["correct_answer"]
	if !ok {
		response.Correct = false
		response.Score = 0
		return response
	}

	answerLower := strings.ToLower(strings.TrimSpace(answer))
	correctStr := strings.ToLower(fmt.Sprintf("%v", correctAnswerInterface))

	// Accept various true/false representations
	response.Correct = (answerLower == "true" || answerLower == "t") && (correctStr == "true" || correctStr == "t") ||
		(answerLower == "false" || answerLower == "f") && (correctStr == "false" || correctStr == "f")

	if response.Correct {
		response.Score = 10
	} else {
		response.Score = 0
	}

	response.CorrectAnswer = correctAnswerInterface
	response.UserAnswer = answer

	// Include explanation
	if explanation, ok := question.Content["explanation"].(string); ok {
		response.Explanation = explanation
	}

	return response
}

// CheckMatching validates matching questions
func CheckMatching(question *models.Question, userMatches string) *models.CheckAnswerResponse {
	response := &models.CheckAnswerResponse{
		MaxScore: 10,
	}

	// Get correct matches
	correctMatchesInterface, ok := question.Content["correct_matches"]
	if !ok {
		response.Correct = false
		response.Score = 0
		return response
	}

	// Parse JSON user matches
	var userMatchMap map[string]string
	if err := json.Unmarshal([]byte(userMatches), &userMatchMap); err != nil {
		response.Correct = false
		response.Score = 0
		return response
	}

	// Parse correct matches
	correctMatches, ok := correctMatchesInterface.(map[string]interface{})
	if !ok {
		response.Correct = false
		response.Score = 0
		return response
	}

	// Compare matches
	correct := 0
	total := 0
	for key, expectedValue := range correctMatches {
		total++
		if userVal, ok := userMatchMap[key]; ok {
			if strings.EqualFold(userVal, fmt.Sprintf("%v", expectedValue)) {
				correct++
			}
		}
	}

	response.Correct = correct == total && total > 0
	response.Score = (correct * 10) / total
	response.CorrectAnswer = correctMatchesInterface
	response.UserAnswer = userMatches

	return response
}

// updateUserStats updates user statistics after answering
func updateUserStats(userID uint, question *models.Question, correct bool, score int) error {
	// Get or create user stats
	stats, err := repository.GetUserStats(userID, question.Subject)
	if err != nil {
		return err
	}

	stats.QuestionsAttempted++
	stats.TotalTime += question.TimeLimit
	stats.LastPractice = time.Now()

	if correct {
		stats.QuestionsCorrect++
		stats.CurrentStreak++
		if stats.CurrentStreak > stats.BestStreak {
			stats.BestStreak = stats.CurrentStreak
		}
	} else {
		stats.CurrentStreak = 0
	}

	stats.TotalScore += score

	return repository.UpsertUserStats(stats)
}

// GetUserStats retrieves user statistics
func GetUserStats(userID uint, subject string) (*models.UserStatsResponse, error) {
	stats, err := repository.GetUserStats(userID, subject)
	if err != nil {
		return nil, err
	}

	response := &models.UserStatsResponse{
		UserID:             stats.UserID,
		Subject:            stats.Subject,
		QuestionsAttempted: stats.QuestionsAttempted,
		QuestionsCorrect:   stats.QuestionsCorrect,
		TotalScore:         stats.TotalScore,
		BestStreak:         stats.BestStreak,
		CurrentStreak:      stats.CurrentStreak,
		LastPractice:       stats.LastPractice,
	}

	if stats.QuestionsAttempted > 0 {
		response.Accuracy = float64(stats.QuestionsCorrect) / float64(stats.QuestionsAttempted)
		response.AverageTimePerQuestion = float64(stats.TotalTime) / float64(stats.QuestionsAttempted)
	}

	return response, nil
}

// Helper function to parse index from string
func parseIndex(s string) int {
	// Remove common prefixes (a, b, c, d, 1, 2, 3, 4)
	s = strings.ToLower(strings.TrimSpace(s))
	if len(s) > 0 {
		switch s[0] {
		case 'a', '1':
			return 0
		case 'b', '2':
			return 1
		case 'c', '3':
			return 2
		case 'd', '4':
			return 3
		}
	}
	return -1
}
