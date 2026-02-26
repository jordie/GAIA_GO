"""
Auto-Assignment Routes

Flask blueprint for task auto-assignment API endpoints.
"""

import logging

from flask import Blueprint, current_app, jsonify, request, session

logger = logging.getLogger(__name__)

auto_assign_bp = Blueprint("auto_assign", __name__, url_prefix="/api/auto-assign")


def get_db_path():
    return str(current_app.config.get("DB_PATH", "data/prod/architect.db"))


def require_auth(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        # Check API key
        api_key = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
        elif request.headers.get("X-API-Key"):
            api_key = request.headers.get("X-API-Key")

        if api_key:
            try:
                from services.api_keys import get_api_key_service

                service = get_api_key_service(get_db_path())
                if service.validate_key(api_key)["valid"]:
                    return f(*args, **kwargs)
            except Exception:
                pass

        # Check session
        if not session.get("user"):
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)

    return decorated


# =============================================================================
# Auto-Assignment Endpoints
# =============================================================================


@auto_assign_bp.route("/task/<int:task_id>", methods=["POST"])
@require_auth
def assign_task(task_id):
    """Auto-assign a specific task to the best available worker.

    Request body (optional):
        strategy: Assignment strategy ('least_loaded', 'round_robin',
                  'skill_match', 'balanced', 'fastest')
        force: If true, reassign even if already assigned

    Returns:
        Assignment result with worker info
    """
    from services.auto_assign import get_auto_assign_service

    data = request.get_json() or {}
    strategy = data.get("strategy")
    force = data.get("force", False)

    service = get_auto_assign_service(get_db_path())
    result = service.assign_task(task_id, strategy=strategy, force=force)

    if result["success"]:
        return jsonify(result)
    return jsonify(result), 400 if "not found" not in result.get("error", "") else 404


@auto_assign_bp.route("/all", methods=["POST"])
@require_auth
def assign_all_pending():
    """Auto-assign all unassigned pending tasks.

    Request body (optional):
        strategy: Assignment strategy
        limit: Maximum tasks to assign (default 100)
        task_types: List of task types to filter

    Returns:
        Summary of assignments made
    """
    from services.auto_assign import get_auto_assign_service

    data = request.get_json() or {}
    strategy = data.get("strategy")
    limit = data.get("limit", 100)
    task_types = data.get("task_types")

    if limit > 500:
        return jsonify({"error": "Limit cannot exceed 500"}), 400

    service = get_auto_assign_service(get_db_path())
    result = service.assign_all_pending(strategy=strategy, limit=limit, task_types=task_types)

    return jsonify(result)


@auto_assign_bp.route("/preview", methods=["GET"])
@require_auth
def preview_assignments():
    """Preview what auto-assignment would do without making changes.

    Query params:
        strategy: Assignment strategy to simulate
        limit: Number of tasks to preview (default 20)

    Returns:
        Preview of suggested assignments
    """
    from services.auto_assign import get_auto_assign_service

    strategy = request.args.get("strategy")
    limit = request.args.get("limit", 20, type=int)

    service = get_auto_assign_service(get_db_path())
    preview = service.get_assignment_preview(strategy=strategy, limit=limit)

    return jsonify(preview)


@auto_assign_bp.route("/workload", methods=["GET"])
@require_auth
def get_workload_summary():
    """Get current workload distribution summary.

    Returns:
        Workload statistics and per-worker metrics
    """
    from services.auto_assign import get_auto_assign_service

    service = get_auto_assign_service(get_db_path())
    summary = service.get_workload_summary()

    return jsonify(summary)


@auto_assign_bp.route("/workers", methods=["GET"])
@require_auth
def get_available_workers():
    """Get list of available workers with workload info.

    Returns:
        List of workers sorted by workload (least loaded first)
    """
    from services.auto_assign import get_auto_assign_service

    service = get_auto_assign_service(get_db_path())
    workers = service.get_available_workers()

    return jsonify({"workers": workers, "count": len(workers)})


@auto_assign_bp.route("/workers/<worker_id>/workload", methods=["GET"])
@require_auth
def get_worker_workload(worker_id):
    """Get workload metrics for a specific worker.

    Returns:
        Worker workload details
    """
    from services.auto_assign import get_auto_assign_service

    service = get_auto_assign_service(get_db_path())
    workload = service.get_worker_workload(worker_id)

    return jsonify(workload)


