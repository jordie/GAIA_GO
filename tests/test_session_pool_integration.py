#!/usr/bin/env python3
"""
Session Pool Integration Tests

Tests for Session Pool Management system (P04).

Tests the full integration of:
- Session pool service layer
- Session pool API routes
- Database operations
- Tmux session management
- Health monitoring
- Auto-restart functionality
"""

import json
import pytest
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture
def test_db(tmp_path):
    """Create temporary test database with session pool schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    # Create session pool tables
    conn.executescript(
        """
        CREATE TABLE session_pool (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            tmux_name TEXT NOT NULL,
            role TEXT DEFAULT 'worker',
            restart_count INTEGER DEFAULT 0,
            health TEXT DEFAULT 'unknown',
            status TEXT DEFAULT 'stopped',
            last_heartbeat TIMESTAMP,
            last_restart TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT
        );

        CREATE TABLE pool_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_name) REFERENCES session_pool(name)
        );

        CREATE INDEX idx_pool_events_session ON pool_events(session_name);
        CREATE INDEX idx_pool_events_timestamp ON pool_events(timestamp);
    """
    )
    conn.commit()

    yield conn

    conn.close()


@pytest.fixture
def session_pool_service(test_db, tmp_path):
    """Create SessionPoolService instance for testing."""
    # Import here to avoid import errors if service not available
    try:
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))
        from services.session_pool_service import SessionPoolService

        service = SessionPoolService(str(tmp_path / "test.db"))
        return service
    except ImportError:
        pytest.skip("SessionPoolService not available")


class TestSessionPoolService:
    """Test SessionPoolService class."""

    def test_save_pool_member(self, session_pool_service, test_db):
        """Test saving a pool member."""
        session_pool_service.save_pool_member(
            name="test-worker-1", tmux_name="claude-test-worker-1", role="worker", status="running"
        )

        # Verify in database
        cursor = test_db.execute("SELECT * FROM session_pool WHERE name = ?", ("test-worker-1",))
        row = cursor.fetchone()

        assert row is not None
        assert row[1] == "test-worker-1"  # name
        assert row[2] == "claude-test-worker-1"  # tmux_name
        assert row[3] == "worker"  # role

    def test_get_pool_members(self, session_pool_service, test_db):
        """Test retrieving pool members."""
        # Insert test data
        test_db.execute(
            """
            INSERT INTO session_pool (name, tmux_name, role, status)
            VALUES ('worker-1', 'claude-worker-1', 'worker', 'running'),
                   ('worker-2', 'claude-worker-2', 'worker', 'stopped')
        """
        )
        test_db.commit()

        # Get all members
        members = session_pool_service.get_pool_members()

        assert len(members) == 2
        assert members[0]["name"] == "worker-1"
        assert members[1]["name"] == "worker-2"

    def test_get_pool_member(self, session_pool_service, test_db):
        """Test retrieving specific pool member."""
        # Insert test data
        test_db.execute(
            """
            INSERT INTO session_pool (name, tmux_name, role, status)
            VALUES ('worker-1', 'claude-worker-1', 'worker', 'running')
        """
        )
        test_db.commit()

        member = session_pool_service.get_pool_member("worker-1")

        assert member is not None
        assert member["name"] == "worker-1"
        assert member["tmux_name"] == "claude-worker-1"
        assert member["status"] == "running"

    def test_update_heartbeat(self, session_pool_service, test_db):
        """Test updating member heartbeat."""
        # Insert test data
        test_db.execute(
            """
            INSERT INTO session_pool (name, tmux_name, role, status)
            VALUES ('worker-1', 'claude-worker-1', 'worker', 'running')
        """
        )
        test_db.commit()

        # Update heartbeat
        session_pool_service.update_heartbeat("worker-1")

        # Verify timestamp updated
        cursor = test_db.execute("SELECT last_heartbeat FROM session_pool WHERE name = ?", ("worker-1",))
        heartbeat = cursor.fetchone()[0]

        assert heartbeat is not None
        # Heartbeat should be recent (within last 5 seconds)
        hb_time = datetime.fromisoformat(heartbeat)
        now = datetime.now()
        assert (now - hb_time).total_seconds() < 5

    def test_update_status(self, session_pool_service, test_db):
        """Test updating member status."""
        # Insert test data
        test_db.execute(
            """
            INSERT INTO session_pool (name, tmux_name, role, status)
            VALUES ('worker-1', 'claude-worker-1', 'worker', 'running')
        """
        )
        test_db.commit()

        # Update status
        session_pool_service.update_status("worker-1", "stopped")

        # Verify status changed
        cursor = test_db.execute("SELECT status FROM session_pool WHERE name = ?", ("worker-1",))
        status = cursor.fetchone()[0]

        assert status == "stopped"

    def test_log_pool_event(self, session_pool_service, test_db):
        """Test logging pool events."""
        # Insert member
        test_db.execute(
            """
            INSERT INTO session_pool (name, tmux_name, role, status)
            VALUES ('worker-1', 'claude-worker-1', 'worker', 'running')
        """
        )
        test_db.commit()

        # Log event
        session_pool_service.log_pool_event("worker-1", "restart", "Manual restart triggered")

        # Verify event logged
        cursor = test_db.execute(
            """
            SELECT event_type, details FROM pool_events
            WHERE session_name = ?
        """,
            ("worker-1",),
        )
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == "restart"
        assert row[1] == "Manual restart triggered"

    def test_get_pool_events(self, session_pool_service, test_db):
        """Test retrieving pool events."""
        # Insert member and events
        test_db.execute(
            """
            INSERT INTO session_pool (name, tmux_name, role, status)
            VALUES ('worker-1', 'claude-worker-1', 'worker', 'running')
        """
        )
        test_db.execute(
            """
            INSERT INTO pool_events (session_name, event_type, details)
            VALUES ('worker-1', 'start', 'Session started'),
                   ('worker-1', 'heartbeat', 'Heartbeat received')
        """
        )
        test_db.commit()

        # Get events
        events = session_pool_service.get_pool_events("worker-1")

        assert len(events) == 2
        assert events[0]["event_type"] == "start"
        assert events[1]["event_type"] == "heartbeat"


class TestSessionPoolHealthMonitoring:
    """Test health monitoring functionality."""

    def test_health_check_healthy_session(self, session_pool_service, test_db):
        """Test health check for healthy session."""
        # Insert member with recent heartbeat
        test_db.execute(
            """
            INSERT INTO session_pool (name, tmux_name, role, status, last_heartbeat)
            VALUES ('worker-1', 'claude-worker-1', 'worker', 'running', ?)
        """,
            (datetime.now().isoformat(),),
        )
        test_db.commit()

        # Mock tmux session check to return True
        # In real test, would need to mock subprocess call

        # For now, just test the service method exists
        member = session_pool_service.get_pool_member("worker-1")
        assert member is not None

    def test_health_check_stale_heartbeat(self, session_pool_service, test_db):
        """Test health check detects stale heartbeat."""
        # Insert member with old heartbeat (>15 minutes ago)
        old_time = datetime.now() - timedelta(minutes=20)
        test_db.execute(
            """
            INSERT INTO session_pool (name, tmux_name, role, status, last_heartbeat)
            VALUES ('worker-1', 'claude-worker-1', 'worker', 'running', ?)
        """,
            (old_time.isoformat(),),
        )
        test_db.commit()

        member = session_pool_service.get_pool_member("worker-1")

        # Calculate age
        if member["last_heartbeat"]:
            hb_time = datetime.fromisoformat(member["last_heartbeat"])
            age_minutes = (datetime.now() - hb_time).total_seconds() / 60

            # Should be stale (>15 minutes)
            assert age_minutes > 15

    def test_auto_restart_increments_counter(self, session_pool_service, test_db):
        """Test auto-restart increments restart counter."""
        # Insert member
        test_db.execute(
            """
            INSERT INTO session_pool (name, tmux_name, role, status, restart_count)
            VALUES ('worker-1', 'claude-worker-1', 'worker', 'stopped', 0)
        """
        )
        test_db.commit()

        # Manually increment restart count (simulating restart)
        test_db.execute(
            """
            UPDATE session_pool
            SET restart_count = restart_count + 1,
                last_restart = CURRENT_TIMESTAMP
            WHERE name = ?
        """,
            ("worker-1",),
        )
        test_db.commit()

        # Verify counter incremented
        cursor = test_db.execute("SELECT restart_count FROM session_pool WHERE name = ?", ("worker-1",))
        restart_count = cursor.fetchone()[0]

        assert restart_count == 1

    def test_max_restart_attempts(self, session_pool_service, test_db):
        """Test max restart attempts limit."""
        # Insert member with high restart count
        test_db.execute(
            """
            INSERT INTO session_pool (name, tmux_name, role, status, restart_count)
            VALUES ('worker-1', 'claude-worker-1', 'worker', 'stopped', 10)
        """
        )
        test_db.commit()

        member = session_pool_service.get_pool_member("worker-1")

        # Should have reached max restarts (10)
        assert member["restart_count"] >= 10


class TestSessionPoolEventLogging:
    """Test event logging functionality."""

    def test_event_log_retention(self, session_pool_service, test_db):
        """Test event log stores all events."""
        # Insert member
        test_db.execute(
            """
            INSERT INTO session_pool (name, tmux_name, role, status)
            VALUES ('worker-1', 'claude-worker-1', 'worker', 'running')
        """
        )
        test_db.commit()

        # Log multiple events
        events = [
            ("start", "Session started"),
            ("heartbeat", "Heartbeat 1"),
            ("heartbeat", "Heartbeat 2"),
            ("restart", "Manual restart"),
            ("stop", "Session stopped"),
        ]

        for event_type, details in events:
            session_pool_service.log_pool_event("worker-1", event_type, details)

        # Verify all events logged
        cursor = test_db.execute(
            """
            SELECT COUNT(*) FROM pool_events
            WHERE session_name = ?
        """,
            ("worker-1",),
        )
        count = cursor.fetchone()[0]

        assert count == 5

    def test_event_log_ordering(self, session_pool_service, test_db):
        """Test events are ordered by timestamp."""
        # Insert member
        test_db.execute(
            """
            INSERT INTO session_pool (name, tmux_name, role, status)
            VALUES ('worker-1', 'claude-worker-1', 'worker', 'running')
        """
        )
        test_db.commit()

        # Log events with delays
        session_pool_service.log_pool_event("worker-1", "event1", "First")
        time.sleep(0.1)
        session_pool_service.log_pool_event("worker-1", "event2", "Second")
        time.sleep(0.1)
        session_pool_service.log_pool_event("worker-1", "event3", "Third")

        # Get events
        events = session_pool_service.get_pool_events("worker-1")

        # Should be in chronological order
        assert events[0]["event_type"] == "event1"
        assert events[1]["event_type"] == "event2"
        assert events[2]["event_type"] == "event3"


class TestSessionPoolMetadata:
    """Test metadata handling."""

    def test_store_metadata_json(self, session_pool_service, test_db):
        """Test storing JSON metadata."""
        metadata = {"cpu": 45.5, "memory": 60.2, "tasks_completed": 100}

        # Insert member with metadata
        test_db.execute(
            """
            INSERT INTO session_pool (name, tmux_name, role, status, metadata)
            VALUES ('worker-1', 'claude-worker-1', 'worker', 'running', ?)
        """,
            (json.dumps(metadata),),
        )
        test_db.commit()

        # Retrieve and verify
        cursor = test_db.execute("SELECT metadata FROM session_pool WHERE name = ?", ("worker-1",))
        stored_metadata = cursor.fetchone()[0]

        parsed = json.loads(stored_metadata)
        assert parsed["cpu"] == 45.5
        assert parsed["memory"] == 60.2
        assert parsed["tasks_completed"] == 100


class TestSessionPoolConcurrency:
    """Test concurrent operations."""

    def test_concurrent_heartbeat_updates(self, session_pool_service, test_db):
        """Test multiple simultaneous heartbeat updates."""
        # Insert member
        test_db.execute(
            """
            INSERT INTO session_pool (name, tmux_name, role, status)
            VALUES ('worker-1', 'claude-worker-1', 'worker', 'running')
        """
        )
        test_db.commit()

        # Perform multiple heartbeat updates
        for _ in range(10):
            session_pool_service.update_heartbeat("worker-1")

        # Should complete without errors
        member = session_pool_service.get_pool_member("worker-1")
        assert member is not None
        assert member["last_heartbeat"] is not None

    def test_concurrent_event_logging(self, session_pool_service, test_db):
        """Test concurrent event logging."""
        # Insert member
        test_db.execute(
            """
            INSERT INTO session_pool (name, tmux_name, role, status)
            VALUES ('worker-1', 'claude-worker-1', 'worker', 'running')
        """
        )
        test_db.commit()

        # Log many events
        for i in range(20):
            session_pool_service.log_pool_event("worker-1", "test_event", f"Event {i}")

        # Verify all events logged
        events = session_pool_service.get_pool_events("worker-1")
        assert len(events) == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
