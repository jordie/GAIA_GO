package rate_limiting

import (
	"context"
	"testing"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupHistoryTestDB creates test database for history tests
func setupHistoryTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to create test DB: %v", err)
	}

	db.Exec(`
		CREATE TABLE appeals (
			id INTEGER PRIMARY KEY,
			user_id INTEGER,
			violation_id INTEGER,
			status TEXT DEFAULT 'pending',
			priority TEXT,
			reason TEXT,
			description TEXT,
			evidence TEXT,
			reputation_lost REAL,
			requested_action TEXT,
			reviewed_by TEXT,
			review_comment TEXT,
			resolution TEXT,
			approved_points REAL,
			created_at TIMESTAMP,
			updated_at TIMESTAMP,
			expires_at TIMESTAMP,
			resolved_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE appeal_status_changes (
			id INTEGER PRIMARY KEY,
			appeal_id INTEGER,
			user_id INTEGER,
			old_status TEXT,
			new_status TEXT,
			changed_by TEXT,
			reason TEXT,
			metadata TEXT,
			created_at TIMESTAMP
		)
	`)

	return db
}

// TestHistoryServiceCreation tests service initialization
func TestHistoryServiceCreation(t *testing.T) {
	db := setupHistoryTestDB(t)
	hs := NewAppealHistoryService(db)

	if hs == nil {
		t.Errorf("Failed to create history service")
	}
}

// TestRecordStatusChange records a status change
func TestRecordStatusChange(t *testing.T) {
	db := setupHistoryTestDB(t)
	hs := NewAppealHistoryService(db)

	err := hs.RecordStatusChange(
		context.Background(),
		1,
		AppealPending,
		AppealReviewing,
		"admin_1",
		"Started review",
		map[string]interface{}{"reviewer_id": 123},
	)

	if err != nil {
		t.Errorf("Failed to record status change: %v", err)
	}

	// Verify recorded
	var count int64
	db.Table("appeal_status_changes").
		Where("appeal_id = ? AND new_status = ?", 1, AppealReviewing).
		Count(&count)

	if count == 0 {
		t.Errorf("Status change not recorded")
	}
}

// TestGetAppealTimeline retrieves appeal timeline
func TestGetAppealTimeline(t *testing.T) {
	db := setupHistoryTestDB(t)
	hs := NewAppealHistoryService(db)

	// Create appeal
	appeal := &Appeal{
		ID:        2,
		UserID:    200,
		Status:    AppealPending,
		CreatedAt: time.Now(),
		ExpiresAt: time.Now().AddDate(0, 0, 30),
	}

	db.Table("appeals").Create(appeal)

	// Record status changes
	hs.RecordStatusChange(context.Background(), 2, AppealPending, AppealReviewing, "admin", "Started", nil)
	time.Sleep(10 * time.Millisecond)
	hs.RecordStatusChange(context.Background(), 2, AppealReviewing, AppealApproved, "admin", "Approved", nil)

	timeline, err := hs.GetAppealTimeline(context.Background(), 2)
	if err != nil {
		t.Errorf("Failed to get timeline: %v", err)
	}

	if timeline == nil {
		t.Errorf("Timeline is nil")
	}

	if len(timeline.Events) < 2 {
		t.Errorf("Expected at least 2 events, got %d", len(timeline.Events))
	}
}

// TestGetUserAppealHistory retrieves user's appeal history
func TestGetUserAppealHistory(t *testing.T) {
	db := setupHistoryTestDB(t)
	hs := NewAppealHistoryService(db)

	// Create multiple appeals for user
	for i := 1; i <= 3; i++ {
		appeal := &Appeal{
			ID:        i,
			UserID:    201,
			Status:    AppealPending,
			CreatedAt: time.Now().AddDate(0, 0, -i),
			ExpiresAt: time.Now().AddDate(0, 0, 30-i),
		}
		db.Table("appeals").Create(appeal)
	}

	history, err := hs.GetUserAppealHistory(context.Background(), 201, 10, 0)
	if err != nil {
		t.Errorf("Failed to get user history: %v", err)
	}

	if len(history) != 3 {
		t.Errorf("Expected 3 appeals, got %d", len(history))
	}
}

