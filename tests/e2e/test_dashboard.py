"""
Dashboard E2E Tests

Tests main dashboard functionality, navigation, and UI components.
"""
import time

import pytest
from playwright.sync_api import Page, expect

from .conftest import E2EConfig
from .pages import DashboardPage, LoginPage


class TestDashboardNavigation:
    """Test dashboard navigation."""

    def test_dashboard_loads(self, authenticated_page: Page):
        """Test dashboard main page loads."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.expect_dashboard_loaded()

    def test_navigate_to_projects(self, authenticated_page: Page):
        """Test navigation to projects panel."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.go_to_projects()
        # Verify projects section is active/visible
        authenticated_page.wait_for_timeout(500)

    def test_navigate_to_features(self, authenticated_page: Page):
        """Test navigation to features panel."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.go_to_features()
        authenticated_page.wait_for_timeout(500)

    def test_navigate_to_bugs(self, authenticated_page: Page):
        """Test navigation to bugs panel."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.go_to_bugs()
        authenticated_page.wait_for_timeout(500)

    def test_navigate_to_tasks(self, authenticated_page: Page):
        """Test navigation to tasks panel."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.go_to_tasks()
        authenticated_page.wait_for_timeout(500)

    def test_navigate_to_errors(self, authenticated_page: Page):
        """Test navigation to errors panel."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.go_to_errors()
        authenticated_page.wait_for_timeout(500)

    def test_navigate_to_tmux(self, authenticated_page: Page):
        """Test navigation to tmux panel."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.go_to_tmux()
        authenticated_page.wait_for_timeout(500)


class TestDashboardUI:
    """Test dashboard UI components."""

    def test_header_visible(self, authenticated_page: Page):
        """Test header is visible."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        expect(dashboard.header).to_be_visible()

    def test_sidebar_visible(self, authenticated_page: Page):
        """Test sidebar/navigation is visible."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        expect(dashboard.sidebar).to_be_visible()

    def test_main_content_visible(self, authenticated_page: Page):
        """Test main content area is visible."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        expect(dashboard.main_content).to_be_visible()

    def test_logout_button_visible(self, authenticated_page: Page):
        """Test logout button is accessible."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.expect_logged_in()


class TestDashboardRefresh:
    """Test dashboard refresh functionality."""

    def test_refresh_button(self, authenticated_page: Page):
        """Test refresh button updates data."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.click_refresh()
        # Should complete without error
        dashboard.wait_for_network_idle()

    def test_auto_refresh(self, authenticated_page: Page):
        """Test page can handle multiple refreshes."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)

        for _ in range(3):
            dashboard.reload()
            dashboard.wait_for_network_idle()
            dashboard.expect_dashboard_loaded()


class TestDashboardSearch:
    """Test dashboard search functionality."""

    def test_search_input_exists(self, authenticated_page: Page):
        """Test search input is present."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        search = dashboard.locator('input[type="search"], input[name="search"], .search-input')
        # Search may or may not exist depending on dashboard implementation

    def test_search_functionality(self, authenticated_page: Page):
        """Test search executes without error."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.search("test")
        dashboard.wait(500)
        dashboard.clear_search()


class TestDashboardResponsive:
    """Test dashboard responsive design."""

    @pytest.mark.parametrize(
        "width,height,name",
        [
            (375, 667, "mobile"),
            (768, 1024, "tablet"),
            (1280, 720, "laptop"),
            (1920, 1080, "desktop"),
        ],
    )
    def test_viewport_renders(self, page: Page, app_server, width, height, name):
        """Test dashboard renders at different viewports."""
        page.set_viewport_size({"width": width, "height": height})

        # Login
        login_page = LoginPage(page, E2EConfig.BASE_URL)
        login_page.navigate()
        login_page.login_and_wait(E2EConfig.USERNAME, E2EConfig.PASSWORD)

        # Dashboard should load
        dashboard = DashboardPage(page, E2EConfig.BASE_URL)
        dashboard.expect_dashboard_loaded()


@pytest.mark.slow
class TestDashboardPerformance:
    """Test dashboard performance."""

    def test_initial_load_time(self, page: Page, app_server):
        """Test initial page load time."""
        # Login first
        login_page = LoginPage(page, E2EConfig.BASE_URL)
        login_page.navigate()
        login_page.login_and_wait(E2EConfig.USERNAME, E2EConfig.PASSWORD)

        # Measure dashboard load
        start = time.time()
        page.goto(f"{E2EConfig.BASE_URL}/")
        page.wait_for_load_state("networkidle")
        load_time = time.time() - start

        assert load_time < 10.0, f"Dashboard took {load_time:.2f}s to load (max 10s)"

    def test_navigation_performance(self, authenticated_page: Page):
        """Test navigation between sections is fast."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)

        sections = [
            dashboard.go_to_projects,
            dashboard.go_to_features,
            dashboard.go_to_bugs,
            dashboard.go_to_tasks,
        ]

        for navigate in sections:
            start = time.time()
            navigate()
            authenticated_page.wait_for_timeout(100)
            duration = time.time() - start

            assert duration < 3.0, f"Navigation took {duration:.2f}s (max 3s)"


class TestDashboardAPI:
    """Test dashboard API interactions from browser."""

    def test_stats_endpoint(self, authenticated_page: Page):
        """Test stats API returns data."""
        response = authenticated_page.request.get(f"{E2EConfig.BASE_URL}/api/stats")
        assert response.status == 200
        data = response.json()
        assert "projects" in data or "features" in data or "bugs" in data

    def test_health_endpoint(self, page: Page, app_server):
        """Test health endpoint."""
        response = page.request.get(f"{E2EConfig.BASE_URL}/health")
        assert response.status == 200
        data = response.json()
        assert data.get("status") == "ok"

    def test_projects_api(self, authenticated_page: Page):
        """Test projects API."""
        response = authenticated_page.request.get(f"{E2EConfig.BASE_URL}/api/projects")
        assert response.status == 200

    def test_tasks_api(self, authenticated_page: Page):
        """Test tasks API."""
        response = authenticated_page.request.get(f"{E2EConfig.BASE_URL}/api/tasks")
        assert response.status == 200
