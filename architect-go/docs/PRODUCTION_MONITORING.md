# Production Monitoring Guide

## Monitoring Stack Overview

```
┌─────────────────────────────────────┐
│  Data Collection Layer              │
│  ├─ Prometheus (metrics)            │
│  ├─ Filebeat (logs)                 │
│  ├─ Jaeger (traces)                 │
│  └─ Telegraf (system metrics)       │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Storage Layer                      │
│  ├─ Prometheus (time-series)        │
│  ├─ Elasticsearch (logs)            │
│  ├─ Jaeger (traces)                 │
│  └─ InfluxDB (metrics)              │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Visualization Layer                │
│  ├─ Grafana (dashboards)            │
│  ├─ Kibana (logs)                   │
│  └─ Jaeger UI (traces)              │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Alerting Layer                     │
│  ├─ Alertmanager (Prometheus)       │
│  ├─ PagerDuty (on-call)             │
│  └─ Slack (notifications)           │
└─────────────────────────────────────┘
```

## Key Metrics to Monitor

### Application Metrics

#### Request Metrics
```promql
# Request rate (requests per second)
rate(http_requests_total[5m])

# Request rate by endpoint
rate(http_requests_total[5m]) by (endpoint)

# Request rate by status code
rate(http_requests_total[5m]) by (status)

# Errors per second
rate(http_requests_total{status=~"5.."}[5m])

# Error percentage
(rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])) * 100
```

#### Latency Metrics
```promql
# Average latency
avg(http_request_duration_seconds_sum / http_request_duration_seconds_count)

# P50 latency
histogram_quantile(0.5, http_request_duration_seconds)

# P95 latency
histogram_quantile(0.95, http_request_duration_seconds)

# P99 latency
histogram_quantile(0.99, http_request_duration_seconds)

# Max latency
max(http_request_duration_seconds)
```

### Resource Metrics

#### CPU and Memory
```promql
# CPU usage percentage
(rate(container_cpu_usage_seconds_total[5m])) * 100

# Memory usage in MB
container_memory_usage_bytes / 1024 / 1024

# Memory percentage
(container_memory_usage_bytes / container_spec_memory_limit_bytes) * 100
```

#### Disk and I/O
```promql
# Disk usage percentage
(node_filesystem_avail_bytes / node_filesystem_size_bytes) * 100

# Disk write rate (MB/s)
rate(node_disk_written_bytes_total[5m]) / 1024 / 1024

# Disk read rate (MB/s)
rate(node_disk_read_bytes_total[5m]) / 1024 / 1024

# I/O wait percentage
rate(node_cpu_seconds_total{mode="iowait"}[5m]) * 100
```

### Database Metrics

#### Connection Pool
```promql
# Active connections
pg_stat_activity_count

# Connection usage percentage
(pg_stat_activity_count / pg_settings_max_connections) * 100

# Idle connections
pg_stat_activity_count{state="idle"}

# Waiting connections
pg_stat_activity_count{wait_event!="null"}
```

#### Query Performance
```promql
# Query execution rate
rate(pg_stat_statements_calls[5m])

# Slow query count
rate(pg_stat_statements_mean_time_milliseconds > 100[5m])

# Query time (mean)
pg_stat_statements_mean_time_milliseconds

# Lock time
pg_locks_count by (locktype)
```

#### Replication
```promql
# Replication lag (seconds)
pg_replication_lag_seconds

# Replica sync status
pg_replication_connected

# Write-ahead log size
pg_wal_lsn_bytes
```

### Cache Metrics

#### Redis Performance
```promql
# Cache hit ratio
rate(redis_keyspace_hits_total[5m]) / (rate(redis_keyspace_hits_total[5m]) + rate(redis_keyspace_misses_total[5m]))

# Keys in database
redis_db_keys

# Used memory (MB)
redis_memory_used_bytes / 1024 / 1024

# Evictions per minute
rate(redis_evicted_keys_total[1m])

# Commands per second
rate(redis_commands_total[5m])
```

## SLO/SLI Definition

### Service Level Indicators (SLIs)

| SLI | Description | Target | Measurement |
|-----|-------------|--------|-------------|
| **Availability** | % of successful requests | 99.95% | (Success / Total) × 100 |
| **Latency** | P95 request duration | < 100ms | histogram_quantile(0.95) |
| **Error Rate** | % of failed requests | < 0.01% | (Errors / Total) × 100 |
| **Saturation** | Resource utilization | 60-70% | CPU, memory, connections |

### Service Level Objectives (SLOs)

#### Availability SLO: 99.95%

```
Error Budget: 0.05% × 720 hours/month = 22 minutes/month

Calculation:
- If 4-hour rolling window < 99.9% → Alert
- If 1-hour rolling window < 99% → Critical

Window Aggregation:
- Hourly: 99%+ required
- Daily: 99.9%+ required
- Monthly: 99.95%+ target
```

