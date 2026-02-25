package app

import (
	"database/sql"
	"sync"
	"time"
)

// Achievement defines an achievement
type Achievement struct {
	ID          string
	AppName     string
	Name        string
	Description string
	Icon        string
	Points      int
	Threshold   int // e.g., 100 for "complete 100 games"
}

// AchievementManager manages user achievements
type AchievementManager struct {
	db           *sql.DB
	achievements map[string]Achievement
	mu           sync.RWMutex
}

// NewAchievementManager creates a new achievement manager
func NewAchievementManager(db *sql.DB) *AchievementManager {
	return &AchievementManager{
		db:           db,
		achievements: make(map[string]Achievement),
	}
}

// RegisterAchievement registers a new achievement
func (am *AchievementManager) RegisterAchievement(ach Achievement) error {
	am.mu.Lock()
	defer am.mu.Unlock()

	am.achievements[ach.ID] = ach

	// Save to database
	_, err := am.db.Exec(`
		INSERT OR IGNORE INTO achievements (id, app_name, name, description, icon, points, threshold)
		VALUES (?, ?, ?, ?, ?, ?, ?)
	`, ach.ID, ach.AppName, ach.Name, ach.Description, ach.Icon, ach.Points, ach.Threshold)

	return err
}

// UnlockAchievement unlocks an achievement for a user
func (am *AchievementManager) UnlockAchievement(userID int64, achievementID string) error {
	am.mu.RLock()
	_, exists := am.achievements[achievementID]
	am.mu.RUnlock()

	if !exists {
		return nil // Achievement doesn't exist, silently ignore
	}

	// Insert achievement for user
	_, err := am.db.Exec(`
		INSERT OR IGNORE INTO user_achievements (user_id, achievement_id, unlocked_at)
		VALUES (?, ?, ?)
	`, userID, achievementID, time.Now())

	return err
}

// HasAchievement checks if user has unlocked an achievement
func (am *AchievementManager) HasAchievement(userID int64, achievementID string) (bool, error) {
	var exists bool
	err := am.db.QueryRow(`
		SELECT EXISTS(SELECT 1 FROM user_achievements WHERE user_id = ? AND achievement_id = ?)
	`, userID, achievementID).Scan(&exists)
	return exists, err
}

// GetUserAchievements gets all achievements unlocked by a user for an app
func (am *AchievementManager) GetUserAchievements(userID int64, appName string) ([]map[string]interface{}, error) {
	rows, err := am.db.Query(`
		SELECT a.id, a.name, a.description, a.icon, a.points, ua.unlocked_at
		FROM achievements a
		LEFT JOIN user_achievements ua ON a.id = ua.achievement_id AND ua.user_id = ?
		WHERE a.app_name = ?
		ORDER BY a.points DESC
	`, userID, appName)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []map[string]interface{}
	for rows.Next() {
		var id, name, description, icon string
		var points int
		var unlockedAt sql.NullTime

		if err := rows.Scan(&id, &name, &description, &icon, &points, &unlockedAt); err != nil {
			continue
		}

		unlocked := false
		if unlockedAt.Valid {
			unlocked = true
		}

		results = append(results, map[string]interface{}{
			"id":          id,
			"name":        name,
			"description": description,
			"icon":        icon,
			"points":      points,
			"unlocked":    unlocked,
		})
	}

	return results, nil
}
