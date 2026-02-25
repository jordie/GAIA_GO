package repository

import (
	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/math/models"
	"gorm.io/gorm"
)

// GetMasteryByFact retrieves mastery for a specific fact
func GetMasteryByFact(userID uint, fact, mode string) (*models.Mastery, error) {
	var mastery models.Mastery
	result := database.DB.
		Where("user_id = ? AND fact = ? AND mode = ?", userID, fact, mode).
		First(&mastery)

	if result.Error != nil {
		if result.Error == gorm.ErrRecordNotFound {
			return nil, nil // No record yet
		}
		return nil, errors.Internal("failed to fetch mastery", result.Error.Error())
	}

	return &mastery, nil
}

// UpdateMastery updates mastery tracking for a fact
func UpdateMastery(mastery *models.Mastery) error {
	result := database.DB.Save(mastery)
	if result.Error != nil {
		return errors.Internal("failed to update mastery", result.Error.Error())
	}
	return nil
}

// CreateMastery creates new mastery record
func CreateMastery(mastery *models.Mastery) error {
	result := database.DB.Create(mastery)
	if result.Error != nil {
		return errors.Internal("failed to create mastery", result.Error.Error())
	}
	return nil
}

// GetUserMasteries retrieves all masteries for a user
func GetUserMasteries(userID uint) ([]*models.Mastery, error) {
	var masteries []*models.Mastery

	result := database.DB.
		Where("user_id = ?", userID).
		Order("mastery_level DESC").
		Find(&masteries)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch masteries", result.Error.Error())
	}

	return masteries, nil
}

// GetMistakes retrieves user's mistakes
func GetMistakes(userID uint, mode string) ([]*models.Mistake, error) {
	var mistakes []*models.Mistake

	query := database.DB.Where("user_id = ?", userID)
	if mode != "" {
		query = query.Where("mode = ?", mode)
	}

	result := query.
		Order("error_count DESC, last_error DESC").
		Limit(20).
		Find(&mistakes)

	if result.Error != nil {
		return nil, errors.Internal("failed to fetch mistakes", result.Error.Error())
	}

	return mistakes, nil
}

// UpdateMistake updates mistake count
func UpdateMistake(userID uint, question string, mode string) error {
	result := database.DB.
		Where("user_id = ? AND question = ? AND mode = ?", userID, question, mode).
		Update("error_count", gorm.Expr("error_count + 1")).
		Update("last_error", gorm.Expr("CURRENT_TIMESTAMP"))

	if result.Error != nil {
		return errors.Internal("failed to update mistake", result.Error.Error())
	}

	return nil
}

// CreateMistake creates new mistake record
func CreateMistake(mistake *models.Mistake) error {
	result := database.DB.Create(mistake)
	if result.Error != nil {
		return errors.Internal("failed to create mistake", result.Error.Error())
	}
	return nil
}
