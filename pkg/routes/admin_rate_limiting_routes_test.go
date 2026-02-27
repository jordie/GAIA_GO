package routes

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"gorm.io/gorm"

	"github.com/jgirmay/GAIA_GO/pkg/services/rate_limiting"
)

// MockRateLimiter implements the RateLimiter interface for testing
type MockRateLimiter struct {
	rules      []rate_limiting.Rule
	quotas     map[string]*rate_limiting.Quota
	violations []rate_limiting.Violation
}

func (m *MockRateLimiter) CheckLimit(ctx context.Context, req rate_limiting.LimitCheckRequest) (rate_limiting.Decision, error) {
	return rate_limiting.Decision{Allowed: true}, nil
}

func (m *MockRateLimiter) GetUsage(ctx context.Context, system, scope, value string) (rate_limiting.Usage, error) {
	return rate_limiting.Usage{
		Current:   0,
		Limit:     100,
		Remaining: 100,
		ResetTime: time.Now().Add(1 * time.Hour),
	}, nil
}

func (m *MockRateLimiter) GetRules(ctx context.Context, system string) ([]rate_limiting.Rule, error) {
	return m.rules, nil
}

func (m *MockRateLimiter) CreateRule(ctx context.Context, rule rate_limiting.Rule) (int64, error) {
	rule.ID = int64(len(m.rules) + 1)
	m.rules = append(m.rules, rule)
	return rule.ID, nil
}

func (m *MockRateLimiter) UpdateRule(ctx context.Context, rule rate_limiting.Rule) error {
	for i, r := range m.rules {
		if r.ID == rule.ID {
			m.rules[i] = rule
			break
		}
	}
	return nil
}

func (m *MockRateLimiter) DeleteRule(ctx context.Context, ruleID int64) error {
	for i, r := range m.rules {
		if r.ID == ruleID {
			m.rules = append(m.rules[:i], m.rules[i+1:]...)
			break
		}
	}
	return nil
}

func (m *MockRateLimiter) GetRule(ctx context.Context, ruleID int64) (*rate_limiting.Rule, error) {
	for _, r := range m.rules {
		if r.ID == ruleID {
			return &r, nil
		}
	}
	return nil, nil
}

func (m *MockRateLimiter) IncrementQuota(ctx context.Context, system, scope, value, resourceType string, amount int) error {
	key := system + ":" + scope + ":" + value
	if quota, ok := m.quotas[key]; ok {
		quota.QuotaUsed += amount
	}
	return nil
}

func (m *MockRateLimiter) GetQuota(ctx context.Context, system, scope, value, resourceType string) (*rate_limiting.Quota, error) {
	key := system + ":" + scope + ":" + value
	if quota, ok := m.quotas[key]; ok {
		return quota, nil
	}
	return nil, nil
}

func (m *MockRateLimiter) GetViolations(ctx context.Context, system string, since time.Time) ([]rate_limiting.Violation, error) {
	return m.violations, nil
}

func (m *MockRateLimiter) GetViolationStats(ctx context.Context, system string) (map[string]interface{}, error) {
	return map[string]interface{}{
		"total_violations": len(m.violations),
		"by_scope": map[string]int{
			"ip": len(m.violations),
		},
	}, nil
}

func (m *MockRateLimiter) CleanupOldBuckets(ctx context.Context, before time.Time) (int64, error) {
	return 0, nil
}

func (m *MockRateLimiter) CleanupOldViolations(ctx context.Context, before time.Time) (int64, error) {
	return 0, nil
}

func (m *MockRateLimiter) CleanupOldMetrics(ctx context.Context, before time.Time) (int64, error) {
	return 0, nil
}

// ===== UNIT TESTS =====

func TestGetRateLimitStats(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	req, _ := http.NewRequest("GET", "/api/admin/rate-limiting/stats?system=global&days=7", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &response)
	assert.Equal(t, "global", response["system"])
	assert.Equal(t, float64(7), response["days_analyzed"])
}

func TestListRateLimitRules(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{
		rules: []rate_limiting.Rule{
			{
				ID:         1,
				SystemID:   "global",
				Scope:      "ip",
				LimitType:  rate_limiting.LimitPerMinute,
				LimitValue: 1000,
				Enabled:    true,
			},
		},
	}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	req, _ := http.NewRequest("GET", "/api/admin/rate-limiting/rules/global", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &response)
	assert.Greater(t, response["count"], float64(0))
}

func TestCreateRateLimitRule(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{
		rules: []rate_limiting.Rule{},
	}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	payload := map[string]interface{}{
		"system_id":    "global",
		"scope":        "ip",
		"limit_type":   "requests_per_minute",
		"limit_value":  1000,
		"priority":     1,
		"enabled":      true,
	}
	body, _ := json.Marshal(payload)

	req, _ := http.NewRequest("POST", "/api/admin/rate-limiting/rules", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusCreated, w.Code)

	var response map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &response)
	assert.True(t, response["success"].(bool))
}

func TestUpdateRateLimitRule(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{
		rules: []rate_limiting.Rule{
			{
				ID:         1,
				SystemID:   "global",
				Scope:      "ip",
				LimitType:  rate_limiting.LimitPerMinute,
				LimitValue: 1000,
				Enabled:    true,
				Priority:   1,
			},
		},
	}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	newLimit := 2000
	payload := map[string]interface{}{
		"limit_value": newLimit,
	}
	body, _ := json.Marshal(payload)

	req, _ := http.NewRequest("PUT", "/api/admin/rate-limiting/rules/1", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &response)
	assert.True(t, response["success"].(bool))
}

