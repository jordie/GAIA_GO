package rate_limiting

import (
	"context"
	"fmt"
	"math"
	"sync"
	"time"

	"gorm.io/gorm"
)

// AnomalyScore represents how anomalous a user's behavior is (0-100)
type AnomalyScore struct {
	Score       float64 `json:"score"`       // 0-100 (0=normal, 100=highly anomalous)
	Severity    string  `json:"severity"`    // low, medium, high, critical
	Reasons     []string `json:"reasons"`    // Why it's anomalous
	Confidence  float64 `json:"confidence"` // 0-1 (confidence in the score)
	LastUpdated time.Time `json:"last_updated"`
}

// AnomalyPattern represents a detected pattern
type AnomalyPattern struct {
	ID           int       `json:"id" gorm:"primaryKey"`
	UserID       int       `json:"user_id" gorm:"index"`
	PatternType  string    `json:"pattern_type"` // burst, unusual_time, resource_spike, etc
	Description  string    `json:"description"`
	Score        float64   `json:"score"`
	Confidence   float64   `json:"confidence"`
	StartTime    time.Time `json:"start_time"`
	EndTime      *time.Time `json:"end_time"`
	Resolved     bool      `json:"resolved"`
	CreatedAt    time.Time `json:"created_at" gorm:"index"`
}

// UserBehaviorProfile represents normal behavior for a user
type UserBehaviorProfile struct {
	ID                    int       `json:"id" gorm:"primaryKey"`
	UserID                int       `json:"user_id" gorm:"uniqueIndex"`
	AvgRequestsPerHour    float64   `json:"avg_requests_per_hour"`
	StdDevRequests        float64   `json:"std_dev_requests"`
	PeakHour              int       `json:"peak_hour"`
	PeakDayOfWeek         int       `json:"peak_day_of_week"`
	AvgResponseTime       float64   `json:"avg_response_time_ms"`
	CommonResources       string    `json:"common_resources"` // JSON array
	ViolationRate         float64   `json:"violation_rate"`   // violations per 1000 requests
	LastAnalyzed          time.Time `json:"last_analyzed"`
	CreatedAt             time.Time `json:"created_at"`
}

// AnomalyDetector detects unusual user behavior patterns
type AnomalyDetector struct {
	db              *gorm.DB
	cache           map[int]*AnomalyScore
	cacheMutex      sync.RWMutex
	cacheTTL        time.Duration
	cacheExpiry     map[int]time.Time
	active          bool
	stopChan        chan struct{}

	// Detection thresholds
	BurstThreshold       float64 // 2.0x = 2x normal rate
	UnusualTimeThreshold float64 // 3.0x = 3x normal rate at unusual hour
	ResourceSpikeThreshold float64 // 2.5x = 2.5x normal resource usage
}

// NewAnomalyDetector creates a new anomaly detector
func NewAnomalyDetector(db *gorm.DB) *AnomalyDetector {
	ad := &AnomalyDetector{
		db:                   db,
		cache:                make(map[int]*AnomalyScore),
		cacheTTL:             5 * time.Minute,
		cacheExpiry:          make(map[int]time.Time),
		stopChan:             make(chan struct{}),
		BurstThreshold:       2.0,
		UnusualTimeThreshold: 3.0,
		ResourceSpikeThreshold: 2.5,
	}

	// Start background analysis
	go ad.startAnalyzer()

	return ad
}

// startAnalyzer starts the background anomaly detection
func (ad *AnomalyDetector) startAnalyzer() {
	ad.active = true
	ticker := time.NewTicker(1 * time.Minute)
	defer ticker.Stop()

	for {
		select {
		case <-ad.stopChan:
			return
		case <-ticker.C:
			ad.analyzeAllUsers()
		}
	}
}

// analyzeAllUsers analyzes behavior for all users
func (ad *AnomalyDetector) analyzeAllUsers() {
	var userIDs []int
	ad.db.Table("reputation_scores").
		Pluck("user_id", &userIDs)

	for _, userID := range userIDs {
		ad.analyzeUser(userID)
	}
}

