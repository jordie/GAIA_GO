# Phase 5 Production Deployment Index

**Status**: Production Ready ✓
**Version**: 1.0
**Last Updated**: 2026-03-02
**Owner**: DevOps Team

---

## Quick Start

```bash
# Single command deployment with all automation
cd /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO
./deployment/phase5_production_deploy.sh v0.5.0-phase5

# Monitor deployment in real-time
open http://localhost:3000/d/phase5-production  # Grafana dashboard
```

---

## Deployment Artifacts & Documentation

### Core Deployment Files

| File | Purpose | Usage |
|------|---------|-------|
| **phase5_production_deploy.sh** | Main deployment orchestrator | `./phase5_production_deploy.sh <IMAGE_TAG>` |
| **PHASE5_PRODUCTION_RUNBOOK.md** | Complete operational guide | Reference during deployment |
| **PRE_DEPLOYMENT_CHECKLIST.md** | Pre-flight validation | Run before deployment starts |
| **DEPLOYMENT_STATUS.md** | Status tracking document | Update during/after deployment |

### Monitoring & Testing

| File | Purpose | Usage |
|------|---------|-------|
| **../scripts/phase5_smoke_tests.sh** | Smoke test suite | `./phase5_smoke_tests.sh <HOST:PORT>` |
| **../scripts/phase5_load_baseline.sh** | Load testing baseline | `./phase5_load_baseline.sh <HOST:PORT>` |
| **../monitoring/phase5_dashboard.json** | Grafana dashboard | Import into Grafana |
| **prometheus.yml** | Prometheus config | Reference for metric collection |

---

## Deployment Decision Tree

```
START
  │
  ├─→ Is this your first deployment?
  │    YES: Read PHASE5_PRODUCTION_RUNBOOK.md sections 1-3
  │    NO:  Proceed to checklist
  │
  ├─→ Complete PRE_DEPLOYMENT_CHECKLIST.md
  │    ✓ All items checked? → Continue
  │    ✗ Issues found? → Fix and restart
  │
  ├─→ Run smoke tests on current (blue) version
  │    ✓ All passed? → Continue to deployment
  │    ✗ Tests failed? → Investigate and fix issues
  │
  ├─→ Run deployment script (dry-run first)
  │    ./phase5_production_deploy.sh v0.5.0-phase5 --dry-run
  │    ✓ Looks good? → Run actual deployment
  │    ✗ Issues? → Fix and re-run dry-run
  │
  ├─→ Execute production deployment
  │    ./phase5_production_deploy.sh v0.5.0-phase5
  │    Monitor with Grafana dashboard (phase5-production)
  │
  ├─→ Canary phases (automated)
  │    • 10% traffic for 15 mins
  │    • 50% traffic for 10 mins
  │    • 100% traffic cutover
  │    ✓ All phases passed? → Continue
  │    ✗ Errors detected? → Automatic rollback
  │
  ├─→ Post-deployment monitoring (24 hours)
  │    Check metrics every 4 hours
  │    ✓ Stable for 24h? → Complete cleanup
  │    ✗ Issues found? → See ROLLBACK section
  │
  └─→ COMPLETE
```

---

## Deployment Phases Overview

### Phase 1: Pre-Deployment (30 mins)
- Verify cluster connectivity
- Check database health
- Create backups
- Run pre-flight checks

**Documentation**: PHASE5_PRODUCTION_RUNBOOK.md → "Pre-Deployment Checklist"
**Script**: Built into `phase5_production_deploy.sh`

### Phase 2: Green Deployment (15 mins)
- Build Docker image
- Push to registry
- Deploy to green environment
- Wait for pods to be ready

**Documentation**: PHASE5_PRODUCTION_RUNBOOK.md → "Deployment Procedures" → "Phase 2"
**Script**: Automated by `phase5_production_deploy.sh`

### Phase 3: Smoke Testing (15 mins)
- Run comprehensive smoke test suite
- Validate all endpoints
- Verify rate limiting
- Check database connectivity

**Documentation**: PHASE5_PRODUCTION_RUNBOOK.md → "Deployment Procedures" → "Phase 3"
**Script**: `./scripts/phase5_smoke_tests.sh`

