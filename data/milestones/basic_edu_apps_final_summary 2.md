# Basic_Edu_Apps_Final - Milestone Plan

Generated: 2026-02-10 06:22:06

## Summary

- Total Tasks: 693
- Total Milestones: 26
- Estimated Total Hours: 910.0
- Estimated Duration: 20.0 days

## Task Breakdown

### By Category
- Bug: 84
- Documentation: 26
- Feature: 226
- Test: 357

### By Priority
- Priority 1: 15
- Priority 2: 154
- Priority 3: 482
- Priority 4: 42

## Milestones

### 1. Basic_Edu_Apps_Final - Planning & Setup
- Phase: Planning
- Start: 2026-02-10
- Target: 2026-02-13
- Tasks: 11
- Estimated Hours: 29.0

**Tasks:**
- [S] Update documentation
- [S] **Fix** Clarify HTTPS cert handling: tolerate missing `cert.pem`/`key.pem`, make the copy-from-`read
- [S] **Fix** Investigate sandbox port errors (`[Errno 1] Operation not permitted`) and document a reliabl
- [S] **Fix** Clarify HTTPS cert handling: tolerate missing `cert.pem`/`key.pem`, make the copy-from-`read
- [S] **Fix** Investigate sandbox port errors (`[Errno 1] Operation not permitted`) and document a reliabl
- [M] **Setup** Create Playwright/Selenium tests for critical user flows.
- [M] **Setup** Create Playwright/Selenium tests for critical user flows.
- [M] **Setup** Create Playwright/Selenium tests for critical user flows.
- [M] **Setup** Create Playwright/Selenium tests for critical user flows.
- [M] **Setup** Create Playwright/Selenium tests for critical user flows.
- ... and 1 more

### 2. Basic_Edu_Apps_Final - Development Phase 1
- Phase: Development
- Start: 2026-02-10
- Target: 2026-02-17
- Tasks: 10
- Estimated Hours: 46.0

**Tasks:**
- [M] Create runbook for troubleshooting
- [M] Create team training materials
- [S] Update `LLMClient.__init__` to use failover client
- [S] Add feature flag: `LLM_FAILOVER_ENABLED`
- [S] Add circuit breaker status checks when selecting sessions
- [S] Add provider-specific routing rules
- [S] Update CLAUDE.md with failover section
- [S] Add provider selection guide
- [C] **Upgrade** Rebuild features tracking with status workflow (spec → in progress → completed)
- [C] **Feature** Add streak/goal system for daily reading goals

### 3. Basic_Edu_Apps_Final - Development Phase 2
- Phase: Development
- Start: 2026-02-17
- Target: 2026-03-09
- Tasks: 10
- Estimated Hours: 160.0

**Tasks:**
- [C] **Upgrade** Rebuild features tracking with status workflow (spec → in progress → completed)
- [C] **Feature** Add streak/goal system for daily reading goals
- [C] **Upgrade** Rebuild features tracking with status workflow (spec → in progress → completed)
- [C] **Feature** Add streak/goal system for daily reading goals
- [C] **Upgrade** Rebuild features tracking with status workflow (spec → in progress → completed)
- [C] **Feature** Add streak/goal system for daily reading goals
- [C] **Upgrade** Rebuild features tracking with status workflow (spec → in progress → completed)
- [C] **Feature** Add streak/goal system for daily reading goals
- [C] **Upgrade** Rebuild features tracking with status workflow (spec → in progress → completed)
- [C] **Feature** Add streak/goal system for daily reading goals

### 4. Basic_Edu_Apps_Final - Development Phase 3
- Phase: Development
- Start: 2026-02-24
- Target: 2026-03-03
- Tasks: 10
- Estimated Hours: 40.0

