package rate_limiting

import (
	"context"
	"testing"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupAppealTestDB creates test database
func setupAppealTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to create test DB: %v", err)
	}

	db.AutoMigrate(&Appeal{}, &AppealReason{}, &ReputationEvent{})

	return db
}

// TestAppealServiceCreation tests service initialization
func TestAppealServiceCreation(t *testing.T) {
	db := setupAppealTestDB(t)
	rm := NewReputationManager(db)
	defer rm.Close()

	as := NewAppealService(db, rm)

	// Check default appeal reasons were created
	var count int64
	db.Model(&AppealReason{}).Count(&count)

	if count != 7 {
		t.Errorf("Expected 7 default appeal reasons, got %d", count)
	}
}

// TestSubmitAppeal tests submitting an appeal
func TestSubmitAppeal(t *testing.T) {
	db := setupAppealTestDB(t)
	rm := NewReputationManager(db)
	defer rm.Close()

	as := NewAppealService(db, rm)
	ctx := context.Background()

	// Create a violation
	violation := &ReputationEvent{
		UserID:        1,
		NodeID:        "test",
		EventType:     "violation",
		ScoreDelta:    -6.0,
		Severity:      2,
		ReasonCode:    "rate_limit_exceeded",
		SourceService: "api",
		Timestamp:     time.Now(),
		CreatedAt:     time.Now(),
	}
	db.Create(violation)

	// Submit appeal
	req := struct {
		Reason          string
		Description     string
		Evidence        string
		RequestedAction string
	}{
		Reason:          "false_positive",
		Description:     "This was a legitimate burst",
		Evidence:        "[]",
		RequestedAction: "restore",
	}

	appeal, err := as.SubmitAppeal(ctx, 1, violation.ID, req)
	if err != nil {
		t.Errorf("Failed to submit appeal: %v", err)
	}

	if appeal.Status != AppealPending {
		t.Errorf("Expected pending status, got %s", appeal.Status)
	}

	if appeal.Priority != AppealHigh {
		t.Errorf("Expected high priority for false_positive, got %s", appeal.Priority)
	}

	if appeal.ReputationLost != 6.0 {
		t.Errorf("Expected 6.0 reputation lost, got %f", appeal.ReputationLost)
	}
}

// TestAppealWindowExpired tests appeal window expiration
func TestAppealWindowExpired(t *testing.T) {
	db := setupAppealTestDB(t)
	rm := NewReputationManager(db)
	defer rm.Close()

	as := NewAppealService(db, rm)
	ctx := context.Background()

	// Create old violation (31 days ago)
	oldTime := time.Now().AddDate(0, 0, -31)
	violation := &ReputationEvent{
		UserID:        1,
		NodeID:        "test",
		EventType:     "violation",
		ScoreDelta:    -6.0,
		Severity:      2,
		ReasonCode:    "rate_limit_exceeded",
		SourceService: "api",
		Timestamp:     oldTime,
		CreatedAt:     oldTime,
	}
	db.Create(violation)

	// Try to appeal
	req := struct {
		Reason          string
		Description     string
		Evidence        string
		RequestedAction string
	}{
		Reason:          "false_positive",
		Description:     "This was a legitimate burst",
		Evidence:        "[]",
		RequestedAction: "restore",
	}

	_, err := as.SubmitAppeal(ctx, 1, violation.ID, req)
	if err == nil {
		t.Errorf("Expected error for expired appeal window")
	}
}

