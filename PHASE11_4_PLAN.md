# Phase 11.4: Admin Dashboard & Monitoring

## Overview

Phase 11.4 implements the administrative interface and monitoring capabilities for command execution quotas. This includes API endpoints for quota management, real-time dashboards, analytics, and alerts.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Admin Dashboard (Web UI)                                   │
│  ├─ Quota Status Panel                                      │
│  ├─ User Quota Management                                   │
│  ├─ Execution Analytics                                     │
│  ├─ System Load Monitoring                                  │
│  └─ Alert Configuration                                     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
        ┌────────────────────────┐
        │  Admin API Endpoints   │
        │  (REST + WebSocket)    │
        └────────────┬───────────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
    ┌─────────┐ ┌──────────┐ ┌─────────┐
    │ Quota   │ │ Analytics│ │ Alerts  │
    │ Mgmt    │ │ Engine   │ │ Engine  │
    └────┬────┘ └────┬─────┘ └────┬────┘
         │           │            │
         └───────────┼────────────┘
                     │
                     ▼
         ┌──────────────────────┐
         │  Database / Cache    │
         │  (Quotas & Metrics)  │
         └──────────────────────┘
```

## Component 1: Admin API Endpoints

### File: `pkg/http/handlers/quota_admin_handlers.go` (NEW)

#### Quota Management Endpoints

**GET /api/admin/quotas/status**
- Returns system-wide quota statistics
- Response:
```json
{
  "total_users": 1234,
  "total_commands_today": 567890,
  "average_throttle_factor": 0.85,
  "high_utilization_users": 45,
  "quotas_exceeded_today": 12,
  "system_load": {
    "cpu_percent": 65.4,
    "memory_percent": 72.1,
    "throttle_active": false
  }
}
```

**GET /api/admin/quotas/users**
- List all users with quota information
- Query params: `sort`, `limit`, `offset`, `search`
- Returns paginated list with current usage

**GET /api/admin/quotas/users/{userID}**
- Get detailed quota info for specific user
- Response:
```json
{
  "user_id": 123,
  "username": "john_doe",
  "daily": {
    "shell": { "limit": 500, "used": 245, "remaining": 255 },
    "code": { "limit": 300, "used": 120, "remaining": 180 },
    "test": { "limit": 1000, "used": 567, "remaining": 433 }
  },
  "weekly": { ... },
  "monthly": { ... },
  "tier": "free",
  "commands_today": 245,
  "throttle_factor": 0.9,
  "last_command": "2026-02-25T22:15:00Z"
}
```

**PUT /api/admin/quotas/users/{userID}**
- Update user quota tier or custom limits
- Request body:
```json
{
  "tier": "premium",  // or "custom"
  "custom_limits": {
    "shell": { "daily": 1000, "weekly": 5000, "monthly": 20000 },
    "code": { "daily": 600, "weekly": 3000, "monthly": 10000 }
  }
}
```

**GET /api/admin/quotas/rules**
- List all quota rules (global + user-specific)
- Returns:
```json
{
  "global_rules": [...],
  "user_specific_rules": [...]
}
```

**POST /api/admin/quotas/rules**
- Create new quota rule
- Request:
```json
{
  "user_id": null,  // null for global
  "command_type": "shell",
  "daily_limit": 500,
  "weekly_limit": 3000,
  "monthly_limit": 10000,
  "enabled": true
}
```

**PUT /api/admin/quotas/rules/{ruleID}**
- Update quota rule

**DELETE /api/admin/quotas/rules/{ruleID}**
- Delete quota rule

#### Execution History Endpoints

**GET /api/admin/quotas/executions**
- List recent command executions
- Query params: `user_id`, `command_type`, `since`, `limit`
- Response:
```json
{
  "executions": [
    {
      "id": 12345,
      "user_id": 123,
      "username": "john_doe",
      "command_type": "shell",
      "duration_ms": 1250,
      "cpu_usage": 15.5,
      "memory_usage": 120,
      "exit_code": 0,
      "executed_at": "2026-02-25T22:15:00Z"
    }
  ],
  "total": 45678
}
```

**GET /api/admin/quotas/executions/stats**
- Aggregate execution statistics
- Response:
```json
{
  "daily_commands": 567890,
  "average_duration_ms": 1250,
  "success_rate": 98.5,
  "by_command_type": {
    "shell": { "count": 234567, "avg_duration": 1100 },
    "code": { "count": 123456, "avg_duration": 1500 }
  },
  "by_user": [
    { "user_id": 123, "commands": 5678, "percent": 10.2 },
    { "user_id": 456, "commands": 4567, "percent": 8.1 }
  ]
}
```

### Monitoring Endpoints

**GET /api/admin/quotas/violations**
- List quota violations
- Response:
```json
{
  "violations": [
    {
      "id": 1,
      "user_id": 123,
      "command_type": "shell",
      "quota_exceeded": "daily",
      "violated_at": "2026-02-25T22:15:00Z",
      "limit": 500,
      "attempted": 501,
      "remaining_period": "12h 45m"
    }
  ]
}
```

**GET /api/admin/quotas/alerts**
- Get configured alerts
- Response:
```json
{
  "alerts": [
    {
      "id": 1,
      "name": "High Quota Utilization",
      "condition": "usage > 80%",
      "threshold": 80,
      "period": "daily",
      "enabled": true,
      "notifications": ["email", "webhook"]
    }
  ]
}
```

**POST /api/admin/quotas/alerts**
- Create new alert
- Request:
```json
{
  "name": "Daily Quota Warning",
  "condition": "usage_percent > 75",
  "threshold": 75,
  "period": "daily",
  "notify_users": true,
  "notify_admins": true,
  "webhook_url": "https://..."
}
```

## Component 2: Analytics Engine

### File: `pkg/services/rate_limiting/analytics.go` (NEW)

```go
type QuotaAnalytics struct {
    db *gorm.DB
    cache map[string]interface{}
    cacheTTL time.Time
}