**Tasks:**
- [M] **Upgrade** Centralize analytics ingest: write summarized metrics into `education_central.db` when a
- [M] **Upgrade** Replace hard-coded hosts/ports (`100.112.58.92`, etc.) with env/config plus `url_for`, a
- [M] **Upgrade** Propagate authenticated users: when Google OAuth completes, create/sync the user across 
- [M] **Upgrade** Persist user identity consistently: reuse the unified session (or a shared cookie) inste
- [M] **Upgrade** Store question/answer detail in a normalized form and surface remediation suggestions fo
- [M] **Upgrade** Capture per-note timing and mistakes as a first-class table to enable analytics and feed
- [M] **Upgrade** Wire apps to the MCP layer (`/mcp`): use `POST /mcp/users` and `POST /mcp/skill-events` 
- [M] **Upgrade** Harden process launcher (`app_launcher.py`/`main_app.py`): stream stdout/stderr or log t
- [M] **Upgrade** Make git branch info clickable with links to commit history
- [M] **Upgrade** Link features to related TODOs and commits

### 5. Basic_Edu_Apps_Final - Development Phase 4
- Phase: Development
- Start: 2026-03-03
- Target: 2026-03-10
- Tasks: 10
- Estimated Hours: 40.0

**Tasks:**
- [M] **Feature** Build skill progression: isolated words → phrases → sentences → passages
- [M] **Upgrade** Centralize analytics ingest: write summarized metrics into `education_central.db` when a
- [M] **Upgrade** Replace hard-coded hosts/ports (`100.112.58.92`, etc.) with env/config plus `url_for`, a
- [M] **Upgrade** Propagate authenticated users: when Google OAuth completes, create/sync the user across 
- [M] **Upgrade** Persist user identity consistently: reuse the unified session (or a shared cookie) inste
- [M] **Upgrade** Store question/answer detail in a normalized form and surface remediation suggestions fo
- [M] **Upgrade** Capture per-note timing and mistakes as a first-class table to enable analytics and feed
- [M] **Upgrade** Wire apps to the MCP layer (`/mcp`): use `POST /mcp/users` and `POST /mcp/skill-events` 
- [M] **Upgrade** Harden process launcher (`app_launcher.py`/`main_app.py`): stream stdout/stderr or log t
- [M] **Upgrade** Make git branch info clickable with links to commit history

### 6. Basic_Edu_Apps_Final - Development Phase 5
- Phase: Development
- Start: 2026-03-10
- Target: 2026-03-17
- Tasks: 10
- Estimated Hours: 40.0

**Tasks:**
- [M] **Upgrade** Link features to related TODOs and commits
- [M] **Feature** Build skill progression: isolated words → phrases → sentences → passages
- [M] **Upgrade** Centralize analytics ingest: write summarized metrics into `education_central.db` when a
- [M] **Upgrade** Replace hard-coded hosts/ports (`100.112.58.92`, etc.) with env/config plus `url_for`, a
- [M] **Upgrade** Propagate authenticated users: when Google OAuth completes, create/sync the user across 
- [M] **Upgrade** Persist user identity consistently: reuse the unified session (or a shared cookie) inste
- [M] **Upgrade** Store question/answer detail in a normalized form and surface remediation suggestions fo
- [M] **Upgrade** Capture per-note timing and mistakes as a first-class table to enable analytics and feed
- [M] **Upgrade** Wire apps to the MCP layer (`/mcp`): use `POST /mcp/users` and `POST /mcp/skill-events` 
- [M] **Upgrade** Harden process launcher (`app_launcher.py`/`main_app.py`): stream stdout/stderr or log t

### 7. Basic_Edu_Apps_Final - Development Phase 6
- Phase: Development
- Start: 2026-03-17
- Target: 2026-03-24
- Tasks: 10
- Estimated Hours: 40.0