// TestDuplicateAppeal tests preventing duplicate appeals
func TestDuplicateAppeal(t *testing.T) {
	db := setupAppealTestDB(t)
	rm := NewReputationManager(db)
	defer rm.Close()

	as := NewAppealService(db, rm)
	ctx := context.Background()

	// Create violation
	violation := &ReputationEvent{
		UserID:        1,
		NodeID:        "test",
		EventType:     "violation",
		ScoreDelta:    -6.0,
		Severity:      2,
		ReasonCode:    "rate_limit_exceeded",
		SourceService: "api",
		Timestamp:     time.Now(),
		CreatedAt:     time.Now(),
	}
	db.Create(violation)

	req := struct {
		Reason          string
		Description     string
		Evidence        string
		RequestedAction string
	}{
		Reason:          "false_positive",
		Description:     "This was a legitimate burst",
		Evidence:        "[]",
		RequestedAction: "restore",
	}

	// First appeal should succeed
	_, err := as.SubmitAppeal(ctx, 1, violation.ID, req)
	if err != nil {
		t.Fatalf("First appeal failed: %v", err)
	}

	// Second appeal should fail
	_, err = as.SubmitAppeal(ctx, 1, violation.ID, req)
	if err == nil {
		t.Errorf("Expected error for duplicate appeal")
	}
}

// TestGetUserAppeals tests retrieving user appeals
func TestGetUserAppeals(t *testing.T) {
	db := setupAppealTestDB(t)
	rm := NewReputationManager(db)
	defer rm.Close()

	as := NewAppealService(db, rm)
	ctx := context.Background()

	// Create and appeal multiple violations
	for i := 1; i <= 3; i++ {
		violation := &ReputationEvent{
			UserID:        1,
			NodeID:        "test",
			EventType:     "violation",
			ScoreDelta:    -6.0,
			Severity:      2,
			ReasonCode:    "rate_limit_exceeded",
			SourceService: "api",
			Timestamp:     time.Now(),
			CreatedAt:     time.Now(),
		}
		db.Create(violation)

		req := struct {
			Reason          string
			Description     string
			Evidence        string
			RequestedAction string
		}{
			Reason:          "false_positive",
			Description:     "This was legitimate",
			Evidence:        "[]",
			RequestedAction: "restore",
		}
		as.SubmitAppeal(ctx, 1, violation.ID, req)
	}

	// Get all appeals
	appeals, err := as.GetUserAppeals(ctx, 1, nil)
	if err != nil {
		t.Errorf("Failed to get appeals: %v", err)
	}

	if len(appeals) != 3 {
		t.Errorf("Expected 3 appeals, got %d", len(appeals))
	}

	// Get pending appeals
	status := AppealPending
	appeals, err = as.GetUserAppeals(ctx, 1, &status)
	if err != nil {
		t.Errorf("Failed to get pending appeals: %v", err)
	}

	if len(appeals) != 3 {
		t.Errorf("Expected 3 pending appeals, got %d", len(appeals))
	}
}

// TestReviewAppeal tests approving an appeal
func TestReviewAppeal(t *testing.T) {
	db := setupAppealTestDB(t)
	rm := NewReputationManager(db)
	defer rm.Close()

	as := NewAppealService(db, rm)
	ctx := context.Background()

	// Create and submit appeal
	violation := &ReputationEvent{
		UserID:        1,
		NodeID:        "test",
		EventType:     "violation",
		ScoreDelta:    -6.0,
		Severity:      2,
		ReasonCode:    "rate_limit_exceeded",
		SourceService: "api",
		Timestamp:     time.Now(),
		CreatedAt:     time.Now(),
	}
	db.Create(violation)

	req := struct {
		Reason          string
		Description     string
		Evidence        string
		RequestedAction string
	}{
		Reason:          "false_positive",
		Description:     "This was legitimate",
		Evidence:        "[]",
		RequestedAction: "restore",
	}

	appeal, err := as.SubmitAppeal(ctx, 1, violation.ID, req)
	if err != nil {
		t.Fatalf("Failed to submit appeal: %v", err)
	}

	// Review and approve
	err = as.ReviewAppeal(ctx, appeal.ID, "reviewer1", AppealApproved, 6.0, "Approved - verified legitimate use")
	if err != nil {
		t.Errorf("Failed to review appeal: %v", err)
	}

	// Verify appeal status changed
	var updated Appeal
	db.First(&updated, appeal.ID)

	if updated.Status != AppealApproved {
		t.Errorf("Expected approved status, got %s", updated.Status)
	}

	if updated.ReviewedBy == nil || *updated.ReviewedBy != "reviewer1" {
		t.Errorf("Reviewer not set correctly")
	}

	if updated.ApprovedPoints == nil || *updated.ApprovedPoints != 6.0 {
		t.Errorf("Approved points not set correctly")
	}
}

