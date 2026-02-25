# Production Deployment Guide

## Overview

This guide covers the production deployment of Architect Dashboard API v3.2.0 with high availability, monitoring, and incident response procedures.

## Production Architecture

```
┌─────────────────────────────────────────────────────┐
│  Global Load Balancer (Multi-Region)                │
│  ├─ SSL/TLS Termination                             │
│  ├─ Health Checks                                   │
│  └─ Geographic Routing                              │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
    ┌─────────┐         ┌─────────┐
    │ US-EAST │         │ EU-WEST │
    │ Region  │         │ Region  │
    └────┬────┘         └────┬────┘
         │                   │
    ┌────▼────────────┐ ┌────▼────────────┐
    │ Load Balancer   │ │ Load Balancer   │
    │ (10+ instances) │ │ (10+ instances) │
    └────┬────────────┘ └────┬────────────┘
         │                   │
    ┌────┴────────────┐ ┌────┴────────────┐
    │ Primary DB      │ │ Primary DB      │
    │ + Replicas (5)  │ │ + Replicas (5)  │
    └────────────────┘ └────────────────┘
         │                   │
    ┌────▼────────────┐ ┌────▼────────────┐
    │ Redis Cluster   │ │ Redis Cluster   │
    │ (5+ nodes)      │ │ (5+ nodes)      │
    └────────────────┘ └────────────────┘
```

## Pre-Production Requirements

### Approval Sign-Offs

All stakeholders must approve before production deployment:

```
✓ CTO/VP Engineering - Strategic approval
✓ Engineering Lead - Code quality assurance
✓ DevOps Lead - Infrastructure readiness
✓ Security Lead - Security compliance
✓ Product Lead - Feature/business requirements
✓ Head of Support - Support readiness
```

### Staging Validation

- [ ] All smoke tests passing in staging
- [ ] Load tests meeting performance targets
- [ ] 24-hour soak test completed
- [ ] All security scans passed
- [ ] Database migration tested with production-like data volume
- [ ] Disaster recovery procedures tested
- [ ] Rollback procedures verified

## Production Deployment Strategies

### 1. Blue-Green Deployment (Recommended)

Two identical production environments:

```
Current (Blue): v3.2.0 (Production Traffic)
↓ (Router/LB points to Blue)
New (Green): v3.2.0 (Staged)
↓
1. Deploy to Green
2. Run tests on Green
3. Switch router to Green
4. Monitor
5. Keep Blue as rollback target
```

**Advantages:**
- Instant rollback (switch router back)
- Zero downtime
- Easy to test before switching
- Safe to keep previous version

**Disadvantages:**
- Requires double infrastructure
- Database migration complexity
- Synchronization needed

### 2. Canary Deployment

Gradually shift traffic to new version:

```
v3.2.0 (New) - 5% traffic ─┐
                            ├─→ Load Balancer
v3.2.0 (Current) - 95% traffic ─┘

Monitor errors, latency, resource usage
↓
v3.2.0 (New) - 25% traffic
v3.2.0 (Current) - 75% traffic
↓
v3.2.0 (New) - 100% traffic
```

**Advantages:**
- Real-world validation
- Gradual traffic shift
- Easy to detect issues
- Minimal blast radius

**Disadvantages:**
- Slower rollout
- Complex monitoring needed
- Database compatibility required

### 3. Rolling Deployment

Update instances one at a time:

```
Pod 1: v3.2.0 (New)
Pod 2: v3.2.0 (Current)
Pod 3: v3.2.0 (Current)
...Pod 10: v3.2.0 (Current)
↓
Pod 1: v3.2.0 (New)
Pod 2: v3.2.0 (New)
Pod 3: v3.2.0 (Current)
...Pod 10: v3.2.0 (Current)
```

**Advantages:**
- No double infrastructure
- Gradual resource scaling
- Easy to understand

**Disadvantages:**
- Slower rollout
- Temporary version mix
- Complex if DB schema changes

## Blue-Green Deployment Steps

### 1. Pre-Deployment (1 hour before)

```bash
# Create deployment checklist document
cat > /tmp/deployment_log_$(date +%s).txt << EOF
Production Deployment: Architect Dashboard API v3.2.0
Start Time: $(date -Iseconds)
Environment: us-east-1 (Primary), eu-west-1 (Secondary)
Strategy: Blue-Green
Approved By: [Names]
EOF

# Verify all systems ready
./scripts/pre_deployment_checks.sh

# Create database backup
./scripts/backup_production_db.sh

# Notify team on Slack
curl -X POST $SLACK_WEBHOOK \
  -d '{"text":"Production deployment starting in 1 hour - v3.2.0"}'
```

