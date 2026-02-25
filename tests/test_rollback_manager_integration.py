"""
Integration tests for rollback_manager.py

Tests automated rollback functionality, health monitoring, snapshot management,
and database backup/restore operations.
"""

import pytest
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import sys
import sqlite3

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rollback_manager import RollbackManager


@pytest.fixture
def test_env(tmp_path, monkeypatch):
    """Create isolated test environment."""
    # Create test directories
    data_dir = tmp_path / "data"
    snapshots_dir = data_dir / "rollback_snapshots"
    data_dir.mkdir(parents=True, exist_ok=True)
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    # Create test database
    db_path = data_dir / "architect.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, data TEXT)")
    conn.execute("INSERT INTO test_table (data) VALUES ('test data')")
    conn.commit()
    conn.close()

    # Patch paths
    monkeypatch.setattr("rollback_manager.DATA_DIR", data_dir)
    monkeypatch.setattr("rollback_manager.SNAPSHOTS_DIR", snapshots_dir)
    monkeypatch.setattr("rollback_manager.HISTORY_FILE", data_dir / "rollback_history.json")
    monkeypatch.setattr("rollback_manager.STATE_FILE", data_dir / "rollback_state.json")
    monkeypatch.setattr("rollback_manager.DB_FILE", db_path)

    yield {
        "data_dir": data_dir,
        "snapshots_dir": snapshots_dir,
        "db_path": db_path,
        "history_file": data_dir / "rollback_history.json",
        "state_file": data_dir / "rollback_state.json"
    }


@pytest.fixture
def manager(test_env):
    """Create RollbackManager instance with test environment."""
    return RollbackManager(
        health_url="http://localhost:8080/health",
        db_path=str(test_env["db_path"])
    )


@pytest.mark.integration
class TestStateManagement:
    """Test state persistence."""

    def test_state_file_created(self, manager, test_env):
        """Test state file is created on save."""
        manager._save_state()

        assert test_env["state_file"].exists()

    def test_state_persists_snapshot_id(self, manager, test_env):
        """Test snapshot ID persists across instances."""
        manager._current_snapshot_id = "test-snapshot-123"
        manager._save_state()

        # Create new manager instance
        new_manager = RollbackManager(db_path=str(test_env["db_path"]))

        assert new_manager._current_snapshot_id == "test-snapshot-123"

    def test_state_persists_failure_count(self, manager, test_env):
        """Test failure count persists."""
        manager._failure_count = 5
        manager._save_state()

        new_manager = RollbackManager(db_path=str(test_env["db_path"]))

        assert new_manager._failure_count == 5


@pytest.mark.integration
class TestGitOperations:
    """Test git-related operations."""

    def test_get_git_info(self, manager, monkeypatch):
        """Test getting git information."""
        # Mock git command - return different values based on command
        def mock_run(cmd, *args, **kwargs):
            class Result:
                returncode = 0
                stdout = ""

            result = Result()
            if "rev-parse HEAD" in " ".join(cmd):
                result.stdout = "abc123def456"
            elif "rev-parse --abbrev-ref HEAD" in " ".join(cmd):
                result.stdout = "main"
            elif "log -1 --pretty=%B" in " ".join(cmd):
                result.stdout = "Test commit message"
            elif "status --porcelain" in " ".join(cmd):
                result.stdout = ""

            return result

        monkeypatch.setattr("subprocess.run", mock_run)

        git_info = manager._get_git_info()

        assert "commit_sha" in git_info
        assert "branch" in git_info
        assert "commit_message" in git_info

    def test_get_git_info_no_git(self, manager, monkeypatch):
        """Test git info when git is not available."""
        def mock_run(*args, **kwargs):
            raise FileNotFoundError("git not found")

        monkeypatch.setattr("subprocess.run", mock_run)

        git_info = manager._get_git_info()

        # Should return empty dict or handle gracefully
        assert isinstance(git_info, dict)


@pytest.mark.integration
class TestDatabaseBackup:
    """Test database backup operations."""

    def test_backup_database_creates_file(self, manager, test_env):
        """Test database backup creates backup file."""
        snapshot_id = "test-snapshot-001"

        backup_path = manager._backup_database(snapshot_id)

        assert backup_path is not None
        assert Path(backup_path).exists()

    def test_backup_contains_data(self, manager, test_env):
        """Test backup file contains database data."""
        snapshot_id = "test-snapshot-002"

        backup_path = manager._backup_database(snapshot_id)

        # Verify backup has data
        backup_conn = sqlite3.connect(backup_path)
        cursor = backup_conn.execute("SELECT data FROM test_table")
        result = cursor.fetchone()
        backup_conn.close()

        assert result is not None
        assert result[0] == "test data"

    def test_multiple_backups_unique(self, manager, test_env):
        """Test multiple backups create unique files."""
        backup1 = manager._backup_database("snapshot-1")
        backup2 = manager._backup_database("snapshot-2")

        assert backup1 != backup2
        assert Path(backup1).exists()
        assert Path(backup2).exists()


