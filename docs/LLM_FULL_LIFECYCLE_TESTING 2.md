# LLM Full Lifecycle Testing System

## Overview

Comprehensive end-to-end testing framework that validates LLM-generated applications through their entire lifecycle:

1. **Code Generation** - LLM creates application code
2. **Deployment** - Deploy to test environment with independent data
3. **UI Testing** - Login flows, session management, user journeys
4. **API Testing** - Backend endpoint validation
5. **Data Isolation** - Verify independent test data
6. **Cleanup** - Remove deployment and verify clean state
7. **Verification** - Confirm ready for next test run

## Components

### Test Suites

**Location**: `testing/test_suites/`

#### `llm_full_lifecycle.json`
- Complete end-to-end test with all phases
- Tests: code generation, SOP compliance, deployment, data isolation, UI flows, API endpoints, cleanup
- ~800 lines, comprehensive coverage

#### `llm_quick_validation.json`
- Quick smoke test for rapid validation
- Tests: generation, basic validation, cleanup
- ~150 lines, 3-minute runtime

### Test Orchestrator

**File**: `workers/llm_lifecycle_orchestrator.py`

**Features**:
- Runs test suites across multiple LLM providers
- Manages test lifecycle (create run → execute → store results)
- Calculates SOP compliance scores
- Parallel test execution support
- Automatic cleanup between tests

**Usage**:
```bash
# Test all providers with all configurations
python3 workers/llm_lifecycle_orchestrator.py

# Test specific providers
python3 workers/llm_lifecycle_orchestrator.py --providers Claude Ollama

# Quick validation only
python3 workers/llm_lifecycle_orchestrator.py --quick

# Specific configuration
python3 workers/llm_lifecycle_orchestrator.py --config "Production Simulation"
```

### Provider Configurations

| Provider | Type | Session | API |
|----------|------|---------|-----|
| Claude | claude | architect | - |
| Codex | codex | codex | - |
| Claude-Architect | claude | claude_architect | - |
| Comet | comet | claude_comet | - |
| AnythingLLM | anything_llm | - | http://localhost:3001 |
| Ollama | ollama | - | http://localhost:11434 |

### Test Configurations

#### Standard Flow
- Full lifecycle with all test phases
- Port: 5000
- Tests: Generation, deployment, UI (login, calculator, session), API, cleanup
- Duration: ~10-15 minutes per provider

#### Quick Validation
- Rapid smoke test
- Port: 5001
- Tests: Generation, validation, cleanup
- Duration: ~3-5 minutes per provider
- Skips: UI testing, API testing, data isolation

#### Production Simulation
- Production-like environment
- Port: 5002
- Tests: Full lifecycle with HTTPS requirement
- Duration: ~15-20 minutes per provider
- Additional: SSL/TLS validation, security headers

## Test Phases

### 1. Code Generation
- **Input**: Detailed prompt with requirements
- **Process**: Send to LLM provider via assigner worker
- **Timeout**: 5 minutes
- **Output**: Generated files in `/tmp/llm_test_{provider}_{run_id}/`
- **Validation**: Directory exists, files present

### 2. SOP Compliance Check
- **Required Files**: calculator.html, calculator.js, calculator.css, app.py
- **Line Limit**: ≤1000 lines total
- **Tests**: File structure, test files, documentation
- **Score**: 0-100 (passing ≥80)

**Scoring Breakdown**:
- Required files present: 40 points
- Under line limit: 20 points
- Has tests: 10 points
- Has documentation: 10 points
- UI tests pass: 20 points

### 3. Deployment
- **Process**: Install dependencies, start Flask application
- **Port**: Assigned from configuration (5000-5002)
- **Health Check**: GET /health → 200 OK
- **Timeout**: 10 seconds for startup
- **PID Tracking**: Store process ID for cleanup

### 4. Data Isolation Verification
- **Initial Check**: Verify data count = 0
- **Create Data**: POST /api/data with test record
- **Verify**: Data count = 1 (isolated environment)
- **Purpose**: Ensure tests don't interfere with each other

### 5. UI Testing

#### Login Flow
- Navigate to application root
- Wait for login form
- Fill username/password (testuser/testpass123)
- Submit login
- Verify redirect to calculator
- Capture screenshots

#### Calculator Operations
- Click buttons: 7, +, 3, =
- Verify result: 10
- Check history shows: "7 + 3 = 10"
- Capture result screenshot

#### Session Persistence
- Extract calculation history
- Refresh page
- Verify still logged in (not redirected)
- Verify history persisted

