package repository

import (
	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/piano/models"
)

// GetProgressByUserID retrieves progress for a user
func GetProgressByUserID(userID uint) (*models.Progress, error) {
	var progress models.Progress
	result := database.DB.Where("user_id = ?", userID).First(&progress)
	if result.Error != nil {
		return nil, errors.NotFound("user progress")
	}
	return &progress, nil
}

// CreateProgress creates a new progress record
func CreateProgress(progress *models.Progress) error {
	result := database.DB.Create(progress)
	if result.Error != nil {
		return errors.Internal("failed to create progress", result.Error.Error())
	}
	return nil
}

// UpdateProgress updates user progress
func UpdateProgress(userID uint, updates map[string]interface{}) error {
	result := database.DB.Model(&models.Progress{}).
		Where("user_id = ?", userID).
		Updates(updates)

	if result.Error != nil {
		return errors.Internal("failed to update progress", result.Error.Error())
	}

	if result.RowsAffected == 0 {
		// Progress doesn't exist, create it
		progress := &models.Progress{UserID: userID}
		for k, v := range updates {
			// Simple field mapping
			switch k {
			case "current_difficulty_level":
				if level, ok := v.(int); ok {
					progress.CurrentDifficultyLevel = level
				}
			case "total_exercises_completed":
				if count, ok := v.(int); ok {
					progress.TotalExercisesCompleted = count
				}
			case "average_accuracy_percentage":
				if acc, ok := v.(float64); ok {
					progress.AverageAccuracyPercentage = acc
				}
			}
		}
		return CreateProgress(progress)
	}

	return nil
}

// GetProgressLeaderboard retrieves top performers
func GetProgressLeaderboard(limit int) ([]*models.Progress, error) {
	var progressList []*models.Progress
	result := database.DB.
		Order("average_accuracy_percentage DESC, total_exercises_completed DESC").
		Limit(limit).
		Find(&progressList)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch leaderboard", result.Error.Error())
	}

	return progressList, nil
}
