"""
Dashboard Page Object

Encapsulates main dashboard interactions.
"""
from typing import Any, Dict, List

from playwright.sync_api import Locator, Page, expect

from .base_page import BasePage


class DashboardPage(BasePage):
    """Page object for the main dashboard."""

    # Navigation selectors
    NAV_PROJECTS = 'a:has-text("Projects"), button:has-text("Projects")'
    NAV_FEATURES = 'a:has-text("Features"), button:has-text("Features")'
    NAV_BUGS = 'a:has-text("Bugs"), button:has-text("Bugs")'
    NAV_TASKS = 'a:has-text("Tasks"), button:has-text("Tasks")'
    NAV_ERRORS = 'a:has-text("Errors"), button:has-text("Errors")'
    NAV_TMUX = 'a:has-text("tmux"), button:has-text("Sessions")'
    NAV_NODES = 'a:has-text("Nodes"), button:has-text("Nodes")'
    NAV_WORKERS = 'a:has-text("Workers"), button:has-text("Workers")'

    # Panel selectors
    PANEL = ".panel, .card, section"
    PANEL_HEADER = ".panel-header, .card-header, h2, h3"

    # User menu
    USER_MENU = ".user-menu, .dropdown-user, #user-dropdown"
    LOGOUT_LINK = 'a:has-text("Logout"), button:has-text("Logout")'

    # Stats
    STATS_CONTAINER = ".stats, .dashboard-stats, .metrics"

    def __init__(self, page: Page, base_url: str = "http://localhost:8099"):
        super().__init__(page, base_url)
        self.url = base_url

    def navigate(self) -> "DashboardPage":
        """Navigate to dashboard."""
        self.goto("/")
        return self

    # =========================================================================
    # Navigation
    # =========================================================================

    def go_to_projects(self) -> None:
        """Navigate to projects panel."""
        self._safe_click(self.NAV_PROJECTS)

    def go_to_features(self) -> None:
        """Navigate to features panel."""
        self._safe_click(self.NAV_FEATURES)

    def go_to_bugs(self) -> None:
        """Navigate to bugs panel."""
        self._safe_click(self.NAV_BUGS)

    def go_to_tasks(self) -> None:
        """Navigate to tasks panel."""
        self._safe_click(self.NAV_TASKS)

    def go_to_errors(self) -> None:
        """Navigate to errors panel."""
        self._safe_click(self.NAV_ERRORS)

    def go_to_tmux(self) -> None:
        """Navigate to tmux sessions panel."""
        self._safe_click(self.NAV_TMUX)

    def go_to_nodes(self) -> None:
        """Navigate to nodes panel."""
        self._safe_click(self.NAV_NODES)

    def go_to_workers(self) -> None:
        """Navigate to workers panel."""
        self._safe_click(self.NAV_WORKERS)

    def _safe_click(self, selector: str) -> bool:
        """Click if element exists, return success."""
        locator = self.locator(selector)
        if locator.count() > 0:
            locator.first.click()
            self.wait(500)
            return True
        return False

    # =========================================================================
    # User Actions
    # =========================================================================

    def logout(self) -> None:
        """Logout from dashboard."""
        # Try clicking user menu first if it exists
        if self.count(self.USER_MENU) > 0:
            self.click(self.USER_MENU)
            self.wait(200)

        self.click(self.LOGOUT_LINK)
        self.wait_for_url(f"{self.base_url}/login")

    def get_username(self) -> str:
        """Get displayed username."""
        user_elem = self.locator(".username, .user-name, #current-user")
        if user_elem.count() > 0:
            return user_elem.first.text_content() or ""
        return ""

    # =========================================================================
    # Panels
    # =========================================================================

    def get_panels(self) -> List[Locator]:
        """Get all visible panels."""
        return [self.locator(self.PANEL).nth(i) for i in range(self.count(self.PANEL))]

    def get_panel_by_title(self, title: str) -> Locator:
        """Get panel by its title."""
        return self.locator(f"{self.PANEL}:has({self.PANEL_HEADER}:has-text('{title}'))")

    def is_panel_visible(self, title: str) -> bool:
        """Check if panel with title is visible."""
        panel = self.get_panel_by_title(title)
        return panel.count() > 0 and panel.is_visible()

    # =========================================================================
    # Stats
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get dashboard statistics."""
        stats = {}
        stat_elements = self.locator(f"{self.STATS_CONTAINER} .stat, .stat-item, .metric")

        for i in range(stat_elements.count()):
            elem = stat_elements.nth(i)
            label = elem.locator(".stat-label, .label, dt").text_content()
            value = elem.locator(".stat-value, .value, dd").text_content()
            if label:
                stats[label.strip()] = value.strip() if value else ""

        return stats

    def get_project_count(self) -> int:
        """Get number of projects from stats."""
        stats = self.get_stats()
        for key in ["Projects", "projects", "Total Projects"]:
            if key in stats:
                try:
                    return int(stats[key])
                except ValueError:
                    pass
        return 0

    # =========================================================================
    # Quick Actions
    # =========================================================================

    def click_new_project(self) -> None:
        """Click new project button."""
        self._safe_click('button:has-text("New Project"), a:has-text("New Project")')

    def click_new_feature(self) -> None:
        """Click new feature button."""
        self._safe_click('button:has-text("New Feature"), a:has-text("New Feature")')

    def click_new_bug(self) -> None:
        """Click new bug button."""
        self._safe_click('button:has-text("New Bug"), a:has-text("Report Bug")')

    def click_new_task(self) -> None:
        """Click new task button."""
        self._safe_click('button:has-text("New Task"), a:has-text("New Task")')

    def click_refresh(self) -> None:
        """Click refresh button."""
        self._safe_click('button:has-text("Refresh"), button[title="Refresh"]')
        self.wait_for_network_idle()

    # =========================================================================
    # Search
    # =========================================================================

    def search(self, query: str) -> None:
        """Perform a search."""
        search_input = self.locator('input[type="search"], input[name="search"], .search-input')
        if search_input.count() > 0:
            search_input.first.fill(query)
            self.page.keyboard.press("Enter")
            self.wait(500)

    def clear_search(self) -> None:
        """Clear search field."""
        search_input = self.locator('input[type="search"], input[name="search"], .search-input')
        if search_input.count() > 0:
            search_input.first.fill("")

    # =========================================================================
    # Assertions
    # =========================================================================

    def expect_dashboard_loaded(self) -> None:
        """Assert dashboard is fully loaded."""
        self.wait_for_load_state("networkidle")
        # Should have some content
        expect(self.main_content).to_be_visible()

    def expect_logged_in(self) -> None:
        """Assert user is logged in."""
        expect(self.locator(self.LOGOUT_LINK)).to_be_visible()

    def expect_panel_visible(self, title: str) -> None:
        """Assert panel with title is visible."""
        panel = self.get_panel_by_title(title)
        expect(panel).to_be_visible()
