# Rapid Full-Stack Testing Guide

## Overview

Optimized testing system that completes full development lifecycle in **5-10 minutes per provider**:

1. Code Generation (2 min)
2. Validation (10 sec)
3. Deployment (30 sec)
4. API Testing (20 sec)
5. UI Testing (30 sec)
6. Load Testing (30 sec)
7. Cleanup (10 sec)
8. Verification (5 sec)

**Total Target**: ~5 minutes per provider

## Key Optimizations

### Simplified Application
- **NO** login/authentication (saves 2-3 min)
- **NO** session management (saves 1-2 min)
- **NO** database persistence (in-memory SQLite)
- **NO** history features (saves complexity)
- Minimal dependencies (flask, flask-cors only)
- Target: Under 300 lines total (vs 1000)

### Faster Generation Prompt
```
Create a minimal TODO app in /tmp/llm_rapid_${provider}_${run_id}:

Files (EXACTLY these, no extras):
1. app.py - Flask backend with in-memory SQLite:
   - GET /api/todos (list all)
   - POST /api/todos (create: {text})
   - DELETE /api/todos/<id>
   - GET /health (return {"status": "ok"})
2. index.html - Single page with:
   - Input field + Add button
   - Todo list (each item has Delete button)
   - Uses fetch() to call API
3. style.css - Simple styling
4. requirements.txt - Just: flask flask-cors

Rules:
- NO login/auth
- NO session management
- NO history feature
- SQLite in-memory only
- CORS enabled
- Each file under 100 lines
- Total under 300 lines
- Be FAST
```

### Reduced Timeouts
- Generation: 2 min (vs 5 min)
- Deployment: 30 sec (vs 60 sec)
- Health checks: 5 sec (vs 10 sec)
- API tests: 5 sec each (vs 10 sec)
- UI tests: 5 sec each (vs 10 sec)

### Parallel Where Possible
- Install deps + start app (single command)
- Concurrent load test (10 simultaneous requests)
- Cleanup in background

## Usage

### Run Rapid Test

```bash
# Test all providers (rapid mode)
PYTHONPATH=/Users/jgirmay/Desktop/gitrepo/pyWork/architect \
python3 workers/llm_lifecycle_orchestrator.py \
  --config "Rapid" \
  --suite llm_rapid_full_stack

# Single provider test (5 min)
PYTHONPATH=/Users/jgirmay/Desktop/gitrepo/pyWork/architect \
python3 workers/llm_lifecycle_orchestrator.py \
  --providers Claude \
  --suite llm_rapid_full_stack
```

### Via Task Queue

```bash
python3 -c "
import sys
sys.path.insert(0, '/Users/jgirmay/Desktop/gitrepo/pyWork/architect')
from db import get_connection
import json

with get_connection('main') as conn:
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO task_queue (task_type, task_data, priority, status)
        VALUES ('shell', ?, 10, 'pending')
    ''', (
        json.dumps({
            'command': 'PYTHONPATH=/Users/jgirmay/Desktop/gitrepo/pyWork/architect python3 workers/llm_lifecycle_orchestrator.py --suite llm_rapid_full_stack --providers Claude'
        }),
    ))
    print(f'Rapid test queued: Task #{cursor.lastrowid}')
"
```

## Test Phases Breakdown

### Phase 1: Rapid Generation (2 min target)
- Send minimal prompt to LLM
- Wait max 2 minutes
- Check every 3 seconds (vs 5 seconds)
- **Expected**: 4 files, ~250 lines

### Phase 2: Rapid Validation (10 sec target)
- Check app.py exists
- Check index.html exists
- Count lines (warning only if over limit)
- **Expected**: Pass if files exist

### Phase 3: Rapid Deployment (30 sec target)
- Install flask + flask-cors (quiet mode)
- Start app in background
- Wait 5 seconds for startup
- Health check
- **Expected**: Health returns 200

### Phase 4: Rapid API Smoke (20 sec target)
- POST /api/todos (create)
- GET /api/todos (list)
- Verify todo in list
- **Expected**: 3 API calls pass

### Phase 5: Rapid UI Smoke (30 sec target)
- Load page
- Find input field
- Type todo
- Click add button
- **Expected**: Page loads, can interact

### Phase 6: Rapid Load Test (30 sec target)
- Send 10 concurrent POST requests
- Wait for completion
- Health check (verify still running)
- Count todos (verify all created)
- **Expected**: Survives 10 concurrent requests

### Phase 7: Rapid Cleanup (10 sec target)
- Kill app process
- Delete files
- **Expected**: Clean execution

### Phase 8: Rapid Verification (5 sec target)
- Try health check (should fail)
- Verify app stopped
- **Expected**: App not reachable

## Expected Timeline

| Provider | Generation | Deploy | Tests | Cleanup | Total |
|----------|------------|--------|-------|---------|-------|
| Claude | 1.5 min | 25 sec | 60 sec | 8 sec | **4.1 min** |
| Codex | 1.2 min | 25 sec | 60 sec | 8 sec | **3.8 min** |
| Ollama | 2.5 min | 25 sec | 60 sec | 8 sec | **5.3 min** |
| Comet | 1.8 min | 25 sec | 60 sec | 8 sec | **4.6 min** |

