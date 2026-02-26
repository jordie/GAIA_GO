#!/usr/bin/env python3
"""
Quick integration test for rate limiting and resource monitoring services.
Tests that all components are properly initialized and working.
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all services can be imported."""
    print("Testing imports...")
    try:
        from services.rate_limiting import RateLimitService
        from services.resource_monitor import ResourceMonitor
        from services.background_tasks import BackgroundTaskManager, get_background_task_manager
        from services.rate_limiting_routes import rate_limiting_bp
        print("  ✓ All services imported successfully")
        return True
    except ImportError as e:
        print(f"  ✗ Import failed: {e}")
        return False


def test_database():
    """Test that database has required tables."""
    print("\nTesting database schema...")
    try:
        import sqlite3
        conn = sqlite3.connect("data/architect.db")
        cursor = conn.cursor()

        # Check for required tables
        tables = [
            "rate_limit_configs",
            "rate_limit_buckets",
            "rate_limit_violations",
            "resource_quotas",
            "resource_consumption",
            "system_load_history",
            "rate_limit_stats"
        ]

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        missing = [t for t in tables if t not in existing_tables]
        if missing:
            print(f"  ✗ Missing tables: {missing}")
            return False

        print(f"  ✓ All 7 required tables exist")

        # Check for indexes
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        index_count = cursor.fetchone()[0]
        print(f"  ✓ Found {index_count} indexes")

        conn.close()
        return True
    except Exception as e:
        print(f"  ✗ Database check failed: {e}")
        return False


def test_services():
    """Test that services can be instantiated."""
    print("\nTesting service instantiation...")
    try:
        from services.rate_limiting import RateLimitService
        from services.resource_monitor import ResourceMonitor
        from services.background_tasks import BackgroundTaskManager
        from db import get_db_connection

        # Test RateLimitService
        rate_limiter = RateLimitService(get_db_connection)
        configs = rate_limiter.get_all_configs()
        print(f"  ✓ RateLimitService initialized ({len(configs)} configs)")

        # Test ResourceMonitor
        monitor = ResourceMonitor(get_db_connection)
        health = monitor.get_health_status()
        print(f"  ✓ ResourceMonitor initialized (CPU: {health['current']['cpu_percent']:.1f}%)")

        # Test BackgroundTaskManager
        manager = BackgroundTaskManager()
        print(f"  ✓ BackgroundTaskManager initialized")

        return True
    except Exception as e:
        print(f"  ✗ Service instantiation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rate_limiting():
    """Test rate limiting functionality."""
    print("\nTesting rate limiting functionality...")
    try:
        from services.rate_limiting import RateLimitService
        from db import get_db_connection

        service = RateLimitService(get_db_connection)

        # Create a test config
        success = service.create_config(
            rule_name="test_rule",
            scope="ip",
            limit_type="requests_per_minute",
            limit_value=10
        )

        if not success:
            print("  ✗ Failed to create test config")
            return False

        print("  ✓ Created test rate limit rule")

        # Test check_limit
        allowed, info = service.check_limit("ip", "192.168.1.1", "test")
        print(f"  ✓ Rate limit check works (allowed: {allowed})")

        # Get stats
        stats = service.get_stats(days=1)
        print(f"  ✓ Statistics retrieval works ({stats.get('total_requests', 0)} requests)")

        # Disable config
        service.disable_config("test_rule")
        print("  ✓ Config management works")

        return True
    except Exception as e:
        print(f"  ✗ Rate limiting test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_resource_monitoring():
    """Test resource monitoring functionality."""
    print("\nTesting resource monitoring functionality...")
    try:
        from services.resource_monitor import ResourceMonitor
        from db import get_db_connection

        monitor = ResourceMonitor(get_db_connection)

        # Get current load
        load = monitor.get_current_load()
        print(f"  ✓ Current load retrieved (CPU: {load['cpu_percent']:.1f}%)")

        # Record snapshot
        snapshot = monitor.record_snapshot()
        print(f"  ✓ Resource snapshot recorded (Memory: {snapshot['memory_percent']:.1f}%)")

        # Check throttle status
        should_throttle, reason = monitor.should_throttle()
        print(f"  ✓ Throttle status checked (throttle: {should_throttle})")

        # Get health status
        health = monitor.get_health_status()
        print(f"  ✓ Health status retrieved (healthy: {health['healthy']})")

        return True
    except Exception as e:
        print(f"  ✗ Resource monitoring test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests."""
    print("=" * 70)
    print("RATE LIMITING INTEGRATION TEST")
    print("=" * 70)

    tests = [
        test_imports,
        test_database,
        test_services,
        test_rate_limiting,
        test_resource_monitoring,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n✗ Test {test.__name__} crashed: {e}")
            results.append(False)

    print("\n" + "=" * 70)
    print(f"RESULTS: {sum(results)}/{len(results)} tests passed")
    print("=" * 70)

    if all(results):
        print("\n✅ ALL INTEGRATION TESTS PASSED")
        print("\nRate limiting services are properly integrated and functional.")
        print("\nNext steps:")
        print("1. Start the app: python3 app.py")
        print("2. Test endpoints: curl http://localhost:8080/api/rate-limiting/dashboard")
        print("3. Monitor logs for initialization messages")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        print("\nPlease review errors above and check:")
        print("1. Database migration applied")
        print("2. All service files exist")
        print("3. Database connection working")
        return 1


if __name__ == "__main__":
    sys.exit(main())
