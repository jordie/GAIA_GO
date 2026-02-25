#!/usr/bin/env python3
"""
Collect Perplexity conversation URLs from open tabs and update Google Sheet
Enhanced with error handling and security improvements
"""

import subprocess
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
from datetime import datetime
import json
import logging
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_current_tab_url():
    """Get URL of current tab in Comet with error handling."""
    applescript = '''
tell application "Comet"
    get URL of active tab of window 1
end tell
'''
    
    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            logger.error(f"AppleScript error: {result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        logger.error("Timeout getting tab URL - AppleScript took too long")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting tab URL: {e}")
        return None


def next_tab():
    """Move to next tab with error handling."""
    try:
        subprocess.run(
            ['osascript', '-e', '''
tell application "System Events"
    keystroke "]" using {command down, shift down}
end tell
'''],
            capture_output=True,
            timeout=5
        )
        return True
    except subprocess.TimeoutExpired:
        logger.error("Timeout moving to next tab")
        return False
    except Exception as e:
        logger.error(f"Error moving to next tab: {e}")
        return False


def update_sheet_with_url(topic_id, url):
    """Update Google Sheet with Perplexity URL - with error handling."""
    
    sheet_id = "1b1H2aZdSpj_0I0UzMVDbdcBMTqXQ5mAgtJ88zlxLm-Q"
    creds_path = Path.home() / ".config" / "gspread" / "service_account.json"
    
    # Validate credentials file exists
    if not creds_path.exists():
        logger.error(f"Credentials file not found: {creds_path}")
        logger.error("Please ensure Google Sheets API credentials are configured")
        return False
    
    try:
        creds = Credentials.from_service_account_file(
            str(creds_path),
            scopes=[
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
        )
    except Exception as e:
        logger.error(f"Failed to load credentials: {e}")
        return False
    
    try:
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(sheet_id)
        ws = spreadsheet.worksheet("Tab Groups")
    except gspread.exceptions.APIError as e:
        logger.error(f"Google Sheets API error: {e}")
        return False
    except Exception as e:
        logger.error(f"Error accessing spreadsheet: {e}")
        return False
    
    try:
        all_data = ws.get_all_values()
        
        for row_num, row in enumerate(all_data[1:], 2):
            if row[0] == topic_id:
                # Update Perplexity URL (column 9)
                ws.update_cell(row_num, 9, url)
                
                # Update status
                ws.update_cell(row_num, 5, "completed")
                
                # Update timestamp
                ws.update_cell(row_num, 14, datetime.now().strftime('%Y-%m-%d %H:%M'))
                
                logger.info(f"Successfully updated sheet for topic: {topic_id}")
                return True
        
        logger.warning(f"Topic ID not found in sheet: {topic_id}")
        return False
        
    except gspread.exceptions.APIError as e:
        logger.error(f"API error updating sheet: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error updating sheet: {e}")
        return False


def main():
    prompts_file = Path("data/ethiopia/ethiopia_prompts.json")
    
    # Validate prompts file exists
    if not prompts_file.exists():
        logger.error(f"Prompts file not found: {prompts_file}")
        logger.error("Please run setup_ethiopia_project.py first")
        sys.exit(1)
    
    try:
        with open(prompts_file) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in prompts file: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error reading prompts file: {e}")
        sys.exit(1)
    
    topics = data.get('tab_groups', [])
    
    if not topics:
        logger.error("No topics found in prompts file")
        sys.exit(1)
    
    print("="*80)
    print("COLLECTING PERPLEXITY CONVERSATION URLs")
    print("="*80)
    print()
    print(f"Topics: {len(topics)}")
    print()
    print("Position browser on first Perplexity tab with responses")
    print()
    
    input("Press Enter to start collecting URLs...")
    
    collected = []
    failed = []
    
    for i, topic in enumerate(topics, 1):
        name = topic.get('name', f'Topic {i}')
        topic_id = topic.get('id', '')
        
        print(f"\n[{i}/{len(topics)}] {name}")
        
        # Get current tab URL
        url = get_current_tab_url()
        
        if url and 'perplexity.ai/search/' in url:
            print(f"  ✅ URL: {url}")
            
            # Update Google Sheet
            success = update_sheet_with_url(topic_id, url)
            
            if success:
                print(f"  ✓ Updated Google Sheet")
                collected.append({'name': name, 'url': url})
            else:
                print(f"  ⚠️  Failed to update sheet")
                failed.append(name)
        
        else:
            print(f"  ⚠️  Not a Perplexity conversation URL: {url}")
            failed.append(name)
        
        # Move to next tab
        if i < len(topics):
            if next_tab():
                import time
                time.sleep(1)
            else:
                logger.warning("Failed to move to next tab, continuing anyway")
    
    print("\n" + "="*80)
    print(f"✅ COLLECTED {len(collected)}/{len(topics)} URLs")
    if failed:
        print(f"⚠️  FAILED: {len(failed)} topics")
    print("="*80)
    print()
    
    if collected:
        print("Updated in Google Sheet:")
        for item in collected:
            print(f"  • {item['name']}")
        print()
    
    if failed:
        print("Failed to collect:")
        for name in failed:
            print(f"  ✗ {name}")
        print()
    
    print("View results:")
    print("  Google Sheet: https://docs.google.com/spreadsheets/d/1b1H2aZdSpj_0I0UzMVDbdcBMTqXQ5mAgtJ88zlxLm-Q/edit")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
