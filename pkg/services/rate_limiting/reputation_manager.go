package rate_limiting

import (
	"context"
	"fmt"
	"sync"
	"time"

	"gorm.io/clause"
	"gorm.io/gorm"
)

// UserReputation represents a user's reputation score and history
type UserReputation struct {
	ID                   int       `gorm:"primaryKey"`
	UserID               int       `gorm:"uniqueIndex"`
	ReputationScore      float64   `gorm:"default:50.0"`
	Tier                 string    `gorm:"default:'standard'"`
	LastViolation        *time.Time
	TotalViolations      int       `gorm:"default:0"`
	TotalCleanRequests   int       `gorm:"default:0"`
	DecayLastApplied     time.Time `gorm:"default:CURRENT_TIMESTAMP"`
	CreatedAt            time.Time `gorm:"autoCreateTime"`
	UpdatedAt            time.Time `gorm:"autoUpdateTime"`
}

// ReputationEvent represents a single reputation event (violation, clean request, decay, etc)
type ReputationEvent struct {
	ID          int       `gorm:"primaryKey"`
	UserID      int
	EventType   string    `gorm:"type:varchar(50)"` // 'violation', 'clean_request', 'decay', 'manual_adjust'
	Severity    int       `gorm:"default:1"`        // 1-5 scale
	Description string
	ScoreDelta  float64   `gorm:"default:0"`
	Timestamp   time.Time `gorm:"autoCreateTime"`

	// Foreign key
	User *UserReputation `gorm:"foreignKey:UserID"`
}

// VIPUser represents a manually-assigned VIP tier
type VIPUser struct {
	ID              int       `gorm:"primaryKey"`
	UserID          int       `gorm:"uniqueIndex"`
	Tier            string    `gorm:"type:varchar(50)"` // 'premium', 'enterprise', 'internal'
	LimitMultiplier float64   `gorm:"default:1.0"`
	Notes           string
	ApprovedBy      *int
	ApprovedAt      *time.Time
	CreatedAt       time.Time `gorm:"autoCreateTime"`

	// Foreign key
	User *UserReputation `gorm:"foreignKey:UserID"`
}

// ReputationManager manages user reputation scores and events
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
		cacheMutex:  sync.RWMutex{},
		cacheTTL:    5 * time.Minute,
		cacheExpiry: make(map[int]time.Time),
	}

	// Auto-migrate tables
	db.AutoMigrate(&UserReputation{}, &ReputationEvent{}, &VIPUser{})

	return rm
}

// GetUserReputation retrieves a user's reputation (with caching)
func (rm *ReputationManager) GetUserReputation(userID int) *UserReputation {
	// Check cache first
	rm.cacheMutex.RLock()
	if rep, exists := rm.cache[userID]; exists {
		if expiry, hasExpiry := rm.cacheExpiry[userID]; !hasExpiry || expiry.After(time.Now()) {
			rm.cacheMutex.RUnlock()
			return rep
		}
	}
	rm.cacheMutex.RUnlock()

	// Load from database
	var rep UserReputation
	result := rm.db.Where("user_id = ?", userID).First(&rep)

	if result.Error == gorm.ErrRecordNotFound {
		// Create new reputation for user
		rep = UserReputation{
			UserID:          userID,
			ReputationScore: 50.0,
			Tier:            "standard",
			DecayLastApplied: time.Now(),
		}
		rm.db.Create(&rep)
	}

	// Update cache
	rm.cacheMutex.Lock()
	rm.cache[userID] = &rep
	rm.cacheExpiry[userID] = time.Now().Add(rm.cacheTTL)
	rm.cacheMutex.Unlock()

	return &rep
}

