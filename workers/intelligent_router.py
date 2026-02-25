#!/usr/bin/env python3
"""
Intelligent Task Router
Classifies tasks and routes them to best-matching sessions based on specialty and success rate.
"""

import logging
import re
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskClassifier:
    """Classifies tasks by analyzing content and keywords."""

    # Task type classification patterns
    PATTERNS = {
        "frontend": [
            r"\b(react|vue|angular|svelte)\b",
            r"\b(css|scss|sass|tailwind)\b",
            r"\b(html|jsx|tsx|template)\b",
            r"\b(component|ui|ux|interface)\b",
            r"\b(frontend|client-side|browser)\b",
            r"\.(html|css|jsx|tsx|vue|svelte)$",
        ],
        "backend": [
            r"\b(api|endpoint|route|controller)\b",
            r"\b(database|sql|query|orm)\b",
            r"\b(python|flask|django|fastapi)\b",
            r"\b(server|backend|service)\b",
            r"\b(rest|graphql|grpc)\b",
            r"\.(py|sql|db)$",
        ],
        "devops": [
            r"\b(docker|kubernetes|k8s)\b",
            r"\b(deploy|deployment|ci/cd)\b",
            r"\b(nginx|apache|server)\b",
            r"\b(aws|gcp|azure|cloud)\b",
            r"\b(terraform|ansible|puppet)\b",
            r"\.(yaml|yml|dockerfile|sh)$",
        ],
        "testing": [
            r"\b(test|testing|spec|unit test|integration test)\b",
            r"\b(pytest|jest|mocha|cypress)\b",
            r"\b(mock|fixture|assertion)\b",
            r"\b(coverage|e2e|end-to-end)\b",
            r"test_.*\.py$",
            r".*\.test\.(js|ts|jsx|tsx)$",
        ],
        "research": [
            r"\b(research|investigate|analyze|study)\b",
            r"\b(explore|understand|learn)\b",
            r"\b(how does|how to|what is|why)\b",
            r"\b(documentation|docs|readme)\b",
            r"\b(architecture|design|pattern)\b",
        ],
        "config": [
            r"\b(config|configuration|settings)\b",
            r"\b(env|environment|variables)\b",
            r"\.(json|yaml|yml|toml|ini|conf|config)$",
            r"\b(setup|install|configure)\b",
        ],
    }

    def classify(self, task_content: str) -> Tuple[str, float]:
        """
        Classify task content into a category.

        Returns:
            Tuple of (task_type, confidence_score)
        """
        task_lower = task_content.lower()
        scores = {}

        for task_type, patterns in self.PATTERNS.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, task_lower, re.IGNORECASE))
                score += matches
            scores[task_type] = score

        # Get task type with highest score
        if max(scores.values()) == 0:
            return "general", 0.0

        best_type = max(scores, key=scores.get)
        total_score = sum(scores.values())
        confidence = scores[best_type] / total_score if total_score > 0 else 0.0

        return best_type, confidence


