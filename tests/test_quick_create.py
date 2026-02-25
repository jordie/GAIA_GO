#!/usr/bin/env python3
"""Test script for quick create endpoints."""

import json
import sys

import requests


def test_quick_create(base_url="http://localhost:8080", session_cookie=None):
    """Test the quick create endpoints."""

    print("Testing Quick Create Endpoints")
    print("=" * 50)

    headers = {}
    cookies = {}

    if session_cookie:
        cookies["session"] = session_cookie

    # Test 1: Get quick create options
    print("\n1. GET /api/quick-create/options")
    try:
        resp = requests.get(
            f"{base_url}/api/quick-create/options", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Projects: {len(data.get('projects', []))}")
            print(f"   Milestones: {len(data.get('milestones', []))}")
            print(f"   Task types: {data.get('task_types', [])[:5]}")
            print(f"   Entity types: {data.get('entity_types', [])}")
        elif resp.status_code == 401:
            print("   (Authentication required - need session cookie)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 2: Get templates
    print("\n2. GET /api/quick-create/templates")
    try:
        resp = requests.get(
            f"{base_url}/api/quick-create/templates", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Templates: {data.get('count')}")
            for t in data.get("templates", [])[:5]:
                print(f"     - {t['name']} ({t['entity_type']})")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 3: Parse quick input
    print("\n3. POST /api/quick-create/parse")
    try:
        test_inputs = [
            "feature: Add login page @1 #high",
            "bug: Button not working @project:2 !critical +john",
            "task: Run tests",
            "milestone: Sprint 5 @1",
        ]
        for text in test_inputs:
            resp = requests.post(
                f"{base_url}/api/quick-create/parse",
                headers=headers,
                cookies=cookies,
                json={"text": text},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                print(f"   Input: '{text}'")
                print(f"   Parsed: type={data['entity_type']}, data={data['data']}")
            elif resp.status_code == 401:
                print("   (Authentication required)")
                break
    except Exception as e:
        print(f"   Error: {e}")

    # Test 4: Quick create feature (dry run - we just show what would be sent)
    print("\n4. POST /api/quick-create/feature (test payload)")
    try:
        payload = {
            "name": "Test Quick Feature",
            "project_id": 1,
            "priority": "medium",
            "description": "Created via quick create test",
        }
        print(f"   Would send: {json.dumps(payload, indent=4)}")
        # Uncomment to actually create:
        # resp = requests.post(
        #     f"{base_url}/api/quick-create/feature",
        #     headers=headers,
        #     cookies=cookies,
        #     json=payload,
        #     timeout=10
        # )
        # print(f"   Status: {resp.status_code}")
        # print(f"   Response: {resp.json()}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 5: Quick create bug (dry run)
    print("\n5. POST /api/quick-create/bug (test payload)")
    try:
        payload = {
            "title": "Test Quick Bug",
            "project_id": 1,
            "severity": "low",
            "description": "Created via quick create test",
        }
        print(f"   Would send: {json.dumps(payload, indent=4)}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 6: Quick create task (dry run)
    print("\n6. POST /api/quick-create/task (test payload)")
    try:
        payload = {
            "task_type": "shell",
            "name": "Run quick test",
            "priority": 0,
            "task_data": {"command": "echo hello"},
        }
        print(f"   Would send: {json.dumps(payload, indent=4)}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 7: Get recent creates
    print("\n7. GET /api/quick-create/recent")
    try:
        resp = requests.get(
            f"{base_url}/api/quick-create/recent",
            headers=headers,
            cookies=cookies,
            params={"limit": 5},
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Recent items: {data.get('count')}")
            for item in data.get("recent", [])[:3]:
                print(f"     - [{item['entity_type']}] {item['title']}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 8: Generic quick create endpoint
    print("\n8. POST /api/quick-create/ (generic)")
    try:
        payload = {
            "entity_type": "devops_task",
            "name": "Database backup",
            "category": "maintenance",
            "priority": "high",
        }
        print(f"   Would send: {json.dumps(payload, indent=4)}")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 50)
    print("Quick create endpoint tests complete!")
    print("\nAvailable endpoints:")
    print("  POST /api/quick-create/ - Generic create (requires entity_type)")
    print("  POST /api/quick-create/feature - Create feature")
    print("  POST /api/quick-create/bug - Create bug")
    print("  POST /api/quick-create/task - Create task")
    print("  POST /api/quick-create/milestone - Create milestone")
    print("  POST /api/quick-create/parse - Parse quick input text")
    print("  POST /api/quick-create/parse-and-create - Parse and create in one call")
    print("  GET /api/quick-create/options - Get dropdown options")
    print("  GET /api/quick-create/templates - Get quick create templates")
    print("  GET /api/quick-create/recent - Get recently created items")
    print("\nQuick input syntax:")
    print("  @N or @project:N - Set project ID")
    print("  %N or %milestone:N - Set milestone ID")
    print("  #priority - Set priority (critical, high, medium, low)")
    print("  !severity - Set severity for bugs")
    print("  +username - Assign to user")


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    session = sys.argv[2] if len(sys.argv) > 2 else None
    test_quick_create(base_url, session)
