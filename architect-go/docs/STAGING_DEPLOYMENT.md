# Staging Deployment Guide

## Overview

This guide covers deploying the Architect Dashboard API to staging for pre-production validation, smoke testing, and load testing before production rollout.

## Pre-Deployment Checklist

Before deploying to staging, ensure:

- [ ] All code reviewed and merged to main branch
- [ ] Unit tests passing (100% of test suite)
- [ ] Integration tests passing
- [ ] Load tests completed and performance acceptable
- [ ] Security review completed
- [ ] Documentation generated and current
- [ ] Database migrations tested locally
- [ ] Environment variables configured
- [ ] SSL certificates prepared
- [ ] Monitoring and alerting configured
- [ ] Backup procedures tested
- [ ] Rollback procedures documented
- [ ] Team communication plan established

## Deployment Environment

### Staging Infrastructure

```
┌─────────────────────────────────────────┐
│  Staging Environment                    │
├─────────────────────────────────────────┤
│  Load Balancer (HTTPS)                  │
│  ├─ SSL Certificate                     │
│  └─ Health Check: /health               │
├─────────────────────────────────────────┤
│  API Instances (3x for redundancy)      │
│  ├─ Instance 1 (10.0.1.10)             │
│  ├─ Instance 2 (10.0.1.11)             │
│  └─ Instance 3 (10.0.1.12)             │
├─────────────────────────────────────────┤
│  PostgreSQL Database                    │
│  ├─ Primary (10.0.2.10)                │
│  ├─ Replica (10.0.2.11) - Read-only    │
│  └─ Backups: 24-hour retention         │
├─────────────────────────────────────────┤
│  Redis Cache                            │
│  ├─ Cluster (3 nodes)                  │
│  └─ AOF persistence enabled             │
├─────────────────────────────────────────┤
│  Monitoring                             │
│  ├─ Prometheus metrics                  │
│  ├─ Grafana dashboards                  │
│  └─ ELK stack logging                   │
└─────────────────────────────────────────┘
```

### Staging vs Production

| Aspect | Staging | Production |
|--------|---------|------------|
| **Scale** | 3 instances | 10+ instances |
| **Database** | Single replica | Multi-region replicas |
| **Cache** | 3-node cluster | 5+ node cluster |
| **Monitoring** | Basic metrics | Advanced + alerts |
| **Uptime SLA** | Best effort | 99.99% |
| **Data** | Test data | Real data |
| **Access** | Internal only | Public or restricted |

## Step-by-Step Deployment

### 1. Build and Test

```bash
# Clone and setup
git clone https://github.com/architect-team/architect-go.git
cd architect-go
git checkout main

# Run all tests
go test ./... -v -cover

# Build release binary
go build -o architect-api ./cmd/architect

# Verify binary
./architect-api --version
```

### 2. Database Migrations

```bash
# Connect to staging database
export DATABASE_URL="postgres://user:pass@staging-db.internal:5432/architect_staging?sslmode=require"

# Run migrations
./architect-api migrate --direction up

# Verify migration status
./architect-api migrate status

# Create database backups before migration
./architect-api backup create --name "pre-deployment-$(date +%s)"
```

### 3. Configuration

Create `.env.staging`:

```bash
# Server Configuration
HOST=0.0.0.0
PORT=8080
ENV=staging
DEBUG=false

# Database
DATABASE_URL=postgres://user:pass@staging-db.internal:5432/architect_staging?sslmode=require
DATABASE_MAX_CONNS=100
DATABASE_IDLE_CONNS=10

# Redis Cache
REDIS_URL=redis://staging-redis.internal:6379
REDIS_DB=0
CACHE_TTL=3600

# Security
JWT_SECRET=<use-secrets-manager>
ENCRYPTION_KEY=<use-secrets-manager>
SESSION_TIMEOUT=3600
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true

# Monitoring
PROMETHEUS_ENABLED=true
JAEGER_ENABLED=true
JAEGER_ENDPOINT=http://staging-jaeger.internal:14268/api/traces

# Logging
LOG_LEVEL=info
LOG_FORMAT=json

# Email (for notifications)
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=<use-secrets-manager>
SMTP_PASSWORD=<use-secrets-manager>

# Integrations
SLACK_WEBHOOK_URL=<use-secrets-manager>
GITHUB_TOKEN=<use-secrets-manager>

# Feature Flags
FEATURE_WEBHOOKS_ENABLED=true
FEATURE_INTEGRATIONS_ENABLED=true
FEATURE_AUTOPILOT_ENABLED=false
```

