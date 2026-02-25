package repository

import (
	"time"

	"github.com/architect/educational-apps/internal/common/database"
	"github.com/architect/educational-apps/internal/common/errors"
	"github.com/architect/educational-apps/internal/analytics/models"
)

// ========== USER XP REPOSITORY ==========

// GetUserXP retrieves user's XP data
func GetUserXP(userID uint) (*models.UserXP, error) {
	var xp models.UserXP
	result := database.DB.Where("user_id = ?", userID).First(&xp)
	if result.Error != nil {
		// Return default XP for new users
		return &models.UserXP{
			UserID:    userID,
			CurrentXP: 0,
			TotalXP:   0,
			Level:     1,
			CreatedAt: time.Now(),
			UpdatedAt: time.Now(),
		}, nil
	}
	return &xp, nil
}

// AwardXP awards XP to a user and checks for level-ups
func AwardXP(userID uint, amount int, source, reason string) error {
	xp, err := GetUserXP(userID)
	if err != nil {
		return err
	}

	xp.CurrentXP += amount
	xp.TotalXP += amount
	xp.LastXPUpdate = time.Now()
	xp.UpdatedAt = time.Now()

	// Check for level-ups
	newLevel := CalculateLevel(xp.TotalXP)
	if newLevel > xp.Level {
		xp.Level = newLevel
	}

	// Update or create
	result := database.DB.Save(xp)
	if result.Error != nil {
		return errors.Internal("failed to award XP", result.Error.Error())
	}

	// Log XP
	log := &models.XPLog{
		UserID:    userID,
		Amount:    amount,
		Source:    source,
		Reason:    reason,
		CreatedAt: time.Now(),
	}
	database.DB.Create(log)

	return nil
}

// GetXPLog retrieves XP logs for a user
func GetXPLog(userID uint, limit int) ([]*models.XPLog, error) {
	var logs []*models.XPLog
	result := database.DB.Where("user_id = ?", userID).Order("created_at DESC").Limit(limit).Find(&logs)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch XP logs", result.Error.Error())
	}
	return logs, nil
}

// ========== USER STREAK REPOSITORY ==========

// GetUserStreak retrieves user's streak data
func GetUserStreak(userID uint) (*models.UserStreak, error) {
	var streak models.UserStreak
	result := database.DB.Where("user_id = ?", userID).First(&streak)
	if result.Error != nil {
		// Return default streak for new users
		return &models.UserStreak{
			UserID:           userID,
			CurrentStreak:    0,
			LongestStreak:    0,
			LastActivityDate: time.Now().AddDate(0, 0, -1), // Yesterday
			CreatedAt:        time.Now(),
			UpdatedAt:        time.Now(),
		}, nil
	}
	return &streak, nil
}

// UpdateStreak updates user's activity streak
func UpdateStreak(userID uint) error {
	streak, err := GetUserStreak(userID)
	if err != nil {
		return err
	}

	today := time.Now().Truncate(24 * time.Hour)
	lastDate := streak.LastActivityDate.Truncate(24 * time.Hour)

	// Check if activity is today
	if today.Equal(lastDate) {
		// Already active today, no change needed
		return nil
	}

	// Check if activity is from yesterday
	yesterday := today.AddDate(0, 0, -1)
	if yesterday.Equal(lastDate) {
		// Continuing streak
		streak.CurrentStreak++
		if streak.CurrentStreak > streak.LongestStreak {
			streak.LongestStreak = streak.CurrentStreak
		}
	} else {
		// Breaking streak or first activity
		streak.CurrentStreak = 1
	}

	streak.LastActivityDate = time.Now()
	streak.UpdatedAt = time.Now()

	result := database.DB.Save(streak)
	if result.Error != nil {
		return errors.Internal("failed to update streak", result.Error.Error())
	}

	return nil
}

// ========== ACHIEVEMENT REPOSITORY ==========

// GetAchievements retrieves all achievements
func GetAchievements() ([]*models.Achievement, error) {
	var achievements []*models.Achievement
	result := database.DB.Find(&achievements)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch achievements", result.Error.Error())
	}
	return achievements, nil
}

// GetAchievementBySlug retrieves achievement by slug
func GetAchievementBySlug(slug string) (*models.Achievement, error) {
	var achievement models.Achievement
	result := database.DB.Where("slug = ?", slug).First(&achievement)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch achievement", result.Error.Error())
	}
	return &achievement, nil
}

