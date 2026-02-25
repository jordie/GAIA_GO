# Monitoring & Observability Guide

This guide covers monitoring architect-go in production.

## Table of Contents

1. [Prometheus Setup](#prometheus-setup)
2. [Grafana Dashboards](#grafana-dashboards)
3. [Alerting](#alerting)
4. [Logging](#logging)
5. [Tracing](#tracing)
6. [Key Metrics](#key-metrics)
7. [Dashboards](#dashboards)

## Prometheus Setup

### Docker Compose

```yaml
# docker-compose.yml
prometheus:
  image: prom/prometheus:latest
  ports:
    - "9090:9090"
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
    - prometheus_data:/prometheus
  command:
    - '--config.file=/etc/prometheus/prometheus.yml'
    - '--storage.tsdb.path=/prometheus'
```

### Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']

scrape_configs:
  - job_name: 'architect-go'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: '/metrics'
    scrape_interval: 5s
```

### Query Examples

```promql
# Request rate (requests per second)
rate(architect_requests_total[5m])

# Error rate
rate(architect_errors_total[5m]) / rate(architect_requests_total[5m])

# Average latency
avg(architect_latency_ms)

# Cache hit rate
avg(architect_cache_hit_rate)

# Active connections
architect_active_connections

# p99 latency
histogram_quantile(0.99, architect_latency_ms)
```

## Grafana Dashboards

### Setup Grafana

```bash
# Docker
docker run -d -p 3000:3000 grafana/grafana:latest

# Access at http://localhost:3000
# Default: admin/admin
```

### Add Prometheus Data Source

1. Go to Configuration > Data Sources
2. Click "Add data source"
3. Select Prometheus
4. URL: http://prometheus:9090
5. Save & Test

### Create Dashboard

**Dashboard JSON**
```json
{
  "dashboard": {
    "title": "Architect-Go",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "rate(architect_requests_total[5m])"
          }
        ]
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(architect_errors_total[5m])"
          }
        ]
      },
      {
        "title": "Latency (p99)",
        "targets": [
          {
            "expr": "histogram_quantile(0.99, architect_latency_ms)"
          }
        ]
      },
      {
        "title": "Cache Hit Rate",
        "targets": [
          {
            "expr": "avg(architect_cache_hit_rate)"
          }
        ]
      },
      {
        "title": "Active Connections",
        "targets": [
          {
            "expr": "architect_active_connections"
          }
        ]
      }
    ]
  }
}
```

## Alerting

### Alert Rules

```yaml
# rules.yml
groups:
  - name: architect-go
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(architect_errors_total[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }}"

      - alert: HighLatency
        expr: histogram_quantile(0.99, architect_latency_ms) > 500
        for: 5m
        annotations:
          summary: "High latency detected"
          description: "p99 latency is {{ $value }}ms"

      - alert: LowCacheHitRate
        expr: avg(architect_cache_hit_rate) < 50
        for: 10m
        annotations:
          summary: "Low cache hit rate"
          description: "Cache hit rate is {{ $value }}%"

      - alert: HighMemoryUsage
        expr: process_resident_memory_bytes > 500000000
        for: 5m
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value }} bytes"

      - alert: DatabaseConnectionPoolExhausted
        expr: architect_active_connections > 90
        for: 2m
        annotations:
          summary: "Database connection pool near capacity"
          description: "Active connections: {{ $value }}/100"
```

### AlertManager Configuration

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  receiver: 'default'
  group_by: ['alertname', 'cluster']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty'
    - match:
        severity: warning
      receiver: 'slack'

receivers:
  - name: 'default'
    email_configs:
      - to: 'ops@example.com'
        from: 'alerts@example.com'
        smarthost: 'smtp.example.com:587'

  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: '<your-pagerduty-key>'

  - name: 'slack'
    slack_configs:
      - api_url: '<your-slack-webhook>'
        channel: '#alerts'
```

## Logging

### Structured Logging

Architecture uses structured JSON logging:

```json
{
  "timestamp": "2026-02-18T12:34:56Z",
  "level": "info",
  "trace_id": "abc123",
  "message": "Request received",
  "endpoint": "/api/users",
  "method": "GET",
  "status": 200,
  "latency_ms": 45
}
```

### Log Aggregation

