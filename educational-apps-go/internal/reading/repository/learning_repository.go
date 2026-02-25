package repository

import (
	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/reading/models"
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

// GetReadingStreak retrieves user's reading streak
func GetReadingStreak(userID uint) (*models.ReadingStreak, error) {
	var streak models.ReadingStreak
	result := database.DB.Where("user_id = ?", userID).First(&streak)

	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, errors.Internal("failed to fetch reading streak", result.Error.Error())
	}

	return &streak, nil
}

// CreateReadingStreak creates new reading streak record
func CreateReadingStreak(streak *models.ReadingStreak) error {
	result := database.DB.Create(streak)
	if result.Error != nil {
		return errors.Internal("failed to create reading streak", result.Error.Error())
	}
	return nil
}

// UpdateReadingStreak updates reading streak
func UpdateReadingStreak(streak *models.ReadingStreak) error {
	result := database.DB.Save(streak)
	if result.Error != nil {
		return errors.Internal("failed to update reading streak", result.Error.Error())
	}
	return nil
}
