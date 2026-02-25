#!/usr/bin/env python3
"""
Roadmap API for Autonomous Agent Task Assignment

Allows Go Wrapper agents to:
- Query available tasks from the roadmap
- Claim tasks for work
- Update task progress
- Mark tasks as complete

Features:
    - Task prioritization and selection
    - Agent assignment tracking
    - Progress reporting
    - Automatic task routing based on complexity

Usage:
    from services.roadmap_api import RoadmapAPI

    api = RoadmapAPI()

    # Agent queries available tasks
    tasks = api.get_available_tasks(agent_id="agent-1")

    # Agent claims a task
    task = api.claim_task(task_id="A01", agent_id="agent-1")

    # Agent updates progress
    api.update_task_progress(task_id="A01", progress=50, status="in_progress")

    # Agent completes task
    api.complete_task(task_id="A01", agent_id="agent-1")
"""

import json
import logging
import os
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RoadmapAPI")


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class Task:
    """Roadmap task with agent assignment."""

    task_id: str
    title: str
    description: str = ""
    feature: str = ""
    priority: str = "medium"
    status: str = "pending"
    estimated_hours: float = 0.0
    progress_percent: int = 0
    assigned_agent: Optional[str] = None
    assigned_at: Optional[str] = None
    completed_at: Optional[str] = None
    subtasks: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    project: str = "architect"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


# =============================================================================
# Roadmap API
# =============================================================================


