# LLM Provider Testing System

## Overview

Comprehensive system for testing and comparing different LLM providers with standardized prompts. Results are stored in the database and available via API for dashboard display.

---

## Components

### 1. Database Schema

**File:** `migrations/032_llm_provider_tests.sql`

**Tables:**
- `llm_test_runs` - Test configurations with prompt templates
- `llm_test_results` - Per-provider results with performance metrics

**Default Test:** Calculator Web App (< 1000 lines)

### 2. Test Runner

**File:** `workers/llm_test_runner.py`

**Supported Providers:**
- Claude (architect session)
- Codex (codex session)
- Claude-Architect (claude_architect session)
- Comet (claude_comet session)

**Process:**
1. Check if session is idle
2. Send standardized prompt
3. Monitor output directory (max 3 min)
4. Verify generated files
5. Calculate metrics
6. Store results in database

**Metrics Collected:**
- Duration (seconds)
- Files created (count)
- Total lines of code
- Total bytes
- Test passed (boolean)
- Error messages

### 3. API Routes

**File:** `services/llm_test_routes.py`

**Endpoints:**
```python
GET  /api/llm-tests/runs              # List all test runs
GET  /api/llm-tests/runs/:id/results  # Results for specific run
GET  /api/llm-tests/latest            # Latest results
GET  /api/llm-tests/stats             # Aggregate statistics
GET  /api/llm-tests/comparison        # Provider comparison
```

---

## Usage

### Running Tests

**Test all providers:**
```bash
python3 workers/llm_test_runner.py
```

**Test specific providers:**
```bash
python3 workers/llm_test_runner.py --providers Claude Codex
```

**Custom test:**
```bash
python3 workers/llm_test_runner.py --test "My Custom Test"
```

### Example Output

```
================================================================================
LLM Provider Test: Calculator Web App
================================================================================
Testing 4 providers
Max lines: 1000

[1/4] Claude
  Sending prompt to architect
  Monitoring output (max 3 minutes)...
  ✓ Generation complete! (45s)
    Files: 4
    Lines: 273
    Bytes: 6518

[2/4] Codex
  Sending prompt to codex
  Session codex is busy
  ✗ FAIL - Session busy

[3/4] Claude-Architect
  Sending prompt to claude_architect
  Monitoring output (max 3 minutes)...
  ✓ Generation complete! (52s)
    Files: 4
    Lines: 298
    Bytes: 7234

[4/4] Comet
  Sending prompt to claude_comet
  Monitoring output (max 3 minutes)...
  ✗ Timeout after 180s

================================================================================
TEST SUMMARY
================================================================================
Success rate: 2/4 (50.0%)
  ✓ PASS - Claude
  ✗ FAIL - Codex
  ✓ PASS - Claude-Architect
  ✗ FAIL - Comet

Results saved to database and available on dashboard
================================================================================
```

---

## Integration with Dashboard

### Step 1: Register Blueprint

Add to `app.py`:

```python
from services.llm_test_routes import llm_test_bp

# Register blueprint
app.register_blueprint(llm_test_bp)
```

### Step 2: Add Dashboard Panel

Add to `templates/dashboard.html`:

