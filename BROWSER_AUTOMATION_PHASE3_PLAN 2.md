# Browser Automation Phase 3 - Execution Loop

## Implementation Plan

**Timeline:** Weeks 4-5 (after Phase 1 & 2 completion)
**Scope:** Orchestrate extraction → decision → execution cycle
**Target Completion:** Full end-to-end browser automation
**Success Criteria:** 90%+ task completion rate across 5 parallel environments

---

## Overview

Phase 3 integrates all prior components into a complete autonomous browser automation system:

```
Phase 1              Phase 2A              Phase 2B              Phase 3
HTML Extractor   +   Decision Router   +   Cache System    =   Execution Loop
(Extract)            (Route)              (Optimize)           (Orchestrate)
   │                    │                    │                    │
   └────────────────────┴────────────────────┴────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │ Execution Runner   │
                    │ Main Loop Logic    │
                    └────────────────────┘
```

---

## Components to Build

### Component 1: Execution Runner
**File:** `workers/browser_automation/runner.py`
**Lines:** ~400-500
**Purpose:** Main loop that chains all components together

#### Core Loop Logic
```python
def run_task(goal, site_url, max_steps=20, browser_type='selenium'):
    """
    Main execution loop for browser automation.

    Flow:
    1. Initialize browser
    2. Navigate to site
    3. Check cache for known path
    4. If cached & recent success: replay path (skip AI)
    5. If no cache: extract elements
    6. Route to appropriate AI (Ollama/Claude/Codex/Gemini)
    7. Execute decision
    8. Wait for page load
    9. Check goal completion
    10. Loop or exit
    """
```

#### Key Methods
```python
class BrowserExecutor:
    def __init__(self, cache_manager, decision_router, extractor):
        self.cache = cache_manager
        self.router = decision_router
        self.extractor = extractor
        self.browser = None
        self.execution_log = []

    def run_task(self, goal, site_url, max_steps=20):
        """Execute task end-to-end"""

    def _check_cache(self, domain, goal_type):
        """Check if path is cached"""

    def _execute_cached_path(self, path):
        """Replay cached navigation steps"""

    def _extract_and_decide(self, goal):
        """Extract elements and route to AI"""

    def _execute_action(self, action):
        """Execute the AI-decided action"""

    def _wait_for_page_load(self, timeout=5):
        """Wait for page transitions"""

    def _check_goal_completion(self, goal):
        """Verify if goal is achieved"""

    def _save_successful_path(self, steps):
        """Cache successful execution for replay"""
```

#### Termination Conditions
```python
# Task completes when any of these occur:
- Goal completion indicator found (success)
- Max steps reached (20 default)
- Unrecoverable error (site down, access denied)
- AI reports inability to proceed
- Same page detected 3x in row (loop detection)
- User timeout exceeded
```

---

### Component 2: Task Coordinator
**File:** `workers/browser_automation/coordinator.py`
**Lines:** ~300-400
**Purpose:** Manage multiple parallel browser tasks

#### Multi-Task Orchestration
```python
class TaskCoordinator:
    """
    Coordinate multiple browser automation tasks.
    Run up to 10 tasks in parallel across different browser sessions.
    """

    def __init__(self, max_concurrent=10):
        self.tasks = {}  # task_id -> task_state
        self.browsers = {}  # browser_id -> BrowserExecutor
        self.results = {}  # task_id -> result

    def submit_task(self, goal, site_url, priority=5):
        """Queue a new browser automation task"""

    def get_task_status(self, task_id):
        """Get current task status"""

    def cancel_task(self, task_id):
        """Cancel in-progress task"""

    def list_active_tasks(self):
        """Show all active tasks"""

    def allocate_browser(self, task_id):
        """Assign browser session to task"""

    def deallocate_browser(self, browser_id):
        """Release browser after task completes"""
```

#### Task State Machine
```
QUEUED → STARTED → EXTRACTING → DECIDING → EXECUTING → CHECKING
  ↓        ↓         ↓            ↓          ↓          ↓
  │        └────────→ LOADING ───→ LOOPING ─→ COMPLETE
  │                                   ↓
  │                            MAX_STEPS_EXCEEDED
  │
  └─────────────────────→ FAILED
                            ↓
                      NEEDS_HUMAN_REVIEW
```