// TestGetStatusChangeHistory retrieves raw status changes
func TestGetStatusChangeHistory(t *testing.T) {
	db := setupHistoryTestDB(t)
	hs := NewAppealHistoryService(db)

	appeal := &Appeal{
		ID:        3,
		UserID:    202,
		Status:    AppealPending,
		CreatedAt: time.Now(),
	}
	db.Table("appeals").Create(appeal)

	hs.RecordStatusChange(context.Background(), 3, AppealPending, AppealReviewing, "admin", "Review", nil)
	hs.RecordStatusChange(context.Background(), 3, AppealReviewing, AppealApproved, "admin", "Approved", nil)

	changes, err := hs.GetStatusChangeHistory(context.Background(), 3)
	if err != nil {
		t.Errorf("Failed to get status change history: %v", err)
	}

	if len(changes) != 2 {
		t.Errorf("Expected 2 changes, got %d", len(changes))
	}

	if changes[0].NewStatus != AppealReviewing {
		t.Errorf("Expected first change to AppealReviewing, got %s", changes[0].NewStatus)
	}

	if changes[1].NewStatus != AppealApproved {
		t.Errorf("Expected second change to AppealApproved, got %s", changes[1].NewStatus)
	}
}

// TestGetTimingMetrics returns timing metrics
func TestGetTimingMetrics(t *testing.T) {
	db := setupHistoryTestDB(t)
	hs := NewAppealHistoryService(db)

	// Create appeals with different timing
	for i := 1; i <= 5; i++ {
		appeal := &Appeal{
			ID:        100 + i,
			UserID:    300 + i,
			Status:    AppealApproved,
			CreatedAt: time.Now().AddDate(0, 0, -30),
			ExpiresAt: time.Now().AddDate(0, 0, -25),
		}
		db.Table("appeals").Create(appeal)

		// Record changes
		hs.RecordStatusChange(
			context.Background(),
			100+i,
			AppealPending,
			AppealReviewing,
			"admin",
			"Review",
			nil,
		)
		time.Sleep(5 * time.Millisecond)
		hs.RecordStatusChange(
			context.Background(),
			100+i,
			AppealReviewing,
			AppealApproved,
			"admin",
			"Approved",
			nil,
		)
	}

	metrics, err := hs.GetTimingMetrics(context.Background())
	if err != nil {
		t.Errorf("Failed to get metrics: %v", err)
	}

	if metrics == nil {
		t.Errorf("Metrics is nil")
	}

	if _, exists := metrics["resolution_rate"]; !exists {
		t.Errorf("resolution_rate not in metrics")
	}
}

// TestGetStatusDistribution returns status distribution
func TestGetStatusDistribution(t *testing.T) {
	db := setupHistoryTestDB(t)
	hs := NewAppealHistoryService(db)

	// Create appeals with different statuses
	statuses := []AppealStatus{AppealPending, AppealReviewing, AppealApproved, AppealPending}
	for i, status := range statuses {
		appeal := &Appeal{
			ID:        200 + i,
			UserID:    400 + i,
			Status:    status,
			CreatedAt: time.Now(),
		}
		db.Table("appeals").Create(appeal)
	}

	dist, err := hs.GetStatusDistribution(context.Background())
	if err != nil {
		t.Errorf("Failed to get distribution: %v", err)
	}

	if dist == nil {
		t.Errorf("Distribution is nil")
	}

	if dist[AppealPending] != 2 {
		t.Errorf("Expected 2 pending, got %d", dist[AppealPending])
	}

	if dist[AppealApproved] != 1 {
		t.Errorf("Expected 1 approved, got %d", dist[AppealApproved])
	}
}

