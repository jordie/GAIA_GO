#!/usr/bin/env python3
"""
Google Sheets integration for project tracking
Syncs project data to Google Sheets for visibility and management
"""

import json
from pathlib import Path

# Note: Install google-auth and gspread
# pip install gspread google-auth google-auth-oauthlib google-auth-httplib2

try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False


class GoogleSheetsSync:
    def __init__(self, credentials_path=None):
        """
        Initialize Google Sheets sync.

        credentials_path: Path to service account JSON credentials
                         If None, looks for 'google_credentials.json' in current dir
        """
        if not HAS_GSPREAD:
            raise ImportError(
                "Google Sheets libraries not installed. Run:\n"
                "pip install gspread google-auth google-auth-oauthlib google-auth-httplib2"
            )

        if credentials_path is None:
            credentials_path = "google_credentials.json"

        self.credentials_path = credentials_path
        self.client = None
        self.connect()

    def connect(self):
        """Connect to Google Sheets API."""
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]

        creds = Credentials.from_service_account_file(
            self.credentials_path,
            scopes=scopes
        )

        self.client = gspread.authorize(creds)

    def create_project_sheet(self, project_name, columns=None):
        """
        Create a new Google Sheet for a project.

        Returns: spreadsheet ID
        """
        if columns is None:
            columns = ["Task", "Status", "Progress", "Notes", "Links", "Updated"]

        # Create spreadsheet
        spreadsheet = self.client.create(f"Project: {project_name}")

        # Get first sheet
        sheet = spreadsheet.sheet1
        sheet.update_title("Overview")

        # Set header row
        sheet.update('A1', [columns])

        # Format header
        sheet.format('A1:Z1', {
            "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.8},
            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
        })

        return spreadsheet.id

    def sync_tab_group_to_sheet(self, spreadsheet_id, tab_group):
        """
        Sync a tab group to Google Sheet.

        tab_group: dict with name, status, progress, notes, tabs
        """
        spreadsheet = self.client.open_by_key(spreadsheet_id)
        sheet = spreadsheet.sheet1

        # Find or create row for this tab group
        row_index = tab_group.get('sheet_row')

        if not row_index:
            # Append new row
            row_index = len(sheet.get_all_values()) + 1

        # Prepare row data
        tabs_links = ", ".join([tab['url'] for tab in tab_group.get('tabs', [])])

        row_data = [
            tab_group['name'],
            tab_group.get('status', 'pending'),
            f"{tab_group.get('progress', 0)}%",
            tab_group.get('notes', ''),
            tabs_links,
            tab_group.get('updated_at', '')
        ]

        # Update row
        sheet.update(f'A{row_index}', [row_data])

        return row_index

    def sync_project_to_sheet(self, project, spreadsheet_id=None):
        """
        Sync entire project to Google Sheet.

        project: dict with name, description, tab_groups
        spreadsheet_id: existing sheet ID, or None to create new
        """
        # Create sheet if needed
        if not spreadsheet_id:
            spreadsheet_id = self.create_project_sheet(project['name'])

        spreadsheet = self.client.open_by_key(spreadsheet_id)
        sheet = spreadsheet.sheet1

        # Clear existing data (except header)
        sheet.delete_rows(2, sheet.row_count)

        # Sync each tab group
        for i, tab_group in enumerate(project['tab_groups']):
            row_index = i + 2  # Start after header
            self.sync_tab_group_to_sheet(spreadsheet_id, tab_group)
            tab_group['sheet_row'] = row_index

        return spreadsheet_id

    def get_sheet_url(self, spreadsheet_id):
        """Get the URL for a spreadsheet."""
        return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"

    def share_sheet(self, spreadsheet_id, email, role='writer'):
        """
        Share sheet with an email address.

        role: 'reader', 'writer', or 'owner'
        """
        spreadsheet = self.client.open_by_key(spreadsheet_id)
        spreadsheet.share(email, perm_type='user', role=role)

    def add_progress_chart(self, spreadsheet_id):
        """Add a progress chart to the sheet."""
        # TODO: Use Google Sheets API to add chart
        pass


def create_credentials_template():
    """Create a template for Google service account credentials."""
    template = {
        "type": "service_account",
        "project_id": "your-project-id",
        "private_key_id": "your-key-id",
        "private_key": "-----BEGIN PRIVATE KEY-----\nYOUR-PRIVATE-KEY\n-----END PRIVATE KEY-----\n",
        "client_email": "your-service-account@your-project.iam.gserviceaccount.com",
        "client_id": "your-client-id",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "your-cert-url"
    }

    with open("google_credentials.json.template", "w") as f:
        json.dump(template, f, indent=2)

    print("Created google_credentials.json.template")
    print("\nTo use Google Sheets integration:")
    print("1. Go to https://console.cloud.google.com/")
    print("2. Create a project or select existing")
    print("3. Enable Google Sheets API")
    print("4. Create service account credentials")
    print("5. Download JSON and save as google_credentials.json")


if __name__ == "__main__":
    if not HAS_GSPREAD:
        print("Google Sheets libraries not installed.")
        print("Run: pip install gspread google-auth google-auth-oauthlib google-auth-httplib2")
        create_credentials_template()
    else:
        print("Google Sheets integration ready!")
        print("Make sure you have google_credentials.json file")
