package openapi

// SchemaGenerator generates JSON schemas for API models
type SchemaGenerator struct {
	schemas map[string]*Schema
}

// NewSchemaGenerator creates a new schema generator
func NewSchemaGenerator() *SchemaGenerator {
	return &SchemaGenerator{
		schemas: make(map[string]*Schema),
	}
}

// GenerateCommonSchemas generates schemas for common model types
func (sg *SchemaGenerator) GenerateCommonSchemas() {
	// Error response schema
	sg.schemas["ErrorResponse"] = &Schema{
		Type:        "object",
		Title:       "ErrorResponse",
		Description: "Standard error response",
		Properties: map[string]*Schema{
			"code": {
				Type:        "string",
				Description: "Error code identifier",
				Example:     "INTERNAL_ERROR",
			},
			"message": {
				Type:        "string",
				Description: "Human-readable error message",
				Example:     "An unexpected error occurred",
			},
			"details": {
				Type:        "object",
				Description: "Additional error details",
				Properties: map[string]*Schema{
					"validation": {
						Type: "array",
						Items: &Schema{
							Type: "object",
							Properties: map[string]*Schema{
								"field": {Type: "string"},
								"reason": {Type: "string"},
							},
						},
					},
				},
			},
		},
		Required: []string{"code", "message"},
	}

	// Pagination response schema
	sg.schemas["PaginatedResponse"] = &Schema{
		Type:        "object",
		Title:       "PaginatedResponse",
		Description: "Paginated list response",
		Properties: map[string]*Schema{
			"data": {
				Type:        "array",
				Description: "List of items",
				Items: &Schema{Type: "object"},
			},
			"pagination": {
				Type: "object",
				Properties: map[string]*Schema{
					"limit": {
						Type:        "integer",
						Description: "Number of items per page",
						Example:     20,
					},
					"offset": {
						Type:        "integer",
						Description: "Number of items skipped",
						Example:     0,
					},
					"total": {
						Type:        "integer",
						Description: "Total number of items",
						Example:     100,
					},
					"pages": {
						Type:        "integer",
						Description: "Total number of pages",
						Example:     5,
					},
				},
			},
		},
		Required: []string{"data", "pagination"},
	}

	// Timestamp schema
	sg.schemas["Timestamp"] = &Schema{
		Type:        "string",
		Format:      "date-time",
		Description: "ISO 8601 timestamp",
		Example:     "2024-02-17T12:00:00Z",
	}

	// UUID schema
	sg.schemas["UUID"] = &Schema{
		Type:        "string",
		Format:      "uuid",
		Description: "UUID identifier",
		Example:     "550e8400-e29b-41d4-a716-446655440000",
	}

	// Health status schema
	sg.schemas["HealthStatus"] = StringEnum("healthy", "degraded", "unhealthy")

	// User schema
	sg.schemas["User"] = &Schema{
		Type:        "object",
		Title:       "User",
		Description: "User object",
		Properties: map[string]*Schema{
			"id": {
				Type:        "string",
				Description: "User ID",
				Example:     "user-123",
			},
			"username": {
				Type:        "string",
				Description: "Username",
				Example:     "architect",
			},
			"email": {
				Type:        "string",
				Format:      "email",
				Description: "User email",
				Example:     "admin@example.com",
			},
			"role": {
				Type:        "string",
				Description: "User role",
				Enum:        []interface{}{"admin", "user", "guest"},
				Example:     "admin",
			},
			"created_at": {
				Type:        "string",
				Format:      "date-time",
				Description: "Creation timestamp",
			},
			"updated_at": {
				Type:        "string",
				Format:      "date-time",
				Description: "Last update timestamp",
			},
		},
		Required: []string{"id", "username", "email", "role"},
	}

	// EventLog schema
	sg.schemas["EventLog"] = &Schema{
		Type:        "object",
		Title:       "EventLog",
		Description: "Event log entry",
		Properties: map[string]*Schema{
			"id": {
				Type:        "string",
				Description: "Event ID",
			},
			"event_type": {
				Type:        "string",
				Description: "Type of event",
				Example:     "user_action",
			},
			"source": {
				Type:        "string",
				Description: "Event source",
				Example:     "api",
			},
			"user_id": {
				Type:        "string",
				Description: "User ID associated with event",
			},
			"project_id": {
				Type:        "string",
				Description: "Project ID associated with event",
			},
			"data": {
				Type:        "object",
				Description: "Event data payload",
			},
			"created_at": {
				Type:        "string",
				Format:      "date-time",
				Description: "Creation timestamp",
			},
		},
		Required: []string{"id", "event_type", "source", "created_at"},
	}

	// ErrorLog schema
	sg.schemas["ErrorLog"] = &Schema{
		Type:        "object",
		Title:       "ErrorLog",
		Description: "Error log entry",
		Properties: map[string]*Schema{
			"id": {
				Type:        "string",
				Description: "Error ID",
			},
			"error_type": {
				Type:        "string",
				Description: "Type of error",
				Example:     "runtime_error",
			},
			"message": {
				Type:        "string",
				Description: "Error message",
			},
			"severity": {
				Type:        "string",
				Description: "Error severity level",
				Enum:        []interface{}{"critical", "high", "medium", "low", "info"},
				Example:     "high",
			},
			"source": {
				Type:        "string",
				Description: "Source of the error",
			},
			"stack_trace": {
				Type:        "string",
				Description: "Stack trace of the error",
			},
			"status": {
				Type:        "string",
				Description: "Error status",
				Enum:        []interface{}{"new", "acknowledged", "resolved"},
				Example:     "new",
			},
			"created_at": {
				Type:        "string",
				Format:      "date-time",
				Description: "Creation timestamp",
			},
		},
		Required: []string{"id", "error_type", "message", "severity", "created_at"},
	}

	// Notification schema
	sg.schemas["Notification"] = &Schema{
		Type:        "object",
		Title:       "Notification",
		Description: "User notification",
		Properties: map[string]*Schema{
			"id": {
				Type:        "string",
				Description: "Notification ID",
			},
			"user_id": {
				Type:        "string",
				Description: "User ID",
			},
			"type": {
				Type:        "string",
				Description: "Notification type",
				Enum:        []interface{}{"info", "warning", "error", "success"},
			},
			"title": {
				Type:        "string",
				Description: "Notification title",
			},
			"message": {
				Type:        "string",
				Description: "Notification message",
			},
			"read": {
				Type:        "boolean",
				Description: "Whether notification has been read",
			},
			"created_at": {
				Type:        "string",
				Format:      "date-time",
				Description: "Creation timestamp",
			},
		},
		Required: []string{"id", "user_id", "type", "title", "message"},
	}

	// Integration schema
	sg.schemas["Integration"] = &Schema{
		Type:        "object",
		Title:       "Integration",
		Description: "Third-party integration",
		Properties: map[string]*Schema{
			"id": {
				Type:        "string",
				Description: "Integration ID",
			},
			"type": {
				Type:        "string",
				Description: "Integration type",
				Example:     "slack",
			},
			"provider": {
				Type:        "string",
				Description: "Integration provider",
				Example:     "slack",
			},
			"enabled": {
				Type:        "boolean",
				Description: "Whether integration is enabled",
			},
			"config": {
				Type:        "object",
				Description: "Integration configuration",
			},
			"created_at": {
				Type:        "string",
				Format:      "date-time",
				Description: "Creation timestamp",
			},
		},
		Required: []string{"id", "type", "provider"},
	}

	// Webhook schema
	sg.schemas["Webhook"] = &Schema{
		Type:        "object",
		Title:       "Webhook",
		Description: "Webhook subscription",
		Properties: map[string]*Schema{
			"id": {
				Type:        "string",
				Description: "Webhook ID",
			},
			"event_type": {
				Type:        "string",
				Description: "Event type to trigger webhook",
				Example:     "event_log.created",
			},
			"url": {
				Type:        "string",
				Format:      "uri",
				Description: "Webhook URL",
				Example:     "https://example.com/webhooks/events",
			},
			"active": {
				Type:        "boolean",
				Description: "Whether webhook is active",
			},
			"headers": {
				Type:        "object",
				Description: "Custom headers to include in webhook requests",
			},
			"retry_policy": {
				Type: "object",
				Properties: map[string]*Schema{
					"max_retries": {
						Type:        "integer",
						Description: "Maximum number of retries",
					},
					"retry_delay_seconds": {
						Type:        "integer",
						Description: "Delay between retries in seconds",
					},
				},
			},
			"created_at": {
				Type:        "string",
				Format:      "date-time",
				Description: "Creation timestamp",
			},
		},
		Required: []string{"id", "event_type", "url"},
	}

	// Health check response
	sg.schemas["HealthCheckResponse"] = &Schema{
		Type:        "object",
		Title:       "HealthCheckResponse",
		Description: "Health check response",
		Properties: map[string]*Schema{
			"status": {
				Type:        "string",
				Description: "Overall health status",
				Enum:        []interface{}{"healthy", "degraded", "unhealthy"},
				Example:     "healthy",
			},
			"timestamp": {
				Type:        "string",
				Format:      "date-time",
				Description: "Health check timestamp",
			},
			"components": {
				Type: "object",
				Properties: map[string]*Schema{
					"database": {
						Type:        "string",
						Description: "Database status",
						Example:     "healthy",
					},
					"cache": {
						Type:        "string",
						Description: "Cache status",
						Example:     "healthy",
					},
					"external_services": {
						Type:        "string",
						Description: "External services status",
						Example:     "degraded",
					},
				},
			},
		},
		Required: []string{"status", "timestamp"},
	}
}

