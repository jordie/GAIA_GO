# GAIA_GO Multi-Environment Architecture

## Overview

GAIA_GO runs three distinct environments with unique purposes, configurations, and lifecycles:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    GAIA_GO DEVELOPMENT PIPELINE                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  DEV (8081)              STAGING (8082)           PROD (8080)          │
│  └─────────────          └──────────────         └──────────           │
│   Rapid iteration        Pre-prod testing        Stable dogfooding     │
│   Experimental           Production-like         Self-improving        │
│   Frequent resets        Persistent data         Mission-critical      │
│   All features on        Selected features       Mature features       │
│                                                                         │
│    NEW FEATURES              VALIDATION            PRODUCTION           │
│    EXPERIMENTATION           INTEGRATION           DOGFOODING           │
│    BUG FIXES                 REGRESSION TESTS      SELF-IMPROVEMENT     │
│    OPTIMIZATIONS             LOAD TESTING          STABILITY            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Environment Characteristics

### DEV Environment

| Aspect | Configuration |
|--------|-----------------|
| **Port** | 8081 (localhost only) |
| **Database** | `dev_gaia.db` (can be reset) |
| **Stability** | Not guaranteed |
| **Features** | All experimental features enabled |
| **Logging** | DEBUG level, verbose |
| **Testing** | Auto-run on changes |
| **Database Reset** | YES on error |
| **Self-Improve** | Aggressive optimization |
| **Purpose** | Rapid development & experimentation |
| **Reset Frequency** | Multiple times per day |
| **Backup** | None required |
| **Users** | foundation (GAIA_GO) developers |

**Use Cases:**
- Test new Phase 8 subsystems
- Experiment with optimizations
- Debug issues with detailed logging
- Rapid iteration on features
- Try experimental configurations

**Workflow:**
```
Dev Feature Branch → Dev Environment Test → If successful → PR to Staging
```

---

### STAGING Environment

| Aspect | Configuration |
|--------|-----------------|
| **Port** | 8082 (network accessible) |
| **Database** | `staging_gaia.db` (persistent) |
| **Stability** | Must be stable |
| **Features** | Production-like subset |
| **Logging** | INFO level |
| **Testing** | Full regression test suite |
| **Database Reset** | NO |
| **Self-Improve** | Controlled optimization |
| **Purpose** | Pre-production validation |
| **Reset Frequency** | Stable, updated via PR merges |
| **Backup** | Daily backup |
| **Users** | QA, integration testing, validators |

**Use Cases:**
- Full integration testing
- Load testing & performance validation
- Regression test suite execution
- Production configuration testing
- Multi-system orchestration testing
- Canary deployments

**Workflow:**
```
Staging PR Merge → Deploy to Staging → Full Test Suite → If all pass → Deploy to Prod
```

---

### PROD Environment

| Aspect | Configuration |
|--------|-----------------|
| **Port** | 8080 (production) |
| **Database** | `prod_gaia.db` (mission-critical) |
| **Stability** | Guaranteed |
| **Features** | Mature, proven features only |
| **Logging** | WARN level (minimal overhead) |
| **Testing** | Health checks every 30s |
| **Database Reset** | NO (daily backups) |
| **Self-Improve** | Dogfooding - uses itself to improve |
| **Purpose** | Production orchestration & self-improvement |
| **Reset Frequency** | Never (continuous operation) |
| **Backup** | Hourly backup, 90-day retention |
| **Users** | foundation session (autonomous) |

**Use Cases:**
- Production orchestration of all systems
- Running 51 tmux sessions (full GAIA_GO)
- Self-improvement cycle (dogfooding)
- Real-world testing of improvements
- Autonomous system management
- Zero-downtime deployments

**Workflow:**
```
Prod Merge → Automated Deploy → Self-Analysis → Detect Issues → Auto-Fix → 
Deploy Improved Version → Verify → Repeat Continuously
```

---

## Directory Structure

```
/GAIA_GO/environments/
├── dev/
│   ├── GAIA_GO.env              # Dev configuration
│   ├── config/                  # Dev-specific configs
│   ├── data/                    # Dev database & state
│   │   └── dev_gaia.db
│   ├── logs/                    # Dev logs
│   └── bin/                     # Dev binaries
│
├── staging/
│   ├── GAIA_GO.env              # Staging configuration
│   ├── config/                  # Staging-specific configs
│   ├── data/                    # Staging database & state
│   │   └── staging_gaia.db
│   ├── logs/                    # Staging logs
│   └── bin/                     # Staging binaries
│
├── prod/
│   ├── GAIA_GO.env              # Production configuration
│   ├── config/                  # Prod-specific configs
│   ├── data/                    # Prod database & state
│   │   ├── prod_gaia.db         # Mission-critical
│   │   └── backups/             # Hourly backups
│   ├── logs/                    # Prod logs (90-day retention)
│   └── bin/                     # Prod binaries
│
└── ENVIRONMENT_MANIFEST.md      # This file
```

