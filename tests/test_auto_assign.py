#!/usr/bin/env python3
"""Test script for task auto-assignment endpoints."""

import json
import sys

import requests


def test_auto_assign(base_url="http://localhost:8080", session_cookie=None):
    """Test the task auto-assignment endpoints."""

    print("Testing Task Auto-Assignment Endpoints")
    print("=" * 50)

    headers = {}
    cookies = {}

    if session_cookie:
        cookies["session"] = session_cookie

    # Test 1: Get available strategies
    print("\n1. GET /api/auto-assign/strategies")
    try:
        resp = requests.get(
            f"{base_url}/api/auto-assign/strategies", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Default strategy: {data.get('default')}")
            print(f"   Available strategies:")
            for s in data.get("strategies", []):
                print(f"     - {s['id']}: {s['description']}")
        elif resp.status_code == 401:
            print("   (Authentication required - need session cookie)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 2: Get configuration
    print("\n2. GET /api/auto-assign/config")
    try:
        resp = requests.get(
            f"{base_url}/api/auto-assign/config", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Max concurrent tasks: {data.get('max_concurrent_tasks')}")
            print(f"   Heartbeat timeout: {data.get('heartbeat_timeout_seconds')}s")
            print(f"   Skill match threshold: {data.get('skill_match_threshold')}")
            print(f"   Workload weights: {data.get('workload_weights')}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 3: Get workload summary
    print("\n3. GET /api/auto-assign/workload")
    try:
        resp = requests.get(
            f"{base_url}/api/auto-assign/workload", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Total workers: {data.get('total_workers')}")
            print(f"   Total capacity: {data.get('total_capacity')}")
            print(f"   Current load: {data.get('total_load')}")
            print(f"   Utilization: {data.get('utilization_percent')}%")
            print(f"   Unassigned tasks: {data.get('unassigned_tasks')}")
            workers = data.get("workers", [])[:3]
            if workers:
                print(f"   Top workers by availability:")
                for w in workers:
                    print(
                        f"     - {w['id']}: {w['task_count']} tasks, {w['utilization_percent']}% utilized"
                    )
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 4: Get available workers
    print("\n4. GET /api/auto-assign/workers")
    try:
        resp = requests.get(
            f"{base_url}/api/auto-assign/workers", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Available workers: {data.get('count')}")
            for w in data.get("workers", [])[:5]:
                print(f"     - {w['id']}: score={w['workload_score']}, tasks={w['task_count']}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 5: Preview assignments
    print("\n5. GET /api/auto-assign/preview")
    try:
        resp = requests.get(
            f"{base_url}/api/auto-assign/preview",
            headers=headers,
            cookies=cookies,
            params={"limit": 10},
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Unassigned tasks: {data.get('unassigned_tasks')}")
            print(f"   Available workers: {data.get('available_workers')}")
            print(f"   Would assign: {data.get('would_assign')}")
            suggestions = data.get("suggested_assignments", [])[:3]
            if suggestions:
                print(f"   Sample assignments:")
                for s in suggestions:
                    print(f"     - Task {s['task_id']} -> {s['suggested_worker']}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 6: Get recommendation for a task
    print("\n6. GET /api/auto-assign/recommend/1 (if task exists)")
    try:
        resp = requests.get(
            f"{base_url}/api/auto-assign/recommend/1", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            rec = data.get("recommendation")
            if rec:
                print(f"   Task type: {data.get('task_type')}")
                print(f"   Recommended worker: {rec.get('worker_id')}")
                print(f"   Worker score: {rec.get('combined_score')}")
                print(f"   Current tasks: {rec.get('current_tasks')}")
            else:
                print(f"   No recommendation: {data.get('reason')}")
        elif resp.status_code == 404:
            print("   (Task not found)")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 7: Assign all pending (dry run concept via preview)
    print("\n7. POST /api/auto-assign/all (with limit=5)")
    try:
        resp = requests.post(
            f"{base_url}/api/auto-assign/all",
            headers=headers,
            cookies=cookies,
            json={"limit": 5, "strategy": "balanced"},
            timeout=30,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Total tasks processed: {data.get('total_tasks')}")
            print(f"   Assigned: {data.get('assigned')}")
            print(f"   Failed: {data.get('failed')}")
            assignments = data.get("assignments", [])[:3]
            if assignments:
                print(f"   Sample assignments:")
                for a in assignments:
                    print(f"     - Task {a['task_id']} -> {a['worker_id']}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 8: Rebalance (dry run)
    print("\n8. POST /api/auto-assign/rebalance (dry_run=true)")
    try:
        resp = requests.post(
            f"{base_url}/api/auto-assign/rebalance",
            headers=headers,
            cookies=cookies,
            json={"dry_run": True, "max_moves": 5},
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Dry run: {data.get('dry_run')}")
            print(f"   Moves planned: {data.get('moves_planned')}")
            before = data.get("before", {})
            print(f"   Before - avg load: {before.get('avg_load')}")
            print(f"   Overloaded workers: {before.get('overloaded_workers')}")
            print(f"   Underloaded workers: {before.get('underloaded_workers')}")
            moves = data.get("moves", [])[:3]
            if moves:
                print(f"   Sample moves:")
                for m in moves:
                    print(f"     - Task {m['task_id']}: {m['from_worker']} -> {m['to_worker']}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 50)
    print("Task auto-assignment endpoint tests complete!")


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    session = sys.argv[2] if len(sys.argv) > 2 else None
    test_auto_assign(base_url, session)
