package services

import (
	"time"

	"github.com/architect/educational-apps/internal/math/models"
	"github.com/architect/educational-apps/internal/math/repository"
)

// GetWeakAreas identifies areas needing practice
func GetWeakAreas(userID uint, mode string) (*models.WeakAreasResponse, error) {
	if mode == "" {
		mode = "addition"
	}

	weaknesses, err := repository.GetWeakAreas(userID, mode)
	if err != nil {
		return nil, err
	}

	response := &models.WeakAreasResponse{
		Weaknesses: make([]map[string]interface{}, len(weaknesses)),
		Suggestions: []string{},
	}

	// Convert to response format and generate suggestions
	for i, w := range weaknesses {
		response.Weaknesses[i] = map[string]interface{}{
			"fact_family": w.FactFamily,
		}
	}

	// Generate suggestions based on weak areas
	if len(weaknesses) > 0 {
		for _, w := range weaknesses {
			suggestion := generateSuggestion(w.FactFamily, mode)
			response.Suggestions = append(response.Suggestions, suggestion)
		}
	}

	return response, nil
}

// GeneratePracticePlan creates personalized practice plan
func GeneratePracticePlan(userID uint) (*models.PracticePlanResponse, error) {
	// Get user stats
	stats, err := repository.GetSessionStatistics(userID)
	if err != nil {
		return nil, err
	}

	plan := &models.PracticePlanResponse{
		RecommendedMode:       "addition",
		RecommendedDifficulty: "easy",
		FocusAreas:            []string{},
		EstimatedTime:         600,
		Rationale:             "Start with basics",
	}

	// Analyze performance patterns
	patterns, _ := repository.GetPerformancePatterns(userID)
	if len(patterns) > 0 {
		// Get time with best performance
		bestTime, _ := repository.GetBestPerformanceTime(userID)
		plan.Rationale = "Practice during your peak learning time: " + getTimeOfDay(bestTime)
	}

	// Get weak areas and recommend focus
	weakAreas, _ := repository.GetWeakAreas(userID, "")
	if len(weakAreas) > 0 {
		plan.RecommendedMode = "mixed"
		plan.FocusAreas = []string{"doubles", "near_doubles", "plus_nine"}
		plan.EstimatedTime = 900
	}

	// Analyze accuracy and adjust difficulty
	if stats != nil {
		if v, ok := stats["average_accuracy"]; ok {
			if acc, ok := v.(float64); ok && acc > 85 {
				plan.RecommendedDifficulty = "medium"
			}
		}
	}

	return plan, nil
}

// AnalyzeLearningProfile analyzes and returns user's learning profile
func AnalyzeLearningProfile(userID uint) (*models.LearningProfile, error) {
	// Get existing profile
	profile, err := repository.GetLearningProfile(userID)
	if err != nil {
		return nil, err
	}

	if profile == nil {
		// Create new profile with defaults
		profile = &models.LearningProfile{
			UserID:             userID,
			LearningStyle:      "sequential",
			PreferredTimeOfDay: "afternoon",
			AttentionSpan:      300,
			ProfileUpdated:     time.Now(),
		}
		if err := repository.CreateLearningProfile(profile); err != nil {
			return nil, err
		}
	}

	// Update profile based on performance patterns
	patterns, err := repository.GetPerformancePatterns(userID)
	if err == nil && len(patterns) > 0 {
		// Find best time
		bestHour := 0
		bestAcc := 0.0
		for _, p := range patterns {
			if p.AverageAccuracy > bestAcc {
				bestAcc = p.AverageAccuracy
				bestHour = p.HourOfDay
			}
		}
		profile.PreferredTimeOfDay = getTimeOfDay(bestHour)

		// Get attention span from session data
		sessions, _ := repository.GetRecentSessions(userID, 5)
		if len(sessions) > 0 {
			totalTime := 0
			for _, s := range sessions {
				totalTime += int(s.TotalTime)
			}
			profile.AttentionSpan = totalTime / len(sessions)
		}

		profile.ProfileUpdated = time.Now()
		repository.UpdateLearningProfile(profile)
	}

	return profile, nil
}

// generateSuggestion creates learning suggestions based on weak area
func generateSuggestion(factFamily, mode string) string {
	suggestions := map[string]string{
		"doubles":        "Practice doubles (n+n) - memorize basic doubles first",
		"near_doubles":   "Focus on near doubles (n+n+1) - build on doubles",
		"plus_one":       "Master plus one facts - count by ones",
		"plus_nine":      "Learn the plus nine strategy - 10 minus 1",
		"make_ten":       "Practice making 10 - foundational for mental math",
		"times_two":      "Work on times two - doubling strategy",
		"times_five":     "Practice times five - counting by fives",
		"times_nine":     "Master times nine - finger trick method",
		"squares":        "Learn square numbers - 1, 4, 9, 16, 25...",
	}

	if suggestion, ok := suggestions[factFamily]; ok {
		return suggestion
	}
	return "Continue practicing " + factFamily
}

// getTimeOfDay converts hour to time of day string
func getTimeOfDay(hour int) string {
	if hour < 12 {
		return "morning"
	} else if hour < 17 {
		return "afternoon"
	}
	return "evening"
}
