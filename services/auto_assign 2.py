"""
Task Auto-Assignment Service

Automatically assigns tasks to workers based on workload, skills, and availability.

Usage:
    from services.auto_assign import get_auto_assign_service

    service = get_auto_assign_service(db_path)
    result = service.assign_task(task_id)
    results = service.assign_all_pending()
"""

import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Assignment strategies
STRATEGY_LEAST_LOADED = "least_loaded"  # Assign to worker with fewest tasks
STRATEGY_ROUND_ROBIN = "round_robin"  # Cycle through workers
STRATEGY_SKILL_MATCH = "skill_match"  # Best skill match first
STRATEGY_BALANCED = "balanced"  # Combination of load + skills
STRATEGY_FASTEST = "fastest"  # Based on average completion time

DEFAULT_STRATEGY = STRATEGY_BALANCED

# Workload calculation weights
WEIGHT_TASK_COUNT = 1.0  # Weight per active task
WEIGHT_STORY_POINTS = 0.5  # Weight per story point
WEIGHT_ESTIMATED_HOURS = 2.0  # Weight per estimated hour
WEIGHT_RUNNING_TASK = 1.5  # Additional weight for running tasks

# Worker availability thresholds
MAX_CONCURRENT_TASKS = 5  # Maximum tasks per worker
HEARTBEAT_TIMEOUT_SECONDS = 300  # 5 minutes heartbeat timeout
SKILL_MATCH_THRESHOLD = 30  # Minimum skill match score (0-100)


