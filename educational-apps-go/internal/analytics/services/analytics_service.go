package services

import (
	"time"

	"github.com/architect/educational-apps/internal/analytics/models"
	"github.com/architect/educational-apps/internal/analytics/repository"
	"github.com/architect/educational-apps/internal/common/errors"
)

// ========== XP & GAMIFICATION SERVICES ==========

// AwardXPAndCheckAchievements awards XP and checks for achievement unlocks
func AwardXPAndCheckAchievements(userID uint, amount int, source, reason string) error {
	// Award XP
	if err := repository.AwardXP(userID, amount, source, reason); err != nil {
		return err
	}

	// Check for achievements
	checkAndUnlockAchievements(userID)

	// Update user activity
	repository.UpdateStreak(userID)

	return nil
}

// GetUserGamificationProfile returns user's gamification status
func GetUserGamificationProfile(userID uint) (*models.GamificationProfileResponse, error) {
	// Get XP data
	xp, err := repository.GetUserXP(userID)
	if err != nil {
		return nil, err
	}

	// Get streak data
	streak, err := repository.GetUserStreak(userID)
	if err != nil {
		return nil, err
	}

	// Get achievements
	achievements, err := repository.GetUserAchievements(userID)
	if err != nil {
		achievements = make([]*models.UserAchievement, 0)
	}

	// Calculate XP to next level
	nextLevelXP := repository.GetXPForLevel(xp.Level + 1)
	xpToNextLevel := nextLevelXP - xp.TotalXP
	if xpToNextLevel < 0 {
		xpToNextLevel = 0
	}

	// Convert achievements to response
	achievementResponses := make([]models.UserAchievementResponse, len(achievements))
	for i, ach := range achievements {
		achievementResponses[i] = models.UserAchievementResponse{
			ID:        ach.ID,
			Slug:      ach.Achievement.Slug,
			Name:      ach.Achievement.Name,
			Icon:      ach.Achievement.Icon,
			Category:  ach.Achievement.Category,
			UnlockedAt: ach.UnlockedAt,
		}
	}

	return &models.GamificationProfileResponse{
		UserID:        userID,
		Level:         xp.Level,
		CurrentXP:     xp.CurrentXP,
		TotalXP:       xp.TotalXP,
		XPToNextLevel: xpToNextLevel,
		CurrentStreak: streak.CurrentStreak,
		LongestStreak: streak.LongestStreak,
		Achievements:  achievementResponses,
	}, nil
}

// checkAndUnlockAchievements checks if user should unlock any achievements
func checkAndUnlockAchievements(userID uint) {
	xp, _ := repository.GetUserXP(userID)
	streak, _ := repository.GetUserStreak(userID)
	achievements, _ := repository.GetAchievements()

	for _, achievement := range achievements {
		// Check if already unlocked
		userAchievements, _ := repository.GetUserAchievements(userID)
		alreadyUnlocked := false
		for _, ua := range userAchievements {
			if ua.AchievementID == achievement.ID {
				alreadyUnlocked = true
				break
			}
		}

		if alreadyUnlocked {
			continue
		}

		// Check unlock conditions
		shouldUnlock := false

		switch achievement.Slug {
		case "streak_3":
			if streak.CurrentStreak >= 3 {
				shouldUnlock = true
			}
		case "streak_7":
			if streak.CurrentStreak >= 7 {
				shouldUnlock = true
			}
		case "streak_30":
			if streak.CurrentStreak >= 30 {
				shouldUnlock = true
			}
		case "level_5":
			if xp.Level >= 5 {
				shouldUnlock = true
			}
		case "level_10":
			if xp.Level >= 10 {
				shouldUnlock = true
			}
		}

		if shouldUnlock {
			repository.UnlockAchievement(userID, achievement.ID)
		}
	}
}

// ========== UNIFIED ANALYTICS SERVICES ==========

