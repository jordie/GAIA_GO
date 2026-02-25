package app

import (
	"database/sql"
	"sync"
)

// StatsManager provides common statistics tracking for apps
type StatsManager struct {
	db *sql.DB
	mu sync.RWMutex
}

// NewStatsManager creates a new stats manager
func NewStatsManager(db *sql.DB) *StatsManager {
	return &StatsManager{
		db: db,
	}
}

// IncrementStat increments a numeric stat for a user in an app
func (sm *StatsManager) IncrementStat(userID int64, appName, statName string, amount int) error {
	_, err := sm.db.Exec(`
		INSERT INTO app_stats (user_id, app_name, stat_name, value)
		VALUES (?, ?, ?, ?)
		ON CONFLICT(user_id, app_name, stat_name)
		DO UPDATE SET value = value + excluded.value
	`, userID, appName, statName, amount)
	return err
}

// GetStat retrieves a user's stat value
func (sm *StatsManager) GetStat(userID int64, appName, statName string) (int, error) {
	var value int
	err := sm.db.QueryRow(`
		SELECT COALESCE(value, 0)
		FROM app_stats
		WHERE user_id = ? AND app_name = ? AND stat_name = ?
	`, userID, appName, statName).Scan(&value)

	if err != nil && err != sql.ErrNoRows {
		return 0, err
	}
	return value, nil
}

// GetAllStats retrieves all stats for a user in an app
func (sm *StatsManager) GetAllStats(userID int64, appName string) (map[string]int, error) {
	rows, err := sm.db.Query(`
		SELECT stat_name, value
		FROM app_stats
		WHERE user_id = ? AND app_name = ?
	`, userID, appName)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	stats := make(map[string]int)
	for rows.Next() {
		var name string
		var value int
		if err := rows.Scan(&name, &value); err != nil {
			continue
		}
		stats[name] = value
	}
	return stats, nil
}

// RecordScore records a high score for a user
func (sm *StatsManager) RecordScore(userID int64, appName string, score int) error {
	_, err := sm.db.Exec(`
		INSERT INTO app_scores (user_id, app_name, score, created_at)
		VALUES (?, ?, ?, CURRENT_TIMESTAMP)
	`, userID, appName, score)
	return err
}

// GetHighScore retrieves a user's best score
func (sm *StatsManager) GetHighScore(userID int64, appName string) (int, error) {
	var score int
	err := sm.db.QueryRow(`
		SELECT MAX(score)
		FROM app_scores
		WHERE user_id = ? AND app_name = ?
	`, userID, appName).Scan(&score)

	if err != nil && err != sql.ErrNoRows {
		return 0, err
	}
	return score, nil
}

// GetLeaderboard retrieves top scores for an app
func (sm *StatsManager) GetLeaderboard(appName string, limit int) ([]map[string]interface{}, error) {
	if limit <= 0 || limit > 100 {
		limit = 10
	}

	rows, err := sm.db.Query(`
		SELECT u.id, u.username, MAX(s.score) as high_score, COUNT(*) as plays
		FROM app_scores s
		JOIN users u ON s.user_id = u.id
		WHERE s.app_name = ?
		GROUP BY s.user_id
		ORDER BY MAX(s.score) DESC
		LIMIT ?
	`, appName, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []map[string]interface{}
	for rows.Next() {
		var userID int64
		var username string
		var highScore int
		var plays int

		if err := rows.Scan(&userID, &username, &highScore, &plays); err != nil {
			continue
		}

		results = append(results, map[string]interface{}{
			"user_id":    userID,
			"username":   username,
			"high_score": highScore,
			"plays":      plays,
		})
	}

	return results, nil
}