---

## Configuration Key Differences

### Logging

| Level | Dev | Staging | Prod |
|-------|-----|---------|------|
| **Format** | Verbose, colorized | Structured | JSON, minimal |
| **Output** | Console + File | File + Metrics | File + Syslog |
| **Retention** | 7 days | 30 days | 90 days |
| **Max Size** | 10M | 50M | 100M |

### Ports

```
DEV:     8081 (development only)
STAGING: 8082 (internal network)
PROD:    8080 (production)

METRICS:
DEV:     9090
STAGING: 9091
PROD:    9092
```

### Database Behavior

| Aspect | Dev | Staging | Prod |
|--------|-----|---------|------|
| **Reset on Error** | YES | NO | NO |
| **Auto Migrate** | YES | YES | NO |
| **Backup** | None | Daily | Hourly |
| **Backup Retention** | N/A | 7 days | 90 days |

### Self-Improvement Settings

| Feature | Dev | Staging | Prod |
|---------|-----|---------|------|
| **Enabled** | YES | YES | YES |
| **Auto Build** | YES | YES | YES |
| **Auto Test** | YES | YES | YES |
| **Auto Deploy** | NO | NO | YES |
| **Aggressive Opt** | YES | NO | YES |
| **Experimental** | YES | NO | NO |

---

## Environment Promotion Path

```
Feature Development
        ↓
   [DEV ENV]
   • Rapid iteration
   • All experiments
   • Frequent resets
        ↓
   Tests pass? Create PR
        ↓
   Code Review → Merge to main
        ↓
   [STAGING ENV]
   • Deploy automatically
   • Run full test suite
   • Integration tests
   • Load tests
        ↓
   All tests pass?
        ↓
   Auto-deploy to PROD
        ↓
   [PROD ENV]
   • Live orchestration
   • Self-improving
   • Dogfooding mode
   • Continuous monitoring
        ↓
   Improvements detected
        ↓
   Cycle repeats (autonomous)
```

---

## Running Each Environment

### DEV Environment
```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/environments/dev
source GAIA_GO.env
go run ../../../cmd/server/main.go
```

### STAGING Environment
```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/environments/staging
source GAIA_GO.env
go run ../../../cmd/server/main.go
```

### PROD Environment (via foundation session)
```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/environments/prod
source GAIA_GO.env
./self_improve.sh  # Dogfooding with auto-deployment
```

---

## Monitoring Each Environment

### Health Checks
```bash
# DEV
curl -v http://localhost:8081/health

# STAGING
curl -v http://localhost:8082/health

# PROD
curl -v http://localhost:8080/health
```

### Metrics (Prometheus)
```bash
# DEV
curl -v http://localhost:9090/metrics

# STAGING
curl -v http://localhost:9091/metrics

# PROD
curl -v http://localhost:9092/metrics
```

### Logs
```bash
# DEV - Real-time with DEBUG
tail -f /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/environments/dev/logs/gaia.log

# STAGING - Last 100 lines
tail -100 /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/environments/staging/logs/gaia.log

# PROD - Last 1000 lines with filtering
tail -1000 /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/environments/prod/logs/gaia.log | grep ERROR
```

---

## Environment Isolation

Each environment is **completely isolated**:
- ✅ Separate database files
- ✅ Separate ports
- ✅ Separate configuration
- ✅ Separate logs
- ✅ Separate binaries
- ✅ Separate data directories
- ✅ Separate metrics endpoints

**One environment failing does NOT affect others.**

---

## Disaster Recovery

### If DEV fails:
```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/environments/dev
rm data/dev_gaia.db
# Restart dev environment - fresh database
```

### If STAGING fails:
```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/environments/staging
# Restore from daily backup
cp data/backups/staging_gaia.db.backup data/staging_gaia.db
# Verify with full test suite
```

### If PROD fails:
```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/environments/prod
# Restore from hourly backup
cp data/backups/prod_gaia.db.$(date -u +%Y%m%d_%H) data/prod_gaia.db
# Verify all subsystems
# foundation session handles recovery automatically
```

---

## Best Practices

1. **Always test in DEV first** - Experiment freely
2. **Run staging for 24h before prod** - Stability validation
3. **PROD is for dogfooding** - Uses itself to improve
4. **Automate the promotion** - Dev → Staging → Prod
5. **Monitor all three** - Health checks every environment
6. **Backup PROD hourly** - Mission-critical data
7. **Never reset STAGING/PROD** - Persistent state matters
8. **Use different databases** - Complete isolation

---

**Status**: ✅ Multi-Environment Architecture Configured
**Environments**: 3 (Dev, Staging, Prod)
**Isolation**: Complete
**Dogfooding**: Enabled in PROD
