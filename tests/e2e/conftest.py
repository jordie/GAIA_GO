"""
Playwright E2E Test Configuration and Fixtures

This module provides shared fixtures, configuration, and utilities
for end-to-end browser testing with Playwright.
"""
import json
import os
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator

import pytest

# Skip entire module if playwright not installed
pytest.importorskip("playwright")

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

# =============================================================================
# Configuration
# =============================================================================


class E2EConfig:
    """E2E test configuration."""

    # Server settings
    PORT = int(os.environ.get("E2E_PORT", 8099))
    HOST = os.environ.get("E2E_HOST", "localhost")
    BASE_URL = f"http://{HOST}:{PORT}"

    # Authentication
    USERNAME = os.environ.get("E2E_USER", "architect")
    PASSWORD = os.environ.get("E2E_PASSWORD", "peace5")

    # Timeouts (milliseconds)
    DEFAULT_TIMEOUT = 30000
    NAVIGATION_TIMEOUT = 60000
    ACTION_TIMEOUT = 10000

    # Browser settings
    HEADLESS = os.environ.get("E2E_HEADLESS", "true").lower() == "true"
    SLOW_MO = int(os.environ.get("E2E_SLOW_MO", 0))

    # Screenshots and traces
    SCREENSHOT_ON_FAILURE = True
    TRACE_ON_FAILURE = True
    ARTIFACTS_DIR = Path(__file__).parent / "artifacts"

    # Video recording
    RECORD_VIDEO = os.environ.get("E2E_RECORD_VIDEO", "false").lower() == "true"

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        return {
            "port": cls.PORT,
            "base_url": cls.BASE_URL,
            "headless": cls.HEADLESS,
            "slow_mo": cls.SLOW_MO,
            "default_timeout": cls.DEFAULT_TIMEOUT,
        }


# =============================================================================
# Server Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def app_server() -> Generator[subprocess.Popen, None, None]:
    """
    Start the Flask application server for E2E tests.

    This fixture has session scope - server starts once for all tests.
    """
    env = os.environ.copy()
    env.update(
        {
            "PORT": str(E2EConfig.PORT),
            "ARCHITECT_USER": E2EConfig.USERNAME,
            "ARCHITECT_PASSWORD": E2EConfig.PASSWORD,
            "APP_ENV": "test",
            "FLASK_ENV": "testing",
        }
    )

    app_path = Path(__file__).parent.parent.parent / "app.py"

    # Start server
    proc = subprocess.Popen(
        ["python3", str(app_path)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(app_path.parent),
    )

    # Wait for server to be ready
    import requests

    max_wait = 30
    for i in range(max_wait * 2):
        try:
            resp = requests.get(f"{E2EConfig.BASE_URL}/health", timeout=1)
            if resp.status_code == 200:
                print(f"\n[E2E] Server started on port {E2EConfig.PORT}")
                break
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.5)
    else:
        proc.kill()
        stdout, stderr = proc.communicate()
        raise RuntimeError(
            f"Server failed to start within {max_wait}s\n"
            f"stdout: {stdout.decode()}\n"
            f"stderr: {stderr.decode()}"
        )

    yield proc

    # Cleanup
    print("\n[E2E] Stopping server...")
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


# =============================================================================
# Browser Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def browser_type_launch_args() -> Dict[str, Any]:
    """Browser launch arguments."""
    return {
        "headless": E2EConfig.HEADLESS,
        "slow_mo": E2EConfig.SLOW_MO,
    }


@pytest.fixture(scope="session")
def browser_context_args() -> Dict[str, Any]:
    """Browser context arguments."""
    args = {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }

    if E2EConfig.RECORD_VIDEO:
        E2EConfig.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        args["record_video_dir"] = str(E2EConfig.ARTIFACTS_DIR / "videos")

    return args


@pytest.fixture
def context(browser: Browser, browser_context_args: Dict) -> Generator[BrowserContext, None, None]:
    """Create a new browser context for each test."""
    context = browser.new_context(**browser_context_args)
    context.set_default_timeout(E2EConfig.DEFAULT_TIMEOUT)
    context.set_default_navigation_timeout(E2EConfig.NAVIGATION_TIMEOUT)

    yield context

    context.close()


