#!/usr/bin/env python3
"""
Setup Ethiopia trip outline and prompts in Google Doc
"""

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from pathlib import Path
import json
from datetime import datetime


def setup_google_doc():
    doc_id = "1Ayru70HNA4Z5eoXC4M1ETpCr09W-TAo33pll1PolQaU"

    # Connect to Google Docs API
    creds_path = Path.home() / ".config" / "gspread" / "service_account.json"
    creds = Credentials.from_service_account_file(
        str(creds_path),
        scopes=[
            'https://www.googleapis.com/auth/documents',
            'https://www.googleapis.com/auth/drive'
        ]
    )

    service = build('docs', 'v1', credentials=creds)

    print("="*80)
    print("SETTING UP ETHIOPIA TRIP GOOGLE DOC")
    print("="*80)
    print()

    # Load prompts
    prompts_file = Path("ethiopia_prompts.json")
    if not prompts_file.exists():
        print("Error: ethiopia_prompts.json not found")
        return

    with open(prompts_file) as f:
        data = json.load(f)

    initial_prompt = data['initial_prompt']
    family_members = data['family_members']
    topics = data['tab_groups']

    # Build document content
    requests = []

    # Title
    requests.append({
        'insertText': {
            'location': {'index': 1},
            'text': 'Ethiopia Family Trip - June 2026\nResearch & Planning Document\n\n'
        }
    })

    # Project Overview
    requests.append({
        'insertText': {
            'location': {'index': 1},
            'text': f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}\n'
                   f'Status: 🤖 Automated Research in Progress\n\n'
        }
    })

    # Initial Prompt Section
    requests.append({
        'insertText': {
            'location': {'index': 1},
            'text': 'PROJECT PROMPT\n\n'
        }
    })

    requests.append({
        'insertText': {
            'location': {'index': 1},
            'text': f'{initial_prompt}\n\n'
        }
    })

    # Family Details
    requests.append({
        'insertText': {
            'location': {'index': 1},
            'text': 'FAMILY MEMBERS\n\n'
        }
    })

    for member in family_members:
        requests.append({
            'insertText': {
                'location': {'index': 1},
                'text': f'• {member["name"]} ({member["age"]} years old)\n'
            }
        })

    requests.append({
        'insertText': {
            'location': {'index': 1},
            'text': '\n'
        }
    })

    # Trip Details
    requests.append({
        'insertText': {
            'location': {'index': 1},
            'text': 'TRIP DETAILS\n\n'
                   '• Departure: Bay Area (SFO/OAK)\n'
                   '• Destination: Addis Ababa, Ethiopia\n'
                   '• Travel Dates: Mid-late June 2026\n'
                   '• Return: Late July 2026\n'
                   '• Duration: 1 month\n'
                   '• Special: 1 week trip to Tigray region (Axum, Adigrat, Mekele)\n\n'
        }
    })

    # Research Topics Section
    requests.append({
        'insertText': {
            'location': {'index': 1},
            'text': 'RESEARCH TOPICS\n\n'
                   'The following topics are being researched via AI systems '
                   'with results aggregated here:\n\n'
        }
    })

    # Add each topic with its prompt
    for i, topic in enumerate(topics, 1):
        topic_name = topic['name']
        topic_prompt = topic['prompt']

        requests.append({
            'insertText': {
                'location': {'index': 1},
                'text': f'{i}. {topic_name}\n\n'
            }
        })

        requests.append({
            'insertText': {
                'location': {'index': 1},
                'text': 'Research Prompt:\n'
            }
        })

        requests.append({
            'insertText': {
                'location': {'index': 1},
                'text': f'{topic_prompt}\n\n'
            }
        })

        requests.append({
            'insertText': {
                'location': {'index': 1},
                'text': 'Status: ⏳ Research in progress...\n\n'
                       'Findings:\n'
                       '[Results will be added here automatically]\n\n'
                       '─────────────────────────────────────────────────────────────\n\n'
            }
        })

    # Automation Info
    requests.append({
        'insertText': {
            'location': {'index': 1},
            'text': 'AUTOMATION STATUS\n\n'
                   '🤖 Fully automated research in progress\n'
                   '• AI Systems: Claude, Codex, Gemini, Perplexity\n'
                   '• Rate Limiting: 3-5 minutes between requests\n'
                   '• Estimated Completion: 2-3 hours\n'
                   '• Progress Tracking: Google Sheet updated in real-time\n\n'
                   'This document will be automatically updated with research findings '
                   'as they are completed.\n\n'
        }
    })

    # Links Section
    requests.append({
        'insertText': {
            'location': {'index': 1},
            'text': 'LINKS\n\n'
                   '• Google Sheet (Live Progress): https://docs.google.com/spreadsheets/d/1b1H2aZdSpj_0I0UzMVDbdcBMTqXQ5mAgtJ88zlxLm-Q/edit\n'
                   '• This Document: https://docs.google.com/document/d/1Ayru70HNA4Z5eoXC4M1ETpCr09W-TAo33pll1PolQaU/edit\n\n'
        }
    })

    # Footer
    requests.append({
        'insertText': {
            'location': {'index': 1},
            'text': f'─────────────────────────────────────────────────────────────\n'
                   f'Last Updated: {datetime.now().strftime("%Y-%m-%d %H:%M")}\n'
                   f'Automation: RUNNING\n'
        }
    })

    # Execute all requests (in reverse order since we're inserting at index 1)
    requests.reverse()

    try:
        result = service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()

        print(f"✓ Google Doc updated successfully")
        print(f"  Document ID: {doc_id}")
        print(f"  Added: {len(requests)} content blocks")
        print(f"  Topics: {len(topics)}")
        print()
        print(f"View: https://docs.google.com/document/d/{doc_id}/edit")
        print()

    except Exception as e:
        print(f"Error updating Google Doc: {e}")
        print()
        print("Note: Make sure the service account has edit access to the document")
        print("Share the document with the service account email from:")
        print(f"  {creds_path}")


if __name__ == "__main__":
    setup_google_doc()
