#!/usr/bin/env python3
"""
Session Status Update Helper

Provides simple interface for sessions to push status updates.
Updates written to data/session_status/{session}_status.json
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class SessionStatus:
    """Helper for pushing session status updates."""

    def __init__(self, session_name: str, base_dir: Optional[Path] = None):
        """
        Initialize status updater.

        Args:
            session_name: Name of the session (e.g., "manager1")
            base_dir: Base directory (defaults to project root)
        """
        self.session_name = session_name

        if base_dir is None:
            # Auto-detect project root
            current = Path(__file__).resolve()
            while current.parent != current:
                if (current / "data").exists():
                    base_dir = current
                    break
                current = current.parent
            else:
                base_dir = Path.cwd()

        self.status_dir = base_dir / "data" / "session_status"
        self.status_dir.mkdir(parents=True, exist_ok=True)

        self.status_file = self.status_dir / f"{session_name}_status.json"

    def push(
        self,
        status: str,
        message: str,
        progress: Optional[float] = None,
        task_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        """
        Push a status update.

        Args:
            status: Status value (idle, working, blocked, completed, error)
            message: Human-readable status message
            progress: Progress percentage (0.0 to 1.0)
            task_id: Associated task/prompt ID
            metadata: Additional metadata dictionary
        """
        update = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session": self.session_name,
            "status": status,
            "message": message,
        }

        if progress is not None:
            update["progress"] = min(max(progress, 0.0), 1.0)  # Clamp 0-1

        if task_id is not None:
            update["task_id"] = str(task_id)

        if metadata is not None:
            update["metadata"] = metadata

        # Append to file (one JSON object per line)
        with open(self.status_file, "a") as f:
            f.write(json.dumps(update) + "\n")

    def idle(self, message: str = "Waiting for tasks"):
        """Mark session as idle."""
        self.push("idle", message)

    def working(self, message: str, progress: Optional[float] = None, task_id: Optional[str] = None):
        """Mark session as working."""
        self.push("working", message, progress=progress, task_id=task_id)

    def blocked(self, message: str, task_id: Optional[str] = None):
        """Mark session as blocked."""
        self.push("blocked", message, task_id=task_id)

    def completed(self, message: str, task_id: Optional[str] = None):
        """Mark session as completed."""
        self.push("completed", message, progress=1.0, task_id=task_id)

    def error(self, message: str, task_id: Optional[str] = None):
        """Mark session as errored."""
        self.push("error", message, task_id=task_id)


def push_status_bash(session_name: str, status: str, message: str, **kwargs):
    """
    Convenience function that can be called from bash via:
    python3 -c "from utils.session_status import push_status_bash; push_status_bash('manager1', 'working', 'Query complete')"
    """
    updater = SessionStatus(session_name)
    updater.push(status, message, **kwargs)


# Command-line interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 4:
        print("Usage: python3 session_status.py <session> <status> <message> [progress] [task_id]")
        print("Example: python3 session_status.py manager1 working 'Querying database' 0.5 160")
        sys.exit(1)

    session = sys.argv[1]
    status = sys.argv[2]
    message = sys.argv[3]
    progress = float(sys.argv[4]) if len(sys.argv) > 4 else None
    task_id = sys.argv[5] if len(sys.argv) > 5 else None

    updater = SessionStatus(session)
    updater.push(status, message, progress=progress, task_id=task_id)
    print(f"✓ Status update pushed for {session}")