class RoadmapAPI:
    """
    API for agents to interact with project roadmap.

    Manages task assignment, progress tracking, and completion.
    """

    def __init__(self, db_path: str = "data/roadmap_tasks.db"):
        """
        Initialize roadmap API.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._ensure_db()

        # Roadmap file paths
        self.roadmap_file = Path("data/milestones/all_projects_roadmap.md")
        self.tasks_file = Path("TASKS.md")

        logger.info(f"RoadmapAPI initialized (DB: {db_path})")

    def _ensure_db(self):
        """Ensure database and tables exist."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_assignments (
                    task_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    feature TEXT,
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'pending',
                    estimated_hours REAL DEFAULT 0.0,
                    progress_percent INTEGER DEFAULT 0,
                    assigned_agent TEXT,
                    assigned_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    project TEXT DEFAULT 'architect',
                    metadata TEXT
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    update_type TEXT NOT NULL,
                    message TEXT,
                    progress_percent INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """
            )

            conn.commit()

    def sync_from_roadmap(self) -> int:
        """
        Sync tasks from roadmap files into database.

        Returns:
            Number of tasks synced
        """
        tasks = self._parse_tasks_from_roadmap()

        with sqlite3.connect(self.db_path) as conn:
            for task in tasks:
                # Check if task exists
                existing = conn.execute(
                    "SELECT status, assigned_agent FROM task_assignments WHERE task_id = ?",
                    (task.task_id,),
                ).fetchone()

                if existing:
                    # Don't overwrite if already assigned or completed
                    status, assigned_agent = existing
                    if status in ["in_progress", "completed"] or assigned_agent:
                        continue

                # Insert or update
                conn.execute(
                    """
                    INSERT OR REPLACE INTO task_assignments
                    (task_id, title, description, feature, priority, status,
                     estimated_hours, project, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        task.task_id,
                        task.title,
                        task.description,
                        task.feature,
                        task.priority,
                        task.status,
                        task.estimated_hours,
                        task.project,
                        json.dumps({"subtasks": task.subtasks, "dependencies": task.dependencies}),
                    ),
                )

            conn.commit()

        logger.info(f"Synced {len(tasks)} tasks from roadmap")
        return len(tasks)

    def _parse_tasks_from_roadmap(self) -> List[Task]:
        """Parse tasks from TASKS.md and roadmap files."""
        tasks = []

        # Parse TASKS.md if it exists
        if self.tasks_file.exists():
            content = self.tasks_file.read_text()
            tasks.extend(self._parse_tasks_md(content))

        return tasks

    def _parse_tasks_md(self, content: str) -> List[Task]:
        """Parse TASKS.md format."""
        tasks = []

        # Find all task sections
        # Use negative lookahead to not match ### (task headers)
        active_pattern = r"## Active Tasks.*?(?=\n## (?!#)|\Z)"
        pending_pattern = r"## Pending Tasks.*?(?=\n## (?!#)|\Z)"

        for pattern, default_status in [
            (active_pattern, "in_progress"),
            (pending_pattern, "pending"),
        ]:
            match = re.search(pattern, content, re.DOTALL)
            if not match:
                continue

            section = match.group(0)

            # Parse individual tasks
            task_pattern = r"### \[([AP]\d+)\] (.+?)(?=###|\Z)"
            for task_match in re.finditer(task_pattern, section, re.DOTALL):
                task_id = task_match.group(1)
                task_body = task_match.group(2)

                # Extract title (first line)
                lines = task_body.strip().split("\n")
                title = lines[0].strip()

                # Extract feature
                feature = ""
                feature_match = re.search(r"\*\*Feature:\*\* (.+)", task_body)
                if feature_match:
                    feature = feature_match.group(1).strip()

                # Extract priority
                priority = "medium"
                priority_match = re.search(r"\*\*Priority:\*\* (\w+)", task_body)
                if priority_match:
                    priority = priority_match.group(1).lower()

                # Extract subtasks
                subtasks = []
                for subtask in re.findall(r"- \[ \] (.+)", task_body):
                    subtasks.append(subtask.strip())

                tasks.append(
                    Task(
                        task_id=task_id,
                        title=title,
                        feature=feature,
                        priority=priority,
                        status=default_status,
                        subtasks=subtasks,
                    )
                )

        return tasks

    def get_available_tasks(
        self, agent_id: str, project: str = None, priority: str = None, limit: int = 10
    ) -> List[Task]:
        """
        Get tasks available for assignment.

        Args:
            agent_id: ID of requesting agent
            project: Filter by project (None = all projects)
            priority: Filter by priority (None = all priorities)
            limit: Maximum tasks to return

        Returns:
            List of available tasks, prioritized
        """
        query = """
            SELECT task_id, title, description, feature, priority, status,
                   estimated_hours, progress_percent, project, metadata
            FROM task_assignments
            WHERE status = 'pending' AND assigned_agent IS NULL
        """
        params = []

        if project:
            query += " AND project = ?"
            params.append(project)

        if priority:
            query += " AND priority = ?"
            params.append(priority)

        # Order by priority (high > medium > low), then by estimated_hours
        query += """
            ORDER BY
                CASE priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                    ELSE 4
                END,
                estimated_hours ASC
            LIMIT ?
        """
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

        tasks = []
        for row in rows:
            metadata = json.loads(row["metadata"] or "{}")
            tasks.append(
                Task(
                    task_id=row["task_id"],
                    title=row["title"],
                    description=row["description"] or "",
                    feature=row["feature"] or "",
                    priority=row["priority"],
                    status=row["status"],
                    estimated_hours=row["estimated_hours"],
                    progress_percent=row["progress_percent"],
                    project=row["project"],
                    subtasks=metadata.get("subtasks", []),
                    dependencies=metadata.get("dependencies", []),
                )
            )

        logger.info(f"Agent {agent_id} queried {len(tasks)} available tasks")
        return tasks

    def claim_task(self, task_id: str, agent_id: str) -> Optional[Task]:
        """
        Claim a task for an agent.

        Args:
            task_id: Task to claim
            agent_id: Agent claiming the task

        Returns:
            Task object if successful, None if already claimed
        """
        with sqlite3.connect(self.db_path) as conn:
            # Check if task is available
            row = conn.execute(
                "SELECT assigned_agent, status FROM task_assignments WHERE task_id = ?", (task_id,)
            ).fetchone()

            if not row:
                logger.warning(f"Task {task_id} not found")
                return None

            assigned_agent, status = row

            if assigned_agent or status != "pending":
                logger.warning(f"Task {task_id} already claimed by {assigned_agent}")
                return None

            # Claim the task
            conn.execute(
                """
                UPDATE task_assignments
                SET assigned_agent = ?, assigned_at = ?, status = 'in_progress'
                WHERE task_id = ?
            """,
                (agent_id, datetime.now().isoformat(), task_id),
            )

            # Log the claim
            conn.execute(
                """
                INSERT INTO task_updates (task_id, agent_id, update_type, message)
                VALUES (?, ?, 'claim', 'Task claimed by agent')
            """,
                (task_id, agent_id),
            )

            conn.commit()

            # Fetch and return the task
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT task_id, title, description, feature, priority, status,
                       estimated_hours, progress_percent, assigned_agent, project, metadata
                FROM task_assignments WHERE task_id = ?
            """,
                (task_id,),
            ).fetchone()

            if row:
                metadata = json.loads(row["metadata"] or "{}")
                task = Task(
                    task_id=row["task_id"],
                    title=row["title"],
                    description=row["description"] or "",
                    feature=row["feature"] or "",
                    priority=row["priority"],
                    status=row["status"],
                    estimated_hours=row["estimated_hours"],
                    progress_percent=row["progress_percent"],
                    assigned_agent=row["assigned_agent"],
                    project=row["project"],
                    subtasks=metadata.get("subtasks", []),
                    dependencies=metadata.get("dependencies", []),
                )

                logger.info(f"Agent {agent_id} claimed task {task_id}: {task.title}")
                return task

        return None

    def update_task_progress(
        self, task_id: str, agent_id: str, progress: int, message: str = None
    ) -> bool:
        """
        Update task progress.

        Args:
            task_id: Task ID
            agent_id: Agent ID
            progress: Progress percentage (0-100)
            message: Optional progress message

        Returns:
            True if successful
        """
        with sqlite3.connect(self.db_path) as conn:
            # Update progress
            conn.execute(
                "UPDATE task_assignments SET progress_percent = ? WHERE task_id = ?",
                (progress, task_id),
            )

            # Log the update
            conn.execute(
                """
                INSERT INTO task_updates (task_id, agent_id, update_type, message, progress_percent)
                VALUES (?, ?, 'progress', ?, ?)
            """,
                (task_id, agent_id, message or f"Progress: {progress}%", progress),
            )

            conn.commit()

        logger.info(f"Agent {agent_id} updated task {task_id}: {progress}%")
        return True

    def complete_task(self, task_id: str, agent_id: str, notes: str = None) -> bool:
        """
        Mark task as complete.

        Args:
            task_id: Task ID
            agent_id: Agent ID
            notes: Optional completion notes

        Returns:
            True if successful
        """
        with sqlite3.connect(self.db_path) as conn:
            # Mark complete
            conn.execute(
                """
                UPDATE task_assignments
                SET status = 'completed', progress_percent = 100, completed_at = ?
                WHERE task_id = ?
            """,
                (datetime.now().isoformat(), task_id),
            )

            # Log completion
            conn.execute(
                """
                INSERT INTO task_updates (task_id, agent_id, update_type, message)
                VALUES (?, ?, 'complete', ?)
            """,
                (task_id, agent_id, notes or "Task completed"),
            )

            conn.commit()

        logger.info(f"Agent {agent_id} completed task {task_id}")
        return True

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed task status including history."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get task
            row = conn.execute(
                """
                SELECT task_id, title, description, feature, priority, status,
                       estimated_hours, progress_percent, assigned_agent, assigned_at,
                       completed_at, project, metadata
                FROM task_assignments WHERE task_id = ?
            """,
                (task_id,),
            ).fetchone()

            if not row:
                return None

            # Get updates
            updates = conn.execute(
                """
                SELECT update_type, message, progress_percent, timestamp
                FROM task_updates
                WHERE task_id = ?
                ORDER BY timestamp DESC
                LIMIT 10
            """,
                (task_id,),
            ).fetchall()

            metadata = json.loads(row["metadata"] or "{}")

            return {
                "task_id": row["task_id"],
                "title": row["title"],
                "description": row["description"],
                "feature": row["feature"],
                "priority": row["priority"],
                "status": row["status"],
                "estimated_hours": row["estimated_hours"],
                "progress_percent": row["progress_percent"],
                "assigned_agent": row["assigned_agent"],
                "assigned_at": row["assigned_at"],
                "completed_at": row["completed_at"],
                "project": row["project"],
                "subtasks": metadata.get("subtasks", []),
                "dependencies": metadata.get("dependencies", []),
                "updates": [dict(u) for u in updates],
            }

    def get_agent_tasks(self, agent_id: str) -> List[Task]:
        """Get all tasks assigned to an agent."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT task_id, title, description, feature, priority, status,
                       estimated_hours, progress_percent, assigned_agent, project, metadata
                FROM task_assignments
                WHERE assigned_agent = ?
                ORDER BY
                    CASE status
                        WHEN 'in_progress' THEN 1
                        WHEN 'pending' THEN 2
                        WHEN 'completed' THEN 3
                        ELSE 4
                    END
            """,
                (agent_id,),
            ).fetchall()

        tasks = []
        for row in rows:
            metadata = json.loads(row["metadata"] or "{}")
            tasks.append(
                Task(
                    task_id=row["task_id"],
                    title=row["title"],
                    description=row["description"] or "",
                    feature=row["feature"] or "",
                    priority=row["priority"],
                    status=row["status"],
                    estimated_hours=row["estimated_hours"],
                    progress_percent=row["progress_percent"],
                    assigned_agent=row["assigned_agent"],
                    project=row["project"],
                    subtasks=metadata.get("subtasks", []),
                    dependencies=metadata.get("dependencies", []),
                )
            )

        return tasks

    def get_stats(self) -> Dict[str, Any]:
        """Get roadmap statistics."""
        with sqlite3.connect(self.db_path) as conn:
            # Overall stats
            total = conn.execute("SELECT COUNT(*) FROM task_assignments").fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM task_assignments WHERE status = 'pending'"
            ).fetchone()[0]
            in_progress = conn.execute(
                "SELECT COUNT(*) FROM task_assignments WHERE status = 'in_progress'"
            ).fetchone()[0]
            completed = conn.execute(
                "SELECT COUNT(*) FROM task_assignments WHERE status = 'completed'"
            ).fetchone()[0]

            # Agent stats
            agent_stats = conn.execute(
                """
                SELECT assigned_agent, COUNT(*) as task_count,
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count
                FROM task_assignments
                WHERE assigned_agent IS NOT NULL
                GROUP BY assigned_agent
            """
            ).fetchall()

            return {
                "total_tasks": total,
                "pending": pending,
                "in_progress": in_progress,
                "completed": completed,
                "agents": [
                    {"agent_id": row[0], "assigned_tasks": row[1], "completed_tasks": row[2]}
                    for row in agent_stats
                ],
            }


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    # Demo usage
    print("=" * 60)
    print("Roadmap API Demo")
    print("=" * 60)
    print()

    api = RoadmapAPI()

    # Sync from roadmap
    synced = api.sync_from_roadmap()
    print(f"Synced {synced} tasks from roadmap")
    print()

    # Get stats
    stats = api.get_stats()
    print("Roadmap Statistics:")
    print(f"  Total Tasks: {stats['total_tasks']}")
    print(f"  Pending: {stats['pending']}")
    print(f"  In Progress: {stats['in_progress']}")
    print(f"  Completed: {stats['completed']}")
    print()

    # Get available tasks
    tasks = api.get_available_tasks("demo-agent", limit=5)
    print(f"Available Tasks ({len(tasks)}):")
    for task in tasks:
        print(f"  [{task.task_id}] {task.title} (priority: {task.priority})")
    print()

    print("Roadmap API ready")
