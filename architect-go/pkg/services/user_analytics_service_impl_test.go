package services

import (
	"context"
	"testing"
	"time"

	"architect-go/pkg/dto"
)

// Tests for UserAnalyticsService

func TestGetUserActivity(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getUserActivityFunc: func(ctx context.Context, sd, ed, g string) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"date":             startDate,
					"active_users":     float64(450),
					"new_users":        float64(45),
					"returning_users":  float64(380),
					"churned_users":    float64(15),
					"dau":              float64(450),
					"mau":              float64(2150),
				},
			}, nil
		},
	}

	service := NewUserAnalyticsService(mockRepo)
	results, err := service.GetActivity(context.Background(), startDate, endDate, "day")

	if err != nil {
		t.Fatalf("GetActivity failed: %v", err)
	}

	if len(results) == 0 {
		t.Error("Expected results, got empty")
	}

	if results[0].ActiveUsers != 450 {
		t.Errorf("Expected 450 active users, got %d", results[0].ActiveUsers)
	}

	if results[0].NewUsers != 45 {
		t.Errorf("Expected 45 new users, got %d", results[0].NewUsers)
	}
}

func TestGetUserEngagement(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getUserEngagementFunc: func(ctx context.Context, sd, ed string) (map[string]interface{}, error) {
			return map[string]interface{}{
				"period":                   "2026-01-18 to 2026-02-17",
				"avg_session_duration_seconds": float64(1800),
				"sessions_per_user":        float64(3.5),
				"avg_actions_per_session":  float64(12),
				"engagement_score":         float64(72.5),
				"engagement_trend_percent": float64(3.2),
			}, nil
		},
	}

	service := NewUserAnalyticsService(mockRepo)
	result, err := service.GetEngagement(context.Background(), startDate, endDate)

	if err != nil {
		t.Fatalf("GetEngagement failed: %v", err)
	}

	if result.EngagementScore < 0 || result.EngagementScore > 100 {
		t.Errorf("Expected engagement score 0-100, got %f", result.EngagementScore)
	}

	if result.SessionsPerUser <= 0 {
		t.Errorf("Expected positive sessions per user, got %f", result.SessionsPerUser)
	}
}

func TestGetFeatureAdoption(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getFeatureAdoptionFunc: func(ctx context.Context, sd, ed, featureName string) (map[string]interface{}, error) {
			return map[string]interface{}{
				"feature_name":            featureName,
				"adopted_users":           float64(850),
				"total_users":             float64(2150),
				"adoption_percent":        float64(39.5),
				"days_to_adopt":           float64(7.5),
				"adoption_trend_percent":  float64(8.3),
			}, nil
		},
	}

	service := NewUserAnalyticsService(mockRepo)
	result, err := service.GetFeatureAdoption(context.Background(), startDate, endDate, "dark_mode")

	if err != nil {
		t.Fatalf("GetFeatureAdoption failed: %v", err)
	}

	if result.FeatureName != "dark_mode" {
		t.Errorf("Expected feature_name 'dark_mode', got '%s'", result.FeatureName)
	}

	if result.AdoptionPercent < 0 || result.AdoptionPercent > 100 {
		t.Errorf("Expected adoption 0-100, got %f", result.AdoptionPercent)
	}

	if result.AdoptedUsers > result.TotalUsers {
		t.Errorf("Adopted users (%d) should not exceed total users (%d)", result.AdoptedUsers, result.TotalUsers)
	}
}

func TestPredictUserChurn(t *testing.T) {
	mockRepo := &MockAnalyticsRepository{
		predictUserChurnFunc: func(ctx context.Context, userID string) (map[string]interface{}, error) {
			return map[string]interface{}{
				"user_id":                userID,
				"churn_risk_percent":     float64(35.5),
				"risk_level":             "medium",
				"risk_factors":           []interface{}{"decreased_engagement", "low_session_frequency"},
				"days_since_last_action": float64(14),
				"recommended_action":     "Send re-engagement email",
			}, nil
		},
	}

	service := NewUserAnalyticsService(mockRepo)
	result, err := service.PredictChurn(context.Background(), "user_12345")

	if err != nil {
		t.Fatalf("PredictChurn failed: %v", err)
	}

	if result.UserID != "user_12345" {
		t.Errorf("Expected user_id 'user_12345', got '%s'", result.UserID)
	}

	if result.ChurnRisk < 0 || result.ChurnRisk > 100 {
		t.Errorf("Expected churn risk 0-100, got %f", result.ChurnRisk)
	}

	if result.RiskLevel != "medium" {
		t.Errorf("Expected risk_level 'medium', got '%s'", result.RiskLevel)
	}

	if len(result.RiskFactors) == 0 {
		t.Error("Expected risk factors, got empty")
	}
}