// GetUserProfile returns comprehensive user profile across all apps
func GetUserProfile(userID uint) (*models.UserProfileResponse, error) {
	// Get user XP
	xp, _ := repository.GetUserXP(userID)

	// Get streak
	streak, _ := repository.GetUserStreak(userID)

	// Get profile
	profile, _ := repository.GetOrCreateUserProfile(userID, "")

	// Get app progress for all apps
	allProgress, _ := repository.GetAllAppProgress(userID)
	appProgressMap := make(map[string]models.AppProgressResponse)
	for _, prog := range allProgress {
		appProgressMap[prog.App] = models.AppProgressResponse{
			App:                 prog.App,
			ActivitiesCompleted: prog.ActivitiesCompleted,
			BestScore:           prog.BestScore,
			AverageScore:        prog.AverageScore,
			TotalTimeSeconds:    prog.TotalTimeSeconds,
			Accuracy:            prog.Accuracy,
		}
	}

	// Get achievements
	achievements, _ := repository.GetUserAchievements(userID)
	achievementResponses := make([]models.UserAchievementResponse, len(achievements))
	for i, ach := range achievements {
		achievementResponses[i] = models.UserAchievementResponse{
			ID:        ach.ID,
			Slug:      ach.Achievement.Slug,
			Name:      ach.Achievement.Name,
			Icon:      ach.Achievement.Icon,
			Category:  ach.Achievement.Category,
			UnlockedAt: ach.UnlockedAt,
		}
	}

	// Calculate total practice time
	totalTime := 0
	for _, prog := range allProgress {
		totalTime += prog.TotalTimeSeconds
	}

	return &models.UserProfileResponse{
		UserID:            userID,
		Username:          profile.Username,
		DisplayName:       profile.DisplayName,
		Level:             xp.Level,
		TotalXP:           xp.TotalXP,
		CurrentStreak:     streak.CurrentStreak,
		LongestStreak:     streak.LongestStreak,
		TotalPracticeTime: totalTime,
		LastActive:        profile.LastActive,
		AppProgress:       appProgressMap,
		Achievements:      achievementResponses,
	}, nil
}

// ========== LEADERBOARD SERVICES ==========

// GetLeaderboard returns ranked users
func GetLeaderboard(period string, limit int) (*models.LeaderboardResponse, error) {
	if limit > 100 {
		limit = 100
	}
	if limit < 1 {
		limit = 10
	}

	entries, err := repository.GetLeaderboard(period, limit)
	if err != nil {
		return nil, err
	}

	// Fetch usernames for entries
	for i := range entries {
		profile, _ := repository.GetOrCreateUserProfile(entries[i].UserID, "")
		entries[i].Username = profile.Username
	}

	return &models.LeaderboardResponse{
		Period:    period,
		Entries:   entries,
		UpdatedAt: time.Now(),
	}, nil
}

// ========== RECOMMENDATION SERVICES ==========

// GetRecommendations generates personalized recommendations
func GetRecommendations(userID uint) ([]string, error) {
	recommendations := make([]string, 0)

	// Get app progress
	allProgress, err := repository.GetAllAppProgress(userID)
	if err != nil {
		return recommendations, nil
	}

	// Find weak areas
	for _, prog := range allProgress {
		if prog.Accuracy < 50 && prog.ActivitiesCompleted > 0 {
			recommendations = append(recommendations, "Your "+prog.App+" accuracy is low. Focus on practice!")
		} else if prog.ActivitiesCompleted == 0 {
			recommendations = append(recommendations, "Start practicing "+prog.App+" to build skills!")
		}
	}

	// Check streak
	streak, _ := repository.GetUserStreak(userID)
	if streak.CurrentStreak == 0 {
		recommendations = append(recommendations, "Start a streak! Practice daily for rewards.")
	} else if streak.CurrentStreak < 7 {
		recommendations = append(recommendations, "Keep your streak alive! " + string(rune(7-streak.CurrentStreak)) + " more days to a badge!")
	}

	// Check XP progress
	xp, _ := repository.GetUserXP(userID)
	if xp.Level < 3 {
		recommendations = append(recommendations, "You're early in your journey. Keep practicing!")
	}

	return recommendations, nil
}

// ========== GOAL TRACKING SERVICES ==========

