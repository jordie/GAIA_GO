"""
Base Page Object

Provides common functionality for all page objects.
"""
import re
from typing import Optional

from playwright.sync_api import Locator, Page, expect


class BasePage:
    """Base class for all page objects."""

    def __init__(self, page: Page, base_url: str = "http://localhost:8099"):
        self.page = page
        self.base_url = base_url

    # =========================================================================
    # Navigation
    # =========================================================================

    def goto(self, path: str = "") -> None:
        """Navigate to a path relative to base URL."""
        url = f"{self.base_url}{path}"
        self.page.goto(url)

    def reload(self) -> None:
        """Reload the current page."""
        self.page.reload()

    def go_back(self) -> None:
        """Go back in browser history."""
        self.page.go_back()

    def current_url(self) -> str:
        """Get current page URL."""
        return self.page.url

    def wait_for_url(self, url_pattern: str, timeout: int = None) -> None:
        """Wait for URL to match pattern."""
        self.page.wait_for_url(url_pattern, timeout=timeout)

    # =========================================================================
    # Element Interaction
    # =========================================================================

    def click(self, selector: str, timeout: int = None) -> None:
        """Click an element."""
        self.page.click(selector, timeout=timeout)

    def fill(self, selector: str, value: str) -> None:
        """Fill an input field."""
        self.page.fill(selector, value)

    def type(self, selector: str, value: str, delay: int = 50) -> None:
        """Type text character by character."""
        self.page.type(selector, value, delay=delay)

    def select(self, selector: str, value: str) -> None:
        """Select an option from a dropdown."""
        self.page.select_option(selector, value)

    def check(self, selector: str) -> None:
        """Check a checkbox."""
        self.page.check(selector)

    def uncheck(self, selector: str) -> None:
        """Uncheck a checkbox."""
        self.page.uncheck(selector)

    def hover(self, selector: str) -> None:
        """Hover over an element."""
        self.page.hover(selector)

    def focus(self, selector: str) -> None:
        """Focus an element."""
        self.page.focus(selector)

    def clear(self, selector: str) -> None:
        """Clear an input field."""
        self.fill(selector, "")

    # =========================================================================
    # Element State
    # =========================================================================

    def is_visible(self, selector: str) -> bool:
        """Check if element is visible."""
        return self.page.is_visible(selector)

    def is_enabled(self, selector: str) -> bool:
        """Check if element is enabled."""
        return self.page.is_enabled(selector)

    def is_checked(self, selector: str) -> bool:
        """Check if checkbox is checked."""
        return self.page.is_checked(selector)

    def get_text(self, selector: str) -> str:
        """Get element text content."""
        return self.page.text_content(selector) or ""

    def get_value(self, selector: str) -> str:
        """Get input value."""
        return self.page.input_value(selector)

    def get_attribute(self, selector: str, attribute: str) -> Optional[str]:
        """Get element attribute."""
        return self.page.get_attribute(selector, attribute)

    def count(self, selector: str) -> int:
        """Count matching elements."""
        return self.page.locator(selector).count()

    # =========================================================================
    # Locators
    # =========================================================================

    def locator(self, selector: str) -> Locator:
        """Get a locator for the selector."""
        return self.page.locator(selector)

    def get_by_role(self, role: str, **kwargs) -> Locator:
        """Get element by ARIA role."""
        return self.page.get_by_role(role, **kwargs)

    def get_by_text(self, text: str, exact: bool = False) -> Locator:
        """Get element by text content."""
        return self.page.get_by_text(text, exact=exact)

    def get_by_label(self, text: str) -> Locator:
        """Get form element by label text."""
        return self.page.get_by_label(text)

    def get_by_placeholder(self, text: str) -> Locator:
        """Get input by placeholder text."""
        return self.page.get_by_placeholder(text)

    def get_by_test_id(self, test_id: str) -> Locator:
        """Get element by data-testid attribute."""
        return self.page.get_by_test_id(test_id)

    # =========================================================================
    # Waiting
    # =========================================================================

    def wait_for_selector(
        self, selector: str, state: str = "visible", timeout: int = None
    ) -> Locator:
        """Wait for element to reach state."""
        return self.page.wait_for_selector(selector, state=state, timeout=timeout)

    def wait_for_load_state(self, state: str = "load") -> None:
        """Wait for page load state."""
        self.page.wait_for_load_state(state)

    def wait_for_network_idle(self) -> None:
        """Wait for network to be idle."""
        self.page.wait_for_load_state("networkidle")

    def wait(self, milliseconds: int) -> None:
        """Wait for specified time (use sparingly)."""
        self.page.wait_for_timeout(milliseconds)

    # =========================================================================
    # Assertions
    # =========================================================================

    def expect_visible(self, selector: str) -> None:
        """Assert element is visible."""
        expect(self.locator(selector)).to_be_visible()

    def expect_hidden(self, selector: str) -> None:
        """Assert element is hidden."""
        expect(self.locator(selector)).to_be_hidden()

    def expect_text(self, selector: str, text: str) -> None:
        """Assert element contains text."""
        expect(self.locator(selector)).to_contain_text(text)

    def expect_value(self, selector: str, value: str) -> None:
        """Assert input has value."""
        expect(self.locator(selector)).to_have_value(value)

    def expect_url(self, pattern: str) -> None:
        """Assert URL matches pattern."""
        expect(self.page).to_have_url(re.compile(pattern))

    def expect_title(self, title: str) -> None:
        """Assert page title."""
        expect(self.page).to_have_title(title)

    # =========================================================================
    # Screenshots and Debugging
    # =========================================================================

    def screenshot(self, path: str = None, full_page: bool = False) -> bytes:
        """Take a screenshot."""
        return self.page.screenshot(path=path, full_page=full_page)

    def console_logs(self) -> list:
        """Get console logs (must be collected during test)."""
        return getattr(self, "_console_logs", [])

    def start_console_collection(self) -> None:
        """Start collecting console logs."""
        self._console_logs = []
        self.page.on(
            "console",
            lambda msg: self._console_logs.append(
                {
                    "type": msg.type,
                    "text": msg.text,
                }
            ),
        )

    # =========================================================================
    # Common UI Elements
    # =========================================================================

    @property
    def header(self) -> Locator:
        """Page header element."""
        return self.locator("header, .header, #header")

    @property
    def footer(self) -> Locator:
        """Page footer element."""
        return self.locator("footer, .footer, #footer")

    @property
    def sidebar(self) -> Locator:
        """Sidebar element."""
        return self.locator(".sidebar, #sidebar, nav")

    @property
    def main_content(self) -> Locator:
        """Main content area."""
        return self.locator("main, .main-content, #main")

    def get_toast(self) -> Locator:
        """Get toast/notification element."""
        return self.locator(".toast, .notification, .alert, .flash-message")

    def get_modal(self) -> Locator:
        """Get modal dialog element."""
        return self.locator(".modal, [role='dialog'], .dialog")

    def close_modal(self) -> None:
        """Close any open modal."""
        close_btn = self.locator(".modal .close, .modal-close, [aria-label='Close']")
        if close_btn.count() > 0:
            close_btn.first.click()

    def get_loading_indicator(self) -> Locator:
        """Get loading indicator element."""
        return self.locator(".loading, .spinner, [aria-busy='true']")

    def wait_for_loading_complete(self, timeout: int = 10000) -> None:
        """Wait for loading indicators to disappear."""
        loading = self.get_loading_indicator()
        if loading.count() > 0:
            expect(loading.first).to_be_hidden(timeout=timeout)
