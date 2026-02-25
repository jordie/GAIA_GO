"""
Browser Automation Task Management API

Provides REST endpoints for:
- Task submission and management
- Execution log tracking
- Metrics and analytics
- Queue management
"""

import logging
import uuid
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

browser_api = Blueprint("browser_automation", __name__, url_prefix="/api/browser-tasks")


# Error responses
def error_response(message, status_code=400):
    """Return standardized error response"""
    return jsonify({"error": message, "success": False}), status_code


def success_response(data, status_code=200):
    """Return standardized success response"""
    return jsonify({"data": data, "success": True}), status_code


# Authentication decorator (placeholder - implement with your auth)
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # TODO: Implement authentication check
        # if not has_auth():
        #     return error_response('Unauthorized', 401)
        return f(*args, **kwargs)

    return decorated_function


# ============================================================================
# TASK SUBMISSION & MANAGEMENT
# ============================================================================


@browser_api.route("", methods=["POST"])
@require_auth
def submit_task():
    """
    Submit new browser automation task

    POST /api/browser-tasks
    {
        "goal": "Register for swimming classes",
        "site_url": "https://aquatechswim.com",
        "priority": 5,
        "timeout_minutes": 30,
        "metadata": { "user_id": "123", "session_id": "abc" }
    }

    Returns:
    {
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "pending",
        "queued_at": "2026-02-17T12:30:00Z",
        "priority": 5
    }
    """
    try:
        from db_orm import db_session
        from models.browser_automation import BrowserTask, BrowserTaskStatus

        data = request.get_json()

        # Validate required fields
        if not data.get("goal"):
            return error_response("Missing required field: goal")
        if not data.get("site_url"):
            return error_response("Missing required field: site_url")

        # Create BrowserTask in database
        task_id = str(uuid.uuid4())
        priority = data.get("priority", 5)
        timeout_minutes = data.get("timeout_minutes", 30)
        metadata = data.get("metadata", {})

        task = BrowserTask(
            id=task_id,
            goal=data.get("goal"),
            site_url=data.get("site_url"),
            status=BrowserTaskStatus.PENDING,
            priority=priority,
            timeout_minutes=timeout_minutes,
            metadata=metadata,
            created_at=datetime.utcnow(),
        )

        db_session.add(task)
        db_session.commit()

        response = {
            "task_id": task.id,
            "status": task.status.value,
            "queued_at": task.created_at.isoformat() + "Z",
            "priority": priority,
            "timeout_minutes": timeout_minutes,
        }

        return success_response(response, 201)

    except Exception as e:
        logger.error(f"Error submitting task: {e}")
        try:
            db_session.rollback()
        except Exception:
            pass
        return error_response(str(e), 500)