// TestDenyAppeal tests denying an appeal
func TestDenyAppeal(t *testing.T) {
	db := setupAppealTestDB(t)
	rm := NewReputationManager(db)
	defer rm.Close()

	as := NewAppealService(db, rm)
	ctx := context.Background()

	// Create and submit appeal
	violation := &ReputationEvent{
		UserID:        1,
		NodeID:        "test",
		EventType:     "violation",
		ScoreDelta:    -6.0,
		Severity:      2,
		ReasonCode:    "rate_limit_exceeded",
		SourceService: "api",
		Timestamp:     time.Now(),
		CreatedAt:     time.Now(),
	}
	db.Create(violation)

	req := struct {
		Reason          string
		Description     string
		Evidence        string
		RequestedAction string
	}{
		Reason:          "burst_needed",
		Description:     "This was legitimate",
		Evidence:        "[]",
		RequestedAction: "restore",
	}

	appeal, err := as.SubmitAppeal(ctx, 1, violation.ID, req)
	if err != nil {
		t.Fatalf("Failed to submit appeal: %v", err)
	}

	// Review and deny
	err = as.ReviewAppeal(ctx, appeal.ID, "reviewer1", AppealDenied, 0, "Denied - violation was legitimate")
	if err != nil {
		t.Errorf("Failed to review appeal: %v", err)
	}

	// Verify appeal status changed
	var updated Appeal
	db.First(&updated, appeal.ID)

	if updated.Status != AppealDenied {
		t.Errorf("Expected denied status, got %s", updated.Status)
	}
}

// TestWithdrawAppeal tests user withdrawing appeal
func TestWithdrawAppeal(t *testing.T) {
	db := setupAppealTestDB(t)
	rm := NewReputationManager(db)
	defer rm.Close()

	as := NewAppealService(db, rm)
	ctx := context.Background()

	// Create and submit appeal
	violation := &ReputationEvent{
		UserID:        1,
		NodeID:        "test",
		EventType:     "violation",
		ScoreDelta:    -6.0,
		Severity:      2,
		ReasonCode:    "rate_limit_exceeded",
		SourceService: "api",
		Timestamp:     time.Now(),
		CreatedAt:     time.Now(),
	}
	db.Create(violation)

	req := struct {
		Reason          string
		Description     string
		Evidence        string
		RequestedAction string
	}{
		Reason:          "false_positive",
		Description:     "This was legitimate",
		Evidence:        "[]",
		RequestedAction: "restore",
	}

	appeal, err := as.SubmitAppeal(ctx, 1, violation.ID, req)
	if err != nil {
		t.Fatalf("Failed to submit appeal: %v", err)
	}

	// Withdraw appeal
	err = as.WithdrawAppeal(ctx, 1, appeal.ID)
	if err != nil {
		t.Errorf("Failed to withdraw appeal: %v", err)
	}

	// Verify status changed
	var updated Appeal
	db.First(&updated, appeal.ID)

	if updated.Status != AppealWithdrawn {
		t.Errorf("Expected withdrawn status, got %s", updated.Status)
	}
}