// Key Methods:
func (qa *QuotaAnalytics) GetSystemStats(ctx) SystemStats
func (qa *QuotaAnalytics) GetUserStats(ctx, userID) UserStats
func (qa *QuotaAnalytics) GetCommandTypeStats(ctx, cmdType) CommandStats
func (qa *QuotaAnalytics) GetQuotaViolationTrends(ctx, days int) TrendData
func (qa *QuotaAnalytics) GetHighUtilizationUsers(ctx) []UserStats
func (qa *QuotaAnalytics) GetPredictedViolations(ctx) []Prediction
```

### Data Types

```go
type SystemStats struct {
    TotalUsers             int
    ActiveUsersToday       int
    TotalCommandsToday     int
    AverageThrottleFactor  float64
    HighUtilizationCount   int
    ViolationsToday        int
    P95ResponseTime        time.Duration
    SystemLoad             SystemLoadStatus
}

type UserStats struct {
    UserID                 int64
    Username               string
    Tier                   string
    QuotaUtilization       map[string]float64 // % per period
    CommandsExecuted       int
    AverageDuration        time.Duration
    SuccessRate            float64
    ThrottleFactor         float64
}

type TrendData struct {
    Dates       []time.Time
    CommandCount []int
    ViolationCount []int
    AverageThrottle []float64
}
```

## Component 3: Alert Engine

### File: `pkg/services/rate_limiting/alerts.go` (NEW)

```go
type AlertEngine struct {
    db *gorm.DB
    notifier Notifier
    checkInterval time.Duration
}

// Alert Types:
const (
    AlertHighUtilization = "high_utilization"      // >80% quota
    AlertViolation       = "quota_violation"       // Exceeded limit
    AlertThrottling      = "sustained_throttling"  // >50% commands throttled
    AlertSystemLoad      = "high_system_load"      // CPU/memory critical
    AlertAnomalies       = "usage_anomalies"       // Unusual patterns
)

// Methods:
func (ae *AlertEngine) CheckAlerts(ctx) []Alert
func (ae *AlertEngine) CreateAlert(ctx, rule AlertRule) error
func (ae *AlertEngine) UpdateAlert(ctx, id int64, rule AlertRule) error
func (ae *AlertEngine) DeleteAlert(ctx, id int64) error
func (ae *AlertEngine) SendNotification(ctx, alert Alert) error
```

### Notification Types

```go
type NotificationChannel interface {
    Send(ctx, alert Alert) error
}

