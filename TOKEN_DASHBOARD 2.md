# Token Tracking Dashboard

## Overview

The token tracking dashboard provides real-time visibility into AI token usage and costs across all concurrent sessions and tasks, ensuring the system stays within budget limits.

## Features

### 1. Global Metrics Dashboard

Real-time tracking of:
- **Tokens/Hour**: Current usage vs 500K limit with progress bar
- **Tokens/Day**: Current usage vs 5M limit with progress bar
- **Cost/Hour**: Current cost vs $5.00 limit
- **Cost/Day**: Current cost vs $50.00 limit

**Color-coded progress bars:**
- 🟢 Green (< 80%): Normal operation
- 🟠 Orange (80-90%): Approaching limit
- 🔴 Red (> 90%): Near limit

### 2. Session Breakdown Table

Per-session metrics showing:
- Session ID
- Task count
- Tokens used (hour/day)
- Cost incurred (hour/day)
- Throttle level indicator

**Throttle Indicators:**
- 🟢 NONE: Normal operation
- 🟡 WARNING: 80-90% of limit
- 🟠 SOFT: 90-95% of limit
- 🔴 HARD: 95-99% of limit
- 🚨 CRITICAL: > 99% of limit

### 3. Task-Level Token Details

Detailed breakdown for recent tasks (last 24 hours):
- Task ID and type
- Session assigned
- Status (completed/running/pending/failed)
- Tokens IN (estimated)
- Tokens OUT (actual)
- Cost per task
- Model used
- Duration

## API Endpoints

### GET /api/tokens/metrics

Returns global and per-session token usage metrics.

**Response:**
```json
{
  "global": {
    "tokens_hour": 48523,
    "tokens_day": 48523,
    "cost_hour": 0.1456,
    "cost_day": 0.1456,
    "cost_month": 0.1456,
    "limits": {
      "tokens_hour": 500000,
      "tokens_day": 5000000,
      "cost_hour": 5.00,
      "cost_day": 50.00
    },
    "usage_percent": {
      "tokens_hour": 9.7,
      "tokens_day": 0.97,
      "cost_hour": 2.9,
      "cost_day": 0.29
    }
  },
  "sessions": [
    {
      "session_id": "concurrent_worker1",
      "task_count": 4,
      "total_tokens": 15234,
      "avg_tokens": 3808,
      "tokens_hour": 15234,
      "tokens_day": 15234,
      "cost_hour": 0.0457,
      "cost_day": 0.0457,
      "throttle_level": "none"
    }
  ],
  "timestamp": "2026-02-01T18:15:00.000Z"
}
```

### GET /api/tokens/tasks?limit=50

Returns token usage for recent tasks.

**Response:**
```json
{
  "tasks": [
    {
      "id": 123,
      "type": "shell",
      "session_id": "concurrent_worker1",
      "status": "completed",
      "tokens_in": 1008,
      "tokens_out": 2145,
      "cost": 0.0064,
      "model": "claude-sonnet-4-5-20250929",
      "delegated_type": "coding",
      "duration": 12.5,
      "created_at": "2026-02-01T18:00:00.000Z"
    }
  ],
  "count": 50
}
```

### GET /api/tokens/sessions/{session_id}

Returns detailed metrics for a specific session.

**Response:**
```json
{
  "session_id": "concurrent_worker1",
  "stats": {
    "tokens_hour": 15234,
    "tokens_day": 15234,
    "cost_hour": 0.0457,
    "cost_day": 0.0457,
    "throttle_level": "none"
  },
  "task_history": [
    {
      "id": 123,
      "task_type": "shell",
      "status": "completed",
      "created_at": "2026-02-01T18:00:00.000Z",
      "tokens_in": 1008,
      "tokens_out": 2145,
      "cost": 0.0064
    }
  ]
}
```

## Accessing the Dashboard

### Via Navigation Menu

1. Click **System** dropdown in top navigation
2. Navigate to **Monitoring** section
3. Click **📊 Token Tracking**

### Direct URL

```
http://localhost:8080/dashboard#tokens
```

## Auto-Refresh

The dashboard automatically refreshes every 30 seconds when visible, ensuring real-time data.

## Integration with Concurrent Task Manager

The dashboard displays metrics from:
1. **Token Throttle System** - Real-time usage tracking
2. **Task Queue** - Historical task data with token estimates
3. **Concurrent Task Manager** - Active session metrics

## Cost Calculation

**Token costs by model:**
- Claude Sonnet 4.5: $0.003 per 1K tokens
- Claude Haiku: $0.00025 per 1K tokens

**Example calculation:**
```
Task uses 2,145 tokens with Sonnet
Cost = (2145 / 1000) * $0.003 = $0.0064
```

## Throttle Integration

The dashboard shows throttle levels that directly affect task assignment:

- **🟢 NONE**: All tasks allowed
- **🟡 WARNING**: Monitoring increased
- **🟠 SOFT**: Low priority tasks queued
- **🔴 HARD**: Only high/critical tasks allowed
- **🚨 CRITICAL**: Only critical emergency tasks

## Best Practices

### 1. Monitor Regularly

Check the dashboard at least once per hour during active development to ensure you're not approaching limits.

### 2. Set Up Alerts

Configure alerts when:
- Tokens/hour reaches 80% (400K tokens)
- Cost/hour reaches 80% ($4.00)
- Any session reaches HARD throttle

### 3. Optimize Task Distribution

Use the session breakdown to identify:
- Sessions using excessive tokens
- Tasks with unusually high token counts
- Opportunities to switch to cheaper models

### 4. Budget Planning

Use the cost/day metric to project monthly costs:
```
Daily cost: $0.98
Monthly projection: $0.98 * 30 = $29.40
Well under $1,000 limit ✅
```

## Troubleshooting

### Dashboard Not Loading

1. Check API endpoint is accessible: `curl http://localhost:8080/api/tokens/metrics`
2. Verify token throttle service is running
3. Check browser console for errors

### Metrics Showing Zero

1. Ensure tasks have metadata with token estimates
2. Check that task queue is being used
3. Verify throttle system is recording usage

### Throttle Level Incorrect

1. Wait for hourly window reset
2. Check if multiple sessions are sharing a limit
3. Verify cost calculations are correct

## Future Enhancements

Planned features:
- Historical charts (tokens/cost over time)
- Budget alerts via email/Slack
- Per-project token allocation
- Model cost comparison
- Export metrics to CSV
- Predictive cost forecasting

## See Also

- [Concurrent Task Management](CONCURRENT_METRICS.md)
- [Token Throttle System](services/token_throttle.py)
- [Task Delegator](services/task_delegator.py)
