#!/usr/bin/env python3
"""Test script for project archive endpoints."""

import json
import sys

import requests


def test_archive_endpoints(base_url="http://localhost:8080", session_cookie=None):
    """Test the project archive endpoints."""

    print("Testing Project Archive Endpoints")
    print("=" * 50)

    headers = {}
    cookies = {}

    if session_cookie:
        cookies["session"] = session_cookie

    # Test 1: Get archive statistics
    print("\n1. GET /api/projects/archive/stats")
    try:
        resp = requests.get(
            f"{base_url}/api/projects/archive/stats", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            summary = data.get("summary", {})
            print(f"   Total projects: {summary.get('total_projects', 0)}")
            print(f"   Active projects: {summary.get('active_projects', 0)}")
            print(f"   Archived projects: {summary.get('archived_projects', 0)}")
            print(f"   Archive percentage: {summary.get('archive_percentage', 0)}%")

            archived_data = data.get("archived_data", {})
            print(f"   Archived items: {archived_data.get('total_items', 0)} total")

            recommendations = data.get("recommendations", {})
            print(
                f"   Archive candidates (90+ days inactive): {recommendations.get('archive_candidates_90_days', 0)}"
            )
        elif resp.status_code == 401:
            print("   (Authentication required - need session cookie)")
        else:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 2: List archived projects
    print("\n2. GET /api/projects/archive")
    try:
        resp = requests.get(
            f"{base_url}/api/projects/archive", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            projects = data.get("projects", [])
            pagination = data.get("pagination", {})
            print(f"   Archived projects: {len(projects)}")
            print(f"   Total: {pagination.get('total', 0)}")
            print(f"   Page: {pagination.get('page', 1)} of {pagination.get('total_pages', 1)}")

            if projects:
                print("\n   Sample archived projects:")
                for p in projects[:3]:
                    print(f"     - {p['name']} (archived {p.get('days_archived', '?')} days ago)")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 3: Bulk archive dry run
    print("\n3. POST /api/projects/archive/bulk (dry run)")
    try:
        resp = requests.post(
            f"{base_url}/api/projects/archive/bulk",
            json={"inactive_days": 90, "dry_run": True},
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Dry run: {data.get('dry_run', False)}")
            print(f"   Projects that would be archived: {data.get('count', 0)}")
            print(
                f"   Criteria: inactive for {data.get('criteria', {}).get('inactive_days', 0)}+ days"
            )

            if data.get("projects_to_archive"):
                print("\n   Would archive:")
                for p in data["projects_to_archive"][:3]:
                    print(f"     - {p['name']} ({p.get('days_inactive', '?')} days inactive)")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 4: Cleanup dry run
    print("\n4. POST /api/projects/archive/cleanup (dry run)")
    try:
        resp = requests.post(
            f"{base_url}/api/projects/archive/cleanup",
            json={"older_than_days": 365, "dry_run": True},
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Dry run: {data.get('dry_run', False)}")
            print(f"   Old archives that would be deleted: {data.get('count', 0)}")
            print(
                f"   Criteria: archived for {data.get('criteria', {}).get('older_than_days', 0)}+ days"
            )
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 50)
    print("Project archive endpoint tests complete!")


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    session = sys.argv[2] if len(sys.argv) > 2 else None
    test_archive_endpoints(base_url, session)
