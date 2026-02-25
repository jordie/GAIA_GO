# Mentor_V2 - Milestone Plan

Generated: 2026-02-10 06:22:07

## Summary

- Total Tasks: 70
- Total Milestones: 9
- Estimated Total Hours: 130.0
- Estimated Duration: 5.0 days

## Task Breakdown

### By Category
- Documentation: 2
- Feature: 65
- Test: 3

### By Priority
- Priority 1: 9
- Priority 3: 61

## Milestones

### 1. Mentor_V2 - Planning & Setup
- Phase: Planning
- Start: 2026-02-10
- Target: 2026-02-13
- Tasks: 2
- Estimated Hours: 2.0

**Tasks:**
- [S] Update documentation
- [S] Updated **README.md** with new features

### 2. Mentor_V2 - Development Phase 1
- Phase: Development
- Start: 2026-02-10
- Target: 2026-02-17
- Tasks: 10
- Estimated Hours: 22.0

**Tasks:**
- [M] Create runbook for troubleshooting
- [M] Create team training materials
- [S] Update `LLMClient.__init__` to use failover client
- [S] Add feature flag: `LLM_FAILOVER_ENABLED`
- [S] Add circuit breaker status checks when selecting sessions
- [S] Add provider-specific routing rules
- [S] Update CLAUDE.md with failover section
- [S] Add provider selection guide
- [M] Create project structure
- [M] Implement Google Sheets service with:

### 3. Mentor_V2 - Development Phase 2
- Phase: Development
- Start: 2026-02-17
- Target: 2026-02-24
- Tasks: 10
- Estimated Hours: 40.0

**Tasks:**
- [M] Create SQLite database models
- [M] Build sync mechanism (Sheets ↔ Local DB)
- [M] Create new project: "Property Management"
- [M] Create Service Account:
- [M] Create feature branch: `feature/git-workflow-enforcement-0207`
- [M] Create project structure
- [M] Implement db.py with connection management
- [M] Create app.py with auth and base routes
- [M] Build login.html and dashboard.html
- [M] Implement dataStore.js

### 4. Mentor_V2 - Development Phase 3
- Phase: Development
- Start: 2026-02-24
- Target: 2026-03-03
- Tasks: 10
- Estimated Hours: 19.0

**Tasks:**
- [M] Create `crawler_config.py` with Chrome profile detection
- [M] Create `crawler_service.py` with:
- [M] Create Chrome startup script
- [S] Update guides
- [S] Add detailed review prompts for Codex (backend) and Comet (UI)
- [S] Add automated validation steps
- [S] Add `session_pool` table (name, tmux_name, role, restart_count, health, etc.)
- [S] Add `pool_events` table (session_name, event_type, details, timestamp)
- [S] Add methods: `save_pool_member()`, `get_pool_members()`, `log_pool_event()`
- [S] Add `GET /api/comet/login-status` - all service statuses

### 5. Mentor_V2 - Development Phase 4
- Phase: Development
- Start: 2026-03-03
- Target: 2026-03-10
- Tasks: 10
- Estimated Hours: 10.0

**Tasks:**
- [S] Add `POST /api/comet/login-check` - trigger immediate check
- [S] Add `GET /api/comet/login-history` - recent check history
- [S] Add input channel for stdin injection
- [S] Add `extractionStore` field to `Extractor`
- [S] Add `sessionStore` field
- [S] Update session stats on completion
- [S] Adds elastic scaling for overflow workload
- [S] Add 15 tasks to queue
- [S] Add CSS variables for terminal font configuration
- [S] Add `font-variant-numeric: tabular-nums slashed-zero` for proper number alignment

### 6. Mentor_V2 - Development Phase 5
- Phase: Development
- Start: 2026-03-10
- Target: 2026-03-17
- Tasks: 10
- Estimated Hours: 10.0

**Tasks:**
- [S] Add scrollback selector dropdown (Current pane / 500 / 1000 / 3000 / Full history)
- [S] Add responsive breakpoints:
- [S] Add `ResizeObserver` to track terminal container dimensions
- [S] Add `crawl_results` table to database schema
- [S] Add `GET /api/crawl/<task_id>/result` endpoint
- [S] Add `GET /api/crawl/history` endpoint
- [S] Add database schema to `app.py`
- [S] Add API endpoints for results
- [S] TODO: can't find libs here
- [S] TODO: rsync for better speed and disconnection imporvements

### 7. Mentor_V2 - Development Phase 6
- Phase: Development
- Start: 2026-03-17
- Target: 2026-03-24
- Tasks: 10
- Estimated Hours: 10.0

**Tasks:**
- [S] TODO: commandline copy files
- [S] TODO: sence usb stick and prompt for source
- [S] TODO: copy over files
- [S] TODO: refresh timer
- [S] TODO: delete files
- [S] TODO: clear trash
- [S] TODO: do multiple disks at the same time
- [S] TODO: prmp for name
- [S] TODO: sensor that runs once you start the app
- [S] TODO: screenshot of ls

### 8. Mentor_V2 - Development Phase 7
- Phase: Development
- Start: 2026-03-24
- Target: 2026-03-31
- Tasks: 5
- Estimated Hours: 5.0

**Tasks:**
- [S] TODO: print he stats for each (sources - bed, living)
- [S] TODO: add any errors here
- [S] TODO: set a future reminder to move drives
- [S] TODO: add any errors here
- [S] TODO: set a future reminder to move drives

### 9. Mentor_V2 - Testing
- Phase: Testing
- Start: 2026-02-24
- Target: 2026-03-01
- Tasks: 3
- Estimated Hours: 12.0

**Tasks:**
- [M] Create isolated test environment using env_manager.py
- [M] Create PR with comprehensive test results
- [M] Create test lead and campaign
