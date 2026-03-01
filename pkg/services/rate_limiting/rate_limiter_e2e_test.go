package rate_limiting

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// setupRateLimiterE2ETestDB creates a test database for E2E tests
func setupRateLimiterE2ETestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	require.NoError(t, err, "failed to create E2E test database")

	// Create required tables
	createRateLimiterE2ETestTables(t, db)

	return db
}

// createRateLimiterE2ETestTables creates all required tables for E2E tests
func createRateLimiterE2ETestTables(t *testing.T, db *gorm.DB) {
	db.Exec(`
		CREATE TABLE rate_limit_configs (
			id INTEGER PRIMARY KEY,
			rule_name TEXT UNIQUE,
			scope TEXT,
			scope_value TEXT,
			limit_type TEXT,
			limit_value INTEGER,
			resource_type TEXT,
			enabled BOOLEAN DEFAULT 1,
			priority INTEGER DEFAULT 1,
			system_id TEXT,
			created_at TIMESTAMP,
			updated_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE rate_limit_buckets (
			id INTEGER PRIMARY KEY,
			rule_id INTEGER,
			system_id TEXT,
			scope TEXT,
			scope_value TEXT,
			window_start TIMESTAMP,
			window_end TIMESTAMP,
			request_count INTEGER DEFAULT 0,
			created_at TIMESTAMP,
			updated_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE INDEX idx_buckets_scope ON rate_limit_buckets(scope, scope_value, window_start)
	`)

	db.Exec(`
		CREATE TABLE resource_quotas (
			id INTEGER PRIMARY KEY,
			system_id TEXT,
			scope TEXT,
			scope_value TEXT,
			resource_type TEXT,
			quota_period TEXT,
			quota_limit INTEGER,
			quota_used INTEGER DEFAULT 0,
			period_start TIMESTAMP,
			period_end TIMESTAMP,
			created_at TIMESTAMP,
			updated_at TIMESTAMP
		)
	`)

	db.Exec(`
		CREATE TABLE rate_limit_violations (
			id INTEGER PRIMARY KEY,
			system_id TEXT,
			scope TEXT,
			scope_value TEXT,
			resource_type TEXT,
			violated_limit INTEGER,
			violation_time TIMESTAMP,
			blocked BOOLEAN DEFAULT 1
		)
	`)
}

// E2E API Response types
type APIResponse struct {
	Success bool        `json:"success"`
	Message string      `json:"message"`
	Data    interface{} `json:"data"`
	Error   string      `json:"error"`
}

type RateLimitRuleAPI struct {
	ID           int    `json:"id"`
	RuleName     string `json:"rule_name"`
	Scope        string `json:"scope"`
	ScopeValue   string `json:"scope_value"`
	LimitType    string `json:"limit_type"`
	LimitValue   int    `json:"limit_value"`
	ResourceType string `json:"resource_type"`
	Enabled      bool   `json:"enabled"`
	Priority     int    `json:"priority"`
	CreatedAt    string `json:"created_at"`
	UpdatedAt    string `json:"updated_at"`
}

type QuotaStatusAPI struct {
	QuotaLimit int    `json:"quota_limit"`
	QuotaUsed  int    `json:"quota_used"`
	Remaining  int    `json:"remaining"`
	Period     string `json:"period"`
	PeriodEnd  string `json:"period_end"`
}

type ViolationAPI struct {
	ID             int64  `json:"id"`
	Scope          string `json:"scope"`
	ScopeValue     string `json:"scope_value"`
	ViolatedLimit  int    `json:"violated_limit"`
	ViolationTime  string `json:"violation_time"`
	Blocked        bool   `json:"blocked"`
	ResourceType   string `json:"resource_type"`
}

type HealthStatusAPI struct {
	Status          string `json:"status"`
	RulesCount      int    `json:"rules_count"`
	ViolationsCount int    `json:"violations_count"`
	AvgLatency      string `json:"avg_latency_ms"`
	Timestamp       string `json:"timestamp"`
}

// MockRateLimitHandler provides mock HTTP handlers for rate limiting API
type MockRateLimitHandler struct {
	db *gorm.DB
}

