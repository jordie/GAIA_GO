#!/usr/bin/env python3
"""
TickTick Open API v1 Client

Integrates with TickTick API v1 endpoints with ETag support for caching.
Uses https://api.ticktick.com/open/v1 (not v2)
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class TickTickAPIv1:
    """TickTick Open API v1 Client with ETag support"""

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.getenv("TICKTICK_TOKEN")
        self.base_url = "https://api.ticktick.com/open/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        if not self.api_token:
            raise ValueError("TICKTICK_TOKEN not set")

        logger.info(f"TickTick API v1 initialized (endpoint: {self.base_url})")

    def test_connection(self) -> bool:
        """Test API connection by getting projects"""
        try:
            response = requests.get(f"{self.base_url}/project", headers=self.headers, timeout=10)

            logger.info(f"API Response Status: {response.status_code}")

            if response.status_code == 200:
                projects = response.json()
                logger.info(f"✓ Connected! Found {len(projects)} projects")
                return True
            else:
                logger.error(f"Auth failed: {response.status_code}")
                logger.error(f"Response: {response.text[:500]}")
                return False

        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    def get_projects(self) -> List[Dict]:
        """Get all projects/folders"""
        try:
            response = requests.get(f"{self.base_url}/project", headers=self.headers, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get projects: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Error getting projects: {e}")
            return []

    def get_lists(self) -> List[Dict]:
        """Get all lists (same as projects in TickTick API)"""
        return self.get_projects()

    def get_project_data(
        self, project_id: str, etag: Optional[str] = None
    ) -> Tuple[Optional[Dict], Optional[str], int]:
        """
        Get project data (tasks) with ETag support.

        Returns:
            Tuple of (data, etag, status_code)
            - data: None if 304 Not Modified
            - etag: ETag from response headers (for next request)
            - status_code: HTTP status code
        """
        try:
            headers = self.headers.copy()

            # Add ETag header for conditional GET
            if etag:
                headers["If-None-Match"] = etag

            response = requests.get(
                f"{self.base_url}/project/{project_id}/data", headers=headers, timeout=10
            )

            new_etag = response.headers.get("ETag")

            if response.status_code == 304:
                # Not Modified - no changes since last sync
                logger.debug(f"304 Not Modified for project {project_id}")
                return None, new_etag, 304

            elif response.status_code == 200:
                # Data changed - return full response
                data = response.json()
                logger.debug(f"200 OK for project {project_id}: {len(data.get('tasks', []))} tasks")
                return data, new_etag, 200

            else:
                logger.error(f"Failed to get project data: {response.status_code}")
                return None, new_etag, response.status_code

        except Exception as e:
            logger.error(f"Error getting project data: {e}")
            return None, None, 500

    def get_focus_list_tasks(self) -> List[Dict]:
        """Get tasks from Focus list"""
        try:
            # Get all projects
            projects = self.get_projects()

            # Find Focus list
            focus_list = None
            for proj in projects:
                if proj.get("name", "").lower() == "focus":
                    focus_list = proj
                    break

            if not focus_list:
                logger.warning("Focus list not found")
                logger.info(f"Available lists: {[p.get('name') for p in projects]}")
                return []

            # Get tasks for Focus list
            project_id = focus_list["id"]
            data, _, status = self.get_project_data(project_id)

            if status == 200 and data:
                tasks = data.get("tasks", [])
                logger.info(f"Found {len(tasks)} tasks in Focus list")
                return tasks
            else:
                logger.error(f"Failed to get Focus tasks: {status}")
                return []

        except Exception as e:
            logger.error(f"Error getting Focus tasks: {e}")
            return []


def main():
    """Main execution"""
    token = os.getenv("TICKTICK_TOKEN")

    if not token:
        print("\nERROR: TICKTICK_TOKEN not set")
        print("Export your token: export TICKTICK_TOKEN='your_token_here'")
        return

    print("\n" + "=" * 70)
    print("TICKTICK API v1 CLIENT")
    print("=" * 70)

    try:
        api = TickTickAPIv1(token)

        # Test connection
        print("\n1. Testing connection...")
        if not api.test_connection():
            print("✗ Connection failed")
            return

        # Get lists
        print("\n2. Fetching your lists...")
        lists = api.get_lists()
        print(f"Found {len(lists)} lists:")
        for lst in lists[:5]:
            print(f"  • {lst.get('name', 'Unknown')} (ID: {lst['id']})")
        if len(lists) > 5:
            print(f"  ... and {len(lists) - 5} more")

        # Get Focus list tasks
        print("\n3. Fetching Focus list tasks...")
        focus_tasks = api.get_focus_list_tasks()

        if focus_tasks:
            print(f"\nTasks in Focus ({len(focus_tasks)}):")
            print("-" * 70)
            for task in focus_tasks[:10]:
                print(f"  ✓ {task.get('title', 'Untitled')}")

            if len(focus_tasks) > 10:
                print(f"  ... and {len(focus_tasks) - 10} more")
        else:
            print("(No tasks in Focus list)")

        print("\n" + "=" * 70 + "\n")

    except Exception as e:
        print(f"\n✗ Error: {e}\n")


if __name__ == "__main__":
    main()
