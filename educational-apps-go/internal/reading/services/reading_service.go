package services

import (
	"fmt"
	"strings"
	"time"

	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/reading/models"
	"github.com/architect/educational-apps/internal/reading/repository"
)

// GetWords retrieves available words for reading practice
func GetWords(limit int) ([]*models.Word, error) {
	var words []*models.Word
	result := database.DB.Limit(limit).Find(&words)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch words", result.Error.Error())
	}
	return words, nil
}

// SaveReadingResult saves a reading practice session and updates word performance
func SaveReadingResult(userID uint, req models.SaveReadingResultRequest) (*models.ReadingResult, error) {
	// Create reading result record
	result := &models.ReadingResult{
		UserID:          userID,
		ExpectedWords:   strings.Join(req.ExpectedWords, ","),
		RecognizedText:  req.RecognizedText,
		Accuracy:        req.Accuracy,
		WordsCorrect:    req.WordsCorrect,
		WordsTotal:      req.WordsTotal,
		ReadingSpeed:    req.ReadingSpeed,
		SessionDuration: req.SessionDuration,
	}

	if err := repository.CreateReadingResult(result); err != nil {
		return nil, err
	}

	// Update word-level performance
	recognizedWords := strings.Fields(strings.ToLower(req.RecognizedText))
	for _, expectedWord := range req.ExpectedWords {
		isCorrect := false
		for _, recognized := range recognizedWords {
			if strings.EqualFold(expectedWord, recognized) {
				isCorrect = true
				break
			}
		}

		if err := repository.UpdateWordPerformance(strings.ToLower(expectedWord), isCorrect); err != nil {
			// Log error but continue processing other words
			continue
		}
	}

	return result, nil
}

// GetReadingStats retrieves comprehensive reading statistics for a user
func GetReadingStats(userID uint) (*models.ReadingStatsResponse, error) {
	stats := &models.ReadingStatsResponse{
		UserID:        userID,
		WeakWords:     make([]*models.WordPerformance, 0),
		StrengthWords: make([]*models.WordPerformance, 0),
	}

	// Get reading result statistics
	resultStats, err := repository.GetReadingStats(userID)
	if err == nil && resultStats != nil {
		if v, ok := resultStats["total_sessions"]; ok {
			stats.TotalSessions = int(v.(int64))
		}
		if v, ok := resultStats["average_accuracy"]; ok {
			stats.AverageAccuracy = v.(float64)
		}
		if v, ok := resultStats["average_speed"]; ok {
			stats.AverageSpeed = v.(float64)
		}
		if v, ok := resultStats["best_accuracy"]; ok {
			stats.BestAccuracy = v.(float64)
		}
		if v, ok := resultStats["best_speed"]; ok {
			stats.BestSpeed = v.(float64)
		}
	}

	// Get recent sessions
	sessions, err := repository.GetUserReadingResults(userID, 10)
	if err == nil {
		stats.RecentSessions = sessions
	}

	// Get weak words
	weakWords, err := repository.GetWeakWords(userID, 10)
	if err == nil {
		stats.WeakWords = weakWords
		stats.WordsInProgress = len(weakWords)
	}

	// Get mastered words
	masteredWords, err := repository.GetMasteredWords(userID, 10)
	if err == nil {
		stats.StrengthWords = masteredWords
		stats.WordsMastered = len(masteredWords)
	}

	// Get learning profile
	profile, err := GetOrCreateLearningProfile(userID)
	if err == nil {
		stats.LearningProfile = profile
	}

	// Get reading streak
	streak, err := GetReadingStreak(userID)
	if err == nil {
		stats.CurrentStreak = streak.CurrentStreak
		stats.LongestStreak = streak.LongestStreak
	}

	return stats, nil
}

// GetWeakAreas identifies areas needing practice
func GetWeakAreas(userID uint) (*models.WeakAreasResponse, error) {
	weakWords, err := repository.GetWeakWords(userID, 15)
	if err != nil {
		return nil, err
	}

	response := &models.WeakAreasResponse{
		WeakWords:   make([]*models.WordPerformance, len(weakWords)),
		Suggestions: []string{},
	}

	for i, w := range weakWords {
		response.WeakWords[i] = w
		suggestion := generateWordSuggestion(w.Word)
		response.Suggestions = append(response.Suggestions, suggestion)
	}

	return response, nil
}

// GeneratePracticePlan creates personalized reading practice recommendations
func GeneratePracticePlan(userID uint) (*models.PracticePlanResponse, error) {
	// Get user stats
	stats, err := repository.GetReadingStats(userID)
	if err != nil {
		return nil, err
	}

	plan := &models.PracticePlanResponse{
		RecommendedLevel: "intermediate",
		FocusWords:       []string{},
		EstimatedTime:    600,
		Rationale:        "Continue practicing to improve reading speed and accuracy",
	}

	// Analyze performance patterns
	if stats != nil && len(stats) > 0 {
		if avgAccuracy, ok := stats["average_accuracy"].(float64); ok {
			if avgAccuracy > 85 {
				plan.RecommendedLevel = "advanced"
			} else if avgAccuracy < 70 {
				plan.RecommendedLevel = "beginner"
			}
		}
	}

	// Get weak areas and recommend focus
	weakWords, err := repository.GetWeakWords(userID, 5)
	if err == nil && len(weakWords) > 0 {
		for _, w := range weakWords {
			plan.FocusWords = append(plan.FocusWords, w.Word)
		}
		plan.EstimatedTime = 900
		plan.Rationale = "Focus on your weakest words to improve overall reading performance"
	}

	return plan, nil
}

