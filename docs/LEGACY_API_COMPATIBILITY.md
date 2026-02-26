# Legacy API Compatibility Layer

Complete guide for maintaining backward compatibility with GAIA_HOME Python clients during the migration to GAIA_GO.

## Overview

The Legacy API Compatibility Layer enables GAIA_HOME Python clients to communicate with GAIA_GO without requiring code changes. This allows for **gradual client migration** where old and new clients can coexist during the transition period.

## Architecture

```
Legacy Python Client
    ↓
Legacy API Endpoints (/api/sessions, /api/tasks, etc.)
    ↓
APIAdapter (Request translation layer)
    ↓
RequestTranslator (Format conversion)
AuthTranslator (Token conversion)
    ↓
GAIA_GO Repository Layer (Native Go models)
    ↓
PostgreSQL Database (Unified storage)
```

## Key Features

1. **Transparent Translation**: Legacy requests automatically converted to new format
2. **Request Logging**: All legacy API usage logged for migration tracking
3. **Token Migration**: Seamless authentication token conversion
4. **Error Recovery**: Graceful fallback for unknown endpoints
5. **Client Tracking**: Identify which clients are still using legacy API
6. **Gradual Deprecation**: Timeline-based legacy API shutdown with warnings

## Supported Endpoints

### Sessions

| Method | Endpoint | Python Format | Go Format |
|--------|----------|---------------|-----------|
| GET | `/api/sessions` | List all sessions | Same |
| POST | `/api/sessions` | Create session | Same |
| GET | `/api/sessions/{sessionID}` | Get session | Same |
| PUT | `/api/sessions/{sessionID}` | Update session | Same |
| DELETE | `/api/sessions/{sessionID}` | Delete session | Same |

### Tasks

| Method | Endpoint | Python Format | Go Format |
|--------|----------|---------------|-----------|
| GET | `/api/tasks` | List all tasks | Same |
| POST | `/api/tasks` | Create task | Same |
| GET | `/api/tasks/{taskID}` | Get task | Same |
| PUT | `/api/tasks/{taskID}` | Update task | Same |
| DELETE | `/api/tasks/{taskID}` | Delete task | Same |
| POST | `/api/tasks/claim` | Claim task for worker | Same |

### Errors

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/errors` | Log error (no auth required) |
| GET | `/api/errors` | List aggregated errors |

### Health

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/health` | System health check |

## Request Format Conversion

### Session Creation

**Legacy Python Format:**
```json
{
    "session_name": "session-123",
    "user_id": "user-456",
    "status": "active",
    "metadata": {
        "tier": "high_level",
        "provider": "claude"
    }
}
```

**Converted to Go Format (internal):**
```go
&models.Session{
    Name:      "session-123",
    UserID:    "user-456",
    Status:    "active",
    Metadata: {
        "tier": "high_level",
        "provider": "claude",
    },
}
```

**Response (same format as received):**
```json
{
    "id": "session-uuid",
    "name": "session-123",
    "user_id": "user-456",
    "status": "active",
    "created_at": "2026-02-25T10:30:00Z",
    "updated_at": "2026-02-25T10:30:00Z",
    "metadata": {...}
}
```

### Task Creation

**Legacy Python Format:**
```json
{
    "title": "Fix authentication bug",
    "description": "Bearer token not validating",
    "status": "pending",
    "priority": 5,
    "assigned_to": "worker-789"
}
```

**Converted to Go Format (internal):**
```go
&models.Task{
    Title:      "Fix authentication bug",
    Description: "Bearer token not validating",
    Status:     "pending",
    Priority:   5,
    AssignedTo: "worker-789",
}
```

## Authentication Token Conversion

The `AuthTranslator` handles conversion between legacy and new authentication formats:

### Supported Legacy Auth Formats

#### 1. Bearer Token (JWT)
```http
Authorization: Bearer eyJhbGc...
```

#### 2. API Key
```http
X-API-Key: gaia_user-456_a1b2c3d4
```

#### 3. Session ID
```http
X-Session-ID: session-123-uuid
```

#### 4. Basic Auth
```http
Authorization: Basic dXNlcjpwYXNz
```

#### 5. Legacy Token
```http
X-Legacy-Token: legacy_token_value
```

### Token Translation Flow

```
Legacy Token (any format)
    ↓
AuthTranslator.TranslateLegacyToken()
    ↓
Parse legacy format
    ↓
Extract User ID
    ↓
Check token cache (24-hour TTL)
    ↓
If cached: Return mapped token
If not: Generate new token & cache
    ↓
Return new JWT token to client
```

### Token Caching

Tokens are cached for 24 hours to avoid re-translation overhead:

```json
{
    "legacy_token": "original_token_value",
    "new_token": "gaia_go_user_456_a1b2c3d_1708779000",
    "user_id": "user-456",
    "legacy_format": "api_key",
    "created_at": "2026-02-25T10:30:00Z",
    "expires_at": "2026-02-26T10:30:00Z"
}
```

## Request Logging for Migration Tracking

Every legacy API request is logged for analysis:

