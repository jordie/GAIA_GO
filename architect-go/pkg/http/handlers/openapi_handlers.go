package handlers

import (
	"encoding/json"
	"net/http"
)

// OpenAPIHandler serves OpenAPI specification
type OpenAPIHandler struct{}

// OpenAPISpec represents OpenAPI 3.0.3 specification
type OpenAPISpec struct {
	OpenAPI    string                 `json:"openapi"`
	Info       Info                   `json:"info"`
	Servers    []Server               `json:"servers"`
	Paths      map[string]PathItem    `json:"paths"`
	Components Components             `json:"components"`
	Tags       []Tag                  `json:"tags"`
}

// Info represents API information
type Info struct {
	Title       string `json:"title"`
	Description string `json:"description"`
	Version     string `json:"version"`
	Contact     Contact `json:"contact,omitempty"`
	License     License `json:"license,omitempty"`
}

// Contact represents contact information
type Contact struct {
	Name string `json:"name,omitempty"`
	URL  string `json:"url,omitempty"`
	Email string `json:"email,omitempty"`
}

// License represents license information
type License struct {
	Name string `json:"name"`
	URL  string `json:"url,omitempty"`
}

// Server represents server information
type Server struct {
	URL         string `json:"url"`
	Description string `json:"description,omitempty"`
}

// PathItem represents an API path
type PathItem struct {
	Get    *Operation `json:"get,omitempty"`
	Post   *Operation `json:"post,omitempty"`
	Put    *Operation `json:"put,omitempty"`
	Delete *Operation `json:"delete,omitempty"`
	Patch  *Operation `json:"patch,omitempty"`
}

// Operation represents an API operation
type Operation struct {
	Summary     string                   `json:"summary"`
	Description string                   `json:"description,omitempty"`
	OperationID string                   `json:"operationId"`
	Tags        []string                 `json:"tags,omitempty"`
	Parameters  []Parameter              `json:"parameters,omitempty"`
	RequestBody *RequestBody             `json:"requestBody,omitempty"`
	Responses   map[string]Response      `json:"responses"`
}

// Parameter represents a parameter
type Parameter struct {
	Name        string `json:"name"`
	In          string `json:"in"`
	Description string `json:"description,omitempty"`
	Required    bool   `json:"required"`
	Schema      Schema `json:"schema"`
}

// RequestBody represents a request body
type RequestBody struct {
	Description string            `json:"description,omitempty"`
	Required    bool              `json:"required"`
	Content     map[string]Content `json:"content"`
}

// Content represents content information
type Content struct {
	Schema Schema `json:"schema"`
}

// Response represents a response
type Response struct {
	Description string            `json:"description"`
	Content     map[string]Content `json:"content,omitempty"`
}

// Schema represents a schema definition
type Schema struct {
	Type        string              `json:"type,omitempty"`
	Format      string              `json:"format,omitempty"`
	Items       *Schema             `json:"items,omitempty"`
	Properties  map[string]Schema   `json:"properties,omitempty"`
	Required    []string            `json:"required,omitempty"`
	Description string              `json:"description,omitempty"`
}

// Components represents reusable components
type Components struct {
	Schemas map[string]Schema `json:"schemas"`
}

// Tag represents an API tag
type Tag struct {
	Name        string `json:"name"`
	Description string `json:"description,omitempty"`
}

// NewOpenAPISpec creates a new OpenAPI specification
func NewOpenAPISpec() *OpenAPISpec {
	return &OpenAPISpec{
		OpenAPI: "3.0.3",
		Info: Info{
			Title:       "Architect Analytics API",
			Description: "Comprehensive analytics API for the Architect Dashboard",
			Version:     "4.5.0",
			Contact: Contact{
				Name: "Architect Team",
			},
			License: License{
				Name: "MIT",
			},
		},
		Servers: []Server{
			{
				URL:         "http://localhost:8080",
				Description: "Development server",
			},
		},
		Paths:      make(map[string]PathItem),
		Components: Components{Schemas: make(map[string]Schema)},
		Tags: []Tag{
			{Name: "Events", Description: "Event analytics"},
			{Name: "Presence", Description: "Presence analytics"},
			{Name: "Activity", Description: "Activity analytics"},
			{Name: "Performance", Description: "Performance metrics"},
			{Name: "Users", Description: "User analytics"},
			{Name: "Errors", Description: "Error analytics"},
		},
	}
}

// ServeOpenAPI serves the OpenAPI specification
func (h *OpenAPIHandler) ServeOpenAPI(w http.ResponseWriter, r *http.Request) {
	spec := NewOpenAPISpec()

	// Add Event Analytics endpoints
	spec.addEventAnalyticsEndpoints()
	// Add Presence Analytics endpoints
	spec.addPresenceAnalyticsEndpoints()
	// Add Activity Analytics endpoints
	spec.addActivityAnalyticsEndpoints()
	// Add Performance Analytics endpoints
	spec.addPerformanceAnalyticsEndpoints()
	// Add User Analytics endpoints
	spec.addUserAnalyticsEndpoints()
	// Add Error Analytics endpoints
	spec.addErrorAnalyticsEndpoints()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(spec)
}