// GetUserAchievements retrieves user's unlocked achievements
func GetUserAchievements(userID uint) ([]*models.UserAchievement, error) {
	var achievements []*models.UserAchievement
	result := database.DB.
		Where("user_id = ?", userID).
		Preload("Achievement").
		Order("unlocked_at DESC").
		Find(&achievements)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch user achievements", result.Error.Error())
	}
	return achievements, nil
}

// UnlockAchievement unlocks an achievement for a user
func UnlockAchievement(userID uint, achievementID uint) error {
	// Check if already unlocked
	var existing models.UserAchievement
	result := database.DB.Where("user_id = ? AND achievement_id = ?", userID, achievementID).First(&existing)
	if result.RowsAffected > 0 {
		return nil // Already unlocked
	}

	// Unlock achievement
	ua := &models.UserAchievement{
		UserID:        userID,
		AchievementID: achievementID,
		UnlockedAt:    time.Now(),
	}

	result = database.DB.Create(ua)
	if result.Error != nil {
		return errors.Internal("failed to unlock achievement", result.Error.Error())
	}

	// Get achievement to award XP
	achievement := &models.Achievement{}
	database.DB.First(achievement, achievementID)
	if achievement.XPReward > 0 {
		AwardXP(userID, achievement.XPReward, "achievement", achievement.Slug)
	}

	return nil
}

// CreateAchievement creates a new achievement
func CreateAchievement(achievement *models.Achievement) (uint, error) {
	result := database.DB.Create(achievement)
	if result.Error != nil {
		return 0, errors.Internal("failed to create achievement", result.Error.Error())
	}
	return achievement.ID, nil
}

// ========== USER PROFILE REPOSITORY ==========

// GetOrCreateUserProfile gets or creates user profile
func GetOrCreateUserProfile(userID uint, username string) (*models.UserProfile, error) {
	profile := &models.UserProfile{
		UserID:   userID,
		Username: username,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	result := database.DB.FirstOrCreate(profile, models.UserProfile{UserID: userID})
	if result.Error != nil {
		return nil, errors.Internal("failed to get/create profile", result.Error.Error())
	}

	return profile, nil
}

// UpdateUserProfile updates user profile
func UpdateUserProfile(profile *models.UserProfile) error {
	profile.UpdatedAt = time.Now()
	result := database.DB.Save(profile)
	if result.Error != nil {
		return errors.Internal("failed to update profile", result.Error.Error())
	}
	return nil
}

// ========== APP PROGRESS REPOSITORY ==========

// GetAppProgress retrieves progress for an app
func GetAppProgress(userID uint, app string) (*models.AppProgress, error) {
	var progress models.AppProgress
	result := database.DB.Where("user_id = ? AND app = ?", userID, app).First(&progress)
	if result.Error != nil {
		// Return default progress for new users
		return &models.AppProgress{
			UserID: userID,
			App:    app,
			CreatedAt: time.Now(),
			UpdatedAt: time.Now(),
		}, nil
	}
	return &progress, nil
}

// GetAllAppProgress retrieves progress across all apps
func GetAllAppProgress(userID uint) ([]*models.AppProgress, error) {
	var progress []*models.AppProgress
	result := database.DB.Where("user_id = ?", userID).Find(&progress)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch app progress", result.Error.Error())
	}
	return progress, nil
}

// UpdateAppProgress updates app-specific progress
func UpdateAppProgress(progress *models.AppProgress) error {
	progress.UpdatedAt = time.Now()

	// Calculate accuracy
	if progress.TotalAttempts > 0 {
		progress.Accuracy = float64(progress.TotalCorrect) / float64(progress.TotalAttempts) * 100
	}

	result := database.DB.Save(progress)
	if result.Error != nil {
		return errors.Internal("failed to update app progress", result.Error.Error())
	}
	return nil
}

// ========== SUBJECT MASTERY REPOSITORY ==========

