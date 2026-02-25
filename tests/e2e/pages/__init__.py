"""
Page Object Models for Playwright E2E Tests

This package provides page objects that encapsulate UI interactions
and provide a clean API for test code.
"""

from .base_page import BasePage
from .dashboard_page import DashboardPage
from .login_page import LoginPage
from .projects_page import ProjectsPage
from .tasks_page import TasksPage

__all__ = [
    "BasePage",
    "LoginPage",
    "DashboardPage",
    "ProjectsPage",
    "TasksPage",
]