@pytest.fixture
def page(context: BrowserContext, app_server) -> Generator[Page, None, None]:
    """Create a new page for each test."""
    page = context.new_page()

    yield page

    page.close()


# =============================================================================
# Authentication Fixtures
# =============================================================================


@pytest.fixture
def authenticated_page(page: Page) -> Page:
    """Return a page that's logged in to the dashboard."""
    page.goto(f"{E2EConfig.BASE_URL}/login")
    page.fill('input[name="username"]', E2EConfig.USERNAME)
    page.fill('input[name="password"]', E2EConfig.PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_url(f"{E2EConfig.BASE_URL}/")
    return page


@pytest.fixture
def auth_context(
    browser: Browser, browser_context_args: Dict, app_server
) -> Generator[BrowserContext, None, None]:
    """
    Create an authenticated browser context with saved state.

    This fixture logs in once and reuses the session for multiple pages.
    """
    context = browser.new_context(**browser_context_args)
    page = context.new_page()

    # Login
    page.goto(f"{E2EConfig.BASE_URL}/login")
    page.fill('input[name="username"]', E2EConfig.USERNAME)
    page.fill('input[name="password"]', E2EConfig.PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_url(f"{E2EConfig.BASE_URL}/")
    page.close()

    yield context

    context.close()


@pytest.fixture
def auth_page(auth_context: BrowserContext) -> Generator[Page, None, None]:
    """Create a new page in an authenticated context."""
    page = auth_context.new_page()
    page.goto(f"{E2EConfig.BASE_URL}/")
    yield page
    page.close()


# =============================================================================
# Utility Fixtures
# =============================================================================


@pytest.fixture
def api_client(authenticated_page: Page):
    """Provide API client from authenticated page context."""

    class APIClient:
        def __init__(self, page: Page):
            self.page = page
            self.base_url = E2EConfig.BASE_URL

        def get(self, endpoint: str):
            return self.page.request.get(f"{self.base_url}{endpoint}")

        def post(self, endpoint: str, data: dict = None):
            return self.page.request.post(
                f"{self.base_url}{endpoint}",
                data=json.dumps(data) if data else None,
                headers={"Content-Type": "application/json"},
            )

        def put(self, endpoint: str, data: dict = None):
            return self.page.request.put(
                f"{self.base_url}{endpoint}",
                data=json.dumps(data) if data else None,
                headers={"Content-Type": "application/json"},
            )

        def delete(self, endpoint: str):
            return self.page.request.delete(f"{self.base_url}{endpoint}")

    return APIClient(authenticated_page)


@pytest.fixture
def screenshot_on_failure(request, page: Page):
    """Capture screenshot on test failure."""
    yield

    if request.node.rep_call.failed and E2EConfig.SCREENSHOT_ON_FAILURE:
        E2EConfig.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_name = request.node.name.replace("/", "_").replace(":", "_")
        screenshot_path = E2EConfig.ARTIFACTS_DIR / f"failure_{test_name}_{timestamp}.png"
        page.screenshot(path=str(screenshot_path))
        print(f"\n[E2E] Screenshot saved: {screenshot_path}")


# =============================================================================
# Hooks
# =============================================================================


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Store test results for use in fixtures."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "smoke: marks tests as smoke tests")
    config.addinivalue_line("markers", "auth: marks tests requiring authentication")
    config.addinivalue_line("markers", "api: marks API tests")


def pytest_collection_modifyitems(config, items):
    """Add markers based on test location."""
    for item in items:
        # Add slow marker to performance tests
        if "performance" in item.nodeid.lower():
            item.add_marker(pytest.mark.slow)

        # Add auth marker to tests using authenticated fixtures
        if "authenticated" in str(item.fixturenames) or "auth_" in str(item.fixturenames):
            item.add_marker(pytest.mark.auth)
