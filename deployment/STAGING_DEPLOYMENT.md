# GAIA_GO Phase 9+10 Staging Deployment Guide

## Overview

This guide covers deploying GAIA_GO Phase 9 (Teacher Monitoring) and Phase 10 (Claude Auto-Confirm Patterns) to a staging environment using Docker.

## Prerequisites

- **Docker**: v20.10 or later
- **Docker Compose**: v2.0 or later
- **Disk Space**: 2GB minimum
- **Memory**: 2GB minimum free RAM
- **Network**: Access to Anthropic API (optional, for real AI agent)

### Install Docker (macOS with Homebrew)

```bash
brew install docker docker-compose
```

### Start Docker Desktop

```bash
open /Applications/Docker.app
```

## Quick Start (30 minutes)

### 1. Deploy to Staging

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO
deployment/deploy.sh deploy
```

This will:
- ✓ Check prerequisites
- ✓ Build the binary
- ✓ Start PostgreSQL
- ✓ Start GAIA_GO server
- ✓ Run smoke tests
- ✓ Print endpoint summary

### 2. Verify Deployment

```bash
# Health check
curl http://localhost:8080/health

# Get global statistics
curl http://localhost:8080/api/claude/confirm/stats | jq '.'
```

### 3. Access Services

| Service | URL | Purpose |
|---------|-----|---------|
| GAIA_GO API | http://localhost:8080 | Main application |
| Health Check | http://localhost:8080/health | Liveness probe |
| Prometheus Metrics | http://localhost:9091 | System metrics |
| PostgreSQL | localhost:5432 | Database |

## Configuration

### Environment Variables

Edit `deployment/.env.staging` to configure:

```bash
# Server
PORT=8080
HOST=0.0.0.0

# Database
DATABASE_URL=postgres://gaia_user:gaia_staging_password@postgres:5432/gaia_go_staging?sslmode=disable

# Claude API Key (for real AI agent)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Feature Flags
CLAUDE_CONFIRM_AI_ENABLED=true
```

### With Real Claude API

1. Get your API key from [https://console.anthropic.com](https://console.anthropic.com)
2. Update `.env.staging`:
   ```bash
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   CLAUDE_CONFIRM_AI_ENABLED=true
   ```
3. Restart services:
   ```bash
   deployment/deploy.sh restart
   ```

## Phase 10 API Testing

### 1. Create a Session with Preferences

```bash
curl -X POST http://localhost:8080/api/claude/confirm/preferences/staging_session \
  -H "Content-Type: application/json" \
  -d '{
    "allow_all": false,
    "use_ai_fallback": true
  }'
```

### 2. Create an Approval Pattern

```bash
curl -X POST http://localhost:8080/api/claude/confirm/patterns \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Read Project Files",
    "permission_type": "read",
    "resource_type": "file",
    "path_pattern": "/Users/jgirmay/Desktop/gitrepo/**",
    "decision_type": "approve",
    "confidence": 0.95,
    "enabled": true
  }'
```

### 3. Test Confirmation Requests

```bash
# Request that matches pattern (should approve)
curl -X POST http://localhost:8080/api/claude/confirm/request \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "staging_session",
    "permission_type": "read",
    "resource_type": "file",
    "resource_path": "/Users/jgirmay/Desktop/gitrepo/README.md",
    "context": "Reading documentation"
  }' | jq '.'

# Request without pattern match (AI fallback)
curl -X POST http://localhost:8080/api/claude/confirm/request \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "staging_session",
    "permission_type": "delete",
    "resource_type": "database",
    "resource_path": "production.db",
    "context": "Delete operations"
  }' | jq '.'
```

### 4. View Statistics

```bash
# Session stats
curl http://localhost:8080/api/claude/confirm/stats/staging_session | jq '.'

# Global stats
curl http://localhost:8080/api/claude/confirm/stats | jq '.'
```

## Monitoring & Logs

### View Application Logs

```bash
# Real-time logs
deployment/deploy.sh logs

# Or using docker-compose directly
docker-compose -f deployment/docker-compose.staging.yml logs -f gaia_go

# View last 100 lines
docker-compose -f deployment/docker-compose.staging.yml logs gaia_go | tail -100
```

### Database Logs

```bash
docker-compose -f deployment/docker-compose.staging.yml logs postgres
```

### Check Service Status

```bash
deployment/deploy.sh status
```

### Prometheus Metrics

Visit http://localhost:9091 for Prometheus. Useful queries:

```promql
# Request rate
rate(http_requests_total[5m])

# Error rate
rate(http_requests_total{status=~"5.."}[5m])

# Response time
histogram_quantile(0.99, http_request_duration_seconds)
```

## Management

### Restart Services

```bash
deployment/deploy.sh restart
```

### Stop Services (without removing data)

```bash
deployment/deploy.sh stop
```

### Complete Cleanup (removes all data!)

```bash
docker-compose -f deployment/docker-compose.staging.yml down -v
```

### View Database

```bash
# Connect to PostgreSQL
docker-compose -f deployment/docker-compose.staging.yml exec postgres \
  psql -U gaia_user -d gaia_go_staging