**Prometheus Alert**:
```yaml
- alert: AvailabilityBudgetExhausted
  expr: |
    (
      sum(rate(http_requests_total{status!~"5.."}[1h])) /
      sum(rate(http_requests_total[1h]))
    ) * 100 < 99
  for: 5m
  labels:
    severity: critical
```

#### Latency SLO: P95 < 100ms

```
Target: 95% of requests complete in < 100ms
Alert Threshold: P95 > 150ms for 10 minutes
Critical Threshold: P95 > 300ms for 5 minutes

Percentiles to Track:
- P50: ~30ms (target)
- P95: <100ms (SLO)
- P99: <300ms (tracking)
- Max: <1000ms (monitoring)
```

**Prometheus Alert**:
```yaml
- alert: HighLatency
  expr: histogram_quantile(0.95, rate(http_request_duration_seconds[5m])) > 0.1
  for: 10m
  labels:
    severity: warning

- alert: CriticalLatency
  expr: histogram_quantile(0.95, rate(http_request_duration_seconds[5m])) > 0.3
  for: 5m
  labels:
    severity: critical
```

#### Error Rate SLO: < 0.01%

```
Target: > 99.99% success rate
Alert Threshold: > 0.05% for 5 minutes
Critical Threshold: > 0.1% for 2 minutes

Excludes:
- 404 Not Found (expected)
- 401 Unauthorized (expected)
- Client errors (4xx)

Includes:
- 500 Server Errors
- 502 Bad Gateway
- 503 Service Unavailable
- Timeouts
- Connection errors
```

**Prometheus Alert**:
```yaml
- alert: HighErrorRate
  expr: |
    (
      sum(rate(http_requests_total{status=~"5.."}[5m])) /
      sum(rate(http_requests_total[5m]))
    ) * 100 > 0.05
  for: 5m
  labels:
    severity: warning
```

## Grafana Dashboards

### Dashboard 1: Overview

Key panels:
- **Big Number**: Current QPS
- **Big Number**: Current Error Rate (%)
- **Big Number**: P95 Latency (ms)
- **Graph**: Request Rate (last 24h)
- **Graph**: Error Rate (last 24h)
- **Graph**: Latency Percentiles (last 24h)
- **Stat**: Availability (24h)
- **Stat**: Error Budget Used (month)

### Dashboard 2: Performance

Panels:
- **Graph**: Request Duration Percentiles (P50, P95, P99)
- **Graph**: Latency by Endpoint
- **Graph**: Error Rate by Endpoint
- **Graph**: Request Rate by Status Code
- **Heatmap**: Latency distribution
- **Table**: Top 10 Slowest Endpoints
- **Table**: Top 10 Error Endpoints

### Dashboard 3: Resources

Panels:
- **Graph**: CPU Usage (%)
- **Graph**: Memory Usage (MB)
- **Graph**: Disk Space (%)
- **Graph**: Network I/O (MB/s)
- **Gauge**: Pod Count
- **Table**: Pod Resource Usage
- **Alert**: Resource Limit Status

### Dashboard 4: Database

Panels:
- **Graph**: Active Connections
- **Graph**: Query Rate
- **Graph**: Query Latency
- **Graph**: Replication Lag (ms)
- **Stat**: Connection Pool Usage (%)
- **Table**: Slow Queries
- **Alert**: Database Health

### Dashboard 5: Cache

Panels:
- **Graph**: Cache Hit Ratio (%)
- **Graph**: Memory Usage (MB)
- **Graph**: Operations/sec
- **Stat**: Keys in Database
- **Table**: Top Keys by Memory
- **Alert**: Eviction Rate

## Alerting Rules

### Alert Routing

```yaml
global:
  resolve_timeout: 5m

route:
  receiver: 'default'
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h

  routes:
  # Critical alerts to PagerDuty immediately
  - match:
      severity: critical
    receiver: 'pagerduty'
    repeat_interval: 5m

  # Warnings to Slack
  - match:
      severity: warning
    receiver: 'slack'

receivers:
- name: 'default'
  slack_configs:
  - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
    channel: '#alerts'

- name: 'pagerduty'
  pagerduty_configs:
  - service_key: 'YOUR_PAGERDUTY_KEY'
    client: 'Prometheus'
    client_url: 'https://prometheus.example.com'

- name: 'slack'
  slack_configs:
  - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
    channel: '#warnings'
```

### Sample Alert Rules