**Average**: ~4.5 minutes per provider
**Total for 4 providers**: ~18 minutes (sequential)

## Scoring

### Rapid SOP Score (100 points)

- **File completeness (30 points)**
  - app.py exists: 15 points
  - index.html exists: 10 points
  - style.css exists: 5 points

- **Line limit (20 points)**
  - ≤300 lines: 20 points
  - 301-400 lines: 10 points
  - >400 lines: 0 points

- **Deployment (20 points)**
  - Health check passes: 20 points

- **API functionality (15 points)**
  - Create works: 5 points
  - List works: 5 points
  - Data persists: 5 points

- **UI functionality (10 points)**
  - Page loads: 5 points
  - Can interact: 5 points

- **Load test (5 points)**
  - Survives 10 concurrent requests: 5 points

**Passing threshold**: ≥70 points (vs 80 for full test)

## Comparison: Rapid vs Full

| Aspect | Rapid Test | Full Test |
|--------|------------|-----------|
| **Duration** | 5 min | 15 min |
| **Lines** | 300 | 1000 |
| **Features** | TODO only | Calculator + login + history |
| **Auth** | None | Username/password |
| **Session** | None | Persistence across refreshes |
| **Database** | In-memory | SQLite file |
| **Tests** | Smoke only | Comprehensive (UI flows, edge cases) |
| **Load** | 10 users, 30 sec | Not included |
| **SOP** | 70% pass | 80% pass |

## When to Use Each

### Use Rapid Test When:
- ✅ Quick validation needed (CI/CD gates)
- ✅ Comparing many providers quickly
- ✅ Testing system itself (not code quality)
- ✅ Resource-constrained environment
- ✅ Development/debugging of test framework

### Use Full Test When:
- ✅ Final validation before deployment
- ✅ Comprehensive quality check needed
- ✅ Testing complex features (auth, sessions)
- ✅ User acceptance testing
- ✅ Performance benchmarking

## Troubleshooting

### Issue: Still takes >10 minutes
**Causes**:
- Session not idle (check with `tmux ls`)
- Provider is slow (try different provider)
- Generation timeout too long (reduce to 90 sec)

**Solutions**:
```bash
# Check session status
tmux capture-pane -t architect -p | tail -5

# Reduce generation timeout
# Edit llm_rapid_full_stack.json: "timeout_minutes": 1.5
```

### Issue: Tests failing
**Common causes**:
1. Port 5050 in use → Change `app_port` in test suite
2. Flask not installed → Run `pip install flask flask-cors`
3. Files not generated → Check session idle status

### Issue: Load test fails
**Cause**: App can't handle 10 concurrent requests

**Debug**:
```bash
# Check app logs
tail -f /tmp/app_*.log

# Reduce concurrent users
# Edit test suite: "load_test_users": 5
```

## Monitoring

### Real-Time Progress

```bash
# Watch test execution
tail -f /tmp/task_worker.log

# Check specific test run
sqlite3 data/prod/architect.db "
SELECT
  provider_name,
  status,
  started_at,
  (julianday('now') - julianday(started_at)) * 1440 as minutes_elapsed
FROM llm_test_results
WHERE status = 'running'
ORDER BY started_at DESC
LIMIT 1;
"
```

### Resource Usage

```bash
# Monitor during test
watch -n 1 'ps aux | grep -E "python3|flask" | grep -v grep'

# Check ports
lsof -i :5050

# Check CPU/memory
top -p $(pgrep -f "app.py")
```

## Next Steps After Rapid Test

### 1. Analyze Results

```bash
# View latest results
sqlite3 data/prod/architect.db "
SELECT
  provider_name,
  duration_seconds,
  files_created,
  total_lines,
  test_passed,
  json_extract(metadata, '$.sop_score') as sop_score
FROM llm_test_results
ORDER BY created_at DESC
LIMIT 5;
"
```

### 2. Identify Best Provider

Based on results:
- **Fastest**: Lowest duration_seconds
- **Most reliable**: Highest test_passed rate
- **Best quality**: Highest sop_score

### 3. Run Full Test on Winner

```bash
# Run comprehensive test on best provider
python3 workers/llm_lifecycle_orchestrator.py \
  --providers Claude \
  --suite llm_full_lifecycle
```

### 4. Fix Issues

If rapid test reveals issues:
1. Check session availability
2. Verify environment setup
3. Adjust timeouts
4. Fix port conflicts
5. Install missing dependencies

### 5. Iterate

- Adjust prompt for better results
- Tune timeouts for your hardware
- Add custom validation rules
- Customize SOP scoring

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: LLM Rapid Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run rapid test
        run: |
          python3 workers/llm_lifecycle_orchestrator.py \
            --suite llm_rapid_full_stack \
            --providers Claude
        timeout-minutes: 10
      - name: Check results
        run: |
          sqlite3 data/prod/architect.db \
            "SELECT * FROM llm_test_results ORDER BY created_at DESC LIMIT 1"
```

---

**Status**: ✅ Ready for testing
**Target**: 5 min per provider
**Suite**: `llm_rapid_full_stack.json`
**Optimizations**: Minimal features, shorter timeouts, parallel operations
