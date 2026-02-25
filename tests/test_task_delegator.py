#!/usr/bin/env python3
"""
Tests for task_delegator.py
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import after path setup
import task_delegator as td


class TestTaskDelegatorDB(unittest.TestCase):
    """Test database operations"""

    def setUp(self):
        """Create temp database for each test"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.original_db_path = td.DB_PATH
        td.DB_PATH = self.temp_db.name

    def tearDown(self):
        """Clean up temp database"""
        td.DB_PATH = self.original_db_path
        try:
            os.unlink(self.temp_db.name)
        except:
            pass

    def test_init_db_creates_tables(self):
        """Test that init_db creates required tables"""
        conn = td.init_db()

        # Check tasks table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
        self.assertIsNotNone(cursor.fetchone())

        # Check environments table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='environments'"
        )
        self.assertIsNotNone(cursor.fetchone())

        conn.close()

    def test_init_db_creates_environments(self):
        """Test that init_db creates 5 environments"""
        conn = td.init_db()

        cursor = conn.execute("SELECT COUNT(*) FROM environments")
        count = cursor.fetchone()[0]
        self.assertEqual(count, 5)

        conn.close()

    def test_init_db_idempotent(self):
        """Test that init_db can be called multiple times"""
        conn1 = td.init_db()
        conn1.close()

        conn2 = td.init_db()
        cursor = conn2.execute("SELECT COUNT(*) FROM environments")
        count = cursor.fetchone()[0]
        self.assertEqual(count, 5)
        conn2.close()


class TestTaskOperations(unittest.TestCase):
    """Test task CRUD operations"""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.original_db_path = td.DB_PATH
        td.DB_PATH = self.temp_db.name
        self.conn = td.init_db()

    def tearDown(self):
        self.conn.close()
        td.DB_PATH = self.original_db_path
        try:
            os.unlink(self.temp_db.name)
        except:
            pass

    def test_add_task(self):
        """Test adding a task"""
        self.conn.execute(
            "INSERT INTO tasks (description, priority) VALUES (?, ?)", ("Test task", "normal")
        )
        self.conn.commit()

        cursor = self.conn.execute("SELECT description, priority, status FROM tasks WHERE id=1")
        row = cursor.fetchone()

        self.assertEqual(row[0], "Test task")
        self.assertEqual(row[1], "normal")
        self.assertEqual(row[2], "pending")

    def test_add_high_priority_task(self):
        """Test adding a high priority task"""
        self.conn.execute(
            "INSERT INTO tasks (description, priority) VALUES (?, ?)", ("Urgent task", "high")
        )
        self.conn.commit()

        cursor = self.conn.execute("SELECT priority FROM tasks WHERE id=1")
        self.assertEqual(cursor.fetchone()[0], "high")

    def test_assign_task_to_environment(self):
        """Test assigning a task to an environment"""
        # Add task
        self.conn.execute("INSERT INTO tasks (description) VALUES (?)", ("Test task",))
        self.conn.commit()

        # Assign to env 1
        self.conn.execute(
            "UPDATE tasks SET status='running', assigned_env=?, assigned_session=? WHERE id=?",
            (1, "test_worker", 1),
        )
        self.conn.execute(
            "UPDATE environments SET status='busy', current_task_id=?, session_name=? WHERE env_id=?",
            (1, "test_worker", 1),
        )
        self.conn.commit()

        # Verify task
        cursor = self.conn.execute(
            "SELECT status, assigned_env, assigned_session FROM tasks WHERE id=1"
        )
        row = cursor.fetchone()
        self.assertEqual(row[0], "running")
        self.assertEqual(row[1], 1)
        self.assertEqual(row[2], "test_worker")

        # Verify environment
        cursor = self.conn.execute(
            "SELECT status, current_task_id, session_name FROM environments WHERE env_id=1"
        )
        row = cursor.fetchone()
        self.assertEqual(row[0], "busy")
        self.assertEqual(row[1], 1)
        self.assertEqual(row[2], "test_worker")

    def test_complete_task(self):
        """Test completing a task"""
        # Add and assign task
        self.conn.execute(
            "INSERT INTO tasks (description, status, assigned_env) VALUES (?, ?, ?)",
            ("Test task", "running", 1),
        )
        self.conn.execute("UPDATE environments SET status='busy', current_task_id=1 WHERE env_id=1")
        self.conn.commit()

        # Complete task
        self.conn.execute("UPDATE tasks SET status='completed' WHERE id=1")
        self.conn.execute(
            "UPDATE environments SET status='idle', current_task_id=NULL WHERE env_id=1"
        )
        self.conn.commit()

        # Verify
        cursor = self.conn.execute("SELECT status FROM tasks WHERE id=1")
        self.assertEqual(cursor.fetchone()[0], "completed")

        cursor = self.conn.execute(
            "SELECT status, current_task_id FROM environments WHERE env_id=1"
        )
        row = cursor.fetchone()
        self.assertEqual(row[0], "idle")
        self.assertIsNone(row[1])