```yaml
groups:
- name: api_alerts
  interval: 30s
  rules:

  # Availability alerts
  - alert: APIDown
    expr: up{job="architect-api"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "API is down"
      description: "API has been unreachable for 1 minute"

  # Latency alerts
  - alert: HighLatencyP95
    expr: histogram_quantile(0.95, rate(http_request_duration_seconds[5m])) > 0.1
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "High P95 latency: {{ $value }}s"

  # Error rate alerts
  - alert: HighErrorRate
    expr: |
      (
        sum(rate(http_requests_total{status=~"5.."}[5m])) /
        sum(rate(http_requests_total[5m]))
      ) * 100 > 0.05
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Error rate: {{ $value }}%"

  # Resource alerts
  - alert: HighCPUUsage
    expr: rate(container_cpu_usage_seconds_total[5m]) > 0.8
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High CPU: {{ $value | humanizePercentage }}"

  - alert: HighMemoryUsage
    expr: (container_memory_usage_bytes / container_spec_memory_limit_bytes) > 0.9
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High memory: {{ $value | humanizePercentage }}"

  - alert: DiskSpaceRunningOut
    expr: (node_filesystem_avail_bytes / node_filesystem_size_bytes) < 0.1
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Low disk space: {{ $value | humanizePercentage }}"

  # Database alerts
  - alert: DatabaseDown
    expr: pg_up == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "PostgreSQL is down"

  - alert: ReplicationLag
    expr: pg_replication_lag_seconds > 30
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Replication lag: {{ $value }}s"

  - alert: ConnectionPoolExhaustion
    expr: |
      (pg_stat_activity_count / pg_settings_max_connections) > 0.9
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Connection pool {{ $value | humanizePercentage }} full"

  # Cache alerts
  - alert: CacheMisses
    expr: |
      (
        rate(redis_keyspace_misses_total[5m]) /
        (rate(redis_keyspace_hits_total[5m]) + rate(redis_keyspace_misses_total[5m]))
      ) > 0.1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High cache miss rate: {{ $value | humanizePercentage }}"

  - alert: RedisDown
    expr: up{job="redis"} == 0
    for: 1m
    labels:
      severity: warning
    annotations:
      summary: "Redis is unreachable"

  # Rate limiting alerts
  - alert: HighRateLimitExceeded
    expr: rate(rate_limit_exceeded_total[5m]) > 10
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Rate limit exceeded: {{ $value }} req/s"
```

## Health Checks

### Application Health Endpoint

```bash
curl https://api.example.com/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-02-17T12:00:00Z",
  "components": {
    "database": "healthy",
    "cache": "healthy",
    "external_services": "healthy"
  },
  "uptime_seconds": 864000,
  "version": "3.2.0"
}
```

### Liveness Probe (Kubernetes)

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
    scheme: HTTPS
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

### Readiness Probe (Kubernetes)

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8080
    scheme: HTTPS
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 5
  failureThreshold: 2
```

## Logging Strategy

### Log Levels

```
DEBUG   - Detailed debugging information
INFO    - General informational messages
WARN    - Warning messages (may indicate issues)
ERROR   - Error messages (something failed)
FATAL   - Fatal errors (will cause shutdown)
```

### What to Log

**Always Log**:
- Request/response timestamps
- User ID (not email/password)
- Request path and method
- Response status code
- Execution time
- Error messages (without sensitive data)

**Never Log**:
- Passwords or API keys
- Credit card numbers
- Session tokens
- Personally identifiable information (PII)
- Database credentials

### Log Format

```json
{
  "timestamp": "2024-02-17T12:00:00Z",
  "level": "INFO",
  "service": "architect-api",
  "instance": "pod-123",
  "request_id": "req-abc-123",
  "user_id": "user-456",
  "message": "Event created",
  "path": "/api/events",
  "method": "POST",
  "status": 201,
  "latency_ms": 45,
  "fields": {
    "event_type": "user_action",
    "event_id": "event-789"
  }
}
```

## Metrics Retention

```
Prometheus:
- Real-time data: 15 days
- Downsampled (1h): 60 days
- Long-term: S3/object storage

Logs (Elasticsearch):
- Hot: 7 days
- Warm: 30 days
- Cold: 90 days
- Delete: > 365 days

Traces (Jaeger):
- Default: 72 hours
- Important: 30 days
```

## Performance Tuning

### Query Optimization

```promql
# Efficient: Range vector already exists
rate(http_requests_total[5m])

# Less efficient: Creating extra range vector
rate(http_requests_total[1m])[5m:]

# Efficient: Aggregation before processing
sum(rate(http_requests_total[5m])) by (endpoint)

# Less efficient: Processing before aggregation
sum by (endpoint) (rate(http_requests_total[5m]))
```

### Metric Cardinality Management

Keep metric cardinality low:
- Limited label values
- No unbounded labels (user_id, session_id)
- Use label limits in scrapers

Example:
```yaml
# BAD - unlimited cardinality
http_requests_total{user_id="..."}  # Many unique values!

# GOOD - limited cardinality
http_requests_total{endpoint="/api/events"}  # Few values
```

---

**Documentation**: Comprehensive monitoring setup for production readiness and operational excellence.
