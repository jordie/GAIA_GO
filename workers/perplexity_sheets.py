#!/usr/bin/env python3
"""
Perplexity + Google Sheets Integration

Reads prompts from a Google Sheet, sends to Perplexity, and writes results back.
Can also run webpage tests and store results.

Usage:
    python3 perplexity_sheets.py                    # Process pending prompts
    python3 perplexity_sheets.py --daemon           # Run continuously
    python3 perplexity_sheets.py --test-sheet       # Test sheet connection
    python3 perplexity_sheets.py --create-sheet     # Create prompts sheet
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import Perplexity panel
from scripts.perplexity_panel import PerplexityPanel

# Configuration
SPREADSHEET_ID = "12i2uO6-41uZdHl_a9BbhBHhR1qbNlAqOgH-CWQBz7rA"
CREDENTIALS_PATH = Path.home() / ".config" / "gspread" / "service_account.json"
LOG_FILE = Path("/tmp/perplexity_sheets.log")
PID_FILE = Path("/tmp/perplexity_sheets.pid")
POLL_INTERVAL = 30  # Check for new prompts every 30 seconds


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except:
        pass


def get_sheets_client():
    """Get authenticated Google Sheets client."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        log("Missing packages. Run: pip3 install gspread google-auth")
        return None

    if not CREDENTIALS_PATH.exists():
        log(f"Credentials not found at {CREDENTIALS_PATH}")
        return None

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(str(CREDENTIALS_PATH), scopes=scopes)
    return gspread.authorize(creds)


def get_or_create_worksheet(spreadsheet, title, rows=200, cols=10):
    """Get existing worksheet or create new one."""
    try:
        return spreadsheet.worksheet(title)
    except:
        return spreadsheet.add_worksheet(title, rows=rows, cols=cols)


def create_prompts_sheet(spreadsheet):
    """Create or initialize the Prompts sheet for AI queries."""
    ws = get_or_create_worksheet(spreadsheet, "Prompts")

    try:
        first_cell = ws.acell("A1").value
        if first_cell == "ID":
            log("Prompts sheet already exists")
            return ws
    except:
        pass

    ws.clear()

    # Headers
    headers = [
        "ID",
        "Prompt",
        "Type",
        "Status",
        "Response",
        "Source",
        "Created",
        "Completed",
        "Notes",
    ]
    ws.update(values=[headers], range_name="A1")
    ws.format(
        "A1:I1",
        {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.2, "green": 0.7, "blue": 0.9}},
    )

    # Add template row
    template = ["NEW", "(Enter your prompt here)", "search", "pending", "", "", "", "", ""]
    ws.update(values=[template], range_name="A2")
    ws.format("A2:I2", {"backgroundColor": {"red": 1, "green": 1, "blue": 0.8}})

    # Add example prompts
    examples = [
        [
            "P1",
            "What is the capital of France?",
            "search",
            "pending",
            "",
            "",
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            "",
            "",
        ],
        [
            "P2",
            "Search for weather in San Francisco today",
            "search",
            "pending",
            "",
            "",
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            "",
            "",
        ],
        [
            "P3",
            "Find the hours for Selam Pharmacy Oakland",
            "search",
            "pending",
            "",
            "",
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            "",
            "",
        ],
    ]
    ws.update(values=examples, range_name="A3")

    log("Created Prompts sheet with examples")
    return ws


def create_web_tests_sheet(spreadsheet):
    """Create or initialize the WebTests sheet for webpage testing."""
    ws = get_or_create_worksheet(spreadsheet, "WebTests")

    try:
        first_cell = ws.acell("A1").value
        if first_cell == "ID":
            log("WebTests sheet already exists")
            return ws
    except:
        pass

    ws.clear()

    # Headers
    headers = [
        "ID",
        "URL",
        "Test Query",
        "Expected",
        "Status",
        "Result",
        "Response",
        "Created",
        "Completed",
    ]
    ws.update(values=[headers], range_name="A1")
    ws.format(
        "A1:I1",
        {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.5, "blue": 0.2}},
    )

    # Add template row
    template = [
        "NEW",
        "(Enter URL)",
        "(What to check)",
        "(Expected result)",
        "pending",
        "",
        "",
        "",
        "",
    ]
    ws.update(values=[template], range_name="A2")

    # Add example tests
    examples = [
        [
            "W1",
            "https://example.com",
            "Is this site accessible?",
            "yes",
            "pending",
            "",
            "",
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            "",
        ],
        [
            "W2",
            "https://perplexity.ai",
            "What is Perplexity AI?",
            "AI search engine",
            "pending",
            "",
            "",
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            "",
        ],
    ]
    ws.update(values=examples, range_name="A3")

    log("Created WebTests sheet with examples")
    return ws


