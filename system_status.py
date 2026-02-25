#!/usr/bin/env python3
"""Real-time system status display for dashboard"""
import sqlite3
from datetime import datetime


def get_status():
    """Get current system status"""
    conn = sqlite3.connect("data/architect.db")
    c = conn.cursor()

    # Get task counts by status
    tasks = {}
    try:
        c.execute(
            """
            SELECT status, COUNT(*)
            FROM (
                SELECT 'pending' as status, COUNT(*) as cnt FROM task_queue WHERE status = 'pending'
                UNION ALL
                SELECT 'in_progress', COUNT(*) FROM task_queue WHERE status = 'in_progress'
                UNION ALL
                SELECT 'completed', COUNT(*) FROM task_queue WHERE status = 'completed'
            )
            GROUP BY status
        """
        )
        for status, count in c.fetchall():
            tasks[status] = count
    except:
        pass

    # Get project counts
    c.execute("SELECT status, COUNT(*) FROM projects GROUP BY status")
    projects = dict(c.fetchall())

    # Get feature counts
    c.execute("SELECT status, COUNT(*) FROM features GROUP BY status")
    features = dict(c.fetchall())

    # Get worker status
    workers = []
    try:
        c.execute(
            """
            SELECT worker_type, status, last_heartbeat
            FROM workers
            WHERE last_heartbeat > datetime('now', '-5 minutes')
            ORDER BY last_heartbeat DESC
        """
        )
        workers = c.fetchall()
    except:
        pass

    conn.close()

    return {
        "tasks": tasks,
        "projects": projects,
        "features": features,
        "workers": workers,
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(get_status(), indent=2))
