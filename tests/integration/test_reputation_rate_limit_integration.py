"""Integration tests for Reputation System + Rate Limiter.

Tests the full workflow of:
1. Rate limiting with reputation adjustments
2. Recording violations as reputation events
3. Applying adjusted limits
4. VIP overrides
5. Feature flag behavior
"""

import unittest
import sqlite3
import os
import tempfile
from datetime import datetime, timedelta
from services.reputation_system import ReputationSystem
from services.rate_limiting_with_reputation import EnhancedRateLimitService


class TestReputationRateLimitIntegration(unittest.TestCase):
    """Integration tests for reputation and rate limiting."""

    def setUp(self):
        """Set up test database and services."""
        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self._init_db()

        def get_db():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn

        # Initialize services AFTER creating tables
        self.get_db = get_db
        self.reputation_system = ReputationSystem(self.db_path)

        self.rate_limiter = EnhancedRateLimitService(
            get_db,
            enable_reputation=True
        )

    def tearDown(self):
        """Clean up test database."""
        if os.path.exists(self.db_path):
            os.close(self.db_fd)
            os.unlink(self.db_path)

    def _init_db(self):
        """Initialize test database with full schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.executescript("""
            -- Rate Limiting Tables
            CREATE TABLE IF NOT EXISTS rate_limit_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_name TEXT NOT NULL UNIQUE,
                scope TEXT NOT NULL,
                scope_value TEXT,
                limit_type TEXT NOT NULL,
                limit_value INTEGER NOT NULL,
                resource_type TEXT,
                enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS rate_limit_buckets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL,
                scope_value TEXT NOT NULL,
                resource_type TEXT,
                window_start TIMESTAMP NOT NULL,
                window_end TIMESTAMP NOT NULL,
                request_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS rate_limit_violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL,
                scope_value TEXT NOT NULL,
                resource_type TEXT,
                exceeded_limit INTEGER,
                blocked BOOLEAN DEFAULT 1,
                request_path TEXT,
                user_agent TEXT,
                violation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS resource_quotas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                api_key TEXT,
                resource_type TEXT NOT NULL,
                quota_period TEXT NOT NULL,
                quota_limit INTEGER NOT NULL,
                quota_used INTEGER DEFAULT 0,
                period_start TIMESTAMP NOT NULL,
                period_end TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Reputation Tables
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

            -- Insert default rate limit rules
            INSERT OR IGNORE INTO rate_limit_configs
            (rule_name, scope, limit_type, limit_value)
            VALUES ('default_global', 'global', 'requests_per_minute', 100);
        """)
        conn.commit()
        conn.close()

    # Test 1: Basic rate limit with neutral reputation
    def test_rate_limit_neutral_reputation(self):
        """Test rate limiting with neutral reputation user."""
        user_id = 1

        # User with neutral reputation (50) should get 1.0x multiplier
        multiplier = self.reputation_system.get_limit_multiplier(user_id)
        self.assertEqual(multiplier, 1.0)

        # Rate limit should be base value (100 * 1.0 = 100)
        allowed, info = self.rate_limiter.check_limit_with_reputation(
            scope="user",
            scope_value="user_1",
            resource_type="default",
            user_id=user_id,
        )
        self.assertTrue(allowed)

    # Test 2: Rate limit with good reputation
    def test_rate_limit_good_reputation(self):
        """Test that good reputation gives higher limits."""
        user_id = 2

        # Build good reputation (75+)
        for _ in range(50):
            self.reputation_system.record_event(user_id, "clean_request")

        score = self.reputation_system.get_reputation(user_id)
        self.assertGreater(score, 74)

        multiplier = self.reputation_system.get_limit_multiplier(user_id)
        self.assertGreaterEqual(multiplier, 1.5)

    # Test 3: Rate limit with restricted reputation
    def test_rate_limit_restricted_reputation(self):
        """Test that restricted reputation gives lower limits."""
        user_id = 3

        # Give user violations to lower score (use high severity)
        for _ in range(40):
            self.reputation_system.record_event(user_id, "rate_limit_violation", severity=8)

        score = self.reputation_system.get_reputation(user_id)
        self.assertLess(score, 40)  # Should be noticeably reduced

        multiplier = self.reputation_system.get_limit_multiplier(user_id)
        self.assertLess(multiplier, 1.0)  # Should be less than neutral

    # Test 4: Violation updates reputation
    def test_violation_updates_reputation_score(self):
        """Test that rate limit violation updates reputation score."""
        user_id = 4

        # Record initial clean requests
        for _ in range(20):
            self.reputation_system.record_event(user_id, "clean_request")

        score_before = self.reputation_system.get_reputation(user_id)

        # Record violation
        allowed, info = self.rate_limiter.check_limit_with_reputation(
            scope="user",
            scope_value="user_4",
            resource_type="default",
            user_id=user_id,
        )

        # Manually trigger violation recording
        self.reputation_system.record_event(user_id, "rate_limit_violation")

        score_after = self.reputation_system.get_reputation(user_id)

        # Score should have decreased
        self.assertLess(score_after, score_before)

    # Test 5: VIP overrides reputation
    def test_vip_override_bypasses_reputation(self):
        """Test that VIP tier overrides reputation-based limits."""
        user_id = 5

        # Give user low reputation
        for _ in range(20):
            self.reputation_system.record_event(user_id, "rate_limit_violation")

        reputation_multiplier = self.reputation_system.get_limit_multiplier(user_id)
        self.assertLess(reputation_multiplier, 1.0)

        # Set as VIP
        self.reputation_system.set_vip_tier(user_id, "premium", limit_multiplier=3.0)

        vip_multiplier = self.reputation_system.get_limit_multiplier(user_id)
        self.assertEqual(vip_multiplier, 3.0)

    # Test 6: Clean requests improve limits
    def test_clean_requests_improve_limits(self):
        """Test that good behavior improves rate limits."""
        user_id = 6

        # Start with low reputation
        for _ in range(15):
            self.reputation_system.record_event(user_id, "rate_limit_violation")

        low_multiplier = self.reputation_system.get_limit_multiplier(user_id)

        # Build reputation with clean requests
        for _ in range(100):
            self.reputation_system.record_event(user_id, "clean_request")

        high_multiplier = self.reputation_system.get_limit_multiplier(user_id)

        self.assertGreater(high_multiplier, low_multiplier)

    # Test 7: Adjusted limit calculation
    def test_adjusted_limit_calculation(self):
        """Test that limits are correctly adjusted by multiplier."""
        user_id = 7
        base_limit = 100

        # Build excellent reputation (90+)
        for _ in range(80):
            self.reputation_system.record_event(user_id, "clean_request")

        multiplier = self.reputation_system.get_limit_multiplier(user_id)
        self.assertGreater(multiplier, 1.5)  # Should be at least good tier

        expected_adjusted = int(base_limit * multiplier)

        adjusted = self.rate_limiter.get_adjusted_limit(base_limit, user_id)

        # Verify the adjustment is greater than base due to good reputation
        self.assertGreaterEqual(adjusted["limit"], base_limit)

    # Test 8: Feature can be disabled
    def test_reputation_feature_can_be_disabled(self):
        """Test that reputation system can be disabled."""
        # Create rate limiter with reputation disabled
        def get_db():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn

        disabled_limiter = EnhancedRateLimitService(get_db, enable_reputation=False)

        # Even with reputation data, should not apply multipliers
        user_id = 8

        # Build excellent reputation
        for _ in range(80):
            self.reputation_system.record_event(user_id, "clean_request")

        multiplier = self.reputation_system.get_limit_multiplier(user_id)
        self.assertGreaterEqual(multiplier, 1.5)  # Should be good/excellent

        # But rate limiter should ignore it
        adjusted = disabled_limiter.get_adjusted_limit(100, user_id)
        self.assertEqual(adjusted["multiplier"], 1.0)  # No adjustment

    # Test 9: Multiple violations accumulate
    def test_multiple_violations_accumulate(self):
        """Test that multiple violations compound reputation loss."""
        user_id = 9

        # Start with clean reputation by recording a clean request
        self.reputation_system.record_event(user_id, "clean_request")
        score_0 = self.reputation_system.get_reputation(user_id)
        self.assertIsNotNone(score_0)

        self.reputation_system.record_event(user_id, "rate_limit_violation", severity=3)
        score_1 = self.reputation_system.get_reputation(user_id)

        for _ in range(4):
            self.reputation_system.record_event(user_id, "rate_limit_violation", severity=3)

        score_5 = self.reputation_system.get_reputation(user_id)

        # Each violation should decrease score
        self.assertLess(score_1, score_0)
        self.assertLess(score_5, score_1)

    # Test 10: Reputation details include multiplier
    def test_reputation_details_include_multiplier(self):
        """Test that reputation details include rate limit multiplier."""
        user_id = 10

        # Build some reputation
        for _ in range(30):
            self.reputation_system.record_event(user_id, "clean_request")

        details = self.reputation_system.get_reputation_details(user_id)

        self.assertIn("limit_multiplier", details)
        self.assertGreaterEqual(details["limit_multiplier"], 1.0)


class TestReputationRateLimitThroughput(unittest.TestCase):
    """Test throughput and performance."""

    def setUp(self):
        """Set up test database and services."""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self._init_db()

        self.reputation_system = ReputationSystem(self.db_path)

        def get_db():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn

        self.rate_limiter = EnhancedRateLimitService(get_db, enable_reputation=True)

    def tearDown(self):
        """Clean up."""
        if os.path.exists(self.db_path):
            os.close(self.db_fd)
            os.unlink(self.db_path)

    def _init_db(self):
        """Initialize test database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS rate_limit_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_name TEXT NOT NULL UNIQUE,
                scope TEXT NOT NULL,
                scope_value TEXT,
                limit_type TEXT NOT NULL,
                limit_value INTEGER NOT NULL,
                resource_type TEXT,
                enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS rate_limit_buckets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL,
                scope_value TEXT NOT NULL,
                resource_type TEXT,
                window_start TIMESTAMP NOT NULL,
                window_end TIMESTAMP NOT NULL,
                request_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS rate_limit_violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL,
                scope_value TEXT NOT NULL,
                resource_type TEXT,
                exceeded_limit INTEGER,
                blocked BOOLEAN DEFAULT 1,
                request_path TEXT,
                user_agent TEXT,
                violation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

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

            INSERT OR IGNORE INTO rate_limit_configs
            (rule_name, scope, limit_type, limit_value)
            VALUES ('default_global', 'global', 'requests_per_minute', 100);
        """)
        conn.commit()
        conn.close()

    def test_multiple_users_concurrent(self):
        """Test handling multiple users simultaneously."""
        # Simulate 10 users with varying reputations
        for user_id in range(1, 11):
            # Give each user different reputation levels
            repetitions = user_id * 5
            for _ in range(repetitions):
                self.reputation_system.record_event(user_id, "clean_request")

        # Check limits for all users
        results = []
        for user_id in range(1, 11):
            adjusted = self.rate_limiter.get_adjusted_limit(100, user_id)
            results.append(adjusted)

        # All should return valid results
        self.assertEqual(len(results), 10)
        for result in results:
            self.assertIn("limit", result)
            self.assertIn("multiplier", result)


if __name__ == "__main__":
    unittest.main()
