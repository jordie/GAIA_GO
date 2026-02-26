# GAIA_GO Phase 9+10 Production Deployment Guide

## Overview

This guide covers deploying GAIA_GO Phase 9+10 to production environment. This is the final step before going live.

**Status**: Production Ready
**Release**: v0.1.0-phase9+10
**Date**: 2026-02-26

## Pre-Deployment Checklist

### 1. Infrastructure Requirements

- [ ] Dedicated production server (2+ cores, 4GB+ RAM)
- [ ] PostgreSQL 15+ database server (separate from app)
- [ ] SSL/TLS certificates (for HTTPS)
- [ ] Reverse proxy (nginx, HAProxy, or AWS ALB)
- [ ] Load balancer (if multi-instance)
- [ ] Monitoring infrastructure (Prometheus, Grafana, ELK)
- [ ] Backup system (daily automated backups)
- [ ] CDN (for static assets if needed)
- [ ] DNS configured and tested

### 2. Security Hardening

- [ ] SSL/TLS certificates installed
- [ ] Database password changed (not default)
- [ ] Database user restricted to app server IP
- [ ] Firewall rules configured (only ports 80, 443, 22 public)
- [ ] SSH key-based authentication enabled
- [ ] API rate limiting enabled
- [ ] CORS restrictions configured
- [ ] Environment variables not in git (use secrets manager)
- [ ] Database encryption enabled
- [ ] Backup encryption enabled

### 3. Code & Deployment

- [ ] Release v0.1.0-phase9+10 downloaded
- [ ] Code reviewed and approved
- [ ] All tests passing (18/18)
- [ ] Documentation reviewed
- [ ] Deployment script tested in staging
- [ ] Rollback plan documented
- [ ] Database migrations tested
- [ ] Environment variables prepared

### 4. Monitoring & Observability

- [ ] Prometheus configured for metrics collection
- [ ] Grafana dashboards created
- [ ] Log aggregation setup (ELK, Loki, CloudWatch)
- [ ] Alerts configured for critical issues
- [ ] Health check endpoints verified
- [ ] Performance baseline established
- [ ] Error tracking configured (Sentry)
- [ ] Uptime monitoring configured (Pingdom, DataDog)

### 5. Operational Readiness

- [ ] On-call schedule established
- [ ] Escalation procedures documented
- [ ] Runbooks written for common issues
- [ ] Disaster recovery plan tested
- [ ] Backup/restore procedures tested
- [ ] Incident response team briefed
- [ ] Maintenance windows scheduled
- [ ] Communication plan prepared

## Production Environment Variables

Create `.env.production` with production-safe values:

```bash
# Server
PORT=8080
HOST=0.0.0.0

# Database - CHANGE ALL PASSWORDS!
DATABASE_URL=postgres://gaia_prod_user:STRONG_PASSWORD_HERE@db.production.internal:5432/gaia_go_prod?sslmode=require

# Claude API
ANTHROPIC_API_KEY=sk-ant-your-production-key-here
CLAUDE_CONFIRM_AI_ENABLED=true

# Security
CORS_ALLOWED_ORIGINS=https://your-domain.com,https://app.your-domain.com
SESSION_TIMEOUT=3600
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=Strict
SESSION_COOKIE_HTTPONLY=true

# Logging
LOG_LEVEL=warn
LOG_FORMAT=json
LOG_OUTPUT=stdout

# Rate Limiting
RATE_LIMIT_ENABLED=true
DEFAULT_RATE_LIMIT=1000
LOGIN_RATE_LIMIT=100

# Monitoring
PROMETHEUS_ENABLED=true
METRICS_PORT=9090
ENABLE_PROFILING=false

# Feature Flags
ENABLE_PATTERN_LEARNING=true
ENABLE_AI_FALLBACK=true
ENABLE_DEBUG_MODE=false
```

## Deployment Steps

### Step 1: Pre-Deployment Verification

