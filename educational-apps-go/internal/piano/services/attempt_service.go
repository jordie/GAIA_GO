package services

import (
	"fmt"

	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/common/validation"
	"github.com/architect/educational-apps/internal/piano/models"
	"github.com/architect/educational-apps/internal/piano/repository"
)

// RecordAttempt records a user's attempt at an exercise
func RecordAttempt(userID uint, req models.CreateAttemptRequest) (*models.Attempt, error) {
	// Validate exercise exists
	exercise, err := GetExerciseByID(req.ExerciseID)
	if err != nil {
		return nil, err
	}

	// Validate input
	if err := validation.ValidateStringRange(req.NotesPlayed, 1, 1000); err != nil {
		return nil, errors.BadRequest("invalid notes played: " + err.Error())
	}

	// Validate accuracy if provided
	if req.AccuracyPercentage != nil {
		if err := validation.ValidateFloatRange(*req.AccuracyPercentage, 0, 100); err != nil {
			return nil, errors.BadRequest("accuracy must be between 0 and 100")
		}
	}

	// Validate response time if provided
	if req.ResponseTimeMs != nil && *req.ResponseTimeMs < 0 {
		return nil, errors.BadRequest("response time must be non-negative")
	}

	// Create attempt
	attempt := &models.Attempt{
		UserID:             userID,
		ExerciseID:         req.ExerciseID,
		NotesPlayed:        req.NotesPlayed,
		IsCorrect:          req.IsCorrect,
		AccuracyPercentage: req.AccuracyPercentage,
		ResponseTimeMs:     req.ResponseTimeMs,
	}

	if err := repository.CreateAttempt(attempt); err != nil {
		return nil, err
	}

	// Update user progress
	if err := updateProgressAfterAttempt(userID, exercise); err != nil {
		// Log error but don't fail the attempt record
		fmt.Printf("Failed to update progress: %v\n", err)
	}

	attempt.Exercise = exercise
	return attempt, nil
}

// GetUserAttempts retrieves all attempts for a user
func GetUserAttempts(userID uint, page, pageSize int) (*models.DatabasePaginatedResult, error) {
	if pageSize <= 0 || pageSize > 100 {
		pageSize = 20
	}
	if page <= 0 {
		page = 1
	}

	offset := (page - 1) * pageSize

	attempts, total, err := repository.GetAttemptsByUserID(userID, pageSize, offset)
	if err != nil {
		return nil, err
	}

	return &models.DatabasePaginatedResult{
		Total:      total,
		Page:       page,
		PageSize:   pageSize,
		TotalPages: (total + int64(pageSize) - 1) / int64(pageSize),
		Data:       attempts,
	}, nil
}

// GetExerciseAttempts retrieves all attempts for an exercise
func GetExerciseAttempts(exerciseID uint, page, pageSize int) (*models.DatabasePaginatedResult, error) {
	if pageSize <= 0 || pageSize > 100 {
		pageSize = 20
	}
	if page <= 0 {
		page = 1
	}

	offset := (page - 1) * pageSize

	attempts, total, err := repository.GetAttemptsByExerciseID(exerciseID, pageSize, offset)
	if err != nil {
		return nil, err
	}

	return &models.DatabasePaginatedResult{
		Total:      total,
		Page:       page,
		PageSize:   pageSize,
		TotalPages: (total + int64(pageSize) - 1) / int64(pageSize),
		Data:       attempts,
	}, nil
}

// GetUserExerciseStats retrieves performance stats for a user on a specific exercise
func GetUserExerciseStats(userID, exerciseID uint) (map[string]interface{}, error) {
	stats, err := repository.GetUserExerciseStats(userID, exerciseID)
	if err != nil {
		return nil, err
	}
	return stats, nil
}

// calculateAccuracy compares notes played to expected notes
func calculateAccuracy(expectedNotes, playedNotes string) float64 {
	if len(expectedNotes) == 0 {
		return 0
	}

	matches := 0
	for i := 0; i < len(expectedNotes) && i < len(playedNotes); i++ {
		if expectedNotes[i] == playedNotes[i] {
			matches++
		}
	}

	return (float64(matches) / float64(len(expectedNotes))) * 100
}

// updateProgressAfterAttempt updates user progress based on attempt result
func updateProgressAfterAttempt(userID uint, exercise *models.Exercise) error {
	// Get or create progress
	progress, err := repository.GetProgressByUserID(userID)
	if err != nil {
		// Create new progress record
		progress = &models.Progress{
			UserID:                     userID,
			CurrentDifficultyLevel:     1,
			TotalExercisesCompleted:    1,
			AverageAccuracyPercentage: 0,
		}
		return repository.CreateProgress(progress)
	}

	// Update progress
	updates := map[string]interface{}{
		"total_exercises_completed": progress.TotalExercisesCompleted + 1,
	}

	// Update difficulty level if exercise is harder
	if exercise.DifficultyLevel > progress.CurrentDifficultyLevel {
		updates["current_difficulty_level"] = exercise.DifficultyLevel
	}

	return repository.UpdateProgress(userID, updates)
}
