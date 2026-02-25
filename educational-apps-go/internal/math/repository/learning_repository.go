package repository

import (
	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/math/models"
	"gorm.io/gorm"
)

// GetLearningProfile retrieves user's learning profile
func GetLearningProfile(userID uint) (*models.LearningProfile, error) {
	var profile models.LearningProfile
	result := database.DB.Where("user_id = ?", userID).First(&profile)

	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, errors.Internal("failed to fetch learning profile", result.Error.Error())
	}

	return &profile, nil
}

// CreateLearningProfile creates new learning profile
func CreateLearningProfile(profile *models.LearningProfile) error {
	result := database.DB.Create(profile)
	if result.Error != nil {
		return errors.Internal("failed to create learning profile", result.Error.Error())
	}
	return nil
}

// UpdateLearningProfile updates learning profile
func UpdateLearningProfile(profile *models.LearningProfile) error {
	result := database.DB.Save(profile)
	if result.Error != nil {
		return errors.Internal("failed to update learning profile", result.Error.Error())
	}
	return nil
}

// GetPerformancePatterns retrieves performance patterns for user
func GetPerformancePatterns(userID uint) ([]*models.PerformancePattern, error) {
	var patterns []*models.PerformancePattern

	result := database.DB.
		Where("user_id = ?", userID).
		Order("average_accuracy DESC").
		Find(&patterns)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch performance patterns", result.Error.Error())
	}

	return patterns, nil
}

// GetBestPerformanceTime returns hour with best performance
func GetBestPerformanceTime(userID uint) (int, error) {
	var hourOfDay int

	result := database.DB.Model(&models.PerformancePattern{}).
		Where("user_id = ?", userID).
		Order("average_accuracy DESC").
		Limit(1).
		Pluck("hour_of_day", &hourOfDay)

	if result.Error != nil {
		return 0, errors.Internal("failed to fetch best time", result.Error.Error())
	}

	return hourOfDay, nil
}

// UpdatePerformancePattern updates or creates performance pattern
func UpdatePerformancePattern(pattern *models.PerformancePattern) error {
	// Try to find existing pattern
	existing := &models.PerformancePattern{}
	result := database.DB.
		Where("user_id = ? AND hour_of_day = ? AND day_of_week = ?",
			pattern.UserID, pattern.HourOfDay, pattern.DayOfWeek).
		First(existing)

	if result.Error == gorm.ErrRecordNotFound {
		// Create new
		return CreatePerformancePattern(pattern)
	}

	if result.Error != nil {
		return errors.Internal("failed to find pattern", result.Error.Error())
	}

	// Update existing
	updateResult := database.DB.Save(pattern)
	if updateResult.Error != nil {
		return errors.Internal("failed to update pattern", updateResult.Error.Error())
	}

	return nil
}

// CreatePerformancePattern creates new performance pattern
func CreatePerformancePattern(pattern *models.PerformancePattern) error {
	result := database.DB.Create(pattern)
	if result.Error != nil {
		return errors.Internal("failed to create pattern", result.Error.Error())
	}
	return nil
}

// GetRepetitionSchedule retrieves facts due for review
func GetRepetitionSchedule(userID uint) ([]*models.RepetitionSchedule, error) {
	var schedules []*models.RepetitionSchedule

	result := database.DB.
		Where("user_id = ? AND next_review <= ?", userID, gorm.Expr("CURRENT_TIMESTAMP")).
		Order("next_review ASC").
		Limit(20).
		Find(&schedules)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch repetition schedule", result.Error.Error())
	}

	return schedules, nil
}

// UpdateRepetitionSchedule updates spaced repetition
func UpdateRepetitionSchedule(schedule *models.RepetitionSchedule) error {
	result := database.DB.Save(schedule)
	if result.Error != nil {
		return errors.Internal("failed to update repetition schedule", result.Error.Error())
	}
	return nil
}
