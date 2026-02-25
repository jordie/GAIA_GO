"""
Integration tests for orchestrator/milestone_tracker.py

Tests milestone evidence packet creation, review workflow, artifact tracking,
and risk assessment.
"""

import pytest
import sqlite3
import json
from datetime import datetime
from pathlib import Path
import sys

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.milestone_tracker import MilestoneTracker


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Create test database with milestone tables."""
    db_path = tmp_path / "test_milestones.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Create tables
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS apps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
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

        CREATE TABLE IF NOT EXISTS milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id INTEGER NOT NULL,
            run_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            milestone_type TEXT DEFAULT 'feature',
            status TEXT DEFAULT 'pending',
            risk_score INTEGER DEFAULT 0,
            risk_factors TEXT,
            blast_radius TEXT,
            rollback_steps TEXT,
            rollback_available BOOLEAN DEFAULT 1,
            ready_at TIMESTAMP,
            reviewed_at TIMESTAMP,
            reviewed_by TEXT,
            reviewer_notes TEXT,
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
            file_path TEXT,
            url TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (milestone_id) REFERENCES milestones(id)
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

        CREATE INDEX idx_milestones_app_id ON milestones(app_id);
        CREATE INDEX idx_milestones_status ON milestones(status);
        CREATE INDEX idx_artifacts_milestone_id ON artifacts(milestone_id);
        CREATE INDEX idx_review_queue_status ON review_queue(status);
    """)

    # Insert test app and run
    conn.execute("INSERT INTO apps (id, name, description) VALUES (1, 'test_app', 'Test Application')")
    conn.execute("INSERT INTO runs (id, app_id, status) VALUES (1, 1, 'running')")
    conn.commit()

    # Patch get_connection to return our test connection
    def mock_get_connection():
        from contextlib import contextmanager
        @contextmanager
        def get_conn():
            try:
                yield conn
            finally:
                pass
        return get_conn()

    monkeypatch.setattr("orchestrator.milestone_tracker.get_connection", mock_get_connection)

    yield conn
    conn.close()


@pytest.fixture
def tracker(test_db):
    """Create MilestoneTracker instance."""
    return MilestoneTracker()


@pytest.mark.integration
class TestMilestoneCreation:
    """Test milestone creation."""

    def test_create_milestone_basic(self, tracker, test_db):
        """Test creating a basic milestone."""
        milestone_id = tracker.create_milestone(
            app_id=1,
            name="Add user authentication",
            milestone_type="feature",
            description="Implement login/logout functionality"
        )

        assert milestone_id > 0

        # Verify in database
        row = test_db.execute("SELECT * FROM milestones WHERE id = ?", (milestone_id,)).fetchone()
        assert row["name"] == "Add user authentication"
        assert row["milestone_type"] == "feature"
        assert row["status"] == "pending"

    def test_create_milestone_with_run(self, tracker, test_db):
        """Test creating milestone linked to a run."""
        milestone_id = tracker.create_milestone(
            app_id=1,
            run_id=1,
            name="Bug fix",
            milestone_type="bugfix"
        )

        row = test_db.execute("SELECT * FROM milestones WHERE id = ?", (milestone_id,)).fetchone()
        assert row["run_id"] == 1

    def test_create_multiple_milestones(self, tracker, test_db):
        """Test creating multiple milestones."""
        ids = []
        for i in range(3):
            milestone_id = tracker.create_milestone(
                app_id=1,
                name=f"Milestone {i+1}",
                milestone_type="feature"
            )
            ids.append(milestone_id)

        assert len(ids) == 3
        assert len(set(ids)) == 3  # All unique


