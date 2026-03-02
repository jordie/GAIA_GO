package rate_limiting

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"gorm.io/datatypes"
	"gorm.io/gorm"
)

// StatusChange represents a single status change in appeal history
type StatusChange struct {
	ID              int64
	AppealID        int
	UserID          *int
	OldStatus       AppealStatus
	NewStatus       AppealStatus
	ChangedBy       string
	Reason          string
	Metadata        datatypes.JSONMap
	CreatedAt       time.Time
}

// AppealTimeline represents a timeline view of appeal changes
type AppealTimeline struct {
	AppealID      int                 `json:"appeal_id"`
	UserID        int                 `json:"user_id"`
	CurrentStatus AppealStatus        `json:"current_status"`
	SubmittedAt   time.Time           `json:"submitted_at"`
	Events        []TimelineEvent     `json:"events"`
	LastUpdateAt  time.Time           `json:"last_update_at"`
	ResolutionDays *float64           `json:"resolution_days"`
}

// TimelineEvent represents a single event in the timeline
type TimelineEvent struct {
	Sequence      int       `json:"sequence"`
	Status        AppealStatus `json:"status"`
	Timestamp     time.Time `json:"timestamp"`
	ChangedBy     string    `json:"changed_by"`
	Reason        string    `json:"reason"`
	RelationDays  float64   `json:"duration_days"`
	Metadata      map[string]interface{} `json:"metadata"`
}

// AppealHistoryService manages appeal history and timeline
type AppealHistoryService struct {
	db *gorm.DB
}

// NewAppealHistoryService creates a new history service
func NewAppealHistoryService(db *gorm.DB) *AppealHistoryService {
	return &AppealHistoryService{db: db}
}

// RecordStatusChange records a status change in the appeal history
func (ahs *AppealHistoryService) RecordStatusChange(
	ctx context.Context,
	appealID int,
	oldStatus AppealStatus,
	newStatus AppealStatus,
	changedBy string,
	reason string,
	metadata map[string]interface{},
) error {
	var userID *int

	// Try to extract user_id from context if available
	if uid, exists := ctx.Value("user_id").(int); exists {
		userID = &uid
	}

	// Convert metadata to JSON
	jsonMetadata := datatypes.JSONMap{}
	if metadata != nil {
		data, _ := json.Marshal(metadata)
		json.Unmarshal(data, &jsonMetadata)
	}

	change := StatusChange{
		AppealID:  appealID,
		UserID:    userID,
		OldStatus: oldStatus,
		NewStatus: newStatus,
		ChangedBy: changedBy,
		Reason:    reason,
		Metadata:  jsonMetadata,
		CreatedAt: time.Now(),
	}

	return ahs.db.WithContext(ctx).
		Table("appeal_status_changes").
		Create(&change).Error
}

// GetAppealTimeline returns the complete timeline for an appeal
func (ahs *AppealHistoryService) GetAppealTimeline(
	ctx context.Context,
	appealID int,
) (*AppealTimeline, error) {
	// Get appeal details
	var appeal Appeal
	result := ahs.db.WithContext(ctx).
		Table("appeals").
		Where("id = ?", appealID).
		First(&appeal)

	if result.Error != nil {
		return nil, result.Error
	}

	// Get all status changes
	var changes []StatusChange
	result = ahs.db.WithContext(ctx).
		Table("appeal_status_changes").
		Where("appeal_id = ?", appealID).
		Order("created_at ASC").
		Scan(&changes)

	if result.Error != nil {
		return nil, result.Error
	}

	// Build timeline events
	timeline := &AppealTimeline{
		AppealID:      appealID,
		UserID:        appeal.UserID,
		CurrentStatus: appeal.Status,
		SubmittedAt:   appeal.CreatedAt,
		Events:        make([]TimelineEvent, 0, len(changes)),
	}

	for i, change := range changes {
		duration := 0.0
		if i > 0 {
			prevTime := changes[i-1].CreatedAt
			duration = change.CreatedAt.Sub(prevTime).Hours() / 24.0
		}

		metadata := make(map[string]interface{})
		if change.Metadata != nil {
			for k, v := range change.Metadata {
				metadata[k] = v
			}
		}

		event := TimelineEvent{
			Sequence:     i + 1,
			Status:       change.NewStatus,
			Timestamp:    change.CreatedAt,
			ChangedBy:    change.ChangedBy,
			Reason:       change.Reason,
			RelationDays: duration,
			Metadata:     metadata,
		}
		timeline.Events = append(timeline.Events, event)
	}

	// Calculate resolution days if resolved
	if len(timeline.Events) > 0 {
		lastEvent := timeline.Events[len(timeline.Events)-1]
		if lastEvent.Status == AppealApproved || lastEvent.Status == AppealDenied {
			resolution := lastEvent.Timestamp.Sub(timeline.SubmittedAt).Hours() / 24.0
			timeline.ResolutionDays = &resolution
			timeline.LastUpdateAt = lastEvent.Timestamp
		} else {
			timeline.LastUpdateAt = time.Now()
		}
	}

	return timeline, nil
}