### 2. Build & Prepare Green Environment (30 mins)

```bash
# Build and tag Docker image
docker build -t prod-registry/architect-api:3.2.0 \
  --label version=3.2.0 \
  --label deployment_date=$(date -Iseconds) \
  .

# Push to production registry
docker push prod-registry/architect-api:3.2.0

# Verify image
docker inspect prod-registry/architect-api:3.2.0

# Deploy to Green environment
kubectl set image deployment/architect-api-green \
  architect-api=prod-registry/architect-api:3.2.0 \
  -n architect-production

# Monitor Green deployment
kubectl rollout status deployment/architect-api-green \
  -n architect-production --timeout=10m
```

### 3. Health Checks on Green (15 mins)

```bash
# Get Green service IP
GREEN_IP=$(kubectl get svc architect-api-green \
  -n architect-production -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Run smoke tests
./scripts/smoke_tests.sh https://$GREEN_IP/api

# Run synthetic monitoring
./scripts/synthetic_tests.sh https://$GREEN_IP/api

# Check metrics
curl http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=up{job="architect-api-green"}'
```

### 4. Database Migration (5 mins)

```bash
# Run pending migrations on production database
kubectl exec -it deployment/architect-api-green \
  -n architect-production -- \
  ./architect-api migrate --direction up

# Verify migration
kubectl exec -it deployment/architect-api-green \
  -n architect-production -- \
  ./architect-api migrate status
```

### 5. Switch Traffic (1 min)

```bash
# Update service selector to point to Green
kubectl patch service architect-api \
  -n architect-production \
  -p '{"spec":{"selector":{"deployment":"architect-api-green"}}}'

# Verify switch
kubectl get svc architect-api -n architect-production -o yaml | grep -A2 selector
```

### 6. Monitor & Validate (30 mins)

```bash
# Monitor key metrics
watch -n 5 'kubectl get pods -n architect-production'

# Check error rates
curl http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=rate(http_requests_total{status=~"5.."}[5m])'

# Check latency
curl http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=histogram_quantile(0.95,http_request_duration_seconds)'

# Review logs
kubectl logs -f deployment/architect-api-green \
  -n architect-production --tail=100
```

### 7. Rollback (if needed)

```bash
# Immediate rollback: switch back to Blue
kubectl patch service architect-api \
  -n architect-production \
  -p '{"spec":{"selector":{"deployment":"architect-api-blue"}}}'

# Restore database from backup
./scripts/restore_production_db.sh backup_pre_v320.sql

# Notify team
curl -X POST $SLACK_WEBHOOK \
  -d '{"text":"⚠️ Production rollback completed - v3.2.0 deployment reverted"}'
```

## Production Monitoring

### Key Metrics (SLIs)

Monitor these metrics continuously:

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| **Latency (P95)** | < 100ms | > 150ms | > 300ms |
| **Latency (P99)** | < 300ms | > 500ms | > 1000ms |
| **Error Rate** | < 0.01% | > 0.05% | > 0.1% |
| **CPU Usage** | 40-60% | > 70% | > 85% |
| **Memory Usage** | 50-70% | > 80% | > 90% |
| **Disk I/O Wait** | < 5% | > 10% | > 20% |
| **Database Connections** | 50-70% | > 80% | > 90% |
| **Cache Hit Ratio** | > 95% | < 90% | < 85% |
| **QPS** | Baseline | ±50% | ±100% |

### Prometheus Queries

```promql
# Request rate
rate(http_requests_total[5m])

# Error rate
rate(http_requests_total{status=~"5.."}[5m])

# Latency percentiles
histogram_quantile(0.95, http_request_duration_seconds)
histogram_quantile(0.99, http_request_duration_seconds)

# Database connection pool
pg_stat_activity_count / pg_settings_max_connections

# Cache hit ratio
rate(redis_keyspace_hits_total[5m]) / (rate(redis_keyspace_hits_total[5m]) + rate(redis_keyspace_misses_total[5m]))
```

### Alert Rules