---

### Component 3: Error Handler & Recovery
**File:** `workers/browser_automation/error_handler.py`
**Lines:** ~250-300
**Purpose:** Handle failures and implement recovery strategies

#### Error Types & Recovery
```python
class ErrorHandler:
    """
    Handle various failure scenarios with smart recovery.
    """

    # Error types with recovery strategies
    RECOVERABLE_ERRORS = {
        'element_not_found': {
            'retry_count': 3,
            'strategy': 'wait_and_retry',
            'timeout': 5
        },
        'page_timeout': {
            'retry_count': 2,
            'strategy': 'refresh_and_retry',
            'timeout': 10
        },
        'login_expired': {
            'retry_count': 1,
            'strategy': 're_authenticate',
            'timeout': 30
        },
        'modal_popup': {
            'retry_count': 1,
            'strategy': 'close_modal_and_retry',
            'timeout': 5
        },
        'rate_limited': {
            'retry_count': 1,
            'strategy': 'back_off_and_retry',
            'timeout': 60
        }
    }

    UNRECOVERABLE_ERRORS = {
        'site_down': 'stop_and_report',
        'access_denied': 'stop_and_report',
        'invalid_url': 'stop_and_report',
        'unknown_error': 'escalate_to_human'
    }

    def classify_error(self, error, context):
        """Classify error as recoverable or unrecoverable"""

    def attempt_recovery(self, error, attempt_num):
        """Try to recover from error"""

    def escalate(self, error, logs):
        """Escalate to human review queue"""
```

#### Recovery Strategies
```python
# 1. Wait and Retry
def wait_and_retry(driver, selector, timeout=5):
    wait = WebDriverWait(driver, timeout)
    element = wait.until(EC.presence_of_element_located(selector))
    return element.click()

# 2. Refresh and Retry
def refresh_and_retry(driver, max_attempts=2):
    for attempt in range(max_attempts):
        driver.refresh()
        time.sleep(2)
        try:
            # Retry extraction
            return extract_elements(driver)
        except TimeoutError:
            continue
    raise Exception("Page still unresponsive after refresh")

# 3. Re-authenticate
def re_authenticate(driver, credentials):
    driver.get(credentials['login_url'])
    driver.find_element_by_id('username').send_keys(credentials['user'])
    driver.find_element_by_id('password').send_keys(credentials['pass'])
    driver.find_element_by_xpath('//button[@type="submit"]').click()
    time.sleep(3)  # Wait for auth

# 4. Close Modal
def close_modal_and_retry(driver):
    modals = driver.find_elements_by_xpath('//div[@role="dialog"]')
    for modal in modals:
        close_btn = modal.find_element_by_xpath('.//button[@aria-label="Close"]')
        close_btn.click()
        time.sleep(1)

# 5. Back Off and Retry
def back_off_and_retry(driver, base_delay=5, max_attempts=3):
    for attempt in range(max_attempts):
        delay = base_delay * (2 ** attempt)  # Exponential backoff
        time.sleep(delay)
        try:
            return extract_elements(driver)
        except RateLimitError:
            continue
    raise Exception("Rate limited - giving up")
```

---

### Component 4: Monitoring & Logging
**File:** `workers/browser_automation/monitor.py`
**Lines:** ~200-300
**Purpose:** Track execution metrics and provide observability

#### Metrics to Track
```python
class ExecutionMonitor:
    """
    Monitor execution and track detailed metrics.
    """

    def track_step(self, task_id, step_num, action, result):
        """Track individual step execution"""

    def record_ai_decision(self, task_id, level, ai_used, duration, cost):
        """Record AI decision with cost tracking"""

    def record_cache_hit(self, task_id, domain, path_id, time_saved):
        """Track cache effectiveness"""

    def get_task_summary(self, task_id):
        """Get execution summary for task"""

    def get_stats(self):
        """Get overall system statistics"""

# Metrics to collect per task:
{
    "task_id": "abc123",
    "goal": "Register for swimming",
    "site": "aquatechswim.com",
    "status": "completed",
    "total_steps": 8,
    "total_time_seconds": 45.2,
    "cache_hit": true,
    "cache_time_saved": 35.0,
    "ai_decisions": [
        {
            "step": 1,
            "level": 1,
            "ai": "ollama",
            "time_ms": 1200,
            "cost": 0.00
        },
        {
            "step": 4,
            "level": 2,
            "ai": "claude",
            "time_ms": 4500,
            "cost": 0.015
        }
    ],
    "total_cost": 0.045,
    "success": true,
    "cached_for_next_run": true
}
```