// TestGetAppealReasons tests retrieving appeal reasons
func TestGetAppealReasons(t *testing.T) {
	db := setupAppealTestDB(t)
	rm := NewReputationManager(db)
	defer rm.Close()

	as := NewAppealService(db, rm)
	ctx := context.Background()

	reasons, err := as.GetAppealReasons(ctx)
	if err != nil {
		t.Errorf("Failed to get reasons: %v", err)
	}

	if len(reasons) != 7 {
		t.Errorf("Expected 7 reasons, got %d", len(reasons))
	}

	// Check specific reason exists
	found := false
	for _, r := range reasons {
		if r.Code == "false_positive" {
			found = true
			break
		}
	}

	if !found {
		t.Errorf("false_positive reason not found")
	}
}

// TestGetAppealMetrics tests getting appeal metrics
func TestGetAppealMetrics(t *testing.T) {
	db := setupAppealTestDB(t)
	rm := NewReputationManager(db)
	defer rm.Close()

	as := NewAppealService(db, rm)
	ctx := context.Background()

	// Create some appeals
	for i := 1; i <= 5; i++ {
		violation := &ReputationEvent{
			UserID:        1,
			NodeID:        "test",
			EventType:     "violation",
			ScoreDelta:    -6.0,
			Severity:      2,
			ReasonCode:    "rate_limit_exceeded",
			SourceService: "api",
			Timestamp:     time.Now(),
			CreatedAt:     time.Now(),
		}
		db.Create(violation)

		req := struct {
			Reason          string
			Description     string
			Evidence        string
			RequestedAction string
		}{
			Reason:          "false_positive",
			Description:     "This was legitimate",
			Evidence:        "[]",
			RequestedAction: "restore",
		}

		as.SubmitAppeal(ctx, 1, violation.ID, req)
	}

	metrics, err := as.GetAppealMetrics(ctx)
	if err != nil {
		t.Errorf("Failed to get metrics: %v", err)
	}

	if metrics.TotalAppeals != 5 {
		t.Errorf("Expected 5 appeals, got %d", metrics.TotalAppeals)
	}

	if metrics.PendingAppeals != 5 {
		t.Errorf("Expected 5 pending, got %d", metrics.PendingAppeals)
	}
}

// TestGetAppealStats tests user appeal statistics
func TestGetAppealStats(t *testing.T) {
	db := setupAppealTestDB(t)
	rm := NewReputationManager(db)
	defer rm.Close()

	as := NewAppealService(db, rm)
	ctx := context.Background()

	// Create appeals
	violation := &ReputationEvent{
		UserID:        1,
		NodeID:        "test",
		EventType:     "violation",
		ScoreDelta:    -6.0,
		Severity:      2,
		ReasonCode:    "rate_limit_exceeded",
		SourceService: "api",
		Timestamp:     time.Now(),
		CreatedAt:     time.Now(),
	}
	db.Create(violation)

	req := struct {
		Reason          string
		Description     string
		Evidence        string
		RequestedAction string
	}{
		Reason:          "false_positive",
		Description:     "This was legitimate",
		Evidence:        "[]",
		RequestedAction: "restore",
	}

	appeal, _ := as.SubmitAppeal(ctx, 1, violation.ID, req)

	// Approve it
	as.ReviewAppeal(ctx, appeal.ID, "reviewer", AppealApproved, 6.0, "Approved")

	// Get stats
	stats, err := as.GetAppealStats(ctx, 1)
	if err != nil {
		t.Errorf("Failed to get stats: %v", err)
	}

	if stats["total_appeals"].(int64) != 1 {
		t.Errorf("Expected 1 appeal")
	}

	if stats["approved_appeals"].(int64) != 1 {
		t.Errorf("Expected 1 approved")
	}

	if stats["approval_rate"].(float64) != 1.0 {
		t.Errorf("Expected 100% approval rate")
	}
}

