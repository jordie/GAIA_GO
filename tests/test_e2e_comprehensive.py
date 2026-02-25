#!/usr/bin/env python3
"""
Comprehensive End-to-End Tests

Tests complete user workflows from start to finish.

Created for: P07 - Create Testing Infrastructure

Requirements:
    pip install playwright pytest-playwright
    playwright install

Note: Tests will be skipped if Playwright is not installed.
"""

import importlib.util
import time

import pytest

# Test markers - mark as e2e for conditional skipping
pytestmark = pytest.mark.e2e

# Check if playwright is available
_playwright_available = importlib.util.find_spec("playwright.sync_api") is not None

if _playwright_available:
    from playwright.sync_api import Page, expect
else:
    # Playwright not available - conftest will skip these tests
    Page = None
    expect = None
    # Don't try to load plugin to avoid import errors during test collection


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context."""
    return {
        **browser_context_args,
        "ignore_https_errors": True,  # For self-signed certs
        "viewport": {"width": 1920, "height": 1080},
    }


class TestDashboardWorkflows:
    """Test dashboard UI workflows."""

    @pytest.fixture
    def base_url(self):
        """Base URL for tests."""
        return "https://localhost:5051"

    def test_dashboard_loads(self, page: Page, base_url):
        """Test dashboard page loads successfully."""
        page.goto(f"{base_url}/")

        # Wait for page to load
        page.wait_for_load_state("networkidle")

        # Verify title
        assert "Architect" in page.title()

    def test_navigation_between_panels(self, page: Page, base_url):
        """Test navigation between dashboard panels."""
        page.goto(f"{base_url}/")

        # Find navigation links
        nav_links = page.query_selector_all("nav a")

        # Should have multiple nav links
        assert len(nav_links) > 0

        # Test navigation to different panels
        panels = ["Overview", "Projects", "Tasks", "Errors"]

        for panel in panels:
            link = page.query_selector(f'a:has-text("{panel}")')
            if link:
                link.click()
                page.wait_for_timeout(500)  # Wait for panel to load

                # Verify panel is visible
                assert page.is_visible(f'[data-panel="{panel.lower()}"]') or page.is_visible(
                    f"#{panel.lower()}"
                )


class TestTaskWorkflows:
    """Test task management workflows."""

    @pytest.fixture
    def base_url(self):
        return "https://localhost:5051"

    def test_create_task_workflow(self, page: Page, base_url):
        """Test creating a new task."""
        page.goto(f"{base_url}/")

        # Navigate to tasks panel
        tasks_link = page.query_selector('a:has-text("Tasks")')
        if tasks_link:
            tasks_link.click()
            page.wait_for_timeout(500)

            # Look for "New Task" or "Add Task" button
            new_task_btn = page.query_selector(
                'button:has-text("New Task")'
            ) or page.query_selector('button:has-text("Add Task")')

            if new_task_btn:
                new_task_btn.click()
                page.wait_for_timeout(500)

                # Fill in task form
                title_input = page.query_selector('input[name="title"]') or page.query_selector(
                    'input[placeholder*="title"]'
                )

                if title_input:
                    title_input.fill("E2E Test Task")

                    # Submit form
                    submit_btn = page.query_selector(
                        'button[type="submit"]'
                    ) or page.query_selector('button:has-text("Create")')

                    if submit_btn:
                        submit_btn.click()
                        page.wait_for_timeout(1000)

                        # Verify task appears in list
                        assert page.is_visible('text="E2E Test Task"')


class TestAPIWorkflows:
    """Test API endpoint workflows."""

    @pytest.fixture
    def api_base_url(self):
        return "https://localhost:5051/api"

    def test_health_check_api(self, page: Page, api_base_url):
        """Test health check API endpoint."""
        response = page.goto(f"{api_base_url}/../health")

        assert response.status == 200

        # Parse JSON response
        content = page.content()
        assert "ok" in content.lower() or "healthy" in content.lower()


class TestPerformanceWorkflows:
    """Test performance characteristics."""

    @pytest.fixture
    def base_url(self):
        return "https://localhost:5051"

    def test_page_load_time(self, page: Page, base_url):
        """Test page load time is reasonable."""
        start_time = time.time()

        page.goto(f"{base_url}/")
        page.wait_for_load_state("networkidle")

        load_time = time.time() - start_time

        # Page should load in under 5 seconds
        assert load_time < 5.0

    def test_api_response_time(self, page: Page, base_url):
        """Test API response time."""
        start_time = time.time()

        response = page.goto(f"{base_url}/health")

        response_time = time.time() - start_time

        # API should respond in under 2 seconds
        assert response_time < 2.0
        assert response.status == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--headed", "--browser", "chromium"])
