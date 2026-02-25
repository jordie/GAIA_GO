#!/usr/bin/env python3
"""Test script for status history endpoints."""

import json
import sys

import requests


def test_status_history(base_url="http://localhost:8080", session_cookie=None):
    """Test the status history endpoints."""

    print("Testing Status History Endpoints")
    print("=" * 50)

    headers = {}
    cookies = {}

    if session_cookie:
        cookies["session"] = session_cookie

    # Test 1: Get recent changes
    print("\n1. GET /api/status-history/recent")
    try:
        resp = requests.get(
            f"{base_url}/api/status-history/recent",
            headers=headers,
            cookies=cookies,
            params={"hours": 168, "limit": 20},  # Last week
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Recent changes: {data.get('count')}")
            print(f"   Period: {data.get('period_hours')} hours")
            changes = data.get("changes", [])[:3]
            for c in changes:
                print(
                    f"     - {c['entity_type']}#{c['entity_id']}: {c.get('old_status')} -> {c['new_status']}"
                )
        elif resp.status_code == 401:
            print("   (Authentication required - need session cookie)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 2: Get transition stats
    print("\n2. GET /api/status-history/stats")
    try:
        resp = requests.get(
            f"{base_url}/api/status-history/stats",
            headers=headers,
            cookies=cookies,
            params={"days": 30},
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Period: {data.get('period_days')} days")
            print(f"   Total changes: {data.get('total_changes')}")
            by_type = data.get("by_entity_type", [])
            if by_type:
                print(f"   By entity type:")
                for t in by_type[:5]:
                    print(f"     - {t['entity_type']}: {t['count']}")
            transitions = data.get("common_transitions", [])
            if transitions:
                print(f"   Common transitions:")
                for t in transitions[:5]:
                    print(f"     - {t['from']} -> {t['to']}: {t['count']}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 3: Get entity history
    print("\n3. GET /api/status-history/feature/1 (if exists)")
    try:
        resp = requests.get(
            f"{base_url}/api/status-history/feature/1", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Entity: {data.get('entity_type')}#{data.get('entity_id')}")
            print(f"   History records: {data.get('count')}")
            history = data.get("history", [])[:5]
            for h in history:
                print(
                    f"     - {h.get('old_status')} -> {h['new_status']} by {h.get('changed_by')} at {h['created_at'][:19]}"
                )
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 4: Get status durations
    print("\n4. GET /api/status-history/feature/1/duration (if exists)")
    try:
        resp = requests.get(
            f"{base_url}/api/status-history/feature/1/duration",
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Total time: {data.get('total_hours')} hours")
            by_status = data.get("by_status", {})
            if by_status:
                print(f"   Time by status:")
                for status, hours in by_status.items():
                    print(f"     - {status}: {hours} hours")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 5: Get allowed transitions
    print("\n5. GET /api/status-history/transitions/feature/in_progress")
    try:
        resp = requests.get(
            f"{base_url}/api/status-history/transitions/feature/in_progress",
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Current status: {data.get('current_status')}")
            print(f"   Allowed transitions: {data.get('allowed_transitions')}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 6: Check specific transition
    print("\n6. POST /api/status-history/transitions/check")
    try:
        resp = requests.post(
            f"{base_url}/api/status-history/transitions/check",
            headers=headers,
            cookies=cookies,
            json={"entity_type": "feature", "from_status": "in_progress", "to_status": "review"},
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Transition: {data.get('from_status')} -> {data.get('to_status')}")
            print(f"   Allowed: {data.get('is_allowed')}")
            print(f"   Requires reason: {data.get('requires_reason')}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 7: Record a status change
    print("\n7. POST /api/status-history/ (record change)")
    try:
        resp = requests.post(
            f"{base_url}/api/status-history/",
            headers=headers,
            cookies=cookies,
            json={
                "entity_type": "feature",
                "entity_id": 999,
                "old_status": "draft",
                "new_status": "planned",
                "change_reason": "Test change from API",
            },
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 201:
            data = resp.json()
            print(f"   Success: {data.get('success')}")
            record = data.get("record", {})
            print(f"   Record ID: {record.get('id')}")
        elif resp.status_code == 200:
            data = resp.json()
            print(f"   Message: {data.get('message')}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 8: Get my changes
    print("\n8. GET /api/status-history/my-changes")
    try:
        resp = requests.get(
            f"{base_url}/api/status-history/my-changes",
            headers=headers,
            cookies=cookies,
            params={"limit": 10},
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   User: {data.get('user_id')}")
            print(f"   My changes: {data.get('count')}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 9: Search history
    print("\n9. GET /api/status-history/search")
    try:
        resp = requests.get(
            f"{base_url}/api/status-history/search",
            headers=headers,
            cookies=cookies,
            params={"entity_type": "feature", "status": "completed", "limit": 10},
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Results: {data.get('count')}")
            filters = data.get("filters", {})
            print(
                f"   Filters: entity_type={filters.get('entity_type')}, status={filters.get('status')}"
            )
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 50)
    print("Status history endpoint tests complete!")
    print("\nAvailable endpoints:")
    print("  GET  /api/status-history/<type>/<id> - Get entity history")
    print("  GET  /api/status-history/<type>/<id>/duration - Get time in each status")
    print("  GET  /api/status-history/recent - Get recent changes")
    print("  GET  /api/status-history/stats - Get transition statistics")
    print("  GET  /api/status-history/user/<id> - Get user's changes")
    print("  GET  /api/status-history/my-changes - Get current user's changes")
    print("  GET  /api/status-history/transitions/<type>/<status> - Get allowed transitions")
    print("  POST /api/status-history/transitions/check - Check if transition allowed")
    print("  POST /api/status-history/ - Record a status change")
    print("  GET  /api/status-history/search - Search history")


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    session = sys.argv[2] if len(sys.argv) > 2 else None
    test_status_history(base_url, session)