**ELK Stack**
```bash
# Start ELK with Docker Compose
docker-compose -f docker-compose.elk.yml up

# Access Kibana: http://localhost:5601
```

**Log Parsing**
```json
{
  "elasticsearch": {
    "hosts": ["localhost:9200"]
  },
  "logstash": {
    "config": "/etc/logstash/conf.d/*.conf"
  }
}
```

## Tracing

### Distributed Tracing

Using OpenTelemetry and Jaeger:

```bash
# Start Jaeger
docker run -d \
  -p 6831:6831/udp \
  -p 16686:16686 \
  jaegertracing/all-in-one

# Access: http://localhost:16686
```

### Request Tracing

Each request includes trace ID header:

```
X-Trace-ID: abc-123-def-456
X-Span-ID: span-001
```

## Key Metrics

### Application Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `architect_requests_total` | Counter | Total HTTP requests |
| `architect_errors_total` | Counter | Total errors |
| `architect_latency_ms` | Gauge | Request latency |
| `architect_cache_hit_rate` | Gauge | Cache hit percentage (0-100) |
| `architect_cache_size` | Gauge | Cache size in bytes |
| `architect_active_connections` | Gauge | Active database connections |

### System Metrics

| Metric | Description |
|--------|-------------|
| `process_resident_memory_bytes` | Memory usage |
| `process_cpu_seconds_total` | CPU time |
| `process_open_fds` | Open file descriptors |
| `go_goroutines` | Active goroutines |
| `go_gc_duration_seconds` | GC duration |

### Business Metrics

| Metric | Description |
|--------|-------------|
| `users_created_total` | Total users created |
| `projects_created_total` | Total projects created |
| `tasks_completed_total` | Total tasks completed |

## Dashboards

### System Health Dashboard

Key panels:
- CPU usage
- Memory usage
- Goroutines count
- GC frequency

### Application Performance Dashboard

Key panels:
- Request rate (RPS)
- Error rate
- Latency (p50, p95, p99)
- Endpoint performance

### Database Dashboard

Key panels:
- Connection pool status
- Query latency
- Slow query count
- Connection errors

### Cache Dashboard

Key panels:
- Cache hit rate
- Cache size
- Cache eviction rate
- Cache operations

### Error Dashboard

Key panels:
- Error rate by endpoint
- Error types distribution
- Error trends
- Critical errors alert

## SLOs & SLIs

### Service Level Objectives (SLOs)

| Objective | Target | Measurement |
|-----------|--------|-------------|
| Availability | 99.9% | Uptime |
| Latency (p99) | <100ms | Response time |
| Error Rate | <0.1% | Failed requests |
| Cache Hit Rate | >80% | Cache effectiveness |

### Service Level Indicators (SLIs)

Measure against SLOs:

```promql
# Availability SLI
(1 - (rate(architect_errors_total[30d]) / rate(architect_requests_total[30d]))) * 100

# Latency SLI
histogram_quantile(0.99, architect_latency_ms) < 100

# Error Rate SLI
(rate(architect_errors_total[5m]) / rate(architect_requests_total[5m])) < 0.001

# Cache Hit Rate SLI
avg(architect_cache_hit_rate) > 80
```

## Runbooks

### High Error Rate

1. Check error logs
2. Review recent deployments
3. Check database connectivity
4. Monitor memory/CPU
5. Rollback if necessary

### High Latency

1. Check database query performance
2. Review cache hit rate
3. Check connection pool status
4. Monitor CPU/memory
5. Check external service latency

### Database Connection Pool Exhausted

1. Increase pool size (gradually)
2. Review long-running queries
3. Monitor connection leaks
4. Scale horizontally if needed

### Cache Not Working

1. Verify cache is enabled
2. Check cache size
3. Monitor cache eviction rate
4. Review TTL settings

## Tools & Commands

```bash
# View metrics in real-time
curl http://localhost:8080/metrics

# Query Prometheus
curl 'http://localhost:9090/api/v1/query?query=architect_requests_total'

# Test alerting
curl -X POST http://localhost:9093/api/v1/alerts

# Check pod metrics (Kubernetes)
kubectl top pods
kubectl top nodes
```

## Contacts & Escalation

- On-call: Slack #on-call
- Critical: PagerDuty integration
- Deployment: #deployments channel