// generateWordSuggestion creates learning suggestion for a word
func generateWordSuggestion(word string) string {
	return fmt.Sprintf("Practice the word '%s' - review its meaning and practice recognition", word)
}

// GetOrCreateLearningProfile retrieves or creates user's learning profile
func GetOrCreateLearningProfile(userID uint) (*models.LearningProfile, error) {
	profile, err := repository.GetLearningProfile(userID)
	if err != nil {
		return nil, err
	}

	if profile != nil {
		return profile, nil
	}

	// Create new profile with defaults
	newProfile := &models.LearningProfile{
		UserID:                userID,
		PreferredReadingLevel: "intermediate",
		AverageReadingSpeed:   200.0, // Default WPM
		AverageAccuracy:       75.0,
		ProfileUpdated:        time.Now(),
	}

	if err := repository.CreateLearningProfile(newProfile); err != nil {
		return nil, err
	}

	return newProfile, nil
}

// UpdateLearningProfile updates user's learning profile based on performance
func UpdateLearningProfile(userID uint) error {
	profile, err := GetOrCreateLearningProfile(userID)
	if err != nil {
		return err
	}

	// Get recent statistics
	stats, err := repository.GetReadingStats(userID)
	if err == nil && stats != nil {
		if avgAccuracy, ok := stats["average_accuracy"].(float64); ok {
			profile.AverageAccuracy = avgAccuracy
		}
		if avgSpeed, ok := stats["average_speed"].(float64); ok {
			profile.AverageReadingSpeed = avgSpeed
		}
		if totalSessions, ok := stats["total_sessions"].(int64); ok {
			profile.TotalWordsLearned = int(totalSessions) * 10 // Estimate
		}
	}

	profile.ProfileUpdated = time.Now()
	return repository.UpdateLearningProfile(profile)
}

// GetReadingStreak retrieves user's reading streak
func GetReadingStreak(userID uint) (*models.ReadingStreak, error) {
	streak, err := repository.GetReadingStreak(userID)
	if err != nil {
		return nil, err
	}

	if streak != nil {
		// Check if streak is still active (practiced today)
		now := time.Now()
		lastPracticedDate := streak.LastPracticed.Truncate(24 * time.Hour)
		todayDate := now.Truncate(24 * time.Hour)

		if lastPracticedDate == todayDate {
			// Streak is active
			return streak, nil
		} else if lastPracticedDate.AddDate(0, 0, 1) == todayDate {
			// Streak can continue if practice happens today
			return streak, nil
		} else {
			// Streak broken
			streak.CurrentStreak = 0
			repository.UpdateReadingStreak(streak)
			return streak, nil
		}
	}

	// Create new streak
	newStreak := &models.ReadingStreak{
		UserID:          userID,
		CurrentStreak:   1,
		LongestStreak:   1,
		LastPracticed:   time.Now(),
		StreakStartDate: time.Now(),
	}

	if err := repository.CreateReadingStreak(newStreak); err != nil {
		return nil, err
	}

	return newStreak, nil
}

// UpdateReadingStreak increments reading streak
func UpdateReadingStreak(userID uint) error {
	streak, err := GetReadingStreak(userID)
	if err != nil {
		return err
	}

	streak.CurrentStreak++
	streak.LastPracticed = time.Now()

	if streak.CurrentStreak > streak.LongestStreak {
		streak.LongestStreak = streak.CurrentStreak
	}

	return repository.UpdateReadingStreak(streak)
}

// AddWord creates a new word in the vocabulary database
// Performs duplicate checking and initializes word performance tracking
func AddWord(word string) (*models.AddWordResponse, error) {
	// Normalize the word (trim, lowercase for duplicate checking)
	normalizedWord := strings.TrimSpace(strings.ToLower(word))

	// Check if word already exists (case-insensitive)
	existingPerformance, err := repository.GetWordPerformance(normalizedWord)
	if err != nil {
		return nil, err
	}

	if existingPerformance != nil {
		return nil, errors.Conflict("word already exists in vocabulary")
	}

	// Create new word record
	newWord := &models.Word{
		Word: normalizedWord,
	}

	if err := repository.CreateWord(newWord); err != nil {
		return nil, err
	}

	// Initialize word performance tracking with 0 mastery
	wordPerf := &models.WordPerformance{
		Word:           normalizedWord,
		CorrectCount:   0,
		IncorrectCount: 0,
		Mastery:        0.0,
		LastPracticed:  time.Now(),
	}

	if err := repository.CreateWordPerformance(wordPerf); err != nil {
		// Log error but don't fail - word was created successfully
		// The performance will be created on first use
		return nil, err
	}

	// Return success response
	return &models.AddWordResponse{
		ID:        newWord.ID,
		Word:      newWord.Word,
		CreatedAt: newWord.CreatedAt,
		Message:   "Word added successfully to vocabulary",
	}, nil
}