// CreateLearningGoal creates a new learning goal
func CreateLearningGoal(userID uint, title, description, app string, targetValue int, targetDate time.Time) (uint, error) {
	goal := &models.LearningGoal{
		UserID:      userID,
		Title:       title,
		Description: description,
		App:         app,
		TargetValue: targetValue,
		TargetDate:  targetDate,
		Status:      "active",
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	}

	return repository.CreateGoal(goal)
}

// UpdateGoalStatus updates goal status
func UpdateGoalStatus(goalID, userID uint, status string) error {
	goal := &models.LearningGoal{
		ID:     goalID,
		Status: status,
	}

	return repository.UpdateGoal(goal)
}

// ========== PROGRESS AGGREGATION ==========

// AggregateUserStats combines statistics from all apps
func AggregateUserStats(userID uint) (map[string]interface{}, error) {
	stats := make(map[string]interface{})

	// Get all app progress
	allProgress, _ := repository.GetAllAppProgress(userID)

	totalActivities := 0
	totalAccuracy := 0.0
	appStats := make(map[string]interface{})

	for _, prog := range allProgress {
		totalActivities += prog.ActivitiesCompleted
		if prog.ActivitiesCompleted > 0 {
			totalAccuracy += prog.Accuracy
		}

		appStats[prog.App] = map[string]interface{}{
			"activities_completed": prog.ActivitiesCompleted,
			"accuracy":             prog.Accuracy,
			"best_score":           prog.BestScore,
			"average_score":        prog.AverageScore,
			"total_time":           prog.TotalTimeSeconds,
		}
	}

	avgAccuracy := 0.0
	if len(allProgress) > 0 {
		avgAccuracy = totalAccuracy / float64(len(allProgress))
	}

	xp, _ := repository.GetUserXP(userID)
	streak, _ := repository.GetUserStreak(userID)

	stats["total_activities"] = totalActivities
	stats["average_accuracy"] = avgAccuracy
	stats["level"] = xp.Level
	stats["total_xp"] = xp.TotalXP
	stats["current_streak"] = streak.CurrentStreak
	stats["app_stats"] = appStats

	return stats, nil
}

// ========== ACTIVITY TRACKING ==========

// LogUserActivity logs a user action
func LogUserActivity(userID uint, app, eventType, details string) error {
	return repository.LogActivity(userID, app, eventType, details)
}

// GetRecentActivity retrieves user's recent activities
func GetRecentActivity(userID uint, limit int) ([]*models.ActivityLogEntry, error) {
	return repository.GetUserActivity(userID, limit)
}

// ========== STREAKS & BONUSES ==========

// CalculateStreakBonus returns XP bonus for streak
func CalculateStreakBonus(days int) int {
	bonuses := map[int]int{
		3:  10,
		7:  50,
		14: 100,
		30: 200,
		60: 500,
		100: 1000,
	}

	// Find highest qualifying bonus
	bonus := 0
	for streak, bonusXP := range bonuses {
		if days >= streak && bonusXP > bonus {
			bonus = bonusXP
		}
	}

	return bonus
}

// ========== ADMIN SERVICES ==========

// GetAdminStudentsList retrieves all students with stats (admin only)
func GetAdminStudentsList(limit, offset int) ([]map[string]interface{}, int64, error) {
	students := make([]map[string]interface{}, 0)

	// This would query all users and aggregate their stats
	// Implementation depends on having a central users table

	return students, 0, errors.Internal("admin features coming in extended version", "")
}

// GetAdminStudentDetails retrieves full details for a student (admin only)
func GetAdminStudentDetails(userID uint) (map[string]interface{}, error) {
	details := make(map[string]interface{})

	profile, _ := GetUserProfile(userID)
	stats, _ := AggregateUserStats(userID)
	goals, _ := repository.GetUserGoals(userID)
	notes, _ := repository.GetUserNotes(userID)
	activity, _ := repository.GetUserActivity(userID, 20)

	details["profile"] = profile
	details["stats"] = stats
	details["goals"] = goals
	details["notes"] = notes
	details["recent_activity"] = activity

	return details, nil
}