// GetUserAppealHistory returns all appeals with status changes for a user
func (ahs *AppealHistoryService) GetUserAppealHistory(
	ctx context.Context,
	userID int,
	limit int,
	offset int,
) ([]AppealTimeline, error) {
	// Get user's appeals
	var appeals []Appeal
	result := ahs.db.WithContext(ctx).
		Table("appeals").
		Where("user_id = ?", userID).
		Order("created_at DESC").
		Limit(limit).
		Offset(offset).
		Scan(&appeals)

	if result.Error != nil {
		return nil, result.Error
	}

	// Build timeline for each appeal
	timelines := make([]AppealTimeline, 0, len(appeals))
	for _, appeal := range appeals {
		timeline, err := ahs.GetAppealTimeline(ctx, appeal.ID)
		if err != nil {
			continue // Skip on error
		}
		timelines = append(timelines, *timeline)
	}

	return timelines, nil
}

// GetStatusChangeHistory returns raw status changes for an appeal
func (ahs *AppealHistoryService) GetStatusChangeHistory(
	ctx context.Context,
	appealID int,
) ([]StatusChange, error) {
	var changes []StatusChange
	result := ahs.db.WithContext(ctx).
		Table("appeal_status_changes").
		Where("appeal_id = ?", appealID).
		Order("created_at ASC").
		Scan(&changes)

	return changes, result.Error
}

