package openapi

import (
	"architect-go/pkg/openapi"
)

// SpecRegistry generates OpenAPI specifications for all API endpoints
type SpecRegistry struct {
	builder        *openapi.SpecBuilder
	schemaGen      *openapi.SchemaGenerator
}

// NewSpecRegistry creates a new OpenAPI specification registry
func NewSpecRegistry() *SpecRegistry {
	schemaGen := openapi.NewSchemaGenerator()
	schemaGen.GenerateCommonSchemas()

	builder := openapi.NewSpecBuilder(
		"Architect Dashboard API",
		"Comprehensive REST API for managing projects, tracking events, and coordinating development workflows",
		"3.2.0",
	)

	builder.
		SetContact("Support", "https://support.architect.example.com", "support@architect.example.com").
		SetLicense("MIT", "https://opensource.org/licenses/MIT").
		AddServer("https://api.architect.example.com", "Production").
		AddServer("https://staging.architect.example.com", "Staging").
		AddServer("http://localhost:8080", "Development")

	return &SpecRegistry{
		builder:   builder,
		schemaGen: schemaGen,
	}
}

// RegisterSecuritySchemes registers all security schemes
func (sr *SpecRegistry) RegisterSecuritySchemes() {
	sr.builder.AddSecurityScheme("sessionCookie", openapi.SecurityScheme{
		Type:        "apiKey",
		Name:        "session",
		In:          "cookie",
		Description: "Session cookie set after login",
	})

	sr.builder.AddSecurityScheme("bearerToken", openapi.SecurityScheme{
		Type:         "http",
		Scheme:       "bearer",
		BearerFormat: "JWT",
		Description:  "Bearer token authentication",
	})
}

// RegisterAuthEndpoints registers authentication endpoints
func (sr *SpecRegistry) RegisterAuthEndpoints() {
	sr.builder.AddTag(openapi.Tag{
		Name:        "Authentication",
		Description: "User authentication and session management",
	})

	// POST /auth/login
	loginOp := openapi.NewOperation(
		"User Login",
		"Authenticate user and create a session",
		"login",
	)
	loginOp.Tags = []string{"Authentication"}

	loginReq := openapi.NewRequestBody("Login credentials", true)
	loginReq.Content["application/json"] = openapi.MediaType{
		Schema: &openapi.Schema{
			Type: "object",
			Properties: map[string]*openapi.Schema{
				"username": {Type: "string", Example: "architect"},
				"password": {Type: "string", Format: "password", Example: "password123"},
			},
			Required: []string{"username", "password"},
		},
	}
	loginOp.SetRequestBody(loginReq)

	loginOp.AddResponse("200", openapi.NewResponse("Login successful"))
	loginOp.AddResponse("401", openapi.NewResponse("Invalid credentials"))

	sr.builder.AddPath("/auth/login", "post", loginOp)

	// POST /auth/logout
	logoutOp := openapi.NewOperation(
		"User Logout",
		"Invalidate the current session",
		"logout",
	)
	logoutOp.Tags = []string{"Authentication"}
	logoutOp.AddResponse("204", openapi.NewResponse("Logout successful"))

	sr.builder.AddPath("/auth/logout", "post", logoutOp)
}

