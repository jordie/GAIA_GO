"""
Integration tests for workers/assigner_worker.py

Tests prompt assignment, session management, retry logic,
and provider-based routing.
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from workers.assigner_worker import (  # noqa: E402
    AssignerWorker,
    PromptStatus,
    SessionStatus,
)


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Create test database for assigner worker."""
    db_path = tmp_path / "test_assigner.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Create tables
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            source TEXT DEFAULT 'api',
            priority INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            assigned_session TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            assigned_at TIMESTAMP,
            completed_at TIMESTAMP,
            response TEXT,
            error TEXT,
            metadata TEXT,
            target_session TEXT,
            target_provider TEXT,
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3
        );

        CREATE TABLE IF NOT EXISTS sessions (
            name TEXT PRIMARY KEY,
            status TEXT DEFAULT 'unknown',
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            current_task_id INTEGER,
            working_dir TEXT,
            is_claude INTEGER DEFAULT 0,
            provider TEXT,
            last_output TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (current_task_id) REFERENCES prompts(id)
        );

        CREATE TABLE IF NOT EXISTS assignment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_id INTEGER NOT NULL,
            session_name TEXT NOT NULL,
            action TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT,
            FOREIGN KEY (prompt_id) REFERENCES prompts(id)
        );

        CREATE INDEX idx_prompts_status ON prompts(status);
        CREATE INDEX idx_prompts_priority
            ON prompts(priority DESC, created_at ASC);
        CREATE INDEX idx_sessions_status ON sessions(status);
    """
    )

    # Insert test sessions
    conn.execute(
        """
        INSERT INTO sessions (
            name, status, provider, is_claude, last_activity
        )
        VALUES ('claude-session', 'idle', 'claude', 1, ?)
    """,
        (datetime.now().isoformat(),),
    )
    conn.execute(
        """
        INSERT INTO sessions (
            name, status, provider, is_claude, last_activity
        )
        VALUES ('codex-session', 'idle', 'codex', 1, ?)
    """,
        (datetime.now().isoformat(),),
    )
    conn.execute(
        """
        INSERT INTO sessions (
            name, status, provider, is_claude, last_activity
        )
        VALUES ('ollama-session', 'busy', 'ollama', 0, ?)
    """,
        (datetime.now().isoformat(),),
    )
    conn.commit()

    # Patch database path
    monkeypatch.setattr("workers.assigner_worker.ASSIGNER_DB", db_path)

    yield {"conn": conn, "path": db_path}
    conn.close()


@pytest.fixture
def worker(test_db, monkeypatch):
    """Create AssignerWorker instance."""
    # Ensure database path is patched before creating worker
    from workers.assigner_worker import AssignerDatabase

    monkeypatch.setattr("workers.assigner_worker.ASSIGNER_DB", test_db["path"])

    # Create worker after patching
    worker_inst = AssignerWorker()
    # Replace the database instance with one using test database
    worker_inst.db = AssignerDatabase(db_path=test_db["path"])
    return worker_inst


@pytest.mark.integration
class TestPromptCreation:
    """Test prompt creation and management."""

    def test_add_prompt_basic(self, worker, test_db):
        """Test adding a basic prompt."""
        prompt_id = worker.db.add_prompt("Test task", priority=5)

        assert prompt_id is not None
        assert isinstance(prompt_id, int)

        # Verify in database
        prompt = (
            test_db["conn"]
            .execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,))
            .fetchone()
        )
        assert prompt is not None
        assert prompt["content"] == "Test task"
        assert prompt["priority"] == 5
        assert prompt["status"] == PromptStatus.PENDING

    def test_add_prompt_with_target_session(self, worker, test_db):
        """Test adding prompt with target session."""
        prompt_id = worker.db.add_prompt(
            "Targeted task", target_session="claude-session"
        )

        prompt = (
            test_db["conn"]
            .execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,))
            .fetchone()
        )
        assert prompt["target_session"] == "claude-session"

    def test_add_prompt_with_target_provider(self, worker, test_db):
        """Test adding prompt with target provider."""
        prompt_id = worker.db.add_prompt(
            "Provider task", target_provider="codex"
        )

        prompt = (
            test_db["conn"]
            .execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,))
            .fetchone()
        )
        assert prompt["target_provider"] == "codex"

    def test_add_prompt_with_metadata(self, worker, test_db):
        """Test adding prompt with metadata."""
        metadata = {"project": "architect", "category": "bug_fix"}
        prompt_id = worker.db.add_prompt(
            "Task with metadata", metadata=metadata
        )

        prompt = (
            test_db["conn"]
            .execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,))
            .fetchone()
        )
        stored_metadata = json.loads(prompt["metadata"])
        assert stored_metadata == metadata


@pytest.mark.integration
class TestPromptStatusManagement:
    """Test prompt status updates."""

    def test_update_prompt_status(self, worker, test_db):
        """Test updating prompt status."""
        prompt_id = worker.db.add_prompt("Test task")

        worker.db.update_prompt_status(
            prompt_id, status=PromptStatus.ASSIGNED
        )

        prompt = (
            test_db["conn"]
            .execute("SELECT status FROM prompts WHERE id = ?", (prompt_id,))
            .fetchone()
        )
        assert prompt["status"] == PromptStatus.ASSIGNED

    def test_update_prompt_to_completed(self, worker, test_db):
        """Test marking prompt as completed."""
        prompt_id = worker.db.add_prompt("Test task")

        worker.db.update_prompt_status(
            prompt_id,
            status=PromptStatus.COMPLETED,
            response="Task done",
        )

        prompt = (
            test_db["conn"]
            .execute(
                "SELECT status, response, completed_at FROM prompts "
                "WHERE id = ?",
                (prompt_id,),
            )
            .fetchone()
        )
        assert prompt["status"] == PromptStatus.COMPLETED
        assert prompt["response"] == "Task done"
        assert prompt["completed_at"] is not None

    def test_update_prompt_to_failed(self, worker, test_db):
        """Test marking prompt as failed with error."""
        prompt_id = worker.db.add_prompt("Test task")

        worker.db.update_prompt_status(
            prompt_id, status=PromptStatus.FAILED, error="Timeout"
        )

        prompt = (
            test_db["conn"]
            .execute(
                "SELECT status, error FROM prompts WHERE id = ?",
                (prompt_id,),
            )
            .fetchone()
        )
        assert prompt["status"] == PromptStatus.FAILED
        assert prompt["error"] == "Timeout"


@pytest.mark.integration
class TestSessionManagement:
    """Test session registration and status tracking."""

    def test_update_session_status(self, worker, test_db):
        """Test updating session status."""
        worker.db.update_session(
            "claude-session", status=SessionStatus.BUSY
        )

        session = (
            test_db["conn"]
            .execute(
                "SELECT status FROM sessions WHERE name = ?",
                ("claude-session",),
            )
            .fetchone()
        )
        assert session["status"] == SessionStatus.BUSY

    def test_update_session_activity(self, worker, test_db):
        """Test updating session last activity."""
        worker.db.update_session("claude-session", status=SessionStatus.IDLE)

        session = (
            test_db["conn"]
            .execute(
                "SELECT last_activity, updated_at FROM sessions WHERE name = ?",
                ("claude-session",),
            )
            .fetchone()
        )
        # Activity and updated_at should exist and be recent
        assert session["last_activity"] is not None
        assert session["updated_at"] is not None


@pytest.mark.integration
class TestSessionQuery:
    """Test querying available sessions."""

    def test_get_available_sessions(self, worker, test_db):
        """Test getting available idle sessions."""
        sessions = worker.db.get_available_sessions()

        assert len(sessions) >= 2  # claude-session, codex-session
        session_names = [s["name"] for s in sessions]
        assert "claude-session" in session_names
        assert "codex-session" in session_names
        # ollama-session is busy, should not be included
        assert "ollama-session" not in session_names

    def test_get_sessions_by_provider(self, worker, test_db):
        """Test filtering sessions by provider."""
        sessions = worker.db.get_available_sessions(provider="claude")

        assert len(sessions) >= 1
        assert all(s["provider"] == "claude" for s in sessions)

    def test_get_all_sessions(self, worker, test_db):
        """Test getting all sessions regardless of status."""
        sessions = worker.db.get_all_sessions()

        assert len(sessions) >= 3
        session_names = [s["name"] for s in sessions]
        assert "claude-session" in session_names
        assert "ollama-session" in session_names


@pytest.mark.integration
class TestPriorityHandling:
    """Test priority-based prompt handling."""

    def test_get_prompts_by_priority(self, worker, test_db):
        """Test prompts are ordered by priority."""
        worker.db.add_prompt("Low priority", priority=1)
        worker.db.add_prompt("High priority", priority=10)
        worker.db.add_prompt("Medium priority", priority=5)

        prompts = worker.db.get_pending_prompts(limit=10)

        # Should be ordered by priority DESC
        priorities = [p["priority"] for p in prompts]
        assert priorities == sorted(priorities, reverse=True)


@pytest.mark.integration
class TestRetryLogic:
    """Test prompt retry functionality."""

    def test_retry_failed_prompt(self, worker, test_db):
        """Test retrying a failed prompt."""
        prompt_id = worker.db.add_prompt("Test task")

        # Mark as failed
        worker.db.update_prompt_status(
            prompt_id, status=PromptStatus.FAILED, error="Timeout"
        )

        # Retry
        success = worker.db.retry_prompt(prompt_id)

        assert success is True

        prompt = (
            test_db["conn"]
            .execute(
                "SELECT status, retry_count FROM prompts WHERE id = ?",
                (prompt_id,),
            )
            .fetchone()
        )
        assert prompt["status"] == PromptStatus.PENDING
        assert prompt["retry_count"] == 1

    def test_retry_increments_count(self, worker, test_db):
        """Test retry count increments."""
        prompt_id = worker.db.add_prompt("Test task")

        # Fail and retry multiple times
        for i in range(3):
            worker.db.update_prompt_status(
                prompt_id, status=PromptStatus.FAILED
            )
            worker.db.retry_prompt(prompt_id)

        prompt = (
            test_db["conn"]
            .execute(
                "SELECT retry_count FROM prompts WHERE id = ?",
                (prompt_id,),
            )
            .fetchone()
        )
        assert prompt["retry_count"] == 3

    def test_retry_all_failed(self, worker, test_db):
        """Test retrying all failed prompts."""
        # Create failed prompts
        id1 = worker.db.add_prompt("Task 1")
        id2 = worker.db.add_prompt("Task 2")
        id3 = worker.db.add_prompt("Task 3")

        worker.db.update_prompt_status(id1, status=PromptStatus.FAILED)
        worker.db.update_prompt_status(id2, status=PromptStatus.FAILED)
        worker.db.update_prompt_status(id3, status=PromptStatus.COMPLETED)

        # Retry all failed
        count = worker.db.retry_all_failed()

        assert count == 2  # Only id1 and id2

        # Verify status
        statuses = (
            test_db["conn"]
            .execute(
                "SELECT id, status FROM prompts WHERE id IN (?, ?, ?)",
                (id1, id2, id3),
            )
            .fetchall()
        )
        status_map = {s["id"]: s["status"] for s in statuses}
        assert status_map[id1] == PromptStatus.PENDING
        assert status_map[id2] == PromptStatus.PENDING
        assert status_map[id3] == PromptStatus.COMPLETED


@pytest.mark.integration
class TestReassignment:
    """Test prompt reassignment."""

    def test_reassign_prompt(self, worker, test_db):
        """Test reassigning a prompt to a different session."""
        prompt_id = worker.db.add_prompt("Test task")

        # Initial assignment
        worker.db.update_prompt_status(
            prompt_id,
            status=PromptStatus.ASSIGNED,
            session="claude-session",
        )

        # Reassign - sets back to pending with new target_session
        success = worker.db.reassign_prompt(prompt_id, "codex-session")

        assert success is True

        prompt = (
            test_db["conn"]
            .execute(
                """SELECT assigned_session, target_session, status
                   FROM prompts WHERE id = ?""",
                (prompt_id,),
            )
            .fetchone()
        )
        assert prompt["status"] == PromptStatus.PENDING
        assert prompt["target_session"] == "codex-session"
        assert prompt["assigned_session"] is None  # Cleared


@pytest.mark.integration
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_update_nonexistent_prompt(self, worker, test_db):
        """Test updating nonexistent prompt."""
        # Should not raise error, just not update anything
        worker.db.update_prompt_status(
            99999, status=PromptStatus.COMPLETED
        )

    def test_retry_completed_prompt(self, worker, test_db):
        """Test retrying a completed prompt."""
        prompt_id = worker.db.add_prompt("Test task")
        worker.db.update_prompt_status(
            prompt_id, status=PromptStatus.COMPLETED
        )

        success = worker.db.retry_prompt(prompt_id)

        # Should not retry completed prompts
        assert success is False

    def test_max_retries_handling(self, worker, test_db):
        """Test max retries respected by retry_all_failed."""
        # Create prompts with max_retries
        test_db["conn"].execute(
            """INSERT INTO prompts (content, status, retry_count, max_retries)
               VALUES ('Task 1', 'failed', 2, 2),
                      ('Task 2', 'failed', 1, 2)"""
        )
        test_db["conn"].commit()

        # retry_all_failed should only retry Task 2 (retry_count < max_retries)
        count = worker.db.retry_all_failed()

        assert count == 1  # Only Task 2 retried

        # Verify statuses
        prompts = (
            test_db["conn"]
            .execute(
                """SELECT content, status, retry_count FROM prompts
                   WHERE content IN ('Task 1', 'Task 2')
                   ORDER BY content"""
            )
            .fetchall()
        )
        task1, task2 = prompts
        assert task1["status"] == "failed"  # Not retried (at max)
        assert task1["retry_count"] == 2
        assert task2["status"] == "pending"  # Retried
        assert task2["retry_count"] == 2  # Incremented


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
