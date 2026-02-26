# Production Deployment Pre-Flight Checklist

**Release**: v0.1.0-phase9+10
**Date**: 2026-02-26
**Status**: Ready for Production

---

## ✅ CODE & RELEASE VERIFICATION

- [ ] Release v0.1.0-phase9+10 is published on GitHub
- [ ] Code reviewed and approved by team lead
- [ ] All 18 tests passing (unit + integration)
- [ ] No compilation warnings
- [ ] No security vulnerabilities identified
- [ ] Changelog updated with new features
- [ ] Release notes complete and accurate

**Verification Commands**:
```bash
git tag -l v0.1.0-phase9+10
go test ./pkg/services/claude_confirm/... -v
go build -o bin/gaia_go cmd/server/main.go
```

---

## ✅ INFRASTRUCTURE READINESS

### Compute & Networking
- [ ] Production server(s) provisioned (2+ cores, 4GB+ RAM)
- [ ] Network connectivity verified
- [ ] Firewall rules configured (80, 443, 22 for SSH only)
- [ ] DNS records created and resolving
- [ ] SSL/TLS certificates obtained and valid
- [ ] Reverse proxy (nginx/HAProxy) installed
- [ ] Load balancer configured (if multi-instance)

### Database
- [ ] PostgreSQL 15+ installed and running
- [ ] Database user created (non-default password)
- [ ] Database `gaia_go_prod` created
- [ ] Connection pooling configured
- [ ] Backup system configured
- [ ] WAL archiving enabled
- [ ] Connection from app server verified

**Test Database Connection**:
```bash
psql -h db.production.internal -U gaia_prod_user -d gaia_go_prod -c "SELECT 1;"
```

### Monitoring
- [ ] Prometheus installed and configured
- [ ] Grafana dashboards created
- [ ] Log aggregation (ELK/Loki) set up
- [ ] Alert rules configured
- [ ] On-call alerting configured (PagerDuty/Opsgenie)
- [ ] Uptime monitoring configured (Pingdom/DataDog)

---

## ✅ SECURITY CONFIGURATION

### Secrets & Credentials
- [ ] `.env.production` created with production values
- [ ] All passwords changed from defaults
- [ ] API keys obtained and validated
- [ ] Secrets stored in vault (not in git)
- [ ] Database user restricted by IP
- [ ] Application user account created (non-root)

### SSL/TLS
- [ ] SSL certificate obtained from CA
- [ ] Certificate validity verified (expiry date)
- [ ] Key stored securely with restricted permissions
- [ ] HSTS header configured
- [ ] TLS 1.2+ only (disable older versions)
- [ ] Strong cipher suites configured

### Application Security
- [ ] CORS origins restricted to production domain
- [ ] X-Frame-Options set to DENY
- [ ] X-Content-Type-Options set to nosniff
- [ ] X-XSS-Protection enabled
- [ ] CSP headers configured
- [ ] Debug mode disabled
- [ ] Error stack traces disabled in responses

### Database Security
- [ ] PostgreSQL passwords strong (20+ characters)
- [ ] `sslmode=require` in DATABASE_URL
- [ ] Row-level security enabled (if needed)
- [ ] Public schema permissions restricted
- [ ] Backup encryption enabled
- [ ] Database activity logging enabled

---

## ✅ DEPLOYMENT ARTIFACTS

### Application Binary
- [ ] Production binary built: `go build -o bin/gaia_go_prod cmd/server/main.go`
- [ ] Binary size verified (~14MB Linux x86_64)
- [ ] Binary tested locally
- [ ] Binary signed (if required)
- [ ] Docker image built and tested
- [ ] Docker image tagged with version
- [ ] Docker image pushed to registry

### Configuration Files
- [ ] `.env.production` prepared with production values
- [ ] nginx/HAProxy config reviewed and tested
- [ ] systemd service file (if using binary deployment)
- [ ] docker-compose.staging.yml reviewed for production
- [ ] Prometheus scrape config updated
- [ ] Backup script configured and tested

### Database
- [ ] Migration files verified
- [ ] Schema matches expected state
- [ ] Initial data loaded (if any)
- [ ] Migrations tested on staging

---

## ✅ TESTING & VALIDATION

### Local Testing
- [ ] Application starts without errors
- [ ] Health check endpoint responds: `/health`
- [ ] Database connection works
- [ ] API endpoints tested locally
- [ ] Pattern matching tested
- [ ] AI fallback tested (with mock)
- [ ] Session preferences tested

### Staging Testing
- [ ] Full smoke test suite passed
- [ ] Load testing completed
- [ ] Performance baselines established
- [ ] Failover tested (database unavailable)
- [ ] Rollback procedure tested
- [ ] Backup/restore tested

**Staging Smoke Test**:
```bash
curl http://staging.internal:8080/health
curl -X POST http://staging.internal:8080/api/claude/confirm/request \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test","permission_type":"read","resource_type":"file","resource_path":"/test.txt","context":"test"}'
```

---

## ✅ DOCUMENTATION & RUNBOOKS

### Operational Documentation
- [ ] Runbooks written for common issues
- [ ] Deployment procedure documented
- [ ] Rollback procedure documented and tested
- [ ] Monitoring dashboards documented
- [ ] Alert rules documented
- [ ] Service dependencies mapped
- [ ] Architecture diagram updated

### Support Documentation
- [ ] On-call procedures documented
- [ ] Escalation matrix created
- [ ] Contact information updated
- [ ] Incident response procedure written
- [ ] Post-incident review template prepared
- [ ] Change management procedure documented

### Knowledge Transfer
- [ ] Team briefed on new features
- [ ] Operations team trained on monitoring
- [ ] Support team trained on common issues
- [ ] Documentation reviewed by team
- [ ] FAQs prepared for common questions

