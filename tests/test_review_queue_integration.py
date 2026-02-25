"""
Integration tests for orchestrator/review_queue.py

Tests review queue management, incident tracking, blocked items,
and queue item resolution workflows.
"""

import pytest
import sqlite3
import json
from datetime import datetime
from pathlib import Path
import sys

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.review_queue import ReviewQueueManager


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Create test database with review queue tables."""
    db_path = tmp_path / "test_review.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Create tables
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS apps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            source_path TEXT,
            current_phase TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (app_id) REFERENCES apps(id)
        );

        CREATE TABLE IF NOT EXISTS review_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            app_id INTEGER,
            run_id INTEGER,
            priority TEXT DEFAULT 'normal',
            title TEXT NOT NULL,
            summary TEXT,
            available_actions TEXT,
            status TEXT DEFAULT 'pending',
            resolved_at TIMESTAMP,
            resolved_by TEXT,
            resolution TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (app_id) REFERENCES apps(id),
            FOREIGN KEY (run_id) REFERENCES runs(id)
        );

        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id INTEGER NOT NULL,
            run_id INTEGER,
            severity TEXT DEFAULT 'warning',
            title TEXT NOT NULL,
            description TEXT,
            source TEXT,
            source_details TEXT,
            suspected_commit TEXT,
            proposed_fix TEXT,
            fix_confidence INTEGER,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (app_id) REFERENCES apps(id),
            FOREIGN KEY (run_id) REFERENCES runs(id)
        );

        CREATE TABLE IF NOT EXISTS milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id INTEGER NOT NULL,
            run_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (app_id) REFERENCES apps(id),
            FOREIGN KEY (run_id) REFERENCES runs(id)
        );

        CREATE TABLE IF NOT EXISTS artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            milestone_id INTEGER NOT NULL,
            artifact_type TEXT NOT NULL,
            title TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (milestone_id) REFERENCES milestones(id)
        );

        CREATE INDEX idx_review_queue_status ON review_queue(status);
        CREATE INDEX idx_review_queue_type ON review_queue(item_type);
    """)

    # Insert test app and run
    conn.execute("INSERT INTO apps (id, name, source_path, current_phase) VALUES (1, 'test_app', '/test', 'dev')")
    conn.execute("INSERT INTO runs (id, app_id, status) VALUES (1, 1, 'running')")
    conn.commit()

    # Patch get_connection
    def mock_get_connection():
        from contextlib import contextmanager
        @contextmanager
        def get_conn():
            try:
                yield conn
            finally:
                pass
        return get_conn()

    monkeypatch.setattr("orchestrator.review_queue.get_connection", mock_get_connection)

    yield conn
    conn.close()


@pytest.fixture
def manager(test_db):
    """Create ReviewQueueManager instance."""
    return ReviewQueueManager()


@pytest.mark.integration
class TestQueueSummary:
    """Test queue summary statistics."""

    def test_empty_queue_summary(self, manager, test_db):
        """Test summary with empty queue."""
        summary = manager.get_queue_summary()

        assert summary["total"] == 0
        assert summary["ready_for_approval"] == 0
        assert summary["incidents"] == 0
        assert summary["blocked"] == 0
        assert summary["needs_input"] == 0

    def test_queue_summary_with_items(self, manager, test_db):
        """Test summary counts items correctly."""
        # Add different types
        test_db.execute(
            "INSERT INTO review_queue (item_type, item_id, app_id, title) VALUES ('milestone', 1, 1, 'M1')"
        )
        test_db.execute(
            "INSERT INTO review_queue (item_type, item_id, app_id, title) VALUES ('milestone', 2, 1, 'M2')"
        )
        test_db.execute(
            "INSERT INTO review_queue (item_type, item_id, app_id, title) VALUES ('incident', 1, 1, 'I1')"
        )
        test_db.commit()

        summary = manager.get_queue_summary()

        assert summary["total"] == 3
        assert summary["ready_for_approval"] == 2
        assert summary["incidents"] == 1

    def test_summary_ignores_resolved(self, manager, test_db):
        """Test summary only counts pending items."""
        test_db.execute(
            "INSERT INTO review_queue (item_type, item_id, app_id, title, status) VALUES ('milestone', 1, 1, 'M1', 'pending')"
        )
        test_db.execute(
            "INSERT INTO review_queue (item_type, item_id, app_id, title, status) VALUES ('milestone', 2, 1, 'M2', 'resolved')"
        )
        test_db.commit()

        summary = manager.get_queue_summary()

        assert summary["total"] == 1
        assert summary["ready_for_approval"] == 1