```yaml
groups:
- name: production_alerts
  rules:

  # Critical: High error rate
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.001
    for: 2m
    labels:
      severity: critical
      team: oncall
    annotations:
      summary: "High error rate: {{ $value | humanizePercentage }}"
      runbook: "https://wiki.example.com/runbooks/high_error_rate"

  # Critical: API unresponsive
  - alert: APIUnresponsive
    expr: up{job="architect-api"} == 0
    for: 1m
    labels:
      severity: critical
      team: oncall
    annotations:
      summary: "API instances down"

  # Warning: High latency
  - alert: HighLatency
    expr: histogram_quantile(0.95, http_request_duration_seconds) > 0.3
    for: 5m
    labels:
      severity: warning
      team: oncall
    annotations:
      summary: "P95 latency high: {{ $value }}s"

  # Warning: High CPU usage
  - alert: HighCPU
    expr: rate(container_cpu_usage_seconds_total[5m]) > 0.85
    for: 5m
    labels:
      severity: warning
      team: oncall
    annotations:
      summary: "CPU usage high: {{ $value | humanizePercentage }}"

  # Critical: Database down
  - alert: DatabaseDown
    expr: pg_up == 0
    for: 1m
    labels:
      severity: critical
      team: oncall
    annotations:
      summary: "PostgreSQL instance down"

  # Warning: Replication lag
  - alert: ReplicationLag
    expr: pg_replication_lag_seconds > 30
    for: 5m
    labels:
      severity: warning
      team: oncall
    annotations:
      summary: "Database replication lag: {{ $value }}s"

  # Critical: Out of disk space
  - alert: DiskSpaceRunningOut
    expr: node_filesystem_avail_bytes / node_filesystem_size_bytes < 0.1
    for: 5m
    labels:
      severity: critical
      team: oncall
    annotations:
      summary: "Disk space critical on {{ $labels.instance }}"
```

## Service Level Objectives (SLOs)

### Availability SLO

**Target: 99.95% uptime** (down time budget: 22 minutes/month)

```
Measurement: (Successful requests) / (Total requests) × 100%

Definition:
- Successful: HTTP 2xx, 3xx, 404
- Failed: HTTP 5xx, timeouts, connection errors

Alert if: 4-hour rolling window < 99.9%
Critical if: 1-hour rolling window < 99%
```

### Latency SLO

**Target: P95 < 100ms** (95% of requests complete in < 100ms)

```
Measurement: 95th percentile of request duration

Alert if: P95 > 200ms for 10 minutes
Critical if: P95 > 500ms for 5 minutes
```

### Error Budget

Monthly error budget: 0.05% (2.16 hours)

```
Used when:
- Planned maintenance
- Emergency patches
- Testing in production
- Canary deployments

Track and report monthly
Reserve for unexpected incidents
```

## Production Runbooks

### Runbook: High Error Rate

**Trigger**: Error rate > 0.1% for 2 minutes

**Steps**:

1. **Acknowledge Alert**
   ```bash
   # PagerDuty / alert acknowledgment
   ```

2. **Assess Severity**
   ```bash
   # Check error rate
   curl http://prometheus:9090/api/v1/query \
     --data-urlencode 'query=rate(http_requests_total{status=~"5.."}[5m])'

   # Check affected endpoints
   curl http://prometheus:9090/api/v1/query \
     --data-urlencode 'query=topk(5,rate(http_requests_total{status=~"5.."}[5m]))'
   ```

3. **Check Recent Changes**
   ```bash
   # View recent deployments
   kubectl rollout history deployment/architect-api -n architect-production

   # Check pod events
   kubectl get events -n architect-production --sort-by='.lastTimestamp' | tail -20
   ```

4. **Check Logs**
   ```bash
   # Stream logs from all pods
   kubectl logs -f deployment/architect-api -n architect-production --all-containers=true

   # Search for errors
   kubectl logs deployment/architect-api -n architect-production | grep ERROR | head -50
   ```

5. **Check Metrics**
   ```bash
   # Database connection pool
   curl http://prometheus:9090/api/v1/query \
     --data-urlencode 'query=pg_stat_activity_count'

   # Cache hit ratio
   curl http://prometheus:9090/api/v1/query \
     --data-urlencode 'query=redis_keyspace_hits_total'
   ```

6. **Potential Fixes**
   - Restart pods: `kubectl rollout restart deployment/architect-api -n architect-production`
   - Scale up: `kubectl scale deployment architect-api --replicas=15 -n architect-production`
   - Rollback: `kubectl rollout undo deployment/architect-api -n architect-production`

### Runbook: High Latency

**Trigger**: P95 latency > 300ms for 5 minutes

**Steps**:

1. **Check Database Performance**
   ```bash
   # Connect to database
   psql $PRODUCTION_DB_URL

   # Find slow queries
   SELECT query, mean_time, calls
   FROM pg_stat_statements
   ORDER BY mean_time DESC LIMIT 10;

   # Check active queries
   SELECT pid, usename, query, query_start
   FROM pg_stat_activity
   WHERE state = 'active';
   ```

2. **Check Cache Performance**
   ```bash
   # Redis info
   redis-cli INFO stats

   # Check memory usage
   redis-cli INFO memory
   ```

3. **Scale Resources**
   ```bash
   # Increase replicas
   kubectl scale deployment architect-api --replicas=20 -n architect-production

   # Monitor for improvement
   watch -n 5 'kubectl top pods -n architect-production'
   ```