def process_pending_prompts(spreadsheet, panel):
    """Process all pending prompts from the Prompts sheet."""
    try:
        ws = spreadsheet.worksheet("Prompts")
        rows = ws.get_all_values()

        if len(rows) < 2:
            return 0

        processed = 0

        for i, row in enumerate(rows[1:], start=2):
            if len(row) < 4:
                continue

            prompt_id = row[0]
            prompt_text = row[1]
            prompt_type = row[2] if len(row) > 2 else "search"
            status = row[3] if len(row) > 3 else ""

            # Skip non-pending or template rows
            if status.lower() != "pending":
                continue
            if not prompt_text or prompt_text.startswith("("):
                continue

            log(f"Processing prompt {prompt_id}: {prompt_text[:50]}...")

            # Update status to processing
            ws.update_acell(f"D{i}", "processing")

            try:
                # Send to Perplexity
                response = panel.ask(prompt_text)

                if response:
                    # Update with response
                    ws.update_acell(f"D{i}", "completed")
                    ws.update_acell(f"E{i}", response[:500])  # Limit response length
                    ws.update_acell(f"H{i}", datetime.now().strftime("%Y-%m-%d %H:%M"))
                    log(f"Completed prompt {prompt_id}")
                    processed += 1
                else:
                    ws.update_acell(f"D{i}", "failed")
                    ws.update_acell(f"I{i}", "No response received")

            except Exception as e:
                ws.update_acell(f"D{i}", "failed")
                ws.update_acell(f"I{i}", str(e)[:100])
                log(f"Error processing {prompt_id}: {e}")

        return processed

    except Exception as e:
        log(f"Error processing prompts: {e}")
        return 0


def process_web_tests(spreadsheet, panel):
    """Process pending web tests from the WebTests sheet."""
    try:
        ws = spreadsheet.worksheet("WebTests")
        rows = ws.get_all_values()

        if len(rows) < 2:
            return 0

        processed = 0

        for i, row in enumerate(rows[1:], start=2):
            if len(row) < 5:
                continue

            test_id = row[0]
            url = row[1]
            query = row[2]
            expected = row[3] if len(row) > 3 else ""
            status = row[4] if len(row) > 4 else ""

            # Skip non-pending or template rows
            if status.lower() != "pending":
                continue
            if not url or url.startswith("("):
                continue

            log(f"Processing test {test_id}: {url[:50]}...")

            # Update status to running
            ws.update_acell(f"E{i}", "running")

            try:
                # Create prompt combining URL and query
                prompt = f"Visit {url} and answer: {query}"
                response = panel.ask(prompt)

                if response:
                    # Check if response matches expected (simple contains check)
                    if expected and expected.lower() in response.lower():
                        result = "passed"
                    elif expected:
                        result = "failed"
                    else:
                        result = "completed"

                    ws.update_acell(f"E{i}", result)
                    ws.update_acell(f"F{i}", result)
                    ws.update_acell(f"G{i}", response[:300])
                    ws.update_acell(f"I{i}", datetime.now().strftime("%Y-%m-%d %H:%M"))
                    log(f"Test {test_id}: {result}")
                    processed += 1
                else:
                    ws.update_acell(f"E{i}", "failed")
                    ws.update_acell(f"F{i}", "No response")

            except Exception as e:
                ws.update_acell(f"E{i}", "error")
                ws.update_acell(f"F{i}", str(e)[:100])
                log(f"Error on test {test_id}: {e}")

        return processed

    except Exception as e:
        log(f"Error processing web tests: {e}")
        return 0


def add_prompt(spreadsheet, prompt_text, prompt_type="search"):
    """Add a new prompt to the sheet programmatically."""
    try:
        ws = spreadsheet.worksheet("Prompts")
        rows = ws.get_all_values()

        # Generate new ID
        next_id = f"P{len(rows)}"

        # Add new row
        new_row = [
            next_id,
            prompt_text,
            prompt_type,
            "pending",
            "",
            "",
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            "",
            "",
        ]
        ws.append_row(new_row)

        log(f"Added prompt {next_id}: {prompt_text[:50]}...")
        return next_id

    except Exception as e:
        log(f"Error adding prompt: {e}")
        return None


def get_prompt_result(spreadsheet, prompt_id):
    """Get the result of a specific prompt."""
    try:
        ws = spreadsheet.worksheet("Prompts")
        rows = ws.get_all_values()

        for row in rows[1:]:
            if row and row[0] == prompt_id:
                return {
                    "id": row[0],
                    "prompt": row[1],
                    "status": row[3] if len(row) > 3 else "",
                    "response": row[4] if len(row) > 4 else "",
                    "completed": row[7] if len(row) > 7 else "",
                }

        return None

    except Exception as e:
        log(f"Error getting prompt result: {e}")
        return None


