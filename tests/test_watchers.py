#!/usr/bin/env python3
"""Test script for task watchers/subscribers endpoints."""

import json
import sys

import requests


def test_watchers_endpoints(base_url="http://localhost:8080", session_cookie=None):
    """Test the task watchers endpoints."""

    print("Testing Task Watchers/Subscribers Endpoints")
    print("=" * 50)

    headers = {}
    cookies = {}

    if session_cookie:
        cookies["session"] = session_cookie

    # Test 1: Get available watch types
    print("\n1. GET /api/watchers/types")
    try:
        resp = requests.get(
            f"{base_url}/api/watchers/types", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Watch types: {list(data.get('watch_types', {}).keys())}")
            print(f"   Task types: {data.get('task_types', [])}")
            print(f"   Event types: {data.get('event_types', [])}")
        elif resp.status_code == 401:
            print("   (Authentication required - need session cookie)")
        else:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 2: Get user's watch preferences
    print("\n2. GET /api/watchers/preferences")
    try:
        resp = requests.get(
            f"{base_url}/api/watchers/preferences", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Auto-watch created: {data.get('auto_watch_created')}")
            print(f"   Auto-watch assigned: {data.get('auto_watch_assigned')}")
            print(f"   Digest frequency: {data.get('digest_frequency')}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 3: Get user's watched tasks
    print("\n3. GET /api/watchers/my-watches")
    try:
        resp = requests.get(
            f"{base_url}/api/watchers/my-watches", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Total watches: {data.get('total', 0)}")
            by_type = data.get("by_type", {})
            for task_type, watches in by_type.items():
                print(f"     - {task_type}: {len(watches)} watches")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 4: Get watcher stats
    print("\n4. GET /api/watchers/stats")
    try:
        resp = requests.get(
            f"{base_url}/api/watchers/stats", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Total watches: {data.get('total_watches', 0)}")
            print(f"   Unread events: {data.get('unread_events', 0)}")
            watches_by_type = data.get("watches_by_type", {})
            if watches_by_type:
                print(f"   Watches by type: {watches_by_type}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 5: Get global stats
    print("\n5. GET /api/watchers/stats?global=true")
    try:
        resp = requests.get(
            f"{base_url}/api/watchers/stats",
            params={"global": "true"},
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Total watchers: {data.get('total_watchers', 0)}")
            print(f"   Total watches: {data.get('total_watches', 0)}")
            print(f"   Events last 24h: {data.get('events_last_24h', 0)}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 6: Get unread events
    print("\n6. GET /api/watchers/events")
    try:
        resp = requests.get(
            f"{base_url}/api/watchers/events", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Unread events: {data.get('count', 0)}")
            events = data.get("events", [])
            for event in events[:3]:
                print(
                    f"     - {event.get('event_type')} on {event.get('task_type')} {event.get('task_id')}"
                )
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 7: Check if watching a task
    print("\n7. GET /api/watchers/check?task_id=1&task_type=feature")
    try:
        resp = requests.get(
            f"{base_url}/api/watchers/check",
            params={"task_id": 1, "task_type": "feature"},
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Is watching: {data.get('is_watching', False)}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 8: Watch a task (example - may fail if task doesn't exist)
    print("\n8. POST /api/watchers/watch (watch feature 1)")
    try:
        resp = requests.post(
            f"{base_url}/api/watchers/watch",
            json={"task_id": 1, "task_type": "feature", "watch_type": "all"},
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code in [200, 201]:
            data = resp.json()
            print(f"   Success: {data.get('success')}")
            print(f"   Message: {data.get('message')}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
        else:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 9: Get watchers for a task
    print("\n9. GET /api/watchers/task/feature/1")
    try:
        resp = requests.get(
            f"{base_url}/api/watchers/task/feature/1", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Watcher count: {data.get('watcher_count', 0)}")
            print(f"   Current user watching: {data.get('is_watching', False)}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 50)
    print("Task watchers endpoint tests complete!")


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    session = sys.argv[2] if len(sys.argv) > 2 else None
    test_watchers_endpoints(base_url, session)