**Tasks:**
- [M] **Upgrade** Make git branch info clickable with links to commit history
- [M] **Upgrade** Link features to related TODOs and commits
- [M] **Feature** Build skill progression: isolated words → phrases → sentences → passages
- [M] **Upgrade** Centralize analytics ingest: write summarized metrics into `education_central.db` when a
- [M] **Upgrade** Replace hard-coded hosts/ports (`100.112.58.92`, etc.) with env/config plus `url_for`, a
- [M] **Upgrade** Propagate authenticated users: when Google OAuth completes, create/sync the user across 
- [M] **Upgrade** Persist user identity consistently: reuse the unified session (or a shared cookie) inste
- [M] **Upgrade** Store question/answer detail in a normalized form and surface remediation suggestions fo
- [M] **Upgrade** Capture per-note timing and mistakes as a first-class table to enable analytics and feed
- [M] **Upgrade** Wire apps to the MCP layer (`/mcp`): use `POST /mcp/users` and `POST /mcp/skill-events` 

### 8. Basic_Edu_Apps_Final - Development Phase 7
- Phase: Development
- Start: 2026-03-24
- Target: 2026-03-31
- Tasks: 10
- Estimated Hours: 40.0

**Tasks:**
- [M] **Upgrade** Harden process launcher (`app_launcher.py`/`main_app.py`): stream stdout/stderr or log t
- [M] **Upgrade** Make git branch info clickable with links to commit history
- [M] **Upgrade** Link features to related TODOs and commits
- [M] **Feature** Build skill progression: isolated words → phrases → sentences → passages
- [M] **Upgrade** Centralize analytics ingest: write summarized metrics into `education_central.db` when a
- [M] **Upgrade** Replace hard-coded hosts/ports (`100.112.58.92`, etc.) with env/config plus `url_for`, a
- [M] **Upgrade** Propagate authenticated users: when Google OAuth completes, create/sync the user across 
- [M] **Upgrade** Persist user identity consistently: reuse the unified session (or a shared cookie) inste
- [M] **Upgrade** Store question/answer detail in a normalized form and surface remediation suggestions fo
- [M] **Upgrade** Capture per-note timing and mistakes as a first-class table to enable analytics and feed

### 9. Basic_Edu_Apps_Final - Development Phase 8
- Phase: Development
- Start: 2026-03-31
- Target: 2026-04-07
- Tasks: 10
- Estimated Hours: 40.0

**Tasks:**
- [M] **Upgrade** Wire apps to the MCP layer (`/mcp`): use `POST /mcp/users` and `POST /mcp/skill-events` 
- [M] **Upgrade** Harden process launcher (`app_launcher.py`/`main_app.py`): stream stdout/stderr or log t
- [M] **Upgrade** Make git branch info clickable with links to commit history
- [M] **Upgrade** Link features to related TODOs and commits
- [M] **Feature** Build skill progression: isolated words → phrases → sentences → passages
- [M] **Upgrade** Centralize analytics ingest: write summarized metrics into `education_central.db` when a
- [M] **Upgrade** Replace hard-coded hosts/ports (`100.112.58.92`, etc.) with env/config plus `url_for`, a
- [M] **Upgrade** Propagate authenticated users: when Google OAuth completes, create/sync the user across 
- [M] **Upgrade** Persist user identity consistently: reuse the unified session (or a shared cookie) inste
- [M] **Upgrade** Store question/answer detail in a normalized form and surface remediation suggestions fo

### 10. Basic_Edu_Apps_Final - Development Phase 9
- Phase: Development
- Start: 2026-04-07
- Target: 2026-04-14
- Tasks: 10
- Estimated Hours: 40.0

**Tasks:**
- [M] **Upgrade** Capture per-note timing and mistakes as a first-class table to enable analytics and feed
- [M] **Upgrade** Wire apps to the MCP layer (`/mcp`): use `POST /mcp/users` and `POST /mcp/skill-events` 
- [M] **Upgrade** Harden process launcher (`app_launcher.py`/`main_app.py`): stream stdout/stderr or log t
- [M] **Upgrade** Make git branch info clickable with links to commit history
- [M] **Upgrade** Link features to related TODOs and commits
- [M] **Feature** Build skill progression: isolated words → phrases → sentences → passages
- [M] Create project structure
- [M] Implement Google Sheets service with:
- [M] Create SQLite database models
- [M] Build sync mechanism (Sheets ↔ Local DB)

