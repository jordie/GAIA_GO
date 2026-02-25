#!/usr/bin/env python3
"""
Test script for cleanup API endpoints

Usage:
    python3 test_cleanup_api.py
"""

import json
from getpass import getpass

import requests

# Configuration
BASE_URL = "http://localhost:8080"
USERNAME = "architect"
PASSWORD = None  # Will prompt


def login(session, username, password):
    """Login and get session cookie"""
    response = session.post(f"{BASE_URL}/login", data={"username": username, "password": password})
    if response.status_code != 200:
        raise Exception(f"Login failed: {response.status_code}")
    print("✓ Logged in successfully")
    return session


def test_cleanup_status(session):
    """Test cleanup status endpoint"""
    print("\n=== Testing Cleanup Status ===")
    response = session.get(f"{BASE_URL}/api/system/cleanup/status")

    if response.status_code != 200:
        print(f"✗ Failed: {response.status_code}")
        print(response.text)
        return False

    data = response.json()
    print(f"✓ Status endpoint working")
    print(f"  Daemon running: {data.get('daemon_running')}")
    print(f"  Last run: {data.get('last_run')}")

    if data.get("last_stats"):
        stats = data["last_stats"]
        print(f"  Last cleanup freed: {stats.get('space_freed_mb')} MB")
        print(f"  Backups deleted: {stats.get('backups_deleted')}")

    return True


def test_cleanup_dry_run(session):
    """Test cleanup with dry run"""
    print("\n=== Testing Cleanup Dry Run ===")
    response = session.post(f"{BASE_URL}/api/system/cleanup", json={"dry_run": True})

    if response.status_code != 200:
        print(f"✗ Failed: {response.status_code}")
        print(response.text)
        return False

    data = response.json()
    print(f"✓ Dry run completed")
    print(f"  Message: {data.get('message')}")

    if data.get("stats"):
        stats = data["stats"]
        print(f"  Would delete {stats.get('backups_deleted')} backups")
        print(f"  Would free {stats.get('space_freed_mb')} MB")

    return True


def test_cleanup_custom_settings(session):
    """Test cleanup with custom settings"""
    print("\n=== Testing Cleanup with Custom Settings ===")
    response = session.post(
        f"{BASE_URL}/api/system/cleanup",
        json={"dry_run": True, "backup_retention": 15, "log_age_days": 60, "task_age_days": 14},
    )

    if response.status_code != 200:
        print(f"✗ Failed: {response.status_code}")
        print(response.text)
        return False

    data = response.json()
    print(f"✓ Custom settings applied")
    print(f"  Message: {data.get('message')}")

    return True


def main():
    """Run all tests"""
    print("Architect Dashboard - Cleanup API Tests")
    print("=" * 50)

    # Get password
    global PASSWORD
    PASSWORD = getpass(f"Password for {USERNAME}: ")

    # Create session
    session = requests.Session()

    try:
        # Login
        login(session, USERNAME, PASSWORD)

        # Run tests
        tests = [
            test_cleanup_status,
            test_cleanup_dry_run,
            test_cleanup_custom_settings,
        ]

        passed = 0
        failed = 0

        for test in tests:
            try:
                if test(session):
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"✗ Test failed with exception: {e}")
                failed += 1

        # Summary
        print("\n" + "=" * 50)
        print(f"Tests passed: {passed}/{len(tests)}")
        print(f"Tests failed: {failed}/{len(tests)}")

        if failed == 0:
            print("✓ All tests passed!")
            return 0
        else:
            print("✗ Some tests failed")
            return 1

    except Exception as e:
        print(f"✗ Fatal error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
