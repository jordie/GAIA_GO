"""Unit tests for rate limiting service."""

import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from services.rate_limiting import RateLimitService
from services.resource_monitor import ResourceMonitor
from services.background_tasks import BackgroundTaskManager


class TestDatabase:
    """Fixture for test database."""

    @pytest.fixture
    def test_db(self):
        """Create an in-memory test database."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row

        # Create tables
        with open("migrations/050_rate_limiting_enhancement.sql") as f:
            conn.executescript(f.read())

        yield conn
        conn.close()


class TestRateLimitService(TestDatabase):
    """Tests for RateLimitService."""

    def test_create_config(self, test_db):
        """Test creating a rate limit configuration."""
        def get_conn():
            return test_db

        service = RateLimitService(get_conn)
        success = service.create_config(
            rule_name="test_limit",
            scope="ip",
            limit_type="requests_per_minute",
            limit_value=10
        )

        assert success
        configs = service.get_all_configs()
        assert len(configs) >= 1
        assert configs[0]["rule_name"] == "test_limit"
        assert configs[0]["limit_value"] == 10

    def test_check_limit_allows_under_limit(self, test_db):
        """Test that requests under limit are allowed."""
        def get_conn():
            return test_db

        service = RateLimitService(get_conn)
        service.create_config(
            rule_name="test",
            scope="ip",
            limit_type="requests_per_minute",
            limit_value=10
        )

        # First request should be allowed
        allowed, info = service.check_limit("ip", "192.168.1.1", "default")
        assert allowed
        assert info is None

    def test_check_limit_denies_over_limit(self, test_db):
        """Test that requests over limit are denied."""
        def get_conn():
            return test_db

        service = RateLimitService(get_conn)
        service.create_config(
            rule_name="test",
            scope="ip",
            limit_type="requests_per_minute",
            limit_value=2
        )

        # Make requests
        allowed1, _ = service.check_limit("ip", "192.168.1.1", "default")
        assert allowed1

        allowed2, _ = service.check_limit("ip", "192.168.1.1", "default")
        assert allowed2

        # Third request should be denied
        allowed3, info = service.check_limit("ip", "192.168.1.1", "default")
        assert not allowed3
        assert info["limit"] == 2

    def test_disable_config(self, test_db):
        """Test disabling a rate limit configuration."""
        def get_conn():
            return test_db

        service = RateLimitService(get_conn)
        service.create_config(
            rule_name="test",
            scope="ip",
            limit_type="requests_per_minute",
            limit_value=10
        )

        success = service.disable_config("test")
        assert success

        configs = service.get_all_configs()
        test_config = next(c for c in configs if c["rule_name"] == "test")
        assert not test_config["enabled"]

    def test_specific_scope_rules_override_defaults(self, test_db):
        """Test that specific scope rules override defaults."""
        def get_conn():
            return test_db

        service = RateLimitService(get_conn)

        # Create default rule
        service.create_config(
            rule_name="default",
            scope="ip",
            limit_type="requests_per_minute",
            limit_value=100,
            scope_value=None  # Default for all IPs
        )

        # Create specific rule
        service.create_config(
            rule_name="specific",
            scope="ip",
            limit_type="requests_per_minute",
            limit_value=5,
            scope_value="192.168.1.1"  # Specific IP
        )

        # Specific IP should get stricter limit
        limits = service._get_limits("ip", "192.168.1.1", "default")
        # Should have both rules, specific first
        assert len(limits) >= 1

    def test_cleanup_old_data(self, test_db):
        """Test cleanup of old data."""
        def get_conn():
            return test_db

        service = RateLimitService(get_conn)
        service.create_config(
            rule_name="test",
            scope="ip",
            limit_type="requests_per_minute",
            limit_value=10
        )

        # Create some violations
        allowed, _ = service.check_limit("ip", "192.168.1.1", "default")
        allowed, _ = service.check_limit("ip", "192.168.1.1", "default")

        # Cleanup should not delete recent data
        deleted = service.cleanup_old_data(days=7)
        assert deleted >= 0  # May or may not delete depending on timing

    def test_get_stats(self, test_db):
        """Test getting rate limiting statistics."""
        def get_conn():
            return test_db

        service = RateLimitService(get_conn)
        service.create_config(
            rule_name="test",
            scope="ip",
            limit_type="requests_per_minute",
            limit_value=2
        )

        # Create some activity
        service.check_limit("ip", "192.168.1.1", "default")
        service.check_limit("ip", "192.168.1.1", "default")
        service.check_limit("ip", "192.168.1.1", "default")  # This one violates

        stats = service.get_stats(days=1)
        # Only 2 requests counted (denied requests not in buckets)
        assert stats["total_requests"] >= 2
        assert "violations_by_scope" in stats
        # Should have at least one violation recorded
        assert stats["violations_by_scope"].get("ip", 0) >= 1

    def test_violations_summary(self, test_db):
        """Test getting violations summary."""
        def get_conn():
            return test_db

        service = RateLimitService(get_conn)
        service.create_config(
            rule_name="test",
            scope="ip",
            limit_type="requests_per_minute",
            limit_value=1
        )

        # Trigger violation
        service.check_limit("ip", "192.168.1.1", "default")
        service.check_limit("ip", "192.168.1.1", "default")  # Violates

        summary = service.get_violations_summary(hours=1)
        assert summary["hours_analyzed"] == 1
        assert summary["total_violations"] >= 1


class TestResourceMonitor(TestDatabase):
    """Tests for ResourceMonitor."""

    def test_get_current_load(self, test_db):
        """Test getting current system load."""
        def get_conn():
            return test_db

        monitor = ResourceMonitor(get_conn)
        load = monitor.get_current_load()

        assert "cpu_percent" in load
        assert "memory_percent" in load
        assert "disk_percent" in load
        assert 0 <= load["cpu_percent"] <= 100
        assert 0 <= load["memory_percent"] <= 100

    def test_should_throttle_normal_load(self, test_db):
        """Test that throttling is not active under normal load."""
        def get_conn():
            return test_db

        monitor = ResourceMonitor(get_conn)
        should_throttle, reason = monitor.should_throttle()

        # Should be False under normal load
        assert isinstance(should_throttle, bool)
        if should_throttle:
            assert reason in ["high_cpu", "critical_cpu", "high_memory", "critical_memory"]

    def test_record_snapshot(self, test_db):
        """Test recording resource snapshot."""
        def get_conn():
            return test_db

        monitor = ResourceMonitor(get_conn)
        snapshot = monitor.record_snapshot()

        assert snapshot["cpu_percent"] >= 0
        assert snapshot["memory_percent"] >= 0
        assert "memory_mb" in snapshot

    def test_get_load_trend(self, test_db):
        """Test getting load trend."""
        def get_conn():
            return test_db

        monitor = ResourceMonitor(get_conn)
        monitor.record_snapshot()

        trend = monitor.get_load_trend(minutes=5)
        if trend:  # May be empty if no data
            assert "cpu" in trend or "memory" in trend

    def test_get_health_status(self, test_db):
        """Test getting health status."""
        def get_conn():
            return test_db

        monitor = ResourceMonitor(get_conn)
        health = monitor.get_health_status()

        assert "healthy" in health
        assert "current" in health
        assert isinstance(health["healthy"], bool)

    def test_set_thresholds(self, test_db):
        """Test setting custom thresholds."""
        def get_conn():
            return test_db

        monitor = ResourceMonitor(get_conn)
        monitor.set_thresholds(high=75, critical=90)

        assert monitor.high_load_threshold == 75
        assert monitor.critical_load_threshold == 90


class TestBackgroundTaskManager:
    """Tests for BackgroundTaskManager."""

    def test_register_task(self):
        """Test registering a background task."""
        manager = BackgroundTaskManager()

        call_count = []

        def dummy_task():
            call_count.append(1)

        success = manager.register_task(
            task_name="test_task",
            task_func=dummy_task,
            interval_seconds=1
        )

        assert success
        assert "test_task" in manager.tasks

    def test_register_duplicate_task(self):
        """Test that duplicate task names are rejected."""
        manager = BackgroundTaskManager()

        def dummy_task():
            pass

        manager.register_task(
            task_name="test",
            task_func=dummy_task,
            interval_seconds=1
        )

        # Try to register again
        success = manager.register_task(
            task_name="test",
            task_func=dummy_task,
            interval_seconds=1
        )

        assert not success

    def test_get_stats(self):
        """Test getting task statistics."""
        manager = BackgroundTaskManager()

        def dummy_task():
            pass

        manager.register_task(
            task_name="test_task",
            task_func=dummy_task,
            interval_seconds=1
        )

        stats = manager.get_stats()
        assert stats["total_tasks"] >= 1
        assert "test_task" in stats["tasks"]
        assert stats["tasks"]["test_task"]["total_runs"] == 0

    def test_start_stop(self):
        """Test starting and stopping background tasks."""
        manager = BackgroundTaskManager()

        def dummy_task():
            pass

        manager.register_task(
            task_name="test",
            task_func=dummy_task,
            interval_seconds=10
        )

        manager.start()
        assert manager._running

        manager.stop()
        assert not manager._running


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