// RecordViolation records a rate limit violation for a user
func (rm *ReputationManager) RecordViolation(userID int, severity int, description string) error {
	rep := rm.GetUserReputation(userID)

	// Calculate score delta based on violation severity
	scoreDelta := rm.calculateViolationDelta(severity, rep.TotalViolations)

	// Record event
	event := ReputationEvent{
		UserID:      userID,
		EventType:   "violation",
		Severity:    severity,
		Description: description,
		ScoreDelta:  scoreDelta,
	}
	if err := rm.db.Create(&event).Error; err != nil {
		return err
	}

	// Update user reputation
	newScore := rep.ReputationScore + scoreDelta
	if newScore < 0 {
		newScore = 0
	}
	if newScore > 100 {
		newScore = 100
	}

	updates := map[string]interface{}{
		"reputation_score":    newScore,
		"total_violations":    rep.TotalViolations + 1,
		"last_violation":      time.Now(),
		"tier":                GetTierForScore(newScore),
		"updated_at":          time.Now(),
	}

	if err := rm.db.Model(&rep).Updates(updates).Error; err != nil {
		return err
	}

	// Invalidate cache
	rm.cacheMutex.Lock()
	delete(rm.cache, userID)
	delete(rm.cacheExpiry, userID)
	rm.cacheMutex.Unlock()

	return nil
}

// RecordCleanRequest records a clean (non-violation) request
func (rm *ReputationManager) RecordCleanRequest(userID int) error {
	rep := rm.GetUserReputation(userID)

	// Every 100 clean requests increases score by 1
	scoreDelta := 0.01

	// Record event (only every 10th request to reduce noise)
	if rep.TotalCleanRequests%10 == 0 {
		event := ReputationEvent{
			UserID:     userID,
			EventType:  "clean_request",
			Severity:   1,
			ScoreDelta: scoreDelta,
		}
		if err := rm.db.Create(&event).Error; err != nil {
			return err
		}
	}

	// Update user reputation
	newScore := rep.ReputationScore + scoreDelta
	if newScore > 100 {
		newScore = 100
	}

	updates := map[string]interface{}{
		"reputation_score":     newScore,
		"total_clean_requests": rep.TotalCleanRequests + 1,
		"tier":                 GetTierForScore(newScore),
		"updated_at":           time.Now(),
	}

	if err := rm.db.Model(&rep).Updates(updates).Error; err != nil {
		return err
	}

	// Invalidate cache
	rm.cacheMutex.Lock()
	delete(rm.cache, userID)
	delete(rm.cacheExpiry, userID)
	rm.cacheMutex.Unlock()

	return nil
}

// ApplyRepDecay applies automatic score decay (weekly)
func (rm *ReputationManager) ApplyRepDecay(userID int) error {
	rep := rm.GetUserReputation(userID)

	// Apply decay: score drifts towards 50 (neutral)
	var scoreDelta float64
	if rep.ReputationScore > 50 {
		// Decay down
		scoreDelta = -1.0
	} else if rep.ReputationScore < 50 {
		// Decay up
		scoreDelta = 1.0
	} else {
		// Already at neutral, no decay needed
		return nil
	}

	// Record decay event
	event := ReputationEvent{
		UserID:      userID,
		EventType:   "decay",
		Severity:    1,
		Description: "Automatic weekly reputation decay",
		ScoreDelta:  scoreDelta,
	}
	if err := rm.db.Create(&event).Error; err != nil {
		return err
	}

	// Update reputation
	newScore := rep.ReputationScore + scoreDelta
	updates := map[string]interface{}{
		"reputation_score":   newScore,
		"decay_last_applied": time.Now(),
		"tier":               GetTierForScore(newScore),
		"updated_at":         time.Now(),
	}

	if err := rm.db.Model(&rep).Updates(updates).Error; err != nil {
		return err
	}

	// Invalidate cache
	rm.cacheMutex.Lock()
	delete(rm.cache, userID)
	delete(rm.cacheExpiry, userID)
	rm.cacheMutex.Unlock()

	return nil
}

// SetVIPTier assigns a VIP tier to a user
func (rm *ReputationManager) SetVIPTier(userID int, tier string, multiplier float64) error {
	vip := VIPUser{
		UserID:          userID,
		Tier:            tier,
		LimitMultiplier: multiplier,
		ApprovedAt:      new(time.Time),
	}
	*vip.ApprovedAt = time.Now()

	return rm.db.Clauses(clause.OnConflict{
		UpdateAll: true,
	}).Create(&vip).Error
}

// RemoveVIPTier removes VIP tier from a user
func (rm *ReputationManager) RemoveVIPTier(userID int) error {
	return rm.db.Delete(&VIPUser{}, "user_id = ?", userID).Error
}

