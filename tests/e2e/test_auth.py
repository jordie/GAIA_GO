"""
Authentication E2E Tests

Tests login, logout, and session management.
"""
import pytest
from playwright.sync_api import Page, expect

from .conftest import E2EConfig
from .pages import DashboardPage, LoginPage


class TestLogin:
    """Test login functionality."""

    def test_login_page_renders(self, page: Page, app_server):
        """Test login page displays correctly."""
        login_page = LoginPage(page, E2EConfig.BASE_URL)
        login_page.navigate()

        login_page.expect_login_form_visible()
        login_page.expect_on_login_page()

    def test_login_page_title(self, page: Page, app_server):
        """Test login page has correct title."""
        page.goto(f"{E2EConfig.BASE_URL}/login")
        expect(page).to_have_title("Login - Architect Dashboard")

    def test_successful_login(self, page: Page, app_server):
        """Test successful login with valid credentials."""
        login_page = LoginPage(page, E2EConfig.BASE_URL)
        login_page.navigate()
        login_page.login_and_wait(E2EConfig.USERNAME, E2EConfig.PASSWORD)

        # Should be on dashboard
        dashboard = DashboardPage(page, E2EConfig.BASE_URL)
        dashboard.expect_dashboard_loaded()

    def test_invalid_username(self, page: Page, app_server):
        """Test login with invalid username."""
        login_page = LoginPage(page, E2EConfig.BASE_URL)
        login_page.navigate()
        login_page.login("invalid_user", E2EConfig.PASSWORD)

        # Should stay on login page with error
        login_page.expect_on_login_page()
        assert "invalid" in login_page.get_error_message().lower() or login_page.is_login_page()

    def test_invalid_password(self, page: Page, app_server):
        """Test login with invalid password."""
        login_page = LoginPage(page, E2EConfig.BASE_URL)
        login_page.navigate()
        login_page.login(E2EConfig.USERNAME, "wrong_password")

        # Should stay on login page
        login_page.expect_on_login_page()

    def test_empty_credentials(self, page: Page, app_server):
        """Test login with empty credentials."""
        login_page = LoginPage(page, E2EConfig.BASE_URL)
        login_page.navigate()
        login_page.click_submit()

        # Should stay on login page
        login_page.expect_on_login_page()

    def test_case_insensitive_username(self, page: Page, app_server):
        """Test username is case-insensitive."""
        login_page = LoginPage(page, E2EConfig.BASE_URL)
        login_page.navigate()

        # Try uppercase username
        login_page.login_and_wait(E2EConfig.USERNAME.upper(), E2EConfig.PASSWORD)

        dashboard = DashboardPage(page, E2EConfig.BASE_URL)
        dashboard.expect_dashboard_loaded()


class TestLogout:
    """Test logout functionality."""

    def test_logout(self, authenticated_page: Page):
        """Test logout redirects to login."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.logout()

        login_page = LoginPage(authenticated_page, E2EConfig.BASE_URL)
        login_page.expect_on_login_page()

    def test_logout_clears_session(self, authenticated_page: Page, page: Page, app_server):
        """Test logout clears session (new page requires login)."""
        dashboard = DashboardPage(authenticated_page, E2EConfig.BASE_URL)
        dashboard.logout()

        # New page should redirect to login
        page.goto(f"{E2EConfig.BASE_URL}/")
        login_page = LoginPage(page, E2EConfig.BASE_URL)
        login_page.expect_on_login_page()


class TestSessionManagement:
    """Test session handling."""

    def test_unauthenticated_redirect(self, page: Page, app_server):
        """Test unauthenticated access redirects to login."""
        page.goto(f"{E2EConfig.BASE_URL}/")

        login_page = LoginPage(page, E2EConfig.BASE_URL)
        login_page.expect_on_login_page()

    def test_session_persists_on_navigation(self, authenticated_page: Page):
        """Test session persists across page navigation."""
        page = authenticated_page

        # Navigate to different sections
        page.goto(f"{E2EConfig.BASE_URL}/#projects")
        page.goto(f"{E2EConfig.BASE_URL}/#tasks")
        page.goto(f"{E2EConfig.BASE_URL}/")

        # Should still be logged in
        dashboard = DashboardPage(page, E2EConfig.BASE_URL)
        dashboard.expect_logged_in()

    def test_session_persists_on_reload(self, authenticated_page: Page):
        """Test session persists after page reload."""
        page = authenticated_page

        page.reload()
        page.wait_for_load_state("networkidle")

        dashboard = DashboardPage(page, E2EConfig.BASE_URL)
        dashboard.expect_logged_in()


class TestLoginAccessibility:
    """Test login page accessibility."""

    def test_keyboard_navigation(self, page: Page, app_server):
        """Test login form is keyboard navigable."""
        login_page = LoginPage(page, E2EConfig.BASE_URL)
        login_page.navigate()

        # Tab through form
        page.keyboard.press("Tab")  # Focus username
        page.keyboard.type(E2EConfig.USERNAME)

        page.keyboard.press("Tab")  # Focus password
        page.keyboard.type(E2EConfig.PASSWORD)

        page.keyboard.press("Tab")  # Focus submit
        page.keyboard.press("Enter")

        # Should login successfully
        page.wait_for_url(f"{E2EConfig.BASE_URL}/")

    def test_form_has_labels(self, page: Page, app_server):
        """Test form inputs have accessible labels."""
        page.goto(f"{E2EConfig.BASE_URL}/login")

        # Check for labels or placeholders
        username_input = page.locator('input[name="username"]')
        password_input = page.locator('input[name="password"]')

        # Should have label, placeholder, or aria-label
        assert (
            page.locator('label[for="username"]').count() > 0
            or username_input.get_attribute("placeholder")
            or username_input.get_attribute("aria-label")
        )

        assert (
            page.locator('label[for="password"]').count() > 0
            or password_input.get_attribute("placeholder")
            or password_input.get_attribute("aria-label")
        )
