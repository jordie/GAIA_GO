#!/usr/bin/env python3
"""Test script for AI task suggestions endpoints."""

import json
import sys

import requests


def test_suggestions(base_url="http://localhost:8080", session_cookie=None):
    """Test the AI task suggestions endpoints."""

    print("Testing AI Task Suggestions Endpoints")
    print("=" * 50)

    headers = {}
    cookies = {}

    if session_cookie:
        cookies["session"] = session_cookie

    # Test 1: Get all suggestions
    print("\n1. GET /api/tasks/suggested")
    try:
        resp = requests.get(
            f"{base_url}/api/tasks/suggested",
            headers=headers,
            cookies=cookies,
            params={"limit": 10},
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Suggestions: {data.get('count')}")
            print(f"   Total candidates: {data.get('total_candidates')}")
            print(f"   Generated at: {data.get('generated_at', '')[:19]}")

            suggestions = data.get("suggestions", [])[:5]
            if suggestions:
                print(f"\n   Top suggestions:")
                for s in suggestions:
                    print(f"     [{s['score']}] {s['type']}: {s['title'][:40]}")
                    print(f"         Action: {s['action']}")

            summary = data.get("summary", {})
            if summary:
                print(f"\n   Summary:")
                features = summary.get("features", {})
                print(
                    f"     Features: {features.get('total')} total, {features.get('in_progress')} in progress, {features.get('blocked')} blocked"
                )
                bugs = summary.get("bugs", {})
                print(
                    f"     Bugs: {bugs.get('total')} total, {bugs.get('open')} open, {bugs.get('critical_open')} critical"
                )
        elif resp.status_code == 401:
            print("   (Authentication required - need session cookie)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 2: Get suggestion types
    print("\n2. GET /api/tasks/suggested/types")
    try:
        resp = requests.get(
            f"{base_url}/api/tasks/suggested/types", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Available types: {data.get('count')}")
            for t in data.get("types", []):
                print(f"     - {t['id']}: {t['description']}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 3: Get personalized suggestions
    print("\n3. GET /api/tasks/suggested/personalized")
    try:
        resp = requests.get(
            f"{base_url}/api/tasks/suggested/personalized",
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   User: {data.get('user_id')}")
            print(f"   Personalized suggestions: {data.get('count')}")
            for s in data.get("suggestions", [])[:3]:
                print(f"     - {s['title']}: {s['reason']}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 4: Get quick wins
    print("\n4. GET /api/tasks/suggested/quick-wins")
    try:
        resp = requests.get(
            f"{base_url}/api/tasks/suggested/quick-wins",
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Quick wins: {data.get('count')}")
            for s in data.get("quick_wins", [])[:3]:
                print(f"     - {s['title']}: {s.get('estimated_hours', 'N/A')} hours")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 5: Get urgent suggestions
    print("\n5. GET /api/tasks/suggested/urgent")
    try:
        resp = requests.get(
            f"{base_url}/api/tasks/suggested/urgent", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Urgent items: {data.get('count')}")
            for s in data.get("urgent", [])[:3]:
                print(f"     - [{s['type']}] {s['title']}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 6: Get next task
    print("\n6. GET /api/tasks/suggested/next")
    try:
        resp = requests.get(
            f"{base_url}/api/tasks/suggested/next", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            suggestion = data.get("suggestion")
            if suggestion:
                print(f"   Next task: {suggestion['title']}")
                print(f"   Type: {suggestion['type']}")
                print(f"   Score: {suggestion['score']}")
                print(f"   Action: {suggestion['action']}")
            else:
                print(f"   Message: {data.get('message')}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 7: Get project-specific suggestions
    print("\n7. GET /api/tasks/suggested/project/1 (if project exists)")
    try:
        resp = requests.get(
            f"{base_url}/api/tasks/suggested/project/1",
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Project ID: {data.get('project_id')}")
            print(f"   Suggestions: {data.get('count')}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 8: Get filtered suggestions
    print("\n8. GET /api/tasks/suggested?types=high_priority,blocked")
    try:
        resp = requests.get(
            f"{base_url}/api/tasks/suggested",
            headers=headers,
            cookies=cookies,
            params={"types": "high_priority,blocked", "limit": 5},
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Filtered suggestions: {data.get('count')}")
            types_found = set(s["type"] for s in data.get("suggestions", []))
            print(f"   Types in result: {', '.join(types_found)}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 9: Get summary only
    print("\n9. GET /api/tasks/suggested/summary")
    try:
        resp = requests.get(
            f"{base_url}/api/tasks/suggested/summary", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            summary = data.get("summary", {})
            features = summary.get("features", {})
            bugs = summary.get("bugs", {})
            tasks = summary.get("tasks", {})
            print(
                f"   Features: {features.get('total', 0)} ({features.get('in_progress', 0)} in progress)"
            )
            print(f"   Bugs: {bugs.get('total', 0)} ({bugs.get('open', 0)} open)")
            print(f"   Tasks: {tasks.get('total', 0)} ({tasks.get('pending', 0)} pending)")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 50)
    print("AI task suggestions endpoint tests complete!")
    print("\nAvailable endpoints:")
    print("  GET /api/tasks/suggested - Get all suggestions")
    print("  GET /api/tasks/suggested/types - List suggestion types")
    print("  GET /api/tasks/suggested/personalized - User-specific suggestions")
    print("  GET /api/tasks/suggested/project/<id> - Project suggestions")
    print("  GET /api/tasks/suggested/quick-wins - Easy tasks")
    print("  GET /api/tasks/suggested/urgent - High priority/blocked/overdue")
    print("  GET /api/tasks/suggested/next - Single best suggestion")
    print("  GET /api/tasks/suggested/summary - Work item summary")


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    session = sys.argv[2] if len(sys.argv) > 2 else None
    test_suggestions(base_url, session)