func TestGetUserSegmentation(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getUserSegmentationFunc: func(ctx context.Context, sd, ed string) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"segment_name":        "Power Users",
					"user_count":          float64(250),
					"percentage":          float64(25.0),
					"avg_engagement_score": float64(85.5),
					"avg_lifetime_value":  float64(1500.0),
					"characteristics":     []interface{}{"frequent_usage", "high_retention"},
				},
				{
					"segment_name":        "At-Risk Users",
					"user_count":          float64(150),
					"percentage":          float64(15.0),
					"avg_engagement_score": float64(25.0),
					"avg_lifetime_value":  float64(300.0),
					"characteristics":     []interface{}{"low_engagement", "high_churn_risk"},
				},
			}, nil
		},
	}

	service := NewUserAnalyticsService(mockRepo)
	results, err := service.GetSegmentation(context.Background(), startDate, endDate)

	if err != nil {
		t.Fatalf("GetSegmentation failed: %v", err)
	}

	if len(results) != 2 {
		t.Errorf("Expected 2 segments, got %d", len(results))
	}

	totalPercentage := results[0].Percentage + results[1].Percentage
	if totalPercentage != 40.0 {
		t.Errorf("Expected total percentage 40.0, got %f", totalPercentage)
	}

	if results[0].AvgEngagement > results[1].AvgEngagement {
		// Power Users should have higher engagement than At-Risk Users
	} else {
		t.Error("Expected Power Users to have higher engagement than At-Risk Users")
	}
}

func TestCalculateNPS(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		calculateNPSFunc: func(ctx context.Context, sd, ed string) (map[string]interface{}, error) {
			return map[string]interface{}{
				"period":      "2026-01-18 to 2026-02-17",
				"promoters":   float64(300),
				"passives":    float64(200),
				"detractors":  float64(100),
				"nps":         float64(40.0),
				"trend_percent": float64(5.5),
			}, nil
		},
	}

	service := NewUserAnalyticsService(mockRepo)
	result, err := service.CalculateNPS(context.Background(), startDate, endDate)

	if err != nil {
		t.Fatalf("CalculateNPS failed: %v", err)
	}

	totalRespondents := result.Promoters + result.Passives + result.Detractors
	if totalRespondents != 600 {
		t.Errorf("Expected 600 total respondents, got %d", totalRespondents)
	}

	if result.NPS < -100 || result.NPS > 100 {
		t.Errorf("Expected NPS -100 to 100, got %f", result.NPS)
	}

	if result.NPS != 40.0 {
		t.Errorf("Expected NPS 40.0, got %f", result.NPS)
	}
}

func TestGetUserDemographics(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getUserDemographicsFunc: func(ctx context.Context, sd, ed string) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"segment_name":        "Age 18-25",
					"user_count":          float64(150),
					"percentage":          float64(15.0),
					"avg_engagement_score": float64(72.0),
					"avg_lifetime_value":  float64(650.0),
				},
				{
					"segment_name":        "Age 26-35",
					"user_count":          float64(350),
					"percentage":          float64(35.0),
					"avg_engagement_score": float64(78.5),
					"avg_lifetime_value":  float64(1200.0),
				},
			}, nil
		},
	}

	service := NewUserAnalyticsService(mockRepo)
	results, err := service.GetDemographics(context.Background(), startDate, endDate)

	if err != nil {
		t.Fatalf("GetDemographics failed: %v", err)
	}

	if len(results) != 2 {
		t.Errorf("Expected 2 demographic segments, got %d", len(results))
	}

	if results[0].AvgLifetimeValue < 0 {
		t.Errorf("Expected positive lifetime value, got %f", results[0].AvgLifetimeValue)
	}
}

func TestGetGeographyAnalysis(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getGeographyAnalysisFunc: func(ctx context.Context, sd, ed string) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"segment_name":        "North America",
					"user_count":          float64(450),
					"percentage":          float64(45.0),
					"avg_engagement_score": float64(75.0),
					"avg_lifetime_value":  float64(1200.0),
				},
				{
					"segment_name":        "Europe",
					"user_count":          float64(350),
					"percentage":          float64(35.0),
					"avg_engagement_score": float64(72.0),
					"avg_lifetime_value":  float64(1150.0),
				},
			}, nil
		},
	}

	service := NewUserAnalyticsService(mockRepo)
	results, err := service.GetGeographyAnalysis(context.Background(), startDate, endDate)

	if err != nil {
		t.Fatalf("GetGeographyAnalysis failed: %v", err)
	}

	if len(results) != 2 {
		t.Errorf("Expected 2 geographic regions, got %d", len(results))
	}

	totalPercentage := results[0].Percentage + results[1].Percentage
	if totalPercentage != 80.0 {
		t.Errorf("Expected total percentage 80.0, got %f", totalPercentage)
	}
}