### 6. API Testing
- **Endpoint**: POST /api/calculate
- **Tests**:
  - Addition: 15 + 25 = 40
  - Multiplication: 6 × 7 = 42
  - Division by zero: 10 ÷ 0 → 400 error
- **Validation**: Status codes, JSON responses

### 7. Cleanup
- **Stop Application**: Kill process by PID
- **Delete Files**: rm -rf output directory
- **Timeout**: 5 seconds

### 8. Cleanup Verification
- **Check Application**: Health endpoint should fail
- **Check Directory**: Output directory should not exist
- **Purpose**: Confirm clean state for next test

## Database Schema

Uses existing `llm_test_runs` and `llm_test_results` tables (migration 032).

### Extended Metadata Fields

Stored in `metadata` JSON column:

```json
{
  "config": {
    "name": "Standard Flow",
    "env": "test",
    "port": 5000
  },
  "provider_type": "claude",
  "api_endpoint": null,
  "sop_score": 85,
  "test_details": {
    "code_generation": {
      "status": "passed",
      "duration": 45.2,
      "steps_passed": 4,
      "steps_total": 4
    },
    "ui_login_flow": {
      "status": "passed",
      "duration": 8.1,
      "steps_passed": 9,
      "steps_total": 9
    },
    ...
  },
  "suite_result": {
    "passed": 8,
    "failed": 0,
    "skipped": 0,
    "total": 8,
    "duration": 127.5
  }
}
```

## Running Through Task Queue

### Via API
```python
import requests

response = requests.post('http://localhost:8080/api/tasks',
    json={
        'type': 'python',
        'data': {
            'script': 'workers/llm_lifecycle_orchestrator.py',
            'args': ['--quick']
        },
        'metadata': {
            'test_type': 'llm_full_lifecycle',
            'scheduled_by': 'user'
        }
    },
    cookies={'session': 'your_session_cookie'}
)
```

### Via CLI
```bash
# Queue as task
python3 -c "
import sys
sys.path.insert(0, '.')
from db import get_connection
import json

with get_connection('main') as conn:
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO task_queue (type, data, metadata, status)
        VALUES ('python', ?, ?, 'pending')
    ''', (
        json.dumps({'script': 'workers/llm_lifecycle_orchestrator.py', 'args': ['--quick']}),
        json.dumps({'test_type': 'llm_full_lifecycle'})
    ))
    print(f'Task queued: {cursor.lastrowid}')
"
```

## Dashboard Integration

### API Endpoints

Reuse existing endpoints from `services/llm_test_routes.py`:

- `GET /api/llm-tests/runs` - List all test runs
- `GET /api/llm-tests/runs/:id/results` - Results for specific run
- `GET /api/llm-tests/latest` - Latest results across providers
- `GET /api/llm-tests/stats` - Aggregate statistics
- `GET /api/llm-tests/comparison` - Provider comparison

### Dashboard Panel

Add to `templates/dashboard.html`:

```html
<div class="panel" id="panel-llm-lifecycle">
    <div class="panel-header">
        <h2>LLM Full Lifecycle Tests</h2>
        <button onclick="runLLMLifecycleTest()">Run Test</button>
    </div>

    <div class="test-matrix">
        <!-- Provider × Configuration matrix -->
        <table>
            <thead>
                <tr>
                    <th>Provider</th>
                    <th>Quick</th>
                    <th>Standard</th>
                    <th>Production</th>
                    <th>Overall</th>
                </tr>
            </thead>
            <tbody id="llm-lifecycle-matrix"></tbody>
        </table>
    </div>

    <div class="test-details">
        <!-- Detailed test phase breakdown -->
        <h3>Latest Test Details</h3>
        <div id="llm-test-phases"></div>
    </div>
</div>
```

### JavaScript Functions

```javascript
async function runLLMLifecycleTest(quick = false) {
    const response = await fetch('/api/tasks', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            type: 'python',
            data: {
                script: 'workers/llm_lifecycle_orchestrator.py',
                args: quick ? ['--quick'] : []
            }
        })
    });

    const result = await response.json();
    alert(`Test queued: Task #${result.task_id}`);

    // Poll for results
    pollTestResults(result.task_id);
}

async function pollTestResults(taskId) {
    // Check task status every 10 seconds
    const interval = setInterval(async () => {
        const response = await fetch(`/api/tasks/${taskId}`);
        const task = await response.json();

        if (task.status === 'completed' || task.status === 'failed') {
            clearInterval(interval);
            refreshLLMLifecycleResults();
        }
    }, 10000);
}