Load configuration from secrets manager:

```bash
# Using AWS Secrets Manager
aws secretsmanager get-secret-value --secret-id architect/staging/config \
  --query 'SecretString' --output text > .env.staging

# Using HashiCorp Vault
vault kv get -format=json secret/architect/staging/config | jq '.data.data' > config.json
```

### 4. Container Deployment

Build and push Docker image:

```bash
# Build Docker image
docker build -t architect-api:3.2.0 \
  -f Dockerfile \
  --build-arg VERSION=3.2.0 \
  --build-arg BUILD_TIME=$(date -Iseconds) \
  --build-arg GIT_COMMIT=$(git rev-parse HEAD) .

# Tag for staging registry
docker tag architect-api:3.2.0 \
  staging-registry.example.com/architect-api:3.2.0

# Push to container registry
docker push staging-registry.example.com/architect-api:3.2.0

# Verify push
docker run --rm staging-registry.example.com/architect-api:3.2.0 \
  ./architect-api --version
```

### 5. Kubernetes Deployment

Deploy to staging cluster:

```bash
# Switch to staging cluster
kubectl config use-context staging

# Create namespace
kubectl create namespace architect-staging

# Create secrets
kubectl create secret generic architect-secrets \
  --from-env-file=.env.staging \
  -n architect-staging

# Apply configuration
kubectl apply -f k8s/staging/ -n architect-staging

# Monitor deployment
kubectl rollout status deployment/architect-api -n architect-staging

# Check pod status
kubectl get pods -n architect-staging -w
```

**Kubernetes Manifest** (`k8s/staging/deployment.yaml`):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: architect-api
  namespace: architect-staging
  labels:
    app: architect-api
    environment: staging
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: architect-api
  template:
    metadata:
      labels:
        app: architect-api
        environment: staging
    spec:
      containers:
      - name: architect-api
        image: staging-registry.example.com/architect-api:3.2.0
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8080
          name: http
        env:
        - name: ENV
          value: staging
        envFrom:
        - secretRef:
            name: architect-secrets
        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 10
          periodSeconds: 5
          failureThreshold: 2
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        securityContext:
          runAsNonRoot: true
          readOnlyRootFilesystem: true
---
apiVersion: v1
kind: Service
metadata:
  name: architect-api
  namespace: architect-staging
spec:
  type: LoadBalancer
  ports:
  - port: 443
    targetPort: http
    protocol: TCP
    name: https
  selector:
    app: architect-api
```

### 6. Health Verification

Verify deployment health:

```bash
# Check pod status
kubectl get pods -n architect-staging

# Check logs
kubectl logs -n architect-staging -l app=architect-api --tail=100

# Test health endpoint
curl -k https://staging-api.architect.internal/health

# Expected response (200 OK):
{
  "status": "healthy",
  "timestamp": "2024-02-17T12:00:00Z",
  "components": {
    "database": "healthy",
    "cache": "healthy",
    "external_services": "healthy"
  }
}
```

## Smoke Tests

Run smoke tests to validate deployment:

```bash
# Run smoke test suite
go test -v -run TestSmoke ./testing/smoke_tests.go

