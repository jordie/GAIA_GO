package rate_limiting

import (
	"fmt"
	"sync"
	"time"

	"gorm.io/gorm"
)

// UserReputation represents a user's reputation score and tier
type UserReputation struct {
	UserID        int       `json:"user_id"`
	Score         int       `json:"score"`
	Tier          string    `json:"tier"`
	Multiplier    float64   `json:"multiplier"`
	VIPTier       string    `json:"vip_tier"`
	VIPExpiresAt  *time.Time `json:"vip_expires_at"`
	ViolationCount int       `json:"violation_count"`
	CleanRequests int       `json:"clean_requests"`
	LastUpdated   time.Time `json:"last_updated"`
	CreatedAt     time.Time `json:"created_at"`
}

// ReputationEvent represents a reputation change event
type ReputationEvent struct {
	ID          int       `json:"id"`
	UserID      int       `json:"user_id"`
	EventType   string    `json:"event_type"` // violation, clean, decay, manual
	Severity    int       `json:"severity"`   // For violations: 1-3
	Description string    `json:"description"`
	ScoreDelta  int       `json:"score_delta"`
	CreatedAt   time.Time `json:"created_at"`
}

// ReputationManager manages user reputation scores and tiers
type ReputationManager struct {
	db          *gorm.DB
	cache       map[int]*UserReputation
	cacheMutex  sync.RWMutex
	cacheTTL    time.Duration
	cacheExpiry map[int]time.Time
}

// NewReputationManager creates a new reputation manager
func NewReputationManager(db *gorm.DB) *ReputationManager {
	rm := &ReputationManager{
		db:          db,
		cache:       make(map[int]*UserReputation),
		cacheTTL:    5 * time.Minute,
		cacheExpiry: make(map[int]time.Time),
	}

	// Start background decay job
	go rm.startDecayJob()

	return rm
}

// GetUserReputation retrieves a user's reputation (with caching)
func (rm *ReputationManager) GetUserReputation(userID int) (*UserReputation, error) {
	// Check cache
	rm.cacheMutex.RLock()
	if rep, ok := rm.cache[userID]; ok && time.Now().Before(rm.cacheExpiry[userID]) {
		rm.cacheMutex.RUnlock()
		return rep, nil
	}
	rm.cacheMutex.RUnlock()

	// Get from database
	rep := &UserReputation{}
	err := rm.db.
		Where("user_id = ?", userID).
		First(rep).Error

	if err == gorm.ErrRecordNotFound {
		// Create new user reputation
		rep = &UserReputation{
			UserID:      userID,
			Score:       50, // Start at neutral
			Tier:        "standard",
			Multiplier:  1.0,
			LastUpdated: time.Now(),
			CreatedAt:   time.Now(),
		}

		if err := rm.db.Create(rep).Error; err != nil {
			return nil, fmt.Errorf("failed to create reputation: %w", err)
		}
	} else if err != nil {
		return nil, fmt.Errorf("failed to get reputation: %w", err)
	}

	// Update cache
	rm.cacheMutex.Lock()
	rm.cache[userID] = rep
	rm.cacheExpiry[userID] = time.Now().Add(rm.cacheTTL)
	rm.cacheMutex.Unlock()

	return rep, nil
}

// RecordViolation records a violation and updates reputation
func (rm *ReputationManager) RecordViolation(userID int, severity int, description string) error {
	rep, err := rm.GetUserReputation(userID)
	if err != nil {
		return err
	}

	// Calculate score penalty based on severity (1-3)
	penalty := severity * 3 // 3, 6, or 9 points

	// Update score
	newScore := rep.Score - penalty
	if newScore < 0 {
		newScore = 0
	}

	// Update reputation
	if err := rm.db.Model(rep).Update("score", newScore).Error; err != nil {
		return fmt.Errorf("failed to update reputation: %w", err)
	}

	// Record event
	event := ReputationEvent{
		UserID:      userID,
		EventType:   "violation",
		Severity:    severity,
		Description: description,
		ScoreDelta:  -penalty,
		CreatedAt:   time.Now(),
	}
	if err := rm.db.Table("reputation_events").Create(&event).Error; err != nil {
		return fmt.Errorf("failed to record event: %w", err)
	}

	// Update tier and multiplier
	rep.Score = newScore
	rep.Tier = getTierForScore(newScore)
	rep.Multiplier = getAdaptiveMultiplier(newScore)
	rep.ViolationCount++
	rep.LastUpdated = time.Now()

	// Invalidate cache
	rm.cacheMutex.Lock()
	delete(rm.cache, userID)
	delete(rm.cacheExpiry, userID)
	rm.cacheMutex.Unlock()

	return nil
}