// analyzeUser analyzes a single user's behavior
func (ad *AnomalyDetector) analyzeUser(userID int) {
	profile, err := ad.getOrCreateProfile(userID)
	if err != nil {
		return
	}

	// Get recent activity
	recentViolations := ad.getRecentViolations(userID, 1*time.Hour)
	recentRequests := ad.getRecentRequests(userID, 1*time.Hour)

	score := &AnomalyScore{
		Reasons:     []string{},
		LastUpdated: time.Now(),
	}

	// Check for burst pattern
	if ad.detectBurst(userID, recentRequests, profile) {
		score.Score += 30
		score.Reasons = append(score.Reasons, "Unusual request burst detected")
	}

	// Check for unusual time pattern
	if ad.detectUnusualTime(userID, recentRequests, profile) {
		score.Score += 20
		score.Reasons = append(score.Reasons, "Requests at unusual hour")
	}

	// Check for resource spike
	if ad.detectResourceSpike(recentViolations) {
		score.Score += 25
		score.Reasons = append(score.Reasons, "High violation rate spike")
	}

	// Check for geographic anomaly (would need IP data)
	if ad.detectGeographicAnomaly(userID) {
		score.Score += 15
		score.Reasons = append(score.Reasons, "Access from unusual location")
	}

	// Cap score at 100
	if score.Score > 100 {
		score.Score = 100
	}

	// Determine severity
	score.Severity = ad.getSeverity(score.Score)
	score.Confidence = ad.calculateConfidence(len(recentRequests), len(recentViolations))

	// Update cache
	ad.cacheMutex.Lock()
	ad.cache[userID] = score
	ad.cacheExpiry[userID] = time.Now().Add(ad.cacheTTL)
	ad.cacheMutex.Unlock()

	// Save pattern if significant
	if score.Score >= 50 {
		ad.savePattern(userID, score)
	}
}

// detectBurst detects sudden spike in request rate
func (ad *AnomalyDetector) detectBurst(userID int, recentRequests int, profile *UserBehaviorProfile) bool {
	if profile.AvgRequestsPerHour == 0 {
		return false
	}

	expectedPerHour := profile.AvgRequestsPerHour
	actualPerHour := float64(recentRequests)

	threshold := expectedPerHour * ad.BurstThreshold
	return actualPerHour > threshold
}

// detectUnusualTime detects requests at unusual hours
func (ad *AnomalyDetector) detectUnusualTime(userID int, recentRequests int, profile *UserBehaviorProfile) bool {
	currentHour := time.Now().Hour()
	peakHour := profile.PeakHour

	// If request at off-peak time, check rate
	if currentHour != peakHour && recentRequests > 0 {
		expectedPerHour := profile.AvgRequestsPerHour / 24 // Assume uniform distribution
		actualPerHour := float64(recentRequests)
		threshold := expectedPerHour * ad.UnusualTimeThreshold

		return actualPerHour > threshold
	}

	return false
}

// detectResourceSpike detects spike in violations/errors
func (ad *AnomalyDetector) detectResourceSpike(violations int) bool {
	// If more than 10 violations in last hour, it's a spike
	return violations > 10
}

// detectGeographicAnomaly detects access from new locations (placeholder)
func (ad *AnomalyDetector) detectGeographicAnomaly(userID int) bool {
	// Would need IP geolocation data
	// Placeholder returns false
	return false
}

// getSeverity determines severity level from score
func (ad *AnomalyDetector) getSeverity(score float64) string {
	switch {
	case score >= 80:
		return "critical"
	case score >= 60:
		return "high"
	case score >= 40:
		return "medium"
	default:
		return "low"
	}
}

// calculateConfidence calculates confidence in the score
func (ad *AnomalyDetector) calculateConfidence(requests, violations int) float64 {
	// More data points = higher confidence
	dataPoints := requests + violations
	confidence := math.Min(float64(dataPoints)/100.0, 1.0)
	return confidence
}

// getOrCreateProfile gets or creates behavior profile for user
func (ad *AnomalyDetector) getOrCreateProfile(userID int) (*UserBehaviorProfile, error) {
	profile := &UserBehaviorProfile{}
	err := ad.db.Where("user_id = ?", userID).First(profile).Error

	if err == gorm.ErrRecordNotFound {
		// Create new profile with defaults
		profile = &UserBehaviorProfile{
			UserID:             userID,
			AvgRequestsPerHour: 100, // Default assumption
			StdDevRequests:     50,
			PeakHour:           12,   // Noon
			PeakDayOfWeek:      3,    // Wednesday
			AvgResponseTime:    200,  // 200ms
			ViolationRate:      5.0,  // 5 per 1000
			LastAnalyzed:       time.Now(),
			CreatedAt:          time.Now(),
		}

		if err := ad.db.Create(profile).Error; err != nil {
			return nil, err
		}
	} else if err != nil {
		return nil, err
	}

	return profile, nil
}