### 11. Basic_Edu_Apps_Final - Development Phase 10
- Phase: Development
- Start: 2026-04-14
- Target: 2026-04-21
- Tasks: 10
- Estimated Hours: 40.0

**Tasks:**
- [M] Create new project: "Property Management"
- [M] Create Service Account:
- [M] Create feature branch: `feature/git-workflow-enforcement-0207`
- [M] Create project structure
- [M] Implement db.py with connection management
- [M] Create app.py with auth and base routes
- [M] Build login.html and dashboard.html
- [M] Implement dataStore.js
- [M] Create `crawler_config.py` with Chrome profile detection
- [M] Create `crawler_service.py` with:

### 12. Basic_Edu_Apps_Final - Development Phase 11
- Phase: Development
- Start: 2026-04-21
- Target: 2026-04-28
- Tasks: 10
- Estimated Hours: 13.0

**Tasks:**
- [M] Create Chrome startup script
- [S] **Upgrade** Finalize `requirements.txt` (Flask version, psutil, sqlite helpers), add `make dev`/`mak
- [S] **Upgrade** Add real-time metrics updates (WebSocket or polling) instead of manual refresh
- [S] **Upgrade** Add TODO priority tagging and sorting
- [S] **Feature** Add sentence/passage mode with comprehension questions
- [S] **Feature** Add leveled curriculum with progression rules dashboard can surface
- [S] **Upgrade** Finalize `requirements.txt` (Flask version, psutil, sqlite helpers), add `make dev`/`mak
- [S] **Upgrade** Add real-time metrics updates (WebSocket or polling) instead of manual refresh
- [S] **Upgrade** Add TODO priority tagging and sorting
- [S] **Feature** Add sentence/passage mode with comprehension questions

### 13. Basic_Edu_Apps_Final - Development Phase 12
- Phase: Development
- Start: 2026-04-28
- Target: 2026-05-05
- Tasks: 10
- Estimated Hours: 10.0

**Tasks:**
- [S] **Feature** Add leveled curriculum with progression rules dashboard can surface
- [S] **Upgrade** Finalize `requirements.txt` (Flask version, psutil, sqlite helpers), add `make dev`/`mak
- [S] **Upgrade** Add real-time metrics updates (WebSocket or polling) instead of manual refresh
- [S] **Upgrade** Add TODO priority tagging and sorting
- [S] **Feature** Add sentence/passage mode with comprehension questions
- [S] **Feature** Add leveled curriculum with progression rules dashboard can surface
- [S] **Upgrade** Finalize `requirements.txt` (Flask version, psutil, sqlite helpers), add `make dev`/`mak
- [S] **Upgrade** Add real-time metrics updates (WebSocket or polling) instead of manual refresh
- [S] **Upgrade** Add TODO priority tagging and sorting
- [S] **Feature** Add sentence/passage mode with comprehension questions

### 14. Basic_Edu_Apps_Final - Development Phase 13
- Phase: Development
- Start: 2026-05-05
- Target: 2026-05-12
- Tasks: 10
- Estimated Hours: 10.0

**Tasks:**
- [S] **Feature** Add leveled curriculum with progression rules dashboard can surface
- [S] **Upgrade** Finalize `requirements.txt` (Flask version, psutil, sqlite helpers), add `make dev`/`mak
- [S] **Upgrade** Add real-time metrics updates (WebSocket or polling) instead of manual refresh
- [S] **Upgrade** Add TODO priority tagging and sorting
- [S] **Feature** Add sentence/passage mode with comprehension questions
- [S] **Feature** Add leveled curriculum with progression rules dashboard can surface
- [S] **Upgrade** Finalize `requirements.txt` (Flask version, psutil, sqlite helpers), add `make dev`/`mak
- [S] **Upgrade** Add real-time metrics updates (WebSocket or polling) instead of manual refresh
- [S] **Upgrade** Add TODO priority tagging and sorting
- [S] **Feature** Add sentence/passage mode with comprehension questions

