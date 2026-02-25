#!/usr/bin/env python3
"""
Add Research to Google Doc
Easily append content from markdown files to Google Docs.

Usage:
    # Add clarification questions
    python3 scripts/add_to_google_doc.py \
        --doc "https://docs.google.com/document/d/..." \
        --file docs/CLARIFICATION_QUESTIONS.md \
        --title "Clarification"

    # Add research report
    python3 scripts/add_to_google_doc.py \
        --doc "1I-cYYH6H3e36vpNSyrlkYobSna3CAkoxAoTTg4X4o7w" \
        --file docs/MULTI_AGENT_ORCHESTRATION_RESEARCH_2026.md \
        --title "Multi-Agent Orchestration Research 2026"

    # Read current document
    python3 scripts/add_to_google_doc.py \
        --doc "1I-cYYH6H3e36vpNSyrlkYobSna3CAkoxAoTTg4X4o7w" \
        --read
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path (noqa: E402)
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.google_docs_client import GoogleDocsClient, extract_doc_id_from_url  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Add content to Google Docs")
    parser.add_argument("--doc", required=True, help="Google Doc URL or ID")
    parser.add_argument("--file", help="Markdown file to add")
    parser.add_argument("--title", help="Section title for new content")
    parser.add_argument("--read", action="store_true", help="Read current document")
    parser.add_argument(
        "--page-break", action="store_true", help="Insert page break before content"
    )
    parser.add_argument(
        "--formatted",
        action="store_true",
        help="Add with professional formatting (headings, bullets, etc.)",
    )

    args = parser.parse_args()

    # Extract doc ID
    doc_id = extract_doc_id_from_url(args.doc)

    # Initialize client
    try:
        client = GoogleDocsClient()
        print("✓ Connected to Google Docs API")
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        print("\nTo set up Google Docs API:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a service account")
        print("3. Enable Google Docs API")
        print("4. Download service account JSON")
        print("5. Save to ~/.config/gspread/service_account.json")
        return 1

    # Get document info
    try:
        doc_info = client.get_doc_info(doc_id)
        print(f"✓ Document: {doc_info['title']}")
    except Exception as e:
        print(f"✗ Error accessing document: {e}")
        print("\nMake sure:")
        print("1. The document exists")
        print("2. The service account has access to the document")
        print("   (Share the doc with the service account email)")
        return 1

    # Read mode
    if args.read:
        print("\n--- Current Document Content ---\n")
        content = client.read_doc(doc_id)
        print(content)
        print("\n--- End of Document ---")
        return 0

    # Add content mode
    if not args.file:
        print("Error: --file required (or use --read to read document)")
        return 1

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return 1

    # Read markdown file
    content = file_path.read_text()
    print(f"✓ Read {len(content)} characters from {file_path}")

    # Prepare section
    section_title = args.title or file_path.stem

    # Use formatted mode if requested
    if args.formatted:
        try:
            print("✓ Adding with professional formatting...")
            client.add_formatted_content(doc_id, content, section_title)
            print(f"✓ Added formatted section '{section_title}' to document")
            url = f"https://docs.google.com/document/d/{doc_id}/edit"
            print(f"✓ Document URL: {url}")
            print("\n📋 Tip: Use 'View > Show document outline' to see TOC")
            return 0
        except Exception as e:
            print(f"✗ Error adding formatted content: {e}")
            print("⚠ Falling back to plain text mode...")
            # Fall through to plain text mode

    # Plain text mode
    section_text = f"\n\n{'=' * 80}\n\n# {section_title}\n\n{content}\n"

    # Add page break if requested
    if args.page_break:
        try:
            # Get current end index
            doc = client.service.documents().get(documentId=doc_id).execute()
            end_index = doc["body"]["content"][-1]["endIndex"] - 1

            client.insert_page_break(doc_id, end_index)
            print("✓ Inserted page break")
        except Exception as e:
            print(f"⚠ Warning: Could not insert page break: {e}")

    # Append content
    try:
        client.append_to_doc(doc_id, section_text)
        print(f"✓ Added section '{section_title}' to document")
        url = f"https://docs.google.com/document/d/{doc_id}/edit"
        print(f"✓ Document URL: {url}")
        return 0
    except Exception as e:
        print(f"✗ Error adding content: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