@pytest.mark.integration
class TestDatabaseRestore:
    """Test database restore operations."""

    def test_restore_database(self, manager, test_env):
        """Test restoring database from backup."""
        # Create backup
        backup_path = manager._backup_database("test-snapshot")

        # Modify original database
        conn = sqlite3.connect(test_env["db_path"])
        conn.execute("UPDATE test_table SET data = 'modified data'")
        conn.commit()
        conn.close()

        # Restore from backup
        success = manager._restore_database(backup_path)

        assert success is True

        # Verify data restored
        conn = sqlite3.connect(test_env["db_path"])
        cursor = conn.execute("SELECT data FROM test_table")
        result = cursor.fetchone()
        conn.close()

        assert result[0] == "test data"

    def test_restore_nonexistent_backup(self, manager, test_env):
        """Test restoring from nonexistent backup fails gracefully."""
        success = manager._restore_database("/nonexistent/backup.db")

        assert success is False


@pytest.mark.integration
class TestSnapshotCreation:
    """Test snapshot creation."""

    def test_create_snapshot_basic(self, manager, test_env, monkeypatch):
        """Test creating a basic snapshot."""
        # Mock git info
        def mock_git_info():
            return {
                "commit_sha": "abc123",
                "branch": "main",
                "remote_url": "https://github.com/test/repo.git"
            }

        monkeypatch.setattr(manager, "_get_git_info", mock_git_info)

        snapshot_id = manager.create_snapshot("Test deployment")

        assert snapshot_id is not None
        assert len(snapshot_id) > 0

    def test_snapshot_creates_backup(self, manager, test_env, monkeypatch):
        """Test snapshot creates database backup."""
        def mock_git_info():
            return {"commit_sha": "abc123", "branch": "main"}

        monkeypatch.setattr(manager, "_get_git_info", mock_git_info)

        snapshot_id = manager.create_snapshot("Test")

        # Verify backup file exists
        backup_files = list(test_env["snapshots_dir"].glob("*.db"))
        assert len(backup_files) > 0

    def test_snapshot_metadata_saved(self, manager, test_env, monkeypatch):
        """Test snapshot metadata is saved."""
        def mock_git_info():
            return {"commit_sha": "abc123", "branch": "main"}

        monkeypatch.setattr(manager, "_get_git_info", mock_git_info)

        snapshot_id = manager.create_snapshot("Test deployment")

        # Verify metadata file
        metadata_file = test_env["snapshots_dir"] / f"{snapshot_id}.json"
        assert metadata_file.exists()

        with open(metadata_file) as f:
            metadata = json.load(f)

        assert metadata["description"] == "Test deployment"
        assert "git" in metadata
        assert "created_at" in metadata


@pytest.mark.integration
class TestSnapshotRetrieval:
    """Test snapshot retrieval operations."""

    def test_get_snapshot(self, manager, test_env, monkeypatch):
        """Test getting a specific snapshot."""
        def mock_git_info():
            return {"commit_sha": "abc123", "branch": "main"}

        monkeypatch.setattr(manager, "_get_git_info", mock_git_info)

        snapshot_id = manager.create_snapshot("Test")
        snapshot = manager.get_snapshot(snapshot_id)

        assert snapshot is not None
        assert snapshot["id"] == snapshot_id
        assert snapshot["description"] == "Test"

    def test_get_nonexistent_snapshot(self, manager, test_env):
        """Test getting nonexistent snapshot returns None."""
        snapshot = manager.get_snapshot("nonexistent-id")

        assert snapshot is None

    def test_list_snapshots(self, manager, test_env, monkeypatch):
        """Test listing snapshots."""
        def mock_git_info():
            return {"commit_sha": "abc123", "branch": "main"}

        monkeypatch.setattr(manager, "_get_git_info", mock_git_info)

        # Create snapshots by directly manipulating files to avoid time-based ID collisions
        snapshot1 = {
            "id": "snapshot-001",
            "created_at": "2026-01-01T10:00:00",
            "description": "Snapshot 1",
            "git": {"commit_sha": "abc123", "branch": "main"},
            "database_backup": None
        }
        snapshot2 = {
            "id": "snapshot-002",
            "created_at": "2026-01-01T11:00:00",
            "description": "Snapshot 2",
            "git": {"commit_sha": "abc123", "branch": "main"},
            "database_backup": None
        }

        with open(test_env["snapshots_dir"] / "snapshot-001.json", "w") as f:
            json.dump(snapshot1, f)
        with open(test_env["snapshots_dir"] / "snapshot-002.json", "w") as f:
            json.dump(snapshot2, f)

        snapshots = manager.list_snapshots()

        assert len(snapshots) == 2
        snapshot_ids = [s["id"] for s in snapshots]
        assert "snapshot-001" in snapshot_ids
        assert "snapshot-002" in snapshot_ids

    def test_list_snapshots_limit(self, manager, test_env, monkeypatch):
        """Test listing snapshots with limit."""
        def mock_git_info():
            return {"commit_sha": "abc123", "branch": "main"}

        monkeypatch.setattr(manager, "_get_git_info", mock_git_info)

        # Create 5 snapshots directly as files
        for i in range(5):
            snapshot = {
                "id": f"snapshot-{i:03d}",
                "created_at": f"2026-01-01T{10+i}:00:00",
                "description": f"Snapshot {i}",
                "git": {"commit_sha": "abc123", "branch": "main"},
                "database_backup": None
            }
            with open(test_env["snapshots_dir"] / f"snapshot-{i:03d}.json", "w") as f:
                json.dump(snapshot, f)

        snapshots = manager.list_snapshots(limit=3)

        assert len(snapshots) == 3