### Phase 4: Canary Release (30+ mins)
- 10% traffic to green (15 mins)
- 50% traffic to green (10 mins)
- 100% traffic cutover (5 mins)

**Documentation**: PHASE5_PRODUCTION_RUNBOOK.md → "Deployment Procedures" → "Phases 4-6"
**Monitoring**: Grafana dashboard (phase5-production)

### Phase 5: Blue Cleanup (15 mins)
- Scale down blue to 1 replica
- Prepare for 24-hour monitoring

**Documentation**: PHASE5_PRODUCTION_RUNBOOK.md → "Deployment Procedures" → "Phase 7"
**Script**: Automated by `phase5_production_deploy.sh`

### Phase 6: Post-Deployment Monitoring (24 hours)
- Real-time monitoring with Grafana
- 4-hour checkpoints
- Automated health checks

**Documentation**: PHASE5_PRODUCTION_RUNBOOK.md → "Monitoring Checkpoints"
**Dashboard**: http://localhost:3000/d/phase5-production

---

## Deployment Workflow

### Standard Deployment

```bash
# 1. Pre-flight (run checklist)
./deployment/PRE_DEPLOYMENT_CHECKLIST.md

# 2. Dry-run (optional but recommended)
./deployment/phase5_production_deploy.sh v0.5.0-phase5 --dry-run

# 3. Full deployment (automated)
./deployment/phase5_production_deploy.sh v0.5.0-phase5

# 4. Monitor dashboard (open in browser)
open http://localhost:3000/d/phase5-production

# 5. After 24 hours (if stable)
kubectl delete deployment gaia-go-blue -n production
```

### Dry-Run Deployment (No Changes)

```bash
# Tests all automation without making actual changes
./deployment/phase5_production_deploy.sh v0.5.0-phase5 --dry-run

# Output shows:
# - Would build image
# - Would deploy to green
# - Would run smoke tests
# - Would shift traffic
# - Would cleanup blue
```

### Manual Step-by-Step

```bash
# For troubleshooting or custom scenarios
# See: PHASE5_PRODUCTION_RUNBOOK.md → "Deployment Procedures"
# Follow section "Manual Step-by-Step Deployment"
```

---

## Rollback Procedures

### Emergency Rollback (< 5 minutes)

**When**: 5xx error rate > 5%, service down, critical bug found

```bash
# Automatic: Script detects errors and rolls back
# Manual: kubectl patch service gaia-go -n production \
#   --type merge \
#   -p '{"spec":{"selector":{"version":"blue"}}}'

# See: PHASE5_PRODUCTION_RUNBOOK.md → "Rollback Procedures" → "Emergency Rollback"
```

### Planned Rollback (< 15 minutes)

**When**: Performance issues after 24h, business decision to revert

```bash
# Step-by-step traffic reduction:
# 1. Reduce to 50% traffic for 10 mins
# 2. Reduce to 10% traffic for 5 mins
# 3. Full rollback to blue

# See: PHASE5_PRODUCTION_RUNBOOK.md → "Rollback Procedures" → "Planned Rollback"
```

### Database Rollback (< 30 minutes)

**When**: Data corruption, migration failure, schema issues

```bash
# From pre-deployment backup
# Requires manual intervention

# See: PHASE5_PRODUCTION_RUNBOOK.md → "Rollback Procedures" → "Database Rollback"
```

---

## Testing & Validation

### Pre-Deployment Tests

```bash
# Run all tests on current environment
go test -v ./pkg/services/rate_limiting

# Expected: 65+ tests, 100% pass rate
```

### Smoke Tests

```bash
# Quick validation of critical functionality
./scripts/phase5_smoke_tests.sh localhost:8080

# Tests:
# ✓ Health check
# ✓ Metrics endpoint
# ✓ Database connectivity
# ✓ Rules API
# ✓ Rate limiting enforcement
# ✓ Migrations status
```

### Load Testing Baseline

```bash
# Establish performance baselines
./scripts/phase5_load_baseline.sh localhost:8080

# Tests:
# • Sustained load (1000 req/s)
# • Burst load (5000 req/s)
# • Concurrent users (100)

# Validates:
# • p99 < 5ms
# • p95 < 2ms
# • Throughput > 10K req/s
```

### Performance Monitoring