```json
{
    "id": "req_1234",
    "client_id": "python-client-v1.2.3",
    "method": "POST",
    "endpoint": "/api/sessions",
    "status_code": 201,
    "duration_ms": 125,
    "translation_applied": true,
    "translation_errors": [],
    "auth_token_type": "api_key",
    "session_id": "session-uuid",
    "timestamp": "2026-02-25T10:30:00Z",
    "client_sdk_version": "1.2.3",
    "source_ip": "192.168.1.10",
    "user_agent": "GAIA_HOME_Client/1.2.3"
}
```

## Migration Metrics

Query `/api/legacy/migration/metrics` to get migration statistics:

```json
{
    "total_requests": 12543,
    "unique_clients": 45,
    "endpoints_used": [
        "/api/sessions",
        "/api/tasks",
        "/api/errors",
        "/api/health"
    ],
    "auth_types_used": [
        "api_key",
        "session_id",
        "jwt_legacy"
    ],
    "translation_errors": 23
}
```

## Configuration

### Enable Legacy API

```go
config := &legacy.MigrationConfig{
    LegacyModeEnabled:      true,
    LogLegacyRequests:      true,
    TranslationEnabled:     true,
    StrictMode:             false,
    ClientMigrationDeadline: time.Date(2026, 5, 1, 0, 0, 0, 0, time.UTC),
}

adapter := legacy.NewAPIAdapter(sessionRepo, taskRepo, config)
```

### Environment Variables

```bash
# Enable/disable legacy API
LEGACY_API_ENABLED=true

# Log all legacy requests for migration tracking
LOG_LEGACY_REQUESTS=true

# Enable automatic request/response translation
LEGACY_TRANSLATION_ENABLED=true

# Legacy API deprecation date
LEGACY_API_DEPRECATION_DATE=2026-05-01

# Token cache timeout in hours
LEGACY_TOKEN_CACHE_TIMEOUT=24

# Maximum request log size before rotation
LEGACY_REQUEST_LOG_MAX_SIZE=10000
```

## Client Migration Strategy

### Phase 1: Compatibility Mode (Weeks 1-4)

**Status**: Legacy API fully functional
**Actions**:
- All legacy clients work transparently
- Request logging active for client identification
- No client code changes required

**Verification**:
```bash
# Check which clients are still using legacy API
curl http://localhost:8080/api/legacy/migration/metrics | jq '.unique_clients'

# Identify migration blockers
curl http://localhost:8080/api/legacy/migration/requests | jq '.[] | select(.translation_errors | length > 0)'
```

### Phase 2: Warning Mode (Weeks 5-8)

**Status**: Legacy API functional with deprecation warnings
**Actions**:
- Add `X-Deprecated-API: true` header to all legacy responses
- Include `X-Deprecation-Date` header with migration deadline
- Log warning for each legacy request in application logs
- Notify teams with migration timeline

**Example Response Headers**:
```http
HTTP/1.1 200 OK
X-Deprecated-API: true
X-Deprecation-Date: 2026-05-01
X-Migration-Guide: https://docs.example.com/migration/go-clients
Content-Type: application/json
```

### Phase 3: Restricted Mode (Weeks 9-10)

**Status**: Legacy API requires explicit opt-in
**Actions**:
- Require `X-Legacy-Accept-Deprecation: true` header to use legacy API
- Return `410 Gone` for requests without this header
- Intensive outreach to remaining clients for migration
- Support tickets for clients unable to migrate

**Example**:
```bash
# This will fail
curl http://localhost:8080/api/sessions

# This will succeed
curl -H "X-Legacy-Accept-Deprecation: true" http://localhost:8080/api/sessions
```

### Phase 4: Shutdown Mode (Week 11+)

**Status**: Legacy API completely disabled
**Actions**:
- Return `410 Gone` for all legacy endpoints
- Redirect to new API documentation
- Archive legacy API code
- Plan infrastructure cleanup

## Request Format Mapping Reference

### Field Name Mappings

Legacy Python → Go GAIA_GO

| Python Field | Go Field | Notes |
|--------------|----------|-------|
| `session_name` | `name` | Session identifier |
| `user_id` | `user_id` | User ownership |
| `status` | `status` | Current state |
| `metadata` | `metadata` | Flexible metadata |
| `created_at` | `created_at` | Creation timestamp |
| `updated_at` | `updated_at` | Last update |
| `task_id` | `id` | Task identifier |
| `title` | `title` | Task name |
| `description` | `description` | Task details |
| `priority` | `priority` | Numeric priority |
| `assigned_to` | `assigned_to` | Worker assignment |
| `error_type` | `type` | Error classification |
| `stack_trace` | `stack_trace` | Error details |
| `node_id` | `node_id` | Error origin |

### Unknown Fields

Any fields not in the mapping are automatically stored in `metadata`:

**Legacy Request**:
```json
{
    "title": "Bug fix",
    "custom_field": "custom_value",
    "another_field": 123
}
```

**Internal Storage**:
```go
Task{
    Title: "Bug fix",
    Metadata: {
        "custom_field": "custom_value",
        "another_field": 123,
    },
}
```

