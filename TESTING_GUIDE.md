# Testing Guide

Complete guide for running, developing, and maintaining tests in the Architect Dashboard.

---

## Quick Start

### Installation

```bash
# Clone repository
git clone <repo-url>
cd architect

# Install dependencies
./run_tests.sh --install

# Run tests
./run_tests.sh
```

### First Time Running Tests

```bash
# Install Playwright browsers
playwright install

# Run unit tests only (fast)
./run_tests.sh --type unit

# Run all tests
./run_tests.sh
```

---

## Running Tests

### Using the Master Script

The `run_tests.sh` script handles all test execution:

```bash
# Show help
./run_tests.sh --help

# Run all tests (default)
./run_tests.sh

# Run specific test type
./run_tests.sh --type unit
./run_tests.sh --type integration
./run_tests.sh --type e2e
./run_tests.sh --type smoke

# Run in parallel (faster)
./run_tests.sh --parallel

# Run with HTML report
./run_tests.sh --report

# Run without coverage
./run_tests.sh --no-coverage

# Watch mode (re-run on changes)
./run_tests.sh --watch

# E2E with Firefox and visible browser
./run_tests.sh --type e2e --browser firefox --headed

# Install dependencies
./run_tests.sh --install
```

### Using pytest Directly

```bash
# Run all tests
pytest

# Run specific file
pytest tests/test_api.py

# Run specific test class
pytest tests/test_api.py::TestProjects

# Run specific test
pytest tests/test_api.py::TestProjects::test_create

# Run with verbosity
pytest -v
pytest -vv  # Extra verbose

# Run with markers
pytest -m unit              # Only unit tests
pytest -m integration       # Only integration tests
pytest -m "not slow"        # Skip slow tests
pytest -m "smoke or unit"   # Smoke OR unit tests

# Run with coverage
pytest --cov=src --cov-report=html

# Run in parallel
pytest -n auto

# Run specific marker with timeout
pytest -m integration --timeout=120

# Generate HTML report
pytest --html=report.html --self-contained-html
```

---

## Test Organization

```
tests/
├── conftest.py                          # Shared fixtures
├── test_*.py                            # Unit tests
├── test_data_persistence_integration.py # Integration tests
├── e2e/                                 # E2E tests
│   ├── conftest.py
│   ├── pytest.ini
│   ├── run_tests.sh
│   ├── test_auth.py
│   ├── test_dashboard.py
│   ├── test_workflows.py
│   └── pages/                          # Page Object Models
│       ├── base_page.py
│       ├── login_page.py
│       ├── dashboard_page.py
│       ├── projects_page.py
│       └── tasks_page.py
```

---

## Test Types

### Unit Tests
- Fast, isolated tests of individual functions
- Marked with `@pytest.mark.unit`
- No external dependencies (database, network)
- Located in `tests/test_*.py`

```bash
./run_tests.sh --type unit
```

### Integration Tests
- Multi-component tests with database/API
- Marked with `@pytest.mark.integration`
- Test data persistence, CRUD operations, transactions
- Located in `tests/test_*_integration.py`

```bash
./run_tests.sh --type integration
```

### E2E Tests
- Full application workflow tests
- Use real browser (Playwright)
- Test UI interactions and navigation
- Located in `tests/e2e/`

```bash
./run_tests.sh --type e2e
```

### Smoke Tests
- Quick tests of critical functionality
- Marked with `@pytest.mark.smoke`
- Should complete in <30 seconds total

```bash
./run_tests.sh --type smoke
```

---

## Fixtures

### Common Fixtures

```python
# Authentication
def test_requires_auth(authenticated_client):
    """Test with authenticated API client."""
    response = authenticated_client.get('/api/projects')
    assert response.status_code == 200

# Database
def test_with_clean_db(clean_database):
    """Test with isolated database."""
    # Database is clean, changes are rolled back after test
    pass

# Test Data
def test_with_valid_inputs(valid_inputs):
    """Test with various valid inputs."""
    assert 'short_text' in valid_inputs
    assert 'long_text' in valid_inputs

def test_with_invalid_inputs(invalid_inputs):
    """Test with invalid/edge-case inputs."""
    assert '' in invalid_inputs.values()
    assert None in invalid_inputs.values()

# API Tests
def test_all_endpoints(api_endpoints):
    """Parametrized test runs for all endpoints."""
    # This test runs for each endpoint in api_endpoints
    pass

def test_status_codes(http_status_codes):
    """Test different HTTP status codes."""
    assert http_status_codes['status_code'] in [200, 201, 400, 404]
```

### Browser Fixtures (E2E)