async function refreshLLMLifecycleResults() {
    const response = await fetch('/api/llm-tests/latest?limit=20');
    const data = await response.json();

    // Update matrix and details
    updateLifecycleMatrix(data.results);
    updateTestDetails(data.results[0]); // Latest test
}
```

## Example Test Flow

### Provider: Claude, Config: Standard Flow

```
[00:00] Create test run: "Claude - Standard Flow"
[00:00] Create test result entry (status: running)
[00:01] Phase 1: Code Generation
[00:01]   Send prompt to architect session
[00:06]   Wait for generation (timeout: 5 min)
[01:23]   Generation complete ✓
[01:23] Phase 2: SOP Compliance Check
[01:23]   Verify required files ✓
[01:24]   Count lines: 847 ✓
[01:24]   SOP Score: 85/100 ✓
[01:24] Phase 3: Deployment
[01:24]   Install dependencies
[01:32]   Start application on port 5000
[01:35]   Health check: 200 OK ✓
[01:35] Phase 4: Data Isolation
[01:35]   Initial count: 0 ✓
[01:36]   Create test data ✓
[01:36]   Verify count: 1 ✓
[01:36] Phase 5: UI Testing - Login Flow
[01:36]   Navigate to app
[01:37]   Fill login form
[01:38]   Submit → Redirected ✓
[01:38]   Screenshot: login_page_Claude.png
[01:38] Phase 6: UI Testing - Calculator
[01:38]   Click: 7, +, 3, =
[01:39]   Result: 10 ✓
[01:39]   History: "7 + 3 = 10" ✓
[01:39] Phase 7: UI Testing - Session Persistence
[01:39]   Refresh page
[01:40]   Still logged in ✓
[01:40]   History persisted ✓
[01:40] Phase 8: API Testing
[01:40]   POST /api/calculate {add, 15, 25} → 40 ✓
[01:40]   POST /api/calculate {multiply, 6, 7} → 42 ✓
[01:41]   POST /api/calculate {divide, 10, 0} → 400 ✓
[01:41] Phase 9: Cleanup
[01:41]   Stop application (PID: 12345)
[01:42]   Delete output directory
[01:43] Phase 10: Cleanup Verification
[01:43]   Health check: Connection refused ✓
[01:43]   Directory deleted ✓
[01:43] Update test result: completed
[01:43] Duration: 102.5s, Files: 5, Lines: 847, SOP: 85, PASSED ✅
```

## Benefits

### For Development
- ✅ **Full lifecycle coverage** - Not just code generation, but deployment through cleanup
- ✅ **Real-world validation** - Actual UI and API testing, not just file checks
- ✅ **Data isolation** - Each test has clean environment
- ✅ **Comprehensive metrics** - SOP compliance, performance, success rates

### For Operations
- ✅ **Provider comparison** - Identify best LLM for each use case
- ✅ **CI/CD integration** - Automated testing on PR merge
- ✅ **Deployment verification** - Confirm deployments work correctly
- ✅ **Regression detection** - Catch issues before production

### For Decision Making
- ✅ **Data-driven provider selection** - Real metrics, not assumptions
- ✅ **Cost optimization** - Compare efficiency across providers
- ✅ **Quality tracking** - Monitor improvement over time
- ✅ **Risk mitigation** - Comprehensive testing reduces production issues

## Troubleshooting

### Issue: Tests timing out
**Solution**: Increase timeout in test suite JSON (`timeout` field)

### Issue: Sessions busy
**Solution**: Use `--providers` to test fewer providers, or wait for sessions to become idle

### Issue: Port already in use
**Solution**: Tests use different ports (5000, 5001, 5002) - ensure these are free

### Issue: Cleanup fails
**Solution**: Manually clean up: `rm -rf /tmp/llm_test_*`

### Issue: Database locked
**Solution**: SQLite can't handle concurrent writes - tests run sequentially by default

## Future Enhancements

### Short Term
- [ ] Parallel provider testing (requires connection pooling)
- [ ] Screenshot comparison (visual regression)
- [ ] Performance benchmarking (load testing)
- [ ] Slack/email notifications on test completion

### Long Term
- [ ] Multi-region testing (distributed deployment)
- [ ] A/B testing framework (compare prompt variations)
- [ ] Machine learning for quality prediction
- [ ] Integration with external test platforms (BrowserStack, Sauce Labs)

---

**Status**: ✅ Ready for use
**Version**: 1.0.0
**Dependencies**: testing framework (runner.py, models.py), task queue, llm_test_routes.py
**Next Step**: Queue test via task system and monitor results on dashboard