// GetSchema returns a schema by name
func (sg *SchemaGenerator) GetSchema(name string) *Schema {
	return sg.schemas[name]
}

// GetAllSchemas returns all generated schemas
func (sg *SchemaGenerator) GetAllSchemas() map[string]*Schema {
	return sg.schemas
}

// AddSchema adds a custom schema
func (sg *SchemaGenerator) AddSchema(name string, schema *Schema) {
	sg.schemas[name] = schema
}

// CreateListResponseSchema creates a paginated list response schema
func (sg *SchemaGenerator) CreateListResponseSchema(itemSchema *Schema) *Schema {
	return &Schema{
		Type:        "object",
		Title:       "ListResponse",
		Description: "Paginated list response",
		Properties: map[string]*Schema{
			"data": {
				Type:        "array",
				Description: "List of items",
				Items:       itemSchema,
			},
			"pagination": {
				Type: "object",
				Properties: map[string]*Schema{
					"limit": {Type: "integer"},
					"offset": {Type: "integer"},
					"total": {Type: "integer"},
					"pages": {Type: "integer"},
				},
			},
		},
		Required: []string{"data", "pagination"},
	}
}

// CreateCreateRequestSchema creates a schema for create requests
func (sg *SchemaGenerator) CreateCreateRequestSchema(properties map[string]*Schema) *Schema {
	return &Schema{
		Type:        "object",
		Title:       "CreateRequest",
		Description: "Create request",
		Properties:  properties,
	}
}

// CreateUpdateRequestSchema creates a schema for update requests
func (sg *SchemaGenerator) CreateUpdateRequestSchema(properties map[string]*Schema) *Schema {
	return &Schema{
		Type:        "object",
		Title:       "UpdateRequest",
		Description: "Update request",
		Properties:  properties,
	}
}
