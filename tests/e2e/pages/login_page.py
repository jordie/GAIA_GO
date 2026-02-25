"""
Login Page Object

Encapsulates login page interactions.
"""
from playwright.sync_api import Page, expect

from .base_page import BasePage


class LoginPage(BasePage):
    """Page object for the login page."""

    # Selectors
    USERNAME_INPUT = 'input[name="username"]'
    PASSWORD_INPUT = 'input[name="password"]'
    SUBMIT_BUTTON = 'button[type="submit"]'
    ERROR_MESSAGE = ".error, .alert-danger, .flash-error"
    REMEMBER_ME = 'input[name="remember"], input[type="checkbox"]'

    def __init__(self, page: Page, base_url: str = "http://localhost:8099"):
        super().__init__(page, base_url)
        self.url = f"{base_url}/login"

    def navigate(self) -> "LoginPage":
        """Navigate to login page."""
        self.goto("/login")
        return self

    def enter_username(self, username: str) -> "LoginPage":
        """Enter username."""
        self.fill(self.USERNAME_INPUT, username)
        return self

    def enter_password(self, password: str) -> "LoginPage":
        """Enter password."""
        self.fill(self.PASSWORD_INPUT, password)
        return self

    def click_submit(self) -> None:
        """Click the login button."""
        self.click(self.SUBMIT_BUTTON)

    def login(self, username: str, password: str) -> None:
        """Complete login flow."""
        self.enter_username(username)
        self.enter_password(password)
        self.click_submit()

    def login_and_wait(self, username: str, password: str, expected_url: str = None) -> None:
        """Login and wait for redirect."""
        self.login(username, password)
        if expected_url:
            self.wait_for_url(expected_url)
        else:
            self.wait_for_url(f"{self.base_url}/")

    def get_error_message(self) -> str:
        """Get login error message if present."""
        if self.is_visible(self.ERROR_MESSAGE):
            return self.get_text(self.ERROR_MESSAGE)
        return ""

    def is_login_page(self) -> bool:
        """Check if currently on login page."""
        return "/login" in self.current_url()

    def check_remember_me(self) -> "LoginPage":
        """Check the remember me checkbox."""
        if self.count(self.REMEMBER_ME) > 0:
            self.check(self.REMEMBER_ME)
        return self

    # Assertions
    def expect_login_form_visible(self) -> None:
        """Assert login form is visible."""
        self.expect_visible(self.USERNAME_INPUT)
        self.expect_visible(self.PASSWORD_INPUT)
        self.expect_visible(self.SUBMIT_BUTTON)

    def expect_error_visible(self) -> None:
        """Assert error message is visible."""
        self.expect_visible(self.ERROR_MESSAGE)

    def expect_error_contains(self, text: str) -> None:
        """Assert error message contains text."""
        self.expect_text(self.ERROR_MESSAGE, text)

    def expect_on_login_page(self) -> None:
        """Assert currently on login page."""
        self.expect_url(r".*/login")