// RecordCleanRequest records an allowed request
func (rm *ReputationManager) RecordCleanRequest(userID int) error {
	rep, err := rm.GetUserReputation(userID)
	if err != nil {
		return err
	}

	// Small positive increment for good behavior
	newScore := rep.Score + 1
	if newScore > 100 {
		newScore = 100
	}

	// Update reputation
	if err := rm.db.Model(rep).Update("score", newScore).Error; err != nil {
		return fmt.Errorf("failed to update reputation: %w", err)
	}

	// Record event (optional, to reduce database load)
	// Only record every Nth clean request
	if rep.CleanRequests%100 == 0 {
		event := ReputationEvent{
			UserID:      userID,
			EventType:   "clean",
			Description: "Clean request recorded",
			ScoreDelta:  1,
			CreatedAt:   time.Now(),
		}
		rm.db.Table("reputation_events").Create(&event)
	}

	// Update representation
	rep.Score = newScore
	rep.Tier = getTierForScore(newScore)
	rep.Multiplier = getAdaptiveMultiplier(newScore)
	rep.CleanRequests++
	rep.LastUpdated = time.Now()

	// Invalidate cache
	rm.cacheMutex.Lock()
	delete(rm.cache, userID)
	delete(rm.cacheExpiry, userID)
	rm.cacheMutex.Unlock()

	return nil
}

// GetAdaptiveLimit returns adjusted rate limit based on reputation
func (rm *ReputationManager) GetAdaptiveLimit(userID int, baseLimit int) int {
	rep, err := rm.GetUserReputation(userID)
	if err != nil {
		return baseLimit // Return base limit on error
	}

	adjusted := int(float64(baseLimit) * rep.Multiplier)
	return adjusted
}

// ApplyRepDecay applies weekly decay to all users
func (rm *ReputationManager) ApplyRepDecay(userID int) error {
	rep, err := rm.GetUserReputation(userID)
	if err != nil {
		return err
	}

	// Decay 5 points per week towards neutral (50)
	decayAmount := 5
	if rep.Score < 50 {
		// Move towards neutral (50) from below
		newScore := rep.Score + decayAmount
		if newScore > 50 {
			newScore = 50
		}
		rep.Score = newScore
	} else if rep.Score > 50 {
		// Move towards neutral (50) from above
		newScore := rep.Score - decayAmount
		if newScore < 50 {
			newScore = 50
		}
		rep.Score = newScore
	}

	// Update database
	if err := rm.db.Model(rep).Update("score", rep.Score).Error; err != nil {
		return fmt.Errorf("failed to apply decay: %w", err)
	}

	// Record event
	event := ReputationEvent{
		UserID:      userID,
		EventType:   "decay",
		Description: "Weekly reputation decay applied",
		CreatedAt:   time.Now(),
	}
	rm.db.Table("reputation_events").Create(&event)

	// Invalidate cache
	rm.cacheMutex.Lock()
	delete(rm.cache, userID)
	delete(rm.cacheExpiry, userID)
	rm.cacheMutex.Unlock()

	return nil
}

// ApplyRepDecayAll applies decay to all users
func (rm *ReputationManager) ApplyRepDecayAll() (int, error) {
	result := rm.db.Model(&UserReputation{}).
		Where("score != ?", 50).
		Update("score", gorm.Expr("CASE WHEN score < 50 THEN score + 5 ELSE score - 5 END"))

	if result.Error != nil {
		return 0, fmt.Errorf("failed to apply decay: %w", result.Error)
	}

	// Clear cache
	rm.cacheMutex.Lock()
	rm.cache = make(map[int]*UserReputation)
	rm.cacheExpiry = make(map[int]time.Time)
	rm.cacheMutex.Unlock()

	return int(result.RowsAffected), nil
}