```html
<!-- LLM Provider Tests Panel -->
<div class="panel" id="panel-llm-tests">
    <div class="panel-header">
        <h2>LLM Provider Tests</h2>
        <button onclick="refreshLLMTests()">Refresh</button>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <h3 id="llm-total-tests">-</h3>
            <p>Total Tests</p>
        </div>
        <div class="stat-card">
            <h3 id="llm-success-rate">-</h3>
            <p>Success Rate</p>
        </div>
        <div class="stat-card">
            <h3 id="llm-avg-duration">-</h3>
            <p>Avg Duration</p>
        </div>
        <div class="stat-card">
            <h3 id="llm-avg-lines">-</h3>
            <p>Avg Lines</p>
        </div>
    </div>

    <h3>Provider Comparison</h3>
    <table class="table">
        <thead>
            <tr>
                <th>Provider</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Files</th>
                <th>Lines</th>
                <th>Passed</th>
            </tr>
        </thead>
        <tbody id="llm-comparison-table"></tbody>
    </table>

    <h3>Recent Results</h3>
    <div id="llm-recent-results"></div>
</div>

<script>
async function refreshLLMTests() {
    try {
        // Get stats
        const statsRes = await fetch('/api/llm-tests/stats');
        const stats = await statsRes.json();

        if (stats.success && stats.overall) {
            document.getElementById('llm-total-tests').textContent = stats.overall.total_tests || 0;
            const successRate = stats.overall.total_tests > 0
                ? ((stats.overall.passed / stats.overall.total_tests) * 100).toFixed(1)
                : 0;
            document.getElementById('llm-success-rate').textContent = successRate + '%';
            document.getElementById('llm-avg-duration').textContent =
                (stats.overall.avg_duration || 0).toFixed(1) + 's';
            document.getElementById('llm-avg-lines').textContent =
                Math.round(stats.overall.avg_lines || 0);
        }

        // Get comparison
        const compRes = await fetch('/api/llm-tests/comparison');
        const comp = await compRes.json();

        if (comp.success) {
            const tbody = document.getElementById('llm-comparison-table');
            tbody.innerHTML = '';

            comp.comparison.forEach(result => {
                const row = tbody.insertRow();
                row.innerHTML = `
                    <td>${result.provider_name}</td>
                    <td><span class="status-badge status-${result.status}">${result.status}</span></td>
                    <td>${result.duration_seconds || 'N/A'}s</td>
                    <td>${result.files_created || 0}</td>
                    <td>${result.total_lines || 0}</td>
                    <td>${result.test_passed ? '✓' : '✗'}</td>
                `;
            });
        }

        // Get recent results
        const recentRes = await fetch('/api/llm-tests/latest?limit=5');
        const recent = await recentRes.json();

        if (recent.success) {
            const container = document.getElementById('llm-recent-results');
            container.innerHTML = '';

            recent.results.forEach(result => {
                const div = document.createElement('div');
                div.className = 'test-result-card';
                div.innerHTML = `
                    <strong>${result.provider_name}</strong> - ${result.test_name}
                    <br>
                    <small>${result.status} | ${result.duration_seconds}s | ${result.total_lines} lines</small>
                `;
                container.appendChild(div);
            });
        }

    } catch (error) {
        console.error('Error loading LLM test data:', error);
    }
}

// Auto-refresh every 30 seconds
setInterval(refreshLLMTests, 30000);
</script>
```

### Step 3: Add CSS Styling

```css
.test-result-card {
    background: #f7fafc;
    border-left: 4px solid #667eea;
    padding: 10px;
    margin-bottom: 10px;
    border-radius: 4px;
}

.status-badge {
    padding: 3px 8px;
    border-radius: 3px;
    font-size: 0.85em;
}

.status-completed {
    background: #c6f6d5;
    color: #22543d;
}

.status-failed {
    background: #fed7d7;
    color: #742a2a;
}

.status-timeout {
    background: #feebc8;
    color: #7c2d12;
}
```

---

## Database Queries

### Get Latest Test Results

```sql
SELECT
    r.provider_name,
    r.status,
    r.duration_seconds,
    r.files_created,
    r.total_lines,
    r.test_passed,
    t.test_name
FROM llm_test_results r
JOIN llm_test_runs t ON r.test_run_id = t.id
WHERE r.status IN ('completed', 'failed', 'timeout')
ORDER BY r.created_at DESC
LIMIT 10;
```

### Get Provider Success Rates

```sql
SELECT
    provider_name,
    COUNT(*) as total,
    SUM(CASE WHEN test_passed = 1 THEN 1 ELSE 0 END) as passed,
    ROUND(AVG(duration_seconds), 1) as avg_duration,
    ROUND(AVG(total_lines), 0) as avg_lines
FROM llm_test_results
WHERE status = 'completed'
GROUP BY provider_name
ORDER BY passed DESC;
```

### Get Test Run History

