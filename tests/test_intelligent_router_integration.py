"""
Integration tests for workers/intelligent_router.py

Tests task classification, intelligent routing, session statistics,
and specialty-based routing.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from workers.intelligent_router import IntelligentRouter, TaskClassifier  # noqa: E402


@pytest.fixture
def test_db(tmp_path):
    """Create test database for intelligent router."""
    db_path = tmp_path / "test_router.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Create sessions table
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            provider TEXT DEFAULT 'ollama',
            specialty TEXT,
            is_claude INTEGER DEFAULT 1,
            status TEXT DEFAULT 'idle',
            current_task_id INTEGER,
            total_tasks INTEGER DEFAULT 0,
            successful_tasks INTEGER DEFAULT 0,
            failed_tasks INTEGER DEFAULT 0,
            total_tasks_completed INTEGER DEFAULT 0,
            total_tasks_failed INTEGER DEFAULT 0,
            total_duration_seconds INTEGER DEFAULT 0,
            avg_duration_seconds REAL DEFAULT 0,
            avg_completion_time INTEGER DEFAULT 0,
            success_rate REAL DEFAULT 0,
            last_used TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX idx_sessions_specialty ON sessions(specialty);
        CREATE INDEX idx_sessions_success_rate ON sessions(success_rate);
    """
    )

    # Insert test sessions
    conn.execute(
        """
        INSERT INTO sessions (
            name, provider, specialty, is_claude, status, total_tasks,
            successful_tasks, failed_tasks, total_tasks_completed,
            total_tasks_failed, success_rate
        )
        VALUES ('frontend-session', 'ollama', 'frontend', 1, 'idle',
                10, 9, 1, 9, 1, 90.0)
    """
    )
    conn.execute(
        """
        INSERT INTO sessions (
            name, provider, specialty, is_claude, status, total_tasks,
            successful_tasks, failed_tasks, total_tasks_completed,
            total_tasks_failed, success_rate
        )
        VALUES ('backend-session', 'ollama', 'backend', 1, 'idle',
                15, 13, 2, 13, 2, 86.7)
    """
    )
    conn.execute(
        """
        INSERT INTO sessions (
            name, provider, specialty, is_claude, status, total_tasks,
            successful_tasks, failed_tasks, total_tasks_completed,
            total_tasks_failed, success_rate
        )
        VALUES ('general-session', 'ollama', 'general', 1, 'idle',
                20, 18, 2, 18, 2, 90.0)
    """
    )
    conn.commit()

    yield {"conn": conn, "path": db_path}
    conn.close()


@pytest.fixture
def classifier():
    """Create TaskClassifier instance."""
    return TaskClassifier()


@pytest.fixture
def router(test_db):
    """Create IntelligentRouter instance."""
    return IntelligentRouter(db_path=str(test_db["path"]))


@pytest.mark.integration
class TestTaskClassification:
    """Test task classification logic."""

    def test_classify_frontend_task(self, classifier):
        """Test classifying frontend task."""
        task = "Update the React component to use Tailwind CSS"

        task_type, confidence = classifier.classify(task)

        assert task_type == "frontend"
        assert confidence > 0

    def test_classify_backend_task(self, classifier):
        """Test classifying backend task."""
        task = "Create a new API endpoint using Flask with database queries"

        task_type, confidence = classifier.classify(task)

        assert task_type == "backend"
        assert confidence > 0

    def test_classify_devops_task(self, classifier):
        """Test classifying devops task."""
        task = "Deploy the application using Docker and Kubernetes"

        task_type, confidence = classifier.classify(task)

        assert task_type == "devops"
        assert confidence > 0

    def test_classify_testing_task(self, classifier):
        """Test classifying testing task."""
        task = "Write pytest unit tests for the authentication module"

        task_type, confidence = classifier.classify(task)

        assert task_type == "testing"
        assert confidence > 0

    def test_classify_research_task(self, classifier):
        """Test classifying research task."""
        task = "Research how to implement OAuth authentication"

        task_type, confidence = classifier.classify(task)

        assert task_type == "research"
        assert confidence > 0

    def test_classify_config_task(self, classifier):
        """Test classifying configuration task."""
        task = "Update the environment variables in config.yaml"

        task_type, confidence = classifier.classify(task)

        assert task_type == "config"
        assert confidence > 0

    def test_classify_general_task(self, classifier):
        """Test classifying task with no clear category."""
        task = "Do something"

        task_type, confidence = classifier.classify(task)

        assert task_type == "general"
        assert confidence == 0.0

    def test_confidence_scores(self, classifier):
        """Test confidence scores are normalized."""
        task = "Create React component with CSS"

        task_type, confidence = classifier.classify(task)

        assert 0.0 <= confidence <= 1.0


