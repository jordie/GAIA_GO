package repository

import (
	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/reading/models"
	"gorm.io/gorm"
)

// CreateReadingResult saves a reading practice session result
func CreateReadingResult(result *models.ReadingResult) error {
	dbResult := database.DB.Create(result)
	if dbResult.Error != nil {
		return errors.Internal("failed to create reading result", dbResult.Error.Error())
	}
	return nil
}

// GetReadingResult retrieves a specific reading result
func GetReadingResult(resultID uint) (*models.ReadingResult, error) {
	var result models.ReadingResult
	dbResult := database.DB.First(&result, resultID)

	if dbResult.Error != nil {
		if dbResult.Error == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, errors.Internal("failed to fetch reading result", dbResult.Error.Error())
	}

	return &result, nil
}

// GetUserReadingResults retrieves recent reading results for a user
func GetUserReadingResults(userID uint, limit int) ([]*models.ReadingResult, error) {
	var results []*models.ReadingResult

	dbResult := database.DB.
		Where("user_id = ?", userID).
		Order("created_at DESC").
		Limit(limit).
		Find(&results)

	if dbResult.Error != nil {
		return nil, errors.Internal("failed to fetch reading results", dbResult.Error.Error())
	}

	return results, nil
}

// GetReadingStats calculates aggregate reading statistics for a user
func GetReadingStats(userID uint) (map[string]interface{}, error) {
	var results []*models.ReadingResult

	// Get all reading results for user
	dbResult := database.DB.
		Where("user_id = ?", userID).
		Find(&results)

	if dbResult.Error != nil {
		return nil, errors.Internal("failed to fetch reading stats", dbResult.Error.Error())
	}

	stats := make(map[string]interface{})
	stats["total_sessions"] = int64(len(results))

	if len(results) == 0 {
		stats["average_accuracy"] = 0.0
		stats["average_speed"] = 0.0
		stats["best_accuracy"] = 0.0
		stats["best_speed"] = 0.0
		return stats, nil
	}

	// Calculate aggregate statistics
	totalAccuracy := 0.0
	totalSpeed := 0.0
	bestAccuracy := 0.0
	bestSpeed := 0.0

	for _, r := range results {
		totalAccuracy += r.Accuracy
		totalSpeed += r.ReadingSpeed

		if r.Accuracy > bestAccuracy {
			bestAccuracy = r.Accuracy
		}
		if r.ReadingSpeed > bestSpeed {
			bestSpeed = r.ReadingSpeed
		}
	}

	stats["average_accuracy"] = totalAccuracy / float64(len(results))
	stats["average_speed"] = totalSpeed / float64(len(results))
	stats["best_accuracy"] = bestAccuracy
	stats["best_speed"] = bestSpeed

	return stats, nil
}

// GetBestReadingTime returns the hour of day when user reads best
func GetBestReadingTime(userID uint) (int, error) {
	var bestHour int

	result := database.DB.Model(&models.ReadingResult{}).
		Where("user_id = ?", userID).
		Select("EXTRACT(HOUR FROM created_at) as hour").
		Order("avg(accuracy) DESC").
		Limit(1).
		Pluck("hour", &bestHour)

	if result.Error != nil && result.Error != gorm.ErrRecordNotFound {
		return 0, errors.Internal("failed to fetch best reading time", result.Error.Error())
	}

	return bestHour, nil
}
