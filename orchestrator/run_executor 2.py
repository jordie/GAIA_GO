"""
Run Executor - Executes autonomous improvement runs

Each run goes through phases:
1. Planning - Analyze app, create roadmap, identify next steps
2. Implementing - Execute tasks via Claude in tmux sessions
3. Testing - Run tests, verify changes
4. Deploying - Deploy to staging/prod based on autopilot mode
5. Monitoring - Watch for regressions
6. Investigating - Analyze issues, propose fixes
"""

import json
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class RunExecutor:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_run(
        self,
        app_id: int,
        trigger_type: str = "scheduled",
        goal: Optional[str] = None,
        trigger_details: Optional[Dict] = None,
    ) -> int:
        """Create a new run for an app."""
        conn = self._get_conn()
        try:
            # Get next run number for this app
            result = conn.execute(
                "SELECT COALESCE(MAX(run_number), 0) + 1 FROM runs WHERE app_id = ?", (app_id,)
            ).fetchone()
            run_number = result[0]

            cursor = conn.execute(
                """
                INSERT INTO runs (app_id, run_number, trigger_type, trigger_details, goal, status, phase)
                VALUES (?, ?, ?, ?, ?, 'running', 'planning')
            """,
                (
                    app_id,
                    run_number,
                    trigger_type,
                    json.dumps(trigger_details) if trigger_details else None,
                    goal,
                ),
            )
            conn.commit()
            run_id = cursor.lastrowid

            # Update app's current run
            conn.execute(
                "UPDATE apps SET current_run_id = ?, current_phase = ? WHERE id = ?",
                (run_id, "planning", app_id),
            )
            conn.commit()

            return run_id
        finally:
            conn.close()

    def get_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        """Get run by ID."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row:
                return self._row_to_dict(row)
            return None
        finally:
            conn.close()

    def get_run_with_details(self, run_id: int) -> Optional[Dict[str, Any]]:
        """Get run with all related artifacts, steps, and milestones."""
        run = self.get_run(run_id)
        if not run:
            return None

        conn = self._get_conn()
        try:
            # Get steps
            steps = conn.execute(
                """
                SELECT * FROM agent_steps WHERE run_id = ? ORDER BY step_number
            """,
                (run_id,),
            ).fetchall()
            run["steps"] = [self._row_to_dict(s) for s in steps]

            # Get artifacts
            artifacts = conn.execute(
                """
                SELECT * FROM artifacts WHERE run_id = ? ORDER BY created_at
            """,
                (run_id,),
            ).fetchall()
            run["artifacts"] = [self._row_to_dict(a) for a in artifacts]

            # Get milestones
            milestones = conn.execute(
                """
                SELECT * FROM milestones WHERE run_id = ? ORDER BY created_at
            """,
                (run_id,),
            ).fetchall()
            run["milestones"] = [self._row_to_dict(m) for m in milestones]

            return run
        finally:
            conn.close()

    def update_run(self, run_id: int, **kwargs) -> bool:
        """Update run status and progress."""
        allowed_fields = {
            "status",
            "phase",
            "total_steps",
            "completed_steps",
            "current_step",
            "tmux_session",
            "outcome_summary",
        }

        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False

        # Handle completion
        if updates.get("status") in ("completed", "failed", "cancelled"):
            updates["completed_at"] = datetime.utcnow().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [run_id]

        conn = self._get_conn()
        try:
            conn.execute(f"UPDATE runs SET {set_clause} WHERE id = ?", values)

            # Update app phase if run phase changed
            if "phase" in updates:
                run = conn.execute("SELECT app_id FROM runs WHERE id = ?", (run_id,)).fetchone()
                if run:
                    conn.execute(
                        "UPDATE apps SET current_phase = ? WHERE id = ?",
                        (updates["phase"], run["app_id"]),
                    )

            conn.commit()
            return True
        finally:
            conn.close()

    def add_step(
        self, run_id: int, step_type: str, description: str, command: Optional[str] = None
    ) -> int:
        """Add a step to a run."""
        conn = self._get_conn()
        try:
            # Get next step number
            result = conn.execute(
                "SELECT COALESCE(MAX(step_number), 0) + 1 FROM agent_steps WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            step_number = result[0]

            cursor = conn.execute(
                """
                INSERT INTO agent_steps (run_id, step_number, step_type, description, command, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
            """,
                (run_id, step_number, step_type, description, command),
            )
            conn.commit()

            # Update run's total steps
            conn.execute("UPDATE runs SET total_steps = total_steps + 1 WHERE id = ?", (run_id,))
            conn.commit()

            return cursor.lastrowid
        finally:
            conn.close()

    def update_step(self, step_id: int, **kwargs) -> bool:
        """Update a step's status and output."""
        allowed_fields = {"status", "output", "error_message", "tmux_session"}

        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False

        if updates.get("status") == "running":
            updates["started_at"] = datetime.utcnow().isoformat()
        elif updates.get("status") in ("completed", "failed", "skipped"):
            updates["completed_at"] = datetime.utcnow().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [step_id]

        conn = self._get_conn()
        try:
            conn.execute(f"UPDATE agent_steps SET {set_clause} WHERE id = ?", values)

            # If step completed, update run's completed_steps
            if updates.get("status") == "completed":
                step = conn.execute(
                    "SELECT run_id FROM agent_steps WHERE id = ?", (step_id,)
                ).fetchone()
                if step:
                    conn.execute(
                        "UPDATE runs SET completed_steps = completed_steps + 1 WHERE id = ?",
                        (step["run_id"],),
                    )

            conn.commit()
            return True
        finally:
            conn.close()

    def add_artifact(
        self,
        run_id: int,
        artifact_type: str,
        title: str,
        content: str = None,
        file_path: str = None,
        url: str = None,
        milestone_id: int = None,
        metadata: Dict = None,
    ) -> int:
        """Add an artifact to a run."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """
                INSERT INTO artifacts (run_id, milestone_id, artifact_type, title, content, file_path, url, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    run_id,
                    milestone_id,
                    artifact_type,
                    title,
                    content,
                    file_path,
                    url,
                    json.dumps(metadata) if metadata else None,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_running_runs(self) -> List[Dict[str, Any]]:
        """Get all currently running runs."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """
                SELECT r.*, a.name as app_name, a.source_path
                FROM runs r
                JOIN apps a ON r.app_id = a.id
                WHERE r.status = 'running'
                ORDER BY r.started_at DESC
            """
            ).fetchall()
            return [self._row_to_dict(row) for row in rows]
        finally:
            conn.close()

    def create_tmux_session(self, run_id: int, session_name: str = None) -> str:
        """Create a tmux session for a run."""
        if not session_name:
            session_name = f"run_{run_id}"

        # Create tmux session
        try:
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", session_name], check=True, capture_output=True
            )
            self.update_run(run_id, tmux_session=session_name)
            return session_name
        except subprocess.CalledProcessError as e:
            # Session might already exist
            return session_name

    def send_to_claude(self, session_name: str, message: str) -> bool:
        """Send a message to Claude in a tmux session."""
        try:
            # Send the message
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, message, "Enter"],
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def capture_session_output(self, session_name: str, lines: int = 100) -> str:
        """Capture output from a tmux session."""
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", session_name, "-p", "-S", f"-{lines}"],
                capture_output=True,
                text=True,
            )
            return result.stdout
        except subprocess.CalledProcessError:
            return ""

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a sqlite Row to a dictionary."""
        d = dict(row)
        for field in ["trigger_details", "metadata"]:
            if field in d and d[field]:
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d