func TestAnalyzeDeviceUsage(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		analyzeDeviceUsageFunc: func(ctx context.Context, sd, ed string) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"segment_name":        "Desktop",
					"user_count":          float64(600),
					"percentage":          float64(60.0),
					"avg_engagement_score": float64(78.0),
					"avg_lifetime_value":  float64(1300.0),
				},
				{
					"segment_name":        "Mobile",
					"user_count":          float64(400),
					"percentage":          float64(40.0),
					"avg_engagement_score": float64(68.0),
					"avg_lifetime_value":  float64(950.0),
				},
			}, nil
		},
	}

	service := NewUserAnalyticsService(mockRepo)
	results, err := service.AnalyzeDeviceUsage(context.Background(), startDate, endDate)

	if err != nil {
		t.Fatalf("AnalyzeDeviceUsage failed: %v", err)
	}

	if len(results) != 2 {
		t.Errorf("Expected 2 device types, got %d", len(results))
	}

	// Desktop users should have higher lifetime value
	if results[0].AvgLifetimeValue <= results[1].AvgLifetimeValue {
		t.Error("Expected desktop users to have higher average lifetime value")
	}

	totalUsers := results[0].UserCount + results[1].UserCount
	if totalUsers != 1000 {
		t.Errorf("Expected 1000 total users, got %d", totalUsers)
	}
}

func TestGetUserLifetimeValue(t *testing.T) {
	mockRepo := &MockAnalyticsRepository{
		getUserLifetimeValueFunc: func(ctx context.Context, userID string) (map[string]interface{}, error) {
			return map[string]interface{}{
				"user_id":                userID,
				"lifetime_value":         float64(1250.50),
				"predicted_value_next_12m": float64(1500.75),
				"segment_average":        float64(950.00),
				"ranking":                "High",
				"recommended_action":     "Premium upgrade",
			}, nil
		},
	}

	service := NewUserAnalyticsService(mockRepo)
	result, err := service.GetLifetimeValue(context.Background(), "user_999")

	if err != nil {
		t.Fatalf("GetLifetimeValue failed: %v", err)
	}

	if result.UserID != "user_999" {
		t.Errorf("Expected user_id 'user_999', got '%s'", result.UserID)
	}

	if result.PredictedValue <= result.LifetimeValue {
		t.Error("Expected predicted value to be greater than lifetime value")
	}

	if result.Ranking != "High" {
		t.Errorf("Expected ranking 'High', got '%s'", result.Ranking)
	}
}

func TestGetLoyaltyScore(t *testing.T) {
	mockRepo := &MockAnalyticsRepository{
		getUserLoyaltyScoreFunc: func(ctx context.Context, userID string) (float64, error) {
			return 78.5, nil
		},
	}

	service := NewUserAnalyticsService(mockRepo)
	result, err := service.GetLoyaltyScore(context.Background(), "user_555")

	if err != nil {
		t.Fatalf("GetLoyaltyScore failed: %v", err)
	}

	if result < 0 || result > 100 {
		t.Errorf("Expected loyalty score 0-100, got %f", result)
	}

	if result != 78.5 {
		t.Errorf("Expected loyalty score 78.5, got %f", result)
	}
}

func TestGetBehaviorPatterns(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		getUserBehaviorPatternsFunc: func(ctx context.Context, sd, ed string) ([]map[string]interface{}, error) {
			return []map[string]interface{}{
				{
					"pattern_name":    "Evening Peak Usage",
					"frequency":       "daily",
					"peak_hours":      []interface{}{"18:00", "19:00", "20:00"},
					"affected_users":  float64(250),
				},
				{
					"pattern_name":    "Weekend Shopping",
					"frequency":       "weekly",
					"peak_days":       []interface{}{"Saturday", "Sunday"},
					"affected_users":  float64(180),
				},
			}, nil
		},
	}

	service := NewUserAnalyticsService(mockRepo)
	results, err := service.GetBehaviorPatterns(context.Background(), startDate, endDate)

	if err != nil {
		t.Fatalf("GetBehaviorPatterns failed: %v", err)
	}

	if len(results) != 2 {
		t.Errorf("Expected 2 behavior patterns, got %d", len(results))
	}
}

func TestUserExport(t *testing.T) {
	startDate := time.Now().AddDate(0, 0, -30)
	endDate := time.Now()

	mockRepo := &MockAnalyticsRepository{
		exportAnalyticsFunc: func(ctx context.Context, sd, ed string, metrics []string, format string) (map[string]interface{}, error) {
			return map[string]interface{}{
				"export_id":  "export_user_321",
				"status":     "completed",
				"created_at": time.Now(),
				"expires_at": time.Now().AddDate(0, 0, 7),
			}, nil
		},
	}

	service := NewUserAnalyticsService(mockRepo)
	result, err := service.Export(context.Background(), &dto.AnalyticsExportRequest{
		Format:    "pdf",
		StartDate: startDate,
		EndDate:   endDate,
		Metrics:   []string{"user_segmentation", "churn_prediction"},
	})

	if err != nil {
		t.Fatalf("Export failed: %v", err)
	}

	if result.ExportID == "" {
		t.Error("Expected non-empty export_id")
	}

	if result.Status != "completed" {
		t.Errorf("Expected status 'completed', got '%s'", result.Status)
	}
}
