#!/usr/bin/env python3
"""Test script for task attachments endpoints."""

import json
import os
import sys
import tempfile

import requests


def test_attachments(base_url="http://localhost:8080", session_cookie=None):
    """Test the task attachments endpoints."""

    print("Testing Task Attachments Endpoints")
    print("=" * 50)

    headers = {}
    cookies = {}

    if session_cookie:
        cookies["session"] = session_cookie

    # Test 1: Get allowed types
    print("\n1. GET /api/attachments/allowed-types")
    try:
        resp = requests.get(
            f"{base_url}/api/attachments/allowed-types",
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Extensions: {len(data.get('extensions', []))} types allowed")
            print(f"   Max file size: {data.get('max_file_size_mb', 0)}MB")
            by_category = data.get("by_category", {})
            for cat, exts in list(by_category.items())[:3]:
                print(f"     - {cat}: {', '.join(exts[:5])}...")
        elif resp.status_code == 401:
            print("   (Authentication required - need session cookie)")
        else:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 2: Validate upload (pre-flight check)
    print("\n2. POST /api/attachments/upload/validate")
    try:
        resp = requests.post(
            f"{base_url}/api/attachments/upload/validate",
            headers=headers,
            cookies=cookies,
            json={"filename": "test.png", "size": 1024},
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Valid: {data.get('valid')}")
            print(f"   Category: {data.get('category', 'N/A')}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
        else:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 3: Validate invalid file type
    print("\n3. POST /api/attachments/upload/validate (invalid type)")
    try:
        resp = requests.post(
            f"{base_url}/api/attachments/upload/validate",
            headers=headers,
            cookies=cookies,
            json={"filename": "malware.exe", "size": 1024},
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Valid: {data.get('valid')}")
            print(f"   Error: {data.get('error', 'N/A')}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 4: Upload a test file
    print("\n4. POST /api/attachments/upload")
    try:
        # Create a small test file
        test_content = b"Test file content for attachments API"
        files = {"file": ("test_upload.txt", test_content, "text/plain")}
        data = {"task_id": 1, "task_type": "feature", "description": "Test upload"}

        resp = requests.post(
            f"{base_url}/api/attachments/upload",
            headers=headers,
            cookies=cookies,
            files=files,
            data=data,
            timeout=30,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 201:
            result = resp.json()
            attachment = result.get("attachment", {})
            print(f"   Success: {result.get('success')}")
            print(f"   Attachment ID: {attachment.get('id')}")
            print(f"   Filename: {attachment.get('original_filename')}")
            print(f"   Size: {attachment.get('file_size')} bytes")
            # Store attachment_id for later tests
            test_attachments["uploaded_id"] = attachment.get("id")
        elif resp.status_code == 401:
            print("   (Authentication required)")
        else:
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 5: Get attachment details
    print("\n5. GET /api/attachments/<id>")
    attachment_id = test_attachments.get("uploaded_id", 1)
    try:
        resp = requests.get(
            f"{base_url}/api/attachments/{attachment_id}",
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ID: {data.get('id')}")
            print(f"   Filename: {data.get('original_filename')}")
            print(f"   MIME type: {data.get('mime_type')}")
            print(f"   Uploaded by: {data.get('uploaded_by')}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
        elif resp.status_code == 404:
            print("   (Attachment not found)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 6: Get task attachments
    print("\n6. GET /api/attachments/task/feature/1")
    try:
        resp = requests.get(
            f"{base_url}/api/attachments/task/feature/1",
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Attachments: {data.get('count', 0)}")
            for att in data.get("attachments", [])[:3]:
                print(f"     - {att.get('original_filename')} ({att.get('file_size')} bytes)")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 7: Get my uploads
    print("\n7. GET /api/attachments/my-uploads")
    try:
        resp = requests.get(
            f"{base_url}/api/attachments/my-uploads", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   My uploads: {data.get('count', 0)}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 8: Search attachments
    print("\n8. GET /api/attachments/search")
    try:
        resp = requests.get(
            f"{base_url}/api/attachments/search",
            headers=headers,
            cookies=cookies,
            params={"q": "test", "limit": 10},
            timeout=10,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Results: {data.get('count', 0)}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 9: Get stats
    print("\n9. GET /api/attachments/stats")
    try:
        resp = requests.get(
            f"{base_url}/api/attachments/stats", headers=headers, cookies=cookies, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Total count: {data.get('total_count', 0)}")
            print(f"   Total size: {data.get('total_size_mb', 0)}MB")
            print(f"   Unique uploaders: {data.get('unique_uploaders', 0)}")
        elif resp.status_code == 401:
            print("   (Authentication required)")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 10: Add comment to attachment
    print("\n10. POST /api/attachments/<id>/comments")
    if test_attachments.get("uploaded_id"):
        try:
            resp = requests.post(
                f"{base_url}/api/attachments/{test_attachments['uploaded_id']}/comments",
                headers=headers,
                cookies=cookies,
                json={"comment": "Test comment from API test"},
                timeout=10,
            )
            print(f"   Status: {resp.status_code}")
            if resp.status_code == 201:
                data = resp.json()
                print(f"   Comment ID: {data.get('id')}")
                print(f"   Comment: {data.get('comment')}")
            elif resp.status_code == 401:
                print("   (Authentication required)")
        except Exception as e:
            print(f"   Error: {e}")
    else:
        print("   (Skipped - no uploaded attachment)")

    # Test 11: Get comments
    print("\n11. GET /api/attachments/<id>/comments")
    if test_attachments.get("uploaded_id"):
        try:
            resp = requests.get(
                f"{base_url}/api/attachments/{test_attachments['uploaded_id']}/comments",
                headers=headers,
                cookies=cookies,
                timeout=10,
            )
            print(f"   Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"   Comments: {data.get('count', 0)}")
            elif resp.status_code == 401:
                print("   (Authentication required)")
        except Exception as e:
            print(f"   Error: {e}")
    else:
        print("   (Skipped - no uploaded attachment)")

    print("\n" + "=" * 50)
    print("Task attachments endpoint tests complete!")
    print("\nNote: Download/view/preview endpoints require a valid attachment ID")
    print("      and return file content rather than JSON.")


# Global storage for test data
test_attachments = {}


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    session = sys.argv[2] if len(sys.argv) > 2 else None
    test_attachments(base_url, session)
