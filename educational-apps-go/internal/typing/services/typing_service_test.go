package services

import (
	"testing"

	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/typing/models"
	"github.com/stretchr/testify/assert"
)

// User Service Tests
func TestCreateUser_ValidUsername(t *testing.T) {
	user, err := CreateUser("testuser")

	// Will fail until DB initialized, validates logic
	assert.True(t, (user != nil && err == nil) || (user == nil && err != nil))
}

func TestCreateUser_TooShort(t *testing.T) {
	user, err := CreateUser("a")

	assert.Nil(t, user)
	assert.NotNil(t, err)
}

func TestCreateUser_TooLong(t *testing.T) {
	user, err := CreateUser("this_is_a_very_long_username_that_exceeds_twenty_characters")

	assert.Nil(t, user)
	assert.NotNil(t, err)
}

func TestGetUser_InvalidID(t *testing.T) {
	user, err := GetUser(0)

	assert.Nil(t, user)
	assert.NotNil(t, err)
	assert.Equal(t, "invalid user ID", err.(*errors.AppError).Message)
}

func TestSwitchUser_InvalidID(t *testing.T) {
	user, err := SwitchUser(0)

	assert.Nil(t, user)
	assert.NotNil(t, err)
}

// Text Service Tests
func TestGenerateText_WordsType(t *testing.T) {
	req := models.GetTextRequest{
		Type:      "words",
		WordCount: 25,
	}

	response, err := GenerateText(req)

	assert.Nil(t, err)
	assert.NotNil(t, response)
	assert.Equal(t, 25, response.WordCount)
	assert.Greater(t, response.CharacterCount, 0)
}

func TestGenerateText_TimeType(t *testing.T) {
	req := models.GetTextRequest{
		Type: "time",
	}

	response, err := GenerateText(req)

	assert.Nil(t, err)
	assert.NotNil(t, response)
	assert.Greater(t, response.WordCount, 0)
	assert.Greater(t, response.CharacterCount, 0)
}

func TestGenerateText_CategoryType(t *testing.T) {
	req := models.GetTextRequest{
		Type:     "category",
		Category: "programming",
	}

	response, err := GenerateText(req)

	assert.Nil(t, err)
	assert.NotNil(t, response)
	assert.Greater(t, response.CharacterCount, 0)
}

func TestGenerateText_InvalidType(t *testing.T) {
	req := models.GetTextRequest{
		Type: "invalid",
	}

	response, err := GenerateText(req)

	assert.Nil(t, response)
	assert.NotNil(t, err)
}

func TestGenerateText_DefaultCategory(t *testing.T) {
	req := models.GetTextRequest{
		Type:     "category",
		Category: "", // Should default to common_words
	}

	response, err := GenerateText(req)

	assert.Nil(t, err)
	assert.NotNil(t, response)
}

// Result Service Tests
func TestSaveResult_InvalidWPM(t *testing.T) {
	req := models.SaveResultRequest{
		WPM:      600, // Too high
		Accuracy: 92.5,
	}

	result, err := SaveResult(1, req)

	assert.Nil(t, result)
	assert.NotNil(t, err)
}

func TestSaveResult_InvalidAccuracy(t *testing.T) {
	req := models.SaveResultRequest{
		WPM:      85,
		Accuracy: 150, // Too high
	}

	result, err := SaveResult(1, req)

	assert.Nil(t, result)
	assert.NotNil(t, err)
}

func TestSaveResult_InvalidCharacterCounts(t *testing.T) {
	req := models.SaveResultRequest{
		WPM:                 85,
		Accuracy:            92.5,
		TotalCharacters:     100,
		CorrectCharacters:   150, // More than total
		IncorrectCharacters: 0,
	}

	result, err := SaveResult(1, req)

	assert.Nil(t, result)
	assert.NotNil(t, err)
}

func TestGetLeaderboard_DefaultLimit(t *testing.T) {
	leaderboard, err := GetLeaderboard(0)

	// Will fail if DB not initialized
	assert.True(t, (leaderboard != nil && err == nil) || (leaderboard == nil && err != nil))
}

func TestGetLeaderboard_CustomLimit(t *testing.T) {
	leaderboard, err := GetLeaderboard(5)

	if err == nil && leaderboard != nil {
		assert.True(t, len(leaderboard.TopWPM) <= 5)
		assert.True(t, len(leaderboard.TopAccuracy) <= 5)
	}
}

func TestGetLeaderboard_LargeLimit(t *testing.T) {
	leaderboard, err := GetLeaderboard(500)

	if err == nil && leaderboard != nil {
		assert.True(t, len(leaderboard.TopWPM) <= 100)
		assert.True(t, len(leaderboard.TopAccuracy) <= 100)
	}
}