@auto_assign_bp.route("/strategies", methods=["GET"])
@require_auth
def get_strategies():
    """Get available assignment strategies.

    Returns:
        List of strategies with descriptions
    """
    from services.auto_assign import (
        DEFAULT_STRATEGY,
        STRATEGY_BALANCED,
        STRATEGY_FASTEST,
        STRATEGY_LEAST_LOADED,
        STRATEGY_ROUND_ROBIN,
        STRATEGY_SKILL_MATCH,
    )

    strategies = [
        {
            "id": STRATEGY_LEAST_LOADED,
            "name": "Least Loaded",
            "description": "Assign to worker with fewest active tasks",
            "best_for": "Even distribution of simple tasks",
        },
        {
            "id": STRATEGY_ROUND_ROBIN,
            "name": "Round Robin",
            "description": "Cycle through workers in order",
            "best_for": "Fair task distribution regardless of load",
        },
        {
            "id": STRATEGY_SKILL_MATCH,
            "name": "Skill Match",
            "description": "Assign to worker with best matching skills",
            "best_for": "Specialized tasks requiring expertise",
        },
        {
            "id": STRATEGY_BALANCED,
            "name": "Balanced",
            "description": "Combine workload, skills, and performance",
            "best_for": "General purpose - recommended default",
        },
        {
            "id": STRATEGY_FASTEST,
            "name": "Fastest",
            "description": "Assign to worker with best completion time",
            "best_for": "Time-sensitive tasks",
        },
    ]

    return jsonify({"strategies": strategies, "default": DEFAULT_STRATEGY})


@auto_assign_bp.route("/config", methods=["GET"])
@require_auth
def get_config():
    """Get auto-assignment configuration.

    Returns:
        Current configuration values
    """
    from services.auto_assign import (
        DEFAULT_STRATEGY,
        HEARTBEAT_TIMEOUT_SECONDS,
        MAX_CONCURRENT_TASKS,
        SKILL_MATCH_THRESHOLD,
        WEIGHT_ESTIMATED_HOURS,
        WEIGHT_RUNNING_TASK,
        WEIGHT_STORY_POINTS,
        WEIGHT_TASK_COUNT,
    )

    return jsonify(
        {
            "max_concurrent_tasks": MAX_CONCURRENT_TASKS,
            "heartbeat_timeout_seconds": HEARTBEAT_TIMEOUT_SECONDS,
            "skill_match_threshold": SKILL_MATCH_THRESHOLD,
            "default_strategy": DEFAULT_STRATEGY,
            "workload_weights": {
                "task_count": WEIGHT_TASK_COUNT,
                "story_points": WEIGHT_STORY_POINTS,
                "estimated_hours": WEIGHT_ESTIMATED_HOURS,
                "running_task": WEIGHT_RUNNING_TASK,
            },
        }
    )