### 15. Basic_Edu_Apps_Final - Development Phase 14
- Phase: Development
- Start: 2026-05-12
- Target: 2026-05-19
- Tasks: 10
- Estimated Hours: 10.0

**Tasks:**
- [S] **Feature** Add leveled curriculum with progression rules dashboard can surface
- [S] Update guides
- [S] Add detailed review prompts for Codex (backend) and Comet (UI)
- [S] Add automated validation steps
- [S] Add `session_pool` table (name, tmux_name, role, restart_count, health, etc.)
- [S] Add `pool_events` table (session_name, event_type, details, timestamp)
- [S] Add methods: `save_pool_member()`, `get_pool_members()`, `log_pool_event()`
- [S] Add `GET /api/comet/login-status` - all service statuses
- [S] Add `POST /api/comet/login-check` - trigger immediate check
- [S] Add `GET /api/comet/login-history` - recent check history

### 16. Basic_Edu_Apps_Final - Development Phase 15
- Phase: Development
- Start: 2026-05-19
- Target: 2026-05-26
- Tasks: 10
- Estimated Hours: 10.0

**Tasks:**
- [S] Add input channel for stdin injection
- [S] Add `extractionStore` field to `Extractor`
- [S] Add `sessionStore` field
- [S] Update session stats on completion
- [S] Adds elastic scaling for overflow workload
- [S] Add 15 tasks to queue
- [S] Add CSS variables for terminal font configuration
- [S] Add `font-variant-numeric: tabular-nums slashed-zero` for proper number alignment
- [S] Add scrollback selector dropdown (Current pane / 500 / 1000 / 3000 / Full history)
- [S] Add responsive breakpoints:

### 17. Basic_Edu_Apps_Final - Development Phase 16
- Phase: Development
- Start: 2026-05-26
- Target: 2026-06-02
- Tasks: 10
- Estimated Hours: 10.0

**Tasks:**
- [S] Add `ResizeObserver` to track terminal container dimensions
- [S] Add `crawl_results` table to database schema
- [S] Add `GET /api/crawl/<task_id>/result` endpoint
- [S] Add `GET /api/crawl/history` endpoint
- [S] Add database schema to `app.py`
- [S] Add API endpoints for results
- [S] TODO: Implement actual digit recognition using:
- [S] TODO: Implement YAML loading
- [S] TODO: Implement actual deployment
- [S] TODO: S TESTS

### 18. Basic_Edu_Apps_Final - Development Phase 17
- Phase: Development
- Start: 2026-06-02
- Target: 2026-06-09
- Tasks: 10
- Estimated Hours: 10.0

**Tasks:**
- [S] TODO: Check if task blocks others
- [S] TODO: Implement actual digit recognition using:
- [S] TODO: Implement actual digit recognition using:
- [S] TODO: Implement actual digit recognition using:
- [S] TODO: Implement YAML loading
- [S] TODO: Implement actual deployment
- [S] TODO: S TESTS
- [S] TODO: Implement YAML loading
- [S] TODO: Implement actual deployment
- [S] TODO: S TESTS

### 19. Basic_Edu_Apps_Final - Development Phase 18
- Phase: Development
- Start: 2026-06-09
- Target: 2026-06-16
- Tasks: 10
- Estimated Hours: 10.0

**Tasks:**
- [S] TODO: Implement YAML loading
- [S] TODO: Implement actual deployment
- [S] TODO: S TESTS
- [S] TODO: Implement\n    pass\n\n@app.route('/api/profile')\ndef profile():\n    return js
- [S] TODO: Implement YAML loading
- [S] TODO: Implement actual deployment
- [S] TODO: S TESTS
- [S] TODO: Implement\n    pass\n\n@app.route('/api/profile')\ndef profile():\n    return js
- [S] TODO: Implement YAML loading
- [S] TODO: Implement actual deployment