func TestDeleteRateLimitRule(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{
		rules: []rate_limiting.Rule{
			{
				ID:         1,
				SystemID:   "global",
				Scope:      "ip",
				LimitType:  rate_limiting.LimitPerMinute,
				LimitValue: 1000,
				Enabled:    true,
			},
		},
	}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	req, _ := http.NewRequest("DELETE", "/api/admin/rate-limiting/rules/1", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &response)
	assert.True(t, response["success"].(bool))
}

func TestGetRateLimitRule(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{
		rules: []rate_limiting.Rule{
			{
				ID:         1,
				SystemID:   "global",
				Scope:      "ip",
				LimitType:  rate_limiting.LimitPerMinute,
				LimitValue: 1000,
				Enabled:    true,
			},
		},
	}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	req, _ := http.NewRequest("GET", "/api/admin/rate-limiting/rules/global/1", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestGetViolations(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{
		violations: []rate_limiting.Violation{
			{
				ID:            1,
				SystemID:      "global",
				Scope:         "ip",
				ScopeValue:    "192.168.1.1",
				ViolatedLimit: 1000,
				ViolationTime: time.Now(),
				Blocked:       true,
			},
		},
	}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	req, _ := http.NewRequest("GET", "/api/admin/rate-limiting/violations/global?hours=24", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &response)
	assert.Greater(t, response["count"], float64(0))
}

func TestGetViolationStats(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{
		violations: []rate_limiting.Violation{
			{
				ID:         1,
				SystemID:   "global",
				Scope:      "ip",
				ScopeValue: "192.168.1.1",
				Blocked:    true,
			},
		},
	}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	req, _ := http.NewRequest("GET", "/api/admin/rate-limiting/violations/global/stats", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &response)
	assert.Greater(t, response["total_violations"], float64(0))
}

func TestGetQuota(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{
		quotas: map[string]*rate_limiting.Quota{
			"global:user:user123": {
				SystemID:     "global",
				Scope:        "user",
				ScopeValue:   "user123",
				QuotaLimit:   100,
				QuotaUsed:    50,
				QuotaPeriod:  rate_limiting.LimitPerDay,
				PeriodStart:  time.Now(),
				PeriodEnd:    time.Now().Add(24 * time.Hour),
			},
		},
	}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	req, _ := http.NewRequest("GET", "/api/admin/rate-limiting/quotas/global/user/user123", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestIncrementQuota(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{
		quotas: map[string]*rate_limiting.Quota{
			"global:user:user123": {
				SystemID:    "global",
				Scope:       "user",
				ScopeValue:  "user123",
				QuotaLimit:  100,
				QuotaUsed:   50,
				QuotaPeriod: rate_limiting.LimitPerDay,
			},
		},
	}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	payload := map[string]interface{}{
		"amount":         10,
		"resource_type": "api_call",
	}
	body, _ := json.Marshal(payload)

	req, _ := http.NewRequest("POST", "/api/admin/rate-limiting/quotas/global/user/user123/increment", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &response)
	assert.True(t, response["success"].(bool))
}

func TestCleanupOldBuckets(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	req, _ := http.NewRequest("POST", "/api/admin/rate-limiting/cleanup/buckets?days=7", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &response)
	assert.True(t, response["success"].(bool))
}

func TestCleanupOldViolations(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	req, _ := http.NewRequest("POST", "/api/admin/rate-limiting/cleanup/violations?days=30", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &response)
	assert.True(t, response["success"].(bool))
}

func TestCleanupOldMetrics(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	req, _ := http.NewRequest("POST", "/api/admin/rate-limiting/cleanup/metrics?days=90", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &response)
	assert.True(t, response["success"].(bool))
}

func TestGetRateLimitingHealth(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	req, _ := http.NewRequest("GET", "/api/admin/rate-limiting/health", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &response)
	assert.Equal(t, "healthy", response["status"])
}

func TestGetMetricsSummary(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	req, _ := http.NewRequest("GET", "/api/admin/rate-limiting/metrics/summary", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &response)
	assert.Equal(t, "healthy", response["system_status"])
}

// ===== EDGE CASE TESTS =====

func TestCreateRuleWithInvalidData(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	req, _ := http.NewRequest("POST", "/api/admin/rate-limiting/rules", bytes.NewBuffer([]byte("invalid")))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestUpdateNonexistentRule(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{
		rules: []rate_limiting.Rule{},
	}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	payload := map[string]interface{}{
		"limit_value": 2000,
	}
	body, _ := json.Marshal(payload)

	req, _ := http.NewRequest("PUT", "/api/admin/rate-limiting/rules/999", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusNotFound, w.Code)
}

func TestIncrementQuotaWithNegativeAmount(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{
		quotas: map[string]*rate_limiting.Quota{},
	}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	payload := map[string]interface{}{
		"amount":        -10,
		"resource_type": "api_call",
	}
	body, _ := json.Marshal(payload)

	req, _ := http.NewRequest("POST", "/api/admin/rate-limiting/quotas/global/user/user123/increment", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestGetRateLimitUsage(t *testing.T) {
	router := gin.New()
	mockLimiter := &MockRateLimiter{}

	RegisterRateLimitingRoutes(router, nil, mockLimiter)

	req, _ := http.NewRequest("GET", "/api/admin/rate-limiting/usage/global/ip/192.168.1.1", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response rate_limiting.Usage
	json.Unmarshal(w.Body.Bytes(), &response)
	assert.Equal(t, 100, response.Limit)
}