// GetSubjectMastery retrieves mastery for a subject
func GetSubjectMastery(userID uint, app, subject string) (*models.SubjectMastery, error) {
	var mastery models.SubjectMastery
	result := database.DB.Where("user_id = ? AND app = ? AND subject = ?", userID, app, subject).First(&mastery)
	if result.Error != nil {
		// Return default mastery for new subjects
		return &models.SubjectMastery{
			UserID:    userID,
			App:       app,
			Subject:   subject,
			CreatedAt: time.Now(),
			UpdatedAt: time.Now(),
		}, nil
	}
	return &mastery, nil
}

// UpdateSubjectMastery updates subject-specific mastery
func UpdateSubjectMastery(mastery *models.SubjectMastery) error {
	// Calculate mastery level (0-100)
	if mastery.QuestionsAttempted > 0 {
		accuracy := float64(mastery.QuestionsCorrect) / float64(mastery.QuestionsAttempted) * 100
		mastery.MasteryLevel = accuracy
	}

	mastery.LastPracticed = time.Now()
	mastery.UpdatedAt = time.Now()

	result := database.DB.Save(mastery)
	if result.Error != nil {
		return errors.Internal("failed to update subject mastery", result.Error.Error())
	}
	return nil
}

// ========== LEADERBOARD REPOSITORY ==========

// GetLeaderboard retrieves ranked users
func GetLeaderboard(period string, limit int) ([]*models.LeaderboardEntry, error) {
	var entries []*models.LeaderboardEntry

	query := database.DB.Table("user_xp").
		Select("ROW_NUMBER() OVER (ORDER BY total_xp DESC) as rank, user_id, total_xp as value, updated_at").
		Limit(limit)

	// Filter by period if not all-time
	if period == "weekly" {
		weekAgo := time.Now().AddDate(0, 0, -7)
		query = query.
			Joins("LEFT JOIN xp_log ON xp_log.user_id = user_xp.user_id").
			Where("xp_log.created_at >= ?", weekAgo)
	} else if period == "daily" {
		today := time.Now().Truncate(24 * time.Hour)
		query = query.
			Joins("LEFT JOIN xp_log ON xp_log.user_id = user_xp.user_id").
			Where("xp_log.created_at >= ?", today)
	}

	result := query.Scan(&entries)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch leaderboard", result.Error.Error())
	}

	return entries, nil
}

// ========== LEARNING GOALS REPOSITORY ==========

// GetUserGoals retrieves user's learning goals
func GetUserGoals(userID uint) ([]*models.LearningGoal, error) {
	var goals []*models.LearningGoal
	result := database.DB.Where("user_id = ?", userID).Order("created_at DESC").Find(&goals)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch goals", result.Error.Error())
	}
	return goals, nil
}

// CreateGoal creates a new learning goal
func CreateGoal(goal *models.LearningGoal) (uint, error) {
	result := database.DB.Create(goal)
	if result.Error != nil {
		return 0, errors.Internal("failed to create goal", result.Error.Error())
	}
	return goal.ID, nil
}

// UpdateGoal updates a learning goal
func UpdateGoal(goal *models.LearningGoal) error {
	goal.UpdatedAt = time.Now()
	result := database.DB.Save(goal)
	if result.Error != nil {
		return errors.Internal("failed to update goal", result.Error.Error())
	}
	return nil
}

// DeleteGoal deletes a learning goal
func DeleteGoal(goalID, userID uint) error {
	result := database.DB.Where("id = ? AND user_id = ?", goalID, userID).Delete(&models.LearningGoal{})
	if result.Error != nil {
		return errors.Internal("failed to delete goal", result.Error.Error())
	}
	return nil
}

// ========== USER NOTES REPOSITORY ==========

// GetUserNotes retrieves notes for a user
func GetUserNotes(userID uint) ([]*models.UserNote, error) {
	var notes []*models.UserNote
	result := database.DB.Where("user_id = ?", userID).Order("created_at DESC").Find(&notes)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch notes", result.Error.Error())
	}
	return notes, nil
}

// CreateNote creates a new user note
func CreateNote(note *models.UserNote) (uint, error) {
	result := database.DB.Create(note)
	if result.Error != nil {
		return 0, errors.Internal("failed to create note", result.Error.Error())
	}
	return note.ID, nil
}

// UpdateNote updates a user note
func UpdateNote(note *models.UserNote) error {
	note.UpdatedAt = time.Now()
	result := database.DB.Save(note)
	if result.Error != nil {
		return errors.Internal("failed to update note", result.Error.Error())
	}
	return nil
}