// SetVIPTier sets VIP tier for a user
func (rm *ReputationManager) SetVIPTier(userID int, tier string, expiresAt *time.Time, reason string) error {
	rep, err := rm.GetUserReputation(userID)
	if err != nil {
		return err
	}

	rep.VIPTier = tier
	rep.VIPExpiresAt = expiresAt

	// Update VIP multiplier
	if tier == "premium" {
		rep.Multiplier = 2.0
	}

	if err := rm.db.Model(rep).Updates(map[string]interface{}{
		"vip_tier":        tier,
		"vip_expires_at":  expiresAt,
	}).Error; err != nil {
		return fmt.Errorf("failed to set VIP tier: %w", err)
	}

	// Record event
	event := ReputationEvent{
		UserID:      userID,
		EventType:   "manual",
		Description: fmt.Sprintf("Set VIP tier to %s. Reason: %s", tier, reason),
		CreatedAt:   time.Now(),
	}
	rm.db.Table("reputation_events").Create(&event)

	// Invalidate cache
	rm.cacheMutex.Lock()
	delete(rm.cache, userID)
	delete(rm.cacheExpiry, userID)
	rm.cacheMutex.Unlock()

	return nil
}

// RemoveVIPTier removes VIP tier from user
func (rm *ReputationManager) RemoveVIPTier(userID int) error {
	rep, err := rm.GetUserReputation(userID)
	if err != nil {
		return err
	}

	rep.VIPTier = ""
	rep.VIPExpiresAt = nil
	rep.Multiplier = getAdaptiveMultiplier(rep.Score)

	if err := rm.db.Model(rep).Updates(map[string]interface{}{
		"vip_tier":       "",
		"vip_expires_at": nil,
	}).Error; err != nil {
		return fmt.Errorf("failed to remove VIP tier: %w", err)
	}

	// Record event
	event := ReputationEvent{
		UserID:      userID,
		EventType:   "manual",
		Description: "VIP tier removed",
		CreatedAt:   time.Now(),
	}
	rm.db.Table("reputation_events").Create(&event)

	// Invalidate cache
	rm.cacheMutex.Lock()
	delete(rm.cache, userID)
	delete(rm.cacheExpiry, userID)
	rm.cacheMutex.Unlock()

	return nil
}

// SetUserReputation allows admin override
func (rm *ReputationManager) SetUserReputation(userID int, score int, description string) error {
	if score < 0 || score > 100 {
		return fmt.Errorf("score must be between 0 and 100")
	}

	rep, err := rm.GetUserReputation(userID)
	if err != nil {
		return err
	}

	oldScore := rep.Score
	rep.Score = score
	rep.Tier = getTierForScore(score)
	rep.Multiplier = getAdaptiveMultiplier(score)
	rep.LastUpdated = time.Now()

	if err := rm.db.Model(rep).Update("score", score).Error; err != nil {
		return fmt.Errorf("failed to set reputation: %w", err)
	}

	// Record event
	event := ReputationEvent{
		UserID:      userID,
		EventType:   "manual",
		Description: description,
		ScoreDelta:  score - oldScore,
		CreatedAt:   time.Now(),
	}
	rm.db.Table("reputation_events").Create(&event)

	// Invalidate cache
	rm.cacheMutex.Lock()
	delete(rm.cache, userID)
	delete(rm.cacheExpiry, userID)
	rm.cacheMutex.Unlock()

	return nil
}

// GetRepHistory returns reputation history for a user
func (rm *ReputationManager) GetRepHistory(userID int, days int) ([]ReputationEvent, error) {
	var events []ReputationEvent
	cutoff := time.Now().AddDate(0, 0, -days)

	err := rm.db.Table("reputation_events").
		Where("user_id = ? AND created_at > ?", userID, cutoff).
		Order("created_at DESC").
		Find(&events).Error

	return events, err
}

// GetUserEvents returns recent events for a user with optional type filter
func (rm *ReputationManager) GetUserEvents(userID int, limit int, eventType string) ([]ReputationEvent, int, error) {
	var events []ReputationEvent
	var total int64

	query := rm.db.Table("reputation_events").Where("user_id = ?", userID)

	if eventType != "" {
		query = query.Where("event_type = ?", eventType)
	}

	// Get total count
	query.Model(&ReputationEvent{}).Count(&total)

	// Get paginated results
	err := query.
		Order("created_at DESC").
		Limit(limit).
		Find(&events).Error

	return events, int(total), err
}

