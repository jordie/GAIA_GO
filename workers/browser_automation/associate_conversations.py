#!/usr/bin/env python3
"""
Associate Perplexity conversations from library with tab groups
"""

import asyncio
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
import json
import websockets
from datetime import datetime

# Known Perplexity conversations from library
KNOWN_CONVERSATIONS = [
    {
        "title": "how far is april 23rd from today?",
        "url": "https://www.perplexity.ai/search/how-far-is-april-23rd-from-tod-5rr4MPJGQWyc0wdxYpohBg",
        "suggested_group": "this is..." # Could be related to Ezana assignment deadline
    },
    {
        "title": "give me a list of tab groups",
        "url": "https://www.perplexity.ai/search/give-me-a-list-of-tab-groups-6HKAK9qzTBy55q6mpAjuWg",
        "suggested_group": "get all..." # Meta - about tab management
    },
    {
        "title": "ollama to automate web browsing",
        "url": "https://www.perplexity.ai/search/ollama-to-automate-web-browsin-ZNAYY4OaRFS8VkeERPniOA",
        "suggested_group": None # General automation research
    }
]

async def main():
    sheet_id = "1b1H2aZdSpj_0I0UzMVDbdcBMTqXQ5mAgtJ88zlxLm-Q"

    # Connect to Google Sheets
    creds_path = Path.home() / ".config" / "gspread" / "service_account.json"
    creds = Credentials.from_service_account_file(
        str(creds_path),
        scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
    )

    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(sheet_id)

    # Get Tab Groups worksheet
    ws_groups = spreadsheet.worksheet("Tab Groups")
    groups_data = ws_groups.get_all_records()

    print("=" * 70)
    print("TAB GROUPS AND SUGGESTED PERPLEXITY CONVERSATIONS")
    print("=" * 70)
    print()

    # Print current tab groups
    for i, group in enumerate(groups_data, 1):
        group_name = group.get('Group Name', '')
        perp_url = group.get('Main Perplexity URL', '')

        print(f"{i}. {group_name}")
        print(f"   Current Perplexity URL: {perp_url if perp_url else 'None'}")

        # Find suggested conversation
        suggested = [c for c in KNOWN_CONVERSATIONS if c['suggested_group'] == group_name]
        if suggested:
            print(f"   💡 Suggested: {suggested[0]['title']}")
            print(f"      {suggested[0]['url']}")
        else:
            print(f"   💡 No conversation suggested yet")
        print()

    print("=" * 70)
    print("ALL KNOWN PERPLEXITY CONVERSATIONS")
    print("=" * 70)
    print()

    for conv in KNOWN_CONVERSATIONS:
        print(f"• {conv['title']}")
        print(f"  {conv['url']}")
        print(f"  Suggested for: {conv['suggested_group'] or 'None (general)'}")
        print()

    print()
    print("To update a tab group with a Perplexity conversation:")
    print("  1. Edit KNOWN_CONVERSATIONS in this script to add more conversations")
    print("  2. Set 'suggested_group' to match the 'Group Name' from the sheet")
    print("  3. Run update_sheet_with_conversations() to apply changes")
    print()


if __name__ == "__main__":
    asyncio.run(main())
