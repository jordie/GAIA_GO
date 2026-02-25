#!/usr/bin/env python3
"""
Analyze tab groups and suggest related Perplexity conversation topics
"""

import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path

def main():
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

    # Get tab groups and their tabs
    ws_groups = spreadsheet.worksheet("Tab Groups")
    ws_tabs = spreadsheet.worksheet("Tabs")

    groups_data = ws_groups.get_all_records()
    tabs_data = ws_tabs.get_all_records()

    print("=" * 80)
    print("TAB GROUPS ANALYSIS - SUGGESTED PERPLEXITY CONVERSATION TOPICS")
    print("=" * 80)
    print()

    # Known conversations from library
    known_conversations = [
        "how far is april 23rd from today?",
        "give me a list of tab groups",
        "ollama to automate web browsing"
    ]

    for group in groups_data:
        group_id = group.get('Group ID', '')
        group_name = group.get('Group Name', '')
        source = group.get('Source Computer', '')

        if not group_name or group_name == 'Group Name':  # Skip header
            continue

        print(f"📁 {group_name}")
        print(f"   Computer: {source}")
        print(f"   Group ID: {group_id}")
        print()

        # Get tabs for this group
        group_tabs = [t for t in tabs_data if t.get('Group ID') == group_id]

        if group_tabs:
            print("   Tabs in this group:")
            for tab in group_tabs:
                tab_title = tab.get('Tab Title', 'Untitled')[:60]
                tab_url = tab.get('URL', '')
                print(f"   • {tab_title}")
                if 'perplexity.ai' in tab_url.lower():
                    print(f"     ✓ Already has Perplexity: {tab_url}")
            print()

        # Suggest relevant conversation topics
        print("   💡 Suggested Perplexity conversation topics:")

        suggestions = get_suggestions_for_group(group_name, group_tabs)
        for suggestion in suggestions:
            print(f"      - {suggestion}")

        # Check if any known conversations match
        print()
        print("   🔍 Check your Perplexity Library for conversations about:")
        keywords = get_keywords_for_group(group_name)
        for keyword in keywords:
            print(f"      • {keyword}")

        print()
        print("-" * 80)
        print()

def get_suggestions_for_group(group_name, tabs):
    """Generate conversation topic suggestions based on group content."""
    suggestions = []

    if "School" in group_name or "Ezana" in group_name:
        suggestions = [
            "Assignment deadlines and planning",
            "Google Forms best practices",
            "School project organization"
        ]
    elif "Phone Plans" in group_name or "AT&T" in group_name:
        suggestions = [
            "AT&T plan comparison",
            "Best phone plans for families",
            "How to reduce phone bill costs"
        ]
    elif "Healthcare" in group_name or "Stanford" in group_name:
        suggestions = [
            "How to use MyHealth portal",
            "Stanford Health Care services",
            "Medical appointment scheduling tips"
        ]
    elif "DENTAL" in group_name or "Medi-Cal" in group_name:
        suggestions = [
            "Finding Medi-Cal dental providers",
            "Best dentists accepting Medi-Cal",
            "Dental coverage under Medi-Cal"
        ]
    elif "Real Estate" in group_name or "Alameda" in group_name:
        suggestions = [
            "Alameda real estate market analysis",
            "Understanding cap rates in real estate",
            "Multi-unit property investment tips"
        ]
    elif "Water Damage" in group_name or "Repairs" in group_name:
        suggestions = [
            "Water damage restoration process",
            "How to choose a water damage contractor",
            "Mold remediation best practices",
            "Insurance claims for water damage"
        ]
    elif "Task Tracking" in group_name:
        suggestions = [
            "Best task management systems",
            "Contractor communication tips",
            "Project tracking with Google Sheets"
        ]
    elif "Health Insurance" in group_name or "Covered CA" in group_name:
        suggestions = [
            "Covered California plan comparison",
            "Health insurance enrollment tips",
            "Best health plans in California"
        ]

    return suggestions

def get_keywords_for_group(group_name):
    """Generate search keywords for finding related conversations."""
    keywords = []

    if "School" in group_name:
        keywords = ["school", "assignment", "Ezana", "deadline", "forms"]
    elif "Phone Plans" in group_name:
        keywords = ["AT&T", "phone plan", "wireless", "family plan"]
    elif "Healthcare" in group_name and "Stanford" in group_name:
        keywords = ["Stanford", "health", "medical", "doctor", "appointment"]
    elif "DENTAL" in group_name:
        keywords = ["dental", "Medi-Cal", "dentist", "teeth"]
    elif "Real Estate" in group_name:
        keywords = ["Alameda", "property", "real estate", "cap rate", "investment"]
    elif "Water Damage" in group_name:
        keywords = ["water damage", "mold", "restoration", "contractor", "repair"]
    elif "Task Tracking" in group_name:
        keywords = ["task", "Javier", "tracking", "project management"]
    elif "Health Insurance" in group_name:
        keywords = ["Covered California", "health insurance", "plan", "coverage"]

    return keywords

if __name__ == "__main__":
    main()