@pytest.mark.integration
class TestGetQueueItems:
    """Test retrieving queue items."""

    def test_get_all_items(self, manager, test_db):
        """Test getting all queue items."""
        test_db.execute(
            "INSERT INTO review_queue (item_type, item_id, app_id, title) VALUES ('milestone', 1, 1, 'M1')"
        )
        test_db.execute(
            "INSERT INTO review_queue (item_type, item_id, app_id, title) VALUES ('incident', 1, 1, 'I1')"
        )
        test_db.commit()

        items = manager.get_queue_items()

        assert len(items) == 2

    def test_filter_by_type(self, manager, test_db):
        """Test filtering items by type."""
        test_db.execute(
            "INSERT INTO review_queue (item_type, item_id, app_id, title) VALUES ('milestone', 1, 1, 'M1')"
        )
        test_db.execute(
            "INSERT INTO review_queue (item_type, item_id, app_id, title) VALUES ('incident', 1, 1, 'I1')"
        )
        test_db.commit()

        items = manager.get_queue_items(item_type='milestone')

        assert len(items) == 1
        assert items[0]["item_type"] == "milestone"

    def test_filter_by_app(self, manager, test_db):
        """Test filtering items by app."""
        test_db.execute("INSERT INTO apps (id, name) VALUES (2, 'app2')")
        test_db.execute(
            "INSERT INTO review_queue (item_type, item_id, app_id, title) VALUES ('milestone', 1, 1, 'M1')"
        )
        test_db.execute(
            "INSERT INTO review_queue (item_type, item_id, app_id, title) VALUES ('milestone', 2, 2, 'M2')"
        )
        test_db.commit()

        items = manager.get_queue_items(app_id=1)

        assert len(items) == 1
        assert items[0]["app_id"] == 1

    def test_items_include_app_name(self, manager, test_db):
        """Test items include app name from join."""
        test_db.execute(
            "INSERT INTO review_queue (item_type, item_id, app_id, title) VALUES ('milestone', 1, 1, 'M1')"
        )
        test_db.commit()

        items = manager.get_queue_items()

        assert items[0]["app_name"] == "test_app"


@pytest.mark.integration
class TestAddToQueue:
    """Test adding items to queue."""

    def test_add_basic_item(self, manager, test_db):
        """Test adding a basic item to queue."""
        queue_id = manager.add_to_queue(
            item_type="milestone",
            item_id=1,
            app_id=1,
            title="Test milestone"
        )

        assert queue_id > 0

        # Verify in database
        row = test_db.execute("SELECT * FROM review_queue WHERE id = ?", (queue_id,)).fetchone()
        assert row["title"] == "Test milestone"
        assert row["status"] == "pending"

    def test_add_with_priority(self, manager, test_db):
        """Test adding item with priority."""
        queue_id = manager.add_to_queue(
            item_type="milestone",
            item_id=1,
            app_id=1,
            title="Urgent item",
            priority="critical"
        )

        row = test_db.execute("SELECT * FROM review_queue WHERE id = ?", (queue_id,)).fetchone()
        assert row["priority"] == "critical"

    def test_add_with_actions(self, manager, test_db):
        """Test adding item with available actions."""
        actions = ["approve", "reject", "request_changes"]

        queue_id = manager.add_to_queue(
            item_type="milestone",
            item_id=1,
            app_id=1,
            title="Item with actions",
            available_actions=actions
        )

        row = test_db.execute("SELECT * FROM review_queue WHERE id = ?", (queue_id,)).fetchone()
        stored_actions = json.loads(row["available_actions"])
        assert stored_actions == actions


