#!/usr/bin/env python3
"""
Google Docs API Client
Provides functionality to read and edit Google Docs using service account authentication.

Usage:
    from utils.google_docs_client import GoogleDocsClient

    client = GoogleDocsClient()

    # Append content to document
    client.append_to_doc(doc_id, "# New Section\n\nContent here...")

    # Insert at specific location
    client.insert_at_index(doc_id, index=1, text="Insert at beginning")

    # Replace all content
    client.replace_content(doc_id, "# New Document\n\nCompletely new content")

    # Read document content
    content = client.read_doc(doc_id)
"""

from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GoogleDocsClient:
    """Client for Google Docs API operations."""

    # Service account credentials path (shared with gspread)
    CREDENTIALS_PATH = Path.home() / ".config" / "gspread" / "service_account.json"

    # API scopes
    SCOPES = ["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive"]

    def __init__(self, credentials_path=None):
        """
        Initialize Google Docs client.

        Args:
            credentials_path: Optional path to service account JSON.
                            Defaults to ~/.config/gspread/service_account.json
        """
        self.credentials_path = credentials_path or self.CREDENTIALS_PATH
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Google Docs API."""
        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"Credentials not found at {self.credentials_path}\n"
                f"Please place your service account JSON file there."
            )

        creds = Credentials.from_service_account_file(
            str(self.credentials_path), scopes=self.SCOPES
        )

        self.service = build("docs", "v1", credentials=creds)

    def read_doc(self, document_id):
        """
        Read the entire document content as plain text.

        Args:
            document_id: Google Doc ID (from URL)

        Returns:
            str: Document content as plain text
        """
        try:
            doc = self.service.documents().get(documentId=document_id).execute()
            content = self._extract_text(doc)
            return content
        except HttpError as e:
            raise Exception(f"Failed to read document: {e}")

    def _extract_text(self, document):
        """Extract plain text from document structure."""
        content = []

        for element in document.get("body", {}).get("content", []):
            if "paragraph" in element:
                paragraph = element["paragraph"]
                for text_run in paragraph.get("elements", []):
                    if "textRun" in text_run:
                        content.append(text_run["textRun"]["content"])
            elif "table" in element:
                # Extract table content
                table = element["table"]
                for row in table.get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        for cell_element in cell.get("content", []):
                            if "paragraph" in cell_element:
                                for text_run in cell_element["paragraph"].get("elements", []):
                                    if "textRun" in text_run:
                                        content.append(text_run["textRun"]["content"])

        return "".join(content)

    def get_doc_info(self, document_id):
        """
        Get document metadata.

        Args:
            document_id: Google Doc ID

        Returns:
            dict: Document metadata (title, documentId, etc.)
        """
        try:
            doc = self.service.documents().get(documentId=document_id).execute()
            return {
                "title": doc.get("title"),
                "documentId": doc.get("documentId"),
                "revisionId": doc.get("revisionId"),
            }
        except HttpError as e:
            raise Exception(f"Failed to get document info: {e}")

    def append_to_doc(self, document_id, text):
        """
        Append text to the end of the document.

        Args:
            document_id: Google Doc ID
            text: Text to append

        Returns:
            dict: API response
        """
        try:
            # Get current document to find end index
            doc = self.service.documents().get(documentId=document_id).execute()
            end_index = doc["body"]["content"][-1]["endIndex"] - 1

            requests = [{"insertText": {"location": {"index": end_index}, "text": text}}]

            result = (
                self.service.documents()
                .batchUpdate(documentId=document_id, body={"requests": requests})
                .execute()
            )

            return result
        except HttpError as e:
            raise Exception(f"Failed to append to document: {e}")

    def insert_at_index(self, document_id, index, text):
        """
        Insert text at a specific index in the document.

        Args:
            document_id: Google Doc ID
            index: Character index where to insert (1 = beginning)
            text: Text to insert

        Returns:
            dict: API response
        """
        try:
            requests = [{"insertText": {"location": {"index": index}, "text": text}}]

            result = (
                self.service.documents()
                .batchUpdate(documentId=document_id, body={"requests": requests})
                .execute()
            )

            return result
        except HttpError as e:
            raise Exception(f"Failed to insert text: {e}")

    def replace_content(self, document_id, new_text):
        """
        Replace all document content with new text.

        Args:
            document_id: Google Doc ID
            new_text: New content for the document

        Returns:
            dict: API response
        """
        try:
            # Get current document
            doc = self.service.documents().get(documentId=document_id).execute()
            end_index = doc["body"]["content"][-1]["endIndex"] - 1

            requests = [
                # Delete all existing content
                {"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end_index}}},
                # Insert new content
                {"insertText": {"location": {"index": 1}, "text": new_text}},
            ]

            result = (
                self.service.documents()
                .batchUpdate(documentId=document_id, body={"requests": requests})
                .execute()
            )

            return result
        except HttpError as e:
            raise Exception(f"Failed to replace content: {e}")

    def create_tab(self, document_id, tab_title, content):
        """
        Create a new section/tab in the document.
        Note: Google Docs doesn't have tabs, but we can create sections with headers.

        Args:
            document_id: Google Doc ID
            tab_title: Title for the new section
            content: Content for the section

        Returns:
            dict: API response
        """
        # Format as a new section
        section_text = f"\n\n{'=' * 80}\n\n# {tab_title}\n\n{content}\n"

        return self.append_to_doc(document_id, section_text)

    def insert_page_break(self, document_id, index):
        """
        Insert a page break at specified index.

        Args:
            document_id: Google Doc ID
            index: Character index for page break

        Returns:
            dict: API response
        """
        try:
            requests = [{"insertPageBreak": {"location": {"index": index}}}]

            result = (
                self.service.documents()
                .batchUpdate(documentId=document_id, body={"requests": requests})
                .execute()
            )

            return result
        except HttpError as e:
            raise Exception(f"Failed to insert page break: {e}")

    def apply_formatting(
        self, document_id, start_index, end_index, bold=False, italic=False, font_size=None
    ):
        """
        Apply text formatting to a range.

        Args:
            document_id: Google Doc ID
            start_index: Start of range
            end_index: End of range
            bold: Make text bold
            italic: Make text italic
            font_size: Font size in points

        Returns:
            dict: API response
        """
        try:
            text_style = {}
            if bold:
                text_style["bold"] = True
            if italic:
                text_style["italic"] = True
            if font_size:
                text_style["fontSize"] = {"magnitude": font_size, "unit": "PT"}

            requests = [
                {
                    "updateTextStyle": {
                        "range": {"startIndex": start_index, "endIndex": end_index},
                        "textStyle": text_style,
                        "fields": ",".join(text_style.keys()),
                    }
                }
            ]

            result = (
                self.service.documents()
                .batchUpdate(documentId=document_id, body={"requests": requests})
                .execute()
            )

            return result
        except HttpError as e:
            raise Exception(f"Failed to apply formatting: {e}")

    def add_formatted_content(self, document_id, markdown_content, title):
        """
        Add content with professional formatting from markdown.
        Converts markdown to Google Docs with proper heading styles.

        Args:
            document_id: Google Doc ID
            markdown_content: Markdown text to format
            title: Main section title

        Returns:
            dict: API response
        """
        try:
            # Get current end index
            doc = self.service.documents().get(documentId=document_id).execute()
            current_index = doc["body"]["content"][-1]["endIndex"] - 1

            # Build requests list
            requests = []

            # Add page break
            requests.append({"insertPageBreak": {"location": {"index": current_index}}})
            current_index += 1

            # Parse and format markdown
            lines = markdown_content.split("\n")
            insert_index = current_index

            # Track positions for formatting
            formatting_tasks = []

            for line in lines:
                line_start = insert_index

                # Process different markdown elements
                if line.startswith("# "):
                    # Heading 1
                    text = line[2:].strip() + "\n"
                    requests.append(
                        {"insertText": {"location": {"index": insert_index}, "text": text}}
                    )
                    formatting_tasks.append(
                        {"type": "heading1", "start": line_start, "end": line_start + len(text)}
                    )
                    insert_index += len(text)

                elif line.startswith("## "):
                    # Heading 2
                    text = line[3:].strip() + "\n"
                    requests.append(
                        {"insertText": {"location": {"index": insert_index}, "text": text}}
                    )
                    formatting_tasks.append(
                        {"type": "heading2", "start": line_start, "end": line_start + len(text)}
                    )
                    insert_index += len(text)

                elif line.startswith("### "):
                    # Heading 3
                    text = line[4:].strip() + "\n"
                    requests.append(
                        {"insertText": {"location": {"index": insert_index}, "text": text}}
                    )
                    formatting_tasks.append(
                        {"type": "heading3", "start": line_start, "end": line_start + len(text)}
                    )
                    insert_index += len(text)

                elif line.startswith("#### "):
                    # Heading 4
                    text = line[5:].strip() + "\n"
                    requests.append(
                        {"insertText": {"location": {"index": insert_index}, "text": text}}
                    )
                    formatting_tasks.append(
                        {"type": "heading4", "start": line_start, "end": line_start + len(text)}
                    )
                    insert_index += len(text)

                elif line.startswith("**") or "**" in line:
                    # Bold text - just insert for now, we'll format in second pass
                    text = line + "\n"
                    requests.append(
                        {"insertText": {"location": {"index": insert_index}, "text": text}}
                    )
                    insert_index += len(text)

                elif line.startswith("```"):
                    # Code block marker - skip
                    continue

                elif line.startswith("- ") or line.startswith("* "):
                    # Bullet point
                    text = line[2:] + "\n"
                    requests.append(
                        {"insertText": {"location": {"index": insert_index}, "text": text}}
                    )
                    formatting_tasks.append(
                        {"type": "bullet", "start": line_start, "end": line_start + len(text)}
                    )
                    insert_index += len(text)

                elif line.startswith("|"):
                    # Table row - just insert as text for now
                    text = line + "\n"
                    requests.append(
                        {"insertText": {"location": {"index": insert_index}, "text": text}}
                    )
                    insert_index += len(text)

                else:
                    # Normal text
                    text = line + "\n"
                    requests.append(
                        {"insertText": {"location": {"index": insert_index}, "text": text}}
                    )
                    insert_index += len(text)

            # Apply formatting after text insertion
            for task in formatting_tasks:
                if task["type"] == "heading1":
                    requests.append(
                        {
                            "updateParagraphStyle": {
                                "range": {"startIndex": task["start"], "endIndex": task["end"]},
                                "paragraphStyle": {"namedStyleType": "HEADING_1"},
                                "fields": "namedStyleType",
                            }
                        }
                    )
                elif task["type"] == "heading2":
                    requests.append(
                        {
                            "updateParagraphStyle": {
                                "range": {"startIndex": task["start"], "endIndex": task["end"]},
                                "paragraphStyle": {"namedStyleType": "HEADING_2"},
                                "fields": "namedStyleType",
                            }
                        }
                    )
                elif task["type"] == "heading3":
                    requests.append(
                        {
                            "updateParagraphStyle": {
                                "range": {"startIndex": task["start"], "endIndex": task["end"]},
                                "paragraphStyle": {"namedStyleType": "HEADING_3"},
                                "fields": "namedStyleType",
                            }
                        }
                    )
                elif task["type"] == "heading4":
                    requests.append(
                        {
                            "updateParagraphStyle": {
                                "range": {"startIndex": task["start"], "endIndex": task["end"]},
                                "paragraphStyle": {"namedStyleType": "HEADING_4"},
                                "fields": "namedStyleType",
                            }
                        }
                    )
                elif task["type"] == "bullet":
                    requests.append(
                        {
                            "createParagraphBullets": {
                                "range": {"startIndex": task["start"], "endIndex": task["end"]},
                                "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
                            }
                        }
                    )

            # Execute all requests in batches (max 500 per request)
            batch_size = 500
            for i in range(0, len(requests), batch_size):
                batch = requests[i : i + batch_size]
                result = (
                    self.service.documents()
                    .batchUpdate(documentId=document_id, body={"requests": batch})
                    .execute()
                )

            return result

        except HttpError as e:
            raise Exception(f"Failed to add formatted content: {e}")


def extract_doc_id_from_url(url):
    """
    Extract document ID from Google Docs URL.

    Args:
        url: Google Docs URL

    Returns:
        str: Document ID

    Example:
        >>> url = "https://docs.google.com/document/d/DOC_ID/edit"
        >>> extract_doc_id_from_url(url)
        'DOC_ID'
    """
    if "/d/" in url:
        doc_id = url.split("/d/")[1].split("/")[0]
        return doc_id
    return url  # Assume it's already a doc ID


# Example usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  Read document:   python google_docs_client.py <doc_id>")
        cmd = "  Append text:     python google_docs_client.py "
        cmd += "<doc_id> append 'Text'"
        print(cmd)
        print(
            "  Replace content: python google_docs_client.py <doc_url_or_id> replace 'New content'"
        )
        sys.exit(1)

    doc_input = sys.argv[1]
    doc_id = extract_doc_id_from_url(doc_input)

    client = GoogleDocsClient()

    if len(sys.argv) == 2:
        # Read document
        print(f"Reading document {doc_id}...")
        content = client.read_doc(doc_id)
        print("\n--- Document Content ---")
        print(content)
        print("\n--- End of Document ---")

    elif sys.argv[2] == "append" and len(sys.argv) > 3:
        text = " ".join(sys.argv[3:])
        print(f"Appending to document {doc_id}...")
        result = client.append_to_doc(doc_id, text)
        print(f"Success! Appended {len(text)} characters.")

    elif sys.argv[2] == "replace" and len(sys.argv) > 3:
        text = " ".join(sys.argv[3:])
        print(f"Replacing content in document {doc_id}...")
        result = client.replace_content(doc_id, text)
        print(f"Success! Replaced with {len(text)} characters.")

    else:
        print("Unknown command. Use 'append' or 'replace'.")
        sys.exit(1)