@pytest.mark.integration
class TestSessionFinding:
    """Test finding best session for tasks."""

    def test_find_session_with_specialty_match(self, router, test_db):
        """Test finding session with matching specialty."""
        best_session = router.find_best_session(
            task_content="Update React component", task_type="frontend"
        )

        # find_best_session returns session NAME (string), not dict
        assert best_session is not None
        assert best_session == "frontend-session"

    def test_find_session_prefers_high_success_rate(self, router, test_db):
        """Test routing prefers sessions with high success rate."""
        # Add another frontend session with lower success rate
        test_db["conn"].execute(
            """
            INSERT INTO sessions (
                name, provider, specialty, is_claude, status, total_tasks,
                successful_tasks, failed_tasks, total_tasks_completed,
                total_tasks_failed, success_rate
            )
            VALUES ('frontend-session-2', 'ollama', 'frontend', 1, 'idle',
                    5, 3, 2, 3, 2, 60.0)
        """
        )
        test_db["conn"].commit()

        best_session = router.find_best_session(task_content="React task", task_type="frontend")

        # Should prefer the session with 90.0% success rate
        assert best_session == "frontend-session"

    def test_find_session_no_specialty_match(self, router, test_db):
        """Test finding session when no specialty match."""
        best_session = router.find_best_session(
            task_content="Unknown task type", task_type="unknown"
        )

        # Should return a session even without specialty match
        assert best_session is not None
        assert isinstance(best_session, str)

    def test_find_session_general_fallback(self, router, test_db):
        """Test fallback to general session."""
        best_session = router.find_best_session(task_content="Generic task", task_type="general")

        assert best_session is not None
        # Should get general-session or any available session (returns string)
        assert "session" in best_session


@pytest.mark.integration
class TestSessionStatsUpdate:
    """Test updating session statistics."""

    def test_update_stats_success(self, router, test_db):
        """Test updating stats for successful task."""
        initial = (
            test_db["conn"]
            .execute(
                """SELECT total_tasks_completed FROM sessions
                   WHERE name = 'frontend-session'"""
            )
            .fetchone()
        )
        initial_count = initial[0]

        router.update_session_stats("frontend-session", success=True, duration_seconds=30)

        updated = (
            test_db["conn"]
            .execute(
                """SELECT total_tasks_completed, total_tasks_failed
                   FROM sessions WHERE name = 'frontend-session'"""
            )
            .fetchone()
        )

        assert updated[0] == initial_count + 1  # total_tasks_completed
        assert updated[1] == 1  # total_tasks_failed unchanged

    def test_update_stats_failure(self, router, test_db):
        """Test updating stats for failed task."""
        initial = (
            test_db["conn"]
            .execute(
                """SELECT total_tasks_failed FROM sessions
                   WHERE name = 'frontend-session'"""
            )
            .fetchone()
        )
        initial_count = initial[0]

        router.update_session_stats("frontend-session", success=False, duration_seconds=15)

        updated = (
            test_db["conn"]
            .execute(
                """SELECT total_tasks_failed FROM sessions
                   WHERE name = 'frontend-session'"""
            )
            .fetchone()
        )

        assert updated[0] == initial_count + 1

    def test_update_stats_recalculates_success_rate(self, router, test_db):
        """Test success rate is recalculated."""
        # Record success
        router.update_session_stats("frontend-session", success=True, duration_seconds=20)

        session = (
            test_db["conn"]
            .execute(
                """SELECT success_rate, total_tasks_completed,
                   total_tasks_failed FROM sessions
                   WHERE name = 'frontend-session'"""
            )
            .fetchone()
        )

        # Success rate stored as percentage (0-100)
        total_tasks = session[1] + session[2]
        expected_rate = (session[1] / total_tasks * 100) if total_tasks > 0 else 0
        assert abs(session[0] - expected_rate) < 0.1

    def test_update_stats_duration_tracking(self, router, test_db):
        """Test duration tracking."""
        router.update_session_stats("frontend-session", success=True, duration_seconds=45)

        session = (
            test_db["conn"]
            .execute("SELECT avg_completion_time FROM sessions WHERE name = 'frontend-session'")
            .fetchone()
        )

        assert session[0] > 0  # avg_completion_time updated


@pytest.mark.integration
class TestSpecialtyAssignment:
    """Test assigning specialties to sessions."""

    def test_assign_specialty(self, router, test_db):
        """Test assigning specialty to session."""
        # Create new session without specialty
        test_db["conn"].execute(
            "INSERT INTO sessions (name, provider) VALUES ('new-session', 'ollama')"
        )
        test_db["conn"].commit()

        router.assign_specialty("new-session", "testing")

        session = (
            test_db["conn"]
            .execute("SELECT specialty FROM sessions WHERE name = 'new-session'")
            .fetchone()
        )

        assert session[0] == "testing"

    def test_reassign_specialty(self, router, test_db):
        """Test reassigning specialty to existing session."""
        router.assign_specialty("frontend-session", "backend")

        session = (
            test_db["conn"]
            .execute("SELECT specialty FROM sessions WHERE name = 'frontend-session'")
            .fetchone()
        )

        assert session[0] == "backend"


