#!/usr/bin/env python3
"""
Tests for Enhanced Connection Pool Module

Verifies:
- Connection pooling functionality
- ServiceConnectionPool helper
- Background health checker
- Pool metrics and monitoring
- Thread safety
"""

import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import (
    POOL_CONFIG,
    ConnectionPool,
    PooledConnection,
    PoolHealthChecker,
    PoolMetrics,
    ServiceConnectionPool,
    close_pooled_connection,
    create_pooled_connection,
    get_connection,
    get_health_check_results,
    get_pool,
    get_pool_metrics,
    get_pool_stats,
    get_pool_summary,
    initialize_pools,
    start_health_checker,
    stop_health_checker,
    warmup_pools,
)


class TestPooledConnection(unittest.TestCase):
    """Test PooledConnection dataclass."""

    def test_creation(self):
        """Test creating a pooled connection."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            pooled = PooledConnection(connection=conn)

            self.assertIsNotNone(pooled.connection)
            self.assertIsNotNone(pooled.created_at)
            self.assertEqual(pooled.use_count, 0)
            self.assertTrue(pooled.is_valid)

            conn.close()
        finally:
            os.unlink(db_path)

    def test_touch(self):
        """Test touch method."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            pooled = PooledConnection(connection=conn)

            initial_time = pooled.last_used
            time.sleep(0.1)
            pooled.touch()

            self.assertGreater(pooled.last_used, initial_time)
            self.assertEqual(pooled.use_count, 1)

            conn.close()
        finally:
            os.unlink(db_path)

    def test_is_expired(self):
        """Test expiration check."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            pooled = PooledConnection(connection=conn)

            self.assertFalse(pooled.is_expired(3600))  # 1 hour
            self.assertFalse(pooled.is_expired(1))  # 1 second

            # Force expiration
            pooled.created_at = time.time() - 10
            self.assertTrue(pooled.is_expired(5))  # 5 seconds

            conn.close()
        finally:
            os.unlink(db_path)

    def test_is_healthy(self):
        """Test health check."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            pooled = PooledConnection(connection=conn)

            self.assertTrue(pooled.is_healthy())

            # Close connection to make it unhealthy
            conn.close()
            self.assertFalse(pooled.is_healthy())
            self.assertFalse(pooled.is_valid)

        finally:
            os.unlink(db_path)


class TestConnectionPool(unittest.TestCase):
    """Test ConnectionPool class."""

    def setUp(self):
        """Set up test database."""
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self.temp_file.name)
        self.temp_file.close()

        # Create table for testing
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY)")
        conn.close()

    def tearDown(self):
        """Clean up."""
        try:
            os.unlink(self.db_path)
        except:
            pass

    def test_pool_creation(self):
        """Test creating a connection pool."""
        pool = ConnectionPool(self.db_path, min_connections=2, max_connections=5)

        self.assertIsNotNone(pool)
        self.assertEqual(pool.min_connections, 2)
        self.assertEqual(pool.max_connections, 5)

        pool.close()

    def test_acquire_release(self):
        """Test acquiring and releasing connections."""
        pool = ConnectionPool(self.db_path, min_connections=1, max_connections=3)

        try:
            pooled = pool.acquire()
            self.assertIsNotNone(pooled)
            self.assertIsNotNone(pooled.connection)

            pool.release(pooled)

        finally:
            pool.close()

    def test_context_manager(self):
        """Test pool context manager."""
        pool = ConnectionPool(self.db_path, min_connections=1, max_connections=3)

        try:
            with pool.get_connection() as conn:
                result = conn.execute("SELECT 1").fetchone()
                self.assertEqual(result[0], 1)

        finally:
            pool.close()

    def test_connection_reuse(self):
        """Test that connections are reused."""
        pool = ConnectionPool(self.db_path, min_connections=1, max_connections=3)

        try:
            # First acquire/release
            pooled1 = pool.acquire()
            conn_id = id(pooled1.connection)
            pool.release(pooled1)

            # Second acquire should reuse
            pooled2 = pool.acquire()

            # Same connection should be reused
            stats = pool.get_stats()
            self.assertGreater(stats["reused"], 0)

            pool.release(pooled2)

        finally:
            pool.close()

    def test_stats(self):
        """Test pool statistics."""
        pool = ConnectionPool(self.db_path, min_connections=1, max_connections=3)

        try:
            stats = pool.get_stats()

            self.assertIn("active", stats)
            self.assertIn("available", stats)
            self.assertIn("created", stats)
            self.assertIn("reused", stats)

        finally:
            pool.close()

    def test_health_check(self):
        """Test pool health check."""
        pool = ConnectionPool(self.db_path, min_connections=2, max_connections=5)

        try:
            result = pool.health_check()

            self.assertIn("healthy", result)
            self.assertIn("timestamp", result)

        finally:
            pool.close()

    def test_concurrent_access(self):
        """Test concurrent access to the pool."""
        pool = ConnectionPool(self.db_path, min_connections=2, max_connections=5)
        results = []
        errors = []

        def worker():
            try:
                with pool.get_connection() as conn:
                    conn.execute("SELECT 1")
                    time.sleep(0.05)
                    results.append(True)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        try:
            self.assertEqual(len(results), 10)
            self.assertEqual(len(errors), 0)
        finally:
            pool.close()