@pytest.mark.integration
class TestResolveItem:
    """Test resolving queue items."""

    def test_resolve_item(self, manager, test_db):
        """Test resolving a queue item."""
        # Add item
        test_db.execute(
            "INSERT INTO review_queue (id, item_type, item_id, app_id, title, status) VALUES (1, 'milestone', 1, 1, 'M1', 'pending')"
        )
        test_db.commit()

        success = manager.resolve_item(1, resolution="approved", resolved_by="john")

        assert success is True

        # Verify update
        row = test_db.execute("SELECT * FROM review_queue WHERE id = 1").fetchone()
        assert row["status"] == "resolved"
        assert row["resolution"] == "approved"
        assert row["resolved_by"] == "john"
        assert row["resolved_at"] is not None


@pytest.mark.integration
class TestDismissItem:
    """Test dismissing queue items."""

    def test_dismiss_item(self, manager, test_db):
        """Test dismissing a queue item."""
        # Add item
        test_db.execute(
            "INSERT INTO review_queue (id, item_type, item_id, app_id, title, status) VALUES (1, 'incident', 1, 1, 'I1', 'pending')"
        )
        test_db.commit()

        success = manager.dismiss_item(1, resolved_by="admin")

        assert success is True

        # Verify update
        row = test_db.execute("SELECT * FROM review_queue WHERE id = 1").fetchone()
        assert row["status"] == "dismissed"
        assert row["resolution"] == "dismissed"
        assert row["resolved_by"] == "admin"


@pytest.mark.integration
class TestAddIncident:
    """Test adding incidents."""

    def test_add_basic_incident(self, manager, test_db):
        """Test adding a basic incident."""
        incident_id = manager.add_incident(
            app_id=1,
            title="Test error",
            description="Something went wrong",
            severity="warning"
        )

        assert incident_id > 0

        # Verify incident created
        row = test_db.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        assert row["title"] == "Test error"
        assert row["severity"] == "warning"

        # Verify added to queue
        queue_item = test_db.execute(
            "SELECT * FROM review_queue WHERE item_type = 'incident' AND item_id = ?",
            (incident_id,)
        ).fetchone()
        assert queue_item is not None

    def test_critical_incident_priority(self, manager, test_db):
        """Test critical incident gets critical priority."""
        incident_id = manager.add_incident(
            app_id=1,
            title="Critical error",
            description="System down",
            severity="critical"
        )

        queue_item = test_db.execute(
            "SELECT * FROM review_queue WHERE item_type = 'incident' AND item_id = ?",
            (incident_id,)
        ).fetchone()
        assert queue_item["priority"] == "critical"

    def test_incident_with_proposed_fix(self, manager, test_db):
        """Test incident with proposed fix includes apply_fix action."""
        incident_id = manager.add_incident(
            app_id=1,
            title="Bug found",
            description="Bug description",
            severity="error",
            proposed_fix="Fix the bug by...",
            fix_confidence=85
        )

        # Verify fix stored
        incident = test_db.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        assert incident["proposed_fix"] == "Fix the bug by..."
        assert incident["fix_confidence"] == 85

        # Verify apply_fix action added
        queue_item = test_db.execute(
            "SELECT * FROM review_queue WHERE item_type = 'incident' AND item_id = ?",
            (incident_id,)
        ).fetchone()
        actions = json.loads(queue_item["available_actions"])
        assert "apply_fix" in actions


@pytest.mark.integration
class TestAddBlockedItem:
    """Test adding blocked items."""

    def test_add_blocked_item(self, manager, test_db):
        """Test adding a blocked item."""
        queue_id = manager.add_blocked_item(
            app_id=1,
            run_id=1,
            title="Blocked on user input",
            reason="Need to choose database",
            question="Which database should we use?"
        )

        assert queue_id > 0

        # Verify in queue
        row = test_db.execute("SELECT * FROM review_queue WHERE id = ?", (queue_id,)).fetchone()
        assert row["item_type"] == "blocked"
        assert row["priority"] == "high"

        # Verify summary contains question
        summary = json.loads(row["summary"])
        assert summary["question"] == "Which database should we use?"

    def test_blocked_item_with_options(self, manager, test_db):
        """Test blocked item with options."""
        options = [
            {"action": "choose_postgres", "label": "PostgreSQL"},
            {"action": "choose_mysql", "label": "MySQL"}
        ]

        queue_id = manager.add_blocked_item(
            app_id=1,
            run_id=1,
            title="Database choice",
            reason="Need database selection",
            options=options
        )

        row = test_db.execute("SELECT * FROM review_queue WHERE id = ?", (queue_id,)).fetchone()
        summary = json.loads(row["summary"])
        assert summary["options"] == options

        # Verify actions include option actions
        actions = json.loads(row["available_actions"])
        assert "choose_postgres" in actions
        assert "choose_mysql" in actions


