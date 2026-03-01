package rate_limiting

import (
	"context"
	"testing"
	"time"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupMLTestDB creates test database for ML tests
func setupMLTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to create test DB: %v", err)
	}

	db.Exec(`
		CREATE TABLE reputation_scores (
			id INTEGER PRIMARY KEY,
			user_id INTEGER UNIQUE,
			score REAL,
			tier TEXT
		)
	`)

	db.Exec(`
		CREATE TABLE user_analytics_summary (
			id INTEGER PRIMARY KEY,
			user_id INTEGER UNIQUE,
			trend_direction TEXT,
			projected_30day_score REAL
		)
	`)

	db.Exec(`
		CREATE TABLE appeals (
			id INTEGER PRIMARY KEY,
			user_id INTEGER,
			violation_id INTEGER,
			reason TEXT,
			status TEXT,
			created_at TIMESTAMP,
			resolved_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE violations (
			id INTEGER PRIMARY KEY,
			user_id INTEGER,
			created_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE ml_predictions (
			id INTEGER PRIMARY KEY,
			appeal_id INTEGER,
			user_id INTEGER,
			prediction_type TEXT,
			prediction_value REAL,
			confidence REAL,
			model_version TEXT,
			predicted_at TIMESTAMP,
			actual_value REAL,
			accuracy_checked_at TIMESTAMP,
			created_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE auto_appeal_suggestions (
			id INTEGER PRIMARY KEY,
			user_id INTEGER,
			violation_id INTEGER,
			suggestion_reason TEXT,
			confidence REAL,
			predicted_success_rate REAL,
			user_accepted INTEGER,
			created_at TIMESTAMP
		)
	`)

	return db
}

// TestMLPredictionServiceCreation tests service initialization
func TestMLPredictionServiceCreation(t *testing.T) {
	db := setupMLTestDB(t)
	mps := NewMLPredictionService(db)

	if mps == nil {
		t.Errorf("Failed to create ML prediction service")
	}
}

// TestPredictReputationRecovery tests recovery prediction
func TestPredictReputationRecovery(t *testing.T) {
	db := setupMLTestDB(t)
	mps := NewMLPredictionService(db)

	// Create user data
	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (1, 35.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO user_analytics_summary (user_id, trend_direction, projected_30day_score)
		VALUES (1, 'improving', 45.0)
	`)

	prediction, err := mps.PredictReputationRecovery(context.Background(), 1)
	if err != nil {
		t.Errorf("Failed to predict recovery: %v", err)
	}

	if prediction == nil {
		t.Errorf("Prediction is nil")
	}

	if prediction.CurrentScore != 35.0 {
		t.Errorf("Expected score 35, got %f", prediction.CurrentScore)
	}

	if prediction.ConfidenceLevel < 0 || prediction.ConfidenceLevel > 1 {
		t.Errorf("Confidence out of range: %f", prediction.ConfidenceLevel)
	}

	if len(prediction.RequiredActions) == 0 {
		t.Errorf("No required actions generated")
	}
}

// TestPredictAppealApprovalProbability tests approval probability
func TestPredictAppealApprovalProbability(t *testing.T) {
	db := setupMLTestDB(t)
	mps := NewMLPredictionService(db)

	// Create appeal
	db.Exec(`
		INSERT INTO appeals (id, user_id, violation_id, reason, status, created_at)
		VALUES (1, 10, 100, 'false_positive', 'pending', datetime('now'))
	`)

	// Create user appeals history
	for i := 0; i < 5; i++ {
		status := "approved"
		if i%2 == 0 {
			status = "denied"
		}
		db.Exec(`
			INSERT INTO appeals (user_id, violation_id, reason, status, created_at)
			VALUES (10, ?, 'false_positive', ?, datetime('now', '-30 days'))
		`, 100+i, status)
	}

	probability, err := mps.PredictAppealApprovalProbability(context.Background(), 1)
	if err != nil {
		t.Errorf("Failed to predict probability: %v", err)
	}

	if probability == nil {
		t.Errorf("Probability is nil")
	}

	if probability.ApprovalProbability < 0 || probability.ApprovalProbability > 1 {
		t.Errorf("Probability out of range: %f", probability.ApprovalProbability)
	}

	if probability.ApprovalProbability+probability.DenialProbability < 0.99 {
		t.Errorf("Probabilities don't sum to 1.0")
	}

	if len(probability.KeyFactors) == 0 {
		t.Errorf("No key factors provided")
	}

	if probability.RecommendedStrategy == "" {
		t.Errorf("No recommended strategy")
	}
}

// TestSuggestAutoAppeal generates auto-appeal suggestions
func TestSuggestAutoAppeal(t *testing.T) {
	db := setupMLTestDB(t)
	mps := NewMLPredictionService(db)

	// Create user violations
	for i := 1; i <= 3; i++ {
		db.Exec(`
			INSERT INTO violations (id, user_id, created_at)
			VALUES (?, 20, datetime('now', '-5 days'))
		`, i)
	}

	suggestions, err := mps.SuggestAutoAppeal(context.Background(), 20)
	if err != nil {
		t.Errorf("Failed to suggest appeals: %v", err)
	}

	// Should have suggestions for violations that haven't been appealed
	if suggestions == nil {
		t.Errorf("Suggestions is nil")
	}
}

// TestGetModelPerformance retrieves model metrics
func TestGetModelPerformance(t *testing.T) {
	db := setupMLTestDB(t)
	mps := NewMLPredictionService(db)

	// Create predictions
	for i := 0; i < 10; i++ {
		db.Exec(`
			INSERT INTO ml_predictions (user_id, prediction_type, prediction_value, confidence, model_version, predicted_at, created_at)
			VALUES (?, 'recovery_timeline', ?, 0.8, 'v1.0', datetime('now'), datetime('now'))
		`, 30+i, 50.0+float64(i)*5)
	}

	performance, err := mps.GetModelPerformance(context.Background(), PredictionTypeRecoveryTimeline)
	if err != nil {
		t.Errorf("Failed to get performance: %v", err)
	}

	if performance == nil {
		t.Errorf("Performance is nil")
	}

	if _, exists := performance["total_predictions"]; !exists {
		t.Errorf("total_predictions not in performance")
	}

	if _, exists := performance["avg_confidence"]; !exists {
		t.Errorf("avg_confidence not in performance")
	}
}

// TestReputationRecoveryDeclining tests declining trend prediction
func TestReputationRecoveryDeclining(t *testing.T) {
	db := setupMLTestDB(t)
	mps := NewMLPredictionService(db)

	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (2, 70.0, 'trusted')
	`)

	db.Exec(`
		INSERT INTO user_analytics_summary (user_id, trend_direction, projected_30day_score)
		VALUES (2, 'declining', 60.0)
	`)

	prediction, _ := mps.PredictReputationRecovery(context.Background(), 2)

	if prediction == nil {
		t.Errorf("Prediction is nil for declining user")
	}

	// Check that action recommends addressing violations
	foundAction := false
	for _, action := range prediction.RequiredActions {
		if len(action) > 0 && action != "" {
			foundAction = true
		}
	}

	if !foundAction {
		t.Errorf("No actions generated for declining user")
	}
}

