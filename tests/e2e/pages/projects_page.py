"""
Projects Page Object

Encapsulates project management interactions.
"""
import time
from typing import Dict, List, Optional

from playwright.sync_api import Locator, Page, expect

from .base_page import BasePage


class ProjectsPage(BasePage):
    """Page object for projects management."""

    # Selectors
    PROJECT_LIST = ".project-list, #projects, .projects-container"
    PROJECT_ITEM = ".project-item, .project-card, .project-row, tr[data-project-id]"
    PROJECT_NAME = ".project-name, .name, h3, td:first-child"
    PROJECT_STATUS = ".project-status, .status, .badge"

    # Form selectors
    NEW_PROJECT_BTN = 'button:has-text("New Project"), a:has-text("New Project"), .add-project'
    PROJECT_FORM = "form#project-form, form.project-form, .modal form"
    NAME_INPUT = 'input[name="name"]'
    DESCRIPTION_INPUT = 'textarea[name="description"], input[name="description"]'
    STATUS_SELECT = 'select[name="status"]'
    SUBMIT_BTN = 'button[type="submit"], button:has-text("Save"), button:has-text("Create")'
    CANCEL_BTN = 'button:has-text("Cancel"), .btn-cancel'

    # Action buttons
    EDIT_BTN = 'button:has-text("Edit"), .edit-btn, [title="Edit"]'
    DELETE_BTN = 'button:has-text("Delete"), .delete-btn, [title="Delete"]'
    VIEW_BTN = 'button:has-text("View"), .view-btn, a.view-link'

    def __init__(self, page: Page, base_url: str = "http://localhost:8099"):
        super().__init__(page, base_url)

    def navigate(self) -> "ProjectsPage":
        """Navigate to projects section."""
        self.goto("/#projects")
        self.wait(500)
        return self

    # =========================================================================
    # Project Listing
    # =========================================================================

    def get_projects(self) -> List[Dict]:
        """Get list of all visible projects."""
        projects = []
        items = self.locator(self.PROJECT_ITEM)

        for i in range(items.count()):
            item = items.nth(i)
            name_elem = item.locator(self.PROJECT_NAME)
            status_elem = item.locator(self.PROJECT_STATUS)

            projects.append(
                {
                    "name": name_elem.text_content() if name_elem.count() > 0 else "",
                    "status": status_elem.text_content() if status_elem.count() > 0 else "",
                    "element": item,
                }
            )

        return projects

    def get_project_count(self) -> int:
        """Get number of projects displayed."""
        return self.count(self.PROJECT_ITEM)

    def find_project(self, name: str) -> Optional[Locator]:
        """Find project by name."""
        items = self.locator(self.PROJECT_ITEM)
        for i in range(items.count()):
            item = items.nth(i)
            if name.lower() in (item.text_content() or "").lower():
                return item
        return None

    def project_exists(self, name: str) -> bool:
        """Check if project with name exists."""
        return self.find_project(name) is not None

    # =========================================================================
    # Create Project
    # =========================================================================

    def open_new_project_form(self) -> "ProjectsPage":
        """Open the new project form/modal."""
        self.click(self.NEW_PROJECT_BTN)
        self.wait(500)
        return self

    def fill_project_form(
        self, name: str, description: str = "", status: str = None
    ) -> "ProjectsPage":
        """Fill the project form."""
        self.fill(self.NAME_INPUT, name)

        if description:
            desc_input = self.locator(self.DESCRIPTION_INPUT)
            if desc_input.count() > 0:
                desc_input.first.fill(description)

        if status:
            status_select = self.locator(self.STATUS_SELECT)
            if status_select.count() > 0:
                status_select.first.select_option(status)

        return self

    def submit_project_form(self) -> None:
        """Submit the project form."""
        self.click(self.SUBMIT_BTN)
        self.wait(1000)

    def cancel_project_form(self) -> None:
        """Cancel the project form."""
        cancel = self.locator(self.CANCEL_BTN)
        if cancel.count() > 0:
            cancel.first.click()
        else:
            self.close_modal()

    def create_project(self, name: str, description: str = "", status: str = None) -> None:
        """Create a new project."""
        self.open_new_project_form()
        self.fill_project_form(name, description, status)
        self.submit_project_form()

    # =========================================================================
    # Project Actions
    # =========================================================================

    def click_project(self, name: str) -> bool:
        """Click on a project to view details."""
        project = self.find_project(name)
        if project:
            project.click()
            self.wait(500)
            return True
        return False

    def edit_project(self, name: str) -> bool:
        """Open edit form for a project."""
        project = self.find_project(name)
        if project:
            edit_btn = project.locator(self.EDIT_BTN)
            if edit_btn.count() > 0:
                edit_btn.first.click()
                self.wait(500)
                return True
        return False

    def delete_project(self, name: str, confirm: bool = True) -> bool:
        """Delete a project."""
        project = self.find_project(name)
        if project:
            delete_btn = project.locator(self.DELETE_BTN)
            if delete_btn.count() > 0:
                delete_btn.first.click()

                # Handle confirmation dialog
                if confirm:
                    confirm_btn = self.locator('button:has-text("Confirm"), button:has-text("Yes")')
                    if confirm_btn.count() > 0:
                        confirm_btn.first.click()
                else:
                    cancel_btn = self.locator('button:has-text("Cancel"), button:has-text("No")')
                    if cancel_btn.count() > 0:
                        cancel_btn.first.click()

                self.wait(500)
                return True
        return False

    def view_project(self, name: str) -> bool:
        """View project details."""
        project = self.find_project(name)
        if project:
            view_btn = project.locator(self.VIEW_BTN)
            if view_btn.count() > 0:
                view_btn.first.click()
                self.wait(500)
                return True
            # Try clicking the project name
            name_elem = project.locator(self.PROJECT_NAME)
            if name_elem.count() > 0:
                name_elem.first.click()
                self.wait(500)
                return True
        return False

    # =========================================================================
    # Filtering & Sorting
    # =========================================================================

    def filter_by_status(self, status: str) -> None:
        """Filter projects by status."""
        filter_select = self.locator('select[name="status-filter"], .status-filter')
        if filter_select.count() > 0:
            filter_select.first.select_option(status)
            self.wait(500)

    def sort_by(self, field: str) -> None:
        """Sort projects by field."""
        sort_header = self.locator(f'th:has-text("{field}"), .sort-{field.lower()}')
        if sort_header.count() > 0:
            sort_header.first.click()
            self.wait(500)

    def search_projects(self, query: str) -> None:
        """Search projects."""
        search = self.locator('input[name="project-search"], .project-search')
        if search.count() > 0:
            search.first.fill(query)
            self.page.keyboard.press("Enter")
            self.wait(500)

    # =========================================================================
    # Assertions
    # =========================================================================

    def expect_project_visible(self, name: str) -> None:
        """Assert project is visible in list."""
        project = self.find_project(name)
        assert project is not None, f"Project '{name}' not found"
        expect(project).to_be_visible()

    def expect_project_not_visible(self, name: str) -> None:
        """Assert project is not in list."""
        project = self.find_project(name)
        assert project is None, f"Project '{name}' should not be visible"

    def expect_project_count(self, count: int) -> None:
        """Assert number of projects."""
        actual = self.get_project_count()
        assert actual == count, f"Expected {count} projects, got {actual}"

    def expect_project_count_at_least(self, min_count: int) -> None:
        """Assert at least N projects."""
        actual = self.get_project_count()
        assert actual >= min_count, f"Expected at least {min_count} projects, got {actual}"