```bash
# Live dashboard
open http://localhost:3000/d/phase5-production

# Key metrics:
# • Request rate (should be consistent)
# • Error rate (should be < 0.1%)
# • p95/p99 latency (should be stable)
# • Memory usage (should not spike)
```

---

## Monitoring & Observability

### Grafana Dashboard

```
File: ../monitoring/phase5_dashboard.json
URL: http://localhost:3000/d/phase5-production
UID: phase5-production

Panels:
1. Request Rate (5m average)
2. HTTP 5xx Error Rate
3. API Latency (p95/p99)
4. Rate Limiting Violations by Scope
5. Top 10 Violators (IPs)
6. Rule Evaluation Performance
7. Database Query Latency
8. Memory Usage (MB)
9. CPU Usage (%)
10. Deployment Status
```

### Key Metrics

| Metric | Healthy | Alert | Critical |
|--------|---------|-------|----------|
| Request Rate | 1-10K/s | < 500/s | 0 |
| 5xx Error Rate | < 0.1% | > 1% | > 5% |
| p95 Latency | < 100ms | > 200ms | > 500ms |
| p99 Latency | < 500ms | > 1000ms | > 2000ms |
| Memory | < 512MB | > 768MB | > 1GB |
| CPU | < 50% | > 70% | > 90% |

### Alert Rules

```
File: ../monitoring/alerts.yaml
Rules:
- HighErrorRate (5xx > 5%)
- HighLatency (p95 > 500ms)
- HighMemory (> 1GB)
- ServiceDown (no responses)
- RateLimitingBroken (no limits enforced)
```

---

## Troubleshooting

### Common Issues

1. **Pods not starting**
   → See: PHASE5_PRODUCTION_RUNBOOK.md → "Troubleshooting" → "Issue 1"

2. **High error rate**
   → See: PHASE5_PRODUCTION_RUNBOOK.md → "Troubleshooting" → "Issue 2"

3. **High latency**
   → See: PHASE5_PRODUCTION_RUNBOOK.md → "Troubleshooting" → "Issue 3"

4. **Rate limiting not working**
   → See: PHASE5_PRODUCTION_RUNBOOK.md → "Troubleshooting" → "Issue 4"

5. **Smoke tests failing**
   → See: PHASE5_PRODUCTION_RUNBOOK.md → "Troubleshooting" → "Issue 5"

### Debug Commands

```bash
# View pod status
kubectl get pods -n production -l app=gaia-go

# View logs
kubectl logs -n production -l app=gaia-go,version=green -f

# Check metrics
curl http://localhost:8080/metrics | grep rate_limit

# Test connectivity
kubectl exec -n production <pod> -- curl http://localhost:8080/health
```

---

## Post-Deployment Actions

### After 24-Hour Monitoring

```bash
# If all metrics are stable:

# 1. Verify metrics
./scripts/phase5_smoke_tests.sh localhost:8080

# 2. Delete blue deployment
kubectl delete deployment gaia-go-blue -n production

# 3. Archive backup
mv /backups/gaia_go_pre_deploy_*.sql /backups/archive/

# 4. Update documentation
# - Add deployment notes
# - Document any issues/resolutions
# - Update performance baselines

# 5. Notify team
# - Post announcement
# - Update status page
# - Create post-mortem (if needed)
```

### Performance Baseline Collection

```bash
# Export baseline metrics for future comparison
kubectl exec -n production <pod> -- curl http://localhost:8080/metrics \
  > /monitoring/baselines/phase5_metrics_$(date +%Y%m%d).txt

# Store in deployment records
cp /monitoring/baselines/phase5_metrics_*.txt \
  /deployment/records/$(date +%Y)/$(date +%m)/
```

---

## Quick Reference

### Essential Commands

```bash
# Deployment
./deployment/phase5_production_deploy.sh v0.5.0-phase5

# Dry-run (no changes)
./deployment/phase5_production_deploy.sh v0.5.0-phase5 --dry-run

# Smoke tests
./scripts/phase5_smoke_tests.sh localhost:8080

# Load testing baseline
./scripts/phase5_load_baseline.sh localhost:8080

# Emergency rollback
kubectl patch service gaia-go -n production \
  --type merge \
  -p '{"spec":{"selector":{"version":"blue"}}}'

# View logs
kubectl logs -n production -l app=gaia-go,version=green -f

# Port forward (for testing)
kubectl port-forward -n production svc/gaia-go 8080:8080
```

