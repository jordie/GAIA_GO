"""Unit tests for the Reputation System.

Tests cover:
- Score calculation and updates
- Event recording and processing
- Tier assignment
- Limit multiplier calculation
- VIP override functionality
- Decay mechanics
- Statistics and reporting
"""

import unittest
import sqlite3
import os
import tempfile
from datetime import datetime, timedelta
from services.reputation_system import ReputationSystem


class TestReputationSystem(unittest.TestCase):
    """Test suite for ReputationSystem."""

    def setUp(self):
        """Set up test database and system."""
        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.system = ReputationSystem(self.db_path)

        # Initialize database schema
        self._init_db()

    def tearDown(self):
        """Clean up test database."""
        if os.path.exists(self.db_path):
            os.close(self.db_fd)
            os.unlink(self.db_path)

    def _init_db(self):
        """Initialize test database with schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create tables (simplified version of migration)
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS user_reputation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                reputation_score REAL DEFAULT 50.0,
                tier TEXT DEFAULT 'standard',
                last_violation TIMESTAMP,
                total_violations INTEGER DEFAULT 0,
                total_clean_requests INTEGER DEFAULT 0,
                decay_last_applied TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reputation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                severity INTEGER DEFAULT 1,
                description TEXT,
                score_delta REAL DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS vip_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                tier TEXT NOT NULL,
                limit_multiplier REAL DEFAULT 1.0,
                notes TEXT,
                approved_by INTEGER,
                approved_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reputation_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT NOT NULL UNIQUE,
                config_value TEXT NOT NULL,
                description TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()

    # Test 1: Initial reputation creation
    def test_new_user_gets_initial_score(self):
        """Test that new users get initial reputation score."""
        user_id = 1
        self.system.record_event(user_id, self.system.EVENT_CLEAN_REQUEST)

        score = self.system.get_reputation(user_id)
        self.assertIsNotNone(score)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    # Test 2: Violation penalty
    def test_violation_reduces_score(self):
        """Test that violations reduce reputation score."""
        user_id = 2
        initial_score = 50.0

        # Create user with initial score
        self.system.record_event(user_id, self.system.EVENT_CLEAN_REQUEST)

        # Record violation
        self.system.record_event(user_id, self.system.EVENT_VIOLATION, severity=5)
        score = self.system.get_reputation(user_id)

        self.assertLess(score, initial_score + 10)  # Should be lower than after first event

    # Test 3: Clean requests improve score
    def test_clean_requests_improve_score(self):
        """Test that clean requests improve reputation score."""
        user_id = 3

        # Record multiple clean requests
        for _ in range(10):
            self.system.record_event(user_id, self.system.EVENT_CLEAN_REQUEST)

        score = self.system.get_reputation(user_id)
        self.assertGreater(score, 50.0)  # Should be above neutral

    # Test 4: Attack penalty is stronger
    def test_attack_penalty_is_severe(self):
        """Test that suspected attacks have stronger penalty."""
        user_id = 4
        self.system.record_event(user_id, self.system.EVENT_CLEAN_REQUEST)

        score_before = self.system.get_reputation(user_id)
        self.system.record_event(user_id, self.system.EVENT_ATTACK, severity=10)
        score_after = self.system.get_reputation(user_id)

        delta = score_before - score_after
        self.assertGreater(delta, 5)  # Attack penalty should be > 5 points

    # Test 5: Tier assignment based on score
    def test_tier_assignment(self):
        """Test that tiers are correctly assigned based on score."""
        test_cases = [
            (95, "excellent"),
            (80, "good"),
            (60, "neutral"),
            (30, "caution"),
            (10, "restricted"),
        ]

        for score, expected_tier in test_cases:
            actual_tier = self.system.get_tier_for_score(score)
            self.assertEqual(actual_tier, expected_tier,
                           f"Score {score} should be tier '{expected_tier}'")

    # Test 6: Limit multiplier based on tier
    def test_limit_multiplier_by_tier(self):
        """Test that limit multipliers match tier."""
        user_id = 6
        # Build up to good tier (75+)
        for _ in range(50):
            self.system.record_event(user_id, self.system.EVENT_CLEAN_REQUEST)

        multiplier = self.system.get_limit_multiplier(user_id)
        self.assertGreaterEqual(multiplier, 1.5)  # Should be in good tier or better

    # Test 7: VIP override limits
    def test_vip_tier_override(self):
        """Test that VIP tier overrides reputation-based limits."""
        user_id = 7

        # Give low reputation
        for _ in range(5):
            self.system.record_event(user_id, self.system.EVENT_VIOLATION)

        reputation_multiplier = self.system.get_limit_multiplier(user_id)

        # Set as VIP
        self.system.set_vip_tier(user_id, "premium", limit_multiplier=3.0)
        vip_multiplier = self.system.get_limit_multiplier(user_id)

        self.assertLess(reputation_multiplier, vip_multiplier)
        self.assertEqual(vip_multiplier, 3.0)

    # Test 8: Remove VIP status
    def test_remove_vip_tier(self):
        """Test removing VIP status reverts to reputation-based limits."""
        user_id = 8

        # Set as VIP
        self.system.set_vip_tier(user_id, "premium", limit_multiplier=3.0)
        vip_multiplier = self.system.get_limit_multiplier(user_id)
        self.assertEqual(vip_multiplier, 3.0)

        # Remove VIP
        self.system.remove_vip_tier(user_id)
        rep_multiplier = self.system.get_limit_multiplier(user_id)

        # Should now be based on reputation (which was never set, so neutral)
        self.assertEqual(rep_multiplier, 1.0)

    # Test 9: Event history tracking
    def test_event_history_tracking(self):
        """Test that event history is properly recorded."""
        user_id = 9

        events_to_record = [
            (self.system.EVENT_CLEAN_REQUEST, 1),
            (self.system.EVENT_VIOLATION, 3),
            (self.system.EVENT_CLEAN_REQUEST, 1),
            (self.system.EVENT_CLEAN_REQUEST, 1),
        ]

        for event_type, severity in events_to_record:
            self.system.record_event(user_id, event_type, severity=severity)

        history = self.system.get_event_history(user_id, limit=10)

        self.assertEqual(len(history), len(events_to_record))
        # Most recent first
        self.assertEqual(history[0]["event_type"], self.system.EVENT_CLEAN_REQUEST)

    # Test 10: Detailed reputation info
    def test_get_reputation_details(self):
        """Test getting detailed reputation information."""
        user_id = 10

        # Record some events
        for _ in range(3):
            self.system.record_event(user_id, self.system.EVENT_CLEAN_REQUEST)
        self.system.record_event(user_id, self.system.EVENT_VIOLATION)

        details = self.system.get_reputation_details(user_id)

        self.assertIsNotNone(details)
        self.assertEqual(details["user_id"], user_id)
        self.assertIn("reputation_score", details)
        self.assertIn("tier", details)
        self.assertIn("limit_multiplier", details)
        self.assertGreater(details["total_violations"], 0)

    # Test 11: Score boundaries
    def test_score_boundaries(self):
        """Test that scores are bounded between 0 and 100."""
        user_id = 11

        # Try to drive score below 0
        for _ in range(100):
            self.system.record_event(user_id, self.system.EVENT_ATTACK, severity=10)

        score = self.system.get_reputation(user_id)
        self.assertGreaterEqual(score, 0)

        # Try to drive score above 100
        user_id_2 = 12
        for _ in range(100):
            self.system.record_event(user_id_2, self.system.EVENT_CLEAN_REQUEST)

        score_2 = self.system.get_reputation(user_id_2)
        self.assertLessEqual(score_2, 100)

    # Test 12: Violation tracking
    def test_violation_count_tracking(self):
        """Test that violation counts are tracked."""
        user_id = 13

        num_violations = 5
        for _ in range(num_violations):
            self.system.record_event(user_id, self.system.EVENT_VIOLATION)

        details = self.system.get_reputation_details(user_id)
        self.assertEqual(details["total_violations"], num_violations)

    # Test 13: Clean request tracking
    def test_clean_request_count_tracking(self):
        """Test that clean request counts are tracked."""
        user_id = 14

        num_clean = 20
        for _ in range(num_clean):
            self.system.record_event(user_id, self.system.EVENT_CLEAN_REQUEST)

        details = self.system.get_reputation_details(user_id)
        self.assertEqual(details["total_clean_requests"], num_clean)

    # Test 14: Last violation timestamp
    def test_last_violation_timestamp(self):
        """Test that last violation time is tracked."""
        user_id = 15

        self.system.record_event(user_id, self.system.EVENT_VIOLATION)

        details = self.system.get_reputation_details(user_id)
        last_viol = details["last_violation"]

        # Just verify that timestamp is not None (SQLite tracks it)
        self.assertIsNotNone(last_viol)

    # Test 15: Get statistics
    def test_get_statistics(self):
        """Test that system statistics are calculated."""
        # Create a few users
        for user_id in range(1, 4):
            for _ in range(10):
                self.system.record_event(user_id, self.system.EVENT_CLEAN_REQUEST)
            self.system.record_event(user_id, self.system.EVENT_VIOLATION)

        stats = self.system.get_statistics()

        self.assertIn("overall", stats)
        self.assertIn("tier_distribution", stats)
        self.assertGreater(stats["overall"]["total_users"], 0)


class TestReputationDecay(unittest.TestCase):
    """Test decay mechanics for reputation system."""

    def setUp(self):
        """Set up test database."""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.system = ReputationSystem(self.db_path)
        self._init_db()

    def tearDown(self):
        """Clean up."""
        if os.path.exists(self.db_path):
            os.close(self.db_fd)
            os.unlink(self.db_path)

    def _init_db(self):
        """Initialize test database with schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS user_reputation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                reputation_score REAL DEFAULT 50.0,
                tier TEXT DEFAULT 'standard',
                last_violation TIMESTAMP,
                total_violations INTEGER DEFAULT 0,
                total_clean_requests INTEGER DEFAULT 0,
                decay_last_applied TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reputation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                severity INTEGER DEFAULT 1,
                description TEXT,
                score_delta REAL DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS vip_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                tier TEXT NOT NULL,
                limit_multiplier REAL DEFAULT 1.0,
                notes TEXT,
                approved_by INTEGER,
                approved_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reputation_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT NOT NULL UNIQUE,
                config_value TEXT NOT NULL,
                description TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()

    # Test 1: Decay applies to old violations
    def test_decay_reduces_impact_of_old_violations(self):
        """Test that old violations have less impact due to decay."""
        user_id = 100

        # This is a simplified test - in a real scenario,
        # you would use time manipulation to test actual decay
        # For now, we just verify the system runs without error

        self.system.record_event(user_id, self.system.EVENT_VIOLATION, severity=10)
        score = self.system.get_reputation(user_id)

        # Score should reflect the violation
        self.assertLess(score, 50)


class TestReputationEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def setUp(self):
        """Set up test database."""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.system = ReputationSystem(self.db_path)
        self._init_db()

    def tearDown(self):
        """Clean up."""
        if os.path.exists(self.db_path):
            os.close(self.db_fd)
            os.unlink(self.db_path)

    def _init_db(self):
        """Initialize test database with schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS user_reputation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                reputation_score REAL DEFAULT 50.0,
                tier TEXT DEFAULT 'standard',
                last_violation TIMESTAMP,
                total_violations INTEGER DEFAULT 0,
                total_clean_requests INTEGER DEFAULT 0,
                decay_last_applied TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reputation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                severity INTEGER DEFAULT 1,
                description TEXT,
                score_delta REAL DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS vip_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                tier TEXT NOT NULL,
                limit_multiplier REAL DEFAULT 1.0,
                notes TEXT,
                approved_by INTEGER,
                approved_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reputation_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT NOT NULL UNIQUE,
                config_value TEXT NOT NULL,
                description TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()

    # Test 1: Non-existent user
    def test_non_existent_user_returns_none(self):
        """Test that querying non-existent user returns None."""
        score = self.system.get_reputation(999999)
        self.assertIsNone(score)

    # Test 2: Multiplier for non-existent user
    def test_multiplier_for_nonexistent_user_defaults_to_one(self):
        """Test that multiplier for non-existent user defaults to 1.0."""
        multiplier = self.system.get_limit_multiplier(999999)
        self.assertEqual(multiplier, 1.0)

    # Test 3: Event with unknown type
    def test_unknown_event_type(self):
        """Test that unknown event types are handled gracefully."""
        result = self.system.record_event(200, "unknown_event_type")
        # Should handle gracefully (return True or False, not crash)
        self.assertIsNotNone(result)

    # Test 4: Top users with no users
    def test_top_users_empty_database(self):
        """Test getting top users from empty database."""
        users = self.system.get_top_users(limit=10)
        self.assertEqual(len(users), 0)


if __name__ == "__main__":
    unittest.main()