// RegisterEventEndpoints registers event tracking endpoints
func (sr *SpecRegistry) RegisterEventEndpoints() {
	sr.builder.AddTag(openapi.Tag{
		Name:        "Events",
		Description: "Event tracking and audit logging",
	})

	// GET /events
	listOp := openapi.NewOperation(
		"List Events",
		"Get paginated list of event logs with filtering",
		"listEvents",
	)
	listOp.Tags = []string{"Events"}
	listOp.AddParameter(openapi.NewParameter("event_type", "query", "Filter by event type", false))
	listOp.AddParameter(openapi.NewParameter("source", "query", "Filter by source", false))
	listOp.AddParameter(openapi.NewParameter("user_id", "query", "Filter by user ID", false))
	listOp.AddParameter(openapi.NewParameter("project_id", "query", "Filter by project ID", false))
	listOp.AddParameter(openapi.NewParameter("limit", "query", "Items per page (1-1000)", false))
	listOp.AddParameter(openapi.NewParameter("offset", "query", "Items to skip", false))
	listOp.AddResponse("200", openapi.NewResponse("Event list"))

	sr.builder.AddPath("/events", "get", listOp)

	// POST /events
	createOp := openapi.NewOperation(
		"Create Event",
		"Create a new event log entry",
		"createEvent",
	)
	createOp.Tags = []string{"Events"}

	createReq := openapi.NewRequestBody("Event data", true)
	createReq.Content["application/json"] = openapi.MediaType{
		Schema: &openapi.Schema{
			Type: "object",
			Properties: map[string]*openapi.Schema{
				"event_type": {Type: "string", Example: "user_action"},
				"source": {Type: "string", Example: "api"},
				"user_id": {Type: "string"},
				"project_id": {Type: "string"},
				"data": {Type: "object"},
			},
			Required: []string{"event_type", "source"},
		},
	}
	createOp.SetRequestBody(createReq)
	createOp.AddResponse("201", openapi.NewResponse("Event created"))

	sr.builder.AddPath("/events", "post", createOp)

	// GET /events/{event_id}
	getOp := openapi.NewOperation(
		"Get Event",
		"Get a specific event log entry",
		"getEvent",
	)
	getOp.Tags = []string{"Events"}
	getOp.AddParameter(openapi.NewParameter("event_id", "path", "Event ID", true))
	getOp.AddResponse("200", openapi.NewResponse("Event details"))
	getOp.AddResponse("404", openapi.NewResponse("Event not found"))

	sr.builder.AddPath("/events/{event_id}", "get", getOp)

	// DELETE /events/{event_id}
	deleteOp := openapi.NewOperation(
		"Delete Event",
		"Delete an event log entry",
		"deleteEvent",
	)
	deleteOp.Tags = []string{"Events"}
	deleteOp.AddParameter(openapi.NewParameter("event_id", "path", "Event ID", true))
	deleteOp.AddResponse("204", openapi.NewResponse("Event deleted"))

	sr.builder.AddPath("/events/{event_id}", "delete", deleteOp)
}

// RegisterErrorEndpoints registers error tracking endpoints
func (sr *SpecRegistry) RegisterErrorEndpoints() {
	sr.builder.AddTag(openapi.Tag{
		Name:        "Errors",
		Description: "Error tracking and aggregation",
	})

	// GET /errors
	listOp := openapi.NewOperation(
		"List Errors",
		"Get paginated list of error logs with filtering",
		"listErrors",
	)
	listOp.Tags = []string{"Errors"}
	listOp.AddParameter(openapi.NewParameter("error_type", "query", "Filter by error type", false))
	listOp.AddParameter(openapi.NewParameter("severity", "query", "Filter by severity", false))
	listOp.AddParameter(openapi.NewParameter("status", "query", "Filter by status", false))
	listOp.AddParameter(openapi.NewParameter("source", "query", "Filter by source", false))
	listOp.AddParameter(openapi.NewParameter("limit", "query", "Items per page", false))
	listOp.AddParameter(openapi.NewParameter("offset", "query", "Items to skip", false))
	listOp.AddResponse("200", openapi.NewResponse("Error list"))

	sr.builder.AddPath("/errors", "get", listOp)

	// POST /errors
	createOp := openapi.NewOperation(
		"Create Error",
		"Create a new error log entry (no auth required)",
		"createError",
	)
	createOp.Tags = []string{"Errors"}

	createReq := openapi.NewRequestBody("Error data", true)
	createReq.Content["application/json"] = openapi.MediaType{
		Schema: &openapi.Schema{
			Type: "object",
			Properties: map[string]*openapi.Schema{
				"error_type": {Type: "string"},
				"message": {Type: "string"},
				"severity": {Type: "string", Enum: []interface{}{"critical", "high", "medium", "low", "info"}},
				"source": {Type: "string"},
				"stack_trace": {Type: "string"},
			},
			Required: []string{"error_type", "message", "severity"},
		},
	}
	createOp.SetRequestBody(createReq)
	createOp.AddResponse("201", openapi.NewResponse("Error created"))

	sr.builder.AddPath("/errors", "post", createOp)

	// GET /errors/{error_id}
	getOp := openapi.NewOperation(
		"Get Error",
		"Get a specific error log entry",
		"getError",
	)
	getOp.Tags = []string{"Errors"}
	getOp.AddParameter(openapi.NewParameter("error_id", "path", "Error ID", true))
	getOp.AddResponse("200", openapi.NewResponse("Error details"))

	sr.builder.AddPath("/errors/{error_id}", "get", getOp)

	// POST /errors/{error_id}/resolve
	resolveOp := openapi.NewOperation(
		"Resolve Error",
		"Mark an error as resolved",
		"resolveError",
	)
	resolveOp.Tags = []string{"Errors"}
	resolveOp.AddParameter(openapi.NewParameter("error_id", "path", "Error ID", true))

	resolveReq := openapi.NewRequestBody("Resolution details", false)
	resolveReq.Content["application/json"] = openapi.MediaType{
		Schema: &openapi.Schema{
			Type: "object",
			Properties: map[string]*openapi.Schema{
				"resolution": {Type: "string"},
			},
		},
	}
	resolveOp.SetRequestBody(resolveReq)
	resolveOp.AddResponse("200", openapi.NewResponse("Error resolved"))

	sr.builder.AddPath("/errors/{error_id}/resolve", "post", resolveOp)
}

