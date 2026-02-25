#!/usr/bin/env python3
"""
Create Milestone Task Helper

Creates a milestone planning task in the Architect dashboard queue.

Usage:
    python3 create_milestone_task.py               # Scan all projects
    python3 create_milestone_task.py architect     # Scan specific project
    python3 create_milestone_task.py --priority 1  # High priority scan
"""

import argparse
import sys
from pathlib import Path

import requests

# Configuration
DASHBOARD_URL = "http://100.112.58.92:8080"
USERNAME = "architect"
PASSWORD = "peace5"

VALID_PROJECTS = ["architect", "claude_browser_agent", "basic_edu_apps_final", "shared_services"]


def create_task(project=None, priority=2):
    """Create a milestone planning task."""

    task_data = {}
    if project:
        if project not in VALID_PROJECTS:
            print(f"Error: Invalid project '{project}'")
            print(f"Valid projects: {', '.join(VALID_PROJECTS)}")
            return False
        task_data["project"] = project

    task = {"task_type": "milestone", "task_data": task_data, "priority": priority}

    try:
        print(f"Creating milestone task...")
        print(f"  Dashboard: {DASHBOARD_URL}")
        if project:
            print(f"  Project: {project}")
        else:
            print(f"  Projects: All ({len(VALID_PROJECTS)})")
        print(f"  Priority: {priority}")

        response = requests.post(
            f"{DASHBOARD_URL}/api/tasks", auth=(USERNAME, PASSWORD), json=task, timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            task_id = result.get("id")
            print(f"\nSuccess! Created task ID: {task_id}")
            print(f"\nThe milestone worker will process this task and generate plans.")
            print(f"Results will be saved to: data/milestones/")
            return True
        else:
            print(f"\nError: {response.status_code}")
            print(response.text)
            return False

    except requests.exceptions.ConnectionError:
        print(f"\nError: Could not connect to dashboard at {DASHBOARD_URL}")
        print("Is the dashboard running?")
        return False
    except Exception as e:
        print(f"\nError: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Create milestone planning task")
    parser.add_argument("project", nargs="?", help="Project to scan (default: all)")
    parser.add_argument(
        "--priority",
        type=int,
        default=2,
        choices=[1, 2, 3, 4, 5],
        help="Task priority (1=highest, 5=lowest, default=2)",
    )
    args = parser.parse_args()

    project = args.project

    # Validate project if specified
    if project and project not in VALID_PROJECTS:
        print(f"Error: Unknown project '{project}'")
        print(f"\nValid projects:")
        for p in VALID_PROJECTS:
            print(f"  - {p}")
        sys.exit(1)

    success = create_task(project, args.priority)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