class IntelligentRouter:
    """Routes tasks to best-matching sessions based on specialty and performance."""

    def __init__(self, db_path: str = "data/assigner/assigner.db"):
        self.db_path = db_path
        self.classifier = TaskClassifier()

    def get_db_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def find_best_session(
        self, task_content: str, task_type: Optional[str] = None
    ) -> Optional[str]:
        """
        Find the best session for a task based on specialty and success rate.

        Args:
            task_content: The task description
            task_type: Optional pre-classified task type

        Returns:
            Session name or None if no suitable session found
        """
        # Classify task if type not provided
        if task_type is None:
            task_type, confidence = self.classifier.classify(task_content)
            logger.info(f"Classified task as '{task_type}' (confidence: {confidence:.2f})")

        conn = self.get_db_connection()
        cursor = conn.cursor()

        # Get available Claude sessions
        cursor.execute(
            """
            SELECT
                name,
                specialty,
                success_rate,
                avg_completion_time,
                total_tasks_completed,
                status
            FROM sessions
            WHERE is_claude = 1
                AND status IN ('idle', 'waiting_input')
                AND current_task_id IS NULL
            ORDER BY
                -- Prioritize exact specialty match
                CASE WHEN specialty = ? THEN 1 ELSE 0 END DESC,
                -- Then by success rate
                success_rate DESC,
                -- Then by completion time (faster is better)
                CASE WHEN avg_completion_time > 0 THEN avg_completion_time ELSE 999999 END ASC,
                -- Finally by experience (more tasks completed)
                total_tasks_completed DESC
            LIMIT 1
        """,
            (task_type,),
        )

        result = cursor.fetchone()
        conn.close()

        if result:
            session_name = result["name"]
            logger.info(
                f"Selected session '{session_name}' for {task_type} task "
                f"(specialty: {result['specialty']}, success_rate: {result['success_rate']:.1%})"
            )
            return session_name

        logger.warning(f"No available sessions found for {task_type} task")
        return None

    def update_session_stats(self, session_name: str, success: bool, duration_seconds: int):
        """
        Update session statistics after task completion.

        Args:
            session_name: Name of the session
            success: Whether the task succeeded
            duration_seconds: How long the task took
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()

        # Get current stats
        cursor.execute(
            """
            SELECT total_tasks_completed, total_tasks_failed, avg_completion_time
            FROM sessions
            WHERE name = ?
        """,
            (session_name,),
        )

        result = cursor.fetchone()
        if not result:
            logger.error(f"Session '{session_name}' not found")
            conn.close()
            return

        total_completed = result["total_tasks_completed"]
        total_failed = result["total_tasks_failed"]
        avg_time = result["avg_completion_time"]

        # Calculate new stats
        if success:
            new_completed = total_completed + 1
            new_failed = total_failed
        else:
            new_completed = total_completed
            new_failed = total_failed + 1

        new_total = new_completed + new_failed
        new_success_rate = (new_completed / new_total * 100) if new_total > 0 else 0

        # Update average completion time (exponential moving average)
        if success and duration_seconds > 0:
            if avg_time == 0:
                new_avg_time = duration_seconds
            else:
                # Weight: 70% old average, 30% new time
                new_avg_time = int(avg_time * 0.7 + duration_seconds * 0.3)
        else:
            new_avg_time = avg_time

        # Update database
        cursor.execute(
            """
            UPDATE sessions
            SET total_tasks_completed = ?,
                total_tasks_failed = ?,
                success_rate = ?,
                avg_completion_time = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE name = ?
        """,
            (new_completed, new_failed, new_success_rate, new_avg_time, session_name),
        )

        conn.commit()
        conn.close()

        logger.info(
            f"Updated stats for '{session_name}': "
            f"success_rate={new_success_rate:.1%}, "
            f"avg_time={new_avg_time}s, "
            f"completed={new_completed}, failed={new_failed}"
        )

    def assign_specialty(self, session_name: str, specialty: str):
        """
        Manually assign a specialty to a session.

        Args:
            session_name: Name of the session
            specialty: One of: frontend, backend, devops, testing, research, config, general
        """
        valid_specialties = [
            "frontend",
            "backend",
            "devops",
            "testing",
            "research",
            "config",
            "general",
        ]
        if specialty not in valid_specialties:
            logger.error(f"Invalid specialty '{specialty}'. Must be one of: {valid_specialties}")
            return False

        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE sessions
            SET specialty = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE name = ?
        """,
            (specialty, session_name),
        )

        conn.commit()
        conn.close()

        logger.info(f"Assigned specialty '{specialty}' to session '{session_name}'")
        return True

    def get_session_stats(self, session_name: Optional[str] = None) -> List[Dict]:
        """
        Get statistics for one or all sessions.

        Args:
            session_name: Optional session name to filter by

        Returns:
            List of session stats dictionaries
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()

        if session_name:
            cursor.execute(
                """
                SELECT name, specialty, success_rate, avg_completion_time,
                       total_tasks_completed, total_tasks_failed, status
                FROM sessions
                WHERE name = ? AND is_claude = 1
            """,
                (session_name,),
            )
        else:
            cursor.execute(
                """
                SELECT name, specialty, success_rate, avg_completion_time,
                       total_tasks_completed, total_tasks_failed, status
                FROM sessions
                WHERE is_claude = 1
                ORDER BY success_rate DESC, total_tasks_completed DESC
            """
            )

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return results


if __name__ == "__main__":
    # Demo usage
    import argparse

    parser = argparse.ArgumentParser(description="Intelligent Task Router")
    parser.add_argument("--classify", type=str, help="Classify a task description")
    parser.add_argument("--route", type=str, help="Find best session for a task")
    parser.add_argument(
        "--assign-specialty",
        nargs=2,
        metavar=("SESSION", "SPECIALTY"),
        help="Assign specialty to session",
    )
    parser.add_argument("--stats", action="store_true", help="Show session statistics")
    parser.add_argument("--session", type=str, help="Filter stats by session name")

    args = parser.parse_args()

    router = IntelligentRouter()

    if args.classify:
        task_type, confidence = router.classifier.classify(args.classify)
        print(f"Task Type: {task_type} (confidence: {confidence:.1%})")

    elif args.route:
        session = router.find_best_session(args.route)
        if session:
            print(f"Best Session: {session}")
        else:
            print("No available session found")

    elif args.assign_specialty:
        session_name, specialty = args.assign_specialty
        router.assign_specialty(session_name, specialty)

    elif args.stats:
        stats = router.get_session_stats(args.session)
        print(
            f"\n{'Session':<25} {'Specialty':<15} {'Success Rate':<15} {'Avg Time':<12} {'Completed':<12} {'Failed':<10}"
        )
        print("=" * 110)
        for s in stats:
            print(
                f"{s['name']:<25} {s['specialty']:<15} {s['success_rate']:>6.1f}%         "
                f"{s['avg_completion_time']:>6}s      {s['total_tasks_completed']:>6}       {s['total_tasks_failed']:>6}"
            )

    else:
        parser.print_help()