// TestExpireOldAppeals tests marking old appeals as expired
func TestExpireOldAppeals(t *testing.T) {
	db := setupAppealTestDB(t)
	rm := NewReputationManager(db)
	defer rm.Close()

	as := NewAppealService(db, rm)
	ctx := context.Background()

	// Create old appeal (expired)
	oldAppeal := &Appeal{
		UserID:        1,
		ViolationID:   1,
		Status:        AppealPending,
		Priority:      AppealMedium,
		Reason:        "test",
		Description:   "test",
		CreatedAt:     time.Now().AddDate(0, 0, -31),
		UpdatedAt:     time.Now().AddDate(0, 0, -31),
		ExpiresAt:     time.Now().AddDate(0, 0, -1), // Expired
	}
	db.Create(oldAppeal)

	// Create new appeal (not expired)
	newAppeal := &Appeal{
		UserID:        1,
		ViolationID:   2,
		Status:        AppealPending,
		Priority:      AppealMedium,
		Reason:        "test",
		Description:   "test",
		CreatedAt:     time.Now(),
		UpdatedAt:     time.Now(),
		ExpiresAt:     time.Now().AddDate(0, 0, 30),
	}
	db.Create(newAppeal)

	// Expire old appeals
	affected, err := as.ExpireOldAppeals(ctx)
	if err != nil {
		t.Errorf("Failed to expire appeals: %v", err)
	}

	if affected != 1 {
		t.Errorf("Expected 1 appeal expired, got %d", affected)
	}

	// Verify status changed
	var updated Appeal
	db.First(&updated, oldAppeal.ID)

	if updated.Status != AppealExpired {
		t.Errorf("Expected expired status, got %s", updated.Status)
	}
}

// BenchmarkSubmitAppeal benchmarks appeal submission
func BenchmarkSubmitAppeal(b *testing.B) {
	db := setupAppealTestDB(&testing.T{})
	rm := NewReputationManager(db)
	defer rm.Close()

	as := NewAppealService(db, rm)
	ctx := context.Background()

	// Pre-create violations
	for i := 0; i < b.N; i++ {
		violation := &ReputationEvent{
			UserID:        (i % 100) + 1,
			NodeID:        "test",
			EventType:     "violation",
			ScoreDelta:    -6.0,
			Severity:      2,
			ReasonCode:    "rate_limit_exceeded",
			SourceService: "api",
			Timestamp:     time.Now(),
			CreatedAt:     time.Now(),
		}
		db.Create(violation)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		violation := &ReputationEvent{}
		db.Where("user_id = ?", (i%100)+1).First(violation)

		req := struct {
			Reason          string
			Description     string
			Evidence        string
			RequestedAction string
		}{
			Reason:          "false_positive",
			Description:     "test",
			Evidence:        "[]",
			RequestedAction: "restore",
		}

		as.SubmitAppeal(ctx, (i%100)+1, violation.ID, req)
	}
}

// BenchmarkReviewAppeal benchmarks appeal review
func BenchmarkReviewAppeal(b *testing.B) {
	db := setupAppealTestDB(&testing.T{})
	rm := NewReputationManager(db)
	defer rm.Close()

	as := NewAppealService(db, rm)
	ctx := context.Background()

	// Pre-create appeals
	appeals := make([]*Appeal, b.N)
	for i := 0; i < b.N; i++ {
		violation := &ReputationEvent{
			UserID:        1,
			NodeID:        "test",
			EventType:     "violation",
			ScoreDelta:    -6.0,
			Severity:      2,
			ReasonCode:    "rate_limit_exceeded",
			SourceService: "api",
			Timestamp:     time.Now(),
			CreatedAt:     time.Now(),
		}
		db.Create(violation)

		req := struct {
			Reason          string
			Description     string
			Evidence        string
			RequestedAction string
		}{
			Reason:          "false_positive",
			Description:     "test",
			Evidence:        "[]",
			RequestedAction: "restore",
		}

		appeal, _ := as.SubmitAppeal(ctx, 1, violation.ID, req)
		appeals[i] = appeal
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		as.ReviewAppeal(ctx, appeals[i].ID, "reviewer", AppealApproved, 6.0, "Approved")
	}
}
