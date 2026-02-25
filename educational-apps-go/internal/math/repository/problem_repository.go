package repository

import (
	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/math/models"
)

// CreateProblem saves a generated problem
func CreateProblem(problem *models.MathProblem) error {
	result := database.DB.Create(problem)
	if result.Error != nil {
		return errors.Internal("failed to create problem", result.Error.Error())
	}
	return nil
}

// GetQuestionHistory retrieves question history for user
func GetQuestionHistory(userID uint, limit, offset int) ([]*models.QuestionHistory, int64, error) {
	var history []*models.QuestionHistory
	var total int64

	query := database.DB.Where("user_id = ?", userID)
	query.Model(&models.QuestionHistory{}).Count(&total)

	result := query.Limit(limit).Offset(offset).
		Order("created_at DESC").
		Find(&history)

	if result.Error != nil {
		return nil, 0, errors.Internal("failed to fetch question history", result.Error.Error())
	}

	return history, total, nil
}

// SaveQuestionHistory saves a single question's answer
func SaveQuestionHistory(history *models.QuestionHistory) error {
	result := database.DB.Create(history)
	if result.Error != nil {
		return errors.Internal("failed to save question history", result.Error.Error())
	}
	return nil
}

// GetWeakAreas retrieves fact families with low accuracy
func GetWeakAreas(userID uint, mode string) ([]*models.QuestionHistory, error) {
	var results []*models.QuestionHistory

	query := database.DB.
		Where("user_id = ? AND mode = ?", userID, mode).
		Group("fact_family").
		Select("fact_family, AVG(CASE WHEN is_correct THEN 1 ELSE 0 END) as accuracy").
		Order("accuracy ASC").
		Limit(5).
		Find(&results)

	if query.Error != nil {
		return nil, errors.Internal("failed to fetch weak areas", query.Error.Error())
	}

	return results, nil
}

// GetByFactFamily retrieves problems by fact family for focused practice
func GetByFactFamily(userID uint, factFamily string, mode string) ([]*models.QuestionHistory, error) {
	var results []*models.QuestionHistory

	query := database.DB.
		Where("user_id = ? AND fact_family = ? AND mode = ?", userID, factFamily, mode).
		Order("created_at DESC").
		Limit(20).
		Find(&results)

	if query.Error != nil {
		return nil, errors.Internal("failed to fetch questions by family", query.Error.Error())
	}

	return results, nil
}
