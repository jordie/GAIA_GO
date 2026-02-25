package repository

import (
	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/reading/models"
	"gorm.io/gorm"
)

// CreateQuiz creates a new quiz
func CreateQuiz(quiz *models.Quiz) (uint, error) {
	result := database.DB.Create(quiz)
	if result.Error != nil {
		return 0, errors.Internal("failed to create quiz", result.Error.Error())
	}
	return quiz.ID, nil
}

// GetQuiz retrieves a specific quiz by ID
func GetQuiz(quizID uint) (*models.Quiz, error) {
	var quiz models.Quiz
	result := database.DB.
		Preload("Questions").
		First(&quiz, quizID)

	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, errors.Internal("failed to fetch quiz", result.Error.Error())
	}

	return &quiz, nil
}

// ListQuizzes retrieves all quizzes with question counts
func ListQuizzes() ([]*models.Quiz, error) {
	var quizzes []*models.Quiz

	result := database.DB.
		Preload("Questions").
		Order("created_at DESC").
		Find(&quizzes)

	if result.Error != nil {
		return nil, errors.Internal("failed to list quizzes", result.Error.Error())
	}

	return quizzes, nil
}

// AddQuestion adds a question to a quiz
func AddQuestion(question *models.Question) (uint, error) {
	result := database.DB.Create(question)
	if result.Error != nil {
		return 0, errors.Internal("failed to add question", result.Error.Error())
	}
	return question.ID, nil
}

// GetQuestions retrieves all questions for a quiz
func GetQuestions(quizID uint) ([]*models.Question, error) {
	var questions []*models.Question

	result := database.DB.
		Where("quiz_id = ?", quizID).
		Order("id ASC").
		Find(&questions)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch questions", result.Error.Error())
	}

	return questions, nil
}

// GetQuestion retrieves a specific question
func GetQuestion(questionID uint) (*models.Question, error) {
	var question models.Question
	result := database.DB.First(&question, questionID)

	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, errors.Internal("failed to fetch question", result.Error.Error())
	}

	return &question, nil
}

// SaveQuizAttempt saves a quiz attempt result
func SaveQuizAttempt(attempt *models.QuizAttempt) (uint, error) {
	result := database.DB.Create(attempt)
	if result.Error != nil {
		return 0, errors.Internal("failed to save quiz attempt", result.Error.Error())
	}
	return attempt.ID, nil
}

// GetQuizAttempt retrieves a specific quiz attempt
func GetQuizAttempt(attemptID uint) (*models.QuizAttempt, error) {
	var attempt models.QuizAttempt
	result := database.DB.
		Preload("Quiz").
		Preload("User").
		First(&attempt, attemptID)

	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, errors.Internal("failed to fetch quiz attempt", result.Error.Error())
	}

	return &attempt, nil
}

// GetUserQuizAttempts retrieves all quiz attempts for a user
func GetUserQuizAttempts(userID uint, limit int) ([]*models.QuizAttempt, error) {
	var attempts []*models.QuizAttempt

	result := database.DB.
		Where("user_id = ?", userID).
		Preload("Quiz").
		Order("taken_at DESC").
		Limit(limit).
		Find(&attempts)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch user quiz attempts", result.Error.Error())
	}

	return attempts, nil
}

// GetQuizAttempts retrieves all attempts for a specific quiz
func GetQuizAttempts(quizID uint, limit int) ([]*models.QuizAttempt, error) {
	var attempts []*models.QuizAttempt

	result := database.DB.
		Where("quiz_id = ?", quizID).
		Preload("User").
		Order("taken_at DESC").
		Limit(limit).
		Find(&attempts)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch quiz attempts", result.Error.Error())
	}

	return attempts, nil
}

// GetQuizStats returns statistics for a quiz
func GetQuizStats(quizID uint) (map[string]interface{}, error) {
	var attempts []*models.QuizAttempt

	result := database.DB.
		Where("quiz_id = ?", quizID).
		Find(&attempts)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch quiz stats", result.Error.Error())
	}

	stats := make(map[string]interface{})
	stats["total_attempts"] = int64(len(attempts))

	if len(attempts) == 0 {
		stats["average_score"] = 0.0
		stats["pass_rate"] = 0.0
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

	return stats, nil
}