```python
def test_login(page):
    """Test with a fresh browser page."""
    page.goto('http://localhost:8099/login')
    # Use page for interactions

def test_authenticated(authenticated_page):
    """Test with logged-in browser state."""
    # authenticated_page is already logged in
    page.goto('http://localhost:8099/')
    # Page is on dashboard

def test_with_api_client(api_client):
    """Make API requests from browser context."""
    response = api_client.get('/api/projects')
    assert response.status_code == 200
```

---

## Writing Tests

### Unit Test Example

```python
import pytest
from mymodule import function_to_test

class TestMyFunction:
    """Test suite for my_function."""

    def test_basic_functionality(self):
        """Test basic operation."""
        result = function_to_test(5)
        assert result == 10

    @pytest.mark.parametrize("input,expected", [
        (1, 2),
        (5, 10),
        (0, 0),
    ])
    def test_various_inputs(self, input, expected):
        """Test with parametrized inputs."""
        result = function_to_test(input)
        assert result == expected

    def test_error_handling(self):
        """Test error cases."""
        with pytest.raises(ValueError):
            function_to_test(-1)
```

### Integration Test Example

```python
import pytest

@pytest.mark.integration
class TestDataPersistence:
    """Integration tests for data persistence."""

    def test_create_and_retrieve(self, authenticated_client):
        """Test create-read workflow."""
        # Create
        response = authenticated_client.post(
            '/api/projects',
            json={'name': 'Test Project', 'description': 'Test'}
        )
        assert response.status_code in [200, 201]
        project = response.get_json()
        project_id = project['id']

        # Retrieve
        response = authenticated_client.get(f'/api/projects/{project_id}')
        assert response.status_code == 200
        assert response.get_json()['name'] == 'Test Project'

    def test_concurrent_operations(self, authenticated_client):
        """Test concurrent requests."""
        import threading

        results = []
        def create_project():
            response = authenticated_client.post(
                '/api/projects',
                json={'name': f'Project {uuid.uuid4()}', 'description': 'Test'}
            )
            if response.status_code in [200, 201]:
                results.append(response.get_json())

        threads = [threading.Thread(target=create_project) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) >= 4  # Most succeeded
```

### E2E Test Example

```python
import pytest
from playwright.sync_api import Page

@pytest.mark.e2e
class TestAuthentication:
    """E2E tests for authentication."""

    def test_login_flow(self, page: Page, app_server):
        """Test complete login workflow."""
        from tests.e2e.pages import LoginPage

        login_page = LoginPage(page, 'http://localhost:8099')
        login_page.navigate()
        login_page.login('testuser', 'testpass')

        page.wait_for_url('http://localhost:8099/')
        assert '/login' not in page.url

    def test_session_persists(self, authenticated_page: Page):
        """Test session persists on navigation."""
        authenticated_page.goto('http://localhost:8099/#projects')
        assert 'login' not in authenticated_page.url
```

---

## Markers

### Using Markers

```python
import pytest

@pytest.mark.unit
def test_something():
    """Fast unit test."""
    pass

@pytest.mark.integration
def test_database_operation():
    """Integration test with database."""
    pass

@pytest.mark.e2e
def test_ui_workflow():
    """End-to-end browser test."""
    pass

@pytest.mark.slow
def test_slow_operation():
    """Takes >1 second to run."""
    pass

@pytest.mark.requires_db
@pytest.mark.integration
def test_with_database():
    """Requires database setup."""
    pass

@pytest.mark.concurrent
def test_parallel_operations():
    """Can run in parallel."""
    pass
```

### Filtering by Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Run slow tests only
pytest -m slow

# Run multiple markers (OR)
pytest -m "unit or smoke"

# Run multiple markers (AND)
pytest -m "integration and api"

# Complex filters
pytest -m "not slow and (unit or smoke)"
```

---

## Coverage

### Generating Coverage Reports

```bash
# Coverage with HTML report
pytest --cov=src --cov-report=html

# Coverage in terminal with missing lines
pytest --cov=src --cov-report=term-missing

# XML report for CI/CD
pytest --cov=src --cov-report=xml

# Multiple formats
pytest --cov=src --cov-report=html --cov-report=xml --cov-report=term

# Coverage for specific packages
pytest --cov=mymodule --cov=anothermodule
```

### Viewing Coverage Report

```bash
# Open HTML report in browser
open htmlcov/index.html

# View coverage.xml in CI/CD
cat coverage.xml
```

---

## Debugging Tests

### Run with Verbose Output

```bash
pytest -v          # Verbose
pytest -vv         # Extra verbose
pytest -vvv        # Very verbose
```

### Run with Print Statements

```bash
# Normally prints are captured. Use -s to show them:
pytest -s tests/test_example.py

# Or use --capture=no
pytest --capture=no tests/test_example.py
```

### Debug Individual Test

```python
def test_example():
    """Test to debug."""
    import pdb
    pdb.set_trace()  # Debugger will stop here
    result = some_function()
    assert result == expected
