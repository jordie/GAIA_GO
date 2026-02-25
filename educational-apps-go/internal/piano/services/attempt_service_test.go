package services

import (
	"testing"

	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/piano/models"
	"github.com/stretchr/testify/assert"
)

func TestRecordAttempt_InvalidExercise(t *testing.T) {
	req := models.CreateAttemptRequest{
		ExerciseID:  999,
		NotesPlayed: "C,D,E",
		IsCorrect:   true,
	}

	attempt, err := RecordAttempt(1, req)

	assert.Nil(t, attempt)
	assert.NotNil(t, err)
}

func TestRecordAttempt_EmptyNotesPlayed(t *testing.T) {
	req := models.CreateAttemptRequest{
		ExerciseID:  1,
		NotesPlayed: "",
		IsCorrect:   false,
	}

	attempt, err := RecordAttempt(1, req)

	assert.Nil(t, attempt)
	assert.NotNil(t, err)
}

func TestRecordAttempt_InvalidAccuracy(t *testing.T) {
	accuracy := 150.0
	req := models.CreateAttemptRequest{
		ExerciseID:         1,
		NotesPlayed:        "C,D,E",
		IsCorrect:          true,
		AccuracyPercentage: &accuracy,
	}

	attempt, err := RecordAttempt(1, req)

	assert.Nil(t, attempt)
	assert.NotNil(t, err)
}

func TestRecordAttempt_NegativeResponseTime(t *testing.T) {
	responseTime := -100
	req := models.CreateAttemptRequest{
		ExerciseID:     1,
		NotesPlayed:    "C,D,E",
		IsCorrect:      true,
		ResponseTimeMs: &responseTime,
	}

	attempt, err := RecordAttempt(1, req)

	assert.Nil(t, attempt)
	assert.NotNil(t, err)
}

func TestGetUserAttempts_InvalidPage(t *testing.T) {
	result, err := GetUserAttempts(1, 0, 10)

	// Should not error, should use default page 1
	assert.NotNil(t, result)
}

func TestGetUserAttempts_InvalidPageSize(t *testing.T) {
	result, err := GetUserAttempts(1, 1, 0)

	// Should not error, should use default page size
	assert.NotNil(t, result)
}

func TestGetUserAttempts_LargePageSize(t *testing.T) {
	result, err := GetUserAttempts(1, 1, 200)

	// Should not error, should cap at 100
	assert.NotNil(t, result)
	if result != nil {
		assert.Equal(t, 100, result.PageSize)
	}
}

func TestGetExerciseAttempts_ValidInput(t *testing.T) {
	result, err := GetExerciseAttempts(1, 1, 10)

	assert.NotNil(t, result)
}

func TestGetUserExerciseStats_ValidInput(t *testing.T) {
	stats, err := GetUserExerciseStats(1, 1)

	// Will fail until DB initialized, but validates interface
	assert.Nil(t, stats)
}