@browser_api.route("", methods=["GET"])
@require_auth
def list_tasks():
    """
    List all tasks with optional filtering

    GET /api/browser-tasks?status=pending&site_url=aquatechswim.com&created_after=2026-02-17T00:00:00Z

    Query Parameters:
    - status: pending, in_progress, completed, failed, paused, recovered
    - site_url: Filter by site URL
    - created_after: ISO timestamp
    - created_before: ISO timestamp
    - limit: Max results (default 100)
    - offset: Pagination offset (default 0)

    Returns:
    {
        "tasks": [
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "goal": "Register for swimming",
                "site_url": "https://aquatechswim.com",
                "status": "pending",
                "progress": 0,
                "cost": 0.0,
                "cache_hit": false,
                "created_at": "2026-02-17T12:30:00Z"
            }
        ],
        "total": 42,
        "limit": 100,
        "offset": 0
    }
    """
    try:
        from db_orm import db_session
        from models.browser_automation import BrowserTask, BrowserTaskStatus

        status = request.args.get("status")
        site_url = request.args.get("site_url")
        created_after = request.args.get("created_after")
        created_before = request.args.get("created_before")
        limit = min(int(request.args.get("limit", 100)), 1000)
        offset = int(request.args.get("offset", 0))

        # Build query with filters
        query = db_session.query(BrowserTask)

        if status:
            try:
                task_status = BrowserTaskStatus[status.upper()]
                query = query.filter(BrowserTask.status == task_status)
            except KeyError:
                return error_response(f"Invalid status: {status}", 400)

        if site_url:
            query = query.filter(BrowserTask.site_url.ilike(f"%{site_url}%"))

        if created_after:
            iso_str = created_after.replace("Z", "+00:00")
            created_after_dt = datetime.fromisoformat(iso_str)
            query = query.filter(BrowserTask.created_at >= created_after_dt)

        if created_before:
            created_before_dt = datetime.fromisoformat(created_before.replace("Z", "+00:00"))
            query = query.filter(BrowserTask.created_at <= created_before_dt)

        # Get total count before pagination
        total = query.count()

        # Apply pagination
        tasks = query.order_by(BrowserTask.created_at.desc()).offset(offset).limit(limit).all()

        # Format response
        tasks_data = []
        for task in tasks:
            progress = 0
            if task.total_steps > 0:
                progress = int((task.total_steps / (task.total_steps + 1)) * 100)

            created_str = task.created_at.isoformat() + "Z" if task.created_at else None
            tasks_data.append(
                {
                    "id": task.id,
                    "goal": task.goal,
                    "site_url": task.site_url,
                    "status": task.status.value,
                    "progress": progress,
                    "cost": float(task.total_cost),
                    "cache_hit": task.cached_path_used,
                    "created_at": created_str,
                }
            )

        response = {
            "tasks": tasks_data,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

        return success_response(response)

    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        return error_response(str(e), 500)


@browser_api.route("/<task_id>", methods=["GET"])
@require_auth
def get_task(task_id):
    """
    Get detailed task information

    GET /api/browser-tasks/550e8400-e29b-41d4-a716-446655440000

    Returns:
    {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "goal": "Register for swimming",
        "site_url": "https://aquatechswim.com",
        "status": "in_progress",
        "created_at": "2026-02-17T12:30:00Z",
        "started_at": "2026-02-17T12:31:00Z",
        "completed_at": null,
        "total_steps": 5,
        "total_time_seconds": 45.5,
        "total_cost": 0.02,
        "cached_path_used": false,
        "cache_time_saved_seconds": 0,
        "final_result": null,
        "error_message": null,
        "recovery_attempts": 0,
        "recovery_succeeded": false
    }
    """
    try:
        from db_orm import db_session
        from models.browser_automation import BrowserTask

        task = db_session.query(BrowserTask).filter(BrowserTask.id == task_id).first()

        if not task:
            return error_response("Task not found", 404)

        response = {
            "id": task.id,
            "goal": task.goal,
            "site_url": task.site_url,
            "status": task.status.value,
            "created_at": task.created_at.isoformat() + "Z" if task.created_at else None,
            "started_at": task.started_at.isoformat() + "Z" if task.started_at else None,
            "completed_at": task.completed_at.isoformat() + "Z" if task.completed_at else None,
            "total_steps": task.total_steps,
            "total_time_seconds": float(task.total_time_seconds),
            "total_cost": float(task.total_cost),
            "cached_path_used": task.cached_path_used,
            "cache_time_saved_seconds": float(task.cache_time_saved_seconds),
            "final_result": task.final_result,
            "error_message": task.error_message,
            "recovery_attempts": task.recovery_attempts,
            "recovery_succeeded": task.recovery_succeeded,
        }

        return success_response(response)

    except Exception as e:
        logger.error(f"Error getting task {task_id}: {e}")
        return error_response(str(e), 500)


# ============================================================================
# EXECUTION LOG TRACKING
# ============================================================================


@browser_api.route("/<task_id>/execution-log", methods=["GET"])
@require_auth
def get_execution_log(task_id):
    """
    Get detailed step-by-step execution log

    GET /api/browser-tasks/550e8400-e29b-41d4-a716-446655440000/execution-log?step_min=1&step_max=10&ai_level=2

    Query Parameters:
    - step_min: Start step number
    - step_max: End step number
    - ai_level: Filter by AI level (1=Ollama, 2=Claude, 3=Codex, 4=Gemini)
    - ai_used: Filter by AI provider
    - limit: Max results (default 100)

    Returns:
    {
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "execution_log": [
            {
                "step_number": 1,
                "action": "Navigate to login page",
                "ai_level": 1,
                "ai_used": "ollama",
                "duration_ms": 2500,
                "cost": 0.0,
                "result": "success",
                "error_details": null,
                "created_at": "2026-02-17T12:31:00Z"
            },
            {
                "step_number": 2,
                "action": "Enter email address",
                "ai_level": 1,
                "ai_used": "ollama",
                "duration_ms": 1200,
                "cost": 0.0,
                "result": "success",
                "error_details": null,
                "created_at": "2026-02-17T12:31:02Z"
            }
        ],
        "total_steps": 2
    }
    """
    try:
        from db_orm import db_session
        from models.browser_automation import BrowserExecutionLog, BrowserTask

        step_min = request.args.get("step_min", type=int)
        step_max = request.args.get("step_max", type=int)
        ai_level = request.args.get("ai_level", type=int)
        ai_used = request.args.get("ai_used")
        limit = min(int(request.args.get("limit", 100)), 1000)

        # Verify task exists
        task = db_session.query(BrowserTask).filter(BrowserTask.id == task_id).first()
        if not task:
            return error_response("Task not found", 404)

        # Build query
        query = db_session.query(BrowserExecutionLog).filter(BrowserExecutionLog.task_id == task_id)

        if step_min is not None:
            query = query.filter(BrowserExecutionLog.step_number >= step_min)

        if step_max is not None:
            query = query.filter(BrowserExecutionLog.step_number <= step_max)

        if ai_level is not None:
            query = query.filter(BrowserExecutionLog.ai_level == ai_level)

        if ai_used:
            query = query.filter(BrowserExecutionLog.ai_used.ilike(f"%{ai_used}%"))

        # Get logs sorted by step number
        logs = query.order_by(BrowserExecutionLog.step_number).limit(limit).all()

        # Format response
        log_data = []
        for log in logs:
            log_data.append(
                {
                    "step_number": log.step_number,
                    "action": log.action,
                    "ai_level": log.ai_level.value if log.ai_level else None,
                    "ai_used": log.ai_used,
                    "duration_ms": log.duration_ms,
                    "cost": float(log.cost),
                    "result": log.result,
                    "error_details": log.error_details,
                    "created_at": log.created_at.isoformat() + "Z" if log.created_at else None,
                }
            )

        response = {
            "task_id": task_id,
            "execution_log": log_data,
            "total_steps": len(log_data),
        }

        return success_response(response)

    except Exception as e:
        logger.error(f"Error getting execution log for {task_id}: {e}")
        return error_response(str(e), 500)


# ============================================================================
# ANALYTICS & METRICS
# ============================================================================


@browser_api.route("/metrics", methods=["GET"])
@require_auth
def get_metrics():
    """
    Get analytics and performance metrics

    GET /api/browser-tasks/metrics?date_from=2026-02-10&date_to=2026-02-17

    Query Parameters:
    - date_from: Start date (ISO format)
    - date_to: End date (ISO format)
    - group_by: 'day', 'week', 'month' (default 'day')

    Returns:
    {
        "summary": {
            "total_tasks_completed": 125,
            "total_tasks_failed": 8,
            "success_rate": 94.0,
            "avg_task_time_seconds": 45.2,
            "avg_task_cost": 0.015,
            "total_cost": 1.875,
            "cache_hit_rate": 72.0,
            "recovery_rate": 87.5
        },
        "metrics_by_date": [
            {
                "date": "2026-02-17",
                "completed": 12,
                "failed": 1,
                "avg_time": 42.5,
                "avg_cost": 0.014,
                "cache_hit_rate": 75.0,
                "recovery_attempts": 2,
                "recovery_success_rate": 100.0
            }
        ],
        "ai_routing_breakdown": {
            "ollama": { "count": 89, "cost": 0.0 },
            "claude": { "count": 28, "cost": 0.84 },
            "codex": { "count": 8, "cost": 0.96 }
        }
    }
    """
    try:
        from sqlalchemy import func

        from db_orm import db_session
        from models.browser_automation import BrowserTask, BrowserTaskStatus

        date_from_str = request.args.get("date_from")
        date_to_str = request.args.get("date_to")
        group_by = request.args.get("group_by", "day")

        # Parse dates
        if date_from_str:
            date_from = datetime.fromisoformat(date_from_str.replace("Z", "+00:00")).date()
        else:
            date_from = (datetime.utcnow() - timedelta(days=30)).date()

        if date_to_str:
            date_to = datetime.fromisoformat(date_to_str.replace("Z", "+00:00")).date()
        else:
            date_to = datetime.utcnow().date()

        # Query completed tasks in date range
        completed = (
            db_session.query(BrowserTask)
            .filter(
                BrowserTask.status == BrowserTaskStatus.COMPLETED,
                func.date(BrowserTask.completed_at) >= date_from,
                func.date(BrowserTask.completed_at) <= date_to,
            )
            .all()
        )

        # Query failed tasks in date range
        failed = (
            db_session.query(BrowserTask)
            .filter(
                BrowserTask.status == BrowserTaskStatus.FAILED,
                func.date(BrowserTask.completed_at) >= date_from,
                func.date(BrowserTask.completed_at) <= date_to,
            )
            .all()
        )

        # Calculate summary metrics
        total_completed = len(completed)
        total_failed = len(failed)
        total_tasks = total_completed + total_failed

        success_rate = (total_completed / total_tasks * 100) if total_tasks > 0 else 0.0

        # Calculate time and cost metrics
        avg_time = 0.0
        total_cost = 0.0
        cache_hits = 0

        for task in completed:
            if task.total_time_seconds:
                avg_time += task.total_time_seconds
            total_cost += task.total_cost
            if task.cached_path_used:
                cache_hits += 1

        avg_time = (avg_time / total_completed) if total_completed > 0 else 0.0
        avg_cost = (total_cost / total_completed) if total_completed > 0 else 0.0
        cache_hit_rate = (cache_hits / total_completed * 100) if total_completed > 0 else 0.0

        # Calculate recovery rate
        recovery_rate = 0.0
        recovery_total = 0
        for task in completed + failed:
            if task.recovery_attempts > 0:
                recovery_total += 1
                if task.recovery_succeeded:
                    recovery_rate += 1
        recovery_rate = (recovery_rate / recovery_total * 100) if recovery_total > 0 else 0.0

        # Build summary
        summary = {
            "total_tasks_completed": total_completed,
            "total_tasks_failed": total_failed,
            "success_rate": round(success_rate, 1),
            "avg_task_time_seconds": round(avg_time, 2),
            "avg_task_cost": round(avg_cost, 4),
            "total_cost": round(total_cost, 4),
            "cache_hit_rate": round(cache_hit_rate, 1),
            "recovery_rate": round(recovery_rate, 1),
        }

        # Build metrics by date
        metrics_by_date = []
        current_date = date_from
        while current_date <= date_to:
            day_completed = (
                db_session.query(func.count(BrowserTask.id))
                .filter(
                    BrowserTask.status == BrowserTaskStatus.COMPLETED,
                    func.date(BrowserTask.completed_at) == current_date,
                )
                .scalar()
                or 0
            )

            day_failed = (
                db_session.query(func.count(BrowserTask.id))
                .filter(
                    BrowserTask.status == BrowserTaskStatus.FAILED,
                    func.date(BrowserTask.completed_at) == current_date,
                )
                .scalar()
                or 0
            )

            day_tasks = (
                db_session.query(BrowserTask)
                .filter(
                    func.date(BrowserTask.completed_at) == current_date,
                    BrowserTask.status.in_([BrowserTaskStatus.COMPLETED, BrowserTaskStatus.FAILED]),
                )
                .all()
            )

            if day_tasks:
                day_avg_time = sum(t.total_time_seconds for t in day_tasks) / len(day_tasks)
                day_avg_cost = sum(t.total_cost for t in day_tasks) / len(day_tasks)
                day_cache_hits = (
                    sum(1 for t in day_tasks if t.cached_path_used) / len(day_tasks) * 100
                )
                day_recovery_attempts = sum(1 for t in day_tasks if t.recovery_attempts > 0)
                day_recovery_success = sum(
                    1 for t in day_tasks if t.recovery_attempts > 0 and t.recovery_succeeded
                )
                day_recovery_rate = (
                    (day_recovery_success / day_recovery_attempts * 100)
                    if day_recovery_attempts > 0
                    else 0.0
                )

                metrics_by_date.append(
                    {
                        "date": current_date.isoformat(),
                        "completed": day_completed,
                        "failed": day_failed,
                        "avg_time": round(day_avg_time, 2),
                        "avg_cost": round(day_avg_cost, 4),
                        "cache_hit_rate": round(day_cache_hits, 1),
                        "recovery_attempts": day_recovery_attempts,
                        "recovery_success_rate": round(day_recovery_rate, 1),
                    }
                )

            current_date += timedelta(days=1)

        # AI routing breakdown (from execution logs)
        from models.browser_automation import BrowserExecutionLog

        ai_breakdown = {}
        logs = (
            db_session.query(
                BrowserExecutionLog.ai_used,
                func.count(BrowserExecutionLog.id),
                func.sum(BrowserExecutionLog.cost),
            )
            .filter(
                func.date(BrowserExecutionLog.created_at) >= date_from,
                func.date(BrowserExecutionLog.created_at) <= date_to,
            )
            .group_by(BrowserExecutionLog.ai_used)
            .all()
        )

        for ai_provider, count, cost in logs:
            ai_breakdown[ai_provider or "unknown"] = {
                "count": count,
                "cost": round(float(cost) if cost else 0.0, 4),
            }

        response = {
            "summary": summary,
            "metrics_by_date": metrics_by_date,
            "ai_routing_breakdown": ai_breakdown,
        }

        return success_response(response)

    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return error_response(str(e), 500)


# ============================================================================
# TASK CONTROL
# ============================================================================


@browser_api.route("/<task_id>/pause", methods=["PUT"])
@require_auth
def pause_task(task_id):
    """
    Pause a running task

    PUT /api/browser-tasks/550e8400-e29b-41d4-a716-446655440000/pause

    Returns:
    {
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "paused",
        "paused_at": "2026-02-17T12:35:00Z",
        "steps_completed": 5
    }
    """
    try:
        from db_orm import db_session
        from models.browser_automation import BrowserTask, BrowserTaskStatus

        task = db_session.query(BrowserTask).filter(BrowserTask.id == task_id).first()

        if not task:
            return error_response("Task not found", 404)

        if task.status not in [BrowserTaskStatus.IN_PROGRESS, BrowserTaskStatus.PENDING]:
            return error_response(f"Cannot pause task with status: {task.status.value}", 400)

        task.status = BrowserTaskStatus.PAUSED
        db_session.commit()

        response = {
            "task_id": task.id,
            "status": task.status.value,
            "paused_at": datetime.utcnow().isoformat() + "Z",
            "steps_completed": task.total_steps,
        }

        return success_response(response)

    except Exception as e:
        logger.error(f"Error pausing task {task_id}: {e}")
        try:
            db_session.rollback()
        except Exception:
            pass
        return error_response(str(e), 500)


@browser_api.route("/<task_id>/resume", methods=["PUT"])
@require_auth
def resume_task(task_id):
    """
    Resume a paused task

    PUT /api/browser-tasks/550e8400-e29b-41d4-a716-446655440000/resume

    Returns:
    {
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "in_progress",
        "resumed_at": "2026-02-17T12:36:00Z"
    }
    """
    try:
        from db_orm import db_session
        from models.browser_automation import BrowserTask, BrowserTaskStatus

        task = db_session.query(BrowserTask).filter(BrowserTask.id == task_id).first()

        if not task:
            return error_response("Task not found", 404)

        if task.status != BrowserTaskStatus.PAUSED:
            return error_response(f"Cannot resume task with status: {task.status.value}", 400)

        task.status = BrowserTaskStatus.IN_PROGRESS
        db_session.commit()

        response = {
            "task_id": task.id,
            "status": task.status.value,
            "resumed_at": datetime.utcnow().isoformat() + "Z",
        }

        return success_response(response)

    except Exception as e:
        logger.error(f"Error resuming task {task_id}: {e}")
        try:
            db_session.rollback()
        except Exception:
            pass
        return error_response(str(e), 500)


@browser_api.route("/<task_id>", methods=["DELETE"])
@require_auth
def cancel_task(task_id):
    """
    Cancel a pending or paused task

    DELETE /api/browser-tasks/550e8400-e29b-41d4-a716-446655440000

    Returns:
    {
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "cancelled",
        "cancelled_at": "2026-02-17T12:37:00Z"
    }
    """
    try:
        from db_orm import db_session
        from models.browser_automation import BrowserTask, BrowserTaskStatus

        task = db_session.query(BrowserTask).filter(BrowserTask.id == task_id).first()

        if not task:
            return error_response("Task not found", 404)

        # Can only cancel pending or paused tasks
        if task.status not in [BrowserTaskStatus.PENDING, BrowserTaskStatus.PAUSED]:
            return error_response(f"Cannot cancel task with status: {task.status.value}", 400)

        task.status = BrowserTaskStatus.CANCELLED
        db_session.commit()

        response = {
            "task_id": task.id,
            "status": task.status.value,
            "cancelled_at": datetime.utcnow().isoformat() + "Z",
        }

        return success_response(response)

    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {e}")
        try:
            db_session.rollback()
        except Exception:
            pass
        return error_response(str(e), 500)


# ============================================================================
# QUEUE MANAGEMENT
# ============================================================================


@browser_api.route("/queue/status", methods=["GET"])
@require_auth
def get_queue_status():
    """
    Get current queue status

    GET /api/browser-tasks/queue/status

    Returns:
    {
        "queue_depth": 5,
        "pending_tasks": 3,
        "running_tasks": 2,
        "completed_today": 42,
        "failed_today": 2,
        "avg_wait_time_seconds": 15.3,
        "avg_completion_time_seconds": 45.2,
        "health": "healthy"
    }
    """
    try:
        from sqlalchemy import func

        from db_orm import db_session
        from models.browser_automation import BrowserTask, BrowserTaskStatus

        today = datetime.utcnow().date()

        # Count tasks by status
        pending = (
            db_session.query(func.count(BrowserTask.id))
            .filter(BrowserTask.status == BrowserTaskStatus.PENDING)
            .scalar()
            or 0
        )

        in_progress = (
            db_session.query(func.count(BrowserTask.id))
            .filter(BrowserTask.status == BrowserTaskStatus.IN_PROGRESS)
            .scalar()
            or 0
        )

        # Count completed/failed today
        completed_today = (
            db_session.query(func.count(BrowserTask.id))
            .filter(
                BrowserTask.status == BrowserTaskStatus.COMPLETED,
                func.date(BrowserTask.completed_at) == today,
            )
            .scalar()
            or 0
        )

        failed_today = (
            db_session.query(func.count(BrowserTask.id))
            .filter(
                BrowserTask.status == BrowserTaskStatus.FAILED,
                func.date(BrowserTask.completed_at) == today,
            )
            .scalar()
            or 0
        )

        # Calculate average times
        completed_tasks = (
            db_session.query(BrowserTask)
            .filter(
                BrowserTask.status == BrowserTaskStatus.COMPLETED,
                func.date(BrowserTask.completed_at) == today,
            )
            .all()
        )

        avg_wait_time = 0.0
        avg_completion_time = 0.0

        if completed_tasks:
            total_wait = 0
            total_completion = 0
            for task in completed_tasks:
                if task.started_at and task.created_at:
                    wait_delta = (task.started_at - task.created_at).total_seconds()
                    total_wait += wait_delta
                if task.completed_at and task.started_at:
                    completion_delta = (task.completed_at - task.started_at).total_seconds()
                    total_completion += completion_delta

            avg_wait_time = total_wait / len(completed_tasks) if total_wait else 0.0
            avg_completion_time = (
                total_completion / len(completed_tasks) if total_completion else 0.0
            )

        # Determine health
        queue_depth = pending + in_progress
        health = "healthy"
        if queue_depth > 50:
            health = "degraded"
        elif queue_depth > 100:
            health = "unhealthy"
        elif in_progress == 0 and pending > 0:
            health = "degraded"

        response = {
            "queue_depth": queue_depth,
            "pending_tasks": pending,
            "running_tasks": in_progress,
            "completed_today": completed_today,
            "failed_today": failed_today,
            "avg_wait_time_seconds": round(avg_wait_time, 2),
            "avg_completion_time_seconds": round(avg_completion_time, 2),
            "health": health,
        }

        return success_response(response)

    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        return error_response(str(e), 500)


# ============================================================================
# HEALTH CHECK
# ============================================================================


@browser_api.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint (no auth required)

    GET /api/browser-tasks/health

    Returns:
    {
        "status": "healthy",
        "timestamp": "2026-02-17T12:40:00Z"
    }
    """
    return success_response(
        {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )


if __name__ == "__main__":
    print("Browser Automation API Blueprint loaded")