@pytest.mark.integration
class TestHistoryTracking:
    """Test rollback history tracking."""

    def test_add_to_history(self, manager, test_env):
        """Test adding entry to history."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "rollback",
            "snapshot_id": "test-123",
            "success": True
        }

        manager._add_to_history(entry)

        # Verify history file
        assert test_env["history_file"].exists()

        with open(test_env["history_file"]) as f:
            history = json.load(f)

        assert len(history) == 1
        assert history[0]["snapshot_id"] == "test-123"

    def test_get_history(self, manager, test_env):
        """Test getting history entries."""
        # Add multiple entries
        for i in range(3):
            entry = {
                "timestamp": datetime.now().isoformat(),
                "action": "rollback",
                "snapshot_id": f"test-{i}",
                "success": True
            }
            manager._add_to_history(entry)

        history = manager.get_history()

        assert len(history) == 3

    def test_history_limit(self, manager, test_env):
        """Test history retrieval with limit."""
        # Add 5 entries
        for i in range(5):
            entry = {
                "timestamp": datetime.now().isoformat(),
                "action": "rollback",
                "snapshot_id": f"test-{i}",
                "success": True
            }
            manager._add_to_history(entry)

        history = manager.get_history(limit=2)

        assert len(history) == 2


@pytest.mark.integration
class TestMonitoringStatus:
    """Test monitoring status tracking."""

    def test_get_monitoring_status_not_active(self, manager, test_env):
        """Test monitoring status when not active."""
        status = manager.get_monitoring_status()

        # When no monitoring thread, active should be None or False (falsy)
        assert not status["active"]

    def test_stop_monitoring(self, manager, test_env):
        """Test stopping monitoring."""
        # Start monitoring (without actual thread)
        manager._monitoring_thread = None
        manager._stop_monitoring.clear()

        manager.stop_health_monitoring()

        assert manager._stop_monitoring.is_set()


@pytest.mark.integration
class TestCleanup:
    """Test snapshot cleanup operations."""

    def test_cleanup_old_snapshots(self, manager, test_env, monkeypatch):
        """Test cleaning up old snapshots."""
        def mock_git_info():
            return {"commit_sha": "abc123", "branch": "main"}

        monkeypatch.setattr(manager, "_get_git_info", mock_git_info)

        # Create 5 snapshots
        snapshot_ids = []
        for i in range(5):
            snapshot_id = manager.create_snapshot(f"Snapshot {i}")
            snapshot_ids.append(snapshot_id)

        # Clean up, keep only 2
        manager.cleanup_old_snapshots(keep_count=2)

        # Verify only 2 remain
        snapshots = manager.list_snapshots()
        assert len(snapshots) <= 2


@pytest.mark.integration
class TestHealthChecking:
    """Test health check operations."""

    def test_check_health_success(self, manager, monkeypatch):
        """Test successful health check."""
        class MockResponse:
            status_code = 200
            def json(self):
                return {"status": "healthy"}

        def mock_get(*args, **kwargs):
            return MockResponse()

        monkeypatch.setattr("requests.get", mock_get)

        result = manager._check_health()

        assert result["healthy"] is True

    def test_check_health_failure(self, manager, monkeypatch):
        """Test failed health check."""
        class MockResponse:
            status_code = 500
            def json(self):
                return {"status": "unhealthy"}

        def mock_get(*args, **kwargs):
            return MockResponse()

        monkeypatch.setattr("requests.get", mock_get)

        result = manager._check_health()

        assert result["healthy"] is False

    def test_check_health_timeout(self, manager, monkeypatch):
        """Test health check timeout."""
        def mock_get(*args, **kwargs):
            raise Exception("Connection timeout")

        monkeypatch.setattr("requests.get", mock_get)

        result = manager._check_health()

        assert result["healthy"] is False


@pytest.mark.integration
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_manager_initialization_no_db(self, tmp_path):
        """Test manager initialization with nonexistent database."""
        manager = RollbackManager(db_path=str(tmp_path / "nonexistent.db"))

        # Should not crash
        assert manager is not None

    def test_empty_snapshots_directory(self, manager, test_env):
        """Test operations with empty snapshots directory."""
        snapshots = manager.list_snapshots()

        assert snapshots == []

    def test_corrupted_state_file(self, manager, test_env):
        """Test loading corrupted state file."""
        # Write invalid JSON
        with open(test_env["state_file"], "w") as f:
            f.write("invalid json {")

        # Should handle gracefully
        new_manager = RollbackManager(db_path=str(test_env["db_path"]))

        assert new_manager is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