**Legacy Response**:
```json
{
    "id": "task-uuid",
    "title": "Bug fix",
    "custom_field": "custom_value",
    "another_field": 123,
    ...
}
```

## Common Issues and Troubleshooting

### Issue: "Unable to parse legacy token format"

**Cause**: Authentication token not in recognized format

**Solution**:
1. Check auth header format (should be Bearer, Basic, X-API-Key, X-Session-ID, or X-Legacy-Token)
2. Verify token is complete and not truncated
3. Check token expiration

```bash
# Test token translation
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8080/api/sessions

# Check which auth format is being used
curl -X GET http://localhost:8080/api/sessions \
  -H "X-Debug-Auth: true" | jq '.auth_format'
```

### Issue: Session not found after migration

**Cause**: Session ID format changed between systems

**Solution**:
1. Check if session exists in new system
2. Verify session ID format (should be UUID)
3. Check translation logs for conversion errors

```bash
# Get translation errors for specific endpoint
curl http://localhost:8080/api/legacy/migration/requests | \
  jq '.[] | select(.endpoint == "/api/sessions/{sessionID}") | .translation_errors'
```

### Issue: Performance degradation with legacy API

**Cause**: Token translation overhead for large request volumes

**Solution**:
1. Increase token cache timeout (default 24 hours)
2. Monitor cache hit rate via metrics
3. Pre-warm cache with expected client tokens
4. Consider rate limiting for specific clients

```bash
# Check token cache stats
curl http://localhost:8080/api/legacy/auth-cache-stats | jq .

# Example response
{
    "total_cached_tokens": 1523,
    "valid_tokens": 1500,
    "expired_tokens": 23,
    "cache_timeout_hours": 24
}
```

## Monitoring and Alerting

### Key Metrics

| Metric | Purpose | Alert Threshold |
|--------|---------|-----------------|
| `legacy_requests_total` | Total legacy API calls | Trend analysis |
| `legacy_translation_errors` | Failed request translations | > 5 per minute |
| `legacy_unique_clients` | Active legacy clients | Track migration progress |
| `legacy_auth_failures` | Failed token translations | > 1% of requests |
| `legacy_response_latency_p95` | Response time percentile | > 500ms |

### Prometheus Queries

```promql
# Request rate by endpoint
rate(legacy_requests_total[5m])

# Error rate
rate(legacy_translation_errors_total[5m]) / rate(legacy_requests_total[5m])

# Unique clients using legacy API
count(count_values("client_id", legacy_requests_total) by (client_id))

# Token cache hit rate
rate(legacy_token_cache_hits_total[5m]) / rate(legacy_token_cache_lookups_total[5m])
```

### Alert Rules

```yaml
groups:
  - name: legacy_api
    rules:
      - alert: HighLegacyTranslationErrorRate
        expr: |
          rate(legacy_translation_errors_total[5m]) /
          rate(legacy_requests_total[5m]) > 0.01
        annotations:
          summary: "{{ $value | humanizePercentage }} legacy requests failing translation"

      - alert: LegacyClientsMissing
        expr: count(count_values("client_id", legacy_requests_total)) == 0
        for: 5m
        annotations:
          summary: "No legacy API traffic detected (expected during normal operation)"

      - alert: LegacyAPIDeprecationDeadline
        expr: |
          time() > ignoring(legacy_deprecation_date)
          (legacy_deprecation_date_unix)
        annotations:
          summary: "Legacy API deprecation deadline has passed"
```

## API Documentation for Clients

### Session Operations

```python
# List sessions
GET /api/sessions
Response: [
    {
        "id": "session-uuid",
        "name": "session-123",
        "status": "active",
        "user_id": "user-456",
        "created_at": "2026-02-25T10:30:00Z",
        "metadata": {...}
    },
    ...
]

# Create session
POST /api/sessions
Request: {
    "session_name": "new-session",
    "user_id": "user-456",
    "status": "active"
}
Response: {
    "id": "session-uuid",
    "name": "new-session",
    ...
}

# Get specific session
GET /api/sessions/{sessionID}
Response: {...}

# Update session
PUT /api/sessions/{sessionID}
Request: {
    "status": "inactive"
}
Response: {...}

# Delete session
DELETE /api/sessions/{sessionID}
Response: 204 No Content
```

## Migration Timeline

```
Week 1-4:    Compatibility Mode
             ├─ Monitor legacy API usage
             ├─ Identify migration blockers
             └─ Plan client updates

Week 5-8:    Warning Mode
             ├─ Deprecation headers added
             ├─ Notify client teams
             └─ Provide migration support

Week 9-10:   Restricted Mode
             ├─ Require explicit opt-in
             ├─ Intensive outreach
             └─ Support migration issues

Week 11+:    Shutdown Mode
             ├─ Legacy API disabled
             ├─ Return 410 Gone
             └─ Archive code
```

## Reference

- [Migration Guide](./MIGRATION_GUIDE.md) - GAIA_HOME to GAIA_GO migration
- [API Documentation](./API.md) - New GAIA_GO API
- [Deployment Guide](./DEPLOYMENT.md) - Infrastructure setup