// Implementations:
- EmailNotifier
- WebhookNotifier
- SlackNotifier
- DashboardNotifier (in-app alert)
```

## Component 4: Dashboard UI

### File: `templates/admin_quotas.html` (NEW)

**Sections:**

1. **System Overview**
   - Total users, commands today
   - System load gauge
   - Throttle status

2. **Quota Status**
   - Overall utilization percentage
   - Commands executed vs. capacity
   - Top command types by usage
   - High utilization users list

3. **User Management**
   - User list with quotas
   - Search and filter
   - Inline quota editing
   - Bulk operations (upgrade tier, reset quotas)

4. **Execution Analytics**
   - Command type distribution (pie chart)
   - Execution timeline (line chart)
   - Duration distribution (histogram)
   - Success rate by type

5. **Violations & Alerts**
   - Recent violations table
   - Alert configuration panel
   - Configured alerts list
   - Test alert functionality

6. **System Health**
   - CPU/Memory graphs
   - Throttle events timeline
   - Database performance metrics
   - Quota check latency

### UI Components

```html
<!-- Quota Status Card -->
<div class="quota-card">
  <h3>Shell Commands</h3>
  <div class="progress-bar">
    <div class="used" style="width: 49%"></div>
  </div>
  <div class="stats">
    <span>245 / 500 (49%)</span>
    <span class="remaining">255 remaining</span>
  </div>
</div>

<!-- User Management Table -->
<table class="user-quotas">
  <thead>
    <tr>
      <th>User</th>
      <th>Tier</th>
      <th>Daily</th>
      <th>Weekly</th>
      <th>Monthly</th>
      <th>Actions</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>john_doe</td>
      <td>
        <select class="tier-select">
          <option>free</option>
          <option selected>premium</option>
          <option>enterprise</option>
        </select>
      </td>
      <td><progress value="245" max="500"></progress> 49%</td>
      <td>32% ████░░░░</td>
      <td>12% █░░░░░░░░</td>
      <td>
        <button>Edit</button>
        <button>Reset</button>
      </td>
    </tr>
  </tbody>
</table>

<!-- Chart Components -->
<canvas id="command-timeline"></canvas>
<canvas id="utilization-by-user"></canvas>
<canvas id="system-load"></canvas>
```

## Component 5: WebSocket Real-Time Updates

### File: `pkg/http/handlers/quota_websocket.go` (NEW)

```go
// WebSocket endpoint: /ws/admin/quotas
// Broadcasts:
// 1. System stats every 5 seconds
// 2. New quota violations in real-time
// 3. Alert notifications
// 4. User status changes