class TestEnvironmentOperations(unittest.TestCase):
    """Test environment operations"""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.original_db_path = td.DB_PATH
        td.DB_PATH = self.temp_db.name
        self.conn = td.init_db()

    def tearDown(self):
        self.conn.close()
        td.DB_PATH = self.original_db_path
        try:
            os.unlink(self.temp_db.name)
        except:
            pass

    def test_all_environments_start_idle(self):
        """Test that all environments start as idle"""
        cursor = self.conn.execute("SELECT status FROM environments")
        for row in cursor.fetchall():
            self.assertEqual(row[0], "idle")

    def test_environment_becomes_busy(self):
        """Test environment status changes to busy"""
        self.conn.execute("UPDATE environments SET status='busy' WHERE env_id=1")
        self.conn.commit()

        cursor = self.conn.execute("SELECT status FROM environments WHERE env_id=1")
        self.assertEqual(cursor.fetchone()[0], "busy")

    def test_find_idle_environment(self):
        """Test finding an idle environment"""
        # Mark first 3 as busy
        for i in range(1, 4):
            self.conn.execute("UPDATE environments SET status='busy' WHERE env_id=?", (i,))
        self.conn.commit()

        # Find idle
        cursor = self.conn.execute(
            "SELECT env_id FROM environments WHERE status='idle' ORDER BY env_id LIMIT 1"
        )
        result = cursor.fetchone()
        self.assertEqual(result[0], 4)


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions"""

    @patch("subprocess.run")
    def test_get_env_branch(self, mock_run):
        """Test getting git branch for environment"""
        mock_run.return_value = MagicMock(stdout="feature/test-branch\n")

        with patch.object(Path, "exists", return_value=True):
            branch = td.get_env_branch(1)

        self.assertEqual(branch, "feature/test-branch")

    @patch("subprocess.run")
    def test_get_env_branch_no_repo(self, mock_run):
        """Test getting branch when no repo exists"""
        with patch.object(Path, "exists", return_value=False):
            branch = td.get_env_branch(1)

        self.assertIsNone(branch)

    @patch("subprocess.run")
    def test_get_tmux_sessions(self, mock_run):
        """Test getting tmux sessions"""
        mock_run.return_value = MagicMock(stdout="session1\nsession2\nsession3\n")

        sessions = td.get_tmux_sessions()

        self.assertEqual(len(sessions), 3)
        self.assertIn("session1", sessions)

    @patch("subprocess.run")
    def test_get_tmux_sessions_empty(self, mock_run):
        """Test getting tmux sessions when none exist"""
        mock_run.return_value = MagicMock(stdout="")

        sessions = td.get_tmux_sessions()

        self.assertEqual(sessions, [])

    @patch("subprocess.run")
    def test_send_to_session(self, mock_run):
        """Test sending command to tmux session"""
        mock_run.return_value = MagicMock()

        result = td.send_to_session("test_session", "test message")

        self.assertTrue(result)
        mock_run.assert_called_once()


class TestCLIMode(unittest.TestCase):
    """Test CLI mode commands"""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.original_db_path = td.DB_PATH
        td.DB_PATH = self.temp_db.name
        td.init_db()

    def tearDown(self):
        td.DB_PATH = self.original_db_path
        try:
            os.unlink(self.temp_db.name)
        except:
            pass

    def test_cli_add_command(self):
        """Test CLI add command"""
        original_argv = sys.argv
        sys.argv = ["task_delegator.py", "add", "Test CLI task"]

        result = td.cli_mode()

        sys.argv = original_argv
        self.assertTrue(result)

        # Verify task was added
        conn = sqlite3.connect(self.temp_db.name)
        cursor = conn.execute("SELECT description FROM tasks WHERE id=1")
        self.assertEqual(cursor.fetchone()[0], "Test CLI task")
        conn.close()

    def test_cli_status_command(self):
        """Test CLI status command"""
        original_argv = sys.argv
        sys.argv = ["task_delegator.py", "status"]

        result = td.cli_mode()

        sys.argv = original_argv
        self.assertTrue(result)

    def test_cli_list_command(self):
        """Test CLI list command"""
        # Add a task first
        conn = sqlite3.connect(self.temp_db.name)
        conn.execute("INSERT INTO tasks (description) VALUES ('Test task')")
        conn.commit()
        conn.close()

        original_argv = sys.argv
        sys.argv = ["task_delegator.py", "list"]

        result = td.cli_mode()

        sys.argv = original_argv
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
