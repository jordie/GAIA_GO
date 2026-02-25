#!/usr/bin/env python3
"""Test script for Gantt chart endpoints."""

import json
import sys

import requests


def test_gantt_endpoints(base_url="http://localhost:8080", session_cookie=None):
    """Test the Gantt chart endpoints."""

    print("Testing Gantt Chart Endpoints")
    print("=" * 50)

    headers = {}
    cookies = {}

    if session_cookie:
        cookies["session"] = session_cookie

    # Test 1: Get Gantt data
    print("\n1. GET /api/milestones/gantt")
    try:
        resp = requests.get(
            f"{base_url}/api/milestones/gantt", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Total tasks: {data.get('summary', {}).get('total_tasks', 0)}")
            print(f"   Milestones: {data.get('summary', {}).get('milestones', 0)}")
            print(f"   Features: {data.get('summary', {}).get('features', 0)}")
            print(f"   Bugs: {data.get('summary', {}).get('bugs', 0)}")
            print(
                f"   Chart range: {data.get('chart_range', {}).get('start')} to {data.get('chart_range', {}).get('end')}"
            )

            if data.get("tasks"):
                print("\n   Sample tasks:")
                for task in data["tasks"][:5]:
                    print(f"     - [{task['type']}] {task['name']}: {task['progress']}%")
        elif resp.status_code == 401:
            print("   (Authentication required - need session cookie)")
        else:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 2: Get Gantt data with filters
    print("\n2. GET /api/milestones/gantt?include_completed=false")
    try:
        resp = requests.get(
            f"{base_url}/api/milestones/gantt",
            params={"include_completed": "false"},
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            summary = data.get("summary", {})
            print(f"   Active tasks only: {summary.get('total_tasks', 0)}")
            print(f"   In progress: {summary.get('in_progress', 0)}")
            print(f"   Not started: {summary.get('not_started', 0)}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 3: Get timeline data
    print("\n3. GET /api/milestones/gantt/timeline")
    try:
        resp = requests.get(
            f"{base_url}/api/milestones/gantt/timeline",
            params={"months": 3},
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            timeline = data.get("timeline", {})
            print(f"   Timeline range: {timeline.get('start')} to {timeline.get('end')}")
            print(f"   Months: {len(timeline.get('months', []))}")
            print(f"   Items: {len(data.get('items', []))}")

            for month in timeline.get("months", []):
                print(f"     - {month['month']}: {len(month.get('weeks', []))} weeks")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 4: Export as CSV
    print("\n4. GET /api/milestones/gantt/export?format=csv")
    try:
        resp = requests.get(
            f"{base_url}/api/milestones/gantt/export",
            params={"format": "csv"},
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "")
            print(f"   Content-Type: {content_type}")
            if "text/csv" in content_type:
                lines = resp.text.strip().split("\n")
                print(f"   CSV rows: {len(lines)}")
                if lines:
                    print(f"   Header: {lines[0]}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 5: Export as iCal
    print("\n5. GET /api/milestones/gantt/export?format=ical")
    try:
        resp = requests.get(
            f"{base_url}/api/milestones/gantt/export",
            params={"format": "ical"},
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "")
            print(f"   Content-Type: {content_type}")
            if "text/calendar" in content_type:
                events = resp.text.count("BEGIN:VEVENT")
                print(f"   Calendar events: {events}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 50)
    print("Gantt chart endpoint tests complete!")


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    session = sys.argv[2] if len(sys.argv) > 2 else None
    test_gantt_endpoints(base_url, session)