@pytest.mark.integration
class TestMilestoneRetrieval:
    """Test milestone retrieval."""

    def test_get_milestone(self, tracker, test_db):
        """Test getting milestone by ID."""
        milestone_id = tracker.create_milestone(app_id=1, name="Test milestone")

        milestone = tracker.get_milestone(milestone_id)

        assert milestone is not None
        assert milestone["id"] == milestone_id
        assert milestone["name"] == "Test milestone"

    def test_get_nonexistent_milestone(self, tracker):
        """Test getting nonexistent milestone returns None."""
        milestone = tracker.get_milestone(99999)
        assert milestone is None

    def test_milestone_json_fields_parsed(self, tracker, test_db):
        """Test JSON fields are parsed correctly."""
        # Create milestone with JSON fields
        milestone_id = tracker.create_milestone(app_id=1, name="Test")

        risk_factors = ["database_change", "api_change"]
        test_db.execute(
            "UPDATE milestones SET risk_factors = ? WHERE id = ?",
            (json.dumps(risk_factors), milestone_id)
        )
        test_db.commit()

        milestone = tracker.get_milestone(milestone_id)

        assert isinstance(milestone["risk_factors"], list)
        assert milestone["risk_factors"] == risk_factors


@pytest.mark.integration
class TestEvidencePacket:
    """Test evidence packet generation."""

    def test_get_evidence_packet_basic(self, tracker, test_db):
        """Test getting basic evidence packet."""
        milestone_id = tracker.create_milestone(app_id=1, name="Feature X")

        packet = tracker.get_evidence_packet(milestone_id)

        assert packet is not None
        assert packet["id"] == milestone_id
        assert "evidence" in packet
        assert "what_changed" in packet["evidence"]
        assert "why_changed" in packet["evidence"]
        assert "proof" in packet["evidence"]
        assert "risk" in packet["evidence"]

    def test_evidence_packet_with_artifacts(self, tracker, test_db):
        """Test evidence packet includes artifacts."""
        milestone_id = tracker.create_milestone(app_id=1, name="Feature")

        # Add artifacts with metadata as JSON string
        test_db.execute(
            "INSERT INTO artifacts (milestone_id, artifact_type, title, content, metadata) VALUES (?, 'commit', 'Add feature', 'abc123', ?)",
            (milestone_id, json.dumps({"sha": "abc123"}))
        )
        test_db.execute(
            "INSERT INTO artifacts (milestone_id, artifact_type, title, content, metadata) VALUES (?, 'test_report', 'Tests passed', '10 passed', ?)",
            (milestone_id, json.dumps({"passed": 10, "failed": 0}))
        )
        test_db.commit()

        packet = tracker.get_evidence_packet(milestone_id)

        assert len(packet["artifacts"]) == 2
        assert any(a["artifact_type"] == "commit" for a in packet["artifacts"])
        assert any(a["artifact_type"] == "test_report" for a in packet["artifacts"])

    def test_what_changed_evidence(self, tracker, test_db):
        """Test 'what changed' evidence extraction."""
        milestone_id = tracker.create_milestone(app_id=1, name="Feature")

        # Add commit artifact
        test_db.execute(
            "INSERT INTO artifacts (milestone_id, artifact_type, title, url, metadata) VALUES (?, 'commit', 'Add login', 'http://github.com/commit/abc', ?)",
            (milestone_id, json.dumps({"sha": "abc123"}))
        )
        test_db.commit()

        packet = tracker.get_evidence_packet(milestone_id)
        what_changed = packet["evidence"]["what_changed"]

        assert len(what_changed["commits"]) == 1
        assert what_changed["commits"][0]["sha"] == "abc123"
        assert what_changed["commits"][0]["message"] == "Add login"

    def test_proof_evidence(self, tracker, test_db):
        """Test 'proof it works' evidence extraction."""
        milestone_id = tracker.create_milestone(app_id=1, name="Feature")

        # Add test report artifact
        test_db.execute(
            "INSERT INTO artifacts (milestone_id, artifact_type, title, content, metadata) VALUES (?, 'test_report', 'Unit tests', 'All passed', ?)",
            (milestone_id, json.dumps({"passed": 10, "failed": 0, "skipped": 1}))
        )
        test_db.commit()

        packet = tracker.get_evidence_packet(milestone_id)
        proof = packet["evidence"]["proof"]

        assert len(proof["test_reports"]) == 1
        assert proof["test_reports"][0]["passed"] == 10
        assert proof["test_reports"][0]["failed"] == 0