// TestApprovalProbabilityHighConfidence tests high confidence prediction
func TestApprovalProbabilityHighConfidence(t *testing.T) {
	db := setupMLTestDB(t)
	mps := NewMLPredictionService(db)

	// Create appeal with high success history
	db.Exec(`
		INSERT INTO appeals (id, user_id, violation_id, reason, status, created_at)
		VALUES (2, 11, 101, 'system_error', 'pending', datetime('now'))
	`)

	for i := 0; i < 10; i++ {
		db.Exec(`
			INSERT INTO appeals (user_id, violation_id, reason, status, created_at)
			VALUES (11, ?, 'system_error', 'approved', datetime('now', '-30 days'))
		`, 100+i)
	}

	probability, _ := mps.PredictAppealApprovalProbability(context.Background(), 2)

	if probability == nil {
		t.Errorf("Probability is nil")
	}

	if probability.Confidence <= 0.7 {
		t.Errorf("Expected high confidence for user with history, got %f", probability.Confidence)
	}
}

// TestPredictionTypes tests all prediction types
func TestPredictionTypes(t *testing.T) {
	types := []PredictionType{
		PredictionTypeRecoveryTimeline,
		PredictionTypeApprovalProbability,
		PredictionTypeLanguageQuality,
	}

	for _, pType := range types {
		if pType == "" {
			t.Errorf("Prediction type is empty")
		}
	}
}

// BenchmarkPredictReputationRecovery benchmarks recovery prediction
func BenchmarkPredictReputationRecovery(b *testing.B) {
	db := setupMLTestDB(&testing.T{})
	mps := NewMLPredictionService(db)

	db.Exec(`
		INSERT INTO reputation_scores (user_id, score, tier)
		VALUES (100, 50.0, 'standard')
	`)

	db.Exec(`
		INSERT INTO user_analytics_summary (user_id, trend_direction, projected_30day_score)
		VALUES (100, 'improving', 60.0)
	`)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		mps.PredictReputationRecovery(context.Background(), 100)
	}
}

// BenchmarkPredictAppealApprovalProbability benchmarks approval prediction
func BenchmarkPredictAppealApprovalProbability(b *testing.B) {
	db := setupMLTestDB(&testing.T{})
	mps := NewMLPredictionService(db)

	db.Exec(`
		INSERT INTO appeals (id, user_id, violation_id, reason, status, created_at)
		VALUES (100, 100, 100, 'false_positive', 'pending', datetime('now'))
	`)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		mps.PredictAppealApprovalProbability(context.Background(), 100)
	}
}
