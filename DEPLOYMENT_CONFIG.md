# GAIA Automated Deployment Configuration

**Status:** Phase 11.4 - Rate Limiting & Resource Monitoring Ready for Deployment

## Deployment Tags

To trigger automated deployment through GAIA, apply these git tags:

```bash
# Tag for staging deployment
git tag deploy/staging/phase-11.4

# Tag for production deployment (requires staging approval)
git tag deploy/production/phase-11.4

# Push tags to trigger GAIA automation
git push origin deploy/staging/phase-11.4
git push origin deploy/production/phase-11.4
```

## What's Included in Phase 11.4 Deployment

### Phase 11.4: Rate Limiting & Resource Monitoring
- **Database Schema:** Migration 050 with rate limiting tables
- **Rate Limiting Service:** PostgreSQL-backed rate limiting
- **Resource Quotas:** Daily/weekly/monthly quota enforcement
- **Resource Monitoring:** System resource tracking
- **Admin Dashboard:** `/admin/quotas` with comprehensive UI
- **WebSocket Real-time Updates:** Live metrics streaming
- **Analytics Engine:** Quota usage analytics
- **Alert System:** Rate limit violation alerts

### Phase 11.4.4: Admin Dashboard UI
- Real-time quota dashboard
- User quota management interface
- Rate limit configuration panel
- Violation history and reporting
- Analytics and trends visualization

### Phase 11.4.5: WebSocket Real-time Updates
- Live stats broadcasting (5-second intervals)
- Real-time violation notifications
- Alert streaming
- Heartbeat detection (10-second intervals)
- Automatic reconnection with exponential backoff

## Deployment Prerequisites

### Environment Variables Required

**Staging:**
```bash
DATABASE_URL=postgres://jgirmay@localhost/gaia_go_staging?sslmode=disable
PORT=8080
CLAUDE_CONFIRM_AI_ENABLED=true
ANTHROPIC_API_KEY=<your-api-key>
RATE_LIMIT_ENABLED=true
```

**Production:**
```bash
DATABASE_URL=postgres://<prod-user>@<prod-host>/gaia_go?sslmode=require
PORT=8080
CLAUDE_CONFIRM_AI_ENABLED=true
ANTHROPIC_API_KEY=<your-api-key>
RATE_LIMIT_ENABLED=true
ENABLE_PATTERN_LEARNING=true
ENABLE_AI_FALLBACK=true
```

### Database Setup

```bash
# Create database (if not exists)
createdb -U jgirmay gaia_go_staging

# Run migrations
psql -U jgirmay -d gaia_go_staging < migrations/050_rate_limiting_enhancement.sql
psql -U jgirmay -d gaia_go_staging < migrations/050_rate_limiting_phase2_reputation.sql
```

## Automated Deployment Workflow

1. **Tag Creation**
   - Tag commit with `deploy/staging/phase-11.4`
   - GAIA monitors for deployment tags

2. **Pre-Deployment Checks**
   - Verify git tag format
   - Check build status
   - Validate environment configuration

3. **Build & Test**
   - Go build: `go build -o build/gaia_server ./cmd/server`
   - Run smoke tests
   - Verify endpoints respond

4. **Deployment**
   - Stop current server (if running)
   - Deploy binary to target environment
   - Apply database migrations
   - Start server with environment vars

5. **Post-Deployment Verification**
   - Health check: GET `/health`
   - API checks: GET `/api/admin/quotas`
   - WebSocket check: WS `/ws/admin/quotas`
   - Database query verification

## Available Endpoints (Phase 11.4)

### Admin APIs
- `GET /api/admin/quotas/config` - Get quota configurations
- `POST /api/admin/quotas/config` - Create/update quota rules
- `GET /api/admin/quotas/usage` - Get current usage stats
- `GET /api/admin/quotas/violations` - Get rate limit violations
- `GET /api/admin/quotas/analytics` - Get usage analytics

### Admin Dashboard UI
- `GET /admin/quotas` - Main quota management dashboard
- `GET /admin/quotas/*` - Dashboard static assets
- `GET /templates/*` - Dashboard templates

### WebSocket
- `WS /ws/admin/quotas` - Real-time metrics stream
- `GET /api/ws/health` - WebSocket health check

### Core APIs (Phase 10)
- `POST /api/claude/confirm/request` - Claude confirmation request
- `GET /api/claude/confirm/patterns` - Get confirmation patterns

## Monitoring Post-Deployment

### Key Metrics to Monitor
- Rate limit violations per minute
- Average quota usage per user
- System resource consumption
- WebSocket active connections
- API response times (p50, p99)

### Logs to Watch
- Server startup: `[INIT]` messages
- Database connections: `[INIT]` PostgreSQL status
- Rate limiting events: `rate_limit_*` messages
- WebSocket events: `ws_*` messages
- Errors: `[ERROR]` messages

### Alert Thresholds
- Error rate > 1% → Alert
- Rate limit violations > 100/min → Alert
- WebSocket connections < 5 → Check
- Database connection pool > 80% → Alert

## Rollback Procedure

If deployment fails:

```bash
# Stop server
killall gaia_server

# Roll back database (if needed)
# Connect to database and manually reverse migrations
psql -U jgirmay -d gaia_go_staging

# Restore previous binary from backup
cp build/gaia_server.backup build/gaia_server

# Restart with previous version
DATABASE_URL=... ./build/gaia_server
```

## Implementation Status

- [x] Go server built with Phase 11.4 support
- [x] Database schema migrations created
- [x] Rate limiting services implemented
- [x] Admin dashboard UI created
- [x] WebSocket real-time updates added
- [x] Deployment documentation complete
- [x] GAIA automation tags ready
- [ ] Staging deployment via GAIA (Awaiting tag trigger)
- [ ] Production deployment via GAIA (Awaiting staging approval + tag)

## Next Steps

1. **Tag the release for staging:**
   ```bash
   git tag -a deploy/staging/phase-11.4 -m "Phase 11.4: Rate Limiting & Resource Monitoring - Staging Deployment"
   git push origin deploy/staging/phase-11.4
   ```

2. **Monitor GAIA automation**
   - Check GAIA logs for deployment progress
   - Verify endpoints are responding

3. **Run integration tests on staging**
   - Test quota enforcement
   - Test WebSocket connections
   - Test admin dashboard

4. **After staging approval, tag for production:**
   ```bash
   git tag -a deploy/production/phase-11.4 -m "Phase 11.4: Rate Limiting & Resource Monitoring - Production Deployment"
   git push origin deploy/production/phase-11.4
   ```

---

**Deployed by:** Claude Code
**Date:** February 26, 2026
**Binary:** 20MB arm64 executable
**Framework:** Go with Chi router, GORM ORM
**Database:** PostgreSQL