@pytest.mark.integration
class TestReviewWorkflow:
    """Test review workflow."""

    def test_mark_ready_for_review(self, tracker, test_db):
        """Test marking milestone ready for review."""
        milestone_id = tracker.create_milestone(app_id=1, name="Feature")

        success = tracker.mark_ready_for_review(
            milestone_id,
            risk_score=50,
            risk_factors=["database_change"],
            rollback_steps=["Revert migration", "Restore backup"]
        )

        assert success is True

        # Verify milestone updated
        row = test_db.execute("SELECT * FROM milestones WHERE id = ?", (milestone_id,)).fetchone()
        assert row["status"] == "ready_for_review"
        assert row["risk_score"] == 50
        assert row["ready_at"] is not None

        # Verify added to review queue
        review = test_db.execute(
            "SELECT * FROM review_queue WHERE item_type = 'milestone' AND item_id = ?",
            (milestone_id,)
        ).fetchone()
        assert review is not None
        assert review["status"] == "pending"
        assert review["priority"] == "normal"

    def test_mark_ready_high_risk(self, tracker, test_db):
        """Test high-risk milestone gets high priority."""
        milestone_id = tracker.create_milestone(app_id=1, name="Feature")

        tracker.mark_ready_for_review(milestone_id, risk_score=75)

        review = test_db.execute(
            "SELECT * FROM review_queue WHERE item_type = 'milestone' AND item_id = ?",
            (milestone_id,)
        ).fetchone()
        assert review["priority"] == "high"

    def test_mark_ready_critical_risk(self, tracker, test_db):
        """Test critical-risk milestone gets critical priority."""
        milestone_id = tracker.create_milestone(app_id=1, name="Feature")

        tracker.mark_ready_for_review(milestone_id, risk_score=85)

        review = test_db.execute(
            "SELECT * FROM review_queue WHERE item_type = 'milestone' AND item_id = ?",
            (milestone_id,)
        ).fetchone()
        assert review["priority"] == "critical"


@pytest.mark.integration
class TestMilestoneApproval:
    """Test milestone approval."""

    def test_approve_milestone(self, tracker, test_db):
        """Test approving a milestone."""
        milestone_id = tracker.create_milestone(app_id=1, name="Feature")
        tracker.mark_ready_for_review(milestone_id, risk_score=30)

        success = tracker.approve_milestone(
            milestone_id,
            reviewer="john_doe",
            notes="Looks good, approved"
        )

        assert success is True

        # Verify milestone updated
        row = test_db.execute("SELECT * FROM milestones WHERE id = ?", (milestone_id,)).fetchone()
        assert row["status"] == "approved"
        assert row["reviewed_by"] == "john_doe"
        assert row["reviewer_notes"] == "Looks good, approved"
        assert row["reviewed_at"] is not None

        # Verify review queue updated
        review = test_db.execute(
            "SELECT * FROM review_queue WHERE item_type = 'milestone' AND item_id = ?",
            (milestone_id,)
        ).fetchone()
        assert review["status"] == "resolved"
        assert review["resolution"] == "approved"
        assert review["resolved_by"] == "john_doe"


@pytest.mark.integration
class TestMilestoneRejection:
    """Test milestone rejection."""

    def test_reject_milestone(self, tracker, test_db):
        """Test rejecting a milestone."""
        milestone_id = tracker.create_milestone(app_id=1, name="Feature")
        tracker.mark_ready_for_review(milestone_id, risk_score=40)

        success = tracker.reject_milestone(
            milestone_id,
            reviewer="jane_smith",
            notes="Tests failing, needs work"
        )

        assert success is True

        # Verify milestone updated
        row = test_db.execute("SELECT * FROM milestones WHERE id = ?", (milestone_id,)).fetchone()
        assert row["status"] == "rejected"
        assert row["reviewed_by"] == "jane_smith"
        assert row["reviewer_notes"] == "Tests failing, needs work"

        # Verify review queue updated
        review = test_db.execute(
            "SELECT * FROM review_queue WHERE item_type = 'milestone' AND item_id = ?",
            (milestone_id,)
        ).fetchone()
        assert review["status"] == "resolved"
        assert review["resolution"] == "rejected"