@auto_assign_bp.route("/recommend/<int:task_id>", methods=["GET"])
@require_auth
def recommend_worker(task_id):
    """Get worker recommendation for a specific task.

    Query params:
        strategy: Strategy to use for recommendation

    Returns:
        Recommended worker with reasoning
    """
    import sqlite3

    from services.auto_assign import get_auto_assign_service

    strategy = request.args.get("strategy")

    service = get_auto_assign_service(get_db_path())

    # Get task
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    task = conn.execute("SELECT * FROM task_queue WHERE id = ?", (task_id,)).fetchone()
    conn.close()

    if not task:
        return jsonify({"error": "Task not found"}), 404

    task_dict = dict(task)

    # Get recommendation
    with sqlite3.connect(get_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        worker = service.select_worker(task_dict, strategy, conn)

        if not worker:
            return jsonify(
                {"task_id": task_id, "recommendation": None, "reason": "No available workers"}
            )

        # Get all candidates for comparison
        candidates = service.get_available_workers(conn)

        return jsonify(
            {
                "task_id": task_id,
                "task_type": task_dict["task_type"],
                "strategy": strategy or "balanced",
                "recommendation": {
                    "worker_id": worker["id"],
                    "workload_score": worker.get("workload_score", 0),
                    "skill_score": worker.get("skill_score"),
                    "combined_score": worker.get("combined_score"),
                    "current_tasks": worker.get("task_count", 0),
                    "capacity_remaining": worker.get("capacity_remaining", 0),
                },
                "alternatives": [
                    {
                        "worker_id": c["id"],
                        "workload_score": c["workload_score"],
                        "current_tasks": c["task_count"],
                    }
                    for c in candidates[1:4]  # Show next 3 alternatives
                ]
                if len(candidates) > 1
                else [],
            }
        )


# =============================================================================
# Batch Operations
# =============================================================================


@auto_assign_bp.route("/batch", methods=["POST"])
@require_auth
def batch_assign():
    """Assign multiple specific tasks.

    Request body:
        task_ids: List of task IDs to assign
        strategy: Assignment strategy (optional)
        force: Reassign even if already assigned (optional)

    Returns:
        Results for each task
    """
    from services.auto_assign import get_auto_assign_service

    data = request.get_json()
    if not data or not data.get("task_ids"):
        return jsonify({"error": "task_ids is required"}), 400

    task_ids = data["task_ids"]
    strategy = data.get("strategy")
    force = data.get("force", False)

    if len(task_ids) > 100:
        return jsonify({"error": "Maximum 100 tasks per batch"}), 400

    service = get_auto_assign_service(get_db_path())

    results = {"total": len(task_ids), "assigned": 0, "failed": 0, "results": []}

    for task_id in task_ids:
        result = service.assign_task(task_id, strategy=strategy, force=force)
        results["results"].append({"task_id": task_id, **result})
        if result["success"]:
            results["assigned"] += 1
        else:
            results["failed"] += 1

    return jsonify(results)


@auto_assign_bp.route("/rebalance", methods=["POST"])
@require_auth
def rebalance_tasks():
    """Rebalance tasks across workers to even out workload.

    Request body (optional):
        dry_run: If true, only preview changes (default false)
        max_moves: Maximum task reassignments (default 10)

    Returns:
        Rebalancing results
    """
    import sqlite3

    from services.auto_assign import MAX_CONCURRENT_TASKS, get_auto_assign_service

    data = request.get_json() or {}
    dry_run = data.get("dry_run", False)
    max_moves = min(data.get("max_moves", 10), 50)

    service = get_auto_assign_service(get_db_path())
    workers = service.get_available_workers()

    if len(workers) < 2:
        return jsonify({"success": False, "error": "Need at least 2 workers to rebalance"})

    # Calculate average load
    total_tasks = sum(w["task_count"] for w in workers)
    avg_load = total_tasks / len(workers)

    # Find overloaded and underloaded workers
    overloaded = [w for w in workers if w["task_count"] > avg_load + 1]
    underloaded = [w for w in workers if w["task_count"] < avg_load - 1]

    moves = []
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row

    try:
        for over_worker in overloaded:
            if len(moves) >= max_moves:
                break

            # Get reassignable tasks from overloaded worker
            tasks = conn.execute(
                """
                SELECT id, task_type, priority FROM task_queue
                WHERE assigned_worker = ?
                AND status = 'pending'
                ORDER BY priority ASC
                LIMIT ?
            """,
                (over_worker["id"], max_moves - len(moves)),
            ).fetchall()

            for task in tasks:
                if len(moves) >= max_moves:
                    break

                # Find underloaded worker
                for under_worker in underloaded:
                    if under_worker["task_count"] < MAX_CONCURRENT_TASKS - 1:
                        moves.append(
                            {
                                "task_id": task["id"],
                                "from_worker": over_worker["id"],
                                "to_worker": under_worker["id"],
                                "task_type": task["task_type"],
                            }
                        )
                        under_worker["task_count"] += 1
                        over_worker["task_count"] -= 1
                        break

        # Apply moves if not dry run
        if not dry_run and moves:
            for move in moves:
                conn.execute(
                    """
                    UPDATE task_queue
                    SET assigned_worker = ?
                    WHERE id = ?
                """,
                    (move["to_worker"], move["task_id"]),
                )
            conn.commit()

        return jsonify(
            {
                "success": True,
                "dry_run": dry_run,
                "moves_planned": len(moves),
                "moves_applied": len(moves) if not dry_run else 0,
                "moves": moves,
                "before": {
                    "avg_load": round(avg_load, 2),
                    "overloaded_workers": len(overloaded),
                    "underloaded_workers": len(underloaded),
                },
            }
        )

    finally:
        conn.close()