@pytest.mark.integration
class TestSessionStats:
    """Test retrieving session statistics."""

    def test_get_all_session_stats(self, router, test_db):
        """Test getting stats for all sessions."""
        stats = router.get_session_stats()

        assert len(stats) >= 3  # At least our 3 test sessions
        assert all("name" in s for s in stats)
        assert all("success_rate" in s for s in stats)

    def test_get_specific_session_stats(self, router, test_db):
        """Test getting stats for specific session."""
        stats = router.get_session_stats(session_name="frontend-session")

        assert len(stats) == 1
        assert stats[0]["name"] == "frontend-session"
        assert "total_tasks_completed" in stats[0]
        assert "total_tasks_failed" in stats[0]
        assert "avg_completion_time" in stats[0]

    def test_get_stats_nonexistent_session(self, router, test_db):
        """Test getting stats for nonexistent session."""
        stats = router.get_session_stats(session_name="nonexistent")

        assert len(stats) == 0


@pytest.mark.integration
class TestClassificationPatterns:
    """Test classification pattern matching."""

    def test_frontend_patterns(self, classifier):
        """Test various frontend task patterns."""
        tasks = [
            "Update React component",
            "Style with Tailwind CSS",
            "Create Vue template",
            "Fix HTML layout",
            "Improve UI design",
        ]

        for task in tasks:
            task_type, confidence = classifier.classify(task)
            assert task_type == "frontend", f"Failed for: {task}"

    def test_backend_patterns(self, classifier):
        """Test various backend task patterns."""
        tasks = [
            "Create API endpoint",
            "Write SQL query",
            "Implement Flask route",
            "Add database migration",
            "Build REST API",
        ]

        for task in tasks:
            task_type, confidence = classifier.classify(task)
            assert task_type == "backend", f"Failed for: {task}"

    def test_mixed_keywords(self, classifier):
        """Test task with mixed keywords."""
        task = "Create React component that calls API endpoint"

        task_type, confidence = classifier.classify(task)

        # Should classify based on which has more matches
        assert task_type in ["frontend", "backend"]


@pytest.mark.integration
class TestRouterDatabaseOperations:
    """Test database operations."""

    def test_database_connection(self, router):
        """Test database connection works."""
        conn = router.get_db_connection()

        assert conn is not None
        cursor = conn.execute("SELECT COUNT(*) FROM sessions")
        count = cursor.fetchone()[0]
        conn.close()

        assert count >= 3

    def test_session_table_structure(self, router, test_db):
        """Test sessions table has required columns."""
        cursor = test_db["conn"].execute("PRAGMA table_info(sessions)")
        columns = [row[1] for row in cursor.fetchall()]

        required_columns = [
            "name",
            "specialty",
            "total_tasks",
            "successful_tasks",
            "failed_tasks",
            "success_rate",
        ]

        for col in required_columns:
            assert col in columns


@pytest.mark.integration
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_classify_empty_string(self, classifier):
        """Test classifying empty task."""
        task_type, confidence = classifier.classify("")

        assert task_type == "general"
        assert confidence == 0.0

    def test_classify_very_long_task(self, classifier):
        """Test classifying very long task description."""
        task = "Create React " * 100  # 200+ words

        task_type, confidence = classifier.classify(task)

        assert task_type == "frontend"

    def test_update_stats_nonexistent_session(self, router, test_db):
        """Test updating stats for nonexistent session."""
        # Should handle gracefully
        try:
            router.update_session_stats("nonexistent", success=True, duration_seconds=10)
        except Exception:
            # May raise exception or handle silently
            pass

    def test_find_session_empty_database(self, tmp_path):
        """Test finding session with empty database."""
        empty_db = tmp_path / "empty.db"
        conn = sqlite3.connect(empty_db)
        conn.execute(
            """
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY,
                name TEXT,
                specialty TEXT,
                is_claude INTEGER DEFAULT 1,
                status TEXT DEFAULT 'idle',
                current_task_id INTEGER,
                success_rate REAL DEFAULT 0,
                avg_completion_time INTEGER DEFAULT 0,
                total_tasks_completed INTEGER DEFAULT 0
            )
        """
        )
        conn.commit()
        conn.close()

        router = IntelligentRouter(db_path=str(empty_db))
        best_session = router.find_best_session("Test task", "frontend")

        # Should return None (no sessions in empty database)
        assert best_session is None

    def test_case_insensitive_classification(self, classifier):
        """Test classification is case insensitive."""
        task1 = "Create REACT component"
        task2 = "create react component"

        type1, conf1 = classifier.classify(task1)
        type2, conf2 = classifier.classify(task2)

        assert type1 == type2
        assert type1 == "frontend"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