@pytest.mark.integration
class TestRequestChanges:
    """Test requesting changes."""

    def test_request_changes(self, tracker, test_db):
        """Test requesting changes on a milestone."""
        milestone_id = tracker.create_milestone(app_id=1, name="Feature")
        tracker.mark_ready_for_review(milestone_id, risk_score=35)

        success = tracker.request_changes(
            milestone_id,
            reviewer="bob_jones",
            notes="Add more test coverage"
        )

        assert success is True

        # Verify milestone updated
        row = test_db.execute("SELECT * FROM milestones WHERE id = ?", (milestone_id,)).fetchone()
        assert row["status"] == "changes_requested"
        assert row["reviewed_by"] == "bob_jones"
        assert row["reviewer_notes"] == "Add more test coverage"

        # Verify review queue updated
        review = test_db.execute(
            "SELECT * FROM review_queue WHERE item_type = 'milestone' AND item_id = ?",
            (milestone_id,)
        ).fetchone()
        assert review["resolution"] == "changes_requested"


@pytest.mark.integration
class TestPendingMilestones:
    """Test getting pending milestones."""

    def test_get_pending_milestones_all(self, tracker, test_db):
        """Test getting all pending milestones."""
        # Create and mark ready for review
        m1 = tracker.create_milestone(app_id=1, name="Feature 1")
        m2 = tracker.create_milestone(app_id=1, name="Feature 2")
        tracker.mark_ready_for_review(m1, risk_score=30)
        tracker.mark_ready_for_review(m2, risk_score=40)

        # Create but don't mark ready
        m3 = tracker.create_milestone(app_id=1, name="Feature 3")

        pending = tracker.get_pending_milestones()

        assert len(pending) == 2
        pending_ids = [m["id"] for m in pending]
        assert m1 in pending_ids
        assert m2 in pending_ids
        assert m3 not in pending_ids

    def test_get_pending_milestones_by_app(self, tracker, test_db):
        """Test getting pending milestones filtered by app."""
        # Add second app
        test_db.execute("INSERT INTO apps (id, name) VALUES (2, 'other_app')")
        test_db.commit()

        m1 = tracker.create_milestone(app_id=1, name="Feature 1")
        m2 = tracker.create_milestone(app_id=2, name="Feature 2")
        tracker.mark_ready_for_review(m1, risk_score=30)
        tracker.mark_ready_for_review(m2, risk_score=40)

        pending = tracker.get_pending_milestones(app_id=1)

        assert len(pending) == 1
        assert pending[0]["id"] == m1

    def test_pending_milestones_include_app_name(self, tracker, test_db):
        """Test pending milestones include app name."""
        m1 = tracker.create_milestone(app_id=1, name="Feature")
        tracker.mark_ready_for_review(m1, risk_score=30)

        pending = tracker.get_pending_milestones()

        assert pending[0]["app_name"] == "test_app"


@pytest.mark.integration
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_approve_nonreviewed_milestone(self, tracker, test_db):
        """Test approving milestone not marked for review still works."""
        milestone_id = tracker.create_milestone(app_id=1, name="Feature")

        success = tracker.approve_milestone(milestone_id, reviewer="admin")

        assert success is True

    def test_empty_artifacts_list(self, tracker, test_db):
        """Test evidence packet with no artifacts."""
        milestone_id = tracker.create_milestone(app_id=1, name="Feature")

        packet = tracker.get_evidence_packet(milestone_id)

        assert len(packet["artifacts"]) == 0
        assert packet["evidence"]["what_changed"]["commits"] == []
        assert packet["evidence"]["proof"]["test_reports"] == []

    def test_malformed_json_field(self, tracker, test_db):
        """Test handling malformed JSON in database."""
        milestone_id = tracker.create_milestone(app_id=1, name="Feature")

        # Insert malformed JSON
        test_db.execute(
            "UPDATE milestones SET risk_factors = ? WHERE id = ?",
            ("not valid json", milestone_id)
        )
        test_db.commit()

        milestone = tracker.get_milestone(milestone_id)

        # Should not crash, just leave as string
        assert milestone["risk_factors"] == "not valid json"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