class AutoAssignService:
    """Service for automatic task assignment based on workload."""

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
        self._round_robin_index = 0
        self._initialized = True

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_worker_workload(self, worker_id: str, conn: sqlite3.Connection = None) -> Dict:
        """Calculate the current workload for a worker.

        Returns:
            Dict with workload metrics:
            - task_count: Number of active tasks
            - running_count: Number of currently running tasks
            - pending_count: Number of pending assigned tasks
            - story_points: Total story points of active tasks
            - estimated_hours: Total estimated hours
            - workload_score: Normalized workload score (higher = more loaded)
        """
        close_conn = False
        if conn is None:
            conn = self._get_connection()
            close_conn = True

        try:
            result = conn.execute(
                """
                SELECT
                    COUNT(*) as task_count,
                    SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running_count,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count,
                    COALESCE(SUM(story_points), 0) as story_points,
                    COALESCE(SUM(estimated_hours), 0) as estimated_hours
                FROM task_queue
                WHERE assigned_worker = ?
                AND status IN ('pending', 'running')
            """,
                (worker_id,),
            ).fetchone()

            task_count = result["task_count"] or 0
            running_count = result["running_count"] or 0
            pending_count = result["pending_count"] or 0
            story_points = result["story_points"] or 0
            estimated_hours = result["estimated_hours"] or 0

            # Calculate workload score
            workload_score = (
                task_count * WEIGHT_TASK_COUNT
                + running_count * WEIGHT_RUNNING_TASK
                + story_points * WEIGHT_STORY_POINTS
                + estimated_hours * WEIGHT_ESTIMATED_HOURS
            )

            return {
                "worker_id": worker_id,
                "task_count": task_count,
                "running_count": running_count,
                "pending_count": pending_count,
                "story_points": story_points,
                "estimated_hours": estimated_hours,
                "workload_score": round(workload_score, 2),
            }
        finally:
            if close_conn:
                conn.close()

    def get_available_workers(self, conn: sqlite3.Connection = None) -> List[Dict]:
        """Get all available workers with their workload metrics.

        Returns:
            List of workers with workload info, sorted by workload_score ascending
        """
        close_conn = False
        if conn is None:
            conn = self._get_connection()
            close_conn = True

        try:
            # Get workers that are online and not at max capacity
            heartbeat_threshold = datetime.now() - timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS)

            workers = conn.execute(
                """
                SELECT
                    w.id,
                    w.node_id,
                    w.worker_type,
                    w.status,
                    w.last_heartbeat,
                    w.tasks_completed,
                    w.tasks_failed,
                    n.hostname as node_hostname
                FROM workers w
                LEFT JOIN nodes n ON w.node_id = n.id
                WHERE w.status != 'offline'
                AND (w.last_heartbeat IS NULL OR w.last_heartbeat > ?)
            """,
                (heartbeat_threshold.isoformat(),),
            ).fetchall()

            available = []
            for worker in workers:
                workload = self.get_worker_workload(worker["id"], conn)

                # Skip workers at max capacity
                if workload["task_count"] >= MAX_CONCURRENT_TASKS:
                    continue

                worker_info = dict(worker)
                worker_info.update(workload)
                worker_info["capacity_remaining"] = MAX_CONCURRENT_TASKS - workload["task_count"]
                available.append(worker_info)

            # Sort by workload score (least loaded first)
            available.sort(key=lambda w: w["workload_score"])

            return available

        finally:
            if close_conn:
                conn.close()

    def get_skill_score(self, worker_id: str, task_type: str, conn: sqlite3.Connection) -> float:
        """Get skill match score for a worker and task type.

        Returns:
            Score from 0-100, or 100 if no skill requirements defined
        """
        try:
            # Check if task type has skill requirements
            requirements = conn.execute(
                """
                SELECT skill_name, min_proficiency, priority
                FROM task_skill_requirements
                WHERE task_type = ?
            """,
                (task_type,),
            ).fetchall()

            if not requirements:
                return 100.0  # No requirements = full match

            # Get worker skills
            skills = conn.execute(
                """
                SELECT skill_name, proficiency
                FROM worker_skills
                WHERE worker_id = ?
            """,
                (worker_id,),
            ).fetchall()

            skill_map = {s["skill_name"]: s["proficiency"] for s in skills}

            total_weight = 0
            weighted_score = 0

            for req in requirements:
                weight = req["priority"] or 1
                total_weight += weight

                if req["skill_name"] in skill_map:
                    proficiency = skill_map[req["skill_name"]]
                    if proficiency >= req["min_proficiency"]:
                        weighted_score += weight * 100
                    else:
                        # Partial credit
                        weighted_score += weight * (proficiency / req["min_proficiency"] * 50)

            return weighted_score / total_weight if total_weight > 0 else 100.0

        except Exception as e:
            logger.warning(f"Error calculating skill score: {e}")
            return 50.0  # Default to mid-range on error

    def get_worker_avg_completion_time(
        self, worker_id: str, task_type: str, conn: sqlite3.Connection
    ) -> Optional[float]:
        """Get average completion time for a worker on a task type.

        Returns:
            Average seconds, or None if no data
        """
        result = conn.execute(
            """
            SELECT AVG(
                CAST((julianday(completed_at) - julianday(started_at)) * 86400 AS REAL)
            ) as avg_seconds
            FROM task_queue
            WHERE assigned_worker = ?
            AND task_type = ?
            AND status = 'completed'
            AND started_at IS NOT NULL
            AND completed_at IS NOT NULL
        """,
            (worker_id, task_type),
        ).fetchone()

        return result["avg_seconds"] if result and result["avg_seconds"] else None

    def select_worker(
        self, task: Dict, strategy: str = None, conn: sqlite3.Connection = None
    ) -> Optional[Dict]:
        """Select the best worker for a task based on strategy.

        Args:
            task: Task dict with id, task_type, priority, etc.
            strategy: Assignment strategy to use
            conn: Optional database connection

        Returns:
            Selected worker dict, or None if no suitable worker
        """
        close_conn = False
        if conn is None:
            conn = self._get_connection()
            close_conn = True

        try:
            strategy = strategy or DEFAULT_STRATEGY
            available = self.get_available_workers(conn)

            if not available:
                return None

            task_type = task.get("task_type", "default")

            if strategy == STRATEGY_LEAST_LOADED:
                # Already sorted by workload
                return available[0]

            elif strategy == STRATEGY_ROUND_ROBIN:
                # Cycle through available workers
                self._round_robin_index = (self._round_robin_index + 1) % len(available)
                return available[self._round_robin_index]

            elif strategy == STRATEGY_SKILL_MATCH:
                # Rank by skill match score
                for worker in available:
                    worker["skill_score"] = self.get_skill_score(worker["id"], task_type, conn)
                available.sort(key=lambda w: w["skill_score"], reverse=True)

                # Filter by minimum skill threshold
                qualified = [w for w in available if w["skill_score"] >= SKILL_MATCH_THRESHOLD]
                return qualified[0] if qualified else available[0]

            elif strategy == STRATEGY_FASTEST:
                # Rank by historical completion time
                for worker in available:
                    avg_time = self.get_worker_avg_completion_time(worker["id"], task_type, conn)
                    # Lower is better, use infinity for unknown
                    worker["avg_completion_time"] = avg_time if avg_time else float("inf")

                available.sort(key=lambda w: w["avg_completion_time"])
                return available[0]

            elif strategy == STRATEGY_BALANCED:
                # Combine workload, skills, and performance
                for worker in available:
                    skill_score = self.get_skill_score(worker["id"], task_type, conn)
                    avg_time = self.get_worker_avg_completion_time(worker["id"], task_type, conn)

                    # Normalize scores (0-100 scale)
                    workload_penalty = min(worker["workload_score"] * 10, 100)
                    speed_score = 100 - min((avg_time or 600) / 60, 100) if avg_time else 50

                    # Combined score (higher is better)
                    worker["combined_score"] = (
                        skill_score * 0.4 + (100 - workload_penalty) * 0.4 + speed_score * 0.2
                    )

                available.sort(key=lambda w: w["combined_score"], reverse=True)
                return available[0]

            else:
                # Default to least loaded
                return available[0]

        finally:
            if close_conn:
                conn.close()

    def assign_task(self, task_id: int, strategy: str = None, force: bool = False) -> Dict:
        """Assign a task to the best available worker.

        Args:
            task_id: ID of task to assign
            strategy: Assignment strategy to use
            force: If True, reassign even if already assigned

        Returns:
            Dict with assignment result
        """
        with self._get_connection() as conn:
            # Get task
            task = conn.execute("SELECT * FROM task_queue WHERE id = ?", (task_id,)).fetchone()

            if not task:
                return {"success": False, "error": "Task not found"}

            task = dict(task)

            # Check if already assigned
            if task["assigned_worker"] and not force:
                return {
                    "success": False,
                    "error": "Task already assigned",
                    "assigned_worker": task["assigned_worker"],
                }

            # Check status
            if task["status"] not in ("pending", "running"):
                return {"success": False, "error": f"Task status '{task['status']}' not assignable"}

            # Select best worker
            worker = self.select_worker(task, strategy, conn)

            if not worker:
                return {"success": False, "error": "No available workers", "task_id": task_id}

            # Assign task
            conn.execute(
                """
                UPDATE task_queue
                SET assigned_worker = ?, assigned_node = ?
                WHERE id = ?
            """,
                (worker["id"], worker.get("node_id"), task_id),
            )
            conn.commit()

            logger.info(f"Auto-assigned task {task_id} to worker {worker['id']}")

            return {
                "success": True,
                "task_id": task_id,
                "assigned_worker": worker["id"],
                "worker_workload": worker.get("workload_score", 0),
                "strategy": strategy or DEFAULT_STRATEGY,
            }

    def assign_all_pending(
        self, strategy: str = None, limit: int = 100, task_types: List[str] = None
    ) -> Dict:
        """Auto-assign all unassigned pending tasks.

        Args:
            strategy: Assignment strategy to use
            limit: Maximum tasks to assign in one call
            task_types: Optional filter for task types

        Returns:
            Dict with assignment results
        """
        with self._get_connection() as conn:
            # Get unassigned pending tasks
            query = """
                SELECT * FROM task_queue
                WHERE status = 'pending'
                AND (assigned_worker IS NULL OR assigned_worker = '')
            """
            params = []

            if task_types:
                placeholders = ",".join("?" * len(task_types))
                query += f" AND task_type IN ({placeholders})"
                params.extend(task_types)

            query += " ORDER BY priority DESC, created_at ASC LIMIT ?"
            params.append(limit)

            tasks = conn.execute(query, params).fetchall()

            results = {
                "success": True,
                "total_tasks": len(tasks),
                "assigned": 0,
                "failed": 0,
                "assignments": [],
                "errors": [],
            }

            for task in tasks:
                task_dict = dict(task)
                worker = self.select_worker(task_dict, strategy, conn)

                if worker:
                    conn.execute(
                        """
                        UPDATE task_queue
                        SET assigned_worker = ?, assigned_node = ?
                        WHERE id = ?
                    """,
                        (worker["id"], worker.get("node_id"), task_dict["id"]),
                    )

                    results["assigned"] += 1
                    results["assignments"].append(
                        {
                            "task_id": task_dict["id"],
                            "worker_id": worker["id"],
                            "task_type": task_dict["task_type"],
                        }
                    )
                else:
                    results["failed"] += 1
                    results["errors"].append(
                        {"task_id": task_dict["id"], "error": "No available worker"}
                    )

            conn.commit()

            logger.info(f"Auto-assigned {results['assigned']}/{results['total_tasks']} tasks")

            return results

    def get_assignment_preview(self, strategy: str = None, limit: int = 20) -> Dict:
        """Preview what would happen if auto-assign was run.

        Returns:
            Dict with preview information
        """
        with self._get_connection() as conn:
            # Get unassigned tasks
            tasks = conn.execute(
                """
                SELECT * FROM task_queue
                WHERE status = 'pending'
                AND (assigned_worker IS NULL OR assigned_worker = '')
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            """,
                (limit,),
            ).fetchall()

            # Get available workers
            workers = self.get_available_workers(conn)

            preview = {
                "unassigned_tasks": len(tasks),
                "available_workers": len(workers),
                "suggested_assignments": [],
                "workers": [
                    {
                        "id": w["id"],
                        "current_load": w["task_count"],
                        "workload_score": w["workload_score"],
                        "capacity_remaining": w["capacity_remaining"],
                    }
                    for w in workers
                ],
            }

            # Simulate assignments
            worker_loads = {w["id"]: w["workload_score"] for w in workers}

            for task in tasks:
                task_dict = dict(task)
                worker = self.select_worker(task_dict, strategy, conn)

                if worker:
                    preview["suggested_assignments"].append(
                        {
                            "task_id": task_dict["id"],
                            "task_type": task_dict["task_type"],
                            "priority": task_dict["priority"],
                            "suggested_worker": worker["id"],
                            "worker_current_load": worker_loads.get(worker["id"], 0),
                        }
                    )
                    # Simulate load increase
                    worker_loads[worker["id"]] = worker_loads.get(worker["id"], 0) + 1

            preview["would_assign"] = len(preview["suggested_assignments"])

            return preview

    def get_workload_summary(self) -> Dict:
        """Get summary of current workload distribution.

        Returns:
            Dict with workload statistics
        """
        with self._get_connection() as conn:
            workers = self.get_available_workers(conn)

            if not workers:
                return {
                    "total_workers": 0,
                    "total_capacity": 0,
                    "total_load": 0,
                    "utilization_percent": 0,
                    "workers": [],
                }

            total_capacity = len(workers) * MAX_CONCURRENT_TASKS
            total_load = sum(w["task_count"] for w in workers)

            # Get unassigned tasks
            unassigned = conn.execute(
                """
                SELECT COUNT(*) as count FROM task_queue
                WHERE status = 'pending'
                AND (assigned_worker IS NULL OR assigned_worker = '')
            """
            ).fetchone()["count"]

            return {
                "total_workers": len(workers),
                "total_capacity": total_capacity,
                "total_load": total_load,
                "unassigned_tasks": unassigned,
                "utilization_percent": round((total_load / total_capacity) * 100, 1)
                if total_capacity > 0
                else 0,
                "average_load": round(total_load / len(workers), 2) if workers else 0,
                "max_concurrent_tasks": MAX_CONCURRENT_TASKS,
                "workers": [
                    {
                        "id": w["id"],
                        "status": w["status"],
                        "task_count": w["task_count"],
                        "workload_score": w["workload_score"],
                        "capacity_remaining": w["capacity_remaining"],
                        "utilization_percent": round(
                            (w["task_count"] / MAX_CONCURRENT_TASKS) * 100, 1
                        ),
                    }
                    for w in workers
                ],
            }


# Singleton getter
_service_instance = None
_service_lock = threading.Lock()


def get_auto_assign_service(db_path: str = None) -> AutoAssignService:
    global _service_instance
    if _service_instance is None or db_path:
        with _service_lock:
            if _service_instance is None or db_path:
                _service_instance = AutoAssignService(db_path)
    return _service_instance