// GetTimingMetrics returns timing metrics for appeal resolution
func (ahs *AppealHistoryService) GetTimingMetrics(
	ctx context.Context,
) (map[string]interface{}, error) {
	var metrics struct {
		AvgResolutionDays     float64
		MedianResolutionDays  float64
		MinResolutionDays     float64
		MaxResolutionDays     float64
		AvgReviewStartDays    float64
		AvgReviewingDays      float64
		ResolutionRate        float64
		PendingAvgDays        float64
	}

	// Average resolution time for completed appeals
	ahs.db.WithContext(ctx).Raw(`
		SELECT
			AVG(EXTRACT(DAY FROM (sc1.created_at - a.created_at))) as avg_resolution_days
		FROM appeals a
		JOIN appeal_status_changes sc1 ON a.id = sc1.appeal_id
		WHERE sc1.new_status IN ('approved', 'denied')
		AND a.created_at > CURRENT_TIMESTAMP - INTERVAL '90 days'
		AND sc1.created_at = (
			SELECT MAX(created_at) FROM appeal_status_changes
			WHERE appeal_id = a.id AND new_status IN ('approved', 'denied')
		)
	`).Scan(&metrics.AvgResolutionDays)

	// Average time to start review
	ahs.db.WithContext(ctx).Raw(`
		SELECT
			AVG(EXTRACT(DAY FROM (sc1.created_at - a.created_at))) as avg_review_start_days
		FROM appeals a
		JOIN appeal_status_changes sc1 ON a.id = sc1.appeal_id
		WHERE sc1.new_status = 'reviewing'
		AND a.created_at > CURRENT_TIMESTAMP - INTERVAL '90 days'
		AND sc1.created_at = (
			SELECT MIN(created_at) FROM appeal_status_changes
			WHERE appeal_id = a.id AND new_status = 'reviewing'
		)
	`).Scan(&metrics.AvgReviewStartDays)

	// Average time in reviewing status
	ahs.db.WithContext(ctx).Raw(`
		SELECT
			AVG(EXTRACT(DAY FROM (sc2.created_at - sc1.created_at))) as avg_reviewing_days
		FROM appeal_status_changes sc1
		JOIN appeal_status_changes sc2 ON sc1.appeal_id = sc2.appeal_id
		WHERE sc1.new_status = 'reviewing'
		AND sc2.new_status IN ('approved', 'denied')
		AND sc2.created_at > sc1.created_at
		AND sc1.created_at > CURRENT_TIMESTAMP - INTERVAL '90 days'
	`).Scan(&metrics.AvgReviewingDays)

	// Resolution rate (resolved / total)
	var totalAppeals, resolvedAppeals int64
	ahs.db.WithContext(ctx).
		Table("appeals").
		Where("created_at > ?", time.Now().AddDate(0, 0, -90)).
		Count(&totalAppeals)

	ahs.db.WithContext(ctx).
		Table("appeals").
		Where("status IN ('approved', 'denied') AND created_at > ?", time.Now().AddDate(0, 0, -90)).
		Count(&resolvedAppeals)

	if totalAppeals > 0 {
		metrics.ResolutionRate = float64(resolvedAppeals) / float64(totalAppeals) * 100
	}

	// Average days pending for unresolved appeals
	ahs.db.WithContext(ctx).Raw(`
		SELECT
			AVG(EXTRACT(DAY FROM (CURRENT_TIMESTAMP - a.created_at))) as pending_avg_days
		FROM appeals a
		WHERE a.status IN ('pending', 'reviewing')
		AND a.created_at > CURRENT_TIMESTAMP - INTERVAL '90 days'
	`).Scan(&metrics.PendingAvgDays)

	return map[string]interface{}{
		"avg_resolution_days":   metrics.AvgResolutionDays,
		"avg_review_start_days": metrics.AvgReviewStartDays,
		"avg_reviewing_days":    metrics.AvgReviewingDays,
		"resolution_rate":       fmt.Sprintf("%.1f%%", metrics.ResolutionRate),
		"pending_avg_days":      metrics.PendingAvgDays,
	}, nil
}

// GetStatusDistribution returns distribution of appeals by status
func (ahs *AppealHistoryService) GetStatusDistribution(
	ctx context.Context,
) (map[AppealStatus]int64, error) {
	var statuses []struct {
		Status AppealStatus
		Count  int64
	}

	result := ahs.db.WithContext(ctx).
		Table("appeals").
		Select("status, COUNT(*) as count").
		Group("status").
		Scan(&statuses)

	if result.Error != nil {
		return nil, result.Error
	}

	distribution := make(map[AppealStatus]int64)
	for _, s := range statuses {
		distribution[s.Status] = s.Count
	}

	return distribution, nil
}

// GetChangeFrequency returns most frequent status changes
func (ahs *AppealHistoryService) GetChangeFrequency(
	ctx context.Context,
) ([]map[string]interface{}, error) {
	var changes []struct {
		OldStatus string
		NewStatus string
		Count     int64
	}

	result := ahs.db.WithContext(ctx).
		Table("appeal_status_changes").
		Select("old_status, new_status, COUNT(*) as count").
		Where("created_at > ?", time.Now().AddDate(0, -3, 0)). // Last 3 months
		Group("old_status, new_status").
		Order("count DESC").
		Limit(10).
		Scan(&changes)

	if result.Error != nil {
		return nil, result.Error
	}

	result_map := make([]map[string]interface{}, len(changes))
	for i, change := range changes {
		result_map[i] = map[string]interface{}{
			"from":  change.OldStatus,
			"to":    change.NewStatus,
			"count": change.Count,
		}
	}

	return result_map, nil
}

// NOTE: datatypes.JSONMap already implements sql.Scanner interface
// Defining methods on external types is not allowed in Go
