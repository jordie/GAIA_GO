#!/usr/bin/env python3
"""
Continuously update Google Doc with research results as they complete
"""

import time
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from pathlib import Path
from datetime import datetime


class EthiopiaDocUpdater:
    def __init__(self):
        self.sheet_id = "1b1H2aZdSpj_0I0UzMVDbdcBMTqXQ5mAgtJ88zlxLm-Q"
        self.doc_id = "1Ayru70HNA4Z5eoXC4M1ETpCr09W-TAo33pll1PolQaU"

        creds_path = Path.home() / ".config" / "gspread" / "service_account.json"
        self.creds = Credentials.from_service_account_file(
            str(creds_path),
            scopes=[
                'https://www.googleapis.com/auth/documents',
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
        )

        self.updated_topics = set()

    def get_completed_topics(self):
        """Get topics with Perplexity URLs from Sheet."""

        gc = gspread.authorize(self.creds)
        spreadsheet = gc.open_by_key(self.sheet_id)
        ws = spreadsheet.worksheet("Tab Groups")

        all_data = ws.get_all_records()
        ethiopia_groups = [g for g in all_data if g.get('Project ID') == 'P002']

        completed = []
        for group in ethiopia_groups:
            name = group.get('Group Name')
            url = group.get('Main Perplexity URL', '')

            if url and url.strip() and name not in self.updated_topics:
                completed.append({
                    'name': name,
                    'url': url,
                    'status': group.get('Status', ''),
                    'notes': group.get('Notes', '')
                })

        return completed

    def update_doc_with_finding(self, topic):
        """Update Google Doc with research finding."""

        print(f"\n📝 Updating doc with: {topic['name']}")

        service = build('docs', 'v1', credentials=self.creds)

        # Read current document
        doc = service.documents().get(documentId=self.doc_id).execute()
        content = doc.get('body').get('content')

        # Find the topic section (search for the topic name)
        # and update the "Status" and "Findings" sections

        # For now, append to end of document
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

        update_text = f'''

─────────────────────────────────────────────────────────────
UPDATE: {topic['name']}
─────────────────────────────────────────────────────────────

Status: ✅ COMPLETED
Timestamp: {timestamp}
Perplexity URL: {topic['url']}

Research Notes:
{topic.get('notes', 'Research completed via automated system.')}

View full conversation: {topic['url']}

'''

        requests = [{
            'insertText': {
                'location': {'index': len(doc.get('body').get('content')[-1].get('paragraph', {}).get('elements', [{}])[0].get('textRun', {}).get('content', ''))},
                'text': update_text
            }
        }]

        try:
            service.documents().batchUpdate(
                documentId=self.doc_id,
                body={'requests': requests}
            ).execute()

            print(f"  ✓ Updated Google Doc")
            self.updated_topics.add(topic['name'])
            return True

        except Exception as e:
            print(f"  ✗ Error updating doc: {e}")
            return False

    def monitor_and_update(self, interval=60):
        """Monitor Sheet and update Doc continuously."""

        print("="*80)
        print("ETHIOPIA DOC UPDATER - RUNNING")
        print("="*80)
        print()
        print(f"Checking for new results every {interval} seconds")
        print("Updates Google Doc automatically as research completes")
        print("Press Ctrl+C to stop")
        print()

        try:
            while True:
                completed = self.get_completed_topics()

                if completed:
                    print(f"\n🔍 Found {len(completed)} new completed topic(s)")

                    for topic in completed:
                        self.update_doc_with_finding(topic)
                        time.sleep(2)  # Brief delay between updates

                else:
                    print(f"⏳ {datetime.now().strftime('%H:%M:%S')} - No new results yet")

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\nDoc updater stopped by user")
            print(f"Updated topics: {len(self.updated_topics)}")


if __name__ == "__main__":
    updater = EthiopiaDocUpdater()
    updater.monitor_and_update(interval=60)
