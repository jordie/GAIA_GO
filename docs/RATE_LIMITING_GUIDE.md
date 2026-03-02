# Rate Limiting & Resource Monitoring Guide

Complete guide for GAIA_GO's rate limiting system with database persistence, auto-throttling, and comprehensive quota management.

## Table of Contents

1. [Overview](#overview)
2. [Rate Limiting Scopes](#rate-limiting-scopes)
3. [Limit Types](#limit-types)
4. [Rule Configuration](#rule-configuration)
5. [Quota Management](#quota-management)
6. [API Endpoints](#api-endpoints)
7. [Usage Examples](#usage-examples)
8. [Performance Targets](#performance-targets)
9. [Troubleshooting](#troubleshooting)

## Overview

The GAIA_GO rate limiting system provides:

- **Database-Backed Persistence**: Survive service restarts, historical analysis
- **Flexible Scoping**: IP-based, user-based, API key-based, or custom scopes
- **Multiple Limit Types**: Per-second, per-minute, per-hour, daily, weekly, monthly
- **Quota Management**: Track and enforce resource quotas per period
- **Violation Tracking**: Complete audit trail of rate limit violations
- **Auto-Throttling**: Automatically reduce request rates under high system load
- **Reputation Integration**: Adjust limits based on user behavior and reputation
- **Rule Caching**: In-memory rule cache with configurable TTL for performance
- **Granular Control**: Priority-based rule evaluation, scope matching, resource type filtering

### Key Features

- **Real-time Evaluation**: Check limits in < 5ms (p99)
- **Sliding Window Algorithm**: Accurate per-second/minute/hour limits
- **Quota Periods**: Support for daily, weekly, and monthly quotas
- **System Load Awareness**: Auto-throttle during high CPU/memory usage
- **User Reputation Integration**: Higher limits for trusted users
- **Violation History**: Track and analyze abuse patterns
- **Automatic Cleanup**: Background jobs clean old data
- **Thread-Safe**: Safe for concurrent requests

## Rate Limiting Scopes

Rate limits can be applied at different scopes:

### IP-Based Limiting

Limits per source IP address.

```
Scope: "ip"
ScopeValue: "192.168.1.100"
```

**Use Cases:**
- Global API throttling
- DDoS protection
- Anonymous user limits

### User-Based Limiting

Limits per authenticated user.

```
Scope: "user"
ScopeValue: "user_123"
```

**Use Cases:**
- Per-user API quotas
- API key consumption tracking
- Fair usage enforcement

### API Key Limiting

Limits per API key or service account.

```
Scope: "api_key"
ScopeValue: "sk_live_abc123xyz"
```

**Use Cases:**
- Third-party API quotas
- Service-to-service rate limiting
- Partner API management

### Email-Based Limiting

Limits per email address (for signup, password reset, etc.).

```
Scope: "email"
ScopeValue: "user@example.com"
```

**Use Cases:**
- Signup/login attempt limiting
- Email sending quotas
- Account recovery limiting

## Limit Types

### Sliding Window Limits

**Per-Second** (`LimitPerSecond`)
```json
{
  "limit_type": "requests_per_second",
  "limit_value": 100
}
```

**Per-Minute** (`LimitPerMinute`)
```json
{
  "limit_type": "requests_per_minute",
  "limit_value": 1000
}
```

**Per-Hour** (`LimitPerHour`)
```json
{
  "limit_type": "requests_per_hour",
  "limit_value": 10000
}
```

### Quota-Based Limits

**Daily Quota** (`LimitPerDay`)
```json
{
  "limit_type": "daily_quota",
  "limit_value": 5000
}
```

**Weekly Quota** (`LimitPerWeek`)
```json
{
  "limit_type": "weekly_quota",
  "limit_value": 50000
}
```

**Monthly Quota** (`LimitPerMonth`)
```json
{
  "limit_type": "monthly_quota",
  "limit_value": 100000
}
```

## Rule Configuration

### Rule Structure

```json
{
  "system_id": "global",
  "scope": "ip",
  "scope_value": null,
  "limit_type": "requests_per_minute",
  "limit_value": 1000,
  "resource_type": null,
  "priority": 1,
  "enabled": true
}
```

### Rule Properties

| Property | Description | Example |
|----------|-------------|---------|
| `system_id` | System identifier | "global", "api-v1", "search" |
| `scope` | Limiting scope | "ip", "user", "api_key", "email" |
| `scope_value` | Specific scope value | "192.168.1.1", "user_123" |
| `limit_type` | Type of limit | "requests_per_minute", "daily_quota" |
| `limit_value` | Limit amount | 1000, 5000 |
| `resource_type` | Optional resource filter | "login", "upload", "search", "api" |
| `priority` | Evaluation order (lower = first) | 1, 10 |
| `enabled` | Is rule active | true/false |

### Rule Precedence

Rules are evaluated in priority order (lower priority = evaluated first). The first matching rule that denies the request causes the request to be blocked.

Example rule set:

```json
[
  {
    "priority": 1,
    "scope": "ip",
    "limit_type": "requests_per_minute",
    "limit_value": 100
  },
  {
    "priority": 2,
    "scope": "user",
    "resource_type": "upload",
    "limit_type": "daily_quota",
    "limit_value": 1000
  },
  {
    "priority": 3,
    "scope": "user",
    "limit_type": "requests_per_minute",
    "limit_value": 10000
  }
]
```

## Quota Management

### Quota Periods

Quotas automatically reset at the period boundary:

- **Daily**: Resets at midnight UTC
- **Weekly**: Resets at Sunday midnight UTC
- **Monthly**: Resets on the 1st at midnight UTC

### Quota Tracking

```
Current Usage: 450 / 5000 (daily quota)
Remaining: 4550
Resets: 2025-02-28 00:00:00 UTC
```

### Quota Endpoints

**Get Current Quota:**
```bash
GET /api/admin/rate-limiting/quotas/:system/:scope/:value
```

**Increment Quota Usage:**
```bash
POST /api/admin/rate-limiting/quotas/:system/:scope/:value/increment
Content-Type: application/json

{
  "amount": 100,
  "resource_type": "api_call"
}
```

## API Endpoints

### Statistics & Monitoring

#### Get Rate Limiting Statistics
```
GET /api/admin/rate-limiting/stats?system=global&days=7
```

**Response:**
```json
{
  "system": "global",
  "days_analyzed": 7,
  "timestamp": "2025-02-27T12:00:00Z",
  "total_rules": 15,
  "enabled_rules": 13,
  "total_violations": 342
}
```

#### Get Rate Limit Usage
```
GET /api/admin/rate-limiting/usage/:system/:scope/:value
```

**Response:**
```json
{
  "current": 450,
  "limit": 1000,
  "remaining": 550,
  "reset_time": "2025-02-27T14:00:00Z"
}
```

#### Get Violations
```
GET /api/admin/rate-limiting/violations/:system?hours=24
```

**Response:**
```json
{
  "violations": [
    {
      "id": 1,
      "scope": "ip",
      "scope_value": "192.168.1.100",
      "violated_limit": 1000,
      "violation_time": "2025-02-27T11:30:00Z",
      "blocked": true
    }
  ],
  "count": 5,
  "hours": 24
}
```

#### Get Violation Statistics
```
GET /api/admin/rate-limiting/violations/:system/stats
```

**Response:**
```json
{
  "total_violations": 342,
  "by_scope": {
    "ip": 280,
    "user": 45,
    "api_key": 17
  },
  "by_resource_type": {
    "upload": 120,
    "login": 85,
    "api": 137
  }
}
```

### Rule Management

#### List Rules for System
```
GET /api/admin/rate-limiting/rules/:system
```

#### Create Rule
```
POST /api/admin/rate-limiting/rules
Content-Type: application/json

{
  "system_id": "global",
  "scope": "ip",
  "limit_type": "requests_per_minute",
  "limit_value": 1000,
  "priority": 1,
  "enabled": true
}
```

#### Update Rule
```
PUT /api/admin/rate-limiting/rules/:id
Content-Type: application/json

{
  "limit_value": 2000,
  "priority": 2,
  "enabled": true
}
```

#### Delete Rule
```
DELETE /api/admin/rate-limiting/rules/:id
```

### System Management

#### Cleanup Old Buckets
```
POST /api/admin/rate-limiting/cleanup/buckets?days=7
```

Removes sliding window buckets older than specified days.

#### Cleanup Old Violations
```
POST /api/admin/rate-limiting/cleanup/violations?days=30
```

Removes violation records older than specified days.

#### Cleanup Old Metrics
```
POST /api/admin/rate-limiting/cleanup/metrics?days=90
```

Removes metric records older than specified days.

#### Health Check
```
GET /api/admin/rate-limiting/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "rate-limiting",
  "version": "1.0",
  "timestamp": "2025-02-27T12:00:00Z"
}
```

## Usage Examples

### Configure Global IP Rate Limiting

```bash
# Allow 1000 requests per minute per IP
curl -X POST http://localhost:8080/api/admin/rate-limiting/rules \
  -H "Content-Type: application/json" \
  -d '{
    "system_id": "global",
    "scope": "ip",
    "limit_type": "requests_per_minute",
    "limit_value": 1000,
    "priority": 1,
    "enabled": true
  }'
```

### Configure Per-User Upload Quota

```bash
# 100 uploads per day per user
curl -X POST http://localhost:8080/api/admin/rate-limiting/rules \
  -H "Content-Type: application/json" \
  -d '{
    "system_id": "api-v1",
    "scope": "user",
    "resource_type": "upload",
    "limit_type": "daily_quota",
    "limit_value": 100,
    "priority": 2,
    "enabled": true
  }'
```

### Configure Strict Login Attempt Limiting

```bash
# 5 failed login attempts per hour per email
curl -X POST http://localhost:8080/api/admin/rate-limiting/rules \
  -H "Content-Type: application/json" \
  -d '{
    "system_id": "auth",
    "scope": "email",
    "resource_type": "login",
    "limit_type": "requests_per_hour",
    "limit_value": 5,
    "priority": 1,
    "enabled": true
  }'
```

### Check Current Usage

```bash
curl http://localhost:8080/api/admin/rate-limiting/usage/global/ip/192.168.1.100
```

### Get Recent Violations

```bash
curl http://localhost:8080/api/admin/rate-limiting/violations/global?hours=24
```

### Update a Rule

```bash
curl -X PUT http://localhost:8080/api/admin/rate-limiting/rules/1 \
  -H "Content-Type: application/json" \
  -d '{
    "limit_value": 2000,
    "enabled": true
  }'
```

## Performance Targets

| Operation | Latency (p99) | Throughput |
|-----------|---------------|-----------|
| CheckLimit | < 5ms | > 10,000 req/s |
| GetUsage | < 10ms | N/A |
| GetRules | < 1ms (cached) | N/A |
| CreateRule | < 50ms | N/A |
| Query Violations | < 100ms | N/A |
| Cleanup | < 1s | N/A |

### Caching Strategy

- **Rule Cache**: 5-minute TTL (configurable)
- **In-Memory Buckets**: Dropped on cleanup cycles
- **Database Indexes**: On (scope, resource_type, timestamp)

## Troubleshooting

### Rate Limits Not Being Enforced

**Check:**
1. Is the rule enabled? `GET /api/admin/rate-limiting/rules/global`
2. Is the rule priority correct?
3. Does the scope and scope_value match?
4. Check system logs for errors

**Solution:**
```bash
# List all rules
curl http://localhost:8080/api/admin/rate-limiting/rules/global

# Check a specific usage
curl http://localhost:8080/api/admin/rate-limiting/usage/global/ip/YOUR_IP

# Check violations
curl http://localhost:8080/api/admin/rate-limiting/violations/global?hours=1
```

### False Positives (Legitimate Requests Blocked)

**Causes:**
- Threshold too low
- Scope too broad
- Resource type filtering incorrect

**Solution:**
1. Increase limit_value
2. Change scope to be more specific
3. Add resource_type filter
4. Adjust priority/precedence

### High System Load Not Triggering Throttling

**Check:**
1. Auto-throttle feature enabled?
2. CPU/memory thresholds configured?
3. Resource monitor running?

**Solution:**
- Check resource monitor logs
- Verify threshold configuration
- Monitor system resources with `top` or `htop`

### Cleanup Task Not Running

**Check:**
1. Background cleanup goroutine running?
2. Database connection healthy?
3. Disk space available?

**Solution:**
```bash
# Manual cleanup old buckets
curl -X POST http://localhost:8080/api/admin/rate-limiting/cleanup/buckets?days=7

# Manual cleanup old violations
curl -X POST http://localhost:8080/api/admin/rate-limiting/cleanup/violations?days=30

# Check database size
du -sh /path/to/database.db
```

## Best Practices

### Rule Design

✅ **DO:**
- Start with conservative limits and adjust based on data
- Use priority to ensure important rules are checked first
- Document why each rule exists
- Test rules in staging before production
- Monitor violation rates regularly

❌ **DON'T:**
- Create too many rules (> 50 becomes hard to maintain)
- Set limits too low (causes customer complaints)
- Mix unrelated scopes in single rule
- Forget to enable/disable rules as needed

### Quota Management

✅ **DO:**
- Set realistic daily/monthly quotas based on usage patterns
- Use resource_type to be specific
- Track quota usage in dashboards
- Notify users approaching limits
- Provide quota increase options

❌ **DON'T:**
- Share quotas across different user types
- Set quotas without historical data
- Ignore quota overflow events

### System Health

- Monitor rate limit violations rate
- Track rule evaluation latency
- Check database cleanup job success
- Monitor for quota exhaustion
- Review auto-throttle events

## Related Documentation

- [Advanced Monitoring & Alerting Guide](ALERTING_GUIDE.md)
- [Admin Dashboard Guide](ADMIN_DASHBOARD_GUIDE.md)
- [Operations Guide](OPERATIONS_GUIDE.md)

## Support

For rate limiting issues:
1. Check rule configuration: `GET /api/admin/rate-limiting/rules/:system`
2. Review recent violations: `GET /api/admin/rate-limiting/violations/:system`
3. Monitor system health: `GET /api/admin/rate-limiting/health`
4. Check database logs for errors
5. Contact operations team
