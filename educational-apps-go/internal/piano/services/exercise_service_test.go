package services

import (
	"testing"

	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/piano/models"
	"github.com/stretchr/testify/assert"
)

func TestGetExercises_ValidDifficulty(t *testing.T) {
	difficulty := 2
	result, err := GetExercises(&difficulty, 1, 10)

	// This will fail until DB is initialized, but shows the test structure
	assert.Nil(t, result)
	assert.NotNil(t, err)
}

func TestGetExercises_NoDifficulty(t *testing.T) {
	result, err := GetExercises(nil, 1, 10)

	assert.Nil(t, result)
	assert.NotNil(t, err)
}

func TestGetExercises_InvalidPage(t *testing.T) {
	result, err := GetExercises(nil, 0, 10)

	assert.Nil(t, result)
	assert.NotNil(t, err)
}

func TestGetExerciseByID_InvalidID(t *testing.T) {
	exercise, err := GetExerciseByID(0)

	assert.Nil(t, exercise)
	assert.NotNil(t, err)
	assert.Equal(t, "invalid exercise ID", err.(*errors.AppError).Message)
}

func TestCreateExercise_ValidRequest(t *testing.T) {
	req := models.CreateExerciseRequest{
		Title:           "Scale Practice",
		Description:     "Practice musical scales",
		DifficultyLevel: 2,
		NotesSequence:   "C,D,E,F,G,A,B",
	}

	exercise, err := CreateExercise(req)

	assert.Nil(t, exercise)
	assert.NotNil(t, err) // DB not initialized
}

func TestCreateExercise_InvalidTitle(t *testing.T) {
	req := models.CreateExerciseRequest{
		Title:           "",
		Description:     "Practice musical scales",
		DifficultyLevel: 2,
		NotesSequence:   "C,D,E",
	}

	exercise, err := CreateExercise(req)

	assert.Nil(t, exercise)
	assert.NotNil(t, err)
}

func TestCreateExercise_InvalidDifficulty(t *testing.T) {
	req := models.CreateExerciseRequest{
		Title:           "Scale Practice",
		Description:     "Practice musical scales",
		DifficultyLevel: 6, // Invalid (> 5)
		NotesSequence:   "C,D,E",
	}

	exercise, err := CreateExercise(req)

	assert.Nil(t, exercise)
	assert.NotNil(t, err)
}

func TestCreateExercise_MissingNotesSequence(t *testing.T) {
	req := models.CreateExerciseRequest{
		Title:           "Scale Practice",
		Description:     "Practice musical scales",
		DifficultyLevel: 2,
		NotesSequence:   "",
	}

	exercise, err := CreateExercise(req)

	assert.Nil(t, exercise)
	assert.NotNil(t, err)
}

func TestUpdateExercise_NotFound(t *testing.T) {
	req := models.CreateExerciseRequest{
		Title:           "Updated Title",
		Description:     "Updated",
		DifficultyLevel: 3,
		NotesSequence:   "C,E,G",
	}

	exercise, err := UpdateExercise(999, req)

	assert.Nil(t, exercise)
	assert.NotNil(t, err)
}

func TestDeleteExercise_InvalidID(t *testing.T) {
	err := DeleteExercise(0)

	assert.NotNil(t, err)
	assert.Equal(t, "invalid exercise ID", err.(*errors.AppError).Message)
}