// TestGetChangeFrequency returns most frequent changes
func TestGetChangeFrequency(t *testing.T) {
	db := setupHistoryTestDB(t)
	hs := NewAppealHistoryService(db)

	// Create appeals and changes
	for i := 0; i < 5; i++ {
		appeal := &Appeal{
			ID:        300 + i,
			UserID:    500 + i,
			Status:    AppealApproved,
			CreatedAt: time.Now(),
		}
		db.Table("appeals").Create(appeal)

		hs.RecordStatusChange(
			context.Background(),
			300+i,
			AppealPending,
			AppealReviewing,
			"admin",
			"Review",
			nil,
		)
		hs.RecordStatusChange(
			context.Background(),
			300+i,
			AppealReviewing,
			AppealApproved,
			"admin",
			"Approved",
			nil,
		)
	}

	changes, err := hs.GetChangeFrequency(context.Background())
	if err != nil {
		t.Errorf("Failed to get change frequency: %v", err)
	}

	if len(changes) == 0 {
		t.Errorf("No change frequencies returned")
	}
}

// TestResolutionDaysCalculation tests resolution days calculation
func TestResolutionDaysCalculation(t *testing.T) {
	db := setupHistoryTestDB(t)
	hs := NewAppealHistoryService(db)

	// Create appeal
	now := time.Now()
	appeal := &Appeal{
		ID:        400,
		UserID:    600,
		Status:    AppealApproved,
		CreatedAt: now,
		ExpiresAt: now.AddDate(0, 0, 30),
		ResolvedAt: &[]time.Time{now.Add(2 * 24 * time.Hour)}[0],
	}
	db.Table("appeals").Create(appeal)

	// Record changes
	hs.RecordStatusChange(context.Background(), 400, AppealPending, AppealReviewing, "admin", "", nil)
	time.Sleep(100 * time.Millisecond)
	hs.RecordStatusChange(context.Background(), 400, AppealReviewing, AppealApproved, "admin", "", nil)

	timeline, err := hs.GetAppealTimeline(context.Background(), 400)
	if err != nil {
		t.Errorf("Failed to get timeline: %v", err)
	}

	if timeline.ResolutionDays == nil {
		t.Errorf("ResolutionDays not calculated")
	} else if *timeline.ResolutionDays < 0 {
		t.Errorf("Resolution days is negative: %f", *timeline.ResolutionDays)
	}
}

// TestTimelineEventOrdering verifies events are in correct order
func TestTimelineEventOrdering(t *testing.T) {
	db := setupHistoryTestDB(t)
	hs := NewAppealHistoryService(db)

	appeal := &Appeal{
		ID:        401,
		UserID:    601,
		Status:    AppealApproved,
		CreatedAt: time.Now(),
	}
	db.Table("appeals").Create(appeal)

	// Record changes with delays
	for i, status := range []AppealStatus{AppealPending, AppealReviewing, AppealApproved} {
		if i > 0 {
			hs.RecordStatusChange(
				context.Background(),
				401,
				[]AppealStatus{AppealPending, AppealReviewing}[i-1],
				status,
				"admin",
				"",
				nil,
			)
			time.Sleep(10 * time.Millisecond)
		}
	}

	timeline, _ := hs.GetAppealTimeline(context.Background(), 401)

	for i, event := range timeline.Events {
		if event.Sequence != i+1 {
			t.Errorf("Event %d has sequence %d, expected %d", i, event.Sequence, i+1)
		}
	}
}

// BenchmarkRecordStatusChange benchmarks status recording
func BenchmarkRecordStatusChange(b *testing.B) {
	db := setupHistoryTestDB(&testing.T{})
	hs := NewAppealHistoryService(db)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		hs.RecordStatusChange(
			context.Background(),
			i,
			AppealPending,
			AppealReviewing,
			"admin",
			"Review",
			nil,
		)
	}
}

// BenchmarkGetAppealTimeline benchmarks timeline retrieval
func BenchmarkGetAppealTimeline(b *testing.B) {
	db := setupHistoryTestDB(&testing.T{})
	hs := NewAppealHistoryService(db)

	appeal := &Appeal{ID: 500, UserID: 700, Status: AppealPending, CreatedAt: time.Now()}
	db.Table("appeals").Create(appeal)

	for i := 0; i < 10; i++ {
		hs.RecordStatusChange(context.Background(), 500, AppealPending, AppealReviewing, "admin", "", nil)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		hs.GetAppealTimeline(context.Background(), 500)
	}
}