---

### Component 5: Integration with Existing Systems
**File:** `workers/browser_automation/integration.py`
**Lines:** ~200-250
**Purpose:** Connect with Assigner, Goal Engine, LLM Metrics

#### Assigner Worker Integration
```python
class AssignerIntegration:
    """
    Integrate with existing Assigner Worker system.
    """

    def register_browser_worker(self):
        """Register as available for browser tasks"""

    def claim_browser_task(self):
        """Claim next browser task from queue"""

    def report_task_complete(self, task_id, result):
        """Report task completion back to assigner"""

    def report_task_failed(self, task_id, error, logs):
        """Report task failure"""

# Task message format:
{
    "type": "browser_task",
    "goal": "Register Eden for swimming at AquaTech",
    "site_url": "https://aquatechswim.com",
    "data": {
        "student_name": "Eden",
        "class_date": "Tuesday Evening",
        "contact": "albert@example.com"
    },
    "priority": 8,
    "timeout_minutes": 30
}

# Result message format:
{
    "task_id": "abc123",
    "status": "completed",
    "goal_achieved": true,
    "execution_time_seconds": 45,
    "steps_taken": 8,
    "ai_cost": 0.045,
    "cache_hit": true,
    "result_data": {
        "confirmation_number": "ABC-123456",
        "registration_date": "2026-02-17"
    }
}
```

#### Goal Engine Integration
```python
class GoalEngineIntegration:
    """
    Receive high-level goals from Goal Engine.
    Convert to browser automation tasks.
    """

    def receive_goal(self, goal_definition):
        """Receive goal from Goal Engine"""

    def convert_to_browser_task(self, goal):
        """Convert high-level goal to browser task"""

    def report_goal_completion(self, goal_id, result):
        """Report goal completion back to Goal Engine"""

# Goal format:
{
    "type": "browser_automation",
    "description": "Register child for swimming lessons",
    "site": "aquatechswim.com",
    "data_sources": [
        "env:AQUATECH_USER",
        "env:AQUATECH_PASS",
        "sheet:Family_Data!B2",  # Student name
        "db:contacts.parents WHERE child_id=42"
    ],
    "success_indicators": [
        "confirmation_number_visible",
        "URL_contains_confirmation",
        "alert_says_registered"
    ]
}
```

#### LLM Metrics Integration
```python
class LLMMetricsIntegration:
    """
    Report AI usage and costs to LLM Metrics system.
    """

    def record_decision(self, task_id, step, level, ai_used, duration, cost):
        """Record AI decision with cost"""

    def get_task_cost_breakdown(self, task_id):
        """Get detailed cost breakdown for task"""

# Cost tracking example:
Task ID: abc123
Total Cost: $0.045
Breakdown:
  - Ollama (Level 1): 0 uses, $0.00 (5 cached decisions)
  - Claude (Level 2): 1 use, $0.015
  - Codex (Level 3): 0 uses, $0.00
  - Gemini (Level 4): 0 uses, $0.00
  - Cache Hit: 1 use, $0.00 (saved $0.035)
```

---

## Implementation Steps

### Step 1: Build Execution Runner (Dev A)
**Duration:** 1 week
**File:** `workers/browser_automation/runner.py`

```
1. Create BrowserExecutor class
2. Implement main execution loop
3. Add cache checking logic
4. Add element extraction step
5. Add AI routing step
6. Add action execution step
7. Add goal completion checking
8. Add logging and metrics
9. Write unit tests (10+ test scenarios)
10. Test end-to-end on AquaTech portal
```

