#!/usr/bin/env python3
"""Test script for deep health check endpoints."""

import json
import sys

import requests


def test_deep_health(base_url="http://localhost:8080", session_cookie=None):
    """Test the deep health check endpoint."""

    print("Testing Deep Health Check Endpoints")
    print("=" * 50)

    headers = {}
    cookies = {}

    if session_cookie:
        cookies["session"] = session_cookie

    # Test 1: Health components list
    print("\n1. GET /api/health/components")
    try:
        resp = requests.get(
            f"{base_url}/api/health/components", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Components: {len(data.get('components', []))}")
            for comp in data.get("components", []):
                print(f"     - {comp['name']}: {comp['description']}")
        elif resp.status_code == 401:
            print("   (Authentication required - need session cookie)")
        else:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 2: Deep health check
    print("\n2. GET /api/health/deep")
    try:
        resp = requests.get(
            f"{base_url}/api/health/deep", headers=headers, cookies=cookies, timeout=30
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Overall Status: {data.get('status')}")
            print(f"   Duration: {data.get('duration_ms')}ms")

            summary = data.get("summary", {})
            print(f"   Summary:")
            print(f"     - Total checks: {summary.get('total')}")
            print(f"     - Healthy: {summary.get('healthy')}")
            print(f"     - Degraded: {summary.get('degraded')}")
            print(f"     - Unhealthy: {summary.get('unhealthy')}")

            print("\n   Check Results:")
            for check_name, check_result in data.get("checks", {}).items():
                status = check_result.get("status", "unknown")
                duration = check_result.get("duration_ms", "?")
                status_icon = {"healthy": "+", "degraded": "~", "unhealthy": "-"}.get(status, "?")
                print(f"     [{status_icon}] {check_name}: {status} ({duration}ms)")
        elif resp.status_code == 401:
            print("   (Authentication required - need session cookie)")
        else:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 3: Single component check
    print("\n3. GET /api/health/component/database")
    try:
        resp = requests.get(
            f"{base_url}/api/health/component/database",
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Component: {data.get('component')}")
            print(f"   Status: {data.get('status')}")
            print(f"   Duration: {data.get('duration_ms')}ms")
            if "tables" in data:
                print(f"   Tables: {data.get('tables')}")
            if "size_mb" in data:
                print(f"   Size: {data.get('size_mb')}MB")
        elif resp.status_code == 401:
            print("   (Authentication required - need session cookie)")
        else:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 4: Invalid component
    print("\n4. GET /api/health/component/invalid")
    try:
        resp = requests.get(
            f"{base_url}/api/health/component/invalid", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 404:
            print("   Correctly returned 404 for unknown component")
        elif resp.status_code == 401:
            print("   (Authentication required)")
        else:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 50)
    print("Deep health check tests complete!")


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    session = sys.argv[2] if len(sys.argv) > 2 else None
    test_deep_health(base_url, session)