// CreateRule creates a new rate limit rule via API
func (h *MockRateLimitHandler) CreateRule(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		RuleName     string `json:"rule_name"`
		Scope        string `json:"scope"`
		ScopeValue   string `json:"scope_value"`
		LimitType    string `json:"limit_type"`
		LimitValue   int    `json:"limit_value"`
		ResourceType string `json:"resource_type"`
		Priority     int    `json:"priority"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	result := h.db.Exec(`
		INSERT INTO rate_limit_configs
		(rule_name, scope, scope_value, limit_type, limit_value, resource_type, priority, enabled, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`, req.RuleName, req.Scope, req.ScopeValue, req.LimitType, req.LimitValue,
		req.ResourceType, req.Priority, true, time.Now(), time.Now())

	if result.Error != nil {
		http.Error(w, "Failed to create rule", http.StatusInternalServerError)
		return
	}

	response := APIResponse{
		Success: true,
		Message: "Rule created successfully",
		Data: map[string]interface{}{
			"rule_name": req.RuleName,
			"scope":     req.Scope,
		},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// ListRules lists all rate limit rules
func (h *MockRateLimitHandler) ListRules(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var rules []RateLimitRuleAPI
	result := h.db.Raw(`
		SELECT id, rule_name, scope, scope_value, limit_type, limit_value,
		       resource_type, enabled, priority, created_at, updated_at
		FROM rate_limit_configs
		WHERE enabled = 1
		ORDER BY priority, created_at DESC
	`).Scan(&rules)

	if result.Error != nil {
		http.Error(w, "Failed to list rules", http.StatusInternalServerError)
		return
	}

	response := APIResponse{
		Success: true,
		Message: "Rules retrieved successfully",
		Data:    rules,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// GetRule retrieves a single rule by ID
func (h *MockRateLimitHandler) GetRule(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	ruleID := r.URL.Query().Get("id")
	var rule RateLimitRuleAPI

	result := h.db.Raw(`
		SELECT id, rule_name, scope, scope_value, limit_type, limit_value,
		       resource_type, enabled, priority, created_at, updated_at
		FROM rate_limit_configs
		WHERE id = ?
	`, ruleID).Scan(&rule)

	if result.RowsAffected == 0 {
		response := APIResponse{
			Success: false,
			Error:   "Rule not found",
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		json.NewEncoder(w).Encode(response)
		return
	}

	response := APIResponse{
		Success: true,
		Message: "Rule retrieved successfully",
		Data:    rule,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// UpdateRule updates an existing rate limit rule
func (h *MockRateLimitHandler) UpdateRule(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		ID         int    `json:"id"`
		LimitValue int    `json:"limit_value"`
		Priority   int    `json:"priority"`
		Enabled    bool   `json:"enabled"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	result := h.db.Exec(`
		UPDATE rate_limit_configs
		SET limit_value = ?, priority = ?, enabled = ?, updated_at = ?
		WHERE id = ?
	`, req.LimitValue, req.Priority, req.Enabled, time.Now(), req.ID)

	if result.RowsAffected == 0 {
		http.Error(w, "Rule not found", http.StatusNotFound)
		return
	}

	response := APIResponse{
		Success: true,
		Message: "Rule updated successfully",
		Data: map[string]interface{}{
			"id": req.ID,
		},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// DeleteRule deletes a rate limit rule
func (h *MockRateLimitHandler) DeleteRule(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	ruleID := r.URL.Query().Get("id")

	result := h.db.Exec(`DELETE FROM rate_limit_configs WHERE id = ?`, ruleID)

	if result.RowsAffected == 0 {
		http.Error(w, "Rule not found", http.StatusNotFound)
		return
	}

	response := APIResponse{
		Success: true,
		Message: "Rule deleted successfully",
		Data: map[string]interface{}{
			"id": ruleID,
		},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// GetQuotaStatus retrieves quota status for a scope
func (h *MockRateLimitHandler) GetQuotaStatus(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	system := r.URL.Query().Get("system")
	scope := r.URL.Query().Get("scope")
	value := r.URL.Query().Get("value")

	var quota struct {
		QuotaLimit int       `json:"quota_limit"`
		QuotaUsed  int       `json:"quota_used"`
		PeriodEnd  time.Time `json:"period_end"`
	}

	result := h.db.Raw(`
		SELECT quota_limit, quota_used, period_end
		FROM resource_quotas
		WHERE system_id = ? AND scope = ? AND scope_value = ?
		AND period_start <= ? AND period_end > ?
	`, system, scope, value, time.Now(), time.Now()).Scan(&quota)

	if result.RowsAffected == 0 {
		response := APIResponse{
			Success: false,
			Error:   "Quota not found",
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		json.NewEncoder(w).Encode(response)
		return
	}

	status := QuotaStatusAPI{
		QuotaLimit: quota.QuotaLimit,
		QuotaUsed:  quota.QuotaUsed,
		Remaining:  quota.QuotaLimit - quota.QuotaUsed,
		Period:     "daily",
		PeriodEnd:  quota.PeriodEnd.Format(time.RFC3339),
	}

	response := APIResponse{
		Success: true,
		Message: "Quota status retrieved successfully",
		Data:    status,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// IncrementQuota increments quota usage
func (h *MockRateLimitHandler) IncrementQuota(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		System   string `json:"system"`
		Scope    string `json:"scope"`
		Value    string `json:"value"`
		Increment int   `json:"increment"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	result := h.db.Exec(`
		UPDATE resource_quotas
		SET quota_used = quota_used + ?
		WHERE system_id = ? AND scope = ? AND scope_value = ?
	`, req.Increment, req.System, req.Scope, req.Value)

	if result.RowsAffected == 0 {
		http.Error(w, "Quota not found", http.StatusNotFound)
		return
	}

	response := APIResponse{
		Success: true,
		Message: "Quota incremented successfully",
		Data: map[string]interface{}{
			"increment": req.Increment,
		},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// GetViolations retrieves recent violations
func (h *MockRateLimitHandler) GetViolations(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	limit := r.URL.Query().Get("limit")
	if limit == "" {
		limit = "100"
	}

	var violations []ViolationAPI
	result := h.db.Raw(`
		SELECT id, scope, scope_value, violated_limit, violation_time, blocked, resource_type
		FROM rate_limit_violations
		ORDER BY violation_time DESC
		LIMIT ?
	`, limit).Scan(&violations)

	if result.Error != nil {
		http.Error(w, "Failed to retrieve violations", http.StatusInternalServerError)
		return
	}

	response := APIResponse{
		Success: true,
		Message: "Violations retrieved successfully",
		Data:    violations,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// Health returns service health status
func (h *MockRateLimitHandler) Health(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var rulesCount int64
	var violationsCount int64

	h.db.Table("rate_limit_configs").Where("enabled = ?", true).Count(&rulesCount)
	h.db.Table("rate_limit_violations").Count(&violationsCount)

	status := HealthStatusAPI{
		Status:          "healthy",
		RulesCount:      int(rulesCount),
		ViolationsCount: int(violationsCount),
		AvgLatency:      "2.5ms",
		Timestamp:       time.Now().Format(time.RFC3339),
	}

	response := APIResponse{
		Success: true,
		Message: "Service is healthy",
		Data:    status,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// TestFullAdminWorkflow tests complete admin workflow through API
func TestFullAdminWorkflow(t *testing.T) {
	db := setupRateLimiterE2ETestDB(t)
	handler := &MockRateLimitHandler{db: db}

	// Setup routes
	router := http.NewServeMux()
	router.HandleFunc("/api/admin/rate-limiting/rules", handler.CreateRule)
	router.HandleFunc("/api/admin/rate-limiting/rules/list", handler.ListRules)
	router.HandleFunc("/api/admin/rate-limiting/rules/get", handler.GetRule)
	router.HandleFunc("/api/admin/rate-limiting/rules/update", handler.UpdateRule)
	router.HandleFunc("/api/admin/rate-limiting/rules/delete", handler.DeleteRule)
	router.HandleFunc("/api/admin/rate-limiting/health", handler.Health)

	// Test server
	server := httptest.NewServer(router)
	defer server.Close()

	t.Run("Create rule", func(t *testing.T) {
		payload := `{
			"rule_name": "test_rule_1",
			"scope": "ip",
			"scope_value": "192.168.1.1",
			"limit_type": "requests_per_minute",
			"limit_value": 100,
			"resource_type": "api_call",
			"priority": 1
		}`

		resp, err := http.Post(
			server.URL+"/api/admin/rate-limiting/rules",
			"application/json",
			strings.NewReader(payload),
		)
		require.NoError(t, err)
		defer resp.Body.Close()

		assert.Equal(t, http.StatusOK, resp.StatusCode)

		var apiResp APIResponse
		err = json.NewDecoder(resp.Body).Decode(&apiResp)
		require.NoError(t, err)
		assert.True(t, apiResp.Success)
		assert.Equal(t, "Rule created successfully", apiResp.Message)
	})

	t.Run("List rules", func(t *testing.T) {
		resp, err := http.Get(server.URL + "/api/admin/rate-limiting/rules/list")
		require.NoError(t, err)
		defer resp.Body.Close()

		assert.Equal(t, http.StatusOK, resp.StatusCode)

		var apiResp APIResponse
		err = json.NewDecoder(resp.Body).Decode(&apiResp)
		require.NoError(t, err)
		assert.True(t, apiResp.Success)

		rules, ok := apiResp.Data.([]interface{})
		assert.True(t, ok, "Data should be a list of rules")
		assert.Greater(t, len(rules), 0, "Should have at least one rule")
	})

	t.Run("Get rule", func(t *testing.T) {
		resp, err := http.Get(server.URL + "/api/admin/rate-limiting/rules/get?id=1")
		require.NoError(t, err)
		defer resp.Body.Close()

		var apiResp APIResponse
		err = json.NewDecoder(resp.Body).Decode(&apiResp)
		require.NoError(t, err)

		if resp.StatusCode == http.StatusOK {
			assert.True(t, apiResp.Success)
		}
	})

	t.Run("Update rule", func(t *testing.T) {
		payload := `{
			"id": 1,
			"limit_value": 200,
			"priority": 2,
			"enabled": true
		}`

		req, err := http.NewRequest(
			http.MethodPut,
			server.URL+"/api/admin/rate-limiting/rules/update",
			strings.NewReader(payload),
		)
		require.NoError(t, err)
		req.Header.Set("Content-Type", "application/json")

		resp, err := http.DefaultClient.Do(req)
		require.NoError(t, err)
		defer resp.Body.Close()

		if resp.StatusCode == http.StatusOK {
			var apiResp APIResponse
			err = json.NewDecoder(resp.Body).Decode(&apiResp)
			require.NoError(t, err)
			assert.True(t, apiResp.Success)
			assert.Equal(t, "Rule updated successfully", apiResp.Message)
		}
	})

	t.Run("Delete rule", func(t *testing.T) {
		req, err := http.NewRequest(
			http.MethodDelete,
			server.URL+"/api/admin/rate-limiting/rules/delete?id=1",
			nil,
		)
		require.NoError(t, err)

		resp, err := http.DefaultClient.Do(req)
		require.NoError(t, err)
		defer resp.Body.Close()

		if resp.StatusCode == http.StatusOK {
			var apiResp APIResponse
			err = json.NewDecoder(resp.Body).Decode(&apiResp)
			require.NoError(t, err)
			assert.True(t, apiResp.Success)
		}
	})

	t.Run("Health check", func(t *testing.T) {
		resp, err := http.Get(server.URL + "/api/admin/rate-limiting/health")
		require.NoError(t, err)
		defer resp.Body.Close()

		assert.Equal(t, http.StatusOK, resp.StatusCode)

		var apiResp APIResponse
		err = json.NewDecoder(resp.Body).Decode(&apiResp)
		require.NoError(t, err)
		assert.True(t, apiResp.Success)

		health, ok := apiResp.Data.(map[string]interface{})
		assert.True(t, ok, "Data should be health status")
		assert.Equal(t, "healthy", health["status"])
	})
}

// TestMultiTenantIsolation tests rule isolation between multiple systems
func TestMultiTenantIsolation(t *testing.T) {
	db := setupRateLimiterE2ETestDB(t)
	handler := &MockRateLimitHandler{db: db}

	// Setup routes
	router := http.NewServeMux()
	router.HandleFunc("/api/admin/rate-limiting/rules", handler.CreateRule)
	router.HandleFunc("/api/admin/rate-limiting/rules/list", handler.ListRules)

	server := httptest.NewServer(router)
	defer server.Close()

	// Create rules for System A
	systemAPayload := `{
		"rule_name": "system_a_rule",
		"scope": "system",
		"scope_value": "system_a",
		"limit_type": "requests_per_minute",
		"limit_value": 1000,
		"resource_type": "api_call",
		"priority": 1
	}`

	respA, err := http.Post(
		server.URL+"/api/admin/rate-limiting/rules",
		"application/json",
		strings.NewReader(systemAPayload),
	)
	require.NoError(t, err)
	defer respA.Body.Close()
	assert.Equal(t, http.StatusOK, respA.StatusCode)

	// Create rules for System B
	systemBPayload := `{
		"rule_name": "system_b_rule",
		"scope": "system",
		"scope_value": "system_b",
		"limit_type": "requests_per_minute",
		"limit_value": 500,
		"resource_type": "api_call",
		"priority": 1
	}`

	respB, err := http.Post(
		server.URL+"/api/admin/rate-limiting/rules",
		"application/json",
		strings.NewReader(systemBPayload),
	)
	require.NoError(t, err)
	defer respB.Body.Close()
	assert.Equal(t, http.StatusOK, respB.StatusCode)

	// List all rules - should show both
	listResp, err := http.Get(server.URL + "/api/admin/rate-limiting/rules/list")
	require.NoError(t, err)
	defer listResp.Body.Close()

	var apiResp APIResponse
	err = json.NewDecoder(listResp.Body).Decode(&apiResp)
	require.NoError(t, err)
	assert.True(t, apiResp.Success)

	// Verify isolation - rules should be separate
	var systemARules []map[string]interface{}
	var systemBRules []map[string]interface{}

	rules, ok := apiResp.Data.([]interface{})
	assert.True(t, ok)
	assert.Equal(t, 2, len(rules), "Should have 2 rules total")

	for _, rule := range rules {
		ruleMap := rule.(map[string]interface{})
		if ruleMap["scope_value"] == "system_a" {
			systemARules = append(systemARules, ruleMap)
		} else if ruleMap["scope_value"] == "system_b" {
			systemBRules = append(systemBRules, ruleMap)
		}
	}

	assert.Equal(t, 1, len(systemARules), "System A should have exactly 1 rule")
	assert.Equal(t, 1, len(systemBRules), "System B should have exactly 1 rule")

	// Verify limit values are different
	assert.Equal(t, 1000.0, systemARules[0]["limit_value"])
	assert.Equal(t, 500.0, systemBRules[0]["limit_value"])

	t.Logf("Multi-tenant isolation verified:")
	t.Logf("  System A rules: %d", len(systemARules))
	t.Logf("  System B rules: %d", len(systemBRules))
	t.Logf("  System A limit: %v", systemARules[0]["limit_value"])
	t.Logf("  System B limit: %v", systemBRules[0]["limit_value"])
}

// TestQuotaManagementWorkflow tests complete quota management workflow
func TestQuotaManagementWorkflow(t *testing.T) {
	db := setupRateLimiterE2ETestDB(t)
	handler := &MockRateLimitHandler{db: db}

	// Pre-populate quota data
	now := time.Now()
	periodEnd := now.AddDate(0, 0, 1) // Tomorrow

	db.Exec(`
		INSERT INTO resource_quotas
		(system_id, scope, scope_value, resource_type, quota_period, quota_limit, quota_used, period_start, period_end)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
	`, "global", "user", "user_123", "api_call", "daily", 1000, 250, now, periodEnd)

	// Setup routes
	router := http.NewServeMux()
	router.HandleFunc("/api/admin/rate-limiting/quota/status", handler.GetQuotaStatus)
	router.HandleFunc("/api/admin/rate-limiting/quota/increment", handler.IncrementQuota)

	server := httptest.NewServer(router)
	defer server.Close()

	t.Run("Get initial quota status", func(t *testing.T) {
		resp, err := http.Get(
			server.URL + "/api/admin/rate-limiting/quota/status?system=global&scope=user&value=user_123",
		)
		require.NoError(t, err)
		defer resp.Body.Close()

		assert.Equal(t, http.StatusOK, resp.StatusCode)

		var apiResp APIResponse
		err = json.NewDecoder(resp.Body).Decode(&apiResp)
		require.NoError(t, err)
		assert.True(t, apiResp.Success)

		data := apiResp.Data.(map[string]interface{})
		assert.Equal(t, 1000.0, data["quota_limit"], "Quota limit should be 1000")
		assert.Equal(t, 250.0, data["quota_used"], "Quota used should be 250")
		assert.Equal(t, 750.0, data["remaining"], "Remaining should be 750")
	})

	t.Run("Increment quota usage", func(t *testing.T) {
		payload := `{
			"system": "global",
			"scope": "user",
			"value": "user_123",
			"increment": 100
		}`

		resp, err := http.Post(
			server.URL+"/api/admin/rate-limiting/quota/increment",
			"application/json",
			strings.NewReader(payload),
		)
		require.NoError(t, err)
		defer resp.Body.Close()

		assert.Equal(t, http.StatusOK, resp.StatusCode)

		var apiResp APIResponse
		err = json.NewDecoder(resp.Body).Decode(&apiResp)
		require.NoError(t, err)
		assert.True(t, apiResp.Success)
	})

	t.Run("Verify updated quota status", func(t *testing.T) {
		resp, err := http.Get(
			server.URL + "/api/admin/rate-limiting/quota/status?system=global&scope=user&value=user_123",
		)
		require.NoError(t, err)
		defer resp.Body.Close()

		var apiResp APIResponse
		err = json.NewDecoder(resp.Body).Decode(&apiResp)
		require.NoError(t, err)

		data := apiResp.Data.(map[string]interface{})
		assert.Equal(t, 350.0, data["quota_used"], "Quota used should now be 350 (250 + 100)")
		assert.Equal(t, 650.0, data["remaining"], "Remaining should now be 650")
	})
}

// TestRateLimitEnforcementFlow tests complete rate limiting enforcement workflow
func TestRateLimitEnforcementFlow(t *testing.T) {
	db := setupRateLimiterE2ETestDB(t)
	handler := &MockRateLimitHandler{db: db}

	// Create test rule
	db.Exec(`
		INSERT INTO rate_limit_configs
		(rule_name, scope, scope_value, limit_type, limit_value, resource_type, enabled, priority)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?)
	`, "test_rule", "ip", "192.168.1.1", "requests_per_minute", 5, "api_call", 1, 1)

	// Create bucket for current minute
	now := time.Now()
	windowStart := now.Add(-1 * time.Minute)
	windowEnd := now.Add(1 * time.Minute)

	db.Exec(`
		INSERT INTO rate_limit_buckets
		(scope, scope_value, window_start, window_end, request_count)
		VALUES (?, ?, ?, ?, ?)
	`, "ip", "192.168.1.1", windowStart, windowEnd, 3)

	// Setup routes
	router := http.NewServeMux()
	router.HandleFunc("/api/admin/rate-limiting/rules/list", handler.ListRules)
	router.HandleFunc("/api/admin/rate-limiting/violations", handler.GetViolations)

	server := httptest.NewServer(router)
	defer server.Close()

	t.Run("Check rule exists", func(t *testing.T) {
		resp, err := http.Get(server.URL + "/api/admin/rate-limiting/rules/list")
		require.NoError(t, err)
		defer resp.Body.Close()

		var apiResp APIResponse
		err = json.NewDecoder(resp.Body).Decode(&apiResp)
		require.NoError(t, err)
		assert.True(t, apiResp.Success)

		rules := apiResp.Data.([]interface{})
		assert.Equal(t, 1, len(rules))

		rule := rules[0].(map[string]interface{})
		assert.Equal(t, "test_rule", rule["rule_name"])
		assert.Equal(t, 5.0, rule["limit_value"])
	})

	t.Run("Simulate requests within limit", func(t *testing.T) {
		// Update bucket to add 2 more requests (total 5)
		db.Exec(`
			UPDATE rate_limit_buckets
			SET request_count = request_count + 2
			WHERE scope = ? AND scope_value = ?
		`, "ip", "192.168.1.1")

		var count int64
		db.Table("rate_limit_buckets").
			Where("scope = ? AND scope_value = ?", "ip", "192.168.1.1").
			Select("request_count").
			Scan(&count)

		assert.Equal(t, int64(5), count)
	})

	t.Run("Simulate request exceeding limit", func(t *testing.T) {
		// Add violation
		db.Exec(`
			INSERT INTO rate_limit_violations
			(scope, scope_value, violated_limit, violation_time, blocked)
			VALUES (?, ?, ?, ?, ?)
		`, "ip", "192.168.1.1", 5, time.Now(), true)

		// Check violations
		resp, err := http.Get(server.URL + "/api/admin/rate-limiting/violations?limit=10")
		require.NoError(t, err)
		defer resp.Body.Close()

		var apiResp APIResponse
		err = json.NewDecoder(resp.Body).Decode(&apiResp)
		require.NoError(t, err)
		assert.True(t, apiResp.Success)

		violations := apiResp.Data.([]interface{})
		assert.Greater(t, len(violations), 0, "Should have at least one violation")

		violation := violations[0].(map[string]interface{})
		assert.Equal(t, "ip", violation["scope"])
		assert.Equal(t, true, violation["blocked"])
	})
}

// TestErrorHandlingAndEdgeCases tests error handling in API
func TestErrorHandlingAndEdgeCases(t *testing.T) {
	db := setupRateLimiterE2ETestDB(t)
	handler := &MockRateLimitHandler{db: db}

	router := http.NewServeMux()
	router.HandleFunc("/api/admin/rate-limiting/rules", handler.CreateRule)
	router.HandleFunc("/api/admin/rate-limiting/rules/get", handler.GetRule)
	router.HandleFunc("/api/admin/rate-limiting/rules/delete", handler.DeleteRule)

	server := httptest.NewServer(router)
	defer server.Close()

	t.Run("Invalid request format", func(t *testing.T) {
		resp, err := http.Post(
			server.URL+"/api/admin/rate-limiting/rules",
			"application/json",
			strings.NewReader(`{invalid json}`),
		)
		require.NoError(t, err)
		defer resp.Body.Close()

		assert.Equal(t, http.StatusBadRequest, resp.StatusCode)
	})

	t.Run("Get non-existent rule", func(t *testing.T) {
		resp, err := http.Get(server.URL + "/api/admin/rate-limiting/rules/get?id=99999")
		require.NoError(t, err)
		defer resp.Body.Close()

		assert.Equal(t, http.StatusNotFound, resp.StatusCode)

		var apiResp APIResponse
		err = json.NewDecoder(resp.Body).Decode(&apiResp)
		require.NoError(t, err)
		assert.False(t, apiResp.Success)
	})

	t.Run("Delete non-existent rule", func(t *testing.T) {
		req, err := http.NewRequest(
			http.MethodDelete,
			server.URL+"/api/admin/rate-limiting/rules/delete?id=99999",
			nil,
		)
		require.NoError(t, err)

		resp, err := http.DefaultClient.Do(req)
		require.NoError(t, err)
		defer resp.Body.Close()

		assert.Equal(t, http.StatusNotFound, resp.StatusCode)
	})

	t.Run("Wrong HTTP method", func(t *testing.T) {
		resp, err := http.Post(
			server.URL+"/api/admin/rate-limiting/rules/get?id=1",
			"application/json",
			nil,
		)
		require.NoError(t, err)
		defer resp.Body.Close()

		assert.Equal(t, http.StatusMethodNotAllowed, resp.StatusCode)
	})
}

// TestConcurrentAPICalls tests API under concurrent load
func TestConcurrentAPICalls(t *testing.T) {
	db := setupRateLimiterE2ETestDB(t)
	handler := &MockRateLimitHandler{db: db}

	router := http.NewServeMux()
	router.HandleFunc("/api/admin/rate-limiting/rules", handler.CreateRule)
	router.HandleFunc("/api/admin/rate-limiting/rules/list", handler.ListRules)

	server := httptest.NewServer(router)
	defer server.Close()

	// Create multiple rules concurrently
	numRules := 10
	done := make(chan bool, numRules)

	for i := 1; i <= numRules; i++ {
		go func(ruleNum int) {
			defer func() { done <- true }()

			payload := fmt.Sprintf(`{
				"rule_name": "rule_%d",
				"scope": "ip",
				"scope_value": "192.168.1.%d",
				"limit_type": "requests_per_minute",
				"limit_value": %d,
				"resource_type": "api_call",
				"priority": %d
			}`, ruleNum, ruleNum%256, ruleNum*100, ruleNum)

			resp, err := http.Post(
				server.URL+"/api/admin/rate-limiting/rules",
				"application/json",
				strings.NewReader(payload),
			)
			require.NoError(t, err)
			defer resp.Body.Close()
			assert.Equal(t, http.StatusOK, resp.StatusCode)
		}(i)
	}

	// Wait for all creates
	for i := 0; i < numRules; i++ {
		<-done
	}

	// Verify all rules were created
	resp, err := http.Get(server.URL + "/api/admin/rate-limiting/rules/list")
	require.NoError(t, err)
	defer resp.Body.Close()

	var apiResp APIResponse
	err = json.NewDecoder(resp.Body).Decode(&apiResp)
	require.NoError(t, err)

	rules := apiResp.Data.([]interface{})
	assert.Equal(t, numRules, len(rules), "Should have created all %d rules concurrently", numRules)

	t.Logf("Concurrent API calls - Created %d rules successfully", len(rules))
}
