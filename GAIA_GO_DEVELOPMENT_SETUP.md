# GAIA_GO Development Setup

## Overview

GAIA_GO is the unified Go-based backend system for the Architect Dashboard, replacing the Python-based architecture with a high-performance, concurrent system designed for production at scale.

**Branch**: `feature/gaia-go-dev-0301`
**Environment**: Isolated development environment with separate database and configuration

## Development Environment Setup

### Prerequisites

- Go 1.21+
- SQLite (for development)
- PostgreSQL (for staging/production)
- Docker (optional, for containerized testing)

### Quick Start

```bash
# 1. Switch to dev branch
git checkout feature/gaia-go-dev-0301

# 2. Install dependencies
cd pyWork/GAIA_GO
go mod download
go mod tidy

# 3. Load development environment
source .env.dev  # Linux/Mac
# or set environment variables on Windows

# 4. Initialize development database
go run ./cmd/migrate -env=dev

# 5. Start development server
go run ./cmd/gaia-server -env=dev
# Server runs on http://localhost:8090
```

### Environment Files

| File | Purpose | Database |
|------|---------|----------|
| `.env.dev` | Development (active work) | `data/gaia_dev.db` |
| `.env.staging` | Staging (pre-production testing) | `data/gaia_staging.db` |
| `.env.prod` | Production (live system) | PostgreSQL (external) |

### Directory Structure

```
pyWork/GAIA_GO/
├── cmd/                           # Executable entry points
│   ├── gaia-server/              # Main API server
│   ├── gaia-cli/                 # CLI tool
│   └── migrate/                  # Database migrations
├── pkg/
│   ├── services/                 # Business logic services
│   │   ├── rate_limiting/        # Rate limiting system
│   │   ├── appeal/               # Appeal management
│   │   ├── negotiation/          # Appeal negotiation
│   │   ├── auth/                 # Authentication
│   │   └── ...
│   ├── models/                   # Data models
│   ├── repository/               # Data access layer
│   ├── middleware/               # HTTP middleware
│   └── utils/                    # Utility functions
├── api/                          # API definitions (OpenAPI/Swagger)
├── migrations/                   # Database migration scripts
├── tests/                        # Test files
├── docs/                         # Documentation
├── data/
│   ├── gaia_dev.db              # Development database
│   ├── gaia_staging.db          # Staging database
│   └── backups/                 # Database backups
├── logs/
│   ├── gaia_dev.log             # Development logs
│   └── gaia_staging.log         # Staging logs
├── go.mod                        # Go module definition
├── go.sum                        # Go dependency checksums
└── Makefile                      # Build automation
```

## Development Workflow

### 1. Making Code Changes

```bash
# Create feature branch off dev branch
git checkout feature/gaia-go-dev-0301
git checkout -b fix/some-issue

# Make changes
nano pkg/services/rate_limiting/service.go

# Run tests frequently
go test ./pkg/services/rate_limiting/...

# Run the dev server with auto-reload (if available)
go run ./cmd/gaia-server -env=dev
```

### 2. Testing Changes

```bash
# Unit tests
go test ./...

# Integration tests (requires db)
go test -tags=integration ./tests/...

# Specific test
go test -run TestAppealsService ./pkg/services/appeal/...

# With coverage
go test -cover ./...
```

### 3. Database Changes

```bash
# Create new migration
go run ./cmd/migrate -create -name=add_new_field

# Run pending migrations
go run ./cmd/migrate -env=dev

# Rollback last migration
go run ./cmd/migrate -env=dev -rollback

# Check migration status
go run ./cmd/migrate -env=dev -status
```

### 4. Committing Work

```bash
# Stage changes
git add .

# Commit with message
git commit -m "feat: implement appeal bulk operations system

- Add BulkOperationsService for batch operations
- Implement approval/denial workflows
- Add progress tracking and error handling
- Tests cover happy path and error scenarios"

# Push to feature branch
git push origin fix/some-issue

# Create pull request to feature/gaia-go-dev-0301
# Merge after review and CI passes
```

## Key Development Features

### 1. Hot Reload
- Changes to Go source files trigger automatic rebuild
- Server restarts with new code
- Useful for rapid iteration

### 2. Detailed Logging
- `DEBUG=true` enables verbose logging
- `LOG_LEVEL=DEBUG` captures all events
- Logs written to `logs/gaia_dev.log`

### 3. Database Profiling
- `ENABLE_PROFILING=true` captures query performance
- Helps identify bottlenecks
- View metrics at `/api/metrics/db`

### 4. Detailed Errors
- `ENABLE_DETAILED_ERRORS=true` shows full stack traces
- Includes variable values and context
- Never enable in production

## Current Development Status

### Active Components (Phase 2)
- ✅ Rate Limiting System
- ✅ Appeal Management Service
- ✅ Admin Bulk Operations
- 🔄 Appeal Negotiation Service (in progress)
- 📋 WebSocket Real-time Updates (planned)

### Completed Phases
- ✅ Phase 1: Foundation (core services, database models)
- ✅ Phase 2: Advanced Features (bulk operations, rate limiting)
- 📋 Phase 3: Distributed System (load balancing, clustering)
- 📋 Phase 4: Production Hardening (monitoring, security)

### Next Immediate Tasks
1. Complete appeal negotiation service
2. Add comprehensive test suite
3. Implement WebSocket support
4. Performance optimization and benchmarking

## Monitoring Development Progress

### Check Current Session Status
```bash
tmux list-sessions
# Look for 'inspector' session - handles GAIA_GO Phase 2
```

### View Real-time Progress
```bash
# Stream live progress updates
bash /tmp/live_progress.sh
# Shows all 6 sessions including inspector (GAIA_GO work)
```

### Check Available Tasks
```bash
# View task queue and assignments
python3 workers/assigner_worker.py --prompts

# Look for inspector session assignments
python3 workers/assigner_worker.py --sessions | grep inspector
```

## Integration with Main Dashboard

GAIA_GO will eventually replace the Python backend. Current integration:

- **Phase 2 (Current)**: GAIA_GO coexists with Python backend
- **Phase 3**: Gradual API cutover to GAIA_GO
- **Phase 4**: Full production deployment

During development:
- Python dashboard remains operational
- GAIA_GO API available at `http://localhost:8090` (dev)
- Can test both systems simultaneously

## Troubleshooting

### Port Already in Use
```bash
# Find process using port 8090
lsof -i :8090

# Kill process
kill -9 <PID>

# Or change port in .env.dev
GAIA_PORT=8092
```

### Database Locked
```bash
# Remove lock file
rm data/gaia_dev.db-wal
rm data/gaia_dev.db-shm

# Or reset database
rm data/gaia_dev.db
go run ./cmd/migrate -env=dev  # Creates new database
```

### Import Issues
```bash
# Verify Go module setup
go mod verify

# Update dependencies
go get -u ./...

# Clean cache
go clean -cache
```

## Resources

- **CLAUDE.md**: Session delegation and architecture guidelines
- **docs/**: Additional documentation in GAIA_GO directory
- **tests/**: Example test patterns and integration tests
- **pkg/services/**: Service layer implementation reference

## Contact & Support

For issues or questions:
1. Check existing documentation in `docs/`
2. Review test files for usage examples
3. Check tmux session `inspector` for current work
4. Review recent commits for implementation patterns
