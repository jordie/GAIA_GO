package repository

import (
	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/piano/models"
)

// GetAttemptsByUserID retrieves all attempts for a user
func GetAttemptsByUserID(userID uint, limit, offset int) ([]*models.Attempt, int64, error) {
	var attempts []*models.Attempt
	var total int64

	query := database.DB.Where("user_id = ?", userID)
	query.Model(&models.Attempt{}).Count(&total)

	result := query.Limit(limit).Offset(offset).
		Preload("Exercise").
		Find(&attempts)

	if result.Error != nil {
		return nil, 0, errors.Internal("failed to fetch attempts", result.Error.Error())
	}

	return attempts, total, nil
}

// GetAttemptsByExerciseID retrieves all attempts for an exercise
func GetAttemptsByExerciseID(exerciseID uint, limit, offset int) ([]*models.Attempt, int64, error) {
	var attempts []*models.Attempt
	var total int64

	query := database.DB.Where("exercise_id = ?", exerciseID)
	query.Model(&models.Attempt{}).Count(&total)

	result := query.Limit(limit).Offset(offset).Find(&attempts)
	if result.Error != nil {
		return nil, 0, errors.Internal("failed to fetch attempts", result.Error.Error())
	}

	return attempts, total, nil
}

// CreateAttempt creates a new attempt record
func CreateAttempt(attempt *models.Attempt) error {
	result := database.DB.Create(attempt)
	if result.Error != nil {
		return errors.Internal("failed to create attempt", result.Error.Error())
	}
	return nil
}

// GetUserExerciseStats retrieves performance stats for a user on an exercise
func GetUserExerciseStats(userID, exerciseID uint) (map[string]interface{}, error) {
	var stats map[string]interface{}

	result := database.DB.Model(&models.Attempt{}).
		Where("user_id = ? AND exercise_id = ?", userID, exerciseID).
		Select(
			"COUNT(*) as total_attempts",
			"SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct_attempts",
			"AVG(accuracy_percentage) as average_accuracy",
			"AVG(response_time_ms) as average_response_time",
		).
		Scan(&stats)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch stats", result.Error.Error())
	}

	return stats, nil
}
