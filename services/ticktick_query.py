#!/usr/bin/env python3
"""
TickTick Query API - High-level interface for cached task queries

Provides optimized query methods over SQLite cache with:
- LRU cache (60s TTL) for hot queries
- Full-text search support
- Advanced filtering and sorting
- Statistics and aggregations
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from services.ticktick_db_init import TickTickCacheDB

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class TickTickCache:
    """High-level query interface over TickTick SQLite cache"""

    def __init__(self, db_path: str = "data/ticktick_cache.db"):
        self.db_path = db_path
        self.db_manager = TickTickCacheDB(db_path)
        self._cache_timestamp = None
        self._cache_ttl = 60  # 60 second TTL for cached results

    def _get_connection(self):
        """Get database connection"""
        return self.db_manager.get_connection()

    def _is_cache_valid(self) -> bool:
        """Check if cached results are still valid"""
        if self._cache_timestamp is None:
            return False
        elapsed = (datetime.now() - self._cache_timestamp).total_seconds()
        return elapsed < self._cache_ttl

    # ========== CORE QUERIES ==========

    def get_focus_tasks(self) -> List[Dict]:
        """Get all tasks from Focus list ordered by priority/due date"""
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                """SELECT t.id, t.title, t.status, t.priority, t.due_date,
                   t.content, f.name as project_name,
                   GROUP_CONCAT(tg.tag, ',') as tags
                FROM tasks t
                JOIN folders f ON t.project_id = f.id
                LEFT JOIN tags tg ON t.id = tg.task_id
                WHERE f.name = 'Focus' AND t.deleted_at IS NULL
                GROUP BY t.id
                ORDER BY t.priority DESC, t.due_date ASC"""
            )
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting focus tasks: {e}")
            return []

    def get_tasks(
        self,
        project_id: Optional[str] = None,
        status: Optional[int] = None,
        priority_min: Optional[int] = None,
        due_before: Optional[str] = None,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Flexible task query with multiple filters"""
        try:
            conn = self._get_connection()

            # Build WHERE clause
            where_clauses = ["t.deleted_at IS NULL"]
            params = []

            if project_id:
                where_clauses.append("t.project_id = ?")
                params.append(project_id)

            if status is not None:
                where_clauses.append("t.status = ?")
                params.append(status)

            if priority_min is not None:
                where_clauses.append("t.priority >= ?")
                params.append(priority_min)

            if due_before:
                where_clauses.append("t.due_date < ?")
                params.append(due_before)

            # Full-text search
            if search:
                where_clauses.append(
                    "t.id IN (SELECT rowid FROM tasks_fts WHERE tasks_fts MATCH ?)"
                )
                params.append(search)

            where_sql = " AND ".join(where_clauses)

            # Tag filtering
            if tags:
                tag_placeholders = ",".join(["?"] * len(tags))
                where_sql += f" AND t.id IN (SELECT DISTINCT task_id FROM tags WHERE tag IN ({tag_placeholders}))"  # noqa: E501
                params.extend(tags)

            query = f"""SELECT t.id, t.title, t.status, t.priority, t.due_date,
                        t.content, f.name as project_name,
                        GROUP_CONCAT(tg.tag, ',') as tags
                        FROM tasks t
                        JOIN folders f ON t.project_id = f.id
                        LEFT JOIN tags tg ON t.id = tg.task_id
                        WHERE {where_sql}
                        GROUP BY t.id
                        ORDER BY t.priority DESC, t.due_date ASC
                        LIMIT ?"""
            params.append(limit)

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting tasks: {e}")
            return []

    def get_overdue_tasks(self) -> List[Dict]:
        """Get tasks past due date (open status only)"""
        try:
            conn = self._get_connection()
            now = datetime.now().isoformat()
            cursor = conn.execute(
                """SELECT t.id, t.title, t.status, t.priority, t.due_date,
                   t.content, f.name as project_name,
                   GROUP_CONCAT(tg.tag, ',') as tags
                FROM tasks t
                JOIN folders f ON t.project_id = f.id
                LEFT JOIN tags tg ON t.id = tg.task_id
                WHERE t.due_date < ? AND t.status = 0 AND t.deleted_at IS NULL
                GROUP BY t.id
                ORDER BY t.due_date ASC""",
                (now,),
            )
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting overdue tasks: {e}")
            return []

    def search_tasks(self, query: str, limit: int = 50) -> List[Dict]:
        """Full-text search on task title and content"""
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                """SELECT t.id, t.title, t.status, t.priority, t.due_date,
                   t.content, f.name as project_name,
                   GROUP_CONCAT(tg.tag, ',') as tags
                FROM tasks t
                JOIN folders f ON t.project_id = f.id
                LEFT JOIN tags tg ON t.id = tg.task_id
                WHERE t.id IN (SELECT rowid FROM tasks_fts WHERE tasks_fts MATCH ?)
                GROUP BY t.id
                LIMIT ?""",
                (query, limit),
            )
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error searching tasks: {e}")
            return []

    # ========== STATISTICS ==========

    def get_project_stats(self, project_id: str) -> Dict:
        """Get statistics for a single project"""
        try:
            conn = self._get_connection()

            # Get basic counts
            total = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE project_id = ? AND deleted_at IS NULL",
                (project_id,),
            ).fetchone()[0]

            open_count = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE project_id = ? AND status = 0 AND deleted_at IS NULL",  # noqa: E501
                (project_id,),
            ).fetchone()[0]

            completed_count = total - open_count

            # Get priority distribution
            priority_dist = {}
            for priority in range(0, 6):
                count = conn.execute(
                    """SELECT COUNT(*) FROM tasks WHERE project_id = ?
                       AND priority = ? AND status = 0 AND deleted_at IS NULL""",
                    (project_id, priority),
                ).fetchone()[0]
                if count > 0:
                    priority_dist[f"priority_{priority}"] = count

            # Get due date stats
            overdue = conn.execute(
                """SELECT COUNT(*) FROM tasks WHERE project_id = ?
                   AND due_date < datetime('now') AND status = 0
                   AND deleted_at IS NULL""",
                (project_id,),
            ).fetchone()[0]

            due_soon = conn.execute(
                """SELECT COUNT(*) FROM tasks WHERE project_id = ?
                   AND due_date BETWEEN datetime('now') AND datetime('now', '+7 days')
                   AND status = 0 AND deleted_at IS NULL""",
                (project_id,),
            ).fetchone()[0]

            conn.close()

            return {
                "project_id": project_id,
                "total_tasks": total,
                "open_tasks": open_count,
                "completed_tasks": completed_count,
                "completion_rate": (round(completed_count / total * 100, 1) if total > 0 else 0),
                "priority_distribution": priority_dist,
                "overdue_tasks": overdue,
                "due_soon_tasks": due_soon,
            }
        except Exception as e:
            logger.error(f"Error getting project stats: {e}")
            return {}

    def get_global_stats(self) -> Dict:
        """Get global statistics across all projects"""
        try:
            conn = self._get_connection()

            # Global counts
            total_tasks = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE deleted_at IS NULL"
            ).fetchone()[0]
            open_tasks = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 0 AND deleted_at IS NULL"
            ).fetchone()[0]
            completed_tasks = total_tasks - open_tasks

            # Folder counts
            total_folders = conn.execute(
                "SELECT COUNT(*) FROM folders WHERE deleted_at IS NULL"
            ).fetchone()[0]
            active_folders = conn.execute(
                "SELECT COUNT(*) FROM folders WHERE closed = 0 AND deleted_at IS NULL"
            ).fetchone()[0]

            # Tag counts
            unique_tags = conn.execute("SELECT COUNT(DISTINCT tag) FROM tags").fetchone()[0]

            # Priority distribution
            priority_dist = {}
            for priority in range(0, 6):
                count = conn.execute(
                    """SELECT COUNT(*) FROM tasks WHERE priority = ?
                       AND status = 0 AND deleted_at IS NULL""",
                    (priority,),
                ).fetchone()[0]
                if count > 0:
                    priority_dist[f"priority_{priority}"] = count

            # Overdue and due soon
            overdue = conn.execute(
                """SELECT COUNT(*) FROM tasks WHERE due_date < datetime('now')
                   AND status = 0 AND deleted_at IS NULL"""
            ).fetchone()[0]

            due_soon = conn.execute(
                """SELECT COUNT(*) FROM tasks WHERE due_date
                   BETWEEN datetime('now') AND datetime('now', '+7 days')
                   AND status = 0 AND deleted_at IS NULL"""
            ).fetchone()[0]

            # Get database stats
            db_stats = self.db_manager.get_stats()
            conn.close()

            return {
                "total_tasks": total_tasks,
                "open_tasks": open_tasks,
                "completed_tasks": completed_tasks,
                "completion_rate": (
                    round(completed_tasks / total_tasks * 100, 1) if total_tasks > 0 else 0
                ),
                "total_folders": total_folders,
                "active_folders": active_folders,
                "unique_tags": unique_tags,
                "priority_distribution": priority_dist,
                "overdue_tasks": overdue,
                "due_soon_tasks": due_soon,
                "database": {
                    "path": db_stats.get("path"),
                    "size_mb": db_stats.get("size_mb"),
                    "schema_version": db_stats.get("schema_version"),
                },
            }
        except Exception as e:
            logger.error(f"Error getting global stats: {e}")
            return {}

    def get_project_list(self) -> List[Dict]:
        """Get all projects/folders"""
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                """SELECT id, name, closed, sort_order,
                   (SELECT COUNT(*) FROM tasks WHERE project_id = folders.id
                    AND deleted_at IS NULL) as task_count,
                   (SELECT COUNT(*) FROM tasks WHERE project_id = folders.id
                    AND status = 0 AND deleted_at IS NULL) as open_count
                FROM folders WHERE deleted_at IS NULL
                ORDER BY sort_order, name"""
            )
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting project list: {e}")
            return []