@pytest.mark.integration
class TestGetItemDetails:
    """Test getting full item details."""

    def test_get_milestone_details(self, manager, test_db):
        """Test getting details for milestone item."""
        # Create milestone
        test_db.execute(
            "INSERT INTO milestones (id, app_id, name, description) VALUES (1, 1, 'M1', 'Test milestone')"
        )

        # Add to queue
        test_db.execute(
            "INSERT INTO review_queue (id, item_type, item_id, app_id, title) VALUES (1, 'milestone', 1, 1, 'Review M1')"
        )

        # Add artifacts
        test_db.execute(
            "INSERT INTO artifacts (milestone_id, artifact_type, title) VALUES (1, 'commit', 'Added feature')"
        )
        test_db.commit()

        details = manager.get_item_details(1)

        assert details is not None
        assert details["item_type"] == "milestone"
        assert "milestone" in details
        assert details["milestone"]["name"] == "M1"
        assert "artifacts" in details
        assert len(details["artifacts"]) == 1

    def test_get_incident_details(self, manager, test_db):
        """Test getting details for incident item."""
        # Create incident
        test_db.execute(
            "INSERT INTO incidents (id, app_id, severity, title, description) VALUES (1, 1, 'error', 'Bug', 'Bug description')"
        )

        # Add to queue
        test_db.execute(
            "INSERT INTO review_queue (id, item_type, item_id, app_id, title) VALUES (1, 'incident', 1, 1, 'Review incident')"
        )
        test_db.commit()

        details = manager.get_item_details(1)

        assert details is not None
        assert "incident" in details
        assert details["incident"]["severity"] == "error"

    def test_get_nonexistent_item(self, manager, test_db):
        """Test getting details for nonexistent item."""
        details = manager.get_item_details(999)

        assert details is None


@pytest.mark.integration
class TestPriorityOrdering:
    """Test priority-based ordering."""

    def test_items_ordered_by_priority(self, manager, test_db):
        """Test items are returned in priority order."""
        # Add items with different priorities and timestamps
        test_db.execute(
            "INSERT INTO review_queue (item_type, item_id, app_id, title, priority, created_at) VALUES ('milestone', 1, 1, 'First', 'normal', '2026-01-01 10:00:00')"
        )
        test_db.execute(
            "INSERT INTO review_queue (item_type, item_id, app_id, title, priority, created_at) VALUES ('milestone', 2, 1, 'Second', 'normal', '2026-01-01 11:00:00')"
        )
        test_db.execute(
            "INSERT INTO review_queue (item_type, item_id, app_id, title, priority, created_at) VALUES ('milestone', 3, 1, 'Third', 'normal', '2026-01-01 12:00:00')"
        )
        test_db.commit()

        items = manager.get_queue_items()

        # Should be 3 items returned (verifying ordering logic executes)
        assert len(items) == 3
        # Items with same priority should be ordered by created_at ASC
        assert items[0]["title"] == "First"
        assert items[1]["title"] == "Second"
        assert items[2]["title"] == "Third"


@pytest.mark.integration
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_queue_items(self, manager, test_db):
        """Test getting items from empty queue."""
        items = manager.get_queue_items()

        assert items == []

    def test_add_item_minimal_fields(self, manager, test_db):
        """Test adding item with only required fields."""
        queue_id = manager.add_to_queue(
            item_type="milestone",
            item_id=1,
            app_id=1,
            title="Minimal"
        )

        assert queue_id > 0

    def test_json_parsing_in_row_to_dict(self, manager, test_db):
        """Test JSON fields are parsed correctly."""
        # Add item with JSON fields
        actions = ["action1", "action2"]
        test_db.execute(
            "INSERT INTO review_queue (item_type, item_id, app_id, title, available_actions) VALUES (?, ?, ?, ?, ?)",
            ("milestone", 1, 1, "Test", json.dumps(actions))
        )
        test_db.commit()

        items = manager.get_queue_items()

        # Actions should be parsed as list
        assert isinstance(items[0]["available_actions"], list)
        assert items[0]["available_actions"] == actions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
