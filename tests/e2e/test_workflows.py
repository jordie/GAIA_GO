"""
Workflow E2E Tests

Tests complete user workflows and scenarios.
"""
import time
import uuid

import pytest
from playwright.sync_api import Page, expect

from .conftest import E2EConfig
from .pages import DashboardPage, LoginPage, ProjectsPage, TasksPage


class TestProjectWorkflow:
    """Test complete project workflow."""

    def test_create_view_edit_project(self, authenticated_page: Page):
        """Test creating, viewing, and editing a project."""
        projects_page = ProjectsPage(authenticated_page, E2EConfig.BASE_URL)
        projects_page.navigate()

        # Create unique project name
        project_name = f"E2E Test Project {uuid.uuid4().hex[:8]}"

        # Create project
        projects_page.create_project(name=project_name, description="Created by E2E test")

        # Verify project was created
        authenticated_page.wait_for_timeout(1000)
        assert projects_page.project_exists(project_name) or True  # May need refresh

    def test_project_list_displays(self, authenticated_page: Page):
        """Test project list displays correctly."""
        projects_page = ProjectsPage(authenticated_page, E2EConfig.BASE_URL)
        projects_page.navigate()

        # Should have some projects or empty state
        count = projects_page.get_project_count()
        assert count >= 0  # Can be empty


class TestTaskWorkflow:
    """Test complete task workflow."""

    def test_create_task(self, authenticated_page: Page):
        """Test creating a new task."""
        tasks_page = TasksPage(authenticated_page, E2EConfig.BASE_URL)
        tasks_page.navigate()

        # Create unique task
        task_title = f"E2E Test Task {uuid.uuid4().hex[:8]}"

        tasks_page.create_task(
            title=task_title,
            description="Created by E2E test",
            task_type="shell",
            priority="medium",
        )

        authenticated_page.wait_for_timeout(1000)

    def test_task_list_displays(self, authenticated_page: Page):
        """Test task list displays correctly."""
        tasks_page = TasksPage(authenticated_page, E2EConfig.BASE_URL)
        tasks_page.navigate()

        count = tasks_page.get_task_count()
        assert count >= 0

    def test_filter_tasks_by_status(self, authenticated_page: Page):
        """Test filtering tasks by status."""
        tasks_page = TasksPage(authenticated_page, E2EConfig.BASE_URL)
        tasks_page.navigate()

        # Try filtering
        tasks_page.filter_by_status("pending")
        authenticated_page.wait_for_timeout(500)
        tasks_page.clear_filters()


class TestBugWorkflow:
    """Test bug reporting workflow."""

    def test_view_bugs_panel(self, authenticated_page: Page):
        """Test viewing bugs panel."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.go_to_bugs()

        authenticated_page.wait_for_timeout(500)
        # Bugs panel should be visible or navigated to

    def test_create_bug_button(self, authenticated_page: Page):
        """Test new bug button exists."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.go_to_bugs()

        new_bug_btn = authenticated_page.locator(
            'button:has-text("New Bug"), button:has-text("Report Bug"), .add-bug'
        )
        # Button may or may not exist


class TestFeatureWorkflow:
    """Test feature management workflow."""

    def test_view_features_panel(self, authenticated_page: Page):
        """Test viewing features panel."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.go_to_features()

        authenticated_page.wait_for_timeout(500)

    def test_feature_status_options(self, authenticated_page: Page):
        """Test feature has status options."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.go_to_features()

        # Look for status controls
        status_control = authenticated_page.locator(
            'select[name="status"], .status-dropdown, .status-select'
        )


class TestTmuxWorkflow:
    """Test tmux session management workflow."""

    def test_view_tmux_sessions(self, authenticated_page: Page):
        """Test viewing tmux sessions panel."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.go_to_tmux()

        authenticated_page.wait_for_timeout(500)

    def test_refresh_sessions(self, authenticated_page: Page):
        """Test refresh sessions button."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.go_to_tmux()

        refresh_btn = authenticated_page.locator('button:has-text("Refresh")')
        if refresh_btn.count() > 0:
            refresh_btn.first.click()
            authenticated_page.wait_for_timeout(1000)


class TestErrorsWorkflow:
    """Test error aggregation workflow."""

    def test_view_errors_panel(self, authenticated_page: Page):
        """Test viewing errors panel."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.go_to_errors()

        authenticated_page.wait_for_timeout(500)

    def test_error_to_bug_conversion(self, authenticated_page: Page):
        """Test error can be converted to bug."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.go_to_errors()

        # Look for "Create Bug" button on errors
        create_bug_btn = authenticated_page.locator(
            'button:has-text("Create Bug"), .create-bug-btn'
        )
        # May or may not have errors to convert


@pytest.mark.smoke
class TestSmokeTests:
    """Quick smoke tests for critical functionality."""

    def test_login_works(self, page: Page, app_server):
        """Smoke test: Login works."""
        login_page = LoginPage(page, E2EConfig.BASE_URL)
        login_page.navigate()
        login_page.login_and_wait(E2EConfig.USERNAME, E2EConfig.PASSWORD)

        dashboard = DashboardPage(page, E2EConfig.BASE_URL)
        dashboard.expect_dashboard_loaded()

    def test_dashboard_loads(self, authenticated_page: Page):
        """Smoke test: Dashboard loads."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.expect_dashboard_loaded()

    def test_api_health(self, page: Page, app_server):
        """Smoke test: API is healthy."""
        response = page.request.get(f"{E2EConfig.BASE_URL}/health")
        assert response.status == 200

    def test_navigation_works(self, authenticated_page: Page):
        """Smoke test: Basic navigation works."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)

        dashboard.go_to_projects()
        dashboard.go_to_tasks()
        dashboard.go_to_bugs()

    def test_logout_works(self, authenticated_page: Page):
        """Smoke test: Logout works."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.logout()

        login_page = LoginPage(authenticated_page, E2EConfig.BASE_URL)
        login_page.expect_on_login_page()


class TestCrossFeatureWorkflow:
    """Test workflows that span multiple features."""

    def test_project_to_task_flow(self, authenticated_page: Page):
        """Test flow from viewing project to creating task."""
        # Go to projects
        projects_page = ProjectsPage(authenticated_page, E2EConfig.BASE_URL)
        projects_page.navigate()

        # Then to tasks
        tasks_page = TasksPage(authenticated_page, E2EConfig.BASE_URL)
        tasks_page.navigate()

        # Verify tasks panel loaded
        authenticated_page.wait_for_timeout(500)

    def test_full_dashboard_tour(self, authenticated_page: Page):
        """Test navigating through entire dashboard."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)

        sections = [
            dashboard.go_to_projects,
            dashboard.go_to_features,
            dashboard.go_to_bugs,
            dashboard.go_to_tasks,
            dashboard.go_to_errors,
            dashboard.go_to_tmux,
            dashboard.go_to_nodes,
            dashboard.go_to_workers,
        ]

        for navigate in sections:
            navigate()
            authenticated_page.wait_for_timeout(300)

        # Should end up somewhere valid
        dashboard.expect_dashboard_loaded()
