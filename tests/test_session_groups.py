#!/usr/bin/env python3
"""Test script for tmux session grouping endpoints."""

import json
import sys

import requests


def test_session_groups(base_url="http://localhost:8080", session_cookie=None):
    """Test the session grouping endpoints."""

    print("Testing Tmux Session Grouping Endpoints")
    print("=" * 50)

    headers = {}
    cookies = {}

    if session_cookie:
        cookies["session"] = session_cookie

    # Test 1: Get grouped sessions
    print("\n1. GET /api/tmux/groups")
    try:
        resp = requests.get(
            f"{base_url}/api/tmux/groups", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Total sessions: {data.get('total_sessions', 0)}")
            print(f"   Total attached: {data.get('total_attached', 0)}")
            groups = data.get("groups", [])
            print(f"   Groups: {len(groups)}")
            for g in groups[:5]:
                print(
                    f"     - {g['icon']} {g['name']}: {g['total_count']} sessions ({g['attached_count']} attached)"
                )
        elif resp.status_code == 401:
            print("   (Authentication required - need session cookie)")
        else:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 2: Get available projects
    print("\n2. GET /api/tmux/groups/projects")
    try:
        resp = requests.get(
            f"{base_url}/api/tmux/groups/projects", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            projects = data.get("projects", [])
            print(f"   Available projects: {len(projects)}")
            for p in projects[:5]:
                print(f"     - {p['name']} (id: {p['id']})")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 3: Get collapsed groups
    print("\n3. GET /api/tmux/groups/collapsed")
    try:
        resp = requests.get(
            f"{base_url}/api/tmux/groups/collapsed", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            collapsed = data.get("collapsed", [])
            print(f"   Collapsed groups: {len(collapsed)}")
            for g in collapsed[:5]:
                print(f"     - {g}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 4: Expand all groups
    print("\n4. POST /api/tmux/groups/expand-all")
    try:
        resp = requests.post(
            f"{base_url}/api/tmux/groups/expand-all", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Success: {data.get('success')}")
            print(f"   Expanded: {data.get('expanded', 0)} groups")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 5: Collapse all groups
    print("\n5. POST /api/tmux/groups/collapse-all")
    try:
        resp = requests.post(
            f"{base_url}/api/tmux/groups/collapse-all", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Success: {data.get('success')}")
            print(f"   Collapsed: {data.get('collapsed', 0)} groups")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 50)
    print("Session grouping endpoint tests complete!")


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    session = sys.argv[2] if len(sys.argv) > 2 else None
    test_session_groups(base_url, session)