// GetRepStats returns system-wide reputation statistics
func (rm *ReputationManager) GetRepStats() (map[string]interface{}, error) {
	var stats struct {
		TotalUsers      int
		FlaggedCount    int
		StandardCount   int
		TrustedCount    int
		PremiumCount    int
		AvgScore        float64
		MedianScore     int
		HighestScore    int
		LowestScore     int
	}

	var users []UserReputation
	if err := rm.db.Find(&users).Error; err != nil {
		return nil, err
	}

	stats.TotalUsers = len(users)
	for _, u := range users {
		switch u.Tier {
		case "flagged":
			stats.FlaggedCount++
		case "standard":
			stats.StandardCount++
		case "trusted":
			stats.TrustedCount++
		case "premium":
			stats.PremiumCount++
		}

		stats.AvgScore += float64(u.Score)
		if u.Score > stats.HighestScore {
			stats.HighestScore = u.Score
		}
		if stats.LowestScore == 0 || u.Score < stats.LowestScore {
			stats.LowestScore = u.Score
		}
	}

	if stats.TotalUsers > 0 {
		stats.AvgScore /= float64(stats.TotalUsers)
	}

	return map[string]interface{}{
		"total_users":      stats.TotalUsers,
		"flagged_count":    stats.FlaggedCount,
		"standard_count":   stats.StandardCount,
		"trusted_count":    stats.TrustedCount,
		"premium_count":    stats.PremiumCount,
		"avg_score":        fmt.Sprintf("%.2f", stats.AvgScore),
		"highest_score":    stats.HighestScore,
		"lowest_score":     stats.LowestScore,
		"distribution": map[string]interface{}{
			"flagged":   stats.FlaggedCount,
			"standard":  stats.StandardCount,
			"trusted":   stats.TrustedCount,
			"premium":   stats.PremiumCount,
		},
	}, nil
}

// GetRepTrends returns reputation trends over time
func (rm *ReputationManager) GetRepTrends(days int) ([]map[string]interface{}, error) {
	var trends []map[string]interface{}

	for i := days; i >= 0; i-- {
		date := time.Now().AddDate(0, 0, -i).Truncate(24 * time.Hour)

		var events []ReputationEvent
		rm.db.Table("reputation_events").
			Where("created_at >= ? AND created_at < ?",
				date,
				date.AddDate(0, 0, 1)).
			Find(&events)

		violationCount := 0
		cleanCount := 0
		decayCount := 0

		for _, e := range events {
			switch e.EventType {
			case "violation":
				violationCount++
			case "clean":
				cleanCount++
			case "decay":
				decayCount++
			}
		}

		trends = append(trends, map[string]interface{}{
			"date":            date.Format("2006-01-02"),
			"violations":      violationCount,
			"clean_requests":  cleanCount,
			"decays":          decayCount,
			"total_events":    len(events),
		})
	}

	return trends, nil
}

// GetAllUsers returns all users with pagination
func (rm *ReputationManager) GetAllUsers(page int, limit int) ([]UserReputation, int, error) {
	var users []UserReputation
	var total int64

	offset := (page - 1) * limit

	// Get total count
	rm.db.Model(&UserReputation{}).Count(&total)

	// Get paginated results
	err := rm.db.
		Order("score DESC, user_id ASC").
		Offset(offset).
		Limit(limit).
		Find(&users).Error

	return users, int(total), err
}

// Helper functions

func getTierForScore(score int) string {
	switch {
	case score <= 20:
		return "flagged"
	case score <= 80:
		return "standard"
	case score <= 100:
		return "trusted"
	default:
		return "premium"
	}
}

func getAdaptiveMultiplier(score int) float64 {
	switch {
	case score <= 20:
		return 0.5
	case score <= 50:
		return 0.75 + (float64(score-20) / 30 * 0.25)
	case score <= 80:
		return 1.0 + (float64(score-50) / 30 * 0.5)
	default:
		return 1.5 + (float64(score-80) / 20 * 0.5)
	}
}

// startDecayJob applies reputation decay weekly
func (rm *ReputationManager) startDecayJob() {
	ticker := time.NewTicker(7 * 24 * time.Hour)
	defer ticker.Stop()

	for range ticker.C {
		rm.ApplyRepDecayAll()
	}
}