```bash
# Verify release is available
git tag -l v0.1.0-phase9+10

# Checkout release
git checkout v0.1.0-phase9+10

# Verify tests pass
go test ./pkg/services/claude_confirm/... -v

# Check binary builds
go build -o bin/gaia_go_prod cmd/server/main.go
file bin/gaia_go_prod
```

### Step 2: Database Setup

```bash
# Create production database and user
psql -h db.production.internal -U postgres <<EOF
CREATE USER gaia_prod_user WITH PASSWORD 'STRONG_PASSWORD_HERE';
CREATE DATABASE gaia_go_prod OWNER gaia_prod_user;
ALTER DATABASE gaia_go_prod SET client_encoding TO 'UTF8';
ALTER DATABASE gaia_go_prod SET default_transaction_isolation TO 'read committed';
ALTER USER gaia_prod_user CREATEDB;
EOF

# Run migrations
PGPASSWORD='STRONG_PASSWORD_HERE' psql \
  -h db.production.internal \
  -U gaia_prod_user \
  -d gaia_go_prod \
  -f migrations/010_claude_confirmation_system.sql
```

### Step 3: Application Deployment

**Option A: Docker (Recommended)**

```bash
# Build production image
docker build -t gaia_go:v0.1.0-phase9+10 \
  -f deployment/Dockerfile \
  .

# Tag for registry
docker tag gaia_go:v0.1.0-phase9+10 your-registry.com/gaia_go:v0.1.0-phase9+10

# Push to registry
docker push your-registry.com/gaia_go:v0.1.0-phase9+10

# Deploy with Docker Compose
docker-compose -f deployment/docker-compose.staging.yml \
  --env-file .env.production \
  up -d
```

**Option B: Binary Deployment**

```bash
# Copy binary to production server
scp bin/gaia_go_prod user@prod-server:/opt/gaia_go/gaia_go

# Create systemd service
sudo tee /etc/systemd/system/gaia_go.service > /dev/null <<EOF
[Unit]
Description=GAIA_GO Application Server
After=network.target postgresql.service

[Service]
Type=simple
User=gaia_go
WorkingDirectory=/opt/gaia_go
ExecStart=/opt/gaia_go/gaia_go
Restart=always
RestartSec=10

# Environment
EnvironmentFile=/opt/gaia_go/.env.production

# Resource limits
LimitNOFILE=65535
LimitNPROC=4096

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Start service
sudo systemctl daemon-reload
sudo systemctl enable gaia_go
sudo systemctl start gaia_go
```

### Step 4: Reverse Proxy Configuration

**nginx Configuration**:

```nginx
upstream gaia_go_backend {
    server localhost:8080 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL Configuration
    ssl_certificate /etc/ssl/certs/your-domain.com.crt;
    ssl_certificate_key /etc/ssl/private/your-domain.com.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Gzip Compression
    gzip on;
    gzip_min_length 1000;
    gzip_types text/plain text/css application/json application/javascript;

    # API Proxy
    location /api/ {
        proxy_pass http://gaia_go_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health Check
    location /health {
        proxy_pass http://gaia_go_backend;
        access_log off;
    }

    # Root
    location / {
        return 404;
    }
}
```

### Step 5: Post-Deployment Verification

```bash
# 1. Health Check
curl -I https://your-domain.com/health

# 2. Test Phase 10 Endpoints
curl -X POST https://your-domain.com/api/claude/confirm/preferences/prod_test \
  -H "Content-Type: application/json" \
  -d '{"allow_all":false,"use_ai_fallback":true}' \
  -k  # Remove -k in production (SSL cert validation)

# 3. Create Test Pattern
curl -X POST https://your-domain.com/api/claude/confirm/patterns \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","permission_type":"read","resource_type":"file","path_pattern":"/test/**","decision_type":"approve","confidence":0.9,"enabled":true}' \
  -k

# 4. Process Test Request
curl -X POST https://your-domain.com/api/claude/confirm/request \
  -H "Content-Type: application/json" \
  -d '{"session_id":"prod_test","permission_type":"read","resource_type":"file","resource_path":"/test/file.txt","context":"Test"}' \
  -k

# 5. Check Statistics
curl https://your-domain.com/api/claude/confirm/stats/prod_test -k | jq '.'

# 6. View Logs
docker logs -f gaia_go_prod
# OR
sudo journalctl -u gaia_go -f
```

