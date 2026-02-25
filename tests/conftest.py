"""
Pytest fixtures for Architect Dashboard tests
"""
import importlib.util
import os
import sqlite3
import sys
import tempfile

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Check for playwright availability and skip e2e tests if not available
def pytest_configure(config):
    """Configure pytest and handle playwright dependency."""
    _playwright_spec = importlib.util.find_spec("playwright.sync_api")
    if _playwright_spec is None:
        # Register marker for skipping e2e tests
        config.addinivalue_line(
            "markers", "e2e: End-to-end tests (require playwright) - skipped if not installed"
        )


def pytest_collection_modifyitems(config, items):
    """Skip e2e tests if playwright is not installed."""
    _playwright_spec = importlib.util.find_spec("playwright.sync_api")
    if _playwright_spec is None:
        # Skip all tests marked as e2e
        skip_e2e = pytest.mark.skip(reason="Playwright not installed")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)


@pytest.fixture(scope="session")
def app():
    """Create application for testing."""
    # Set test environment
    os.environ["APP_ENV"] = "test"
    os.environ["ARCHITECT_USER"] = "testuser"
    os.environ["ARCHITECT_PASSWORD"] = "testpass"

    # Create temp database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    os.environ["DB_PATH"] = db_path

    # Import app after setting env vars
    # If already imported, we need to reload to get the new DB_PATH
    if "app" in sys.modules:
        # Remove cached module to force fresh import
        del sys.modules["app"]

    import app as flask_app

    # Verify database was initialized with all tables
    with sqlite3.connect(db_path) as conn:
        # Verify deployment tables exist
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t[0] for t in tables]

        # If deployment tables don't exist, reinitialize
        if "deployments" not in table_names or "deployment_gates" not in table_names:
            flask_app.init_database()

    flask_app.app.config["TESTING"] = True
    flask_app.app.config["WTF_CSRF_ENABLED"] = False

    yield flask_app.app

    # Cleanup
    try:
        os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture
def client(app):
    """Create test client."""
    with app.test_client() as client:
        yield client


@pytest.fixture
def authenticated_client(client):
    """Create authenticated test client."""
    client.post("/login", data={"username": "testuser", "password": "testpass"})
    yield client


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Create basic tables
    conn.execute(
        """
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'active'
        )
    """
    )
    conn.execute(
        """
        CREATE TABLE features (
            id INTEGER PRIMARY KEY,
            project_id INTEGER,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'draft'
        )
    """
    )
    conn.commit()

    yield conn, db_path

    conn.close()
    try:
        os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture
def sample_project(authenticated_client):
    """Create a sample project for testing, or return existing one."""
    import time
    import uuid

    # Try to create with unique name
    unique_name = f"Test Project {uuid.uuid4().hex[:8]}"
    response = authenticated_client.post(
        "/api/projects", json={"name": unique_name, "description": "A test project"}
    )
    result = response.get_json()

    # If created successfully, return it
    if result.get("id"):
        return result

    # If failed (e.g., duplicate), try to get existing project
    if "error" in result:
        # Get list of projects and return first one
        list_response = authenticated_client.get("/api/projects")
        projects = list_response.get_json()
        if projects and isinstance(projects, list) and len(projects) > 0:
            return projects[0]

        # If no projects exist, create one with a timestamp
        fallback_name = f"Test Project {int(time.time() * 1000)}"
        fallback_response = authenticated_client.post(
            "/api/projects",
            json={"name": fallback_name, "description": "A test project (fallback)"},
        )
        fallback_result = fallback_response.get_json()
        if fallback_result.get("id"):
            return fallback_result

    # Return a minimal valid project dict as last resort
    return {"id": 1, "name": unique_name, "description": "Fallback project"}


@pytest.fixture
def sample_feature(authenticated_client, sample_project):
    """Create a sample feature for testing."""
    response = authenticated_client.post(
        "/api/features",
        json={
            "project_id": sample_project.get("id", 1),
            "name": "Test Feature",
            "description": "A test feature",
        },
    )
    return response.get_json()


# =========================================================================
# Enhanced Fixtures for Comprehensive Testing
# =========================================================================


@pytest.fixture
def valid_inputs():
    """Fixture providing valid input values for testing."""
    return {
        "short_text": "hello",
        "medium_text": "This is a medium length text",
        "long_text": "A" * 100,
        "special_underscore": "test_with_underscore",
        "numbers": "test123",
        "mixed_case": "TestMixedCase",
        "email": "test@example.com",
        "url": "https://example.com",
        "unicode": "café",
        "whitespace_trimmed": "  text with spaces  ",
    }


@pytest.fixture
def invalid_inputs():
    """Fixture providing invalid input values that should be rejected."""
    return {
        "empty": "",
        "whitespace_only": "   ",
        "tabs": "\t\t\t",
        "newlines": "\n\n",
        "null": None,
        "too_long": "A" * 10000,
        "sql_injection": "'; DROP TABLE users; --",
        "xss_attack": "<script>alert('xss')</script>",
        "path_traversal": "../../etc/passwd",
    }


@pytest.fixture
def edge_case_inputs():
    """Fixture providing edge case inputs for boundary testing."""
    return {
        "single_char": "a",
        "two_chars": "ab",
        "max_reasonable": "A" * 1000,
        "special_chars": "!@#$%^&*()",
        "unicode_symbols": "🎉🎊✨",
        "mixed_unicode_ascii": "hello🌍world",
        "control_chars": "\x00\x01\x02",
        "high_unicode": "\uffff",
        "combining_chars": "e\u0301",  # é as e + combining accent
    }