// RegisterNotificationEndpoints registers notification endpoints
func (sr *SpecRegistry) RegisterNotificationEndpoints() {
	sr.builder.AddTag(openapi.Tag{
		Name:        "Notifications",
		Description: "User notifications and alerts",
	})

	// GET /notifications
	listOp := openapi.NewOperation(
		"List Notifications",
		"Get notifications for the current user",
		"listNotifications",
	)
	listOp.Tags = []string{"Notifications"}
	listOp.AddParameter(openapi.NewParameter("type", "query", "Filter by type", false))
	listOp.AddParameter(openapi.NewParameter("read", "query", "Filter by read status", false))
	listOp.AddParameter(openapi.NewParameter("limit", "query", "Items per page", false))
	listOp.AddParameter(openapi.NewParameter("offset", "query", "Items to skip", false))
	listOp.AddResponse("200", openapi.NewResponse("Notification list"))

	sr.builder.AddPath("/notifications", "get", listOp)

	// POST /notifications
	createOp := openapi.NewOperation(
		"Create Notification",
		"Create a notification for a user",
		"createNotification",
	)
	createOp.Tags = []string{"Notifications"}

	createReq := openapi.NewRequestBody("Notification data", true)
	createReq.Content["application/json"] = openapi.MediaType{
		Schema: &openapi.Schema{
			Type: "object",
			Properties: map[string]*openapi.Schema{
				"user_id": {Type: "string"},
				"type": {Type: "string", Enum: []interface{}{"info", "warning", "error", "success"}},
				"title": {Type: "string"},
				"message": {Type: "string"},
				"data": {Type: "object"},
			},
			Required: []string{"user_id", "type", "title", "message"},
		},
	}
	createOp.SetRequestBody(createReq)
	createOp.AddResponse("201", openapi.NewResponse("Notification created"))

	sr.builder.AddPath("/notifications", "post", createOp)

	// PUT /notifications/{notification_id}/mark-read
	markReadOp := openapi.NewOperation(
		"Mark Notification as Read",
		"Mark a notification as read",
		"markNotificationRead",
	)
	markReadOp.Tags = []string{"Notifications"}
	markReadOp.AddParameter(openapi.NewParameter("notification_id", "path", "Notification ID", true))
	markReadOp.AddResponse("200", openapi.NewResponse("Notification updated"))

	sr.builder.AddPath("/notifications/{notification_id}/mark-read", "put", markReadOp)

	// DELETE /notifications/{notification_id}
	deleteOp := openapi.NewOperation(
		"Delete Notification",
		"Delete a notification",
		"deleteNotification",
	)
	deleteOp.Tags = []string{"Notifications"}
	deleteOp.AddParameter(openapi.NewParameter("notification_id", "path", "Notification ID", true))
	deleteOp.AddResponse("204", openapi.NewResponse("Notification deleted"))

	sr.builder.AddPath("/notifications/{notification_id}", "delete", deleteOp)
}

// RegisterSessionEndpoints registers session management endpoints
func (sr *SpecRegistry) RegisterSessionEndpoints() {
	sr.builder.AddTag(openapi.Tag{
		Name:        "Sessions",
		Description: "Session tracking and management",
	})

	// GET /sessions
	listOp := openapi.NewOperation(
		"List Sessions",
		"List active sessions for the current user",
		"listSessions",
	)
	listOp.Tags = []string{"Sessions"}
	listOp.AddResponse("200", openapi.NewResponse("Session list"))

	sr.builder.AddPath("/sessions", "get", listOp)

	// DELETE /sessions/{session_id}
	deleteOp := openapi.NewOperation(
		"Delete Session",
		"Invalidate a session (logout)",
		"deleteSession",
	)
	deleteOp.Tags = []string{"Sessions"}
	deleteOp.AddParameter(openapi.NewParameter("session_id", "path", "Session ID", true))
	deleteOp.AddResponse("204", openapi.NewResponse("Session deleted"))

	sr.builder.AddPath("/sessions/{session_id}", "delete", deleteOp)
}