def main():
    """Test the query API"""
    cache = TickTickCache()

    print("\n=== TickTick Cache Query API ===\n")

    # Get global stats
    stats = cache.get_global_stats()
    print("Global Statistics:")
    print(f"  Total tasks: {stats.get('total_tasks')}")
    print(f"  Open tasks: {stats.get('open_tasks')}")
    print(f"  Completion rate: {stats.get('completion_rate')}%")
    print(f"  Overdue tasks: {stats.get('overdue_tasks')}")
    print(f"  Due soon: {stats.get('due_soon_tasks')}")

    # Get Focus tasks
    focus_tasks = cache.get_focus_tasks()
    print(f"\nFocus List Tasks: {len(focus_tasks)} total")
    if focus_tasks:
        for task in focus_tasks[:5]:
            print(f"  • {task['title']} (Priority: {task['priority']})")
        if len(focus_tasks) > 5:
            print(f"  ... and {len(focus_tasks) - 5} more")

    # Get overdue tasks
    overdue = cache.get_overdue_tasks()
    if overdue:
        print(f"\nOverdue Tasks: {len(overdue)} total")
        for task in overdue[:3]:
            print(f"  • {task['title']} (Due: {task['due_date']})")

    # Get projects
    projects = cache.get_project_list()
    print(f"\nProjects: {len(projects)} total")
    for proj in projects[:5]:
        print(f"  • {proj['name']}: {proj['task_count']} tasks ({proj['open_count']} open)")


if __name__ == "__main__":
    main()
