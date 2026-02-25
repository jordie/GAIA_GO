# GAIA_GO Multi-Environment Development Pipeline

## Architecture Overview

GAIA_GO now operates across **three isolated environments**, each with unique purposes, configurations, and lifecycles:

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                   GAIA_GO DEVELOPMENT PIPELINE (Multi-Env)               ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║  DEV (8081)              STAGING (8082)          PROD (8080)            ║
║  ────────────            ──────────────          ─────────              ║
║  🧪 Rapid Testing       ✔️ Pre-Production       🚀 Dogfooding          ║
║  🔬 Experiments         🧪 Integration Tests    ⚙️ Self-Improving      ║
║  📈 Aggressive Opt      📊 Load Testing        🔄 Autonomous           ║
║  ✨ All Features        ⚡ Stable Setup        🛡️ Mission-Critical    ║
║                                                                          ║
║  Database: dev_gaia.db  Database: staging_gaia.db  Database: prod_gaia.db ║
║  Reset: YES (safe)      Reset: NO (persistent)     Reset: NO (backed up)  ║
║  Logs: 7 days           Logs: 30 days              Logs: 90 days          ║
║  Backup: None           Backup: Daily              Backup: Hourly         ║
║                                                                          ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

## Directory Structure

```
/GAIA_GO/environments/
├── ENVIRONMENT_MANIFEST.md          # Detailed documentation
├── manage_environments.sh            # Environment management CLI
│
├── dev/                             # Development Environment
│   ├── GAIA_GO.env                  # Dev configuration (port 8081)
│   ├── config/                      # Dev-specific configs
│   ├── data/
│   │   └── dev_gaia.db              # Can be reset freely
│   ├── logs/                        # DEBUG level, 7-day retention
│   └── bin/                         # Dev binaries
│
├── staging/                         # Staging Environment
│   ├── GAIA_GO.env                  # Staging configuration (port 8082)
│   ├── config/                      # Staging-specific configs
│   ├── data/
│   │   ├── staging_gaia.db          # Persistent, production-like
│   │   └── backups/                 # Daily backups
│   ├── logs/                        # INFO level, 30-day retention
│   └── bin/                         # Staging binaries
│
└── prod/                            # Production Environment
    ├── GAIA_GO.env                  # Production configuration (port 8080)
    ├── config/                      # Prod-specific configs
    ├── data/
    │   ├── prod_gaia.db             # Mission-critical, hourly backup
    │   └── backups/                 # 90-day backup retention
    ├── logs/                        # WARN level, 90-day retention
    ├── bin/                         # Production binaries
    ├── self_improve.sh              # Self-improvement orchestrator
    └── SELF_IMPROVEMENT_QUEUE.md    # Dogfooding task queue
```

## Environment Comparison Matrix

| Aspect | DEV | STAGING | PROD |
|--------|-----|---------|------|
| **Port** | 8081 | 8082 | 8080 |
| **Hostname** | localhost | 0.0.0.0 | 0.0.0.0 |
| **Database** | dev_gaia.db | staging_gaia.db | prod_gaia.db |
| **Reset Safe** | ✅ YES | ❌ NO | ❌ NO |
| **Log Level** | DEBUG | INFO | WARN |
| **Logging** | Verbose | Structured | JSON/Minimal |
| **Retention** | 7 days | 30 days | 90 days |
| **Backup** | None | Daily | Hourly |
| **Auto Build** | YES | YES | YES |
| **Auto Test** | YES | YES | YES |
| **Auto Deploy** | NO | NO | YES |
| **Experimental** | YES | NO | NO |
| **Dogfooding** | NO | NO | YES |
| **Stability** | Experimental | Stable | Guaranteed |
| **Use Case** | Development | Integration | Production |
| **Users** | Developers | QA/Testers | Autonomous (foundation) |

## Environment Promotion Pipeline

```
┌─────────────────────┐
│  DEV ENVIRONMENT    │
│  Port: 8081         │
│  All experiments ON │
│  Auto-reset enabled │
└──────────┬──────────┘
           │ (Tests pass)
           ▼
┌─────────────────────┐
│  STAGING ENVIRONMENT │
│  Port: 8082         │
│  Production config  │
│  Full test suite    │
└──────────┬──────────┘
           │ (All tests pass)
           ▼
┌─────────────────────┐
│  PROD ENVIRONMENT   │
│  Port: 8080         │
│  Live dogfooding    │
│  Self-improving     │
│  Mission-critical   │
└─────────────────────┘
           │
           │ (Detects improvements)
           ▼
    ┌──────────────┐
    │ Self-improve │
    │ (foundation) │
    └──────────────┘
           │
           ▼ (Deploy improvements)
    Back to DEV environment
```

## Running Each Environment

### DEV Environment (Development & Experimentation)

```bash
# Load configuration
cd /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/environments/dev
source GAIA_GO.env

# Run server with DEBUG logging
go run ../../cmd/server/main.go

# In another terminal - check health
curl http://localhost:8081/health

# View logs in real-time
tail -f ./logs/gaia.log
```

**When to use:**
- Testing new Phase 8 subsystems
- Experimenting with optimizations
- Rapid iteration on features
- Debugging with detailed logs

