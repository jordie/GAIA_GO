"""
Skill-based Task Assignment Service

Matches workers to tasks based on their skills and expertise levels.
"""

import sqlite3
from typing import Dict, List, Optional


def calculate_skill_match_score(worker_id: str, task_type: str, conn) -> dict:
    """Calculate how well a worker matches a task's skill requirements.

    Args:
        worker_id: The worker ID to evaluate
        task_type: The task type to match against
        conn: Database connection with row_factory set

    Returns:
        dict with score (0-100), matched_skills, missing_skills, details
    """
    # Get task skill requirements
    requirements = conn.execute(
        """
        SELECT skill_name, min_proficiency, priority
        FROM task_skill_requirements
        WHERE task_type = ?
        ORDER BY priority DESC
    """,
        [task_type],
    ).fetchall()

    if not requirements:
        return {
            "score": 100,
            "matched_skills": [],
            "missing_skills": [],
            "details": "No skill requirements for this task type",
            "matched_count": 0,
            "total_requirements": 0,
        }

    # Get worker skills
    worker_skills = conn.execute(
        """
        SELECT skill_name, proficiency, tasks_completed
        FROM worker_skills
        WHERE worker_id = ?
    """,
        [worker_id],
    ).fetchall()

    skill_map = {
        s["skill_name"]: {"proficiency": s["proficiency"], "tasks": s["tasks_completed"]}
        for s in worker_skills
    }

    matched = []
    missing = []
    total_weight = 0
    weighted_score = 0

    for req in requirements:
        skill = req["skill_name"]
        min_prof = req["min_proficiency"]
        priority = req["priority"]
        total_weight += priority

        if skill in skill_map:
            prof = skill_map[skill]["proficiency"]
            if prof >= min_prof:
                matched.append(
                    {
                        "skill": skill,
                        "proficiency": prof,
                        "required": min_prof,
                        "experience": skill_map[skill]["tasks"],
                    }
                )
                # Full points for meeting requirement, bonus for exceeding
                weighted_score += priority * min(100, prof)
            else:
                missing.append(
                    {
                        "skill": skill,
                        "proficiency": prof,
                        "required": min_prof,
                        "gap": min_prof - prof,
                    }
                )
                # Partial credit based on how close they are
                weighted_score += priority * (prof / min_prof * 50) if min_prof > 0 else 0
        else:
            missing.append(
                {"skill": skill, "proficiency": 0, "required": min_prof, "gap": min_prof}
            )
            # No credit for completely missing skills

    final_score = round(weighted_score / total_weight) if total_weight > 0 else 0

    return {
        "score": final_score,
        "matched_skills": matched,
        "missing_skills": missing,
        "total_requirements": len(requirements),
        "matched_count": len(matched),
        "worker_id": worker_id,
        "task_type": task_type,
    }


def find_best_worker_for_task(
    task_type: str, available_workers: List[Dict], conn, min_score: int = 0
) -> dict:
    """Find the best matching worker for a task based on skills.

    Args:
        task_type: The type of task to match
        available_workers: List of available worker dicts with 'id' key
        conn: Database connection
        min_score: Minimum acceptable match score (0-100)

    Returns:
        dict with best_worker, score, all candidates ranked
    """
    candidates = []

    for worker in available_workers:
        worker_id = worker["id"] if isinstance(worker, dict) else worker
        match = calculate_skill_match_score(worker_id, task_type, conn)

        candidates.append(
            {
                "worker_id": worker_id,
                "worker_type": worker.get("worker_type") if isinstance(worker, dict) else None,
                "node_id": worker.get("node_id") if isinstance(worker, dict) else None,
                "score": match["score"],
                "matched_skills": len(match["matched_skills"]),
                "missing_skills": len(match["missing_skills"]),
                "details": match,
            }
        )

    # Sort by score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Filter by minimum score
    qualified = [c for c in candidates if c["score"] >= min_score]

    return {
        "best_worker": qualified[0] if qualified else None,
        "candidates": candidates[:10],
        "qualified_count": len(qualified),
        "total_evaluated": len(candidates),
        "min_score_required": min_score,
    }


def update_worker_skill_stats(
    worker_id: str, skill_name: str, task_duration_seconds: float, success: bool, conn
):
    """Update worker skill statistics after task completion.

    Args:
        worker_id: The worker who completed the task
        skill_name: The primary skill used
        task_duration_seconds: How long the task took
        success: Whether the task was successful
        conn: Database connection
    """
    if success:
        conn.execute(
            """
            UPDATE worker_skills SET
                tasks_completed = tasks_completed + 1,
                avg_duration_seconds = COALESCE(
                    (avg_duration_seconds * tasks_completed + ?) / (tasks_completed + 1),
                    ?
                ),
                last_used = CURRENT_TIMESTAMP
            WHERE worker_id = ? AND skill_name = ?
        """,
            [task_duration_seconds, task_duration_seconds, worker_id, skill_name],
        )

        # Optionally increase proficiency slightly for successful completions
        conn.execute(
            """
            UPDATE worker_skills SET
                proficiency = MIN(100, proficiency + 1)
            WHERE worker_id = ? AND skill_name = ?
              AND proficiency < 100
              AND tasks_completed > 0
              AND tasks_completed % 10 = 0
        """,
            [worker_id, skill_name],
        )


def get_skill_leaderboard(skill_name: str, conn, limit: int = 10) -> List[Dict]:
    """Get top workers for a specific skill.

    Args:
        skill_name: The skill to rank
        conn: Database connection
        limit: Max workers to return

    Returns:
        List of workers ranked by proficiency and experience
    """
    workers = conn.execute(
        """
        SELECT ws.worker_id, ws.proficiency, ws.tasks_completed,
               ws.avg_duration_seconds, w.worker_type, w.status
        FROM worker_skills ws
        JOIN workers w ON ws.worker_id = w.id
        WHERE ws.skill_name = ?
        ORDER BY ws.proficiency DESC, ws.tasks_completed DESC
        LIMIT ?
    """,
        [skill_name.lower(), limit],
    ).fetchall()

    return [dict(w) for w in workers]


def suggest_skills_for_worker(worker_id: str, conn, limit: int = 5) -> List[Dict]:
    """Suggest skills a worker should learn based on task demand.

    Args:
        worker_id: The worker to suggest for
        conn: Database connection
        limit: Max suggestions

    Returns:
        List of suggested skills with demand info
    """
    # Find skills required by tasks that this worker doesn't have
    suggestions = conn.execute(
        """
        SELECT tsr.skill_name, COUNT(DISTINCT tsr.task_type) as task_types,
               AVG(tsr.min_proficiency) as avg_required
        FROM task_skill_requirements tsr
        WHERE tsr.skill_name NOT IN (
            SELECT skill_name FROM worker_skills WHERE worker_id = ?
        )
        GROUP BY tsr.skill_name
        ORDER BY task_types DESC
        LIMIT ?
    """,
        [worker_id, limit],
    ).fetchall()

    return [dict(s) for s in suggestions]
