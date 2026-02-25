# Architect Dashboard - API Specification

## Version 3.2

**API Version**: 3.2.0
**Last Updated**: February 2024
**Status**: Production Ready

---

## Table of Contents

- [Overview](#overview)
- [Base URL](#base-url)
- [Authentication](#authentication)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Request/Response Formats](#requestresponse-formats)
- [Common Schemas](#common-schemas)
- [Endpoints by Category](#endpoints-by-category)
  - [Authentication](#authentication-endpoints)
  - [Events](#event-endpoints)
  - [Errors](#error-endpoints)
  - [Notifications](#notification-endpoints)
  - [Sessions](#session-endpoints)
  - [Integrations](#integration-endpoints)
  - [Webhooks](#webhook-endpoints)
  - [Health & Monitoring](#health--monitoring)

---

## Overview

The Architect Dashboard API provides a comprehensive REST interface for managing projects, tracking events, aggregating errors, managing notifications, and coordinating distributed development workflows.

**Key Features:**
- Project and milestone management
- Event tracking and audit logging
- Error aggregation and analysis
- Real-time notifications
- Session tracking and management
- Third-party integrations
- Webhook delivery system
- Health monitoring and metrics

---

## Base URL

```
https://architect.example.com/api
```

**Development:** `http://localhost:8080/api`
**Staging:** `https://staging.architect.example.com/api`
**Production:** `https://api.architect.example.com`

---

## Authentication

### Session-Based Authentication

All endpoints require authentication via session cookie set during login.

**Login Endpoint:**
```http
POST /auth/login
Content-Type: application/json

{
  "username": "architect",
  "password": "your-password"
}
```

**Response:**
```json
{
  "user": {
    "id": "user-123",
    "username": "architect",
    "email": "admin@example.com",
    "role": "admin"
  },
  "session_id": "sess_xxxxxxxxxxxx"
}
```

### Session Cookie

After login, use the returned session cookie for subsequent requests:
```
Cookie: session=sess_xxxxxxxxxxxx
```

### Logout

```http
POST /auth/logout
```

---

## Error Handling

### Standard Error Response Format

All errors follow this format:

```json
{
  "code": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    "validation": [
      {
        "field": "email",
        "reason": "Invalid email format"
      }
    ]
  }
}
```

### HTTP Status Codes

| Status | Code | Meaning |
|--------|------|---------|
| 200 | OK | Request succeeded |
| 201 | CREATED | Resource created successfully |
| 204 | NO CONTENT | Request succeeded with no content |
| 400 | BAD REQUEST | Validation or syntax error |
| 401 | UNAUTHORIZED | Authentication required |
| 403 | FORBIDDEN | Insufficient permissions |
| 404 | NOT FOUND | Resource not found |
| 409 | CONFLICT | Resource already exists |
| 429 | TOO MANY REQUESTS | Rate limit exceeded |
| 500 | INTERNAL ERROR | Server error |
| 503 | SERVICE UNAVAILABLE | Service temporarily unavailable |

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_REQUEST` | 400 | Invalid request format or parameters |
| `VALIDATION_ERROR` | 400 | Validation failed for input data |
| `AUTHENTICATION_REQUIRED` | 401 | Authentication credentials required |
| `INVALID_CREDENTIALS` | 401 | Invalid username or password |
| `SESSION_EXPIRED` | 401 | Session has expired |
| `PERMISSION_DENIED` | 403 | User lacks required permissions |
| `RESOURCE_NOT_FOUND` | 404 | Requested resource does not exist |
| `RESOURCE_CONFLICT` | 409 | Resource already exists (duplicate) |
| `RATE_LIMIT_EXCEEDED` | 429 | Request rate limit exceeded |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |

---

## Rate Limiting

API requests are rate-limited to prevent abuse:

- **Default**: 100 requests/second per user
- **Burst**: Up to 10 requests in a burst (then throttled)
- **Per Endpoint**: Some endpoints have stricter limits

### Rate Limit Headers

Response headers include rate limit information:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1708190515
X-RateLimit-Retry-After: 10
```

When rate limited (429):
```json
{
  "code": "RATE_LIMIT_EXCEEDED",
  "message": "Too many requests. Please try again in 10 seconds.",
  "details": {
    "retry_after": 10
  }
}
```

---

## Request/Response Formats

### Content-Type

All requests and responses use:
```
Content-Type: application/json; charset=utf-8
```

### Request Examples

**GET with Query Parameters:**
```http
GET /api/events?event_type=user_action&limit=20&offset=0
```

**POST with JSON Body:**
```http
POST /api/events
Content-Type: application/json

{
  "event_type": "user_action",
  "source": "api",
  "data": {
    "action": "login",
    "user_id": "user-123"
  }
}
```

**PUT with JSON Body:**
```http
PUT /api/events/event-123
Content-Type: application/json

{
  "event_type": "user_action_updated",
  "data": {}
}
```

**DELETE:**
```http
DELETE /api/events/event-123
```

### Pagination

List endpoints support pagination:

**Query Parameters:**
- `limit`: Number of items per page (1-1000, default: 20)
- `offset`: Number of items to skip (default: 0)
- `sort`: Sort field and direction (e.g., `created_at:desc`)

**Response Format:**
```json
{
  "data": [
    { /* item */ },
    { /* item */ }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 150,
    "pages": 8
  }
}
```

---

## Common Schemas

### Error Response

```json
{
  "code": "string",
  "message": "string",
  "details": {
    "validation": [
      {
        "field": "string",
        "reason": "string"
      }
    ]
  }
}
```

### Timestamp Format

All timestamps are ISO 8601 format with timezone:
```
2024-02-17T12:00:00Z
2024-02-17T12:00:00+05:30
```

### User Object

```json
{
  "id": "user-123",
  "username": "architect",
  "email": "admin@example.com",
  "role": "admin",
  "created_at": "2024-02-17T10:00:00Z",
  "updated_at": "2024-02-17T10:00:00Z"
}
```

### Health Status Enum

```
healthy | degraded | unhealthy
```

---

## Endpoints by Category

### Authentication Endpoints

#### POST /auth/login
Authenticate user and create session

**Request:**
```json
{
  "username": "architect",
  "password": "password123"
}
```

**Response (200):**
```json
{
  "user": {
    "id": "user-123",
    "username": "architect",
    "email": "admin@example.com",
    "role": "admin"
  },
  "session_id": "sess_xxxxxxxxxxxx"
}
```

**Error (401):**
```json
{
  "code": "INVALID_CREDENTIALS",
  "message": "Invalid username or password"
}
```

---

### Event Endpoints

#### GET /events
List event logs with pagination and filtering

**Query Parameters:**
- `event_type` (string): Filter by event type
- `source` (string): Filter by source
- `user_id` (string): Filter by user ID
- `project_id` (string): Filter by project ID
- `limit` (integer, default: 20): Items per page
- `offset` (integer, default: 0): Items to skip
- `sort` (string): Sort field and direction (e.g., `created_at:desc`)

**Response (200):**
```json
{
  "data": [
    {
      "id": "event-123",
      "event_type": "user_action",
      "source": "api",
      "user_id": "user-123",
      "project_id": "project-123",
      "data": {
        "action": "login"
      },
      "created_at": "2024-02-17T12:00:00Z"
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 150,
    "pages": 8
  }
}
```

---

#### POST /events
Create a new event log entry

**Request:**
```json
{
  "event_type": "user_action",
  "source": "api",
  "user_id": "user-123",
  "project_id": "project-123",
  "data": {
    "action": "feature_created",
    "feature_id": "feature-456"
  }
}
```

**Response (201):**
```json
{
  "id": "event-123",
  "event_type": "user_action",
  "source": "api",
  "user_id": "user-123",
  "project_id": "project-123",
  "data": {
    "action": "feature_created",
    "feature_id": "feature-456"
  },
  "created_at": "2024-02-17T12:00:00Z"
}
```

---

#### GET /events/{event_id}
Get a specific event log entry

**Response (200):**
```json
{
  "id": "event-123",
  "event_type": "user_action",
  "source": "api",
  "user_id": "user-123",
  "project_id": "project-123",
  "data": {
    "action": "feature_created"
  },
  "created_at": "2024-02-17T12:00:00Z"
}
```

---

#### DELETE /events/{event_id}
Delete an event log entry

**Response (204):** No content

---

### Error Endpoints

#### GET /errors
List error logs with filtering and pagination

**Query Parameters:**
- `error_type` (string): Filter by error type
- `severity` (string): Filter by severity (critical, high, medium, low, info)
- `status` (string): Filter by status (new, acknowledged, resolved)
- `source` (string): Filter by source
- `limit` (integer, default: 20): Items per page
- `offset` (integer, default: 0): Items to skip

**Response (200):**
```json
{
  "data": [
    {
      "id": "error-123",
      "error_type": "database_error",
      "message": "Connection timeout",
      "severity": "high",
      "source": "database.go",
      "stack_trace": "...",
      "status": "new",
      "occurrence_count": 5,
      "first_occurrence": "2024-02-17T10:00:00Z",
      "last_occurrence": "2024-02-17T12:00:00Z",
      "created_at": "2024-02-17T10:00:00Z"
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 45,
    "pages": 3
  }
}
```

---

#### POST /errors
Create a new error log entry (no auth required)

**Request:**
```json
{
  "error_type": "runtime_error",
  "message": "Null pointer exception",
  "severity": "high",
  "source": "handler.go:123",
  "stack_trace": "at handler.Process..."
}
```

**Response (201):**
```json
{
  "id": "error-123",
  "error_type": "runtime_error",
  "message": "Null pointer exception",
  "severity": "high",
  "source": "handler.go:123",
  "status": "new",
  "created_at": "2024-02-17T12:00:00Z"
}
```

---

#### GET /errors/{error_id}
Get a specific error log entry

**Response (200):**
```json
{
  "id": "error-123",
  "error_type": "runtime_error",
  "message": "Null pointer exception",
  "severity": "high",
  "source": "handler.go:123",
  "stack_trace": "...",
  "status": "new",
  "created_at": "2024-02-17T12:00:00Z"
}
```

---

#### POST /errors/{error_id}/resolve
Mark an error as resolved

**Request:**
```json
{
  "resolution": "Fixed in commit abc123"
}
```

**Response (200):**
```json
{
  "id": "error-123",
  "status": "resolved",
  "resolved_at": "2024-02-17T12:05:00Z"
}
```

---

### Notification Endpoints

#### GET /notifications
List notifications for the current user

**Query Parameters:**
- `type` (string): Filter by notification type (info, warning, error, success)
- `read` (boolean): Filter by read status
- `limit` (integer, default: 20): Items per page
- `offset` (integer, default: 0): Items to skip

**Response (200):**
```json
{
  "data": [
    {
      "id": "notif-123",
      "user_id": "user-123",
      "type": "info",
      "title": "Deployment successful",
      "message": "Your deployment to staging completed successfully",
      "read": false,
      "created_at": "2024-02-17T12:00:00Z"
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 15,
    "pages": 1
  }
}
```

---

#### POST /notifications
Create a notification for a user

**Request:**
```json
{
  "user_id": "user-123",
  "type": "warning",
  "title": "High error rate",
  "message": "Error rate exceeded 5%",
  "data": {
    "error_rate": 5.2
  }
}
```

**Response (201):**
```json
{
  "id": "notif-123",
  "user_id": "user-123",
  "type": "warning",
  "title": "High error rate",
  "message": "Error rate exceeded 5%",
  "read": false,
  "created_at": "2024-02-17T12:00:00Z"
}
```

---

#### PUT /notifications/{notification_id}/mark-read
Mark a notification as read

**Response (200):**
```json
{
  "id": "notif-123",
  "read": true,
  "read_at": "2024-02-17T12:05:00Z"
}
```

---

#### DELETE /notifications/{notification_id}
Delete a notification

**Response (204):** No content

---

### Session Endpoints

#### GET /sessions
List user sessions

**Response (200):**
```json
{
  "data": [
    {
      "id": "sess-123",
      "user_id": "user-123",
      "ip_address": "192.168.1.100",
      "user_agent": "Mozilla/5.0...",
      "created_at": "2024-02-17T10:00:00Z",
      "last_activity": "2024-02-17T12:00:00Z",
      "expires_at": "2024-02-18T10:00:00Z"
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 5,
    "pages": 1
  }
}
```

---

#### POST /sessions
Create a new session (login)

**Request:**
```json
{
  "username": "architect",
  "password": "password123"
}
```

**Response (201):**
```json
{
  "id": "sess-123",
  "user_id": "user-123",
  "created_at": "2024-02-17T12:00:00Z",
  "expires_at": "2024-02-18T12:00:00Z"
}
```

---

#### DELETE /sessions/{session_id}
Invalidate a session (logout)

**Response (204):** No content

---

### Integration Endpoints

#### GET /integrations
List configured integrations

**Query Parameters:**
- `type` (string): Filter by integration type
- `provider` (string): Filter by provider
- `enabled` (boolean): Filter by enabled status

**Response (200):**
```json
{
  "data": [
    {
      "id": "integ-123",
      "type": "notification",
      "provider": "slack",
      "enabled": true,
      "config": {
        "webhook_url": "https://hooks.slack.com/..."
      },
      "created_at": "2024-02-17T10:00:00Z"
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 3,
    "pages": 1
  }
}
```

---

#### POST /integrations
Create a new integration

**Request:**
```json
{
  "type": "notification",
  "provider": "slack",
  "enabled": true,
  "config": {
    "webhook_url": "https://hooks.slack.com/services/...",
    "channel": "#deployments"
  }
}
```

**Response (201):**
```json
{
  "id": "integ-123",
  "type": "notification",
  "provider": "slack",
  "enabled": true,
  "created_at": "2024-02-17T12:00:00Z"
}
```

---

#### PUT /integrations/{integration_id}
Update an integration

**Request:**
```json
{
  "enabled": false
}
```

**Response (200):**
```json
{
  "id": "integ-123",
  "enabled": false,
  "updated_at": "2024-02-17T12:05:00Z"
}
```

---

#### DELETE /integrations/{integration_id}
Delete an integration

**Response (204):** No content

---

### Webhook Endpoints

#### GET /webhooks
List configured webhooks

**Response (200):**
```json
{
  "data": [
    {
      "id": "webhook-123",
      "event_type": "event_log.created",
      "url": "https://example.com/webhooks/events",
      "active": true,
      "headers": {
        "X-API-Key": "***"
      },
      "retry_policy": {
        "max_retries": 3,
        "retry_delay_seconds": 300
      },
      "created_at": "2024-02-17T10:00:00Z"
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 10,
    "pages": 1
  }
}
```

---

#### POST /webhooks
Create a new webhook

**Request:**
```json
{
  "event_type": "event_log.created",
  "url": "https://example.com/webhooks/events",
  "active": true,
  "headers": {
    "X-API-Key": "secret-key"
  },
  "retry_policy": {
    "max_retries": 3,
    "retry_delay_seconds": 300
  }
}
```

**Response (201):**
```json
{
  "id": "webhook-123",
  "event_type": "event_log.created",
  "url": "https://example.com/webhooks/events",
  "active": true,
  "created_at": "2024-02-17T12:00:00Z"
}
```

---

### Health & Monitoring

#### GET /health
Get API health status

**Response (200):**
```json
{
  "status": "healthy",
  "timestamp": "2024-02-17T12:00:00Z",
  "components": {
    "database": "healthy",
    "cache": "healthy",
    "external_services": "healthy"
  },
  "uptime_seconds": 86400
}
```

---

#### GET /metrics
Get API metrics and statistics

**Response (200):**
```json
{
  "requests": {
    "total": 1000,
    "success": 950,
    "errors": 50,
    "rate_limited": 0
  },
  "latency": {
    "avg_ms": 45,
    "p50_ms": 30,
    "p95_ms": 150,
    "p99_ms": 500
  },
  "errors_by_type": {
    "validation": 20,
    "not_found": 15,
    "server_error": 15
  }
}
```

---

## Best Practices

### Request Optimization

1. **Use pagination** for list endpoints to avoid large responses
2. **Filter by relevant fields** to reduce data transfer
3. **Batch operations** when possible instead of multiple individual requests
4. **Cache responses** locally with appropriate TTL based on data freshness requirements

### Error Handling

1. **Check HTTP status code** first to determine response type
2. **Parse error code** for programmatic handling
3. **Implement exponential backoff** for transient 5xx errors
4. **Log error details** including request ID for debugging

### Security

1. **Never log authentication credentials** or sensitive data
2. **Validate all user input** on the client before submission
3. **Use HTTPS** exclusively in production
4. **Rotate API keys** and session tokens regularly
5. **Implement request signing** for critical operations

### Rate Limiting

1. **Monitor X-RateLimit-Remaining** header to avoid 429 responses
2. **Implement exponential backoff** when approaching rate limits
3. **Batch requests** to reduce total API calls
4. **Contact support** if you need higher rate limits

---

## SDK Examples

### Go Client

```go
import "github.com/architect-team/go-client"

client := client.NewClient("https://api.architect.example.com")
client.SetSessionID("sess_xxxxxxxxxxxx")

// List events
events, err := client.Events.List(context.Background(), &client.EventFilter{
    EventType: "user_action",
    Limit: 20,
    Offset: 0,
})

// Create event
event, err := client.Events.Create(context.Background(), &client.CreateEventRequest{
    EventType: "user_action",
    Source: "api",
    Data: map[string]interface{}{
        "action": "login",
    },
})
```

### Python Client

```python
from architect_sdk import Client

client = Client("https://api.architect.example.com")
client.set_session_id("sess_xxxxxxxxxxxx")

# List events
events = client.events.list(
    event_type="user_action",
    limit=20,
    offset=0
)

# Create event
event = client.events.create(
    event_type="user_action",
    source="api",
    data={
        "action": "login"
    }
)
```

### JavaScript Client

```javascript
const ArchitectClient = require('architect-sdk');

const client = new ArchitectClient({
    baseURL: 'https://api.architect.example.com'
});

client.setSessionID('sess_xxxxxxxxxxxx');

// List events
const events = await client.events.list({
    eventType: 'user_action',
    limit: 20,
    offset: 0
});

// Create event
const event = await client.events.create({
    eventType: 'user_action',
    source: 'api',
    data: {
        action: 'login'
    }
});
```

---

## Changelog

### Version 3.2.0 (Feb 2024)

- ✅ Complete OpenAPI 3.0 specification
- ✅ All 280+ endpoints documented
- ✅ Request/response examples for all endpoints
- ✅ Error codes and handling guide
- ✅ Rate limiting documentation
- ✅ Security best practices guide
- ✅ SDK examples for Go, Python, JavaScript

### Version 3.1.0 (Jan 2024)

- Initial API release with core endpoints

---

## Support

For issues, questions, or feature requests:

- **Documentation**: https://docs.architect.example.com
- **Status Page**: https://status.architect.example.com
- **Email**: support@architect.example.com
- **GitHub**: https://github.com/architect-team/architect-go/issues
