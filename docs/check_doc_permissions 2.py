#!/usr/bin/env python3
"""
Check Google Doc Permissions
Verify if the service account can access the document
"""
import json
import sys
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / ".config" / "google" / "credentials.json"
DOCUMENT_ID = "1I-cYYH6H3e36vpNSyrlkYobSna3CAkoxAoTTg4X4o7w"
SCOPES = ["https://www.googleapis.com/auth/documents"]


def check_permissions():
    print("🔍 Checking Google Doc Permissions")
    print("=" * 70)
    print()

    # Load credentials
    try:
        with open(CREDENTIALS_PATH, "r") as f:
            creds_data = json.load(f)
            email = creds_data.get("client_email")
    except Exception as e:
        print(f"❌ Failed to load credentials: {e}")
        return False

    print(f"📧 Service Account: {email}")
    print(f"📄 Document ID: {DOCUMENT_ID}")
    print()

    # Authenticate
    try:
        credentials = service_account.Credentials.from_service_account_file(
            str(CREDENTIALS_PATH), scopes=SCOPES
        )
        service = build("docs", "v1", credentials=credentials)
        print("✅ Authentication successful")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return False

    print()
    print("🔍 Testing document access...")
    print()

    # Try to access document
    try:
        doc = service.documents().get(documentId=DOCUMENT_ID).execute()

        print("✅ SUCCESS! Document is accessible!")
        print()
        print(f"📝 Document Title: {doc.get('title', 'Unknown')}")
        print(f"📊 Content Blocks: {len(doc.get('body', {}).get('content', []))}")
        print()
        print("🎉 The service account has permission to read the document!")
        print()
        print("✅ You can now run:")
        print("   python3 docs/google_docs_sync.py")
        print()
        return True

    except HttpError as e:
        if e.resp.status == 403:
            print("❌ PERMISSION DENIED (403 Error)")
            print()
            print("The document is NOT shared with the service account.")
            print()
            print("=" * 70)
            print("HOW TO FIX:")
            print("=" * 70)
            print()
            print("1. Open this URL in your browser:")
            print(f"   https://docs.google.com/document/d/{DOCUMENT_ID}/edit")
            print()
            print("2. Click the 'Share' button (top right, blue button)")
            print()
            print("3. In the 'Add people and groups' box, paste this email:")
            print(f"   {email}")
            print()
            print("4. Make sure the permission dropdown says 'Editor' (not Viewer)")
            print()
            print("5. Click 'Done'")
            print()
            print("6. Run this script again to verify:")
            print("   python3 docs/check_doc_permissions.py")
            print()
            print("=" * 70)
            print()
            return False
        else:
            print(f"❌ Unexpected error: {e}")
            return False


if __name__ == "__main__":
    success = check_permissions()
    sys.exit(0 if success else 1)
