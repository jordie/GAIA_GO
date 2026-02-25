package repository

import (
	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/typing/models"
)

// CreateResult creates a new typing result
func CreateResult(result *models.TypingResult) error {
	queryResult := database.DB.Create(result)
	if queryResult.Error != nil {
		return errors.Internal("failed to create result", queryResult.Error.Error())
	}
	return nil
}

// GetUserResults retrieves paginated results for a user
func GetUserResults(userID uint, limit, offset int) ([]*models.TypingResult, int64, error) {
	var results []*models.TypingResult
	var total int64

	query := database.DB.Where("user_id = ?", userID)
	query.Model(&models.TypingResult{}).Count(&total)

	result := query.Limit(limit).Offset(offset).
		Order("created_at DESC").
		Preload("User").
		Find(&results)

	if result.Error != nil {
		return nil, 0, errors.Internal("failed to fetch results", result.Error.Error())
	}

	return results, total, nil
}

// GetTopWPMScores retrieves top WPM scores globally
func GetTopWPMScores(limit int) ([]*models.TypingResult, error) {
	var results []*models.TypingResult

	result := database.DB.
		Order("wpm DESC, created_at DESC").
		Limit(limit).
		Preload("User").
		Find(&results)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch top scores", result.Error.Error())
	}

	return results, nil
}

// GetTopAccuracyScores retrieves top accuracy scores with minimum WPM
func GetTopAccuracyScores(minWPM int, limit int) ([]*models.TypingResult, error) {
	var results []*models.TypingResult

	result := database.DB.
		Where("wpm >= ?", minWPM).
		Order("accuracy DESC, wpm DESC, created_at DESC").
		Limit(limit).
		Preload("User").
		Find(&results)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch accuracy scores", result.Error.Error())
	}

	return results, nil
}

// GetBestScoresByType gets best scores grouped by test type for a user
func GetBestScoresByType(userID uint) (map[string]interface{}, error) {
	var results []map[string]interface{}

	queryResult := database.DB.Model(&models.TypingResult{}).
		Select("test_type, MAX(wpm) as best_wpm, MAX(accuracy) as best_accuracy").
		Where("user_id = ?", userID).
		Group("test_type").
		Scan(&results)

	if queryResult.Error != nil {
		return nil, errors.Internal("failed to fetch best scores", queryResult.Error.Error())
	}

	// Convert to map
	scoresMap := make(map[string]interface{})
	for _, r := range results {
		testType := r["test_type"].(string)
		scoresMap[testType] = r
	}

	return scoresMap, nil
}

// GetRecentResults gets recent results for a user
func GetRecentResults(userID uint, limit int) ([]*models.TypingResult, error) {
	var results []*models.TypingResult

	result := database.DB.
		Where("user_id = ?", userID).
		Order("created_at DESC").
		Limit(limit).
		Preload("User").
		Find(&results)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch recent results", result.Error.Error())
	}

	return results, nil
}

// GetResultsCount returns the total count of results for a user
func GetResultsCount(userID uint) (int64, error) {
	var count int64
	result := database.DB.Model(&models.TypingResult{}).
		Where("user_id = ?", userID).
		Count(&count)

	if result.Error != nil {
		return 0, errors.Internal("failed to count results", result.Error.Error())
	}

	return count, nil
}