// getRecentViolations gets violation count in time window
func (ad *AnomalyDetector) getRecentViolations(userID int, window time.Duration) int {
	var count int64
	ad.db.Table("reputation_events").
		Where("user_id = ? AND event_type = ? AND created_at > ?",
			userID, "violation", time.Now().Add(-window)).
		Count(&count)
	return int(count)
}

// getRecentRequests gets request count in time window
func (ad *AnomalyDetector) getRecentRequests(userID int, window time.Duration) int {
	var count int64
	ad.db.Table("rate_limit_buckets").
		Where("scope = ? AND scope_value = ? AND window_end > ?",
			"user", fmt.Sprintf("%d", userID), time.Now().Add(-window)).
		Sum("request_count", &count)
	return int(count)
}

// GetAnomalyScore gets current anomaly score for user
func (ad *AnomalyDetector) GetAnomalyScore(userID int) *AnomalyScore {
	ad.cacheMutex.RLock()
	if score, ok := ad.cache[userID]; ok && time.Now().Before(ad.cacheExpiry[userID]) {
		ad.cacheMutex.RUnlock()
		return score
	}
	ad.cacheMutex.RUnlock()

	// Cache miss, analyze user
	ad.analyzeUser(userID)

	ad.cacheMutex.RLock()
	defer ad.cacheMutex.RUnlock()
	if score, ok := ad.cache[userID]; ok {
		return score
	}

	return &AnomalyScore{Score: 0, Severity: "low"}
}

// savePattern saves detected anomaly pattern
func (ad *AnomalyDetector) savePattern(userID int, score *AnomalyScore) error {
	pattern := AnomalyPattern{
		UserID:      userID,
		PatternType: score.Severity, // Use severity as simple pattern type
		Description: fmt.Sprintf("Detected anomaly: %v", score.Reasons),
		Score:       score.Score,
		Confidence:  score.Confidence,
		StartTime:   time.Now(),
		Resolved:    false,
		CreatedAt:   time.Now(),
	}

	return ad.db.Table("anomaly_patterns").Create(&pattern).Error
}

// GetAnomalyPatterns gets detected patterns for user
func (ad *AnomalyDetector) GetAnomalyPatterns(ctx context.Context, userID int, limit int) ([]AnomalyPattern, error) {
	var patterns []AnomalyPattern
	err := ad.db.WithContext(ctx).
		Where("user_id = ? AND resolved = ?", userID, false).
		Order("created_at DESC").
		Limit(limit).
		Find(&patterns).Error
	return patterns, err
}

// ResolvePattern marks an anomaly pattern as resolved
func (ad *AnomalyDetector) ResolvePattern(ctx context.Context, patternID int) error {
	now := time.Now()
	return ad.db.WithContext(ctx).
		Model(&AnomalyPattern{}).
		Where("id = ?", patternID).
		Updates(map[string]interface{}{
			"resolved": true,
			"end_time": now,
		}).Error
}

// GetAnomalyStats returns anomaly detection statistics
func (ad *AnomalyDetector) GetAnomalyStats(ctx context.Context) (map[string]interface{}, error) {
	var stats struct {
		TotalPatterns     int64
		UnresolvedCount   int64
		CriticalCount     int64
		HighCount         int64
		AverageScore      float64
	}

	ad.db.WithContext(ctx).Table("anomaly_patterns").Count(&stats.TotalPatterns)
	ad.db.WithContext(ctx).Table("anomaly_patterns").
		Where("resolved = ?", false).Count(&stats.UnresolvedCount)
	ad.db.WithContext(ctx).Table("anomaly_patterns").
		Where("pattern_type = ?", "critical").Count(&stats.CriticalCount)
	ad.db.WithContext(ctx).Table("anomaly_patterns").
		Where("pattern_type = ?", "high").Count(&stats.HighCount)
	ad.db.WithContext(ctx).Table("anomaly_patterns").
		Select("AVG(score)").Row().Scan(&stats.AverageScore)

	return map[string]interface{}{
		"total_patterns":     stats.TotalPatterns,
		"unresolved_count":   stats.UnresolvedCount,
		"critical_count":     stats.CriticalCount,
		"high_count":         stats.HighCount,
		"average_score":      fmt.Sprintf("%.2f", stats.AverageScore),
	}, nil
}

// Close stops the anomaly detector
func (ad *AnomalyDetector) Close() error {
	if ad.active {
		close(ad.stopChan)
		ad.active = false
	}
	return nil
}