## Monitoring & Alerting

### Prometheus Metrics

Key metrics to monitor:

```
http_requests_total{endpoint,method,status}
http_request_duration_seconds{endpoint}
claude_confirmations_total{session_id,decision}
claude_approval_rate{session_id}
database_connection_errors
database_query_duration_seconds
```

### Grafana Dashboard

Create dashboard with:
- Request rate (requests/sec)
- Error rate (5xx responses)
- Response time (p50, p95, p99)
- Database connection pool
- Pattern matching accuracy
- AI agent decision distribution
- System resource usage (CPU, memory)

### Alert Rules

```yaml
groups:
  - name: gaia_go_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate (>5%)"

      - alert: SlowResponses
        expr: histogram_quantile(0.95, http_request_duration_seconds) > 1
        for: 10m
        annotations:
          summary: "p95 response time >1s"

      - alert: DatabaseDown
        expr: up{job="postgres"} == 0
        for: 1m
        annotations:
          summary: "Database is down"

      - alert: LowDiskSpace
        expr: node_filesystem_avail_bytes / node_filesystem_size_bytes < 0.1
        annotations:
          summary: "Disk space <10%"
```

## Backup & Recovery

### Daily Automated Backups

```bash
#!/bin/bash
# /opt/gaia_go/backup.sh

BACKUP_DIR="/var/backups/gaia_go"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
PGPASSWORD='$DB_PASSWORD' pg_dump \
  -h db.production.internal \
  -U gaia_prod_user \
  gaia_go_prod | gzip > $BACKUP_DIR/gaia_go_db_$DATE.sql.gz

# Backup application data
tar -czf $BACKUP_DIR/gaia_go_app_$DATE.tar.gz \
  /opt/gaia_go/.env.production \
  /opt/gaia_go/migrations

# Upload to S3 (or other remote storage)
aws s3 cp $BACKUP_DIR/gaia_go_db_$DATE.sql.gz s3://backup-bucket/gaia_go/

# Cleanup old backups
find $BACKUP_DIR -type f -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $DATE"
```

Add to crontab:
```bash
0 2 * * * /opt/gaia_go/backup.sh >> /var/log/gaia_go_backup.log 2>&1
```

### Recovery Procedure

```bash
# 1. Stop application
sudo systemctl stop gaia_go

# 2. Restore database from backup
BACKUP_FILE="gaia_go_db_20260225_020000.sql.gz"
gunzip < /var/backups/gaia_go/$BACKUP_FILE | \
  PGPASSWORD='$DB_PASSWORD' psql \
    -h db.production.internal \
    -U gaia_prod_user \
    gaia_go_prod

# 3. Restart application
sudo systemctl start gaia_go

# 4. Verify
curl https://your-domain.com/health
```

## Scaling Considerations

### Horizontal Scaling (Multiple Instances)

```yaml
# Load balancer configuration
upstream gaia_go_cluster {
    least_conn;  # Load balancing algorithm
    server app1.internal:8080 max_fails=3;
    server app2.internal:8080 max_fails=3;
    server app3.internal:8080 max_fails=3;

    # Health check
    check interval=3000 rise=2 fall=5 timeout=1000 type=http;
    check_http_send "GET /health HTTP/1.0\r\n\r\n";
    check_http_expect_alive http_2xx http_3xx;
}

server {
    location /api/ {
        proxy_pass http://gaia_go_cluster;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Database Scaling

For production with high load:

1. **Read Replicas**: PostgreSQL streaming replication
2. **Connection Pooling**: pgBouncer for connection management
3. **Sharding**: Partition data by session_id if needed
4. **Caching**: Redis for session preferences and hot patterns

## Troubleshooting Production Issues

### Application not starting

```bash
# Check service status
sudo systemctl status gaia_go

