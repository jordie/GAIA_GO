# GAIA_GO Stable Releases

## Quick Start

### For Production (Stable)
```bash
# Switch to the stable Phase 9 release
git checkout stable-phase9

# Build the server
go build -o ./bin/server ./cmd/server

# Run the server
./bin/server
```

### For Development (Latest)
```bash
# Use the development branch for new features
git checkout feature/phase9-consolidation-0225

# Your changes won't affect the stable release
```

## Release Structure

- **`stable-phase9`** - Stable production branch, always ready to use
- **`feature/phase9-consolidation-*`** - Active development (may have breaking changes)
- **`v0.1.0-phase9`** - Release tag for this version

## Switching Between Versions

### Use Stable Release
```bash
git checkout stable-phase9
```

### Use Latest Development
```bash
git checkout feature/phase9-consolidation-0225
```

### Use Specific Tagged Release
```bash
git checkout v0.1.0-phase9
```

## What's Stable (v0.1.0-phase9)

✓ **Working Components:**
- Teacher Dashboard HTTP handlers
- Frustration detection engine
- Real-time metrics aggregation
- PostgreSQL persistence (GORM)
- Event-driven metrics pipeline
- Graceful shutdown and health checks

✗ **Not Yet Complete:**
- Distributed session coordination
- Task queue integration
- Session affinity scoring
- Auto-confirm patterns with AI fallback
- Rando inspector foundation integration
- Basic_edu integration

## Creating Features from Stable

If you want to add features on top of the stable release:

```bash
# Start from stable, not development
git checkout stable-phase9

# Create your feature branch
git checkout -b feature/my-feature-0225

# Make your changes, commit, and push
git add .
git commit -m "Add my feature"
```

## Environment Setup for Phase 9

### Required Environment Variables
```bash
# PostgreSQL connection
export DATABASE_URL="postgres://user:password@localhost:5432/gaia_go"

# Server configuration
export PORT=8080
```

### Database Requirements
- PostgreSQL 12+ (or compatible)
- Database created with name `gaia_go`
- Migrations automatically applied on startup

## Known Issues & Limitations

1. **Session Affinity**: Currently uses placeholder scoring (returns first available session)
2. **Distributed Consensus**: Raft integration incomplete - SessionCoordinator and TaskQueue not fully operational
3. **Auto-Confirm Patterns**: Not yet implemented - use manual approval for now

## Getting Help

### For Stable Release Issues
1. Check that you're on `stable-phase9` branch: `git branch`
2. Verify version: `git describe --tags --always`
3. See VERSION file for release notes: `cat VERSION`
4. Check server logs: `$GAIA_GO_HOME/logs/`

### For New Features or Development
- Work on `feature/phase9-consolidation-*` branches
- See CLAUDE.md for multi-session development guidelines
- Submit significant changes for review before merging to stable

## Next Steps (Phase 10)

The following features are in active development:

- [ ] Auto-confirm patterns with AI agent fallback
- [ ] Rando inspector foundation support
- [ ] Basic_edu integration
- [ ] Distributed session coordination
- [ ] Task queue management improvements

These will be released as `v0.1.1-phase9` and later in Phase 10 releases.

## Server API Reference

### Health Check
```bash
curl http://localhost:8080/health
# {"status":"healthy"}
```

### Teacher Dashboard Endpoints

**Classroom Metrics**
```bash
GET /api/dashboard/classroom/{classroomID}/metrics
GET /api/classrooms/{classroomID}/metrics
```

**Student Frustration**
```bash
GET /api/dashboard/student/frustration
GET /api/students/{studentID}/frustration
```

**Struggling Students**
```bash
GET /api/dashboard/struggling-students
GET /api/classrooms/{classroomID}/struggling-students
```

**Interventions**
```bash
POST /api/dashboard/interventions
POST /api/interventions/
```

**Dashboard Health**
```bash
GET /api/dashboard/health
```

## Version History

| Version | Release Date | Status | Phase | Notes |
|---------|------------|--------|-------|-------|
| v0.1.0-phase9 | 2026-02-25 | Stable | 9 | Initial Phase 9 release |

See VERSION file for detailed release notes.