@pytest.fixture
def api_test_data():
    """Fixture providing common API test data."""
    return {
        "valid_project": {"name": "Test Project", "description": "Test Description"},
        "valid_feature": {"name": "Test Feature", "description": "Test Description"},
        "valid_task": {"title": "Test Task", "description": "Test Description"},
        "invalid_empty": {"name": "", "description": ""},
        "invalid_null": {"name": None, "description": None},
        "invalid_long_name": {"name": "A" * 500, "description": "Test"},
    }


@pytest.fixture
def clean_database(test_db):
    """Fixture for clean database before each test with automatic cleanup."""
    conn, db_path = test_db

    yield conn

    # Cleanup after test
    try:
        conn.close()
        os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture
def db_transaction(test_db):
    """Fixture providing database transaction with rollback for isolation."""
    conn, db_path = test_db

    # Begin transaction
    conn.isolation_level = None
    cursor = conn.cursor()

    try:
        yield conn, cursor
    finally:
        # Rollback all changes
        try:
            conn.rollback()
        except Exception:
            pass
        finally:
            cursor.close()
            conn.close()
            try:
                os.unlink(db_path)
            except Exception:
                pass


@pytest.fixture(params=[
    "projects",
    "features",
    "bugs",
    "tasks",
    "errors",
    "nodes",
])
def api_endpoints(request):
    """Parametrized fixture for testing all API endpoints."""
    return request.param


@pytest.fixture(params=[
    {"status_code": 200, "description": "Success"},
    {"status_code": 201, "description": "Created"},
    {"status_code": 204, "description": "No Content"},
    {"status_code": 400, "description": "Bad Request"},
    {"status_code": 401, "description": "Unauthorized"},
    {"status_code": 403, "description": "Forbidden"},
    {"status_code": 404, "description": "Not Found"},
    {"status_code": 500, "description": "Internal Server Error"},
])
def http_status_codes(request):
    """Parametrized fixture for HTTP status codes."""
    return request.param


@pytest.fixture
def form_validation_data():
    """Fixture providing data for form validation testing."""
    return {
        "required_fields": [
            {"field": "name", "empty_value": "", "error_msg": "required"},
            {"field": "description", "empty_value": "", "error_msg": "required"},
        ],
        "max_length": [
            {"field": "name", "max": 255, "test_value": "A" * 256},
            {"field": "description", "max": 1000, "test_value": "A" * 1001},
        ],
        "invalid_formats": [
            {"field": "email", "value": "invalid-email", "error_msg": "invalid"},
            {"field": "url", "value": "not a url", "error_msg": "invalid"},
        ],
    }


@pytest.fixture
def error_scenarios():
    """Fixture providing common error scenarios for testing."""
    return {
        "not_found": {
            "status": 404,
            "message": "Not found",
            "resource": "project",
            "id": 999999,
        },
        "conflict": {
            "status": 409,
            "message": "Already exists",
            "resource": "name",
        },
        "validation_error": {
            "status": 400,
            "message": "Validation failed",
            "errors": [
                {"field": "name", "message": "Required"},
                {"field": "email", "message": "Invalid format"},
            ],
        },
        "server_error": {
            "status": 500,
            "message": "Internal server error",
        },
        "unavailable": {
            "status": 503,
            "message": "Service unavailable",
        },
    }


@pytest.fixture
def concurrent_test_data():
    """Fixture providing data for concurrent/parallel testing."""
    import uuid
    return {
        "user1": {"id": str(uuid.uuid4()), "name": "User 1"},
        "user2": {"id": str(uuid.uuid4()), "name": "User 2"},
        "user3": {"id": str(uuid.uuid4()), "name": "User 3"},
        "tasks": [
            {"title": f"Task {i}", "user": f"user{i % 3 + 1}"}
            for i in range(10)
        ],
    }


@pytest.fixture
def performance_test_data():
    """Fixture providing large datasets for performance testing."""
    return {
        "small": list(range(10)),
        "medium": list(range(1000)),
        "large": list(range(10000)),
        "items": [
            {"id": i, "name": f"Item {i}", "value": i * 1.5}
            for i in range(1000)
        ],
    }


# =========================================================================
# Pytest Markers and Hooks (Extended)
# =========================================================================


def pytest_configure_markers(config):
    """Add additional markers for comprehensive test organization."""
    # Additional markers for test categorization
    markers = [
        "requires_db: Tests requiring database",
        "requires_network: Tests requiring network",
        "concurrent: Concurrent/parallel tests",
        "security: Security-related tests",
        "flaky: Tests that may be flaky",
    ]

    for marker in markers:
        config.addinivalue_line("markers", marker)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Store test result for use in fixtures."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


def pytest_collection_modifyitems_extended(config, items):
    """Add markers and modify test collection (extended)."""
    # Auto-mark slow tests
    for item in items:
        if "slow" in item.nodeid.lower() or "performance" in item.nodeid.lower():
            item.add_marker(pytest.mark.slow)

        # Auto-mark integration tests
        if "integration" in item.nodeid.lower():
            item.add_marker(pytest.mark.integration)

        # Auto-mark concurrent tests
        if "concurrent" in item.nodeid.lower():
            item.add_marker(pytest.mark.concurrent)