```sql
SELECT
    t.test_name,
    COUNT(r.id) as total_runs,
    SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) as completed,
    SUM(CASE WHEN r.test_passed = 1 THEN 1 ELSE 0 END) as passed
FROM llm_test_runs t
LEFT JOIN llm_test_results r ON t.id = r.test_run_id
GROUP BY t.id
ORDER BY t.created_at DESC;
```

---

## Adding Custom Tests

### 1. Insert Test Configuration

```sql
INSERT INTO llm_test_runs (test_name, description, prompt_template, max_lines)
VALUES (
    'My Custom Test',
    'Description of what this tests',
    'Your prompt template with {output_dir} and {max_lines} placeholders',
    500  -- Max lines allowed
);
```

### 2. Run the Test

```bash
python3 workers/llm_test_runner.py --test "My Custom Test"
```

---

## Current Test: Calculator Web App

**Prompt Template:**
```
Create a simple Calculator web application in {output_dir} with:
1. calculator.html - Main HTML page with calculator interface
2. calculator.js - JavaScript for calculator logic
3. calculator.css - Styling
4. README.md - Brief description

Requirements:
- Basic arithmetic operations (add, subtract, multiply, divide)
- Display calculation history (last 5 calculations)
- Clear button to reset
- Responsive design
- Keep it simple and functional
- Total implementation under {max_lines} lines
```

**Success Criteria:**
- At least 3 files generated
- Total lines ≤ max_lines (1000)
- Files contain valid code
- No errors during generation

---

## Benefits

### For Development

- ✓ **Standardized Testing:** Same prompt across all providers
- ✓ **Automated Execution:** No manual intervention
- ✓ **Performance Tracking:** Duration, code size, success rate
- ✓ **Quality Metrics:** Line count, file count, test pass/fail
- ✓ **Historical Data:** Track improvements over time

### For Operations

- ✓ **Provider Comparison:** See which providers work best
- ✓ **Availability Monitoring:** Detect when providers are down
- ✓ **Cost Optimization:** Compare efficiency across providers
- ✓ **Failover Planning:** Know which providers are reliable

### For Decision Making

- ✓ **Data-Driven:** Real metrics for provider selection
- ✓ **Trend Analysis:** Performance changes over time
- ✓ **Capacity Planning:** Understand session availability
- ✓ **Budget Planning:** Cost per successful generation

---

## Troubleshooting

### Issue: All Tests Failing

**Cause:** All Claude sessions busy

**Solution:**
1. Check session availability: `python3 scripts/session_terminal.py --sessions`
2. Wait for sessions to become idle
3. Or implement session queuing system

### Issue: Timeout on All Tests

**Cause:** Prompts not being processed

**Check:**
1. Is session responsive? `tmux capture-pane -t architect -p`
2. Is Claude Code active? Look for prompt indicators
3. Is output directory writable? `ls -la /tmp/llm_test_*`

### Issue: No Files Generated

**Cause:** Prompt format or session issue

**Debug:**
1. Check session output: `tmux attach -t architect`
2. Verify prompt was sent correctly
3. Check for error messages in session

---

## Future Enhancements

### Short Term
- [ ] Web UI for starting tests
- [ ] Real-time progress monitoring
- [ ] Email notifications on completion
- [ ] Test result visualizations (charts)

### Medium Term
- [ ] Multi-round testing (stability)
- [ ] Code quality scoring
- [ ] Performance regression detection
- [ ] Automated scheduling (daily/weekly)

### Long Term
- [ ] A/B testing framework
- [ ] Custom scoring algorithms
- [ ] Machine learning for quality prediction
- [ ] Integration with CI/CD pipelines

---

## Status

**Version:** 1.0.0
**Status:** ✅ Ready for use
**Database:** Migrated (032_llm_provider_tests.sql)
**API:** Implemented (services/llm_test_routes.py)
**CLI:** Functional (workers/llm_test_runner.py)
**Dashboard:** Pending integration

**Next Step:** Integrate API routes into main app.py and add dashboard UI