### Runbook: Pod Crashes

**Trigger**: Pods repeatedly restarting

**Steps**:

1. **Check Pod Status**
   ```bash
   kubectl describe pod <pod-name> -n architect-production
   ```

2. **View Logs**
   ```bash
   kubectl logs <pod-name> -n architect-production --previous
   ```

3. **Check Resource Limits**
   ```bash
   kubectl describe deployment architect-api -n architect-production | grep -A 5 "Limits"
   ```

4. **Recovery**
   - Increase resource limits
   - Rollback deployment
   - Check for OOM (out of memory) errors

## Production Checklist

- [ ] Database backups running every 1 hour
- [ ] Replication lag < 30 seconds
- [ ] All metrics being collected (Prometheus)
- [ ] Grafana dashboards showing live data
- [ ] Alerting rules configured and tested
- [ ] PagerDuty integration active
- [ ] On-call schedule published
- [ ] Runbooks accessible to all team members
- [ ] SSL certificates valid (expires > 30 days)
- [ ] WAF (Web Application Firewall) rules updated
- [ ] CDN cache rules configured
- [ ] DNS TTL appropriate (300-3600s)
- [ ] Rate limiting per user configured
- [ ] DDoS protection enabled
- [ ] Security group rules reviewed
- [ ] VPC flow logs enabled
- [ ] CloudTrail (or equivalent) logging enabled
- [ ] No hardcoded secrets visible
- [ ] Configuration encrypted at rest
- [ ] Access logs being collected
- [ ] Performance logs being collected
- [ ] Error tracking (Sentry/New Relic) configured
- [ ] Distributed tracing (Jaeger) enabled
- [ ] Synthetic monitoring configured
- [ ] Status page updated

## Post-Deployment

**First Hour (Critical Monitoring)**
- [ ] Monitor error rate every 2 minutes
- [ ] Monitor latency every 2 minutes
- [ ] Check for any exceptions in logs
- [ ] Verify all endpoints responding
- [ ] Confirm database migrations applied

**First 4 Hours (Active Monitoring)**
- [ ] Continue monitoring all key metrics
- [ ] Check for resource exhaustion
- [ ] Verify external integrations working
- [ ] Test critical user workflows
- [ ] Monitor customer feedback channels

**First 24 Hours (Extended Monitoring)**
- [ ] Daily monitoring of all systems
- [ ] Review application logs for errors
- [ ] Check backup completion
- [ ] Verify replication status
- [ ] Monitor cost and resource usage

**First Week (Validation Period)**
- [ ] Weekly review of metrics
- [ ] Compare with baseline performance
- [ ] Identify any performance regressions
- [ ] Gather user feedback
- [ ] Schedule retrospective

## Incident Response

### Incident Severity Levels

| Level | Impact | Response Time | Example |
|-------|--------|--------------|---------|
| **P1 - Critical** | Service down | 5 minutes | API completely unavailable |
| **P2 - High** | Degraded service | 15 minutes | 50% error rate, high latency |
| **P3 - Medium** | Limited impact | 1 hour | Specific endpoint slow |
| **P4 - Low** | Minor issue | 4 hours | Non-critical feature affected |

### Incident Response Procedure

1. **Detect** → Alert fires in PagerDuty
2. **Acknowledge** → Engineer acknowledges within SLA
3. **Assess** → Determine severity and impact
4. **Communicate** → Notify stakeholders
5. **Remediate** → Implement fix or rollback
6. **Verify** → Confirm service restored
7. **Document** → Create incident report
8. **Review** → Schedule postmortem

### War Room Setup

```bash
# Declare Slack #incidents channel as war room
@incident-commander: Incident #1234 - High Error Rate
Severity: P1
Status: INVESTIGATING
Lead: @john

Real-time updates below...
```

## Rollback Procedures

### Blue-Green Rollback

Immediate (30 seconds):
```bash
# Switch traffic back to Blue
kubectl patch service architect-api \
  -n architect-production \
  -p '{"spec":{"selector":{"deployment":"architect-api-blue"}}}'
```

### Database Rollback

If migration caused issues:
```bash
# Rollback database
./scripts/restore_production_db.sh backup_pre_v320.sql

# Verify schema
psql $DATABASE_URL -c "\dt"
```

### Full Rollback

Complete rollback to previous version:
```bash
# Rollback deployment
kubectl rollout undo deployment/architect-api \
  -n architect-production \
  --to-revision=<previous_revision>

# Verify rollback
kubectl rollout status deployment/architect-api \
  -n architect-production
```

---

**Next Steps**: Continuous monitoring, performance optimization, and feature development based on production insights.
