# Phase 5 Production Deployment Runbook

**Version**: 1.0
**Last Updated**: 2026-03-02
**Status**: Production Ready
**Audience**: DevOps Engineers, Site Reliability Engineers, On-Call Engineers

---

## Table of Contents

1. [Overview](#overview)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Deployment Procedures](#deployment-procedures)
4. [Monitoring Checkpoints](#monitoring-checkpoints)
5. [Rollback Procedures](#rollback-procedures)
6. [Troubleshooting Guide](#troubleshooting-guide)
7. [Escalation Paths](#escalation-paths)
8. [Post-Deployment Actions](#post-deployment-actions)
9. [Quick Reference](#quick-reference)

---

## Overview

This runbook covers the production deployment of Phase 5 (Rate Limiting Infrastructure) for GAIA_GO using a **blue-green deployment strategy with canary testing**.

### Deployment Goals

- **Zero Downtime**: No service interruption during deployment
- **Risk Mitigation**: Gradual traffic shift (10% → 50% → 100%)
- **Automated Testing**: Comprehensive smoke tests before each phase
- **Easy Rollback**: Instant rollback capability at any phase
- **Full Observability**: Real-time monitoring throughout deployment

### Key Features

- Phase 5 Rate Limiting Infrastructure
- Reputation System Integration
- Appeal & Appeal Negotiation Services
- Distributed Rate Limiting (supports multiple nodes)
- Analytics & Alerting
- Data-driven Testing Framework

### Deployment Duration

| Phase | Duration | Activity |
|-------|----------|----------|
| Pre-Deployment | 30 mins | Checklist, backup, health checks |
| Green Deployment | 15 mins | Deploy, smoke tests |
| Canary 10% | 15 mins | 10% traffic, monitor |
| Canary 50% | 10 mins | 50% traffic, monitor |
| Full Cutover | 5 mins | 100% traffic switch |
| Blue Cleanup | 15 mins | Scale down, prepare cleanup |
| Monitoring | 24 hours | Extended monitoring, health checks |

**Total Active Time**: ~90 minutes
**Total With Monitoring**: 24 hours

---

## Pre-Deployment Checklist

### 1. Access & Permissions

- [ ] Access to Kubernetes cluster (kubectl configured)
- [ ] Access to Docker registry (ghcr.io credentials)
- [ ] Access to production database (for backup/restore)
- [ ] SSH access to production servers
- [ ] Grafana/Prometheus access for monitoring
- [ ] PagerDuty/Alerting access for incident management

### 2. Code & Release Readiness

```bash
# Verify release tag exists and is ready
git tag | grep phase5

# Check all tests passing
go test -v ./pkg/services/rate_limiting 2>&1 | grep "PASS\|FAIL"

# Verify code is in main branch
git log -1 --oneline
git branch -a | grep "\*"
```

**Checklist**:
- [ ] All 65+ tests passing
- [ ] Code reviewed and approved
- [ ] Deployment documentation reviewed
- [ ] Release v0.5.0-phase5 (or latest) built and pushed
- [ ] Docker image verified in registry

### 3. Infrastructure Prerequisites

```bash
# Verify cluster connectivity
kubectl cluster-info

# Verify namespace exists
kubectl get namespace production

# Verify deployments exist
kubectl get deployments -n production | grep gaia-go

# Verify service configuration
kubectl get service gaia-go -n production

# Verify persistent storage (if used)
kubectl get pvc -n production
```

**Checklist**:
- [ ] Kubernetes cluster accessible
- [ ] Production namespace exists
- [ ] Blue & green deployments ready
- [ ] Service load balancer configured
- [ ] Persistent volumes mounted (if applicable)
- [ ] Network policies correct (ingress/egress)

### 4. Database Readiness

```bash
# Verify database connectivity from blue deployment
BLUE_POD=$(kubectl get pods -n production -l app=gaia-go,version=blue -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n production $BLUE_POD -- curl -s http://localhost:8080/api/health/database

# Verify all migrations applied
kubectl exec -n production $BLUE_POD -- curl -s http://localhost:8080/api/health/migrations

# Create pre-deployment backup
pg_dump -U postgres -h $DB_HOST gaia_go > /backups/gaia_go_pre_deploy_$(date +%Y%m%d_%H%M%S).sql
```

**Checklist**:
- [ ] Database online and healthy
- [ ] Backup system operational
- [ ] All migrations applied to current version
- [ ] Connection pool limits appropriate
- [ ] Disk space sufficient (>50% free)
- [ ] Pre-deployment backup completed

### 5. Monitoring & Alerting

```bash
# Verify Prometheus is scraping metrics
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets | length'

# Verify Grafana dashboards exist
curl -s http://localhost:3000/api/dashboards | jq '.dashboards | length'

# Test alerting (optional)
amtool silence add -d 1h "test alert"
```

**Checklist**:
- [ ] Prometheus collecting metrics
- [ ] Grafana dashboards prepared (phase5_dashboard.json imported)
- [ ] Alert rules configured and active
- [ ] On-call engineer on standby
- [ ] Escalation path documented
- [ ] Incident channel ready (#gaia-incidents)

### 6. Security & Compliance

```bash
# Verify SSL/TLS certificates
kubectl get certificates -n production

# Verify service accounts/RBAC
kubectl get serviceaccount gaia-go -n production
kubectl get rolebinding -n production | grep gaia-go

# Verify network policies
kubectl get networkpolicy -n production
```

**Checklist**:
- [ ] SSL/TLS certificates valid (not expiring in < 30 days)
- [ ] RBAC policies correct
- [ ] Network policies in place
- [ ] Secrets management configured
- [ ] No hardcoded credentials in code

### 7. Communication & Notification

**Checklist**:
- [ ] Status page updated (if applicable)
- [ ] Team notified of deployment window
- [ ] On-call engineer informed
- [ ] Escalation contacts confirmed
- [ ] Customer notification (if applicable) scheduled
- [ ] Deployment log being captured

### Pre-Deployment Sign-Off

```bash
# Run pre-deployment validation script
./scripts/pre_deployment_validation.sh

# Expected output:
# ✓ All prerequisites verified
# ✓ Ready to proceed with deployment
```

---

## Deployment Procedures

### Quick Start (Default Deployment)

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO

# Execute deployment script
./deployment/phase5_production_deploy.sh v0.5.0-phase5

# Follow script output for progress
# Script handles all phases automatically
```

### Manual Step-by-Step Deployment

#### Phase 1: Pre-Deployment Setup (30 mins)

**Step 1.1: Set Environment Variables**

```bash
export NAMESPACE="production"
export APP_NAME="gaia-go"
export IMAGE_TAG="v0.5.0-phase5"
export DOCKER_REGISTRY="ghcr.io/jordie"
export BACKUP_DIR="/backups"

echo "Deployment Configuration:"
echo "  Namespace: $NAMESPACE"
echo "  App: $APP_NAME"
echo "  Image: $DOCKER_REGISTRY/$APP_NAME:$IMAGE_TAG"
```

**Step 1.2: Pre-Deployment Health Checks**

```bash
# Check blue deployment is healthy
BLUE_POD=$(kubectl get pods -n $NAMESPACE -l app=$APP_NAME,version=blue \
  -o jsonpath='{.items[0].metadata.name}')

echo "Blue Pod: $BLUE_POD"

kubectl exec -n $NAMESPACE $BLUE_POD -- curl -s http://localhost:8080/health
# Expected: {"status":"ok"} or similar

# Check green deployment is running
GREEN_POD=$(kubectl get pods -n $NAMESPACE -l app=$APP_NAME,version=green \
  -o jsonpath='{.items[0].metadata.name}')

echo "Green Pod: $GREEN_POD"
```

**Step 1.3: Create Database Backup**

```bash
# Get database credentials from secrets
DB_USER=$(kubectl get secret -n $NAMESPACE postgres-creds -o jsonpath='{.data.username}' | base64 -d)
DB_PASS=$(kubectl get secret -n $NAMESPACE postgres-creds -o jsonpath='{.data.password}' | base64 -d)
DB_HOST=$(kubectl get secret -n $NAMESPACE postgres-creds -o jsonpath='{.data.host}' | base64 -d)

# Create backup
BACKUP_FILE="$BACKUP_DIR/gaia_go_$(date +%Y%m%d_%H%M%S).sql"
PGPASSWORD=$DB_PASS pg_dump -U $DB_USER -h $DB_HOST gaia_go > $BACKUP_FILE

echo "Backup created: $BACKUP_FILE"
ls -lh $BACKUP_FILE
```

#### Phase 2: Green Deployment (15 mins)

**Step 2.1: Update Green Deployment**

```bash
# Set new image on green deployment
kubectl set image deployment/$APP_NAME-green \
  $APP_NAME=$DOCKER_REGISTRY/$APP_NAME:$IMAGE_TAG \
  -n $NAMESPACE \
  --record

echo "Green deployment image updated"
```

**Step 2.2: Wait for Rollout**

```bash
# Wait for green pods to be ready (max 5 minutes)
kubectl rollout status deployment/$APP_NAME-green \
  -n $NAMESPACE \
  --timeout=300s

# Expected: "deployment 'gaia-go-green' successfully rolled out"
```

**Step 2.3: Verify Green Deployment Health**

```bash
# Get green pod
GREEN_POD=$(kubectl get pods -n $NAMESPACE -l app=$APP_NAME,version=green \
  -o jsonpath='{.items[0].metadata.name}')

# Check health endpoint
kubectl exec -n $NAMESPACE $GREEN_POD -- curl -s http://localhost:8080/health

# Check metrics
kubectl exec -n $NAMESPACE $GREEN_POD -- curl -s http://localhost:8080/metrics | head -20
```

#### Phase 3: Smoke Testing (15 mins)

**Step 3.1: Run Smoke Tests**

```bash
# Port-forward to green service for testing
kubectl port-forward -n $NAMESPACE svc/$APP_NAME-green 8080:8080 &

# Wait for port forward to establish
sleep 3

# Run smoke tests
./scripts/phase5_smoke_tests.sh localhost:8080

# Expected: "✅ All Phase 5 smoke tests passed"

# Kill port forward
pkill -f "port-forward"
```

**Step 3.2: Review Test Output**

```bash
# Smoke test results logged to /tmp/phase5_smoke_tests_*.log
ls -la /tmp/phase5_smoke_tests_*.log | tail -1

# Review results
tail -100 /tmp/phase5_smoke_tests_*.log | tail -1
```

#### Phase 4: Canary Release - 10% Traffic (15 mins)

**Step 4.1: Shift 10% Traffic to Green**

```bash
# Method A: Update service selector with traffic split annotation
kubectl annotate service $APP_NAME -n $NAMESPACE \
  "traffic.split=90% blue,10% green" \
  --overwrite

# Verify annotation
kubectl get service $APP_NAME -n $NAMESPACE -o jsonpath='{.metadata.annotations.traffic\.split}'
```

**Step 4.2: Monitor During Canary**

```bash
# Check error logs (should be minimal)
kubectl logs -n $NAMESPACE -l app=$APP_NAME,version=green --tail=50 --all-containers

# Watch metrics in Grafana
# Dashboard: http://localhost:3000/d/phase5-production

# Monitor for errors over 15 minutes
watch -n 5 'kubectl get pods -n production -l app=gaia-go,version=green'

# Check p95 latency
kubectl exec -n $NAMESPACE $GREEN_POD -- curl -s http://localhost:8080/metrics | grep latency

# Check error rate
kubectl exec -n $NAMESPACE $GREEN_POD -- curl -s http://localhost:8080/metrics | grep error_rate
```

**Step 4.3: Decide Continue or Rollback**

```bash
# If errors > 20 or error rate > 5%: ROLLBACK
# If all metrics healthy: Continue to 50%

echo "✓ 10% canary phase completed successfully"
```

#### Phase 5: Canary Release - 50% Traffic (10 mins)

**Step 5.1: Shift 50% Traffic to Green**

```bash
kubectl annotate service $APP_NAME -n $NAMESPACE \
  "traffic.split=50% blue,50% green" \
  --overwrite

echo "Traffic split 50/50 blue/green"
```

**Step 5.2: Monitor During Canary**

```bash
# Monitor metrics
watch -n 5 'kubectl get pods -n production'

# Check database performance
kubectl logs -n $NAMESPACE -l app=$APP_NAME,version=green | grep "database\|connection"

# Verify rate limiting is working
kubectl exec -n $NAMESPACE $GREEN_POD -- curl -s http://localhost:8080/api/check-limit/test
```

**Step 5.3: Proceed or Rollback**

```bash
# If all metrics healthy: Proceed to 100%
# Otherwise: Rollback to blue

echo "✓ 50% canary phase completed successfully"
```

#### Phase 6: Full Traffic Cutover (5 mins)

**Step 6.1: Switch to Green Only**

```bash
# Update service to select only green pods
kubectl patch service $APP_NAME -n $NAMESPACE \
  --type merge \
  -p '{"spec":{"selector":{"version":"green"}}}'

echo "✓ Traffic fully switched to green deployment"
```

**Step 6.2: Verify Traffic Switch**

```bash
# Check service endpoints
kubectl get endpoints $APP_NAME -n $NAMESPACE

# Verify green pods are receiving traffic
kubectl logs -n $NAMESPACE -l app=$APP_NAME,version=green --tail=20
```

#### Phase 7: Blue Cleanup (15 mins)

**Step 7.1: Scale Down Blue**

```bash
# Keep blue at 1 replica for rollback option
kubectl scale deployment/$APP_NAME-blue --replicas=1 -n $NAMESPACE

echo "Blue deployment scaled to 1 replica"
echo "⚠️  Keep blue running for 24 hours as rollback option"
```

**Step 7.2: Verify Green Stability**

```bash
# Wait 10 minutes and verify no new errors
sleep 600

# Check error logs
kubectl logs -n $NAMESPACE -l app=$APP_NAME,version=green --tail=100 | grep -i error || echo "No errors found"

# Verify all metrics are healthy
kubectl exec -n $NAMESPACE $GREEN_POD -- curl -s http://localhost:8080/metrics | grep "error_rate\|latency"
```

---

## Monitoring Checkpoints

### Real-Time Monitoring

#### Dashboard Access

```bash
# Forward Grafana port (if not exposed)
kubectl port-forward -n monitoring svc/grafana 3000:3000 &

# Access dashboard
open http://localhost:3000/d/phase5-production
# Username: admin
# Password: (from secrets)
```

#### Key Metrics to Monitor

| Metric | Healthy Range | Alert Threshold |
|--------|---------------|-----------------|
| Request Rate | 1K-10K req/s | < 500 or > 50K |
| HTTP 5xx Rate | < 0.1% | > 5% |
| p95 Latency | < 100ms | > 500ms |
| p99 Latency | < 500ms | > 1000ms |
| Rate Limit Violations | Normal for workload | Spike > 2x baseline |
| Memory Usage | < 512MB | > 1GB |
| CPU Usage | < 50% | > 80% |
| Database Latency | < 10ms | > 50ms |

#### Manual Metric Checks

```bash
# Check request rate
kubectl exec -n $NAMESPACE $GREEN_POD -- curl -s http://localhost:8080/metrics | grep http_requests_total

# Check error rate
kubectl exec -n $NAMESPACE $GREEN_POD -- curl -s http://localhost:8080/metrics | grep "code=\"5"

# Check latency
kubectl exec -n $NAMESPACE $GREEN_POD -- curl -s http://localhost:8080/metrics | grep http_request_duration

# Check rate limiting status
kubectl exec -n $NAMESPACE $GREEN_POD -- curl -s http://localhost:8080/api/admin/rate-limiting/rules/list
```

### 4-Hour Checkpoints

| Checkpoint | Action | Success Criteria |
|-----------|--------|------------------|
| After 4 hours | Review error logs, verify metrics | No 5xx errors, latency < 500ms |
| After 8 hours | Check database performance | Query latency < 10ms |
| After 12 hours | Verify cost/performance | No unexpected resource usage |
| After 24 hours | Final validation | All metrics stable, approve cleanup |

### 24-Hour Post-Deployment

```bash
# At the 24-hour mark, if all metrics are stable:

# Delete blue deployment (no longer needed)
kubectl delete deployment $APP_NAME-blue -n $NAMESPACE

# Archive backup
mv $BACKUP_FILE /backups/archive/

# Update DNS records (if needed)
# Update status page

# Notify team of successful deployment
echo "✅ Deployment complete and verified"
```

---

## Rollback Procedures

### Emergency Rollback (< 5 minutes)

**Triggers**:
- 5xx error rate > 5%
- p95 latency > 500ms
- Service unavailable
- Rate limiting broken

**Steps**:

```bash
# 1. Immediately switch traffic back to blue
kubectl patch service $APP_NAME -n $NAMESPACE \
  --type merge \
  -p '{"spec":{"selector":{"version":"blue"}}}'

echo "✓ Traffic switched back to blue"

# 2. Verify blue is healthy
BLUE_POD=$(kubectl get pods -n $NAMESPACE -l app=$APP_NAME,version=blue \
  -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n $NAMESPACE $BLUE_POD -- curl -s http://localhost:8080/health

# 3. Notify team
echo "⚠️  EMERGENCY ROLLBACK EXECUTED"
echo "Service restored to previous version"
echo "Deploy team notified"
```

### Planned Rollback (< 15 minutes)

**Triggers**:
- Higher than expected violation rates
- Performance degradation after 24 hours
- Data corruption detected
- Business decision to revert

**Steps**:

```bash
# Step 1: Reduce to 50% traffic
kubectl annotate service $APP_NAME -n $NAMESPACE \
  "traffic.split=50% blue,50% green" \
  --overwrite
echo "Step 1: Traffic reduced to 50% green"
sleep 600  # Wait 10 minutes

# Step 2: Reduce to 10% traffic
kubectl annotate service $APP_NAME -n $NAMESPACE \
  "traffic.split=90% blue,10% green" \
  --overwrite
echo "Step 2: Traffic reduced to 10% green"
sleep 300  # Wait 5 minutes

# Step 3: Full rollback
kubectl patch service $APP_NAME -n $NAMESPACE \
  --type merge \
  -p '{"spec":{"selector":{"version":"blue"}}}'
echo "Step 3: Full rollback to blue complete"

# Step 4: Scale down green
kubectl scale deployment/$APP_NAME-green --replicas=1 -n $NAMESPACE
echo "Green deployment scaled down"
```

### Database Rollback (< 30 minutes)

**Triggers**:
- Data corruption
- Migration failure
- Schema incompatibility

**Steps**:

```bash
# 1. Stop green deployment
kubectl scale deployment/$APP_NAME-green --replicas=0 -n $NAMESPACE

# 2. Restore database from backup
DB_USER=$(kubectl get secret -n $NAMESPACE postgres-creds -o jsonpath='{.data.username}' | base64 -d)
DB_PASS=$(kubectl get secret -n $NAMESPACE postgres-creds -o jsonpath='{.data.password}' | base64 -d)
DB_HOST=$(kubectl get secret -n $NAMESPACE postgres-creds -o jsonpath='{.data.host}' | base64 -d)

# Find latest backup
BACKUP_FILE=$(ls -t /backups/gaia_go_*.sql | head -1)

# Restore
PGPASSWORD=$DB_PASS psql -U $DB_USER -h $DB_HOST -d gaia_go < $BACKUP_FILE

echo "Database restored from $BACKUP_FILE"

# 3. Restart services
kubectl scale deployment/$APP_NAME-green --replicas=1 -n $NAMESPACE

# 4. Verify
kubectl rollout status deployment/$APP_NAME-green -n $NAMESPACE --timeout=300s
```

### Rollback Verification

```bash
# After any rollback, verify:

# 1. Service responding
curl -s http://localhost:8080/health

# 2. Metrics available
curl -s http://localhost:8080/metrics | head -10

# 3. Database connected
curl -s http://localhost:8080/api/health/database

# 4. No errors in logs
kubectl logs -n $NAMESPACE -l app=$APP_NAME --tail=50 | grep -i error || echo "✓ No errors"

echo "✓ Rollback verification complete"
```

---

## Troubleshooting Guide

### Common Issues & Solutions

#### Issue 1: Pods Not Starting

**Symptoms**: Green pods stuck in `Pending` or `CrashLoopBackOff`

**Diagnosis**:

```bash
# Check pod status
kubectl get pods -n $NAMESPACE -l app=$APP_NAME,version=green -o wide

# View events
kubectl describe pod <green-pod-name> -n $NAMESPACE

# Check logs
kubectl logs <green-pod-name> -n $NAMESPACE --all-containers
```

**Solutions**:

```bash
# 1. Check resource requests/limits
kubectl get deployment $APP_NAME-green -n $NAMESPACE -o yaml | grep -A 10 resources

# 2. Verify image pull
kubectl get pods -n $NAMESPACE -l app=$APP_NAME,version=green -o jsonpath='{.items[*].status.containerStatuses[*].imageID}'

# 3. Check node resources
kubectl top nodes

# 4. Check persistent volume (if used)
kubectl get pvc -n $NAMESPACE
```

#### Issue 2: High Error Rate During Deployment

**Symptoms**: 5xx errors > 5%, service returning errors

**Diagnosis**:

```bash
# Check error logs
kubectl logs -n $NAMESPACE -l app=$APP_NAME,version=green --tail=200 | grep -i "error\|panic\|fatal"

# Check database connections
kubectl exec -n $NAMESPACE $GREEN_POD -- curl -s http://localhost:8080/api/health/database

# Check migrations
kubectl exec -n $NAMESPACE $GREEN_POD -- curl -s http://localhost:8080/api/health/migrations
```

**Solutions**:

```bash
# 1. Immediate rollback (if > 20 errors)
kubectl patch service $APP_NAME -n $NAMESPACE \
  --type merge \
  -p '{"spec":{"selector":{"version":"blue"}}}'

# 2. Investigate root cause
# Check if database is locked by long-running queries
psql -U postgres -h $DB_HOST -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"

# 3. Check migration status
kubectl exec -n $NAMESPACE $BLUE_POD -- curl -s http://localhost:8080/api/health/migrations

# 4. Rollback migrations if needed
# (See database rollback section)
```

#### Issue 3: High Latency/Timeout Errors

**Symptoms**: p95 latency > 500ms, timeout errors

**Diagnosis**:

```bash
# Check database query performance
kubectl exec -n $NAMESPACE $GREEN_POD -- curl -s http://localhost:8080/metrics | grep query_duration

# Check resource usage
kubectl top pod -n $NAMESPACE -l app=$APP_NAME,version=green

# Check database connection pool
psql -U postgres -h $DB_HOST -c "SELECT count(*) FROM pg_stat_activity WHERE datname='gaia_go';"
```

**Solutions**:

```bash
# 1. Increase replicas to distribute load
kubectl scale deployment/$APP_NAME-green --replicas=3 -n $NAMESPACE

# 2. Check for queries causing slowness
psql -U postgres -h $DB_HOST -c "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# 3. Create missing indexes
# (Specific to your workload)

# 4. Check network latency
kubectl exec -n $NAMESPACE $GREEN_POD -- ping $DB_HOST
```

#### Issue 4: Rate Limiting Not Working

**Symptoms**: All requests allowed, violations not recorded

**Diagnosis**:

```bash
# Check rate limiter is running
kubectl exec -n $NAMESPACE $GREEN_POD -- curl -s http://localhost:8080/api/admin/rate-limiting/rules/list

# Check rules
curl -s http://localhost:8080/api/admin/rate-limiting/rules/list | jq '.'

# Check violations
curl -s http://localhost:8080/metrics | grep rate_limit_violations
```

**Solutions**:

```bash
# 1. Verify rules are created and enabled
./scripts/phase5_smoke_tests.sh localhost:8080

# 2. Check database has rate limiting data
psql -U postgres -h $DB_HOST -d gaia_go -c "SELECT COUNT(*) FROM rate_limiting_rules;"

# 3. Check service is receiving requests
kubectl exec -n $NAMESPACE $GREEN_POD -- curl -s http://localhost:8080/api/check-limit/test

# 4. Restart rate limiter service (if separate)
kubectl rollout restart deployment/$APP_NAME-green -n $NAMESPACE
```

#### Issue 5: Smoke Tests Failing

**Symptoms**: Smoke test script errors, test assertions failing

**Diagnosis**:

```bash
# Run with verbose output
bash -x ./scripts/phase5_smoke_tests.sh localhost:8080

# Check service responding
curl -v http://localhost:8080/health

# Check network connectivity
ping 192.168.x.x  # Service IP

# Check security groups/network policies
kubectl get networkpolicy -n $NAMESPACE
```

**Solutions**:

```bash
# 1. Port-forward if network access limited
kubectl port-forward -n $NAMESPACE svc/$APP_NAME-green 8080:8080 &

# 2. Run smoke tests locally
./scripts/phase5_smoke_tests.sh localhost:8080

# 3. Check logs for service startup
kubectl logs -n $NAMESPACE $GREEN_POD --since=5m

# 4. Verify all endpoints are available
curl -s http://localhost:8080/health
curl -s http://localhost:8080/metrics
curl -s http://localhost:8080/api/health/database
```

### Debug Utilities

```bash
# Get detailed deployment status
kubectl describe deployment $APP_NAME-green -n $NAMESPACE

# Stream real-time logs
kubectl logs -n $NAMESPACE -l app=$APP_NAME,version=green -f

# Execute commands in pod
kubectl exec -it <pod-name> -n $NAMESPACE -- /bin/bash

# Get environment variables
kubectl exec <pod-name> -n $NAMESPACE -- env | sort

# Check mounted volumes
kubectl exec <pod-name> -n $NAMESPACE -- mount | grep /

# Network debugging
kubectl run debug-pod --image=alpine --rm -it --restart=Never -- sh
# Inside pod: nc -zv $APP_NAME-green.production.svc.cluster.local 8080
```

---

## Escalation Paths

### Incident Severity Levels

| Level | Definition | Response Time | Escalation |
|-------|-----------|--------------|-----------|
| **Critical** | Service down, data loss, 5xx > 10% | Immediate | On-call SRE → Eng Lead → CTO |
| **High** | Degraded performance, 5xx 1-10% | 15 mins | On-call SRE → Team Lead |
| **Medium** | Minor issues, recoverable errors | 30 mins | Team Lead → Eng Lead |
| **Low** | Non-urgent issues, warnings | 4 hours | Team Lead → Backlog |

### Escalation Contacts

```
On-Call SRE:        +1-xxx-xxx-xxxx (PagerDuty)
Team Lead:          slack: @team_lead
Engineering Lead:   slack: @eng_lead
CTO:                slack: @cto (critical only)
```

### Incident Communication

1. **Declare Incident**: Post to #gaia-incidents in Slack
2. **Status Page**: Update status.gaia.io if customer-facing
3. **Notify Stakeholders**: Email to support@gaia.io
4. **Prepare Postmortem**: Document timeline and resolution
5. **Root Cause Analysis**: Schedule within 24 hours of resolution

### Emergency Contacts

```bash
# During deployment
echo "Emergency Escalation:"
echo "PagerDuty: https://pagerduty.com/incidents"
echo "Slack Channel: #gaia-incidents"
echo "Status Page: https://status.gaia.io"
echo "War Room: https://zoom.us/my/gaia-incidents (if needed)"
```

---

## Post-Deployment Actions

### After 24-Hour Monitoring

```bash
# If deployment is stable and all metrics green:

# 1. Verify metrics one final time
./scripts/phase5_smoke_tests.sh localhost:8080
# Expected: ✅ All Phase 5 smoke tests passed

# 2. Clean up blue deployment
kubectl delete deployment $APP_NAME-blue -n $NAMESPACE

# 3. Archive backup
mv /backups/gaia_go_pre_deploy_*.sql /backups/archive/

# 4. Update documentation
# - Update DEPLOYMENT_STATUS.md
# - Add release notes
# - Update runbook with lessons learned

# 5. Notify team
# - Post announcement in #deployment
# - Update status page

# 6. Schedule post-mortem (if any issues occurred)
# - Document timeline
# - Identify root causes
# - Create action items
```

### Performance Baseline Collection

```bash
# Collect baseline metrics for future reference
kubectl exec -n $NAMESPACE $GREEN_POD -- curl -s http://localhost:8080/metrics > /monitoring/baselines/phase5_metrics_$(date +%Y%m%d).txt

# Query Prometheus for historical data
# (Grafana → Export dashboard JSON with 24h data)

# Store in deployment records
cp /monitoring/baselines/phase5_metrics_*.txt /deployment/records/$(date +%Y)/$(date +%m)/
```

### Next Phases & Enhancements

After successful Phase 5 production deployment:

- **Phase 6**: Advanced features (Redis caching, ML-based detection)
- **Phase 7**: Federated learning across nodes
- **Phase 8**: Custom rate limiting policies
- **Phase 9**: Reputation marketplace
- **Phase 10**: Production hardening & optimization

---

## Quick Reference

### Essential Commands

```bash
# Deployment
./deployment/phase5_production_deploy.sh v0.5.0-phase5    # Full deployment
./deployment/phase5_production_deploy.sh v0.5.0-phase5 --dry-run  # Dry run

# Smoke Tests
./scripts/phase5_smoke_tests.sh localhost:8080

# Emergency Rollback
kubectl patch service gaia-go -n production \
  --type merge \
  -p '{"spec":{"selector":{"version":"blue"}}}'

# View Logs
kubectl logs -n production -l app=gaia-go,version=green -f

# Check Status
kubectl rollout status deployment/gaia-go-green -n production

# Port Forward (for testing)
kubectl port-forward -n production svc/gaia-go 8080:8080

# Execute Command in Pod
kubectl exec -n production <pod-name> -- curl http://localhost:8080/health
```

### Useful Aliases

```bash
# Add to ~/.bash_profile or ~/.zshrc
alias k=kubectl
alias kgp='kubectl get pods -n production'
alias kgd='kubectl get deployments -n production'
alias kgs='kubectl get svc -n production'
alias kl='kubectl logs -n production -f'
alias kex='kubectl exec -n production -it'
alias kdesc='kubectl describe pod -n production'
```

### Log Analysis

```bash
# Find errors
kubectl logs -n production -l app=gaia-go,version=green | grep -i "error\|panic\|fatal"

# Find specific pattern
kubectl logs -n production -l app=gaia-go,version=green | grep "rate_limit"

# Last 100 lines
kubectl logs -n production -l app=gaia-go,version=green --tail=100

# Since specific time
kubectl logs -n production -l app=gaia-go,version=green --since=10m
```

### Metrics Queries

```bash
# Request rate
curl -s http://localhost:8080/metrics | grep "http_requests_total"

# Error rate
curl -s http://localhost:8080/metrics | grep "code=\"5"

# Latency
curl -s http://localhost:8080/metrics | grep "duration"

# Rate limiting
curl -s http://localhost:8080/metrics | grep "rate_limit"
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-02 | DevOps Team | Initial release for Phase 5 production deployment |

---

## Appendix: Additional Resources

- [Phase 5 Testing Documentation](./PHASE5_TESTING_COMPLETE.md)
- [Rate Limiting Architecture](../ARCHITECTURE_PHASE5.md)
- [Kubernetes Deployment YAML](../deployment/k8s/)
- [Prometheus Alert Rules](../monitoring/alerts.yaml)
- [Grafana Dashboard](./monitoring/phase5_dashboard.json)
- [Troubleshooting Guide](./TROUBLESHOOTING.md)

---

**Last Updated**: 2026-03-02
**Next Review**: 2026-04-02
**Owner**: DevOps Team
**Status**: Production Ready ✓
