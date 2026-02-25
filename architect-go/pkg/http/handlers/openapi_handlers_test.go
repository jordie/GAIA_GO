package handlers

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestOpenAPISpec_ServeOpenAPI(t *testing.T) {
	handler := &OpenAPIHandler{}

	w := httptest.NewRecorder()
	r := httptest.NewRequest("GET", "/api/openapi.json", nil)

	handler.ServeOpenAPI(w, r)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var spec OpenAPISpec
	err := json.Unmarshal(w.Body.Bytes(), &spec)
	if err != nil {
		t.Errorf("failed to unmarshal response: %v", err)
	}

	if spec.OpenAPI != "3.0.3" {
		t.Errorf("expected OpenAPI 3.0.3, got %s", spec.OpenAPI)
	}

	if spec.Info.Title != "Architect Analytics API" {
		t.Errorf("expected title 'Architect Analytics API', got %s", spec.Info.Title)
	}

	if len(spec.Paths) == 0 {
		t.Error("expected paths to be populated")
	}

	if len(spec.Tags) == 0 {
		t.Error("expected tags to be populated")
	}
}

func TestOpenAPISpec_EventAnalyticsEndpoints(t *testing.T) {
	spec := NewOpenAPISpec()
	spec.addEventAnalyticsEndpoints()

	if _, exists := spec.Paths["/api/analytics/events/timeline"]; !exists {
		t.Error("expected timeline endpoint")
	}

	if _, exists := spec.Paths["/api/analytics/events/trends"]; !exists {
		t.Error("expected trends endpoint")
	}
}

func TestOpenAPISpec_PresenceAnalyticsEndpoints(t *testing.T) {
	spec := NewOpenAPISpec()
	spec.addPresenceAnalyticsEndpoints()

	if _, exists := spec.Paths["/api/analytics/presence/trends"]; !exists {
		t.Error("expected presence trends endpoint")
	}

	if _, exists := spec.Paths["/api/analytics/presence/heatmap"]; !exists {
		t.Error("expected presence heatmap endpoint")
	}
}

func TestOpenAPISpec_PerformanceAnalyticsEndpoints(t *testing.T) {
	spec := NewOpenAPISpec()
	spec.addPerformanceAnalyticsEndpoints()

	if _, exists := spec.Paths["/api/analytics/performance/requests"]; !exists {
		t.Error("expected requests endpoint")
	}

	if _, exists := spec.Paths["/api/analytics/performance/system"]; !exists {
		t.Error("expected system metrics endpoint")
	}
}

func TestOpenAPISpec_ErrorAnalyticsEndpoints(t *testing.T) {
	spec := NewOpenAPISpec()
	spec.addErrorAnalyticsEndpoints()

	if _, exists := spec.Paths["/api/analytics/errors/metrics"]; !exists {
		t.Error("expected error metrics endpoint")
	}

	if _, exists := spec.Paths["/api/analytics/errors/critical"]; !exists {
		t.Error("expected critical errors endpoint")
	}
}

func TestOpenAPIHandler_ServeSwaggerUI(t *testing.T) {
	handler := &OpenAPIHandler{}

	w := httptest.NewRecorder()
	r := httptest.NewRequest("GET", "/api/docs", nil)

	handler.ServeSwaggerUI(w, r)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	if w.Header().Get("Content-Type") != "text/html; charset=utf-8" {
		t.Errorf("expected HTML content type")
	}

	body := w.Body.String()
	if !contains(body, "swagger-ui") {
		t.Error("expected Swagger UI elements in response")
	}
}

func TestOpenAPISpec_HasRequiredTags(t *testing.T) {
	spec := NewOpenAPISpec()

	requiredTags := []string{"Events", "Presence", "Activity", "Performance", "Users", "Errors"}

	if len(spec.Tags) != len(requiredTags) {
		t.Errorf("expected %d tags, got %d", len(requiredTags), len(spec.Tags))
	}

	for _, required := range requiredTags {
		found := false
		for _, tag := range spec.Tags {
			if tag.Name == required {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("expected tag %s not found", required)
		}
	}
}

func TestOpenAPISpec_AllEndpointsDocumented(t *testing.T) {
	spec := NewOpenAPISpec()
	spec.addEventAnalyticsEndpoints()
	spec.addPresenceAnalyticsEndpoints()
	spec.addActivityAnalyticsEndpoints()
	spec.addPerformanceAnalyticsEndpoints()
	spec.addUserAnalyticsEndpoints()
	spec.addErrorAnalyticsEndpoints()

	expectedEndpoints := []string{
		"/api/analytics/events/timeline",
		"/api/analytics/events/trends",
		"/api/analytics/presence/trends",
		"/api/analytics/presence/heatmap",
		"/api/analytics/activity/trends",
		"/api/analytics/performance/requests",
		"/api/analytics/performance/system",
		"/api/analytics/users/growth",
		"/api/analytics/errors/metrics",
		"/api/analytics/errors/critical",
	}

	for _, endpoint := range expectedEndpoints {
		if _, exists := spec.Paths[endpoint]; !exists {
			t.Errorf("expected endpoint %s not found in spec", endpoint)
		}
	}
}

// Helper function for string containment check
func contains(s, substr string) bool {
	return strings.Contains(s, substr)
}
