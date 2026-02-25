#!/usr/bin/env python3
"""
Task Router - Routes tasks to appropriate worker sessions

Routes tasks based on type:
- Development tasks → Development sessions (architect, foundation, etc.)
- PR reviews → pr_review_worker
- Deployments → deployment_worker
- Testing → testing_worker
- Monitoring → monitoring sessions

Development sessions should ONLY receive development tasks.
"""

import json
import logging
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TaskRouter")

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "task_routing.db"


class TaskRouter:
    """Routes tasks to appropriate workers based on task type."""

    def __init__(self):
        self.db_path = DB_PATH
        self.init_database()

        # Define session types and their responsibilities
        self.session_types = {
            'development': {
                'sessions': ['architect', 'foundation', 'dev_worker1', 'dev_worker2', 'dev_worker3'],
                'task_types': ['feature', 'bugfix', 'refactor', 'code', 'implement']
            },
            'deployment': {
                'sessions': ['deployment_worker'],
                'task_types': ['deploy', 'release', 'tag', 'publish']
            },
            'pr_review': {
                'sessions': ['pr_review_worker'],
                'task_types': ['review', 'merge', 'pr', 'pull request']
            },
            'testing': {
                'sessions': ['qa_tester1', 'qa_tester2', 'qa_tester3', 'testing_worker'],
                'task_types': ['test', 'qa', 'verify', 'validate']
            },
            'monitoring': {
                'sessions': ['foundation_monitor', 'session_monitor'],
                'task_types': ['monitor', 'watch', 'track', 'observe']
            }
        }

    def init_database(self):
        """Initialize task routing database."""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_routes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                task_type TEXT,
                task_description TEXT,
                routed_to_session TEXT,
                routed_to_type TEXT,
                priority INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                assigned_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS routing_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_pattern TEXT,
                session_type TEXT,
                priority INTEGER DEFAULT 50,
                enabled INTEGER DEFAULT 1
            )
        """)

        # Insert default rules if table is empty
        cursor.execute("SELECT COUNT(*) FROM routing_rules")
        if cursor.fetchone()[0] == 0:
            default_rules = [
                ('deploy%', 'deployment', 100),
                ('merge%', 'pr_review', 90),
                ('review pr%', 'pr_review', 90),
                ('test%', 'testing', 70),
                ('qa%', 'testing', 70),
                ('monitor%', 'monitoring', 50),
                ('implement%', 'development', 60),
                ('feature%', 'development', 60),
                ('fix%', 'development', 70),
                ('refactor%', 'development', 50),
            ]

            for pattern, session_type, priority in default_rules:
                cursor.execute(
                    "INSERT INTO routing_rules (task_pattern, session_type, priority) VALUES (?, ?, ?)",
                    (pattern, session_type, priority)
                )

        conn.commit()
        conn.close()

    def classify_task(self, task_description: str) -> Dict:
        """Classify task and determine routing."""
        task_lower = task_description.lower()

        # Check against routing rules
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM routing_rules
            WHERE enabled = 1
            ORDER BY priority DESC
        """)

        rules = cursor.fetchall()
        conn.close()

        for rule in rules:
            pattern = rule['task_pattern'].replace('%', '')
            if pattern in task_lower:
                return {
                    'task_type': rule['session_type'],
                    'priority': rule['priority'],
                    'matched_pattern': rule['task_pattern']
                }

        # Default to development if no match
        return {
            'task_type': 'development',
            'priority': 50,
            'matched_pattern': 'default'
        }

    def get_available_session(self, session_type: str) -> Optional[str]:
        """Get an available session of the specified type."""
        sessions = self.session_types.get(session_type, {}).get('sessions', [])

        if not sessions:
            logger.warning(f"No sessions configured for type: {session_type}")
            return None

        # Check which sessions are running
        for session in sessions:
            if self.is_session_running(session):
                return session

        logger.warning(f"No running sessions found for type: {session_type}")
        return None

    def is_session_running(self, session_name: str) -> bool:
        """Check if a tmux session is running."""
        try:
            result = subprocess.run(
                ['tmux', 'has-session', '-t', session_name],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def route_task(self, task_description: str, task_id: Optional[str] = None,
                   priority: Optional[int] = None) -> Dict:
        """Route a task to the appropriate session."""

        # Classify task
        classification = self.classify_task(task_description)
        task_type = classification['task_type']
        task_priority = priority if priority is not None else classification['priority']

        # Get available session
        session = self.get_available_session(task_type)

        if not session:
            logger.error(f"No available session for task type: {task_type}")
            return {
                'success': False,
                'error': f'No available session for type: {task_type}',
                'task_type': task_type
            }

        # Log routing
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO task_routes
            (task_id, task_type, task_description, routed_to_session,
             routed_to_type, priority, status, assigned_at)
            VALUES (?, ?, ?, ?, ?, ?, 'routed', ?)
        """, (
            task_id or f"task-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            task_type,
            task_description,
            session,
            task_type,
            task_priority,
            datetime.now().isoformat()
        ))

        route_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Routed task to {session} ({task_type}): {task_description[:50]}")

        return {
            'success': True,
            'route_id': route_id,
            'task_type': task_type,
            'session': session,
            'priority': task_priority,
            'classification': classification
        }

    def send_task_to_session(self, session: str, task: str) -> bool:
        """Send task to a tmux session."""
        try:
            subprocess.run(
                ['tmux', 'send-keys', '-t', session, task, 'Enter'],
                timeout=5,
                check=True
            )
            return True
        except Exception as e:
            logger.error(f"Error sending task to {session}: {e}")
            return False

    def route_and_send(self, task_description: str, task_id: Optional[str] = None) -> Dict:
        """Route task and send to session immediately."""

        # Route the task
        route_result = self.route_task(task_description, task_id=task_id)

        if not route_result['success']:
            return route_result

        # Send to session
        session = route_result['session']
        sent = self.send_task_to_session(session, task_description)

        if sent:
            # Update status
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE task_routes SET status = 'sent' WHERE id = ?",
                (route_result['route_id'],)
            )
            conn.commit()
            conn.close()

            return {**route_result, 'sent': True}
        else:
            return {**route_result, 'sent': False, 'error': 'Failed to send to session'}

    def get_routing_stats(self) -> Dict:
        """Get routing statistics."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM task_routes")
        total_routes = cursor.fetchone()[0]

        cursor.execute("""
            SELECT routed_to_type, COUNT(*) as count
            FROM task_routes
            GROUP BY routed_to_type
        """)
        by_type = dict(cursor.fetchall())

        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM task_routes
            GROUP BY status
        """)
        by_status = dict(cursor.fetchall())

        conn.close()

        return {
            'total_routes': total_routes,
            'by_type': by_type,
            'by_status': by_status,
            'session_types': list(self.session_types.keys())
        }


def main():
    """CLI interface."""
    import sys

    router = TaskRouter()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == '--route':
            if len(sys.argv) < 3:
                print("Usage: --route '<task description>'")
                sys.exit(1)

            task = sys.argv[2]
            result = router.route_task(task)
            print(json.dumps(result, indent=2))

        elif command == '--send':
            if len(sys.argv) < 3:
                print("Usage: --send '<task description>'")
                sys.exit(1)

            task = sys.argv[2]
            result = router.route_and_send(task)
            print(json.dumps(result, indent=2))

        elif command == '--stats':
            stats = router.get_routing_stats()
            print(json.dumps(stats, indent=2))

        elif command == '--classify':
            if len(sys.argv) < 3:
                print("Usage: --classify '<task description>'")
                sys.exit(1)

            task = sys.argv[2]
            classification = router.classify_task(task)
            print(json.dumps(classification, indent=2))

        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    else:
        print("Task Router")
        print("\nUsage:")
        print("  python3 task_router.py --classify '<task>'  # Show task classification")
        print("  python3 task_router.py --route '<task>'     # Route task to session")
        print("  python3 task_router.py --send '<task>'      # Route and send to session")
        print("  python3 task_router.py --stats              # Show routing statistics")


if __name__ == "__main__":
    main()