**Success Criteria:**
- Main loop orchestrates all 5 phases
- Cache integration working (skip AI on cache hit)
- Goal completion detection working
- End-to-end test completes in <2 minutes

---

### Step 2: Build Task Coordinator (Dev B)
**Duration:** 1 week
**File:** `workers/browser_automation/coordinator.py`

```
1. Create TaskCoordinator class
2. Implement task queue management
3. Add browser session allocation
4. Implement state machine
5. Add concurrent task tracking
6. Write unit tests
7. Test with 5+ parallel tasks
8. Verify browser cleanup
9. Add task timeout handling
10. Integration test with runner
```

**Success Criteria:**
- Run 5 tasks in parallel without interference
- All tasks complete successfully
- Browser cleanup working (no orphaned processes)
- Task status queries working

---

### Step 3: Build Error Handler (Dev C)
**Duration:** 1 week
**File:** `workers/browser_automation/error_handler.py`

```
1. Define error classification system
2. Implement recovery strategies (5 types)
3. Add retry logic with exponential backoff
4. Implement escalation to human review
5. Add error logging
6. Write unit tests (error scenarios)
7. Integration test with runner
8. Test recovery success rates
9. Add metrics tracking
10. Documentation and playbooks
```

**Success Criteria:**
- Recoverable errors fixed in ≤3 retries
- Success rate for recovery ≥80%
- Escalation working for unrecoverable errors
- All 5 recovery types tested

---

### Step 4: Build Monitoring System (Dev D)
**Duration:** 1 week
**File:** `workers/browser_automation/monitor.py`

```
1. Create ExecutionMonitor class
2. Implement metrics collection
3. Add cost tracking
4. Implement step-by-step logging
5. Build execution summary builder
6. Add statistics aggregation
7. Create metrics dashboard data format
8. Write logging tests
9. Integration test with coordinator
10. Performance impact testing
```

**Success Criteria:**
- All metrics collected without overhead
- Cost tracking accurate to $0.001
- Dashboard data available in real-time
- Performance impact <5% on execution time

---

### Step 5: Integration & Testing (Dev E)
**Duration:** 1 week
**File:** `workers/browser_automation/integration.py`

```
1. Build Assigner Worker integration
2. Build Goal Engine integration
3. Build LLM Metrics integration
4. Create task message format handlers
5. Implement result reporting
6. Write integration tests (3+ systems)
7. End-to-end testing (real workflow)
8. Performance load testing (10+ concurrent)
9. Failure scenario testing
10. Documentation & deployment guide
```

**Success Criteria:**
- Full integration with 3+ existing systems
- Message formats validated
- Error handling working
- 10+ concurrent tasks handling smoothly
- Production-ready

---

## Database Requirements

### Tasks Table (New)
```sql
CREATE TABLE browser_tasks (
    id TEXT PRIMARY KEY,
    goal VARCHAR(500),
    site_url VARCHAR(500),
    status VARCHAR(50),  -- queued, running, completed, failed
    task_data JSON,
    created_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    total_steps INT,
    total_time_seconds FLOAT,
    total_cost DECIMAL(10, 4),
    result_data JSON,
    error_message TEXT,
    cached_path_used BOOLEAN,
    cache_time_saved_seconds FLOAT
);

CREATE INDEX idx_browser_tasks_status ON browser_tasks(status);
CREATE INDEX idx_browser_tasks_site ON browser_tasks(site_url);
```

### Execution Log Table (New)
```sql
CREATE TABLE browser_execution_log (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    task_id TEXT,
    step_number INT,
    action VARCHAR(200),
    ai_level INT,
    ai_used VARCHAR(50),
    duration_ms INT,
    cost DECIMAL(10, 4),
    result VARCHAR(200),
    created_at TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES browser_tasks(id)
);

CREATE INDEX idx_execution_log_task ON browser_execution_log(task_id);
```

---

## File Structure

