package services

import (
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/piano/models"
	"github.com/architect/educational-apps/internal/piano/repository"
)

// GetUserProgress retrieves user's progress
func GetUserProgress(userID uint) (*models.Progress, error) {
	if userID == 0 {
		return nil, errors.BadRequest("invalid user ID")
	}

	progress, err := repository.GetProgressByUserID(userID)
	if err != nil {
		// Return default progress if not found (first time user)
		return &models.Progress{
			UserID:                     userID,
			CurrentDifficultyLevel:     1,
			TotalExercisesCompleted:    0,
			AverageAccuracyPercentage: 0,
		}, nil
	}

	return progress, nil
}

// GetLeaderboard retrieves top performers
func GetLeaderboard(limit int) ([]*models.ProgressWithUserInfo, error) {
	if limit <= 0 || limit > 100 {
		limit = 10
	}

	progressList, err := repository.GetProgressLeaderboard(limit)
	if err != nil {
		return nil, err
	}

	// Convert to response format
	leaderboard := make([]*models.ProgressWithUserInfo, len(progressList))
	for i, p := range progressList {
		leaderboard[i] = &models.ProgressWithUserInfo{
			UserID:                     p.UserID,
			CurrentDifficultyLevel:     p.CurrentDifficultyLevel,
			TotalExercisesCompleted:    p.TotalExercisesCompleted,
			AverageAccuracyPercentage: p.AverageAccuracyPercentage,
			Rank:                       i + 1,
		}
	}

	return leaderboard, nil
}

// ResetUserProgress resets user's progress (admin only)
func ResetUserProgress(userID uint) error {
	if userID == 0 {
		return errors.BadRequest("invalid user ID")
	}

	updates := map[string]interface{}{
		"current_difficulty_level":      1,
		"total_exercises_completed":     0,
		"average_accuracy_percentage":   0,
	}

	return repository.UpdateProgress(userID, updates)
}