# Expected output:
# === RUN   TestSmokeAuth_Login
# --- PASS: TestSmokeAuth_Login (0.45s)
# === RUN   TestSmokeEvents_Create
# --- PASS: TestSmokeEvents_Create (0.52s)
# ... (all tests should pass)
```

### Smoke Test Coverage

**Authentication**
- [ ] Login with valid credentials
- [ ] Login with invalid credentials returns 401
- [ ] Session cookie is set correctly
- [ ] Logout clears session

**Events**
- [ ] Create event
- [ ] List events with pagination
- [ ] Get specific event
- [ ] Delete event

**Errors**
- [ ] Create error (no auth required)
- [ ] List errors
- [ ] Resolve error
- [ ] Error aggregation works

**Notifications**
- [ ] Create notification
- [ ] List notifications
- [ ] Mark as read
- [ ] Delete notification

**Health**
- [ ] Health check returns 200
- [ ] All components report healthy
- [ ] Metrics endpoint responds
- [ ] Database connection works

## Load Testing

Run load tests in staging environment:

```bash
# Run load test suite
go test -v -run TestLoad ./testing/load_tests.go

# Light load test (baseline)
go test -bench=BenchmarkLight -benchmem ./testing/

# Medium load test (expected traffic)
go test -bench=BenchmarkMedium -benchmem ./testing/

# Heavy load test (spike traffic)
go test -bench=BenchmarkHeavy -benchmem ./testing/

# Sustained load test (24 hours)
./scripts/load_test_sustained.sh staging 24h
```

### Performance Targets

**Latency**
- P50: < 100ms
- P95: < 500ms
- P99: < 1000ms
- Max: < 2000ms

**Throughput**
- Minimum: 100 requests/second
- Target: 500 requests/second
- Peak capacity: 1000+ requests/second

**Error Rate**
- Target: < 0.1%
- Maximum acceptable: < 1%

**Resource Usage**
- CPU: < 70% sustained
- Memory: < 80% sustained
- Database connections: < 80% of pool

## Monitoring Setup

### Prometheus Metrics

Verify metrics collection:

```bash
# Access Prometheus
curl http://staging-prometheus.internal:9090

# Query API latency
curl 'http://staging-prometheus.internal:9090/api/v1/query?query=http_request_duration_seconds'

# Expected metrics:
# - http_requests_total
# - http_request_duration_seconds
# - database_query_duration_seconds
# - cache_hit_ratio
# - error_rate
```

### Grafana Dashboards

Import dashboards:

```bash
# Import API performance dashboard
curl -X POST http://staging-grafana.internal:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <api-token>" \
  -d @dashboards/api-performance.json

# Import system metrics dashboard
curl -X POST http://staging-grafana.internal:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <api-token>" \
  -d @dashboards/system-metrics.json

# Import error tracking dashboard
curl -X POST http://staging-grafana.internal:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <api-token>" \
  -d @dashboards/error-tracking.json
```

### Alerting Rules

Configure Prometheus alerts:

```yaml
groups:
- name: api_alerts
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.01
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High error rate detected"

  - alert: HighLatency
    expr: histogram_quantile(0.95, http_request_duration_seconds) > 0.5
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "API latency elevated"

  - alert: DatabaseDown
    expr: pg_up == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Database connection lost"

  - alert: CacheDown
    expr: redis_up == 0
    for: 1m
    labels:
      severity: warning
    annotations:
      summary: "Redis cache unavailable"
```

## Validation Checklist

After deployment, verify:

### Functionality
- [ ] All API endpoints accessible
- [ ] Authentication working correctly
- [ ] Database queries executing
- [ ] Caching functioning
- [ ] External integrations responding
- [ ] Email notifications sending
- [ ] Webhooks delivering

### Performance
- [ ] Response times within SLA
- [ ] Error rate below threshold
- [ ] Throughput meeting targets
- [ ] Resource utilization optimal
- [ ] No memory leaks
- [ ] Database performance acceptable

### Security
- [ ] HTTPS enforced
- [ ] SSL certificate valid
- [ ] Rate limiting working
- [ ] Input validation active
- [ ] SQL injection prevention verified
- [ ] XSS prevention active
- [ ] CORS properly configured

### Monitoring
- [ ] Prometheus scraping metrics
- [ ] Grafana dashboards updating
- [ ] Alerts firing correctly
- [ ] Logs being collected
- [ ] Distributed tracing working
- [ ] Error tracking functional

### Data Integrity
- [ ] Database migrations complete
- [ ] No data corruption
- [ ] Backups succeeding
- [ ] Replication lag acceptable
- [ ] Consistency checks passing

## Rollback Procedures

If issues detected:

```bash
# View deployment history
kubectl rollout history deployment/architect-api -n architect-staging

