"""
End-to-End Browser Tests using Playwright

Tests the Architect Dashboard with real browser automation.
Run with: pytest tests/test_e2e_playwright.py --browser chromium
"""
import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

# Skip if playwright not installed
pytest.importorskip("playwright")

from playwright.sync_api import Page, expect

# Test configuration
TEST_PORT = 8099
TEST_URL = f"http://localhost:{TEST_PORT}"
TEST_USER = "architect"
TEST_PASS = "peace5"


@pytest.fixture(scope="module")
def server():
    """Start a test server for e2e tests."""
    env = os.environ.copy()
    env["PORT"] = str(TEST_PORT)
    env["ARCHITECT_USER"] = TEST_USER
    env["ARCHITECT_PASSWORD"] = TEST_PASS
    env["APP_ENV"] = "test"

    # Start server in background
    app_path = Path(__file__).parent.parent / "app.py"
    proc = subprocess.Popen(
        ["python3", str(app_path)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    # Wait for server to start
    for _ in range(30):
        try:
            import requests

            resp = requests.get(f"{TEST_URL}/health", timeout=1)
            if resp.status_code == 200:
                break
        except:
            pass
        time.sleep(0.5)
    else:
        proc.kill()
        raise RuntimeError("Server failed to start")

    yield proc

    # Cleanup
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=5)


@pytest.fixture
def authenticated_page(page: Page, server):
    """Return a page that's logged in."""
    page.goto(f"{TEST_URL}/login")
    page.fill('input[name="username"]', TEST_USER)
    page.fill('input[name="password"]', TEST_PASS)
    page.click('button[type="submit"]')
    page.wait_for_url(f"{TEST_URL}/")
    return page


class TestLoginFlow:
    """Test authentication flows."""

    def test_login_page_loads(self, page: Page, server):
        """Test that login page renders correctly."""
        page.goto(f"{TEST_URL}/login")
        expect(page).to_have_title("Login - Architect Dashboard")
        expect(page.locator('input[name="username"]')).to_be_visible()
        expect(page.locator('input[name="password"]')).to_be_visible()

    def test_successful_login(self, page: Page, server):
        """Test successful login redirects to dashboard."""
        page.goto(f"{TEST_URL}/login")
        page.fill('input[name="username"]', TEST_USER)
        page.fill('input[name="password"]', TEST_PASS)
        page.click('button[type="submit"]')

        # Should redirect to dashboard
        page.wait_for_url(f"{TEST_URL}/")
        expect(page.locator("body")).to_contain_text("Dashboard")

    def test_invalid_login(self, page: Page, server):
        """Test invalid credentials show error."""
        page.goto(f"{TEST_URL}/login")
        page.fill('input[name="username"]', "wrong")
        page.fill('input[name="password"]', "wrong")
        page.click('button[type="submit"]')

        # Should stay on login page with error
        expect(page.locator("body")).to_contain_text("Invalid")

    def test_logout(self, authenticated_page: Page):
        """Test logout functionality."""
        page = authenticated_page

        # Find and click logout
        page.click('a:has-text("Logout")')

        # Should redirect to login
        page.wait_for_url(f"{TEST_URL}/login")


class TestDashboardNavigation:
    """Test dashboard navigation and panels."""

    def test_dashboard_loads(self, authenticated_page: Page):
        """Test dashboard main page loads."""
        page = authenticated_page
        expect(page.locator("body")).to_contain_text("Dashboard")

    def test_projects_panel(self, authenticated_page: Page):
        """Test projects panel is accessible."""
        page = authenticated_page

        # Click projects tab/link if exists
        projects_link = page.locator('a:has-text("Projects"), button:has-text("Projects")')
        if projects_link.count() > 0:
            projects_link.first.click()
            page.wait_for_timeout(500)

    def test_features_panel(self, authenticated_page: Page):
        """Test features panel is accessible."""
        page = authenticated_page

        features_link = page.locator('a:has-text("Features"), button:has-text("Features")')
        if features_link.count() > 0:
            features_link.first.click()
            page.wait_for_timeout(500)

    def test_bugs_panel(self, authenticated_page: Page):
        """Test bugs panel is accessible."""
        page = authenticated_page

        bugs_link = page.locator('a:has-text("Bugs"), button:has-text("Bugs")')
        if bugs_link.count() > 0:
            bugs_link.first.click()
            page.wait_for_timeout(500)

    def test_tmux_panel(self, authenticated_page: Page):
        """Test tmux sessions panel is accessible."""
        page = authenticated_page

        tmux_link = page.locator('a:has-text("tmux"), button:has-text("tmux")')
        if tmux_link.count() > 0:
            tmux_link.first.click()
            page.wait_for_timeout(500)


class TestProjectWorkflow:
    """Test project CRUD operations in browser."""

    def test_create_project(self, authenticated_page: Page):
        """Test creating a new project via UI."""
        page = authenticated_page

        # Look for new project button
        new_btn = page.locator('button:has-text("New Project"), a:has-text("New Project")')
        if new_btn.count() > 0:
            new_btn.first.click()
            page.wait_for_timeout(500)

            # Fill form if modal appears
            name_input = page.locator('input[name="name"], input[placeholder*="name"]')
            if name_input.count() > 0:
                name_input.fill(f"E2E Test Project {int(time.time())}")

                # Submit
                submit = page.locator('button[type="submit"], button:has-text("Create")')
                if submit.count() > 0:
                    submit.first.click()
                    page.wait_for_timeout(1000)


class TestFeatureWorkflow:
    """Test feature management in browser."""

    def test_view_features(self, authenticated_page: Page):
        """Test viewing features list."""
        page = authenticated_page

        # Navigate to features
        page.goto(f"{TEST_URL}/#features")
        page.wait_for_timeout(500)

    def test_feature_status_change(self, authenticated_page: Page):
        """Test changing feature status."""
        page = authenticated_page

        # Look for a status dropdown or button
        status_btn = page.locator('.status-dropdown, select[name="status"]')
        if status_btn.count() > 0:
            status_btn.first.click()


class TestErrorsPanel:
    """Test error aggregation panel."""

    def test_errors_display(self, authenticated_page: Page):
        """Test errors panel displays."""
        page = authenticated_page

        # Navigate to errors section
        errors_link = page.locator('a:has-text("Errors"), button:has-text("Errors")')
        if errors_link.count() > 0:
            errors_link.first.click()
            page.wait_for_timeout(500)


class TestTmuxIntegration:
    """Test tmux session management."""

    def test_tmux_sessions_list(self, authenticated_page: Page):
        """Test tmux sessions list displays."""
        page = authenticated_page

        # Navigate to tmux section
        tmux_link = page.locator('a:has-text("tmux"), button:has-text("Sessions")')
        if tmux_link.count() > 0:
            tmux_link.first.click()
            page.wait_for_timeout(500)

    def test_refresh_sessions(self, authenticated_page: Page):
        """Test refresh sessions button."""
        page = authenticated_page

        refresh_btn = page.locator('button:has-text("Refresh")')
        if refresh_btn.count() > 0:
            refresh_btn.first.click()
            page.wait_for_timeout(1000)


class TestResponsiveDesign:
    """Test responsive design at different viewports."""

    def test_mobile_viewport(self, page: Page, server):
        """Test dashboard on mobile viewport."""
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(f"{TEST_URL}/login")

        # Login should still work
        page.fill('input[name="username"]', TEST_USER)
        page.fill('input[name="password"]', TEST_PASS)
        page.click('button[type="submit"]')
        page.wait_for_url(f"{TEST_URL}/")

    def test_tablet_viewport(self, page: Page, server):
        """Test dashboard on tablet viewport."""
        page.set_viewport_size({"width": 768, "height": 1024})
        page.goto(f"{TEST_URL}/login")

        page.fill('input[name="username"]', TEST_USER)
        page.fill('input[name="password"]', TEST_PASS)
        page.click('button[type="submit"]')
        page.wait_for_url(f"{TEST_URL}/")

    def test_desktop_viewport(self, page: Page, server):
        """Test dashboard on desktop viewport."""
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.goto(f"{TEST_URL}/login")

        page.fill('input[name="username"]', TEST_USER)
        page.fill('input[name="password"]', TEST_PASS)
        page.click('button[type="submit"]')
        page.wait_for_url(f"{TEST_URL}/")


class TestAPIFromBrowser:
    """Test API calls from browser context."""

    def test_health_endpoint(self, page: Page, server):
        """Test health endpoint from browser."""
        response = page.request.get(f"{TEST_URL}/health")
        assert response.status == 200
        data = response.json()
        assert data.get("status") == "ok"

    def test_stats_endpoint(self, authenticated_page: Page):
        """Test stats endpoint from authenticated context."""
        page = authenticated_page

        # Make API call from page context
        response = page.request.get(f"{TEST_URL}/api/stats")
        assert response.status == 200


class TestAccessibility:
    """Basic accessibility tests."""

    def test_form_labels(self, page: Page, server):
        """Test that form inputs have labels."""
        page.goto(f"{TEST_URL}/login")

        # Check username input has associated label
        username_label = page.locator('label[for="username"], label:has-text("Username")')
        assert (
            username_label.count() > 0
            or page.locator('input[name="username"][placeholder]').count() > 0
        )

    def test_keyboard_navigation(self, page: Page, server):
        """Test basic keyboard navigation."""
        page.goto(f"{TEST_URL}/login")

        # Tab through form fields
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")

        # Should be able to navigate


class TestPerformance:
    """Basic performance tests."""

    def test_page_load_time(self, page: Page, server):
        """Test that pages load within acceptable time."""
        start = time.time()
        page.goto(f"{TEST_URL}/login")
        load_time = time.time() - start

        # Page should load within 5 seconds
        assert load_time < 5.0

    def test_dashboard_load_time(self, authenticated_page: Page):
        """Test dashboard loads quickly."""
        page = authenticated_page

        start = time.time()
        page.goto(f"{TEST_URL}/")
        page.wait_for_load_state("networkidle")
        load_time = time.time() - start

        # Dashboard should load within 10 seconds
        assert load_time < 10.0