### 20. Basic_Edu_Apps_Final - Development Phase 19
- Phase: Development
- Start: 2026-06-16
- Target: 2026-06-28
- Tasks: 10
- Estimated Hours: 100.0

**Tasks:**
- [S] TODO: S TESTS
- [S] TODO: Check if task blocks others
- [S] TODO: Implement\n    pass\n\n@app.route('/api/profile')\ndef profile():\n    return js
- [S] TODO: Implement\n    pass\n\n@app.route('/api/profile')\ndef profile():\n    return js
- [C] **Wish** Add leveled passages with comprehension checks and a simple streak/goal system so students 
- [C] **Wish** Add leveled passages with comprehension checks and a simple streak/goal system so students 
- [C] **Wish** Add leveled passages with comprehension checks and a simple streak/goal system so students 
- [C] **Wish** Add leveled passages with comprehension checks and a simple streak/goal system so students 
- [C] **Wish** Add leveled passages with comprehension checks and a simple streak/goal system so students 
- [C] **Wish** Add leveled passages with comprehension checks and a simple streak/goal system so students 

### 21. Basic_Edu_Apps_Final - Development Phase 20
- Phase: Development
- Start: 2026-06-23
- Target: 2026-06-30
- Tasks: 10
- Estimated Hours: 40.0

**Tasks:**
- [M] **Upgrade** Tighten result storage: store expected vs recognized words in a separate table with per-
- [M] **Wish** Build a leveled curriculum/course plan (sight words through multisyllabic) with progression
- [M] **Upgrade** Tighten result storage: store expected vs recognized words in a separate table with per-
- [M] **Wish** Build a leveled curriculum/course plan (sight words through multisyllabic) with progression
- [M] **Upgrade** Tighten result storage: store expected vs recognized words in a separate table with per-
- [M] **Wish** Build a leveled curriculum/course plan (sight words through multisyllabic) with progression
- [M] **Upgrade** Tighten result storage: store expected vs recognized words in a separate table with per-
- [M] **Wish** Build a leveled curriculum/course plan (sight words through multisyllabic) with progression
- [M] **Upgrade** Tighten result storage: store expected vs recognized words in a separate table with per-
- [M] **Wish** Build a leveled curriculum/course plan (sight words through multisyllabic) with progression

### 22. Basic_Edu_Apps_Final - Development Phase 21
- Phase: Development
- Start: 2026-06-30
- Target: 2026-07-07
- Tasks: 10
- Estimated Hours: 16.0

**Tasks:**
- [M] **Upgrade** Tighten result storage: store expected vs recognized words in a separate table with per-
- [M] **Wish** Build a leveled curriculum/course plan (sight words through multisyllabic) with progression
- [S] **Wish** Add a user-facing profile/progress view that merges stats across typing/math/reading/piano 
- [S] **Wish** Add guided practice plans (e.g., accuracy-first then speed drills) with milestone badges/ex
- [S] **Wish** Add adaptive practice modes (spaced repetition pacing + mixed-operations challenges) with p
- [S] **Wish** Add practice playlists (left/right/both hand drills) with progress meters and downloadable 
- [S] **Wish** Add a user-facing profile/progress view that merges stats across typing/math/reading/piano 
- [S] **Wish** Add guided practice plans (e.g., accuracy-first then speed drills) with milestone badges/ex
- [S] **Wish** Add adaptive practice modes (spaced repetition pacing + mixed-operations challenges) with p
- [S] **Wish** Add practice playlists (left/right/both hand drills) with progress meters and downloadable 

### 23. Basic_Edu_Apps_Final - Development Phase 22
- Phase: Development
- Start: 2026-07-07
- Target: 2026-07-14
- Tasks: 10
- Estimated Hours: 10.0