# Rollback to previous version
kubectl rollout undo deployment/architect-api -n architect-staging

# Rollback to specific revision
kubectl rollout undo deployment/architect-api -n architect-staging --to-revision=2

# Verify rollback
kubectl rollout status deployment/architect-api -n architect-staging

# Restore database from backup
./architect-api backup restore --name "pre-deployment-<timestamp>"
```

### Incident Response

If critical issues detected:

1. **Immediate Actions**
   - Invoke rollback procedure
   - Restore database from backup
   - Notify team via Slack/PagerDuty
   - Document incident timeline

2. **Investigation**
   - Collect logs and metrics
   - Review error patterns
   - Analyze database state
   - Check external dependencies

3. **Post-Incident**
   - Create incident report
   - Identify root cause
   - Plan corrective actions
   - Update runbooks
   - Schedule retrospective

## Sign-Off

Deployment requires approval from:

- [ ] Engineering Lead - Code review and testing
- [ ] DevOps Lead - Infrastructure and monitoring
- [ ] Security Lead - Security validation
- [ ] Product Lead - Feature readiness

Document sign-off:

```
Deployment Sign-Off: Architect Dashboard API v3.2.0
Date: 2024-02-17
Environment: Staging

Engineering Lead: _____________________ Date: _____
DevOps Lead: _______________________ Date: _____
Security Lead: ______________________ Date: _____
Product Lead: ______________________ Date: _____

Notes:
- All tests passing
- Performance targets met
- Security review complete
- Ready for production
```

## Troubleshooting

### Common Issues

**Pod Crash Loop**
```bash
# View pod logs
kubectl logs -n architect-staging <pod-name>

# Check resource limits
kubectl describe pod -n architect-staging <pod-name>

# Check event log
kubectl get events -n architect-staging --sort-by='.lastTimestamp'
```

**High Memory Usage**
```bash
# Check memory metrics
kubectl top pods -n architect-staging

# Profile application
go tool pprof http://localhost:6060/debug/pprof/heap

# Identify memory leaks
go tool pprof http://localhost:6060/debug/pprof/allocs
```

**Database Connection Errors**
```bash
# Test database connectivity
psql $DATABASE_URL -c "SELECT 1"

# Check connection pool stats
curl http://localhost:8080/metrics | grep database_connection

# View active connections
psql $DATABASE_URL -c "SELECT datname, usename, state FROM pg_stat_activity"
```

**High API Latency**
```bash
# Check database query performance
curl http://localhost:8080/metrics | grep query_duration_seconds

# Review slow query log
tail -f /var/log/postgresql/slow_queries.log

# Profile endpoints
go tool pprof http://localhost:6060/debug/pprof/profile
```

## Post-Deployment

After successful staging deployment:

1. **Document Findings**
   - Record performance metrics
   - Note any optimizations needed
   - Document configuration changes

2. **Team Briefing**
   - Share deployment results
   - Discuss any issues encountered
   - Plan next steps

3. **Schedule Production Deployment**
   - Set deployment window
   - Assign on-call personnel
   - Prepare communication plan
   - Plan post-deployment validation

4. **Update Runbooks**
   - Document lessons learned
   - Update deployment procedures
   - Add troubleshooting tips
   - Train team on new procedures

---

**Next Phase**: Phase 3.2.20 - Production Rollout with Monitoring
