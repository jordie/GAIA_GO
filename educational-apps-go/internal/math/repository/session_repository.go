package repository

import (
	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/math/models"
)

// CreateSession saves a complete practice session
func CreateSession(session *models.SessionResult) error {
	result := database.DB.Create(session)
	if result.Error != nil {
		return errors.Internal("failed to create session", result.Error.Error())
	}
	return nil
}

// GetUserSessions retrieves paginated sessions for a user
func GetUserSessions(userID uint, limit, offset int) ([]*models.SessionResult, int64, error) {
	var sessions []*models.SessionResult
	var total int64

	query := database.DB.Where("user_id = ?", userID)
	query.Model(&models.SessionResult{}).Count(&total)

	result := query.Limit(limit).Offset(offset).
		Order("created_at DESC").
		Find(&sessions)

	if result.Error != nil {
		return nil, 0, errors.Internal("failed to fetch sessions", result.Error.Error())
	}

	return sessions, total, nil
}

// GetRecentSessions retrieves recent sessions
func GetRecentSessions(userID uint, limit int) ([]*models.SessionResult, error) {
	var sessions []*models.SessionResult

	result := database.DB.
		Where("user_id = ?", userID).
		Order("created_at DESC").
		Limit(limit).
		Find(&sessions)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch recent sessions", result.Error.Error())
	}

	return sessions, nil
}

// GetSessionStatistics calculates overall statistics
func GetSessionStatistics(userID uint) (map[string]interface{}, error) {
	var stats map[string]interface{}

	result := database.DB.Model(&models.SessionResult{}).
		Where("user_id = ?", userID).
		Select(
			"COUNT(*) as total_sessions",
			"AVG(accuracy) as average_accuracy",
			"AVG(average_time) as average_time",
			"MAX(accuracy) as best_accuracy",
			"MIN(average_time) as best_time",
		).
		Scan(&stats)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch statistics", result.Error.Error())
	}

	return stats, nil
}

// GetStatsByMode gets statistics grouped by mode
func GetStatsByMode(userID uint) ([]map[string]interface{}, error) {
	var results []map[string]interface{}

	query := database.DB.Model(&models.SessionResult{}).
		Where("user_id = ?", userID).
		Select(
			"mode",
			"COUNT(*) as sessions",
			"AVG(accuracy) as avg_accuracy",
			"AVG(average_time) as avg_time",
		).
		Group("mode").
		Scan(&results)

	if query.Error != nil {
		return nil, errors.Internal("failed to fetch mode statistics", query.Error.Error())
	}

	return results, nil
}

// GetMasteryStats gets mastery levels for a user
func GetMasteryStats(userID uint) ([]*models.Mastery, error) {
	var masteries []*models.Mastery

	result := database.DB.
		Where("user_id = ?", userID).
		Order("mastery_level DESC").
		Limit(20).
		Find(&masteries)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch mastery stats", result.Error.Error())
	}

	return masteries, nil
}
