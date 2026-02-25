#!/usr/bin/env python3
"""
Google Docs Auto-Sync
Automatically synchronizes markdown documentation to Google Docs

Usage:
    python3 docs/google_docs_sync.py              # Sync all docs
    python3 docs/google_docs_sync.py --file X.md  # Sync specific file
    python3 docs/google_docs_sync.py --preview    # Preview without writing
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Google Docs API setup
SCOPES = ["https://www.googleapis.com/auth/documents"]
# Use credentials from project root
PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / ".config" / "google" / "credentials.json"
DOCUMENT_ID = "1I-cYYH6H3e36vpNSyrlkYobSna3CAkoxAoTTg4X4o7w"


class GoogleDocsSync:
    """Sync markdown files to Google Docs"""

    def __init__(self, credentials_path: str = CREDENTIALS_PATH):
        self.credentials_path = credentials_path
        self.service = None
        self.docs_dir = Path(__file__).parent

    def authenticate(self) -> bool:
        """Authenticate with service account"""
        try:
            print("🔐 Authenticating with Google Docs API...")

            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=SCOPES
            )

            self.service = build("docs", "v1", credentials=credentials)

            with open(self.credentials_path, "r") as f:
                creds_data = json.load(f)
                email = creds_data.get("client_email", "unknown")

            print(f"✅ Authenticated as: {email}")
            return True

        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            return False

    def get_markdown_files(self) -> List[Path]:
        """Get all markdown files in docs directory"""
        md_files = sorted(self.docs_dir.glob("*.md"))
        # Exclude the sync script's directory
        md_files = [f for f in md_files if f.name != "google_docs_sync.py"]
        return md_files

    def read_markdown(self, file_path: Path) -> str:
        """Read markdown file content"""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def markdown_to_doc_requests(self, markdown: str, start_index: int = 1) -> List[Dict]:
        """
        Convert markdown to Google Docs API requests
        Returns list of insertText requests
        """
        requests = []
        current_index = start_index

        lines = markdown.split("\n")

        for line in lines:
            # Handle headers
            if line.startswith("# "):
                text = line[2:] + "\n"
                requests.append(
                    {"insertText": {"location": {"index": current_index}, "text": text}}
                )
                # Style as heading 1
                requests.append(
                    {
                        "updateParagraphStyle": {
                            "range": {
                                "startIndex": current_index,
                                "endIndex": current_index + len(text),
                            },
                            "paragraphStyle": {"namedStyleType": "HEADING_1"},
                            "fields": "namedStyleType",
                        }
                    }
                )
                current_index += len(text)

            elif line.startswith("## "):
                text = line[3:] + "\n"
                requests.append(
                    {"insertText": {"location": {"index": current_index}, "text": text}}
                )
                # Style as heading 2
                requests.append(
                    {
                        "updateParagraphStyle": {
                            "range": {
                                "startIndex": current_index,
                                "endIndex": current_index + len(text),
                            },
                            "paragraphStyle": {"namedStyleType": "HEADING_2"},
                            "fields": "namedStyleType",
                        }
                    }
                )
                current_index += len(text)

            elif line.startswith("### "):
                text = line[4:] + "\n"
                requests.append(
                    {"insertText": {"location": {"index": current_index}, "text": text}}
                )
                # Style as heading 3
                requests.append(
                    {
                        "updateParagraphStyle": {
                            "range": {
                                "startIndex": current_index,
                                "endIndex": current_index + len(text),
                            },
                            "paragraphStyle": {"namedStyleType": "HEADING_3"},
                            "fields": "namedStyleType",
                        }
                    }
                )
                current_index += len(text)

            elif line.startswith("```"):
                # Code block - just insert as plain text for now
                text = line + "\n"
                requests.append(
                    {"insertText": {"location": {"index": current_index}, "text": text}}
                )
                current_index += len(text)

            else:
                # Regular paragraph
                text = line + "\n"
                requests.append(
                    {"insertText": {"location": {"index": current_index}, "text": text}}
                )
                current_index += len(text)

        return requests

    def build_document_content(self, md_files: List[Path]) -> str:
        """Build complete document content from multiple markdown files"""
        content_parts = []

        # Add header
        content_parts.append("# Architect System Documentation\n\n")
        content_parts.append(f"**Auto-generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        content_parts.append("---\n\n")

        # Table of contents
        content_parts.append("## Table of Contents\n\n")
        for md_file in md_files:
            title = md_file.stem.replace("_", " ").title()
            content_parts.append(f"- {title}\n")
        content_parts.append("\n---\n\n")

        # Add each document
        for md_file in md_files:
            title = md_file.stem.replace("_", " ").title()
            content_parts.append(f"# {title}\n\n")

            content = self.read_markdown(md_file)
            content_parts.append(content)
            content_parts.append("\n\n---\n\n")

        return "".join(content_parts)

    def clear_document(self, document_id: str) -> bool:
        """Clear all content from document"""
        try:
            doc = self.service.documents().get(documentId=document_id).execute()
            end_index = doc.get("body", {}).get("content", [{}])[-1].get("endIndex", 1)

            if end_index > 1:
                requests = [
                    {"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end_index - 1}}}
                ]

                self.service.documents().batchUpdate(
                    documentId=document_id, body={"requests": requests}
                ).execute()

            return True

        except HttpError as e:
            print(f"❌ Failed to clear document: {e}")
            return False

    def write_to_doc(self, document_id: str, content: str) -> bool:
        """Write content to Google Doc"""
        try:
            print(f"📝 Writing content to document...")

            # Clear existing content
            if not self.clear_document(document_id):
                return False

            # Insert new content (simple version - just insert text)
            requests = [{"insertText": {"location": {"index": 1}, "text": content}}]

            self.service.documents().batchUpdate(
                documentId=document_id, body={"requests": requests}
            ).execute()

            print(f"✅ Successfully updated document!")
            print(f"📄 View at: https://docs.google.com/document/d/{document_id}/edit")
            return True

        except HttpError as e:
            if e.resp.status == 403:
                print(f"❌ Permission denied. Please share the document with the service account.")
                with open(self.credentials_path, "r") as f:
                    creds_data = json.load(f)
                    email = creds_data.get("client_email")
                    print(f"   Service account: {email}")
                    print(f"   Grant 'Editor' access to this email")
            else:
                print(f"❌ Failed to write to document: {e}")
            return False

    def sync(self, specific_file: str = None, preview: bool = False) -> bool:
        """Main sync method"""
        print("📚 Google Docs Auto-Sync")
        print("=" * 60)
        print()

        # Authenticate
        if not self.authenticate():
            return False

        print()

        # Get markdown files
        if specific_file:
            md_files = [self.docs_dir / specific_file]
            if not md_files[0].exists():
                print(f"❌ File not found: {specific_file}")
                return False
        else:
            md_files = self.get_markdown_files()

        print(f"📂 Found {len(md_files)} markdown file(s):")
        for f in md_files:
            print(f"   - {f.name}")
        print()

        # Build content
        print("🔨 Building document content...")
        content = self.build_document_content(md_files)
        print(f"   Content length: {len(content)} characters")
        print()

        if preview:
            print("=" * 60)
            print("PREVIEW (first 2000 characters):")
            print("=" * 60)
            print(content[:2000])
            print("=" * 60)
            return True

        # Write to document
        return self.write_to_doc(DOCUMENT_ID, content)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Sync markdown docs to Google Docs")
    parser.add_argument("--file", help="Sync specific markdown file")
    parser.add_argument("--preview", action="store_true", help="Preview without writing")
    parser.add_argument("--doc-id", default=DOCUMENT_ID, help="Google Doc ID")

    args = parser.parse_args()

    syncer = GoogleDocsSync()
    success = syncer.sync(specific_file=args.file, preview=args.preview)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
