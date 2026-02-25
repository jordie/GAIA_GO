#!/usr/bin/env python3
"""
Create a Test Google Doc
Creates a new document that you automatically own and can share
"""
import json
import sys
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / ".config" / "google" / "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/documents"]


def create_test_doc():
    print("📝 Creating Test Google Doc")
    print("=" * 70)
    print()

    # Note about permissions
    print("⚠️  NOTE: Service accounts CANNOT create documents.")
    print("   Documents must be created by a user, then shared.")
    print()
    print("=" * 70)
    print()
    print("SOLUTION: Create document manually")
    print("=" * 70)
    print()
    print("1. Go to: https://docs.google.com/")
    print()
    print("2. Click: '+ Blank' (or 'Blank' button)")
    print()
    print("3. A new document opens. Copy the ID from the URL:")
    print("   https://docs.google.com/document/d/DOCUMENT_ID_HERE/edit")
    print("                                      ^^^^^^^^^^^^^^^^")
    print("   Copy everything between /d/ and /edit")
    print()
    print("4. Share the document:")
    print("   - Click 'Share' button")
    print("   - Add: sheets-sync@homademics.iam.gserviceaccount.com")
    print("   - Permission: Editor")
    print("   - Click 'Done'")
    print()
    print("5. Update the script to use your document ID:")
    print("   Edit: docs/google_docs_sync.py")
    print("   Change: DOCUMENT_ID = 'YOUR_NEW_DOCUMENT_ID'")
    print()
    print("=" * 70)
    print()


if __name__ == "__main__":
    create_test_doc()