# Useful queries:
# \dt              - List tables
# SELECT * FROM claude_confirmations LIMIT 10;
# SELECT * FROM approval_patterns;
# \q              - Quit
```

## Troubleshooting

### Server won't start

Check logs:
```bash
deployment/deploy.sh logs
```

Common issues:
- **Port 8080 in use**: Change `PORT` in `.env.staging`
- **Database connection failed**: Ensure PostgreSQL is running and healthy
- **Out of memory**: Reduce container resources in `docker-compose.staging.yml`

### Database connection errors

```bash
# Check database status
docker-compose -f deployment/docker-compose.staging.yml ps postgres

# Check database logs
docker-compose -f deployment/docker-compose.staging.yml logs postgres

# Manual connection test
docker-compose -f deployment/docker-compose.staging.yml exec postgres \
  pg_isready -U gaia_user -d gaia_go_staging
```

### Slow queries

Enable query logging in `docker-compose.staging.yml`:
```yaml
postgres:
  environment:
    POSTGRES_INITDB_ARGS: "-c log_statement=all"
```

### Out of disk space

```bash
# Clean up old containers and images
docker system prune -a

# View disk usage
docker system df
```

## Performance Tuning

### Database Connection Pool

Edit `cmd/server/main.go`:
```go
db, err := gorm.Open(postgres.Open(dbURL), &gorm.Config{
  ConnPool: sqlc.NewConnector(&sqlc.Config{
    MaxConns: 25,        // Increase for higher concurrency
    MaxIdleConns: 5,
    ConnMaxLifetime: 5 * time.Minute,
  }),
})
```

### Container Resources

Edit `docker-compose.staging.yml`:
```yaml
gaia_go:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
      reservations:
        cpus: '1'
        memory: 1G
```

## Security Considerations

### For Staging Only

⚠️ **Warning**: This deployment is for staging only. For production:

1. **Use TLS/SSL**:
   - Enable `sslmode=require` in DATABASE_URL
   - Use reverse proxy (nginx) with SSL certificates

2. **Secure Secrets**:
   - Use Docker secrets instead of environment variables
   - Store ANTHROPIC_API_KEY in secure vault

3. **Network Security**:
   - Restrict database access to application subnet
   - Use VPC security groups
   - Enable firewall rules

4. **Authentication**:
   - Implement API authentication
   - Use OAuth2 or API keys
   - Rotate credentials regularly

5. **Monitoring**:
   - Enable audit logging
   - Monitor for suspicious patterns
   - Set up alerting

## Backup & Restore

### Backup Database

```bash
# Create backup
docker-compose -f deployment/docker-compose.staging.yml exec postgres \
  pg_dump -U gaia_user gaia_go_staging > backup.sql

# View backup size
ls -lh backup.sql
```

### Restore Database

```bash
# Stop application
deployment/deploy.sh stop

# Restore from backup
docker-compose -f deployment/docker-compose.staging.yml exec -T postgres \
  psql -U gaia_user gaia_go_staging < backup.sql

# Restart
deployment/deploy.sh restart
```

## Migration from Development

### Backup dev data

```bash
# Export from local database
psql -h localhost gaia_go -U jgirmay -c "COPY (SELECT * FROM claude_confirmations) TO STDOUT;" > confirmations.csv
```

### Import to staging

```bash
# Connect to staging database
docker-compose -f deployment/docker-compose.staging.yml exec postgres psql -U gaia_user -d gaia_go_staging

# Inside psql:
# COPY claude_confirmations FROM STDIN; (paste data)
# \. confirmations.csv
```

## Next Steps

1. **Test API Endpoints**: Use the API testing section above
2. **Load Testing**: Deploy [k6](https://k6.io/) for load testing
3. **Integration Testing**: Connect reading apps (rando_inspector, basic_edu)
4. **Performance Testing**: Use Prometheus metrics
5. **Production Deployment**: Follow PRODUCTION_DEPLOYMENT.md

## Support

For issues or questions:

1. Check `deployment/deploy.sh logs`
2. Review this guide's troubleshooting section
3. Check [GitHub Issues](https://github.com/jordie/GAIA_GO/issues)
4. Review Phase 10 documentation: `pkg/services/claude_confirm/README.md`

## Deployment Checklist

- [ ] Docker and Docker Compose installed
- [ ] `.env.staging` configured
- [ ] `deployment/deploy.sh deploy` executed successfully
- [ ] Health check responding (http://localhost:8080/health)
- [ ] Database connected and initialized
- [ ] Phase 10 endpoints tested
- [ ] Logs being collected properly
- [ ] Monitoring accessible (http://localhost:9091)
- [ ] API key configured (if using real Claude)
- [ ] Ready for integration testing

---

**Status**: Phase 9+10 Staging Deployment Ready ✓
**Last Updated**: 2026-02-25
**Version**: 1.0