---

## ✅ TEAM & PROCESS

### Personnel
- [ ] Deployment lead assigned
- [ ] On-call engineer assigned
- [ ] Database admin available
- [ ] Security team notified
- [ ] Stakeholders notified (product, marketing)

### Communication
- [ ] Deployment window scheduled
- [ ] Status page prepared
- [ ] Customer notifications drafted (if needed)
- [ ] Internal status channel ready
- [ ] Incident escalation contacts prepared

### Approval
- [ ] Technical lead approved
- [ ] Security team approved
- [ ] Operations team approved
- [ ] Product team approved
- [ ] Executive stakeholder approved (if required)

---

## ✅ PRODUCTION READINESS FINAL CHECK

### Go/No-Go Decision Criteria

**GO IF ALL TRUE**:
- ✅ All checklist items completed
- ✅ No critical security issues
- ✅ All tests passing
- ✅ Staging deployment successful
- ✅ Team trained and ready
- ✅ Monitoring fully operational
- ✅ Runbooks tested
- ✅ Rollback plan ready

**NO-GO IF ANY TRUE**:
- ❌ Outstanding critical issues
- ❌ Security vulnerabilities found
- ❌ Tests failing
- ❌ Team not ready
- ❌ Monitoring not functional
- ❌ Database issues
- ❌ Network connectivity problems
- ❌ SSL certificate issues

### Final Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Deployment Lead | __________ | _____ | __________ |
| Technical Lead | __________ | _____ | __________ |
| Operations Lead | __________ | _____ | __________ |
| Security Lead | __________ | _____ | __________ |

---

## DEPLOYMENT PROCEDURE

Once all checkboxes are complete, proceed with deployment:

### Phase 1: Pre-Deployment (30 minutes before)
```bash
# 1. Notify team
echo "Deployment starting in 30 minutes"

# 2. Final verification
go test ./pkg/services/claude_confirm/... -v

# 3. Backup current state
docker-compose -f deployment/docker-compose.staging.yml exec postgres \
  pg_dump -U gaia_user gaia_go_prod > pre_deployment_backup.sql

# 4. Alert setup verification
curl http://localhost:9091/api/v1/rules
```

### Phase 2: Deployment (30-45 minutes)
```bash
# 1. Start deployment
echo "Starting production deployment at $(date)"

# 2. Deploy application
cd deployment
docker-compose -f docker-compose.staging.yml up -d

# 3. Run migrations (if any)
docker-compose -f docker-compose.staging.yml exec postgres \
  psql -U gaia_prod_user -d gaia_go_prod -f migrations/010_claude_confirmation_system.sql

# 4. Verify services are running
docker-compose -f docker-compose.staging.yml ps
```

### Phase 3: Post-Deployment Verification (15 minutes)
```bash
# 1. Health check
curl https://your-domain.com/health

# 2. Test endpoints
curl -X POST https://your-domain.com/api/claude/confirm/preferences/test \
  -H "Content-Type: application/json" \
  -d '{"allow_all":false,"use_ai_fallback":true}'

# 3. Check logs
docker-compose -f docker-compose.staging.yml logs gaia_go

# 4. Verify metrics
curl http://localhost:9090/metrics | grep http_requests_total

# 5. Monitor for errors (5 minutes)
docker-compose -f docker-compose.staging.yml logs -f gaia_go | grep -i error
```

### Phase 4: Sign-Off
```bash
# 1. Notify team
echo "Production deployment SUCCESSFUL at $(date)"

# 2. Update status
# Update status page: "All systems operational"

# 3. Document deployment
# Add entry to change log

# 4. Schedule post-deployment review
# Schedule for 24 hours post-deployment
```

---

## ROLLBACK PROCEDURE

If critical issues occur:

```bash
# 1. Immediate notification
echo "INCIDENT: Rolling back deployment"

# 2. Stop new version
docker-compose -f docker-compose.staging.yml down

# 3. Restore from pre-deployment backup
cat pre_deployment_backup.sql | \
  PGPASSWORD='password' psql -h db.production.internal -U gaia_prod_user gaia_go_prod

# 4. Redeploy previous version
git checkout v0.1.0-phase8
docker build -t gaia_go:v0.1.0-phase8 .
docker-compose -f docker-compose.staging.yml up -d

# 5. Verify
curl https://your-domain.com/health

# 6. Notify team
echo "Rollback COMPLETE - investigating issue"
```

---

## POST-DEPLOYMENT MONITORING (24 Hours)

Monitor these metrics continuously:

- [ ] Error rate < 0.1%
- [ ] p95 response time < 1 second
- [ ] Database connection pool healthy
- [ ] No memory leaks (check memory growth)
- [ ] CPU usage < 80%
- [ ] Disk usage < 80%
- [ ] Zero alerts triggered
- [ ] Pattern matching working
- [ ] AI agent responding correctly
- [ ] Session preferences being saved

**24-Hour Check**:
```bash
# Run at 24 hours post-deployment
curl https://your-domain.com/api/claude/confirm/stats | jq '.'
# Should show normal usage patterns
```

---

## SUCCESS CRITERIA ✅

Production deployment is successful when:

1. ✅ Application responding to all requests
2. ✅ Database fully operational
3. ✅ Phase 10 endpoints working correctly
4. ✅ Monitoring and alerts active
5. ✅ No critical errors in logs
6. ✅ Performance meets SLAs
7. ✅ Team trained and confident
8. ✅ Backup/restore tested
9. ✅ Rollback plan verified
10. ✅ Documentation complete

---

**Status**: READY FOR PRODUCTION DEPLOYMENT ✅

**Next Step**: Complete all checklist items, get sign-offs, and execute deployment.