// GetAdaptiveLimit returns the adjusted rate limit for a user
func (rm *ReputationManager) GetAdaptiveLimit(userID int, baseLimit int) int {
	rep := rm.GetUserReputation(userID)

	// Start with base limit
	limit := float64(baseLimit)

	// Check for VIP tier override
	var vip VIPUser
	if err := rm.db.Where("user_id = ?", userID).First(&vip).Error; err == nil {
		// VIP multiplier overrides reputation score
		limit = limit * vip.LimitMultiplier
	} else {
		// Apply reputation-based multiplier
		multiplier := GetAdaptiveMultiplier(rep.ReputationScore)
		limit = limit * multiplier
	}

	return int(limit)
}

// GetRepHistory returns reputation events for a user
func (rm *ReputationManager) GetRepHistory(userID int, days int) ([]ReputationEvent, error) {
	var events []ReputationEvent
	since := time.Now().AddDate(0, 0, -days)

	err := rm.db.Where("user_id = ? AND timestamp > ?", userID, since).
		Order("timestamp DESC").
		Find(&events).Error

	return events, err
}

// GetRepStats returns reputation statistics
func (rm *ReputationManager) GetRepStats(ctx context.Context) (map[string]interface{}, error) {
	var stats struct {
		TotalUsers      int64
		AverageScore    float64
		UsersFlagged    int64
		UsersSuspended  int64
		ViolationsToday int64
	}

	// Total users
	rm.db.Model(&UserReputation{}).Count(&stats.TotalUsers)

	// Average score
	rm.db.Model(&UserReputation{}).Select("AVG(reputation_score)").Row().Scan(&stats.AverageScore)

	// Flagged users (score < 30)
	rm.db.Model(&UserReputation{}).Where("reputation_score < ?", 30).Count(&stats.UsersFlagged)

	// Suspended users (score < 10)
	rm.db.Model(&UserReputation{}).Where("reputation_score < ?", 10).Count(&stats.UsersSuspended)

	// Violations today
	today := time.Now().Truncate(24 * time.Hour)
	rm.db.Model(&ReputationEvent{}).
		Where("event_type = ? AND timestamp >= ?", "violation", today).
		Count(&stats.ViolationsToday)

	return map[string]interface{}{
		"total_users":       stats.TotalUsers,
		"average_score":     fmt.Sprintf("%.2f", stats.AverageScore),
		"users_flagged":     stats.UsersFlagged,
		"users_suspended":   stats.UsersSuspended,
		"violations_today":  stats.ViolationsToday,
	}, nil
}

// Helper functions

// calculateViolationDelta calculates score change for a violation
func (rm *ReputationManager) calculateViolationDelta(severity int, previousViolations int) float64 {
	// Base penalty: 5 points per violation
	penalty := float64(severity * 5)

	// Additional penalty for repeat violators
	if previousViolations > 2 {
		penalty = penalty + float64((previousViolations-2)*2)
	}

	return -penalty
}

// GetTierForScore returns the appropriate tier for a reputation score
func GetTierForScore(score float64) string {
	if score < 30 {
		return "flagged"
	} else if score < 50 {
		return "standard"
	} else if score < 75 {
		return "trusted"
	} else {
		return "premium"
	}
}

// GetAdaptiveMultiplier returns the rate limit multiplier for a score
func GetAdaptiveMultiplier(score float64) float64 {
	// Score-based multiplier
	if score < 20 {
		return 0.5 // 50% of base limit
	} else if score < 40 {
		return 0.75 // 75% of base limit
	} else if score < 50 {
		return 0.9 // 90% of base limit
	} else if score < 75 {
		return 1.0 // Normal limit
	} else if score < 90 {
		return 1.2 // 120% of base limit
	} else {
		return 1.5 // 150% of base limit (premium)
	}
}

// IsUserFlagged returns true if user's reputation is flagged
func IsUserFlagged(score float64) bool {
	return score < 30
}

// IsUserSuspended returns true if user should be suspended
func IsUserSuspended(score float64) bool {
	return score < 10
}
