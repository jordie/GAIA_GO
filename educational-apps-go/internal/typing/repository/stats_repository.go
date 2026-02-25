package repository

import (
	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/typing/models"
	"gorm.io/gorm"
)

// CreateStats creates user statistics record
func CreateStats(stats *models.UserStats) error {
	result := database.DB.Create(stats)
	if result.Error != nil {
		return errors.Internal("failed to create stats", result.Error.Error())
	}
	return nil
}

// GetStatsByUserID retrieves user statistics
func GetStatsByUserID(userID uint) (*models.UserStats, error) {
	var stats models.UserStats
	result := database.DB.Where("user_id = ?", userID).Preload("User").First(&stats)
	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			return nil, errors.NotFound("user stats")
		}
		return nil, errors.Internal("failed to fetch stats", result.Error.Error())
	}
	return &stats, nil
}

// UpdateStats updates user statistics after a new result
func UpdateStats(userID uint, result *models.TypingResult) error {
	stats, err := GetStatsByUserID(userID)
	if err != nil {
		// Create new stats if doesn't exist
		stats = &models.UserStats{
			UserID: userID,
		}
		if err := CreateStats(stats); err != nil {
			return err
		}
	}

	// Calculate new averages
	newTotalTests := stats.TotalTests + 1
	newAverageWPM := ((stats.AverageWPM * float64(stats.TotalTests)) + float64(result.WPM)) / float64(newTotalTests)
	newAverageAccuracy := ((stats.AverageAccuracy * float64(stats.TotalTests)) + result.Accuracy) / float64(newTotalTests)
	newBestWPM := result.WPM
	if result.WPM < stats.BestWPM {
		newBestWPM = stats.BestWPM
	}
	newTotalTime := stats.TotalTimeTyped + result.TestDuration

	// Update stats
	updateResult := database.DB.Model(&models.UserStats{}).
		Where("user_id = ?", userID).
		Updates(map[string]interface{}{
			"total_tests":        newTotalTests,
			"average_wpm":        newAverageWPM,
			"average_accuracy":   newAverageAccuracy,
			"best_wpm":           newBestWPM,
			"total_time_typed":   newTotalTime,
			"last_updated":       gorm.Expr("CURRENT_TIMESTAMP"),
		})

	if updateResult.Error != nil {
		return errors.Internal("failed to update stats", updateResult.Error.Error())
	}

	return nil
}

// GetTopUsers retrieves top users by average WPM
func GetTopUsers(limit int) ([]*models.UserStats, error) {
	var stats []*models.UserStats

	result := database.DB.
		Where("total_tests > 0").
		Order("average_wpm DESC, total_tests DESC").
		Limit(limit).
		Preload("User").
		Find(&stats)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch top users", result.Error.Error())
	}

	return stats, nil
}

// ResetUserStats resets all statistics for a user
func ResetUserStats(userID uint) error {
	result := database.DB.Model(&models.UserStats{}).
		Where("user_id = ?", userID).
		Updates(map[string]interface{}{
			"total_tests":      0,
			"average_wpm":      0,
			"average_accuracy": 0,
			"best_wpm":         0,
			"total_time_typed": 0,
		})

	if result.Error != nil {
		return errors.Internal("failed to reset stats", result.Error.Error())
	}

	return nil
}
