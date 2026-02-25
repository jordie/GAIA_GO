"""
Bulk Task Operations API
Provides endpoints for bulk operations on task queue items.
"""

import json
import logging

from flask import Blueprint, jsonify, request, session

# Import from parent - these will be available when imported into app.py
# We'll use dependency injection pattern

logger = logging.getLogger(__name__)

bulk_tasks_bp = Blueprint("bulk_tasks", __name__, url_prefix="/api/tasks/bulk")


def init_bulk_tasks(
    get_db_connection,
    log_activity,
    broadcast_queue,
    broadcast_stats,
    api_error,
    require_auth,
    rate_limit,
):
    """Initialize bulk tasks blueprint with dependencies."""

    @bulk_tasks_bp.route("/create", methods=["POST"])
    @require_auth
    @rate_limit(requests_per_minute=10)
    def bulk_create_tasks():
        """Create multiple tasks in a single request.

        Request body:
            tasks: Array of task objects, each with:
                - task_type: Required task type
                - task_data: Optional task data dict
                - priority: Optional priority (default 0)
                - max_retries: Optional max retries (default 3)

        Returns:
            created: Array of created task IDs
            failed: Array of failed task indices with errors
            total_created: Count of successfully created tasks
        """
        data = request.get_json() or {}
        tasks = data.get("tasks", [])

        if not tasks:
            return api_error("No tasks provided", 400, "validation_error")

        if not isinstance(tasks, list):
            return api_error("tasks must be an array", 400, "validation_error")

        if len(tasks) > 100:
            return api_error("Maximum 100 tasks per bulk operation", 400, "validation_error")

        created = []
        failed = []

        with get_db_connection() as conn:
            for idx, task in enumerate(tasks):
                task_type = task.get("task_type")
                if not task_type:
                    failed.append({"index": idx, "error": "task_type is required"})
                    continue

                try:
                    cursor = conn.execute(
                        """
                        INSERT INTO task_queue (task_type, task_data, priority, max_retries)
                        VALUES (?, ?, ?, ?)
                    """,
                        (
                            task_type,
                            json.dumps(task.get("task_data", {})),
                            task.get("priority", 0),
                            task.get("max_retries", 3),
                        ),
                    )
                    created.append({"index": idx, "id": cursor.lastrowid, "task_type": task_type})
                except Exception as e:
                    failed.append({"index": idx, "error": str(e)})

        if created:
            log_activity("bulk_create_tasks", "task", None, f"Created {len(created)} tasks")
            broadcast_queue()

        return jsonify(
            {
                "success": True,
                "created": created,
                "failed": failed,
                "total_created": len(created),
                "total_failed": len(failed),
            }
        )

    @bulk_tasks_bp.route("/update-status", methods=["POST"])
    @require_auth
    def bulk_update_task_status():
        """Update status of multiple tasks.

        Request body:
            task_ids: Array of task IDs to update
            status: New status (pending, completed, failed, cancelled)
            error_message: Optional error message (for failed status)

        Returns:
            updated: Count of updated tasks
            failed: Array of task IDs that failed to update
        """
        data = request.get_json() or {}
        task_ids = data.get("task_ids", [])
        new_status = data.get("status")
        error_message = data.get("error_message")

        if not task_ids:
            return api_error("No task_ids provided", 400, "validation_error")

        if not isinstance(task_ids, list):
            return api_error("task_ids must be an array", 400, "validation_error")

        if len(task_ids) > 100:
            return api_error("Maximum 100 tasks per bulk operation", 400, "validation_error")

        valid_statuses = ["pending", "completed", "failed", "cancelled"]
        if new_status not in valid_statuses:
            return api_error(
                f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
                400,
                "validation_error",
            )

        updated = 0
        failed_ids = []

        with get_db_connection() as conn:
            for task_id in task_ids:
                try:
                    if new_status == "completed":
                        conn.execute(
                            """
                            UPDATE task_queue SET
                                status = 'completed',
                                completed_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """,
                            (task_id,),
                        )
                    elif new_status == "failed":
                        conn.execute(
                            """
                            UPDATE task_queue SET
                                status = 'failed',
                                error_message = ?
                            WHERE id = ?
                        """,
                            (error_message or "Bulk marked as failed", task_id),
                        )
                    elif new_status == "cancelled":
                        conn.execute(
                            """
                            UPDATE task_queue SET
                                status = 'cancelled',
                                error_message = 'Cancelled via bulk operation'
                            WHERE id = ? AND status IN ('pending', 'running')
                        """,
                            (task_id,),
                        )
                    else:  # pending
                        conn.execute(
                            """
                            UPDATE task_queue SET
                                status = 'pending',
                                assigned_worker = NULL,
                                started_at = NULL
                            WHERE id = ?
                        """,
                            (task_id,),
                        )

                    if conn.total_changes > 0:
                        updated += 1
                    else:
                        failed_ids.append(task_id)
                except Exception as e:
                    logger.error(f"Error updating task {task_id}: {e}")
                    failed_ids.append(task_id)

        if updated > 0:
            log_activity(
                "bulk_update_tasks", "task", None, f"Updated {updated} tasks to {new_status}"
            )
            broadcast_queue()
            broadcast_stats()

        return jsonify(
            {"success": True, "updated": updated, "failed": failed_ids, "new_status": new_status}
        )

    @bulk_tasks_bp.route("/delete", methods=["POST"])
    @require_auth
    def bulk_delete_tasks():
        """Delete multiple tasks.

        Request body:
            task_ids: Array of task IDs to delete
            force: If true, delete even running tasks (default false)

        Returns:
            deleted: Count of deleted tasks
            failed: Array of task IDs that failed to delete
        """
        data = request.get_json() or {}
        task_ids = data.get("task_ids", [])
        force = data.get("force", False)

        if not task_ids:
            return api_error("No task_ids provided", 400, "validation_error")

        if not isinstance(task_ids, list):
            return api_error("task_ids must be an array", 400, "validation_error")

        if len(task_ids) > 100:
            return api_error("Maximum 100 tasks per bulk operation", 400, "validation_error")

        deleted = 0
        failed_ids = []

        with get_db_connection() as conn:
            for task_id in task_ids:
                try:
                    if force:
                        conn.execute("DELETE FROM task_queue WHERE id = ?", (task_id,))
                    else:
                        conn.execute(
                            """
                            DELETE FROM task_queue
                            WHERE id = ? AND status != 'running'
                        """,
                            (task_id,),
                        )

                    if conn.total_changes > 0:
                        deleted += 1
                    else:
                        failed_ids.append(task_id)
                except Exception as e:
                    logger.error(f"Error deleting task {task_id}: {e}")
                    failed_ids.append(task_id)

        if deleted > 0:
            log_activity("bulk_delete_tasks", "task", None, f"Deleted {deleted} tasks")
            broadcast_queue()
            broadcast_stats()

        return jsonify({"success": True, "deleted": deleted, "failed": failed_ids})

    @bulk_tasks_bp.route("/retry", methods=["POST"])
    @require_auth
    def bulk_retry_tasks():
        """Retry multiple failed tasks.

        Request body:
            task_ids: Array of task IDs to retry (optional - if not provided, retries all failed)
            reset_retries: If true, reset retry count to 0 (default true)

        Returns:
            retried: Count of tasks queued for retry
            failed: Array of task IDs that couldn't be retried
        """
        data = request.get_json() or {}
        task_ids = data.get("task_ids")
        reset_retries = data.get("reset_retries", True)

        retried = 0
        failed_ids = []

        with get_db_connection() as conn:
            if task_ids:
                if not isinstance(task_ids, list):
                    return api_error("task_ids must be an array", 400, "validation_error")

                if len(task_ids) > 100:
                    return api_error(
                        "Maximum 100 tasks per bulk operation", 400, "validation_error"
                    )

                for task_id in task_ids:
                    try:
                        if reset_retries:
                            conn.execute(
                                """
                                UPDATE task_queue SET
                                    status = 'pending',
                                    retries = 0,
                                    assigned_worker = NULL,
                                    started_at = NULL,
                                    error_message = NULL
                                WHERE id = ? AND status IN ('failed', 'cancelled')
                            """,
                                (task_id,),
                            )
                        else:
                            conn.execute(
                                """
                                UPDATE task_queue SET
                                    status = 'pending',
                                    assigned_worker = NULL,
                                    started_at = NULL
                                WHERE id = ? AND status IN ('failed', 'cancelled') AND retries < max_retries
                            """,
                                (task_id,),
                            )

                        if conn.total_changes > 0:
                            retried += 1
                        else:
                            failed_ids.append(task_id)
                    except Exception as e:
                        logger.error(f"Error retrying task {task_id}: {e}")
                        failed_ids.append(task_id)
            else:
                if reset_retries:
                    cursor = conn.execute(
                        """
                        UPDATE task_queue SET
                            status = 'pending',
                            retries = 0,
                            assigned_worker = NULL,
                            started_at = NULL,
                            error_message = NULL
                        WHERE status IN ('failed', 'cancelled')
                    """
                    )
                else:
                    cursor = conn.execute(
                        """
                        UPDATE task_queue SET
                            status = 'pending',
                            assigned_worker = NULL,
                            started_at = NULL
                        WHERE status IN ('failed', 'cancelled') AND retries < max_retries
                    """
                    )
                retried = cursor.rowcount

        if retried > 0:
            log_activity("bulk_retry_tasks", "task", None, f"Retried {retried} tasks")
            broadcast_queue()
            broadcast_stats()

        return jsonify(
            {"success": True, "retried": retried, "failed": failed_ids if task_ids else []}
        )

    @bulk_tasks_bp.route("/cancel", methods=["POST"])
    @require_auth
    def bulk_cancel_tasks():
        """Cancel multiple pending or running tasks.

        Request body:
            task_ids: Array of task IDs to cancel (optional - if not provided, cancels all pending)
            include_running: If true, also cancel running tasks (default false)

        Returns:
            cancelled: Count of cancelled tasks
            failed: Array of task IDs that couldn't be cancelled
        """
        data = request.get_json() or {}
        task_ids = data.get("task_ids")
        include_running = data.get("include_running", False)

        cancelled = 0
        failed_ids = []

        statuses = "('pending')" if not include_running else "('pending', 'running')"

        with get_db_connection() as conn:
            if task_ids:
                if not isinstance(task_ids, list):
                    return api_error("task_ids must be an array", 400, "validation_error")

                if len(task_ids) > 100:
                    return api_error(
                        "Maximum 100 tasks per bulk operation", 400, "validation_error"
                    )

                for task_id in task_ids:
                    try:
                        conn.execute(
                            f"""
                            UPDATE task_queue SET
                                status = 'cancelled',
                                error_message = 'Cancelled via bulk operation'
                            WHERE id = ? AND status IN {statuses}
                        """,
                            (task_id,),
                        )

                        if conn.total_changes > 0:
                            cancelled += 1
                        else:
                            failed_ids.append(task_id)
                    except Exception as e:
                        logger.error(f"Error cancelling task {task_id}: {e}")
                        failed_ids.append(task_id)
            else:
                cursor = conn.execute(
                    f"""
                    UPDATE task_queue SET
                        status = 'cancelled',
                        error_message = 'Cancelled via bulk operation'
                    WHERE status IN {statuses}
                """
                )
                cancelled = cursor.rowcount

        if cancelled > 0:
            log_activity("bulk_cancel_tasks", "task", None, f"Cancelled {cancelled} tasks")
            broadcast_queue()
            broadcast_stats()

        return jsonify(
            {"success": True, "cancelled": cancelled, "failed": failed_ids if task_ids else []}
        )

    @bulk_tasks_bp.route("/prioritize", methods=["POST"])
    @require_auth
    def bulk_prioritize_tasks():
        """Update priority of multiple tasks.

        Request body:
            task_ids: Array of task IDs to update
            priority: New priority value (0-10, higher = more urgent)
            increment: If true, add priority to current value instead of replacing

        Returns:
            updated: Count of updated tasks
            failed: Array of task IDs that failed to update
        """
        data = request.get_json() or {}
        task_ids = data.get("task_ids", [])
        priority = data.get("priority")
        increment = data.get("increment", False)

        if not task_ids:
            return api_error("No task_ids provided", 400, "validation_error")

        if priority is None:
            return api_error("priority is required", 400, "validation_error")

        if not isinstance(task_ids, list):
            return api_error("task_ids must be an array", 400, "validation_error")

        if len(task_ids) > 100:
            return api_error("Maximum 100 tasks per bulk operation", 400, "validation_error")

        try:
            priority = int(priority)
        except (ValueError, TypeError):
            return api_error("priority must be a number", 400, "validation_error")

        updated = 0
        failed_ids = []

        with get_db_connection() as conn:
            for task_id in task_ids:
                try:
                    if increment:
                        conn.execute(
                            """
                            UPDATE task_queue SET
                                priority = MIN(10, MAX(0, priority + ?))
                            WHERE id = ? AND status = 'pending'
                        """,
                            (priority, task_id),
                        )
                    else:
                        conn.execute(
                            """
                            UPDATE task_queue SET
                                priority = MIN(10, MAX(0, ?))
                            WHERE id = ? AND status = 'pending'
                        """,
                            (priority, task_id),
                        )

                    if conn.total_changes > 0:
                        updated += 1
                    else:
                        failed_ids.append(task_id)
                except Exception as e:
                    logger.error(f"Error updating priority for task {task_id}: {e}")
                    failed_ids.append(task_id)

        if updated > 0:
            log_activity(
                "bulk_prioritize_tasks", "task", None, f"Updated priority for {updated} tasks"
            )
            broadcast_queue()

        return jsonify(
            {
                "success": True,
                "updated": updated,
                "failed": failed_ids,
                "new_priority": priority if not increment else f"+{priority}",
            }
        )

    return bulk_tasks_bp