```

### Run with Python Debugger

```bash
# Run with debugger on failure
pytest --pdb tests/test_example.py

# Drop to debugger on first failure
pytest -x --pdb tests/test_example.py
```

---

## Common Issues

### Tests Fail Intermittently (Flaky Tests)

**Mark as flaky:**
```python
@pytest.mark.flaky(reruns=3)
def test_potentially_flaky():
    pass
```

**Causes:**
- Timing issues (missing waits)
- Database state not clean
- External service timeouts
- Non-deterministic behavior

**Solutions:**
- Add explicit waits: `WebDriverWait`, `page.wait_for()`
- Use `clean_database` fixture
- Mock external services
- Make tests deterministic

### Timeout Errors

```bash
# Increase timeout
pytest --timeout=600  # 10 minutes

# No timeout
pytest -p no:timeout
```

### Database Errors

```python
# Ensure using clean_database fixture
def test_something(clean_database):
    # Database is isolated for this test
    pass

# Or db_transaction for rollback
def test_something(db_transaction):
    conn, cursor = db_transaction
    # Changes rolled back after test
    pass
```

### E2E Tests Fail

```bash
# Run headed (visible browser)
./run_tests.sh --type e2e --headed

# Run with specific browser
./run_tests.sh --type e2e --browser firefox

# Debug specific test
pytest tests/e2e/test_auth.py::TestLogin::test_login_page_renders -v -s --headed
```

### Tests Pass Locally but Fail in CI/CD

**Common causes:**
- Python version differences (test on 3.8-3.11)
- Missing dependencies
- Environment variables not set
- Timing issues on slower runners

**Solutions:**
- Test on multiple Python versions locally
- Check environment variables in CI/CD
- Add explicit waits
- Increase timeouts slightly for CI/CD

---

## Performance

### Running Tests in Parallel

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run with all CPU cores
pytest -n auto

# Run with specific number of cores
pytest -n 4

# Distribute by test file
pytest -n auto --dist=loadfile

# Distribute by test group
pytest -n auto --dist=loadscope
```

### Measuring Test Performance

```bash
# Show slowest tests
pytest --durations=10

# Show slowest 20 tests
pytest --durations=20

# With threshold (show tests >1s)
pytest --durations=10 --durations-min=1.0
```

### Optimizing Test Suite

1. **Use `--maxfail` to stop early:**
   ```bash
   pytest -x tests/  # Stop on first failure
   pytest -x --lf    # Run last failed first
   ```

2. **Mark slow tests and skip in development:**
   ```bash
   pytest -m "not slow"
   ```

3. **Run unit tests first:**
   ```bash
   pytest -m unit && pytest -m integration
   ```

4. **Use pytest-timeout:**
   ```bash
   pytest --timeout=60  # Max 60s per test
   ```

---

## CI/CD Integration

### GitHub Actions

Tests automatically run on:
- Push to main, dev, feature/* branches
- Pull requests
- Scheduled (if configured)

View results:
1. Go to repository
2. Click "Actions" tab
3. Select workflow run
4. View job details

### Coverage Badges

Add to README.md:
```markdown
![Coverage](https://img.shields.io/codecov/c/github/owner/repo)
![Tests](https://github.com/owner/repo/actions/workflows/test.yml/badge.svg)
```

---

## Best Practices

### Test Structure

```python
def test_clear_description():
    """Clear description of what is being tested."""
    # Setup
    test_data = {"key": "value"}

    # Execute
    result = function_under_test(test_data)

    # Assert
    assert result == expected_value
```

### Naming Conventions

- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`
- Test names should describe what is tested

```python
# Good
def test_create_project_with_valid_name():
    pass

# Bad
def test_proj():
    pass
```

### Assertion Messages

```python
# Good - message clarifies failure
assert result == expected, f"Expected {expected}, got {result}"

# Better - use pytest assertion rewriting
assert result == expected

# Best - clear assertion
assert user.email == "user@example.com", "User email should match input"
```

### Avoid Test Interdependencies

```python
# Bad - tests depend on order
def test_create():
    global project_id
    project_id = create_project()

def test_update():  # Depends on test_create
    update_project(project_id)

# Good - each test is independent
def test_create(authenticated_client):
    response = authenticated_client.post('/api/projects', json=data)
    assert response.status_code in [200, 201]

def test_update(authenticated_client, sample_project):
    project_id = sample_project['id']
    response = authenticated_client.put(f'/api/projects/{project_id}', json=data)
    assert response.status_code in [200, 204]
```

---

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [Playwright documentation](https://playwright.dev/python/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [pytest-xdist documentation](https://pytest-xdist.readthedocs.io/)

---

## Support

For issues or questions:
1. Check this guide
2. Review test examples in `tests/`
3. Check pytest documentation
4. Open an issue in the repository

Happy testing! 🧪