// addEventAnalyticsEndpoints adds event analytics endpoints to spec
func (spec *OpenAPISpec) addEventAnalyticsEndpoints() {
	spec.Paths["/api/analytics/events/timeline"] = PathItem{
		Get: &Operation{
			Summary:     "Get event timeline",
			OperationID: "getEventTimeline",
			Tags:        []string{"Events"},
			Parameters: []Parameter{
				{Name: "period", In: "query", Required: false, Schema: Schema{Type: "string"}},
				{Name: "interval", In: "query", Required: false, Schema: Schema{Type: "string"}},
			},
			Responses: map[string]Response{
				"200": {Description: "Timeline data returned"},
			},
		},
	}

	spec.Paths["/api/analytics/events/trends"] = PathItem{
		Get: &Operation{
			Summary:     "Get event trends",
			OperationID: "getEventTrends",
			Tags:        []string{"Events"},
			Responses: map[string]Response{
				"200": {Description: "Trends data returned"},
			},
		},
	}
}

// addPresenceAnalyticsEndpoints adds presence analytics endpoints to spec
func (spec *OpenAPISpec) addPresenceAnalyticsEndpoints() {
	spec.Paths["/api/analytics/presence/trends"] = PathItem{
		Get: &Operation{
			Summary:     "Get presence trends",
			OperationID: "getPresenceTrends",
			Tags:        []string{"Presence"},
			Responses: map[string]Response{
				"200": {Description: "Presence trends returned"},
			},
		},
	}

	spec.Paths["/api/analytics/presence/heatmap"] = PathItem{
		Get: &Operation{
			Summary:     "Get presence heatmap",
			OperationID: "getPresenceHeatmap",
			Tags:        []string{"Presence"},
			Responses: map[string]Response{
				"200": {Description: "Heatmap data returned"},
			},
		},
	}
}

// addActivityAnalyticsEndpoints adds activity analytics endpoints to spec
func (spec *OpenAPISpec) addActivityAnalyticsEndpoints() {
	spec.Paths["/api/analytics/activity/trends"] = PathItem{
		Get: &Operation{
			Summary:     "Get activity trends",
			OperationID: "getActivityTrends",
			Tags:        []string{"Activity"},
			Responses: map[string]Response{
				"200": {Description: "Activity trends returned"},
			},
		},
	}
}

// addPerformanceAnalyticsEndpoints adds performance analytics endpoints to spec
func (spec *OpenAPISpec) addPerformanceAnalyticsEndpoints() {
	spec.Paths["/api/analytics/performance/requests"] = PathItem{
		Get: &Operation{
			Summary:     "Get request metrics",
			OperationID: "getRequestMetrics",
			Tags:        []string{"Performance"},
			Responses: map[string]Response{
				"200": {Description: "Request metrics returned"},
			},
		},
	}

	spec.Paths["/api/analytics/performance/system"] = PathItem{
		Get: &Operation{
			Summary:     "Get system metrics",
			OperationID: "getSystemMetrics",
			Tags:        []string{"Performance"},
			Responses: map[string]Response{
				"200": {Description: "System metrics returned"},
			},
		},
	}
}

// addUserAnalyticsEndpoints adds user analytics endpoints to spec
func (spec *OpenAPISpec) addUserAnalyticsEndpoints() {
	spec.Paths["/api/analytics/users/growth"] = PathItem{
		Get: &Operation{
			Summary:     "Get user growth metrics",
			OperationID: "getUserGrowth",
			Tags:        []string{"Users"},
			Responses: map[string]Response{
				"200": {Description: "User growth metrics returned"},
			},
		},
	}
}

// addErrorAnalyticsEndpoints adds error analytics endpoints to spec
func (spec *OpenAPISpec) addErrorAnalyticsEndpoints() {
	spec.Paths["/api/analytics/errors/metrics"] = PathItem{
		Get: &Operation{
			Summary:     "Get error metrics",
			OperationID: "getErrorMetrics",
			Tags:        []string{"Errors"},
			Responses: map[string]Response{
				"200": {Description: "Error metrics returned"},
			},
		},
	}

	spec.Paths["/api/analytics/errors/critical"] = PathItem{
		Get: &Operation{
			Summary:     "Get critical errors",
			OperationID: "getCriticalErrors",
			Tags:        []string{"Errors"},
			Responses: map[string]Response{
				"200": {Description: "Critical errors returned"},
			},
		},
	}
}

// ServeSwaggerUI serves Swagger UI
func (h *OpenAPIHandler) ServeSwaggerUI(w http.ResponseWriter, r *http.Request) {
	html := `
<!DOCTYPE html>
<html>
  <head>
    <title>Architect Analytics API - Swagger UI</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@3/swagger-ui.css">
    <style>
      body { margin: 0; }
    </style>
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@3/swagger-ui-bundle.js"></script>
    <script>
    window.onload = function() {
      SwaggerUIBundle({
        url: "/api/openapi.json",
        dom_id: '#swagger-ui',
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIBundle.SwaggerUIStandalonePreset
        ],
        layout: "BaseLayout",
        requestInterceptor: (request) => {
          request.headers['X-API-Key'] = 'your-api-key-here';
          return request;
        }
      })
    }
    </script>
  </body>
</html>
`
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(html))
}
