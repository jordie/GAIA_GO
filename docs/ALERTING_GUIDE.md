# Advanced Monitoring & Alerting Guide

Complete guide for the GAIA_GO reputation system's real-time incident detection and alerting capabilities.

## Table of Contents

1. [Overview](#overview)
2. [Alert Rules](#alert-rules)
3. [Alert States](#alert-states)
4. [Severity Levels](#severity-levels)
5. [Notification Channels](#notification-channels)
6. [API Endpoints](#api-endpoints)
7. [Usage Examples](#usage-examples)
8. [Configuration](#configuration)
9. [Troubleshooting](#troubleshooting)

## Overview

The alerting system monitors metrics in real-time and triggers notifications when thresholds are breached. It supports multiple notification channels and provides a complete audit trail of all alert events.

### Key Features

- **Real-time Monitoring**: Evaluates rules every 10 seconds (configurable)
- **Multiple Channels**: Email, Slack, PagerDuty, Webhooks
- **Severity Levels**: Critical, Warning, Info
- **Alert Management**: Resolve, silence, or acknowledge alerts
- **Event History**: Complete audit trail of all alert events
- **Thread-Safe**: Handles concurrent metric updates
- **Scalable**: Supports 100+ concurrent alert rules

## Alert Rules

An alert rule defines when to trigger an alert based on a metric condition.

### Rule Structure

```json
{
  "name": "High Error Rate",
  "description": "Alert when error rate exceeds 5%",
  "severity": "critical",
  "metric": "error_rate",
  "threshold": 0.05,
  "type": "greater_than",
  "check_interval_seconds": 60,
  "enabled": true
}
```

### Rule Properties

| Property | Description | Example |
|----------|-------------|---------|
| name | Display name for the rule | "High API Latency" |
| description | Detailed description | "Alert when p99 latency > 1s" |
| severity | critical/warning/info | "critical" |
| metric | Metric name to monitor | "appeal_latency_p99" |
| threshold | Threshold value | 1000 (milliseconds) |
| type | Condition type | "greater_than" |
| check_interval_seconds | Evaluation frequency | 60 |
| enabled | Is rule active | true |

### Condition Types

**greater_than**
```
Alert when: metric_value > threshold
Example: error_rate > 0.05
```

**less_than**
```
Alert when: metric_value < threshold
Example: uptime < 0.999
```

**equals**
```
Alert when: metric_value == threshold
Example: appeal_status == "critical"
```

**percentage_change**
```
Alert when: metric changes by X%
Example: latency increases 50% in 5 minutes
```

## Alert States

Alerts progress through different states as conditions change.

### State Transitions

```
Triggered (Rule condition met)
    ↓
Active (Alert is firing)
    ├→ Resolved (Condition no longer met)
    ├→ Silenced (Manually suppressed)
    └→ Re-fired (Condition persists)

Resolved (Alert ended)
    ↓
History (Archived)
```

### State Descriptions

| State | Description | Duration |
|-------|-------------|----------|
| **Triggered** | Condition first met | Instant |
| **Active** | Currently alerting | Until resolved/silenced |
| **Resolved** | Condition no longer met | Immediate |
| **Silenced** | Notifications suppressed | User-defined (1h - 7d) |

## Severity Levels

Alerts have three severity levels determining response urgency.

### Severity Definitions

| Level | Description | Response Time | Example |
|-------|-------------|---------------|---------|
| **Critical** | Immediate action required | < 5 minutes | API down, data loss |
| **Warning** | Should be addressed soon | 15 - 30 minutes | High latency, degraded |
| **Info** | For information/monitoring | No action | Quota approaching |

### Alert Examples

**Critical Alerts:**
- Error rate > 5%
- API response time (p99) > 2 seconds
- Database connections exhausted
- System disk space < 5%
- Appeal submission failures > 10%

**Warning Alerts:**
- Error rate > 1%
- API response time (p95) > 500ms
- Appeal processing slow > 10%
- Memory usage > 80%
- Database size growing rapidly

**Info Alerts:**
- Appeal quota > 80% used
- Daily reports generated
- Maintenance window starting
- New deployment completed

## Notification Channels

Alerts can be sent to multiple destinations simultaneously.

### Supported Channels

#### Email

```json
{
  "type": "email",
  "config": {
    "recipients": "ops-team@example.com",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": "587"
  }
}
```

#### Slack

```json
{
  "type": "slack",
  "config": {
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    "channel": "#alerts",
    "username": "ReputationBot"
  }
}
```

#### PagerDuty

```json
{
  "type": "pagerduty",
  "config": {
    "integration_key": "YOUR_INTEGRATION_KEY",
    "severity_mapping": "critical->critical,warning->warning"
  }
}
```

#### Webhook

```json
{
  "type": "webhook",
  "config": {
    "url": "https://example.com/alerts",
    "method": "POST",
    "auth_header": "Bearer TOKEN"
  }
}
```

## API Endpoints

Complete REST API for alert management.

### Alert Status Endpoints

#### Get Alert Statistics

```
GET /api/admin/alerts/stats
```

Returns overall alert statistics.

**Response:**
```json
{
  "total_alerts": 45,
  "active_alerts": 3,
  "critical": 1,
  "warning": 2,
  "info": 0,
  "total_events": 1250,
  "registered_rules": 25,
  "notification_chans": 4
}
```

#### Get Active Alerts

```
GET /api/admin/alerts/active
```

Returns all currently active alerts.

**Response:**
```json
{
  "alerts": [
    {
      "id": "alert_1234567890",
      "rule_id": "rule_high_error_rate",
      "severity": "critical",
      "title": "High Error Rate",
      "current_value": 0.08,
      "threshold_value": 0.05,
      "triggered_at": "2024-02-27T10:30:00Z",
      "fired_count": 5,
      "affected_metric": "error_rate"
    }
  ],
  "count": 1
}
```

#### Get Alerts by Severity

```
GET /api/admin/alerts/by-severity/{severity}
```

Get alerts of specific severity (critical, warning, info).

#### Get Alert History

```
GET /api/admin/alerts/history?limit=100
```

Returns recent alert events in reverse chronological order.

**Response:**
```json
{
  "events": [
    {
      "id": "event_123456",
      "alert_id": "alert_1234567890",
      "event_type": "triggered",
      "severity": "critical",
      "value": 0.08,
      "threshold": 0.05,
      "message": "triggered: High Error Rate (0.08 / 0.05)",
      "timestamp": "2024-02-27T10:30:00Z"
    }
  ],
  "count": 1
}
```

### Alert Management Endpoints

#### Resolve Alert

```
POST /api/admin/alerts/resolve/{id}
```

Manually resolve an active alert.

**Response:**
```json
{
  "success": true
}
```

#### Silence Alert

```
POST /api/admin/alerts/silence/{id}
```

Suppress alert notifications for specified duration.

**Request:**
```json
{
  "duration_minutes": 60
}
```

**Response:**
```json
{
  "success": true
}
```

### Alert Rules Endpoints

#### List Alert Rules

```
GET /api/admin/alerts/rules
```

Returns all defined alert rules.

#### Create Alert Rule

```
POST /api/admin/alerts/rules
```

Create a new alert rule.

**Request:**
```json
{
  "name": "High Appeal Volume",
  "description": "Alert when appeal submission rate is high",
  "severity": "warning",
  "metric": "appeal_submission_rate",
  "threshold": 100,
  "type": "greater_than",
  "check_interval_seconds": 30,
  "enabled": true
}
```

#### Update Alert Rule

```
PUT /api/admin/alerts/rules/{id}
```

Update existing rule configuration.

#### Delete Alert Rule

```
DELETE /api/admin/alerts/rules/{id}
```

Remove an alert rule.

### Notification Channels Endpoints

#### List Channels

```
GET /api/admin/alerts/channels
```

Returns configured notification channels.

#### Create Channel

```
POST /api/admin/alerts/channels
```

Add a new notification channel.

**Request:**
```json
{
  "type": "slack",
  "config": {
    "webhook_url": "https://hooks.slack.com/...",
    "channel": "#alerts"
  },
  "enabled": true
}
```

#### Update Channel

```
PUT /api/admin/alerts/channels/{id}
```

Modify channel configuration.

#### Delete Channel

```
DELETE /api/admin/alerts/channels/{id}
```

Remove notification channel.

### Metrics Endpoint

#### Update Metric

```
POST /api/admin/alerts/metrics/{name}
```

Push metric update to trigger rule evaluation.

**Request:**
```json
{
  "value": 0.045
}
```

## Usage Examples

### Create Alert Rule

```bash
curl -X POST http://localhost:8080/api/admin/alerts/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High API Latency",
    "description": "Alert when p99 latency > 1 second",
    "severity": "critical",
    "metric": "api_latency_p99",
    "threshold": 1000,
    "type": "greater_than",
    "check_interval_seconds": 30,
    "enabled": true
  }'
```

### Register Slack Channel

```bash
curl -X POST http://localhost:8080/api/admin/alerts/channels \
  -H "Content-Type: application/json" \
  -d '{
    "type": "slack",
    "config": {
      "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
      "channel": "#reputation-alerts"
    },
    "enabled": true
  }'
```

### Update Metric

```bash
curl -X POST http://localhost:8080/api/admin/alerts/metrics/error_rate \
  -H "Content-Type: application/json" \
  -d '{
    "value": 0.032
  }'
```

### Resolve Alert

```bash
curl -X POST http://localhost:8080/api/admin/alerts/resolve/alert_1234567890
```

### Silence Alert for 2 hours

```bash
curl -X POST http://localhost:8080/api/admin/alerts/silence/alert_1234567890 \
  -H "Content-Type: application/json" \
  -d '{
    "duration_minutes": 120
  }'
```

## Configuration

### Alert Rule Configuration

```yaml
# Example alerting configuration
rules:
  - name: "High Error Rate"
    metric: "error_rate"
    severity: critical
    threshold: 0.05
    type: "greater_than"
    check_interval: 60s
    enabled: true

  - name: "High Latency"
    metric: "api_latency_p99"
    severity: warning
    threshold: 1000
    type: "greater_than"
    check_interval: 30s
    enabled: true

  - name: "Low Uptime"
    metric: "system_uptime"
    severity: critical
    threshold: 0.999
    type: "less_than"
    check_interval: 300s
    enabled: true

notification_channels:
  - id: "slack"
    type: "slack"
    webhook_url: "${SLACK_WEBHOOK_URL}"
    enabled: true

  - id: "email"
    type: "email"
    recipients: "ops-team@example.com"
    enabled: true

  - id: "pagerduty"
    type: "pagerduty"
    integration_key: "${PAGERDUTY_KEY}"
    enabled: true
```

## Troubleshooting

### Alerts Not Triggering

**Check:**
1. Is the rule enabled? `GET /api/admin/alerts/rules`
2. Are metrics being updated? `POST /api/admin/alerts/metrics/{name}`
3. Are thresholds correct?
4. Check metric value: Higher/lower than threshold?

**Solution:**
```bash
# Verify metrics are being pushed
curl -X POST http://localhost:8080/api/admin/alerts/metrics/test_metric \
  -d '{"value": 100}'

# Check active alerts
curl http://localhost:8080/api/admin/alerts/active
```

### Notifications Not Sending

**Check:**
1. Is channel enabled? `GET /api/admin/alerts/channels`
2. Are credentials correct?
3. Are alerts being triggered?
4. Check channel configuration

**Solution:**
- Verify Slack webhook URL is accessible
- Test email SMTP connectivity
- Check PagerDuty API key validity
- Verify webhook endpoint is responsive

### Alert Flooding

**Solution:**
1. Silence alert: `POST /api/admin/alerts/silence/{id}`
2. Adjust check interval
3. Adjust threshold value
4. Disable rule temporarily

### Performance Issues

**If alerts are slow:**
1. Reduce number of active rules
2. Increase check interval
3. Profile metric update latency
4. Check notification delivery delays

## Best Practices

### Alert Design

✅ **DO:**
- Set realistic thresholds based on historical data
- Use different severity levels appropriately
- Document why each alert exists
- Test alerts before enabling
- Set up multiple notification channels

❌ **DON'T:**
- Create too many alert rules (100+ becomes unwieldy)
- Set thresholds too aggressively (causes alert fatigue)
- Ignore resolved alerts without investigation
- Keep spam notifications enabled
- Mix unrelated metrics in single rule

### Notification Management

✅ **DO:**
- Route critical alerts to on-call engineers
- Use severity levels for routing
- Send summaries during low-alert periods
- Archive old alerts for analysis
- Test notifications regularly

### Operational Excellence

- Regularly review alert rules (weekly)
- Tune thresholds based on incidents
- Document alert runbooks
- Test escalation procedures
- Track alert effectiveness

## Performance Targets

| Operation | Latency | Throughput |
|-----------|---------|-----------|
| Rule Evaluation | < 1ms | N/A |
| Metric Update | < 100µs | > 1000/sec |
| Alert Retrieval | < 10ms | N/A |
| Channel Notification | < 100ms | > 100/sec |

## Related Documentation

- [Admin Dashboard Guide](ADMIN_DASHBOARD_GUIDE.md)
- [Operations Guide](OPERATIONS_GUIDE.md)
- [Monitoring Configuration](../config/reputation_monitoring.yml)

## Support

For alerting issues:
1. Check `GET /api/admin/alerts/stats`
2. Review alert history: `GET /api/admin/alerts/history`
3. Check rule configuration: `GET /api/admin/alerts/rules`
4. Verify channels: `GET /api/admin/alerts/channels`
5. Contact operations team