```
architect/
├── workers/
│   └── browser_automation/
│       ├── __init__.py
│       ├── runner.py              # Main execution loop (400-500 lines)
│       ├── coordinator.py         # Multi-task orchestration (300-400 lines)
│       ├── error_handler.py       # Error handling & recovery (250-300 lines)
│       ├── monitor.py             # Metrics & logging (200-300 lines)
│       ├── integration.py         # System integration (200-250 lines)
│       └── config.py              # Configuration & constants
├── tests/
│   └── test_browser_automation/
│       ├── test_runner.py         # Execution loop tests
│       ├── test_coordinator.py    # Orchestration tests
│       ├── test_error_handler.py  # Error recovery tests
│       ├── test_monitor.py        # Metrics tests
│       └── test_integration.py    # Integration tests
├── migrations/
│   └── 0XX_browser_automation_tables.sql  # Database schema
└── docs/
    ├── BROWSER_AUTOMATION_PHASE3_IMPLEMENTATION.md
    ├── ERROR_RECOVERY_PLAYBOOK.md
    ├── TROUBLESHOOTING_GUIDE.md
    └── OPERATION_MANUAL.md
```

---

## Success Metrics

| Metric | Target | Definition |
|--------|--------|-----------|
| Task Completion Rate | 90%+ | % of tasks achieving goal |
| Average Task Time | <60s | Average time per task |
| Cache Hit Rate | 70%+ | % of repeat tasks using cache |
| Cache Time Savings | 50% avg | Time saved vs non-cached |
| Error Recovery Rate | 80%+ | % of recoverable errors fixed |
| Cost per Task | <$0.05 | Average LLM cost per task |
| Concurrent Tasks | 10+ | Tasks running simultaneously |
| System Uptime | 99%+ | Availability during business hours |

---

## Phase 3 to Phase 4 Transition

Once Phase 3 is complete, can proceed to:

**Phase 4: Chrome Extension (Optional, Weeks 6-8)**
- WebSocket server for in-browser automation
- Extension for existing browser sessions
- Comet AI integration
- Tab group management

**Phase 5: Production Hardening (Week 8+)**
- Load testing (100+ concurrent tasks)
- Security audit
- Credential management
- Monitoring dashboard
- Production deployment

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Browser crashes | High | Medium | Add automatic recovery, session cleanup |
| Network timeouts | Medium | Medium | Implement retries, backoff strategy |
| AI decision errors | Medium | High | Add human review queue, decision logging |
| Database bottlenecks | Low | High | Add connection pooling, caching |
| Rate limiting | Low | Medium | Add throttling, backoff strategy |

---

## Estimated Effort

| Component | Dev Days | Total |
|-----------|----------|-------|
| Execution Runner | 5 | 5 |
| Task Coordinator | 5 | 10 |
| Error Handler | 4 | 14 |
| Monitoring | 3 | 17 |
| Integration | 5 | 22 |
| Testing/QA | 8 | 30 |
| Documentation | 3 | 33 |

**Total: 33 dev-days (6-8 weeks with team of 2-3)**

---

## Dependencies

**Must Complete Before Phase 3:**
- ✅ Phase 1: HTML Element Extractor
- ✅ Phase 2A: AI Decision Router
- ✅ Phase 2B: Site Knowledge Cache

**External Dependencies:**
- Selenium/Playwright (already available)
- LLM providers (Ollama, Claude, Codex, Gemini)
- Database (SQLite or PostgreSQL)
- Assigner Worker system (already available)

---

## Deployment Checklist

- [ ] All 5 components implemented
- [ ] Unit tests passing (80%+ coverage)
- [ ] Integration tests passing
- [ ] Load testing completed (10+ concurrent)
- [ ] Error scenarios tested
- [ ] Performance benchmarks met
- [ ] Documentation complete
- [ ] Team trained on operation
- [ ] Monitoring alerts configured
- [ ] Backup procedures documented
- [ ] Disaster recovery tested
- [ ] Production deployment approved

---

## Getting Started

When ready to start Phase 3:

1. Assign Component 1 (Execution Runner) to available developer
2. Assign Component 2 (Task Coordinator) to parallel developer
3. Assign Component 3-5 to additional team members
4. Set up daily sync meetings
5. Create shared testing environment
6. Set performance benchmarks
7. Begin implementation

**Estimated Start:** Week 4 (after Phase 1 & 2 complete)
**Estimated Completion:** Week 8
**Production Ready:** Week 10