**Safe operations:**
- Reset database: `rm data/dev_gaia.db` (will recreate on startup)
- Delete logs: `rm logs/*` (will restart logging)

### STAGING Environment (Pre-Production Validation)

```bash
# Load configuration
cd /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/environments/staging
source GAIA_GO.env

# Run server (production-like)
go run ../../cmd/server/main.go

# In another terminal - run test suite
cd /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO
go test -v ./... -tags=staging

# Check metrics
curl http://localhost:9091/metrics
```

**When to use:**
- Integration testing
- Load testing & performance validation
- Regression test suite
- Multi-system orchestration testing
- Pre-production verification

**Do NOT:**
- Reset the database (persistent state)
- Delete logs without backup
- Deploy untested code

### PROD Environment (Production Dogfooding)

```bash
# Via foundation session (autonomous)
cd /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/environments/prod
source GAIA_GO.env

# Run self-improvement cycle (dogfooding)
./self_improve.sh

# Monitor in real-time
tail -f ./logs/gaia.log | grep -i "phase\|improvement\|error"

# Check health
curl http://localhost:8080/health
```

**Automatic operations:**
- Phase 1: Self-analysis & diagnostics
- Phase 2: Issue detection
- Phase 3: Task generation
- Phase 4: Fix execution
- Phase 5: Verification testing
- Phase 6: Metrics reporting

**Do NOT manually:**
- Stop the server (foundation manages it)
- Reset database (mission-critical)
- Delete backups
- Edit configuration directly

## Environment Management Commands

### Check Status
```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/environments
./manage_environments.sh status
```

### Check Health
```bash
./manage_environments.sh health dev
./manage_environments.sh health staging
./manage_environments.sh health prod
```

### View Logs
```bash
./manage_environments.sh logs dev      # Last 100 lines (DEBUG)
./manage_environments.sh logs staging  # Last 100 lines (INFO)
./manage_environments.sh logs prod     # Last 100 lines (WARN)
```

### Backup All Environments
```bash
./manage_environments.sh backup
```

### Reset DEV (Safe)
```bash
./manage_environments.sh reset dev
```

## Key Configuration Differences

### Ports
- **DEV**: 8081 (localhost only)
- **STAGING**: 8082 (internal network)
- **PROD**: 8080 (production)

**Metrics Ports:**
- **DEV**: 9090
- **STAGING**: 9091
- **PROD**: 9092

### Logging
```
DEV:     Debug level, colorized, console + file (10M max)
STAGING: Info level, structured, file + metrics (50M max)
PROD:    Warn level, JSON, file + syslog (100M max)
```

### Database Behavior
```
DEV:     Auto-reset on error, auto-migrate, no backup
STAGING: Never reset, auto-migrate, daily backup (7 days)
PROD:    Never reset, locked, hourly backup (90 days)
```

### Self-Improvement
```
DEV:     Aggressive optimization, experimental features enabled
STAGING: Controlled optimization, experimental features disabled
PROD:    Aggressive optimization, dogfooding enabled, auto-deploy
```

## Session Integration

### foundation Session (GAIA_GO Orchestrator)

The **foundation** tmux session runs GAIA_GO in **PROD** environment with dogfooding:

```bash
# foundation session automatically:
cd /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/environments/prod
source GAIA_GO.env

# Runs continuous self-improvement cycle
while true; do
    ./self_improve.sh
    sleep 3600  # Run hourly
done
```

### basic_edu Session (App Coordinator)

The **basic_edu** session receives orchestrated tasks from GAIA_GO:
- Manages basic_edu app
- Executes tests via GAIA_GO
- Provides feedback to GAIA_GO
- Gets improvements from PROD

## Monitoring Dashboard

```bash
# Monitor all three environments simultaneously
watch -n 5 '
  echo "=== DEV (8081) ===" && curl -s http://localhost:8081/health && \
  echo "=== STAGING (8082) ===" && curl -s http://localhost:8082/health && \
  echo "=== PROD (8080) ===" && curl -s http://localhost:8080/health
'
```

## Disaster Recovery

### DEV Environment Failure
```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/environments/dev
./manage_environments.sh reset dev
# Restart DEV - fresh database created automatically
```

### STAGING Environment Failure
```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/environments/staging
# Restore from daily backup
cp data/backups/staging_gaia.db.backup data/staging_gaia.db
# Verify with full test suite
go test -v ./... -tags=staging
```

### PROD Environment Failure
```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/environments/prod
# Restore from hourly backup
cp data/backups/prod_gaia.db.backup_latest data/prod_gaia.db
# foundation session auto-recovers
```

## Next Steps

1. ✅ Multi-environment structure created
2. ✅ Configuration files generated
3. ✅ Environment management script ready
4. ▶️ **foundation** session runs PROD environment
5. ▶️ **basic_edu** session receives orchestrated tasks
6. ▶️ Monitor health checks across all environments
7. ▶️ Verify dogfooding cycle in PROD

---

**Status**: ✅ Multi-Environment Setup Complete
**Environments**: 3 (Dev, Staging, Prod)
**Isolation**: Complete
**Dogfooding**: Enabled in PROD
**Management**: Automated via manage_environments.sh
