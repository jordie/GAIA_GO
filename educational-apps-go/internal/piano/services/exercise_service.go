package services

import (
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/common/validation"
	"github.com/architect/educational-apps/internal/piano/models"
	"github.com/architect/educational-apps/internal/piano/repository"
)

// GetExercises retrieves exercises with optional difficulty filter
func GetExercises(difficulty *int, page, pageSize int) (*models.DatabasePaginatedResult, error) {
	if difficulty != nil {
		if err := validation.ValidateIntRange(*difficulty, 1, 5); err != nil {
			return nil, errors.BadRequest("invalid difficulty level: " + err.Error())
		}
	}

	if pageSize <= 0 || pageSize > 100 {
		pageSize = 20
	}
	if page <= 0 {
		page = 1
	}

	offset := (page - 1) * pageSize

	exercises, total, err := repository.GetExercises(difficulty, pageSize, offset)
	if err != nil {
		return nil, err
	}

	return &models.DatabasePaginatedResult{
		Total:      total,
		Page:       page,
		PageSize:   pageSize,
		TotalPages: (total + int64(pageSize) - 1) / int64(pageSize),
		Data:       exercises,
	}, nil
}

// GetExerciseByID retrieves a specific exercise
func GetExerciseByID(id uint) (*models.Exercise, error) {
	if id == 0 {
		return nil, errors.BadRequest("invalid exercise ID")
	}
	return repository.GetExerciseByID(id)
}

// CreateExercise creates a new exercise
func CreateExercise(req models.CreateExerciseRequest) (*models.Exercise, error) {
	// Validate input
	if err := validation.ValidateStringRange(req.Title, 1, 255); err != nil {
		return nil, errors.BadRequest("invalid title: " + err.Error())
	}

	if err := validation.ValidateIntRange(req.DifficultyLevel, 1, 5); err != nil {
		return nil, errors.BadRequest("invalid difficulty level: " + err.Error())
	}

	if err := validation.ValidateStringRange(req.NotesSequence, 1, 1000); err != nil {
		return nil, errors.BadRequest("invalid notes sequence: " + err.Error())
	}

	exercise := &models.Exercise{
		Title:           req.Title,
		Description:     req.Description,
		DifficultyLevel: req.DifficultyLevel,
		NotesSequence:   req.NotesSequence,
	}

	if err := repository.CreateExercise(exercise); err != nil {
		return nil, err
	}

	return exercise, nil
}

// UpdateExercise updates an existing exercise
func UpdateExercise(id uint, req models.CreateExerciseRequest) (*models.Exercise, error) {
	// Validate exercise exists
	exercise, err := GetExerciseByID(id)
	if err != nil {
		return nil, err
	}

	// Validate input
	if err := validation.ValidateStringRange(req.Title, 1, 255); err != nil {
		return nil, errors.BadRequest("invalid title: " + err.Error())
	}

	if err := validation.ValidateIntRange(req.DifficultyLevel, 1, 5); err != nil {
		return nil, errors.BadRequest("invalid difficulty level: " + err.Error())
	}

	updates := map[string]interface{}{
		"title":            req.Title,
		"description":      req.Description,
		"difficulty_level": req.DifficultyLevel,
		"notes_sequence":   req.NotesSequence,
	}

	if err := repository.UpdateExercise(id, updates); err != nil {
		return nil, err
	}

	// Fetch updated exercise
	exercise.Title = req.Title
	exercise.Description = req.Description
	exercise.DifficultyLevel = req.DifficultyLevel
	exercise.NotesSequence = req.NotesSequence

	return exercise, nil
}

// DeleteExercise deletes an exercise
func DeleteExercise(id uint) error {
	if id == 0 {
		return errors.BadRequest("invalid exercise ID")
	}
	return repository.DeleteExercise(id)
}
