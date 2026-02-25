# Testing Infrastructure Guide

Complete guide to testing infrastructure, test environments, campaigns, and best practices.

## Table of Contents

1. [Overview](#overview)
2. [Test Environments](#test-environments)
3. [Test Categories](#test-categories)
4. [Running Tests](#running-tests)
5. [Test Campaigns](#test-campaigns)
6. [Integration Testing](#integration-testing)
7. [End-to-End Testing](#end-to-end-testing)
8. [CI/CD Integration](#cicd-integration)
9. [Troubleshooting](#troubleshooting)

---

## Overview

### Test Infrastructure Components

| Component | Purpose | Location |
|-----------|---------|----------|
| **Unit Tests** | Test individual functions/classes | `tests/test_*.py` |
| **Integration Tests** | Test component interactions | `tests/test_*_integration.py` |
| **E2E Tests** | Test complete workflows | `tests/e2e/` |
| **Test Database** | Test runs and results tracking | `data/architect.db` tables |
| **Test Environments** | Isolated test execution | Managed by `env_manager.py` |
| **Pytest Configuration** | Test runner settings | `pytest.ini` |
| **Test Fixtures** | Shared test setup | `tests/conftest.py` |

### Statistics

- **Total Test Files**: 44 Python test files
- **Test Categories**: Unit, Integration, E2E, Browser
- **Test Markers**: `e2e`, `slow`, `integration`
- **Database Tables**: `test_runs`, `test_results`, `deployment_gates`

---

## Test Environments

### Available Environments

Test environments are managed via `env_manager.py`:

```bash
# List all environments
./env_manager.py list

# Show running status
./env_manager.py status

# Create isolated test environment
./env_manager.py create test_env_1 5100

# Start test environment
./env_manager.py start test_env_1

# Stop test environment
./env_manager.py stop test_env_1
```

### Creating Isolated Test Environments

**Purpose**: Run tests in complete isolation without affecting dev/qa/prod.

**Steps**:

1. **Create test environment**:
   ```bash
   ./env_manager.py create test_suite 5100
   ```

2. **Verify creation**:
   ```bash
   ./env_manager.py list
   # Should show: test_suite   5100   feature    no      Feature environment test_suite
   ```

3. **Start environment**:
   ```bash
   ./env_manager.py start test_suite
   # Output: ✓ Started test_suite on https://0.0.0.0:5100
   #         Database: data/test_suite/architect.db
   #         Log: /tmp/architect_test_suite.log
   ```

4. **Run tests against environment**:
   ```bash
   TEST_ENV=test_suite TEST_PORT=5100 python3 -m pytest tests/ -v
   ```

5. **Stop after testing**:
   ```bash
   ./env_manager.py stop test_suite
   ```

### Environment Configuration

Environments are configured in `data/environments.json`:

```json
{
  "architect_envs": {
    "test_suite": {
      "port": 5100,
      "type": "feature",
      "description": "Isolated test environment",
      "auto_start": false
    }
  }
}
```

---

## Test Categories

### 1. Unit Tests

**Purpose**: Test individual functions and methods in isolation.

**Location**: `tests/test_*.py` (except integration/e2e)

**Examples**:
- `test_database.py` - Database operations
- `test_api.py` - API endpoint responses
- `test_auto_assign.py` - Task assignment logic
- `test_csrf.py` - CSRF protection

**Run unit tests**:
```bash
python3 -m pytest tests/test_database.py -v
python3 -m pytest tests/test_api.py -v
```

### 2. Integration Tests

**Purpose**: Test interactions between multiple components.

**Marker**: `@pytest.mark.integration`

**Examples**:
- `test_jira_integration.py` - Jira API integration
- `test_connection_pool.py` - Database pool management
- `test_collaboration.py` - Multi-user workflows

**Run integration tests**:
```bash
python3 -m pytest -m integration -v
```

### 3. End-to-End Tests

**Purpose**: Test complete user workflows from start to finish.

**Location**: `tests/e2e/` and `tests/test_e2e_*.py`

**Types**:
- **Playwright E2E**: Browser automation tests
- **Claude Workflow E2E**: AI agent workflow tests
- **Complete Workflow**: Full system workflows

**Examples**:
- `test_e2e_playwright.py` - Browser-based UI testing
- `test_e2e_claude_workflow.py` - AI agent workflows
- `test_e2e_workflow.py` - Complete system workflows

**Run E2E tests**:
```bash
# Requires playwright
playwright install

# Run E2E tests
python3 -m pytest -m e2e -v

# Run specific E2E test
python3 -m pytest tests/test_e2e_playwright.py --browser chromium -v
```

### 4. Slow Tests

**Purpose**: Tests that take longer to execute.

**Marker**: `@pytest.mark.slow`

**Run slow tests separately**:
```bash
python3 -m pytest -m slow -v
```

---

## Running Tests

### Basic Test Execution

```bash
# Run all tests
python3 -m pytest

# Run with verbose output
python3 -m pytest -v

# Run specific test file
python3 -m pytest tests/test_api.py -v

# Run specific test function
python3 -m pytest tests/test_api.py::test_health_endpoint -v

# Run tests matching pattern
python3 -m pytest -k "database" -v
```

### Advanced Test Execution

```bash
# Run with coverage
python3 -m pytest --cov=. --cov-report=html

# Run with parallel execution (requires pytest-xdist)
python3 -m pytest -n auto

# Stop on first failure
python3 -m pytest -x

# Show local variables in tracebacks
python3 -m pytest -l

# Run last failed tests only
python3 -m pytest --lf

# Run tests in random order (requires pytest-random-order)
python3 -m pytest --random-order
```

### Running by Category

```bash
# Unit tests only (exclude markers)
python3 -m pytest -m "not integration and not e2e and not slow"

# Integration tests only
python3 -m pytest -m integration

# E2E tests only
python3 -m pytest -m e2e

# Slow tests only
python3 -m pytest -m slow

# Fast tests (exclude slow)
python3 -m pytest -m "not slow"
```

### Test Output Options

```bash
# Short traceback
python3 -m pytest --tb=short

# No traceback
python3 -m pytest --tb=no

# Show all test output (no capture)
python3 -m pytest -s

# Show 10 slowest tests
python3 -m pytest --durations=10

# Generate JUnit XML report
python3 -m pytest --junit-xml=results.xml
```

---

## Test Campaigns

### Database Schema

Test campaigns are tracked in the database:

```sql
-- Test runs
CREATE TABLE test_runs (
    id INTEGER PRIMARY KEY,
    run_id TEXT UNIQUE NOT NULL,
    project_id INTEGER,
    environment TEXT,
    triggered_by TEXT,
    trigger_type TEXT DEFAULT 'manual',
    status TEXT DEFAULT 'running',
    total_tests INTEGER DEFAULT 0,
    passed INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    skipped INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    duration_seconds REAL,
    output TEXT,
    category TEXT DEFAULT 'all',
    coverage INTEGER DEFAULT 0,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Test results (individual tests)
CREATE TABLE test_results (
    id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL,
    test_name TEXT NOT NULL,
    test_file TEXT,
    test_class TEXT,
    status TEXT NOT NULL,
    duration_seconds REAL,
    error_message TEXT,
    stack_trace TEXT,
    stdout TEXT,
    stderr TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES test_runs(run_id)
);
```

### Creating Test Campaigns

**1. Define Campaign Goal**:
```sql
INSERT INTO test_runs (
    run_id, environment, triggered_by, trigger_type, category
) VALUES (
    'campaign_regression_2026_02_10',
    'test_suite',
    'architect',
    'manual',
    'regression'
);
```

**2. Execute Tests**:
```bash
# Run test suite and capture results
python3 -m pytest tests/ -v --junit-xml=test_results.xml
```

**3. Parse and Store Results**:
```python
import xml.etree.ElementTree as ET
import sqlite3

def parse_junit_xml(xml_file, run_id):
    """Parse JUnit XML and store in database."""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    conn = sqlite3.connect('data/architect.db')

    for testsuite in root.findall('testsuite'):
        for testcase in testsuite.findall('testcase'):
            test_name = testcase.get('name')
            test_file = testcase.get('file')
            test_class = testcase.get('classname')
            duration = float(testcase.get('time', 0))

            # Determine status
            if testcase.find('failure') is not None:
                status = 'failed'
                error = testcase.find('failure').get('message')
                stack_trace = testcase.find('failure').text
            elif testcase.find('error') is not None:
                status = 'error'
                error = testcase.find('error').get('message')
                stack_trace = testcase.find('error').text
            elif testcase.find('skipped') is not None:
                status = 'skipped'
                error = None
                stack_trace = None
            else:
                status = 'passed'
                error = None
                stack_trace = None

            # Insert result
            conn.execute("""
                INSERT INTO test_results (
                    run_id, test_name, test_file, test_class,
                    status, duration_seconds, error_message, stack_trace
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (run_id, test_name, test_file, test_class,
                  status, duration, error, stack_trace))

    conn.commit()
    conn.close()

# Usage
parse_junit_xml('test_results.xml', 'campaign_regression_2026_02_10')
```

**4. Update Campaign Stats**:
```python
def update_campaign_stats(run_id):
    """Update test_runs with aggregate statistics."""
    conn = sqlite3.connect('data/architect.db')

    # Calculate stats
    stats = conn.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) as passed,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
            SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped,
            SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors,
            SUM(duration_seconds) as duration
        FROM test_results
        WHERE run_id = ?
    """, (run_id,)).fetchone()

    # Update test_runs
    conn.execute("""
        UPDATE test_runs
        SET total_tests = ?, passed = ?, failed = ?,
            skipped = ?, errors = ?, duration_seconds = ?,
            status = 'completed', completed_at = CURRENT_TIMESTAMP
        WHERE run_id = ?
    """, (*stats, run_id))

    conn.commit()
    conn.close()

# Usage
update_campaign_stats('campaign_regression_2026_02_10')
```

### Querying Campaign Results

```sql
-- Get campaign summary
SELECT run_id, environment, category, triggered_by,
       total_tests, passed, failed, skipped, errors,
       ROUND(duration_seconds, 2) as duration_sec,
       ROUND(100.0 * passed / total_tests, 1) as pass_rate,
       status, started_at, completed_at
FROM test_runs
WHERE run_id = 'campaign_regression_2026_02_10';

-- Get failed tests in campaign
SELECT test_name, test_file, error_message, duration_seconds
FROM test_results
WHERE run_id = 'campaign_regression_2026_02_10'
  AND status = 'failed'
ORDER BY duration_seconds DESC;

-- Get slowest tests
SELECT test_name, test_file, duration_seconds
FROM test_results
WHERE run_id = 'campaign_regression_2026_02_10'
ORDER BY duration_seconds DESC
LIMIT 10;
```

### Campaign Types

| Type | Trigger | Purpose |
|------|---------|---------|
| **Regression** | Manual/Scheduled | Verify no regressions after changes |
| **Integration** | PR merge | Test component interactions |
| **Smoke** | Deployment | Quick health check after deploy |
| **Full** | Release | Comprehensive pre-release testing |
| **Focused** | Bug fix | Test specific area thoroughly |

---

## Integration Testing

### Purpose

Test interactions between multiple system components:
- API ↔ Database
- Frontend ↔ Backend
- Service ↔ Service
- External integrations (Jira, Slack, LLM providers)

### Integration Test Structure

```python
import pytest
from tests.conftest import client, app

@pytest.mark.integration
def test_task_assignment_workflow(client):
    """Test complete task assignment workflow."""
    # 1. Create task
    response = client.post('/api/tasks', json={
        'title': 'Test Task',
        'priority': 'high'
    })
    assert response.status_code == 201
    task_id = response.json['task_id']

    # 2. Assign task
    response = client.post(f'/api/tasks/{task_id}/assign', json={
        'assignee_id': 1
    })
    assert response.status_code == 200

    # 3. Update status
    response = client.put(f'/api/tasks/{task_id}', json={
        'status': 'in_progress'
    })
    assert response.status_code == 200

    # 4. Verify task state
    response = client.get(f'/api/tasks/{task_id}')
    assert response.json['status'] == 'in_progress'
    assert response.json['assignee_id'] == 1
```

### Database Integration Tests

```python
@pytest.mark.integration
def test_database_cascade_delete(app):
    """Test cascade delete behavior."""
    with app.app_context():
        conn = get_db()

        # Create project with tasks
        cursor = conn.execute("""
            INSERT INTO projects (name, description)
            VALUES ('Test Project', 'Description')
        """)
        project_id = cursor.lastrowid

        conn.execute("""
            INSERT INTO tasks (project_id, title)
            VALUES (?, 'Task 1'), (?, 'Task 2')
        """, (project_id, project_id))
        conn.commit()

        # Delete project
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()

        # Verify tasks also deleted
        task_count = conn.execute("""
            SELECT COUNT(*) FROM tasks WHERE project_id = ?
        """, (project_id,)).fetchone()[0]

        assert task_count == 0
```

### External Integration Tests

```python
@pytest.mark.integration
def test_llm_provider_failover(app):
    """Test LLM provider failover mechanism."""
    from services.llm_provider import UnifiedLLMClient

    client = UnifiedLLMClient()

    # Should succeed with primary or failover
    response = client.messages.create(
        model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=100
    )

    assert response is not None
    assert 'provider' in response
    assert response['provider'] in ['claude', 'ollama', 'anythingllm', 'gemini', 'openai']
```

---

## End-to-End Testing

### Playwright E2E Tests

**Setup**:
```bash
# Install Playwright
pip install playwright pytest-playwright

# Install browsers
playwright install chromium firefox webkit
```

**Example E2E Test**:
```python
import pytest
from playwright.sync_api import Page, expect

@pytest.mark.e2e
def test_login_workflow(page: Page):
    """Test complete login workflow."""
    # Navigate to login
    page.goto("https://localhost:5051/login")

    # Fill in credentials
    page.fill('input[name="username"]', 'testuser')
    page.fill('input[name="password"]', 'testpass')

    # Click login
    page.click('button[type="submit"]')

    # Verify redirect to dashboard
    expect(page).to_have_url("https://localhost:5051/dashboard")

    # Verify user info displayed
    expect(page.locator('.user-info')).to_contain_text('testuser')
```

**Running Playwright Tests**:
```bash
# Run with Chromium
python3 -m pytest tests/test_e2e_playwright.py --browser chromium

# Run with multiple browsers
python3 -m pytest tests/test_e2e_playwright.py --browser chromium --browser firefox

# Run headless (default)
python3 -m pytest tests/test_e2e_playwright.py

# Run headed (show browser)
python3 -m pytest tests/test_e2e_playwright.py --headed

# Debug mode
python3 -m pytest tests/test_e2e_playwright.py --headed --slowmo 1000
```

### Claude Workflow E2E Tests

Tests for AI agent workflows:

```python
@pytest.mark.e2e
def test_autonomous_task_execution():
    """Test autonomous agent completing a task."""
    # Create task
    task_id = create_task("Implement feature X")

    # Assign to agent
    assign_to_agent(task_id, "claude-worker-1")

    # Monitor progress
    wait_for_completion(task_id, timeout=300)

    # Verify completion
    result = get_task_result(task_id)
    assert result['status'] == 'completed'
    assert result['success'] == True
```

### API Workflow E2E Tests

```python
@pytest.mark.e2e
def test_complete_deployment_workflow(client):
    """Test complete deployment from commit to production."""
    # 1. Create commit
    commit_hash = create_test_commit()

    # 2. Trigger CI
    response = client.post('/api/ci/trigger', json={
        'commit': commit_hash
    })
    assert response.status_code == 200
    build_id = response.json['build_id']

    # 3. Wait for tests
    wait_for_tests(build_id)

    # 4. Deploy to QA
    response = client.post('/api/deploy', json={
        'environment': 'qa',
        'build_id': build_id
    })
    assert response.status_code == 200

    # 5. Verify QA deployment
    qa_health = client.get('https://qa-server:5052/health')
    assert qa_health.status_code == 200

    # 6. Promote to prod
    response = client.post('/api/deploy/promote', json={
        'from': 'qa',
        'to': 'prod',
        'build_id': build_id
    })
    assert response.status_code == 200
```

---

## CI/CD Integration

### GitHub Actions Integration

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.14'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov

    - name: Run tests
      run: |
        python3 -m pytest tests/ -v --junit-xml=results.xml --cov=. --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v2
      with:
        files: ./coverage.xml

    - name: Upload test results
      uses: actions/upload-artifact@v2
      with:
        name: test-results
        path: results.xml
```

### Pre-commit Hook Integration

```bash
# .git/hooks/pre-commit
#!/bin/bash

echo "Running tests before commit..."

# Run fast tests only
python3 -m pytest -m "not slow and not e2e" --tb=short

if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi

echo "Tests passed. Proceeding with commit."
```

### Deployment Gate Integration

```python
def check_deployment_gate(environment):
    """Check if deployment gate requirements met."""
    conn = sqlite3.connect('data/architect.db')

    # Get gate requirements
    gate = conn.execute("""
        SELECT requires_tests, min_test_pass_rate
        FROM deployment_gates
        WHERE environment = ?
    """, (environment,)).fetchone()

    if not gate or not gate[0]:
        return True  # No gate or tests not required

    # Get latest test run
    test_run = conn.execute("""
        SELECT passed, total_tests
        FROM test_runs
        WHERE environment = ? AND status = 'completed'
        ORDER BY completed_at DESC
        LIMIT 1
    """, (environment,)).fetchone()

    if not test_run:
        return False  # No test runs found

    pass_rate = (test_run[0] / test_run[1]) * 100
    min_pass_rate = gate[1]

    return pass_rate >= min_pass_rate

# Usage in deployment
if check_deployment_gate('prod'):
    deploy_to_prod()
else:
    print("Deployment gate not met. Run tests first.")
```

---

## Troubleshooting

### Common Issues

#### 1. Database Lock Errors

**Symptom**: `sqlite3.OperationalError: database is locked`

**Solutions**:
- Use isolated test environment
- Enable WAL mode: `PRAGMA journal_mode=WAL;`
- Increase busy_timeout: `PRAGMA busy_timeout=30000;`
- Close all connections properly

```python
# Good practice
with get_db() as conn:
    conn.execute("...")
# Connection automatically closed
```

#### 2. Import Errors

**Symptom**: `ModuleNotFoundError: No module named '...'`

**Solutions**:
```bash
# Install test dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install pytest pytest-cov pytest-asyncio pytest-flask

# Run from project root
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect
python3 -m pytest
```

#### 3. Fixture Not Found

**Symptom**: `fixture 'app' not found`

**Solutions**:
- Ensure `conftest.py` is in tests directory
- Check pytest configuration in `pytest.ini`
- Verify imports in test file

#### 4. Async Test Failures

**Symptom**: `RuntimeError: Event loop is closed`

**Solutions**:
```python
# Use pytest-asyncio
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await async_operation()
    assert result is not None
```

#### 5. Port Already in Use

**Symptom**: `OSError: [Errno 48] Address already in use`

**Solutions**:
```bash
# Find process on port
lsof -ti :5100

# Kill process
kill -9 $(lsof -ti :5100)

# Or use env_manager
./env_manager.py stop test_suite
```

### Debug Tips

```bash
# Run with verbose output
python3 -m pytest -vv

# Show local variables on failure
python3 -m pytest -l

# Drop into debugger on failure
python3 -m pytest --pdb

# Don't capture output (show prints)
python3 -m pytest -s

# Run specific test with all debug info
python3 -m pytest tests/test_api.py::test_endpoint -vvl -s

# Show pytest version and plugins
python3 -m pytest --version
python3 -m pytest --help
```

### Performance Profiling

```bash
# Show 20 slowest tests
python3 -m pytest --durations=20

# Profile with pytest-profiling
pip install pytest-profiling
python3 -m pytest --profile

# Memory profiling with pytest-memprof
pip install pytest-memprof
python3 -m pytest --memprof
```

---

## Best Practices

### 1. Test Organization

```
tests/
├── conftest.py              # Shared fixtures
├── test_api.py              # API tests
├── test_database.py         # Database tests
├── test_integration.py      # Integration tests
├── e2e/                     # End-to-end tests
│   ├── test_workflows.py
│   └── test_ui.py
└── fixtures/                # Test data
    ├── sample_data.json
    └── test_database.sql
```

### 2. Test Naming

```python
# Good
def test_user_creation_with_valid_data():
    ...

def test_user_creation_with_duplicate_email_raises_error():
    ...

# Bad
def test1():
    ...

def test_user():
    ...
```

### 3. Test Independence

```python
# Each test should be independent
def test_create_user():
    user = create_user("test@example.com")
    assert user is not None
    # Cleanup
    delete_user(user.id)

# Or use fixtures for cleanup
@pytest.fixture
def user():
    u = create_user("test@example.com")
    yield u
    delete_user(u.id)

def test_user_login(user):
    result = login(user.email, "password")
    assert result.success
```

### 4. Assertion Messages

```python
# Good
assert len(results) == 5, f"Expected 5 results, got {len(results)}"
assert user.active, f"User {user.id} should be active after creation"

# Bad
assert len(results) == 5
assert user.active
```

### 5. Test Data Management

```python
# Use fixtures for test data
@pytest.fixture
def sample_tasks():
    return [
        {'title': 'Task 1', 'priority': 'high'},
        {'title': 'Task 2', 'priority': 'medium'},
        {'title': 'Task 3', 'priority': 'low'},
    ]

def test_task_filtering(sample_tasks):
    high_priority = filter_tasks(sample_tasks, priority='high')
    assert len(high_priority) == 1
```

---

**Last Updated**: 2026-02-10
**Version**: 1.0
**Maintainer**: Architect Team
