package services

import (
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/common/validation"
	"github.com/architect/educational-apps/internal/typing/models"
	"github.com/architect/educational-apps/internal/typing/repository"
)

// SaveResult records a typing test result and updates user stats
func SaveResult(userID uint, req models.SaveResultRequest) (*models.TypingResult, error) {
	// Validate user exists
	if _, err := GetUser(userID); err != nil {
		return nil, err
	}

	// Validate input
	if err := validation.ValidateIntRange(req.WPM, 0, 500); err != nil {
		return nil, errors.BadRequest("invalid WPM value")
	}

	if err := validation.ValidateFloatRange(req.Accuracy, 0, 100); err != nil {
		return nil, errors.BadRequest("invalid accuracy value")
	}

	if req.TotalCharacters < req.CorrectCharacters || req.TotalCharacters < req.IncorrectCharacters {
		return nil, errors.BadRequest("invalid character counts")
	}

	// Create result
	result := &models.TypingResult{
		UserID:              userID,
		ExerciseID:          req.ExerciseID,
		WPM:                 req.WPM,
		Accuracy:            req.Accuracy,
		TestType:            req.TestType,
		TestDuration:        req.TestDuration,
		TotalCharacters:     req.TotalCharacters,
		CorrectCharacters:   req.CorrectCharacters,
		IncorrectCharacters: req.IncorrectCharacters,
	}

	if err := repository.CreateResult(result); err != nil {
		return nil, err
	}

	// Update user stats
	if err := repository.UpdateStats(userID, result); err != nil {
		// Log error but don't fail the result save
	}

	return result, nil
}

// GetUserResults retrieves paginated results for a user
func GetUserResults(userID uint, page, pageSize int) (*models.PaginatedTypingResults, error) {
	if _, err := GetUser(userID); err != nil {
		return nil, err
	}

	if pageSize <= 0 || pageSize > 100 {
		pageSize = 20
	}
	if page <= 0 {
		page = 1
	}

	offset := (page - 1) * pageSize

	results, total, err := repository.GetUserResults(userID, pageSize, offset)
	if err != nil {
		return nil, err
	}

	// Convert to response format
	responses := make([]models.TypingResultResponse, len(results))
	for i, r := range results {
		responses[i] = models.TypingResultResponse{
			ID:                  r.ID,
			WPM:                 r.WPM,
			Accuracy:            r.Accuracy,
			TestType:            r.TestType,
			TestDuration:        r.TestDuration,
			TotalCharacters:     r.TotalCharacters,
			CorrectCharacters:   r.CorrectCharacters,
			IncorrectCharacters: r.IncorrectCharacters,
			CreatedAt:           r.CreatedAt,
		}
	}

	return &models.PaginatedTypingResults{
		Total:      total,
		Page:       page,
		PageSize:   pageSize,
		TotalPages: (total + int64(pageSize) - 1) / int64(pageSize),
		Data:       responses,
	}, nil
}

// GetLeaderboard retrieves top performers
func GetLeaderboard(limit int) (*models.LeaderboardResponse, error) {
	if limit <= 0 || limit > 100 {
		limit = 10
	}

	// Get top WPM scores
	topWPMResults, err := repository.GetTopWPMScores(limit)
	if err != nil {
		return nil, err
	}

	topWPM := make([]models.LeaderboardEntry, len(topWPMResults))
	for i, r := range topWPMResults {
		username := "Unknown"
		if r.User != nil {
			username = r.User.Username
		}
		topWPM[i] = models.LeaderboardEntry{
			Rank:     i + 1,
			Username: username,
			WPM:      r.WPM,
			Accuracy: r.Accuracy,
			TestType: r.TestType,
			Date:     r.CreatedAt,
		}
	}

	// Get top accuracy scores (minimum 30 WPM)
	topAccuracyResults, err := repository.GetTopAccuracyScores(30, limit)
	if err != nil {
		return nil, err
	}

	topAccuracy := make([]models.LeaderboardEntry, len(topAccuracyResults))
	for i, r := range topAccuracyResults {
		username := "Unknown"
		if r.User != nil {
			username = r.User.Username
		}
		topAccuracy[i] = models.LeaderboardEntry{
			Rank:     i + 1,
			Username: username,
			WPM:      r.WPM,
			Accuracy: r.Accuracy,
			TestType: r.TestType,
			Date:     r.CreatedAt,
		}
	}

	return &models.LeaderboardResponse{
		TopWPM:      topWPM,
		TopAccuracy: topAccuracy,
	}, nil
}