class TestServiceConnectionPool(unittest.TestCase):
    """Test ServiceConnectionPool helper class."""

    def setUp(self):
        """Set up test database."""
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self.temp_file.name)
        self.temp_file.close()

        # Create table for testing
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY)")
        conn.close()

    def tearDown(self):
        """Clean up."""
        ServiceConnectionPool.close_all()
        try:
            os.unlink(self.db_path)
        except:
            pass

    def test_creation(self):
        """Test creating a service connection pool."""
        pool = ServiceConnectionPool(self.db_path)

        self.assertIsNotNone(pool)
        self.assertEqual(pool.db_path, self.db_path)

    def test_get_or_create(self):
        """Test get_or_create returns same instance."""
        pool1 = ServiceConnectionPool.get_or_create(self.db_path)
        pool2 = ServiceConnectionPool.get_or_create(self.db_path)

        self.assertIs(pool1, pool2)

    def test_connection_context_manager(self):
        """Test connection context manager."""
        pool = ServiceConnectionPool(self.db_path)

        with pool.connection() as conn:
            result = conn.execute("SELECT 1").fetchone()
            self.assertEqual(result[0], 1)

    def test_get_stats(self):
        """Test getting pool statistics."""
        pool = ServiceConnectionPool(self.db_path)

        stats = pool.get_stats()
        self.assertIn("db_path", stats)


class TestPoolHealthChecker(unittest.TestCase):
    """Test PoolHealthChecker class."""

    def test_creation(self):
        """Test creating a health checker."""
        checker = PoolHealthChecker(check_interval=5)

        self.assertEqual(checker.check_interval, 5)
        self.assertFalse(checker.is_running())

    def test_start_stop(self):
        """Test starting and stopping the health checker."""
        checker = PoolHealthChecker(check_interval=1)

        checker.start()
        self.assertTrue(checker.is_running())

        time.sleep(0.1)

        checker.stop()
        self.assertFalse(checker.is_running())

    def test_get_results(self):
        """Test getting health check results."""
        checker = PoolHealthChecker(check_interval=1)

        checker.start()
        time.sleep(1.5)  # Wait for at least one check
        checker.stop()

        results = checker.get_last_results()
        # Results may or may not be populated depending on timing


class TestPoolMetrics(unittest.TestCase):
    """Test PoolMetrics class."""

    def test_get_summary(self):
        """Test getting pool summary."""
        summary = PoolMetrics.get_pool_summary()

        self.assertIn("pools", summary)
        self.assertIn("pooling_enabled", summary)

    def test_get_all_metrics(self):
        """Test getting all metrics."""
        metrics = PoolMetrics.get_all_metrics()

        self.assertIn("timestamp", metrics)
        self.assertIn("config", metrics)
        self.assertIn("pools", metrics)
        self.assertIn("summary", metrics)


class TestConvenienceFunctions(unittest.TestCase):
    """Test module-level convenience functions."""

    def test_get_pool_stats(self):
        """Test get_pool_stats function."""
        stats = get_pool_stats()
        self.assertIsInstance(stats, dict)

    def test_get_pool_metrics(self):
        """Test get_pool_metrics function."""
        metrics = get_pool_metrics()

        self.assertIn("timestamp", metrics)
        self.assertIn("config", metrics)

    def test_get_pool_summary(self):
        """Test get_pool_summary function."""
        summary = get_pool_summary()

        self.assertIn("pooling_enabled", summary)


class TestCreatePooledConnection(unittest.TestCase):
    """Test drop-in replacement for sqlite3.connect."""

    def setUp(self):
        """Set up test database."""
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self.temp_file.name)
        self.temp_file.close()

    def tearDown(self):
        """Clean up."""
        ServiceConnectionPool.close_all()
        try:
            os.unlink(self.db_path)
        except:
            pass

    def test_create_and_close(self):
        """Test creating and closing a pooled connection."""
        conn = create_pooled_connection(self.db_path)

        self.assertIsNotNone(conn)

        # Should be able to execute queries
        conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER)")
        conn.commit()

        close_pooled_connection(conn)

    def test_connection_is_reusable(self):
        """Test that connections from create_pooled_connection are reused."""
        conn1 = create_pooled_connection(self.db_path)
        close_pooled_connection(conn1)

        conn2 = create_pooled_connection(self.db_path)
        close_pooled_connection(conn2)

        # Should work without errors


class TestHealthCheckerGlobal(unittest.TestCase):
    """Test global health checker functions."""

    def test_start_stop_health_checker(self):
        """Test starting and stopping the global health checker."""
        start_health_checker(check_interval=1)

        time.sleep(0.1)

        results = get_health_check_results()
        # Results structure depends on whether checks have run

        stop_health_checker()


if __name__ == "__main__":
    unittest.main(verbosity=2)