// RegisterIntegrationEndpoints registers integration endpoints
func (sr *SpecRegistry) RegisterIntegrationEndpoints() {
	sr.builder.AddTag(openapi.Tag{
		Name:        "Integrations",
		Description: "Third-party integrations",
	})

	// GET /integrations
	listOp := openapi.NewOperation(
		"List Integrations",
		"Get list of configured integrations",
		"listIntegrations",
	)
	listOp.Tags = []string{"Integrations"}
	listOp.AddParameter(openapi.NewParameter("type", "query", "Filter by type", false))
	listOp.AddParameter(openapi.NewParameter("provider", "query", "Filter by provider", false))
	listOp.AddParameter(openapi.NewParameter("enabled", "query", "Filter by enabled status", false))
	listOp.AddResponse("200", openapi.NewResponse("Integration list"))

	sr.builder.AddPath("/integrations", "get", listOp)

	// POST /integrations
	createOp := openapi.NewOperation(
		"Create Integration",
		"Create a new integration",
		"createIntegration",
	)
	createOp.Tags = []string{"Integrations"}

	createReq := openapi.NewRequestBody("Integration config", true)
	createReq.Content["application/json"] = openapi.MediaType{
		Schema: &openapi.Schema{
			Type: "object",
			Properties: map[string]*openapi.Schema{
				"type": {Type: "string"},
				"provider": {Type: "string"},
				"enabled": {Type: "boolean"},
				"config": {Type: "object"},
			},
			Required: []string{"type", "provider"},
		},
	}
	createOp.SetRequestBody(createReq)
	createOp.AddResponse("201", openapi.NewResponse("Integration created"))

	sr.builder.AddPath("/integrations", "post", createOp)

	// PUT /integrations/{integration_id}
	updateOp := openapi.NewOperation(
		"Update Integration",
		"Update an integration",
		"updateIntegration",
	)
	updateOp.Tags = []string{"Integrations"}
	updateOp.AddParameter(openapi.NewParameter("integration_id", "path", "Integration ID", true))

	updateReq := openapi.NewRequestBody("Updated integration data", true)
	updateReq.Content["application/json"] = openapi.MediaType{
		Schema: &openapi.Schema{
			Type: "object",
			Properties: map[string]*openapi.Schema{
				"enabled": {Type: "boolean"},
				"config": {Type: "object"},
			},
		},
	}
	updateOp.SetRequestBody(updateReq)
	updateOp.AddResponse("200", openapi.NewResponse("Integration updated"))

	sr.builder.AddPath("/integrations/{integration_id}", "put", updateOp)

	// DELETE /integrations/{integration_id}
	deleteOp := openapi.NewOperation(
		"Delete Integration",
		"Delete an integration",
		"deleteIntegration",
	)
	deleteOp.Tags = []string{"Integrations"}
	deleteOp.AddParameter(openapi.NewParameter("integration_id", "path", "Integration ID", true))
	deleteOp.AddResponse("204", openapi.NewResponse("Integration deleted"))

	sr.builder.AddPath("/integrations/{integration_id}", "delete", deleteOp)
}

// RegisterHealthEndpoints registers health and monitoring endpoints
func (sr *SpecRegistry) RegisterHealthEndpoints() {
	sr.builder.AddTag(openapi.Tag{
		Name:        "Health & Monitoring",
		Description: "Health checks and metrics",
	})

	// GET /health
	healthOp := openapi.NewOperation(
		"Health Check",
		"Get API health status",
		"health",
	)
	healthOp.Tags = []string{"Health & Monitoring"}
	healthOp.AddResponse("200", openapi.NewResponse("Health status"))

	sr.builder.AddPath("/health", "get", healthOp)

	// GET /metrics
	metricsOp := openapi.NewOperation(
		"Get Metrics",
		"Get API metrics and statistics",
		"metrics",
	)
	metricsOp.Tags = []string{"Health & Monitoring"}
	metricsOp.AddResponse("200", openapi.NewResponse("API metrics"))

	sr.builder.AddPath("/metrics", "get", metricsOp)
}

// Build generates the complete OpenAPI specification
func (sr *SpecRegistry) Build() ([]byte, error) {
	sr.RegisterSecuritySchemes()
	sr.RegisterAuthEndpoints()
	sr.RegisterEventEndpoints()
	sr.RegisterErrorEndpoints()
	sr.RegisterNotificationEndpoints()
	sr.RegisterSessionEndpoints()
	sr.RegisterIntegrationEndpoints()
	sr.RegisterHealthEndpoints()

	// Add all schemas to builder
	for name, schema := range sr.schemaGen.GetAllSchemas() {
		sr.builder.AddSchema(name, schema)
	}

	return sr.builder.Build()
}