**Tasks:**
- [S] **Wish** Add a user-facing profile/progress view that merges stats across typing/math/reading/piano 
- [S] **Wish** Add guided practice plans (e.g., accuracy-first then speed drills) with milestone badges/ex
- [S] **Wish** Add adaptive practice modes (spaced repetition pacing + mixed-operations challenges) with p
- [S] **Wish** Add practice playlists (left/right/both hand drills) with progress meters and downloadable 
- [S] **Wish** Add a user-facing profile/progress view that merges stats across typing/math/reading/piano 
- [S] **Wish** Add guided practice plans (e.g., accuracy-first then speed drills) with milestone badges/ex
- [S] **Wish** Add adaptive practice modes (spaced repetition pacing + mixed-operations challenges) with p
- [S] **Wish** Add practice playlists (left/right/both hand drills) with progress meters and downloadable 
- [S] **Wish** Add a user-facing profile/progress view that merges stats across typing/math/reading/piano 
- [S] **Wish** Add guided practice plans (e.g., accuracy-first then speed drills) with milestone badges/ex

### 24. Basic_Edu_Apps_Final - Development Phase 23
- Phase: Development
- Start: 2026-07-14
- Target: 2026-07-21
- Tasks: 6
- Estimated Hours: 6.0

**Tasks:**
- [S] **Wish** Add adaptive practice modes (spaced repetition pacing + mixed-operations challenges) with p
- [S] **Wish** Add practice playlists (left/right/both hand drills) with progress meters and downloadable 
- [S] **Wish** Add a user-facing profile/progress view that merges stats across typing/math/reading/piano 
- [S] **Wish** Add guided practice plans (e.g., accuracy-first then speed drills) with milestone badges/ex
- [S] **Wish** Add adaptive practice modes (spaced repetition pacing + mixed-operations challenges) with p
- [S] **Wish** Add practice playlists (left/right/both hand drills) with progress meters and downloadable 

### 25. Basic_Edu_Apps_Final - Bug Fixes
- Phase: Development
- Start: 2026-07-21
- Target: 2026-07-28
- Tasks: 15
- Estimated Hours: 60.0

**Tasks:**
- [M] **Fix** Serve templates without string-munging: render via blueprints with correct `static_url_path`
- [M] **Fix** Dashboard template/static resolution in `unified_app.py` to consistently load from `dashboar
- [M] **Fix** Central DB schema drift: align `education_central.db` initialization between `unified_app.py
- [M] **Fix** Anchor DB path to the module directory to avoid creating stray `typing.db` files when runnin
- [M] **Fix** Align math schema/file (`math/math_practice.db`) used by `math/app.py`, `unified_app.py` `/m
- [M] **Fix** Create/use the questions detail table expected by `unified_app.py` (currently writes to `que
- [M] **Fix** Resolve session defaulting: index route hard-codes `user_id = 1`; look up/create the guest u
- [M] **Fix** Move `/reading/api/*` endpoints onto the blueprint used by the unified server so per-app and
- [M] **Fix** Mount `/piano/api/*` on the blueprint used by `unified_app.py`, and anchor `piano.db` to the
- [M] **Fix** Serve templates without string-munging: render via blueprints with correct `static_url_path`
- ... and 5 more

### 26. Basic_Edu_Apps_Final - Testing
- Phase: Testing
- Start: 2026-02-24
- Target: 2026-03-01
- Tasks: 10
- Estimated Hours: 40.0

**Tasks:**
- [M] **Setup** Create Playwright/Selenium tests for critical user flows.
- [M] **Setup** Create Playwright/Selenium tests for critical user flows.
- [M] **Setup** Create Playwright/Selenium tests for critical user flows.
- [M] **Setup** Create Playwright/Selenium tests for critical user flows.
- [M] **Setup** Create Playwright/Selenium tests for critical user flows.
- [M] **Setup** Create Playwright/Selenium tests for critical user flows.
- [M] **Fix** Unify typing persistence: standardize on `typing/typing.db` schema and align inserts/queries
- [M] **Test** Form validation: ensure required fields show errors, invalid inputs are rejected, and succe
- [M] **Test** Score/streak tracking: ensure correct answers increment scores and streaks reset on errors.
- [M] **Test** Backend error logging: cause 500 errors and verify they're written to errors.md with stack 