// DeleteNote deletes a user note
func DeleteNote(noteID, userID uint) error {
	result := database.DB.Where("id = ? AND user_id = ?", noteID, userID).Delete(&models.UserNote{})
	if result.Error != nil {
		return errors.Internal("failed to delete note", result.Error.Error())
	}
	return nil
}

// ========== ACTIVITY LOG REPOSITORY ==========

// LogActivity logs a user activity
func LogActivity(userID uint, app, eventType, details string) error {
	activity := &models.ActivityLogEntry{
		UserID:    userID,
		App:       app,
		EventType: eventType,
		Details:   details,
		CreatedAt: time.Now(),
	}

	result := database.DB.Create(activity)
	if result.Error != nil {
		return errors.Internal("failed to log activity", result.Error.Error())
	}

	return nil
}

// GetUserActivity retrieves user's recent activity
func GetUserActivity(userID uint, limit int) ([]*models.ActivityLogEntry, error) {
	var activity []*models.ActivityLogEntry
	result := database.DB.
		Where("user_id = ?", userID).
		Order("created_at DESC").
		Limit(limit).
		Find(&activity)
	if result.Error != nil {
		return nil, errors.Internal("failed to fetch activity", result.Error.Error())
	}
	return activity, nil
}

// ========== HELPER FUNCTIONS ==========

// CalculateLevel calculates the user's level based on total XP
func CalculateLevel(totalXP int) int {
	// XP thresholds per level: [0, 100, 250, 500, 1000, 1750, 2750, 4000, 5500, 7500, 10000]
	thresholds := []int{0, 100, 250, 500, 1000, 1750, 2750, 4000, 5500, 7500, 10000}

	for i := len(thresholds) - 1; i >= 0; i-- {
		if totalXP >= thresholds[i] {
			return i + 1
		}
	}
	return 1
}

// GetXPForLevel returns XP needed to reach a specific level
func GetXPForLevel(level int) int {
	thresholds := []int{0, 100, 250, 500, 1000, 1750, 2750, 4000, 5500, 7500, 10000}
	if level > 0 && level <= len(thresholds) {
		return thresholds[level-1]
	}
	return 0
}

// SeedAchievements initializes achievements
func SeedAchievements() error {
	achievements := []models.Achievement{
		{Slug: "first_question", Name: "First Step", Description: "Answer your first question", Icon: "🎯", XPReward: 10, Category: "milestone"},
		{Slug: "perfect_score", Name: "Perfect Score", Description: "Get 100% on a session", Icon: "💯", XPReward: 50, Category: "perfection"},
		{Slug: "streak_3", Name: "On Fire", Description: "Achieve 3-day streak", Icon: "🔥", XPReward: 25, Category: "streak"},
		{Slug: "streak_7", Name: "Blazing", Description: "Achieve 7-day streak", Icon: "🌟", XPReward: 100, Category: "streak"},
		{Slug: "streak_30", Name: "Unstoppable", Description: "Achieve 30-day streak", Icon: "👑", XPReward: 500, Category: "streak"},
		{Slug: "level_5", Name: "Rising Star", Description: "Reach level 5", Icon: "🏆", XPReward: 0, Category: "level"},
		{Slug: "level_10", Name: "Legend", Description: "Reach level 10", Icon: "💎", XPReward: 0, Category: "level"},
		{Slug: "math_master", Name: "Math Master", Description: "90%+ accuracy in Math", Icon: "🧮", XPReward: 75, Category: "subject"},
		{Slug: "reading_expert", Name: "Reading Expert", Description: "90%+ accuracy in Reading", Icon: "📚", XPReward: 75, Category: "subject"},
		{Slug: "comprehension_pro", Name: "Comprehension Pro", Description: "90%+ accuracy in Comprehension", Icon: "🧠", XPReward: 75, Category: "subject"},
		{Slug: "speed_demon", Name: "Speed Demon", Description: "Complete 10 activities in one day", Icon: "⚡", XPReward: 50, Category: "engagement"},
	}

	for _, achievement := range achievements {
		result := database.DB.FirstOrCreate(&achievement, models.Achievement{Slug: achievement.Slug})
		if result.Error != nil {
			return result.Error
		}
	}

	return nil
}
