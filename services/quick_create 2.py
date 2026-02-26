"""
Quick Create Service

Handles rapid task creation with minimal required fields.

Usage:
    from services.quick_create import get_quick_create_service

    service = get_quick_create_service(db_path)
    result = service.quick_create('feature', {'name': 'New Feature', 'project_id': 1})
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Entity types that can be quick-created
QUICK_CREATE_TYPES = {
    "feature": {
        "table": "features",
        "required": ["name", "project_id"],
        "defaults": {"status": "planned", "priority": "medium"},
    },
    "bug": {
        "table": "bugs",
        "required": ["title", "project_id"],
        "defaults": {"status": "open", "severity": "medium"},
    },
    "task": {
        "table": "task_queue",
        "required": ["task_type"],
        "defaults": {"status": "pending", "priority": 0, "max_retries": 3},
    },
    "milestone": {
        "table": "milestones",
        "required": ["name", "project_id"],
        "defaults": {"status": "open"},
    },
    "devops_task": {
        "table": "devops_tasks",
        "required": ["name"],
        "defaults": {"status": "pending", "priority": "medium"},
    },
}


class QuickCreateService:
    """Service for quick task creation."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = None):
        if self._initialized:
            if db_path:
                self.db_path = db_path
            return

        self.db_path = db_path
        self._initialized = True

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def quick_create(self, entity_type: str, data: Dict, created_by: str = None) -> Dict:
        """Quickly create an entity with minimal required fields.

        Args:
            entity_type: Type of entity to create
            data: Entity data (name/title, project_id, etc.)
            created_by: User creating the entity

        Returns:
            Created entity with ID
        """
        if entity_type not in QUICK_CREATE_TYPES:
            raise ValueError(
                f"Unknown entity type: {entity_type}. Valid types: {', '.join(QUICK_CREATE_TYPES.keys())}"
            )

        config = QUICK_CREATE_TYPES[entity_type]

        # Validate required fields
        missing = [f for f in config["required"] if not data.get(f)]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        # Apply defaults
        for key, value in config["defaults"].items():
            if key not in data:
                data[key] = value

        # Add created_by if provided
        if created_by:
            if entity_type in ("feature", "bug"):
                data["assigned_to"] = data.get("assigned_to") or created_by
            elif entity_type == "task":
                pass  # Tasks don't have created_by field in this schema

        # Create based on entity type
        with self._get_connection() as conn:
            if entity_type == "feature":
                return self._create_feature(conn, data)
            elif entity_type == "bug":
                return self._create_bug(conn, data)
            elif entity_type == "task":
                return self._create_task(conn, data)
            elif entity_type == "milestone":
                return self._create_milestone(conn, data)
            elif entity_type == "devops_task":
                return self._create_devops_task(conn, data)

    def _create_feature(self, conn: sqlite3.Connection, data: Dict) -> Dict:
        """Create a feature."""
        conn.execute(
            """
            INSERT INTO features (
                name, description, project_id, milestone_id,
                status, priority, assigned_to, spec,
                estimated_hours, story_points
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                data["name"],
                data.get("description", ""),
                data["project_id"],
                data.get("milestone_id"),
                data.get("status", "planned"),
                data.get("priority", "medium"),
                data.get("assigned_to"),
                data.get("spec", ""),
                data.get("estimated_hours"),
                data.get("story_points"),
            ),
        )
        conn.commit()

        feature_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        feature = conn.execute("SELECT * FROM features WHERE id = ?", (feature_id,)).fetchone()

        logger.info(f"Quick created feature #{feature_id}: {data['name']}")
        return {
            "success": True,
            "entity_type": "feature",
            "id": feature_id,
            "entity": dict(feature),
        }

    def _create_bug(self, conn: sqlite3.Connection, data: Dict) -> Dict:
        """Create a bug."""
        conn.execute(
            """
            INSERT INTO bugs (
                title, description, project_id, milestone_id,
                status, severity, assigned_to, steps_to_reproduce,
                expected_behavior, actual_behavior
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                data["title"],
                data.get("description", ""),
                data["project_id"],
                data.get("milestone_id"),
                data.get("status", "open"),
                data.get("severity", "medium"),
                data.get("assigned_to"),
                data.get("steps_to_reproduce", ""),
                data.get("expected_behavior", ""),
                data.get("actual_behavior", ""),
            ),
        )
        conn.commit()

        bug_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        bug = conn.execute("SELECT * FROM bugs WHERE id = ?", (bug_id,)).fetchone()

        logger.info(f"Quick created bug #{bug_id}: {data['title']}")
        return {"success": True, "entity_type": "bug", "id": bug_id, "entity": dict(bug)}

    def _create_task(self, conn: sqlite3.Connection, data: Dict) -> Dict:
        """Create a task queue item."""
        task_data = data.get("task_data", {})
        if isinstance(task_data, dict):
            # Add name/description to task_data if provided
            if data.get("name"):
                task_data["name"] = data["name"]
            if data.get("description"):
                task_data["description"] = data["description"]
            task_data = json.dumps(task_data)

        conn.execute(
            """
            INSERT INTO task_queue (
                task_type, task_data, priority, status,
                max_retries, timeout_seconds, story_points, estimated_hours
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                data["task_type"],
                task_data,
                data.get("priority", 0),
                data.get("status", "pending"),
                data.get("max_retries", 3),
                data.get("timeout_seconds"),
                data.get("story_points"),
                data.get("estimated_hours"),
            ),
        )
        conn.commit()

        task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        task = conn.execute("SELECT * FROM task_queue WHERE id = ?", (task_id,)).fetchone()

        logger.info(f"Quick created task #{task_id}: {data['task_type']}")
        return {"success": True, "entity_type": "task", "id": task_id, "entity": dict(task)}

    def _create_milestone(self, conn: sqlite3.Connection, data: Dict) -> Dict:
        """Create a milestone."""
        conn.execute(
            """
            INSERT INTO milestones (
                name, description, project_id, target_date, status
            ) VALUES (?, ?, ?, ?, ?)
        """,
            (
                data["name"],
                data.get("description", ""),
                data["project_id"],
                data.get("target_date"),
                data.get("status", "open"),
            ),
        )
        conn.commit()

        milestone_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        milestone = conn.execute(
            "SELECT * FROM milestones WHERE id = ?", (milestone_id,)
        ).fetchone()

        logger.info(f"Quick created milestone #{milestone_id}: {data['name']}")
        return {
            "success": True,
            "entity_type": "milestone",
            "id": milestone_id,
            "entity": dict(milestone),
        }

    def _create_devops_task(self, conn: sqlite3.Connection, data: Dict) -> Dict:
        """Create a devops task."""
        conn.execute(
            """
            INSERT INTO devops_tasks (
                name, description, category, priority, status,
                assigned_to, scheduled_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                data["name"],
                data.get("description", ""),
                data.get("category", "general"),
                data.get("priority", "medium"),
                data.get("status", "pending"),
                data.get("assigned_to"),
                data.get("scheduled_at"),
            ),
        )
        conn.commit()

        task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        task = conn.execute("SELECT * FROM devops_tasks WHERE id = ?", (task_id,)).fetchone()

        logger.info(f"Quick created devops task #{task_id}: {data['name']}")
        return {"success": True, "entity_type": "devops_task", "id": task_id, "entity": dict(task)}

    def get_quick_create_options(self) -> Dict:
        """Get options for quick create (projects, milestones, etc.)."""
        with self._get_connection() as conn:
            # Get active projects
            projects = conn.execute(
                """
                SELECT id, name FROM projects
                WHERE status != 'archived'
                ORDER BY name
            """
            ).fetchall()

            # Get open milestones
            milestones = conn.execute(
                """
                SELECT m.id, m.name, m.project_id, p.name as project_name
                FROM milestones m
                LEFT JOIN projects p ON m.project_id = p.id
                WHERE m.status != 'completed'
                ORDER BY m.target_date, m.name
            """
            ).fetchall()

            # Get task types
            task_types = conn.execute(
                """
                SELECT DISTINCT task_type FROM task_queue
                ORDER BY task_type
            """
            ).fetchall()

            return {
                "projects": [dict(p) for p in projects],
                "milestones": [dict(m) for m in milestones],
                "task_types": [t["task_type"] for t in task_types]
                + ["shell", "python", "git", "deploy", "test", "build", "tmux"],
                "priorities": ["critical", "high", "medium", "low"],
                "severities": ["critical", "high", "medium", "low"],
                "entity_types": list(QUICK_CREATE_TYPES.keys()),
            }

    def parse_quick_input(self, text: str) -> Dict:
        """Parse a quick input string into structured data.

        Supports formats like:
        - "feature: Add login page @project:1 #high"
        - "bug: Button not working @project:2 !critical"
        - "task: Run tests"

        Args:
            text: Quick input text

        Returns:
            Parsed data with entity_type and fields
        """
        text = text.strip()

        # Detect entity type from prefix
        entity_type = "feature"  # Default
        for etype in QUICK_CREATE_TYPES.keys():
            if text.lower().startswith(f"{etype}:"):
                entity_type = etype
                text = text[len(etype) + 1 :].strip()
                break

        data = {}

        # Parse project reference (@project:N or @N)
        import re

        project_match = re.search(r"@project:(\d+)|@(\d+)", text)
        if project_match:
            project_id = project_match.group(1) or project_match.group(2)
            data["project_id"] = int(project_id)
            text = re.sub(r"@project:\d+|@\d+", "", text).strip()

        # Parse milestone reference (%milestone:N or %N)
        milestone_match = re.search(r"%milestone:(\d+)|%(\d+)", text)
        if milestone_match:
            milestone_id = milestone_match.group(1) or milestone_match.group(2)
            data["milestone_id"] = int(milestone_id)
            text = re.sub(r"%milestone:\d+|%\d+", "", text).strip()

        # Parse priority (#high, #critical, etc.)
        priority_match = re.search(r"#(critical|high|medium|low)", text, re.I)
        if priority_match:
            data["priority"] = priority_match.group(1).lower()
            text = re.sub(r"#(critical|high|medium|low)", "", text, flags=re.I).strip()

        # Parse severity for bugs (!critical, !high, etc.)
        severity_match = re.search(r"!(critical|high|medium|low)", text, re.I)
        if severity_match:
            data["severity"] = severity_match.group(1).lower()
            text = re.sub(r"!(critical|high|medium|low)", "", text, flags=re.I).strip()

        # Parse assignee (+username)
        assignee_match = re.search(r"\+(\w+)", text)
        if assignee_match:
            data["assigned_to"] = assignee_match.group(1)
            text = re.sub(r"\+\w+", "", text).strip()

        # Remaining text is the name/title
        text = " ".join(text.split())  # Normalize whitespace

        if entity_type == "bug":
            data["title"] = text
        elif entity_type == "task":
            data["task_type"] = data.get("task_type", "shell")
            data["task_data"] = {"name": text, "description": text}
        else:
            data["name"] = text

        return {"entity_type": entity_type, "data": data, "parsed_text": text}


# Singleton getter
_service_instance = None
_service_lock = threading.Lock()


def get_quick_create_service(db_path: str = None) -> QuickCreateService:
    global _service_instance
    if _service_instance is None or db_path:
        with _service_lock:
            if _service_instance is None or db_path:
                _service_instance = QuickCreateService(db_path)
    return _service_instance
