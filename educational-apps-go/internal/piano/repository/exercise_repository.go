package repository

import (
	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/piano/models"
)

// GetExercises retrieves all exercises, optionally filtered by difficulty
func GetExercises(difficulty *int, limit, offset int) ([]*models.Exercise, int64, error) {
	var exercises []*models.Exercise
	var total int64

	query := database.DB.Model(&models.Exercise{})

	if difficulty != nil {
		query = query.Where("difficulty_level = ?", *difficulty)
	}

	query.Count(&total)

	result := query.Limit(limit).Offset(offset).Find(&exercises)
	if result.Error != nil {
		return nil, 0, errors.Internal("failed to fetch exercises", result.Error.Error())
	}

	return exercises, total, nil
}

// GetExerciseByID retrieves an exercise by ID
func GetExerciseByID(id uint) (*models.Exercise, error) {
	var exercise models.Exercise
	result := database.DB.First(&exercise, id)
	if result.Error != nil {
		return nil, errors.NotFound("exercise")
	}
	return &exercise, nil
}

// CreateExercise creates a new exercise
func CreateExercise(exercise *models.Exercise) error {
	result := database.DB.Create(exercise)
	if result.Error != nil {
		return errors.Internal("failed to create exercise", result.Error.Error())
	}
	return nil
}

// UpdateExercise updates an existing exercise
func UpdateExercise(id uint, updates map[string]interface{}) error {
	result := database.DB.Model(&models.Exercise{}).Where("id = ?", id).Updates(updates)
	if result.Error != nil {
		return errors.Internal("failed to update exercise", result.Error.Error())
	}
	if result.RowsAffected == 0 {
		return errors.NotFound("exercise")
	}
	return nil
}

// DeleteExercise deletes an exercise
func DeleteExercise(id uint) error {
	result := database.DB.Delete(&models.Exercise{}, id)
	if result.Error != nil {
		return errors.Internal("failed to delete exercise", result.Error.Error())
	}
	if result.RowsAffected == 0 {
		return errors.NotFound("exercise")
	}
	return nil
}
