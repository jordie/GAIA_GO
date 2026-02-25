"""
Tasks Page Object

Encapsulates task queue interactions.
"""
from typing import Dict, List, Optional

from playwright.sync_api import Locator, Page, expect

from .base_page import BasePage


class TasksPage(BasePage):
    """Page object for task queue management."""

    # Selectors
    TASK_LIST = ".task-list, #tasks, .queue-container, table.tasks"
    TASK_ITEM = ".task-item, .task-row, tr[data-task-id], .queue-item"
    TASK_TITLE = ".task-title, .title, td.title, h4"
    TASK_STATUS = ".task-status, .status, .badge"
    TASK_TYPE = ".task-type, .type"
    TASK_PRIORITY = ".task-priority, .priority"

    # Form selectors
    NEW_TASK_BTN = 'button:has-text("New Task"), a:has-text("Add Task"), .add-task'
    TASK_FORM = "form#task-form, form.task-form, .modal form"
    TITLE_INPUT = 'input[name="title"]'
    DESCRIPTION_INPUT = 'textarea[name="description"]'
    TYPE_SELECT = 'select[name="type"], select[name="task_type"]'
    PRIORITY_SELECT = 'select[name="priority"]'
    ASSIGNEE_SELECT = 'select[name="assignee"], select[name="assigned_to"]'
    PROJECT_SELECT = 'select[name="project_id"], select[name="project"]'
    SUBMIT_BTN = 'button[type="submit"], button:has-text("Create")'

    # Action buttons
    CLAIM_BTN = 'button:has-text("Claim"), .claim-btn'
    COMPLETE_BTN = 'button:has-text("Complete"), .complete-btn'
    FAIL_BTN = 'button:has-text("Fail"), .fail-btn'
    RETRY_BTN = 'button:has-text("Retry"), .retry-btn'
    DELETE_BTN = 'button:has-text("Delete"), .delete-btn'

    # Filters
    STATUS_FILTER = 'select[name="status-filter"], .status-filter'
    TYPE_FILTER = 'select[name="type-filter"], .type-filter'
    PRIORITY_FILTER = 'select[name="priority-filter"], .priority-filter'

    def __init__(self, page: Page, base_url: str = "http://localhost:8099"):
        super().__init__(page, base_url)

    def navigate(self) -> "TasksPage":
        """Navigate to tasks section."""
        self.goto("/#tasks")
        self.wait(500)
        return self

    # =========================================================================
    # Task Listing
    # =========================================================================

    def get_tasks(self) -> List[Dict]:
        """Get list of all visible tasks."""
        tasks = []
        items = self.locator(self.TASK_ITEM)

        for i in range(items.count()):
            item = items.nth(i)
            tasks.append(
                {
                    "title": self._get_text(item, self.TASK_TITLE),
                    "status": self._get_text(item, self.TASK_STATUS),
                    "type": self._get_text(item, self.TASK_TYPE),
                    "priority": self._get_text(item, self.TASK_PRIORITY),
                    "element": item,
                }
            )

        return tasks

    def _get_text(self, parent: Locator, selector: str) -> str:
        """Get text from child element."""
        elem = parent.locator(selector)
        return elem.text_content().strip() if elem.count() > 0 else ""

    def get_task_count(self) -> int:
        """Get number of tasks displayed."""
        return self.count(self.TASK_ITEM)

    def find_task(self, title: str) -> Optional[Locator]:
        """Find task by title."""
        items = self.locator(self.TASK_ITEM)
        for i in range(items.count()):
            item = items.nth(i)
            if title.lower() in (item.text_content() or "").lower():
                return item
        return None

    def get_tasks_by_status(self, status: str) -> List[Locator]:
        """Get tasks with specific status."""
        result = []
        items = self.locator(self.TASK_ITEM)
        for i in range(items.count()):
            item = items.nth(i)
            status_elem = item.locator(self.TASK_STATUS)
            if (
                status_elem.count() > 0
                and status.lower() in (status_elem.text_content() or "").lower()
            ):
                result.append(item)
        return result

    # =========================================================================
    # Create Task
    # =========================================================================

    def open_new_task_form(self) -> "TasksPage":
        """Open the new task form."""
        self.click(self.NEW_TASK_BTN)
        self.wait(500)
        return self

    def fill_task_form(
        self,
        title: str,
        description: str = "",
        task_type: str = None,
        priority: str = None,
        project_id: str = None,
        assignee: str = None,
    ) -> "TasksPage":
        """Fill the task form."""
        self.fill(self.TITLE_INPUT, title)

        if description:
            self.locator(self.DESCRIPTION_INPUT).fill(description)

        if task_type:
            type_select = self.locator(self.TYPE_SELECT)
            if type_select.count() > 0:
                type_select.select_option(task_type)

        if priority:
            priority_select = self.locator(self.PRIORITY_SELECT)
            if priority_select.count() > 0:
                priority_select.select_option(priority)

        if project_id:
            project_select = self.locator(self.PROJECT_SELECT)
            if project_select.count() > 0:
                project_select.select_option(project_id)

        if assignee:
            assignee_select = self.locator(self.ASSIGNEE_SELECT)
            if assignee_select.count() > 0:
                assignee_select.select_option(assignee)

        return self

    def submit_task_form(self) -> None:
        """Submit the task form."""
        self.click(self.SUBMIT_BTN)
        self.wait(1000)

    def create_task(
        self, title: str, description: str = "", task_type: str = None, priority: str = None
    ) -> None:
        """Create a new task."""
        self.open_new_task_form()
        self.fill_task_form(title, description, task_type, priority)
        self.submit_task_form()

    # =========================================================================
    # Task Actions
    # =========================================================================

    def claim_task(self, title: str) -> bool:
        """Claim a task."""
        task = self.find_task(title)
        if task:
            claim_btn = task.locator(self.CLAIM_BTN)
            if claim_btn.count() > 0:
                claim_btn.first.click()
                self.wait(500)
                return True
        return False

    def complete_task(self, title: str) -> bool:
        """Mark task as complete."""
        task = self.find_task(title)
        if task:
            complete_btn = task.locator(self.COMPLETE_BTN)
            if complete_btn.count() > 0:
                complete_btn.first.click()
                self.wait(500)
                return True
        return False

    def fail_task(self, title: str, reason: str = "") -> bool:
        """Mark task as failed."""
        task = self.find_task(title)
        if task:
            fail_btn = task.locator(self.FAIL_BTN)
            if fail_btn.count() > 0:
                fail_btn.first.click()
                if reason:
                    reason_input = self.locator('textarea[name="reason"], input[name="reason"]')
                    if reason_input.count() > 0:
                        reason_input.fill(reason)
                confirm = self.locator('button:has-text("Confirm"), button:has-text("Submit")')
                if confirm.count() > 0:
                    confirm.first.click()
                self.wait(500)
                return True
        return False

    def retry_task(self, title: str) -> bool:
        """Retry a failed task."""
        task = self.find_task(title)
        if task:
            retry_btn = task.locator(self.RETRY_BTN)
            if retry_btn.count() > 0:
                retry_btn.first.click()
                self.wait(500)
                return True
        return False

    def delete_task(self, title: str, confirm: bool = True) -> bool:
        """Delete a task."""
        task = self.find_task(title)
        if task:
            delete_btn = task.locator(self.DELETE_BTN)
            if delete_btn.count() > 0:
                delete_btn.first.click()
                if confirm:
                    confirm_btn = self.locator('button:has-text("Confirm"), button:has-text("Yes")')
                    if confirm_btn.count() > 0:
                        confirm_btn.first.click()
                self.wait(500)
                return True
        return False

    # =========================================================================
    # Filtering
    # =========================================================================

    def filter_by_status(self, status: str) -> None:
        """Filter tasks by status."""
        filter_elem = self.locator(self.STATUS_FILTER)
        if filter_elem.count() > 0:
            filter_elem.select_option(status)
            self.wait(500)

    def filter_by_type(self, task_type: str) -> None:
        """Filter tasks by type."""
        filter_elem = self.locator(self.TYPE_FILTER)
        if filter_elem.count() > 0:
            filter_elem.select_option(task_type)
            self.wait(500)

    def filter_by_priority(self, priority: str) -> None:
        """Filter tasks by priority."""
        filter_elem = self.locator(self.PRIORITY_FILTER)
        if filter_elem.count() > 0:
            filter_elem.select_option(priority)
            self.wait(500)

    def clear_filters(self) -> None:
        """Clear all filters."""
        for selector in [self.STATUS_FILTER, self.TYPE_FILTER, self.PRIORITY_FILTER]:
            filter_elem = self.locator(selector)
            if filter_elem.count() > 0:
                filter_elem.select_option("")

    # =========================================================================
    # Assertions
    # =========================================================================

    def expect_task_visible(self, title: str) -> None:
        """Assert task is visible."""
        task = self.find_task(title)
        assert task is not None, f"Task '{title}' not found"
        expect(task).to_be_visible()

    def expect_task_not_visible(self, title: str) -> None:
        """Assert task is not visible."""
        task = self.find_task(title)
        assert task is None, f"Task '{title}' should not be visible"

    def expect_task_status(self, title: str, status: str) -> None:
        """Assert task has specific status."""
        task = self.find_task(title)
        assert task is not None, f"Task '{title}' not found"
        status_elem = task.locator(self.TASK_STATUS)
        expect(status_elem).to_contain_text(status)

    def expect_task_count(self, count: int) -> None:
        """Assert number of tasks."""
        actual = self.get_task_count()
        assert actual == count, f"Expected {count} tasks, got {actual}"

    def expect_pending_tasks(self, count: int) -> None:
        """Assert number of pending tasks."""
        pending = self.get_tasks_by_status("pending")
        assert len(pending) == count, f"Expected {count} pending tasks, got {len(pending)}"