# View logs
sudo journalctl -u gaia_go -n 100

# Check if port is in use
sudo lsof -i :8080

# Test database connection
PGPASSWORD='password' psql -h db.production.internal -U gaia_prod_user -d gaia_go_prod -c "SELECT 1;"
```

### High latency

```bash
# Check database query performance
# Enable slow query log in PostgreSQL:
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- Log queries >1s
SELECT pg_reload_conf();

# Check application metrics
curl http://localhost:9090/metrics | grep duration

# Check system resources
top
df -h
```

### Database connection errors

```bash
# Check database connectivity
nc -zv db.production.internal 5432

# Verify connection pool settings in app
# Edit cmd/server/main.go - increase MaxConns if needed

# Check for connection leaks
SELECT * FROM pg_stat_activity;
```

## Rollback Plan

If critical issues occur post-deployment:

### Quick Rollback (< 5 minutes)

```bash
# 1. Switch traffic to old version
#    (Update load balancer/reverse proxy to point to backup instance)

# 2. Stop new version
docker-compose -f deployment/docker-compose.staging.yml down
# OR
sudo systemctl stop gaia_go

# 3. Restore from pre-deployment backup
PGPASSWORD='password' pg_dump gaia_go_prod_backup | \
  PGPASSWORD='password' psql -h db.production.internal -U gaia_prod_user gaia_go_prod
```

### Full Rollback (to previous release)

```bash
# Checkout previous release
git checkout v0.1.0-phase8

# Rebuild and redeploy
docker build -t gaia_go:v0.1.0-phase8 .
docker-compose up -d

# Restore database to pre-v0.1.0-phase9+10 backup
```

## Post-Deployment Checklist

- [ ] Application is running and healthy
- [ ] All endpoints responding normally
- [ ] Database is connected and initialized
- [ ] Metrics being collected (Prometheus)
- [ ] Logs being aggregated (ELK)
- [ ] Alerts are firing correctly
- [ ] Backups are working
- [ ] SSL/TLS certificates valid
- [ ] Performance meets baseline
- [ ] No errors in application logs
- [ ] Team notified of successful deployment
- [ ] Monitoring dashboards updated
- [ ] Runbooks have been tested
- [ ] On-call team is aware

## Production Support Contacts

| Role | Contact | Availability |
|------|---------|--------------|
| On-Call Engineer | +1-XXX-XXX-XXXX | 24/7 |
| Database Admin | db-team@company.com | Business hours |
| Security Team | security@company.com | Business hours |
| DevOps Lead | devops-lead@company.com | Business hours |

## Incident Response

If production issues occur:

1. **Assess Severity**: Is it affecting users?
2. **Page On-Call**: If customer-impacting
3. **Gather Data**: Logs, metrics, traces
4. **Communicate**: Update status page
5. **Mitigate**: Implement quick fix or rollback
6. **Investigate**: Root cause analysis
7. **Document**: Write incident report
8. **Improve**: Update runbooks/monitoring

## Success Criteria

Production deployment is successful when:

✅ Health check passing (http://your-domain.com/health)
✅ All Phase 10 endpoints responsive
✅ Database fully operational
✅ Monitoring & alerts active
✅ Logs aggregating correctly
✅ Performance meets SLAs
✅ Zero critical errors in logs
✅ Backup/restore tested
✅ Team trained and ready
✅ Runbooks available

---

## Summary

GAIA_GO Phase 9+10 is ready for production deployment. Follow this guide step-by-step for a smooth, reliable production launch.

**Need Help?**
- Check troubleshooting section above
- Review deployment/STAGING_DEPLOYMENT.md for detailed instructions
- Contact your DevOps team

**Release**: v0.1.0-phase9+10
**Date**: 2026-02-26
**Status**: Production Ready ✅
