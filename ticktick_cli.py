#!/usr/bin/env python3
"""
TickTick CLI Tool - Command-line interface for managing TickTick tasks

Supports:
- Create new tasks
- Read/List tasks with filtering
- Update tasks (title, status, priority, date)
- Delete tasks
- Search tasks
- Manage projects/folders
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

import requests

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from services.ticktick_api import TickTickAPIv1  # noqa: E402


class TickTickCLI:
    """Command-line interface for TickTick"""

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.getenv("TICKTICK_TOKEN")
        if not self.api_token:
            print("ERROR: TICKTICK_TOKEN not set")
            sys.exit(1)
        self.api = TickTickAPIv1(self.api_token)

    # ========== CREATE ==========

    def create_task(
        self,
        title: str,
        project: Optional[str] = None,
        content: Optional[str] = None,
        priority: int = 0,
        due_date: Optional[str] = None,
    ) -> bool:
        """Create a new task"""
        try:
            # Get project ID
            projects = self.api.get_projects()
            project_id = None

            if project:
                for proj in projects:
                    if proj["name"].lower() == project.lower():
                        project_id = proj["id"]
                        break
                if not project_id:
                    print(f"✗ Project '{project}' not found")
                    return False
            else:
                # Default to first project
                project_id = projects[0]["id"]

            # Create task via API
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            }

            task_data = {
                "title": title,
                "priority": priority,
            }

            if content:
                task_data["content"] = content
            if due_date:
                task_data["dueDate"] = due_date

            response = requests.post(
                f"{self.api.base_url}/project/{project_id}/task",
                headers=headers,
                json=task_data,
                timeout=10,
            )

            if response.status_code == 200:
                task = response.json()
                print(f"✓ Created task: {task.get('id')}")
                print(f"  Title: {title}")
                if project:
                    print(f"  Project: {project}")
                return True
            else:
                print(f"✗ Failed to create task: {response.status_code}")
                print(f"  {response.text}")
                return False

        except Exception as e:
            print(f"✗ Error creating task: {e}")
            return False

    # ========== READ ==========

    def list_tasks(
        self,
        project: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        limit: int = 20,
    ) -> bool:
        """List tasks with optional filtering"""
        try:
            projects = self.api.get_projects()

            # Filter by project if specified
            if project:
                projects = [p for p in projects if p["name"].lower() == project.lower()]
                if not projects:
                    print(f"✗ Project '{project}' not found")
                    return False

            # Collect all tasks
            all_tasks = []
            for proj in projects:
                data, _, status_code = self.api.get_project_data(proj["id"])
                if status_code == 200 and data:
                    for task in data.get("tasks", []):
                        task["project_name"] = proj["name"]
                        all_tasks.append(task)

            # Filter by status
            if status:
                status_map = {"open": 0, "completed": 1}
                status_val = status_map.get(status.lower())
                if status_val is not None:
                    all_tasks = [t for t in all_tasks if t.get("status") == status_val]

            # Filter by priority
            if priority:
                all_tasks = [t for t in all_tasks if t.get("priority") == priority]

            # Sort by priority and due date
            all_tasks.sort(
                key=lambda t: (
                    -t.get("priority", 0),
                    t.get("dueDate", "9999-12-31"),
                )
            )

            # Display
            if not all_tasks:
                print("No tasks found")
                return True

            print(f"\nTasks ({len(all_tasks)} total):")
            print("-" * 100)

            for i, task in enumerate(all_tasks[:limit], 1):
                status_icon = "✓" if task.get("status") == 1 else "○"
                priority_str = f"[P{task.get('priority')}]" if task.get("priority") else ""
                due_date = task.get("dueDate", "").split("T")[0] if task.get("dueDate") else ""
                project_name = task.get("project_name", "")

                print(f"{i:2}. {status_icon} {task.get('title', 'Untitled')} {priority_str}")
                print(f"    Project: {project_name:20} Due: {due_date}")

                if task.get("content"):
                    preview = task["content"].replace("\n", " ")[:60]
                    print(f"    {preview}...")

                print()

            if len(all_tasks) > limit:
                print(f"... and {len(all_tasks) - limit} more tasks")

            return True

        except Exception as e:
            print(f"✗ Error listing tasks: {e}")
            return False

    def show_task(self, task_id: str) -> bool:
        """Show detailed task information"""
        try:
            projects = self.api.get_projects()

            for proj in projects:
                data, _, status_code = self.api.get_project_data(proj["id"])
                if status_code == 200 and data:
                    for task in data.get("tasks", []):
                        if task.get("id") == task_id:
                            print("\nTask Details:")
                            print("-" * 50)
                            print(f"ID:       {task.get('id')}")
                            print(f"Title:    {task.get('title')}")
                            print(f"Project:  {proj['name']}")
                            print(f"Status:   {'Completed' if task.get('status') == 1 else 'Open'}")
                            print(f"Priority: {task.get('priority', 0)}")
                            print(f"Due:      {task.get('dueDate', 'None')}")
                            print(f"Content:  {task.get('content', '(empty)')}")
                            print(f"Tags:     {', '.join(task.get('tags', []))}")
                            print()
                            return True

            print(f"✗ Task '{task_id}' not found")
            return False

        except Exception as e:
            print(f"✗ Error showing task: {e}")
            return False

    # ========== UPDATE ==========

    def update_task(
        self,
        task_id: str,
        title: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        due_date: Optional[str] = None,
    ) -> bool:
        """Update a task"""
        try:
            # Find task and its project
            projects = self.api.get_projects()
            task = None

            for proj in projects:
                data, _, status_code = self.api.get_project_data(proj["id"])
                if status_code == 200 and data:
                    for t in data.get("tasks", []):
                        if t.get("id") == task_id:
                            task = t
                            break
                if task:
                    break

            if not task:
                print(f"✗ Task '{task_id}' not found")
                return False

            # Build update data
            update_data = {}
            if title:
                update_data["title"] = title
            if status:
                status_map = {"open": 0, "completed": 1}
                update_data["status"] = status_map.get(status.lower(), 0)
            if priority is not None:
                update_data["priority"] = priority
            if due_date:
                update_data["dueDate"] = due_date

            # Update via API
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            }

            response = requests.post(
                f"{self.api.base_url}/task/{task_id}",
                headers=headers,
                json=update_data,
                timeout=10,
            )

            if response.status_code == 200:
                print(f"✓ Updated task: {task_id}")
                return True
            else:
                print(f"✗ Failed to update task: {response.status_code}")
                print(f"  {response.text}")
                return False

        except Exception as e:
            print(f"✗ Error updating task: {e}")
            return False

    # ========== DELETE ==========

    def delete_task(self, task_id: str) -> bool:
        """Delete a task"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            }

            response = requests.delete(
                f"{self.api.base_url}/task/{task_id}",
                headers=headers,
                timeout=10,
            )

            if response.status_code in [200, 204]:
                print(f"✓ Deleted task: {task_id}")
                return True
            else:
                print(f"✗ Failed to delete task: {response.status_code}")
                return False

        except Exception as e:
            print(f"✗ Error deleting task: {e}")
            return False

    # ========== PROJECTS ==========

    def list_projects(self) -> bool:
        """List all projects/folders"""
        try:
            projects = self.api.get_projects()

            print(f"\nProjects ({len(projects)} total):")
            print("-" * 50)

            for i, proj in enumerate(projects, 1):
                status = "✓" if not proj.get("closed") else "✗"
                print(f"{i:2}. {status} {proj.get('name')}")
                print(f"    ID: {proj['id']}")
                print()

            return True

        except Exception as e:
            print(f"✗ Error listing projects: {e}")
            return False

    # ========== SEARCH ==========

    def search_tasks(self, query: str) -> bool:
        """Search tasks by title or content"""
        try:
            projects = self.api.get_projects()
            results = []

            for proj in projects:
                data, _, status_code = self.api.get_project_data(proj["id"])
                if status_code == 200 and data:
                    for task in data.get("tasks", []):
                        title = task.get("title", "").lower()
                        content = task.get("content", "").lower()
                        if query.lower() in title or query.lower() in content:
                            task["project_name"] = proj["name"]
                            results.append(task)

            if not results:
                print(f"No tasks found matching '{query}'")
                return True

            print(f"\nSearch results for '{query}' ({len(results)} found):")
            print("-" * 100)

            for i, task in enumerate(results[:20], 1):
                status_icon = "✓" if task.get("status") == 1 else "○"
                print(f"{i:2}. {status_icon} {task.get('title')}")
                print(f"    Project: {task.get('project_name')}")
                print()

            return True

        except Exception as e:
            print(f"✗ Error searching tasks: {e}")
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="TickTick CLI - Manage your tasks from the command line"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # ===== CREATE =====
    create = subparsers.add_parser("create", help="Create a new task")
    create.add_argument("title", help="Task title")
    create.add_argument("--project", "-p", help="Project name")
    create.add_argument("--content", "-c", help="Task description")
    create.add_argument("--priority", "-pr", type=int, default=0, help="Priority (0-5)")
    create.add_argument("--due", "-d", help="Due date (YYYY-MM-DD)")

    # ===== READ =====
    list_cmd = subparsers.add_parser("list", help="List tasks")
    list_cmd.add_argument("--project", "-p", help="Filter by project")
    list_cmd.add_argument("--status", "-s", choices=["open", "completed"], help="Filter by status")
    list_cmd.add_argument("--priority", "-pr", type=int, help="Filter by priority")
    list_cmd.add_argument("--limit", "-l", type=int, default=20, help="Max results")

    show = subparsers.add_parser("show", help="Show task details")
    show.add_argument("task_id", help="Task ID")

    # ===== UPDATE =====
    update = subparsers.add_parser("update", help="Update a task")
    update.add_argument("task_id", help="Task ID")
    update.add_argument("--title", "-t", help="New title")
    update.add_argument("--status", "-s", choices=["open", "completed"], help="New status")
    update.add_argument("--priority", "-pr", type=int, help="New priority")
    update.add_argument("--due", "-d", help="New due date")

    # ===== DELETE =====
    delete = subparsers.add_parser("delete", help="Delete a task")
    delete.add_argument("task_id", help="Task ID")

    # ===== PROJECTS =====
    subparsers.add_parser("projects", help="List all projects")

    # ===== SEARCH =====
    search = subparsers.add_parser("search", help="Search tasks")
    search.add_argument("query", help="Search query")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    cli = TickTickCLI()

    # Execute command
    if args.command == "create":
        success = cli.create_task(
            args.title,
            project=args.project,
            content=args.content,
            priority=args.priority,
            due_date=args.due,
        )

    elif args.command == "list":
        success = cli.list_tasks(
            project=args.project,
            status=args.status,
            priority=args.priority,
            limit=args.limit,
        )

    elif args.command == "show":
        success = cli.show_task(args.task_id)

    elif args.command == "update":
        success = cli.update_task(
            args.task_id,
            title=args.title,
            status=args.status,
            priority=args.priority,
            due_date=args.due,
        )

    elif args.command == "delete":
        success = cli.delete_task(args.task_id)

    elif args.command == "projects":
        success = cli.list_projects()

    elif args.command == "search":
        success = cli.search_tasks(args.query)

    else:
        parser.print_help()
        success = False

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
