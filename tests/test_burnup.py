#!/usr/bin/env python3
"""Test script for burnup chart endpoints."""

import json
import sys

import requests


def test_burnup(base_url="http://localhost:8080", session_cookie=None):
    """Test the burnup chart endpoints."""

    print("Testing Burnup Chart Endpoints")
    print("=" * 50)

    headers = {}
    cookies = {}

    if session_cookie:
        cookies["session"] = session_cookie

    # Test 1: Get burnup data (all milestones)
    print("\n1. GET /api/milestones/burnup")
    try:
        resp = requests.get(
            f"{base_url}/api/milestones/burnup",
            headers=headers,
            cookies=cookies,
            params={"granularity": "day", "metric": "count"},
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            config = data.get("config", {})
            summary = data.get("summary", {})
            points = data.get("data_points", [])

            print(f"   Date range: {config.get('start_date')} to {config.get('end_date')}")
            print(f"   Granularity: {config.get('granularity')}")
            print(f"   Metric: {config.get('metric')}")
            print(f"   Data points: {len(points)}")
            print(f"   Total items: {summary.get('total_items')}")
            print(f"   Completed: {summary.get('total_completed')}")
            print(f"   Completion: {summary.get('completion_percent')}%")
            print(f"   Avg velocity: {summary.get('avg_velocity')} {summary.get('velocity_unit')}")

            if points:
                print(f"\n   Sample data points:")
                for p in points[:3]:
                    print(
                        f"     - {p['date']}: scope={p['scope']}, completed={p['completed']}, progress={p['progress_percent']}%"
                    )
                if len(points) > 3:
                    print(f"     ... ({len(points) - 3} more)")

            prediction = data.get("prediction")
            if prediction:
                print(f"\n   Prediction:")
                print(f"     Estimated completion: {prediction.get('estimated_completion')}")
                print(f"     Remaining: {prediction.get('remaining_items')}")
        elif resp.status_code == 401:
            print("   (Authentication required - need session cookie)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 2: Get burnup with story points metric
    print("\n2. GET /api/milestones/burnup (story_points metric)")
    try:
        resp = requests.get(
            f"{base_url}/api/milestones/burnup",
            headers=headers,
            cookies=cookies,
            params={"granularity": "week", "metric": "story_points"},
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            points = data.get("data_points", [])
            print(f"   Weekly data points: {len(points)}")
            if points:
                latest = points[-1]
                print(
                    f"   Latest: scope={latest['scope']} pts, completed={latest['completed']} pts"
                )
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 3: Get burnup for specific milestone
    print("\n3. GET /api/milestones/burnup/1 (milestone-specific, if exists)")
    try:
        resp = requests.get(
            f"{base_url}/api/milestones/burnup/1", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            summary = data.get("summary", {})
            print(
                f"   Features: {summary.get('total_features')} ({summary.get('completed_features')} completed)"
            )
            print(
                f"   Bugs: {summary.get('total_bugs')} ({summary.get('completed_bugs')} completed)"
            )
        elif resp.status_code == 404:
            print("   (Milestone not found)")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 4: Get burndown data
    print("\n4. GET /api/milestones/burndown")
    try:
        resp = requests.get(
            f"{base_url}/api/milestones/burndown",
            headers=headers,
            cookies=cookies,
            params={"granularity": "day"},
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            points = data.get("data_points", [])
            initial = data.get("initial_scope", 0)
            print(f"   Initial scope: {initial}")
            print(f"   Data points: {len(points)}")
            if points:
                latest = points[-1]
                print(f"   Latest remaining: {latest.get('remaining')}")
                print(f"   Scope changes: {latest.get('scope_change')}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 5: Get burnup by project
    print("\n5. GET /api/milestones/burnup?project_id=1 (if project exists)")
    try:
        resp = requests.get(
            f"{base_url}/api/milestones/burnup",
            headers=headers,
            cookies=cookies,
            params={"project_id": 1, "granularity": "day"},
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            config = data.get("config", {})
            summary = data.get("summary", {})
            print(f"   Project filter: {config.get('project_id')}")
            print(f"   Items in project: {summary.get('total_items')}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 6: Get monthly burnup
    print("\n6. GET /api/milestones/burnup (monthly granularity)")
    try:
        resp = requests.get(
            f"{base_url}/api/milestones/burnup",
            headers=headers,
            cookies=cookies,
            params={"granularity": "month", "metric": "hours"},
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            points = data.get("data_points", [])
            ideal = data.get("ideal_line", [])
            print(f"   Monthly data points: {len(points)}")
            print(f"   Ideal line points: {len(ideal)}")
            if points:
                print(f"   Using hours metric")
                for p in points[:3]:
                    print(f"     - {p['date']}: {p['scope']}h scope, {p['completed']}h done")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 50)
    print("Burnup chart endpoint tests complete!")
    print("\nAvailable endpoints:")
    print("  GET /api/milestones/burnup - Get burnup chart data")
    print("  GET /api/milestones/burnup/<id> - Get burnup for specific milestone")
    print("  GET /api/milestones/burndown - Get burndown chart data")
    print("\nQuery parameters:")
    print("  milestone_id - Filter by milestone")
    print("  project_id - Filter by project")
    print("  start_date - Chart start date (YYYY-MM-DD)")
    print("  end_date - Chart end date (YYYY-MM-DD)")
    print("  granularity - day, week, or month")
    print("  metric - count, story_points, or hours")


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    session = sys.argv[2] if len(sys.argv) > 2 else None
    test_burnup(base_url, session)