type QuotaUpdate struct {
    Type      string                 // "stats", "violation", "alert", "user_update"
    Timestamp time.Time
    Data      map[string]interface{}
}
```

## Implementation Phases

### Phase 11.4.1: API Endpoints (Week 1)
1. Create `quota_admin_handlers.go` with all CRUD endpoints
2. Implement quota management endpoints
3. Add execution history endpoints
4. Add violation/alert endpoints
5. Write unit tests for endpoints

### Phase 11.4.2: Analytics Engine (Week 1-2)
1. Create `analytics.go` with QuotaAnalytics service
2. Implement system-wide statistics
3. Implement per-user statistics
4. Implement trend analysis
5. Implement anomaly detection

### Phase 11.4.3: Alert Engine (Week 2)
1. Create `alerts.go` with AlertEngine
2. Implement alert rules and checking
3. Implement notification channels
4. Add webhook support
5. Add email notifications

### Phase 11.4.4: Dashboard UI (Week 2-3)
1. Create admin quota dashboard template
2. Implement system overview panel
3. Implement user management table
4. Add analytics charts
5. Add quota editing interface

### Phase 11.4.5: Real-Time Updates (Week 3)
1. Implement WebSocket endpoint
2. Add server-sent events
3. Real-time alerts in dashboard
4. Live metric updates

### Phase 11.4.6: Testing & Integration (Week 3-4)
1. Integration tests for API
2. Load test analytics queries
3. Test alert triggering
4. Test dashboard performance
5. Production deployment

## API Security

- ✓ Require admin role for all quota endpoints
- ✓ Log all quota modifications
- ✓ Rate limit admin API (100 req/min per admin)
- ✓ Audit trail for quota changes
- ✓ CSRF protection on all POST/PUT/DELETE
- ✓ Input validation on all parameters

## Performance Targets

| Operation | Target | Method |
|-----------|--------|--------|
| List users | <200ms | Pagination + caching |
| Get user stats | <50ms | Materialized views |
| System stats | <100ms | Cache with 1min TTL |
| Analytics query | <500ms | Pre-aggregated data |
| WebSocket update | <10ms | In-memory streaming |

## Monitoring & Logging

**Logs to capture:**
- Quota modifications (user, admin, timestamp, change)
- Quota violations (user, command, exceeded by how much)
- Alerts triggered (type, user affected, action taken)
- API access (endpoint, user, response time)
- Analytics queries (type, duration, cache hit)

**Metrics to export:**
- `quota_checks_total` - Total quota checks
- `quota_violations_total` - Total violations
- `quota_api_requests` - Admin API requests
- `analytics_query_duration_ms` - Analytics latency
- `alert_notifications_sent` - Alerts sent
- `dashboard_websocket_connections` - Active connections

## Database Views for Analytics

```sql
-- Quota utilization by user (daily)
CREATE VIEW daily_utilization AS
SELECT u.id, u.username,
       SUM(cqu.commands_executed) as commands_used,
       SUM(cqr.daily_limit) as quota_limit,
       (SUM(cqu.commands_executed) * 100.0 / SUM(cqr.daily_limit)) as utilization_percent
FROM users u
LEFT JOIN command_quota_usage cqu ON u.id = cqu.user_id
LEFT JOIN command_quota_rules cqr ON u.id = cqr.user_id
WHERE cqu.usage_period = 'daily' AND cqu.period_start = CURRENT_DATE
GROUP BY u.id, u.username;

-- Quota violations trend
CREATE VIEW violation_trends AS
SELECT DATE(violation_time) as date,
       COUNT(*) as total_violations,
       COUNT(DISTINCT user_id) as unique_users_affected
FROM quota_violations
GROUP BY DATE(violation_time)
ORDER BY date DESC;
```

## Integration with Architect Dashboard

**New Menu Items:**
- System → Quotas & Rate Limiting
  - System Overview
  - User Management
  - Quota Rules
  - Analytics
  - Alerts

**New Panels:**
- Dashboard → Quota Status (summary)
- System Health → Quota Metrics

## Rollout Strategy

1. **Phase 1: Deploy APIs**
   - Deploy endpoints in read-only mode
   - Monitor for performance issues
   - Collect baseline metrics

2. **Phase 2: Enable Modifications**
   - Enable quota updates for specific admins
   - Test quota changes
   - Monitor impact

3. **Phase 3: Deploy Dashboard**
   - Make dashboard available to admins
   - Train admins on usage
   - Gather feedback

4. **Phase 4: Enable User-Facing Features**
   - Show quotas to users in API responses
   - Add quota warnings to CLI
   - Notify users of limits

## Success Criteria

- ✓ All admin endpoints operational
- ✓ Analytics queries complete in <500ms
- ✓ Dashboard loads in <2 seconds
- ✓ Real-time updates with <1s latency
- ✓ Alert system responds in <30 seconds
- ✓ No impact on command execution performance
- ✓ Comprehensive audit trail
- ✓ Zero false positives in alerts

## Files to Create

1. `pkg/http/handlers/quota_admin_handlers.go`
2. `pkg/services/rate_limiting/analytics.go`
3. `pkg/services/rate_limiting/alerts.go`
4. `pkg/http/handlers/quota_websocket.go`
5. `templates/admin_quotas.html`
6. `static/js/admin_quotas.js`
7. `static/css/admin_quotas.css`

## Files to Modify

1. `cmd/server/main.go` - Register new routes
2. `pkg/http/handlers/handlers.go` - Add handler registration
3. `templates/dashboard.html` - Add menu item

---

**Status:** Ready for Implementation
**Complexity:** High (multiple services, UI components)
**Estimated Duration:** 3-4 weeks
**Risk:** Low (isolated features, optional monitoring)