### Critical URLs

| Resource | URL | Purpose |
|----------|-----|---------|
| **Grafana Dashboard** | http://localhost:3000/d/phase5-production | Real-time monitoring |
| **Prometheus** | http://localhost:9090 | Metrics query |
| **Status Page** | https://status.gaia.io | Customer-facing status |
| **War Room** | https://zoom.us/my/gaia-incidents | Incident discussion |

---

## Team Roles & Responsibilities

| Role | Responsibility | Contact |
|------|---------------|---------|
| **DevOps Lead** | Overall deployment coordination | @devops-lead |
| **SRE On-Call** | Real-time monitoring & incident response | @sre-oncall |
| **Database Admin** | Backup/restore operations | @dba-team |
| **Engineering Lead** | Code validation & go/no-go decision | @eng-lead |

---

## Deployment Schedule

| Phase | Duration | Start | End | Owner |
|-------|----------|-------|-----|-------|
| Pre-Deployment | 30 mins | T+0:00 | T+0:30 | DevOps |
| Green Deploy | 15 mins | T+0:30 | T+0:45 | DevOps |
| Smoke Tests | 15 mins | T+0:45 | T+1:00 | QA/DevOps |
| Canary 10% | 15 mins | T+1:00 | T+1:15 | SRE |
| Canary 50% | 10 mins | T+1:15 | T+1:25 | SRE |
| Cutover | 5 mins | T+1:25 | T+1:30 | SRE |
| Cleanup | 15 mins | T+1:30 | T+1:45 | DevOps |
| Monitoring | 24 hours | T+1:45 | T+25:45 | SRE/DevOps |

**Total Active Time**: ~2 hours
**Total With Monitoring**: 24 hours

---

## Documentation Index

### Main Documents

1. **PHASE5_DEPLOYMENT_INDEX.md** (this file)
   - Overview and decision tree
   - Quick reference guide

2. **PHASE5_PRODUCTION_RUNBOOK.md**
   - Complete operational procedures
   - Pre-deployment checklists
   - Step-by-step instructions
   - Rollback procedures
   - Troubleshooting guide
   - Escalation paths

3. **PRE_DEPLOYMENT_CHECKLIST.md**
   - Access & permissions
   - Code & release readiness
   - Infrastructure prerequisites
   - Database readiness
   - Monitoring & alerting
   - Security & compliance
   - Pre-deployment sign-off

4. **DEPLOYMENT_STATUS.md**
   - Current deployment status
   - Recent changes
   - Known issues
   - Performance baselines

### Supporting Files

- **phase5_production_deploy.sh** - Main deployment script
- **../scripts/phase5_smoke_tests.sh** - Smoke test suite
- **../scripts/phase5_load_baseline.sh** - Load testing
- **../monitoring/phase5_dashboard.json** - Grafana dashboard
- **prometheus.yml** - Prometheus configuration

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-02 | DevOps Team | Initial release - Phase 5 production deployment |

---

## Support & Escalation

**For Deployment Issues**:
- Check troubleshooting guide: PHASE5_PRODUCTION_RUNBOOK.md → Troubleshooting
- Contact: @devops-lead or #gaia-deployment Slack channel

**For Production Incidents**:
- Declare incident: Post to #gaia-incidents
- Escalate: Page on-call engineer via PagerDuty
- War room: https://zoom.us/my/gaia-incidents

**For Questions**:
- Review runbook and quick reference
- Check documentation index above
- Ask in #gaia-ops Slack channel

---

**Last Updated**: 2026-03-02
**Next Review**: 2026-04-02
**Status**: Production Ready ✓

---

## Related Documentation

- [Phase 5 Testing Complete](../docs/PHASE5_TESTING_COMPLETE.md)
- [Architecture Overview](../ARCHITECTURE_PHASE5.md)
- [Rate Limiting Design](../docs/RATE_LIMITING_DESIGN.md)
- [Kubernetes Setup](./k8s/README.md)
- [Troubleshooting Guide](../docs/TROUBLESHOOTING.md)