def run_daemon():
    """Run continuous processing daemon."""
    log("Starting Perplexity Sheets daemon...")

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    client = get_sheets_client()
    if not client:
        return

    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        log(f"Connected to: {spreadsheet.title}")
    except Exception as e:
        log(f"Failed to open spreadsheet: {e}")
        return

    # Initialize Perplexity panel
    panel = PerplexityPanel()
    if not panel.connect():
        log("Failed to connect to Perplexity. Make sure Comet is running with debug mode.")
        return

    while True:
        try:
            prompts_done = process_pending_prompts(spreadsheet, panel)
            tests_done = process_web_tests(spreadsheet, panel)

            if prompts_done > 0 or tests_done > 0:
                log(f"Processed {prompts_done} prompts, {tests_done} tests")

        except Exception as e:
            log(f"Daemon error: {e}")
            # Try to reconnect
            try:
                panel.close()
                panel = PerplexityPanel()
                panel.connect()
            except:
                pass

        time.sleep(POLL_INTERVAL)


def test_sheet_connection():
    """Test Google Sheets connection and list sheets."""
    client = get_sheets_client()
    if not client:
        print("Failed to connect to Google Sheets")
        return False

    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        print(f"Connected to: {spreadsheet.title}")
        print(f"URL: {spreadsheet.url}")
        print("\nWorksheets:")
        for ws in spreadsheet.worksheets():
            print(f"  - {ws.title} ({ws.row_count} rows)")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_create_and_modify():
    """Test creating and modifying the sheet."""
    log("Testing sheet creation and modification...")

    client = get_sheets_client()
    if not client:
        return False

    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        log(f"Connected to: {spreadsheet.title}")

        # Create Prompts sheet
        create_prompts_sheet(spreadsheet)

        # Create WebTests sheet
        create_web_tests_sheet(spreadsheet)

        # Add a test prompt
        ws = spreadsheet.worksheet("Prompts")
        test_prompt = f"Test prompt added at {datetime.now().strftime('%H:%M:%S')}"
        test_id = add_prompt(spreadsheet, test_prompt, "test")
        log(f"Added test prompt: {test_id}")

        # Modify it
        rows = ws.get_all_values()
        for i, row in enumerate(rows[1:], start=2):
            if row and row[0] == test_id:
                ws.update_acell(f"I{i}", "Test modification successful")
                log(f"Modified row {i}")
                break

        log("Sheet test completed successfully!")
        return True

    except Exception as e:
        log(f"Sheet test failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Perplexity + Google Sheets Integration")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--test-sheet", action="store_true", help="Test sheet connection")
    parser.add_argument("--create-sheet", action="store_true", help="Create prompts sheet")
    parser.add_argument("--test-modify", action="store_true", help="Test create and modify")
    parser.add_argument("--add", type=str, help="Add a prompt")
    parser.add_argument("--status", action="store_true", help="Check daemon status")
    parser.add_argument("--stop", action="store_true", help="Stop daemon")

    args = parser.parse_args()

    if args.status:
        if PID_FILE.exists():
            pid = PID_FILE.read_text().strip()
            try:
                os.kill(int(pid), 0)
                print(f"Daemon running (PID {pid})")
            except:
                print("Daemon not running (stale PID)")
        else:
            print("Daemon not running")
        return

    if args.stop:
        if PID_FILE.exists():
            pid = PID_FILE.read_text().strip()
            try:
                os.kill(int(pid), 15)
                print(f"Stopped daemon (PID {pid})")
                PID_FILE.unlink()
            except:
                print("Failed to stop")
        return

    if args.test_sheet:
        test_sheet_connection()
        return

    if args.test_modify:
        test_create_and_modify()
        return

    if args.create_sheet:
        client = get_sheets_client()
        if client:
            spreadsheet = client.open_by_key(SPREADSHEET_ID)
            create_prompts_sheet(spreadsheet)
            create_web_tests_sheet(spreadsheet)
        return

    if args.add:
        client = get_sheets_client()
        if client:
            spreadsheet = client.open_by_key(SPREADSHEET_ID)
            prompt_id = add_prompt(spreadsheet, args.add)
            if prompt_id:
                print(f"Added prompt: {prompt_id}")
        return

    if args.daemon:
        run_daemon()
        return

    # Default: process once
    client = get_sheets_client()
    if not client:
        return

    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)

        # Initialize Perplexity panel
        panel = PerplexityPanel()
        if not panel.connect():
            log("Failed to connect to Perplexity. Make sure Comet is running with debug mode.")
            return

        prompts = process_pending_prompts(spreadsheet, panel)
        tests = process_web_tests(spreadsheet, panel)

        log(f"Processed {prompts} prompts, {tests} tests")
        panel.close()

    except Exception as e:
        log(f"Error: {e}")


if __name__ == "__main__":
    main()
