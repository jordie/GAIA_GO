#!/usr/bin/env python3
"""
Project Orchestrator - Autonomous Development System

Continuously improves code by coordinating between:
- Comet/Perplexity: Research, best practices, solutions
- Claude Code (tmux): Implementation, code changes
- Google Sheets: Task tracking, progress monitoring

Flow:
1. Pull task from Google Sheets
2. Research solution via Perplexity
3. Send implementation to Claude Code tmux session
4. Monitor completion
5. Validate and create follow-up tasks
6. Repeat

Usage:
    python3 project_orchestrator.py                # Run once
    python3 project_orchestrator.py --daemon       # Run continuously
    python3 project_orchestrator.py --status       # Check status
    python3 project_orchestrator.py --stop         # Stop daemon
"""

import argparse
import json
import os
import random
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import our modules
from scripts.perplexity_panel import PerplexityPanel

# Configuration
SPREADSHEET_ID = "12i2uO6-41uZdHl_a9BbhBHhR1qbNlAqOgH-CWQBz7rA"
CREDENTIALS_PATH = Path.home() / ".config" / "gspread" / "service_account.json"
LOG_FILE = Path("/tmp/project_orchestrator.log")
PID_FILE = Path("/tmp/project_orchestrator.pid")
DB_FILE = Path("/tmp/project_orchestrator.db")

# Timing
CYCLE_INTERVAL = 60  # Check for new tasks every 60 seconds
TASK_TIMEOUT = 300  # 5 minutes max per task
RESEARCH_TIMEOUT = 90  # 90 seconds for research queries
MILESTONE_SIZE = 5  # Tasks before generating admin decisions
DECISION_CHECK_INTERVAL = 10  # Cycles between checking for decision needs

# Target tmux sessions for different task types
WORKER_SESSIONS = [
    "task_worker1",
    "task_worker2",
    "task_worker3",
    "task_worker4",
    "task_worker5",
    "edu_worker1",
    "edu_worker2",
    "edu_worker3",
]
EXCLUDED_SESSIONS = {"autoconfirm", "architect"}  # Exclude auto-confirm and management session
AUTO_CREATE_SESSIONS = True  # Create new sessions if none available
MAX_AUTO_SESSIONS = 3  # Maximum auto-created sessions


def log(msg: str):
    """Log message to console and file."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except:
        pass


def init_db():
    """Initialize the orchestrator database."""
    conn = sqlite3.connect(str(DB_FILE))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS task_history (
            id INTEGER PRIMARY KEY,
            task_id TEXT,
            task_type TEXT,
            description TEXT,
            research_query TEXT,
            research_result TEXT,
            implementation_session TEXT,
            status TEXT,
            started_at TEXT,
            completed_at TEXT,
            result TEXT
        )
    """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session_state (
            session_name TEXT PRIMARY KEY,
            current_task_id TEXT,
            status TEXT,
            last_activity TEXT
        )
    """
    )
    conn.commit()
    conn.close()


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


def get_or_create_worksheet(spreadsheet, title, rows=200, cols=15):
    """Get existing worksheet or create new one."""
    try:
        return spreadsheet.worksheet(title)
    except:
        return spreadsheet.add_worksheet(title, rows=rows, cols=cols)


def setup_orchestrator_sheet(spreadsheet):
    """Set up the Orchestrator sheet for task coordination."""
    ws = get_or_create_worksheet(spreadsheet, "Orchestrator")

    try:
        first_cell = ws.acell("A1").value
        if first_cell == "ID":
            return ws
    except:
        pass

    ws.clear()
    headers = [
        "ID",
        "Task",
        "Type",
        "Priority",
        "Status",
        "Research Query",
        "Research Result",
        "Implementation",
        "Assigned Session",
        "Created",
        "Started",
        "Completed",
        "Notes",
    ]
    ws.update(values=[headers], range_name="A1")
    ws.format(
        "A1:M1",
        {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.2, "green": 0.8, "blue": 0.4}},
    )

    # Add example tasks
    examples = [
        [
            "O1",
            "Add input validation to login form",
            "feature",
            "7",
            "pending",
            "Best practices for Flask form validation",
            "",
            "",
            "",
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            "",
            "",
            "",
        ],
        [
            "O2",
            "Optimize database queries in dashboard",
            "optimization",
            "5",
            "pending",
            "SQLite query optimization techniques",
            "",
            "",
            "",
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            "",
            "",
            "",
        ],
        [
            "O3",
            "Add error handling to API endpoints",
            "improvement",
            "6",
            "pending",
            "Flask API error handling best practices",
            "",
            "",
            "",
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            "",
            "",
            "",
        ],
    ]
    ws.update(values=examples, range_name="A2")

    log("Created Orchestrator sheet")
    return ws


def get_pending_tasks(spreadsheet) -> List[Dict]:
    """Get pending tasks from the Orchestrator sheet."""
    try:
        ws = spreadsheet.worksheet("Orchestrator")
        rows = ws.get_all_values()

        if len(rows) < 2:
            return []

        tasks = []
        for i, row in enumerate(rows[1:], start=2):
            if len(row) < 5:
                continue

            status = row[4] if len(row) > 4 else ""
            if status.lower() != "pending":
                continue

            tasks.append(
                {
                    "row": i,
                    "id": row[0],
                    "task": row[1],
                    "type": row[2] if len(row) > 2 else "feature",
                    "priority": int(row[3]) if len(row) > 3 and row[3].isdigit() else 5,
                    "research_query": row[5] if len(row) > 5 else "",
                }
            )

        # Sort by priority (higher first)
        tasks.sort(key=lambda x: x["priority"], reverse=True)
        return tasks

    except Exception as e:
        log(f"Error getting pending tasks: {e}")
        return []


def update_task_status(spreadsheet, row: int, status: str, **kwargs):
    """Update task status and other fields in the sheet."""
    try:
        ws = spreadsheet.worksheet("Orchestrator")
        ws.update_acell(f"E{row}", status)

        if "research_result" in kwargs:
            ws.update_acell(f"G{row}", kwargs["research_result"][:500])
        if "implementation" in kwargs:
            ws.update_acell(f"H{row}", kwargs["implementation"][:500])
        if "session" in kwargs:
            ws.update_acell(f"I{row}", kwargs["session"])
        if "started" in kwargs:
            ws.update_acell(f"K{row}", kwargs["started"])
        if "completed" in kwargs:
            ws.update_acell(f"L{row}", kwargs["completed"])
        if "notes" in kwargs:
            ws.update_acell(f"M{row}", kwargs["notes"][:200])

    except Exception as e:
        log(f"Error updating task status: {e}")


def research_with_perplexity(panel: PerplexityPanel, query: str, retries: int = 2) -> Optional[str]:
    """Research a topic using Perplexity via Comet."""
    if not query:
        return None

    for attempt in range(retries + 1):
        try:
            log(
                f"Researching: {query[:50]}..."
                + (f" (attempt {attempt + 1})" if attempt > 0 else "")
            )

            # Reconnect panel if needed
            if attempt > 0:
                try:
                    panel.close()
                except:
                    pass
                if not panel.connect():
                    log("Failed to reconnect to Perplexity")
                    continue

            response = panel.ask(query)
            if response and len(response) > 50:
                log(f"Got research result ({len(response)} chars)")
                return response
            elif response:
                log(f"Got short response ({len(response)} chars), retrying...")
            else:
                log("Empty response, retrying...")

        except Exception as e:
            log(f"Research error: {e}")

        time.sleep(2)

    return None


def create_claude_session(session_name: str) -> bool:
    """Create a new tmux session with Claude Code."""
    try:
        log(f"Creating Claude Code session: {session_name}")

        # Create the tmux session
        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            log(f"Failed to create session: {result.stderr}")
            return False

        time.sleep(1)

        # Start Claude Code in the session
        subprocess.run(
            [
                "tmux",
                "send-keys",
                "-t",
                session_name,
                f"cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect && claude",
                "Enter",
            ],
            timeout=5,
        )

        # Wait for Claude to start
        log(f"Waiting for Claude to start in {session_name}...")
        time.sleep(10)

        # Verify Claude is running (should show prompt)
        capture = subprocess.run(
            ["tmux", "capture-pane", "-t", session_name, "-p"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if "❯" in capture.stdout or "Claude" in capture.stdout:
            log(f"Claude Code started in {session_name}")
            return True

        log(f"Claude may not have started properly in {session_name}")
        return True  # Session created, Claude may still be loading

    except Exception as e:
        log(f"Error creating session: {e}")
        return False


def get_auto_created_sessions() -> List[str]:
    """Get list of auto-created sessions."""
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []

        sessions = result.stdout.strip().split("\n")
        return [s for s in sessions if s.startswith("auto_worker_")]
    except:
        return []


def get_available_session(create_if_needed: bool = True) -> Optional[str]:
    """Find an available tmux session for implementation."""
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None

        sessions = result.stdout.strip().split("\n")

        # First try worker sessions
        for session in WORKER_SESSIONS:
            if session in sessions:
                if is_session_available(session):
                    log(f"Found available session: {session}")
                    return session

        # Then try any non-excluded session
        for session in sessions:
            if session not in EXCLUDED_SESSIONS and session not in WORKER_SESSIONS:
                if is_session_available(session):
                    log(f"Found available session: {session}")
                    return session

        # Create new session if allowed
        if create_if_needed and AUTO_CREATE_SESSIONS:
            auto_sessions = get_auto_created_sessions()
            if len(auto_sessions) < MAX_AUTO_SESSIONS:
                new_session = f"auto_worker_{len(auto_sessions) + 1}"
                if create_claude_session(new_session):
                    return new_session

        return None

    except Exception as e:
        log(f"Error finding session: {e}")
        return None


def is_session_available(session: str) -> bool:
    """Check if a session is available (at prompt and not busy)."""
    try:
        capture = subprocess.run(
            ["tmux", "capture-pane", "-t", session, "-p"], capture_output=True, text=True, timeout=5
        )
        if capture.returncode != 0:
            return False

        output = capture.stdout

        # Check for working indicators (Claude is busy)
        working_indicators = [
            "Metamorphosing",
            "Effecting",
            "Flummoxing",
            "Crunching",
            "esc to interrupt",
            "thought for",
        ]
        for indicator in working_indicators:
            if indicator in output:
                return False

        # Check for command prompt in last 5 lines
        last_lines = output.strip().split("\n")[-5:]
        for line in last_lines:
            if "❯" in line:
                # Make sure it's not just a status bar ❯
                line_stripped = line.strip()
                if line_stripped.startswith("❯") or line_stripped == "❯":
                    return True
                # Also accept prompt with space after
                if "❯ " in line and not "accept" in line.lower():
                    return True

        return False
    except:
        return False


def clear_session_state(session: str) -> bool:
    """Clear any pending state in a Claude Code session before sending new task."""
    try:
        # Capture current state
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", session, "-p"], capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return False

        output = result.stdout

        # Check for pending "accept edits" - press Escape to dismiss
        if "accept edits" in output.lower():
            log(f"Clearing pending edits in {session}")
            subprocess.run(["tmux", "send-keys", "-t", session, "Escape"], timeout=5)
            time.sleep(1)

        # Press Ctrl+C to cancel any ongoing command, then clear line
        subprocess.run(["tmux", "send-keys", "-t", session, "C-c"], timeout=5)
        time.sleep(0.5)

        return True

    except Exception as e:
        log(f"Error clearing session: {e}")
        return False


def send_to_claude_session(session: str, task: str, research: str = None) -> bool:
    """Send a task to a Claude Code tmux session."""
    try:
        log(f"=== Sending task to session: {session} ===")
        log(f"  Task: {task[:80]}{'...' if len(task) > 80 else ''}")
        if research:
            log(f"  Research: {research[:50]}{'...' if len(research) > 50 else ''}")

        # Clear any pending state first
        clear_session_state(session)
        time.sleep(1)

        # Build the prompt - keep it simple, single line works best
        prompt = f"Task: {task}"
        if research:
            # Add research on same line to avoid newline issues
            prompt += f" (Research: {research[:200]})"
        prompt += " Please implement this. When done, say 'TASK COMPLETE'."

        log(f"  Prompt length: {len(prompt)} chars")

        # Send prompt text first using -l (literal) flag to handle special chars
        result1 = subprocess.run(
            ["tmux", "send-keys", "-t", session, "-l", prompt],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result1.returncode != 0:
            log(f"  Warning: send-keys returned {result1.returncode}")

        time.sleep(0.3)

        # Send Enter separately to ensure it's processed
        result2 = subprocess.run(
            ["tmux", "send-keys", "-t", session, "Enter"], capture_output=True, text=True, timeout=5
        )
        if result2.returncode != 0:
            log(f"  Warning: Enter key returned {result2.returncode}")

        log(f"  ✓ Task sent successfully to {session}")
        return True

    except subprocess.TimeoutExpired:
        log(f"  ✗ Timeout sending task to {session}")
        return False
    except Exception as e:
        log(f"  ✗ Error sending to session {session}: {e}")
        return False


def check_session_status(session: str, task_prompt: str = None) -> str:
    """Check the status of a tmux session.

    Args:
        session: The tmux session name
        task_prompt: Optional task prompt (unused, kept for compatibility)
    """
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", session, "-p", "-S", "-50"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return "unknown"

        output = result.stdout

        # Check for completion - look for TASK COMPLETE in recent output
        # Must exclude false positives from the instruction prompt itself
        lines = output.split("\n")
        recent_lines = lines[-30:]

        for line in recent_lines:
            line_stripped = line.strip()
            line_lower = line_stripped.lower()

            # Skip empty lines
            if not line_stripped:
                continue

            # Skip lines that are part of the instruction prompt
            # These contain "say 'TASK COMPLETE'" or similar quoted instructions
            if "say 'task complete'" in line_lower or 'say "task complete"' in line_lower:
                continue
            if "when done" in line_lower and "task complete" in line_lower:
                continue

            # Look for actual completion markers from Claude's response
            # The completion message should be standalone or at start of line
            if "task complete" in line_lower:
                # Additional validation: completion message is typically short
                # and not embedded in a longer instruction
                if len(line_stripped) < 100:  # Short line, likely actual completion
                    return "completed"
                # Or starts with TASK COMPLETE
                if line_lower.startswith("task complete"):
                    return "completed"
                # Or is just the phrase with punctuation
                if line_lower.strip(".,!") == "task complete":
                    return "completed"

        # Check for command prompt in last 5 lines
        last_lines = output.strip().split("\n")[-5:]
        for line in last_lines:
            if "❯" in line or line.strip().endswith("$"):
                # Session is at prompt - check if Claude is actively working
                # Look for Claude activity indicators
                if "⏺" in output[-500:]:  # Claude thinking/working indicator
                    return "working"
                return "idle"

        # Still working if no prompt found
        return "working"

    except Exception as e:
        return "unknown"


def create_followup_task(spreadsheet, original_task: Dict, result: str):
    """Create a follow-up task based on the result.

    Only creates follow-ups for specific actionable items, not recursive reviews.
    """
    # Never create follow-ups for review tasks
    task_lower = original_task.get("task", "").lower()
    type_lower = original_task.get("type", "").lower()

    if "review" in type_lower or "review" in task_lower:
        log(f"No follow-up needed for review task {original_task['id']}")
        return

    # Don't auto-generate follow-ups - let user define goals
    log(f"Task {original_task['id']} completed. Add follow-up tasks manually if needed.")
    return


def process_task(spreadsheet, panel: PerplexityPanel, task: Dict) -> bool:
    """Process a single task through research and implementation."""
    task_id = task["id"]
    task_start = time.time()

    log(f"")
    log(f"{'='*60}")
    log(f"PROCESSING TASK: {task_id}")
    log(f"{'='*60}")
    log(f"  Description: {task['task'][:70]}{'...' if len(task['task']) > 70 else ''}")
    log(f"  Type: {task.get('type', 'unknown')}")
    log(f"  Priority: {task.get('priority', 'N/A')}")

    # Update status to researching
    update_task_status(
        spreadsheet, task["row"], "researching", started=datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    # Step 1: Research with Perplexity (if available)
    log(f"")
    log(f"[Step 1/4] Research Phase")
    research_result = None
    if task["research_query"] and panel:
        log(f"  Query: {task['research_query'][:50]}...")
        research_result = research_with_perplexity(panel, task["research_query"])
        if research_result:
            log(f"  ✓ Research complete ({len(research_result)} chars)")
            update_task_status(
                spreadsheet, task["row"], "researched", research_result=research_result
            )
        else:
            log(f"  ✗ Research failed/empty")
    elif not panel:
        log(f"  ⊘ Skipped (Perplexity not connected)")
    else:
        log(f"  ⊘ Skipped (no research query)")

    # Step 2: Find available session
    log(f"")
    log(f"[Step 2/4] Finding Available Session")
    session = get_available_session()
    if not session:
        log(f"  ✗ No available session found")
        update_task_status(spreadsheet, task["row"], "pending", notes="No available session")
        return False
    log(f"  ✓ Found session: {session}")

    # Step 3: Send to Claude Code session
    log(f"")
    log(f"[Step 3/4] Sending to Claude Code")
    update_task_status(spreadsheet, task["row"], "implementing", session=session)

    if not send_to_claude_session(session, task["task"], research_result):
        log(f"  ✗ Failed to send task to session")
        update_task_status(spreadsheet, task["row"], "failed", notes="Failed to send to session")
        return False

    # Step 4: Monitor implementation (with timeout)
    log(f"")
    log(f"[Step 4/4] Monitoring Implementation")
    log(f"  Timeout: {TASK_TIMEOUT}s, checking every 10s")

    # Build task prompt for detection (same as sent)
    task_prompt = f"Task: {task['task']}"

    # Wait before first check to let Claude start processing
    log(f"  Waiting 5s for task to be received...")
    time.sleep(5)

    start_time = time.time()
    check_count = 0
    while time.time() - start_time < TASK_TIMEOUT:
        check_count += 1
        status = check_session_status(session, task_prompt)
        elapsed = int(time.time() - start_time)

        if status == "completed":
            log(f"  ✓ TASK COMPLETE after {elapsed}s ({check_count} checks)")
            update_task_status(
                spreadsheet,
                task["row"],
                "completed",
                completed=datetime.now().strftime("%Y-%m-%d %H:%M"),
                notes="Task completed successfully",
            )

            # Create follow-up task
            create_followup_task(spreadsheet, task, "completed")
            log(f"{'='*60}")
            log(f"Task {task_id} completed successfully!")
            log(f"{'='*60}")
            return True

        elif status == "failed":
            log(f"  ✗ Task FAILED after {elapsed}s")
            update_task_status(
                spreadsheet,
                task["row"],
                "failed",
                completed=datetime.now().strftime("%Y-%m-%d %H:%M"),
                notes="Implementation failed",
            )
            return False

        elif status == "idle":
            # Session is idle but no completion message
            log(f"  ⊘ Session idle after {elapsed}s - marking for review")
            update_task_status(
                spreadsheet,
                task["row"],
                "review_needed",
                completed=datetime.now().strftime("%Y-%m-%d %H:%M"),
                notes="Needs manual review",
            )
            return True

        # Log progress periodically
        if check_count % 6 == 0:  # Every 60 seconds
            log(f"  ... still working ({elapsed}s elapsed, status: {status})")

        time.sleep(10)

    # Timeout
    log(f"  ✗ TIMEOUT after {TASK_TIMEOUT}s")
    update_task_status(spreadsheet, task["row"], "timeout", notes=f"Timeout after {TASK_TIMEOUT}s")
    log(f"Task {task_id} timed out")
    return False


def generate_improvement_tasks(spreadsheet, panel: PerplexityPanel):
    """Use Perplexity to analyze the codebase and generate improvement tasks."""
    try:
        # Ask Perplexity for improvement suggestions
        query = """Analyze a Flask Python project called 'Architect Dashboard' that manages:
        - Projects, Milestones, Features, Bugs
        - tmux sessions
        - Task queues
        - Google Sheets integration

        Suggest 3 specific improvements for:
        1. Code quality
        2. Performance
        3. User experience

        Be specific and actionable."""

        response = research_with_perplexity(panel, query)

        if response:
            # Parse suggestions and add as tasks
            ws = spreadsheet.worksheet("Orchestrator")
            rows = ws.get_all_values()
            base_id = len(rows) + 1

            # Add a meta-improvement task
            new_task = [
                f"O{base_id}",
                "Review and implement suggested improvements",
                "improvement",
                "6",
                "pending",
                "How to prioritize code improvements in a Flask application",
                response[:500],
                "",
                "",
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                "",
                "",
                "Auto-generated from Perplexity analysis",
            ]
            ws.append_row(new_task)
            log("Generated improvement task from Perplexity analysis")

    except Exception as e:
        log(f"Error generating improvement tasks: {e}")


def get_completed_tasks_count(spreadsheet) -> int:
    """Get count of completed tasks since last decision point."""
    try:
        ws = spreadsheet.worksheet("Orchestrator")
        rows = ws.get_all_values()
        completed = sum(1 for row in rows[1:] if len(row) > 4 and row[4].lower() == "completed")
        return completed
    except:
        return 0


def get_recent_activity_summary(spreadsheet) -> str:
    """Get a summary of recent activity for admin decisions."""
    try:
        ws = spreadsheet.worksheet("Orchestrator")
        rows = ws.get_all_values()

        completed = []
        in_progress = []
        failed = []

        for row in rows[1:]:
            if len(row) < 5:
                continue
            status = row[4].lower()
            task_desc = row[1][:50] if len(row) > 1 else ""

            if status == "completed":
                completed.append(task_desc)
            elif status in ["implementing", "researching", "researched"]:
                in_progress.append(task_desc)
            elif status in ["failed", "timeout"]:
                failed.append(task_desc)

        summary = f"""
Recent Activity Summary:
- Completed: {len(completed)} tasks
- In Progress: {len(in_progress)} tasks
- Failed: {len(failed)} tasks

Recent completions:
{chr(10).join(f'  - {t}' for t in completed[-5:])}

Failed tasks:
{chr(10).join(f'  - {t}' for t in failed[-3:])}
"""
        return summary.strip()

    except Exception as e:
        return f"Error getting summary: {e}"


def generate_admin_decisions(spreadsheet, panel: PerplexityPanel):
    """Generate high-level decisions for admin review every few milestones."""
    try:
        log("Generating admin decisions for milestone review...")

        # Get activity summary
        activity_summary = get_recent_activity_summary(spreadsheet)

        # Ask Perplexity for strategic recommendations
        query = f"""Based on this project activity summary for 'Architect Dashboard':

{activity_summary}

As a senior software architect, provide 3 strategic decisions the admin should make:
1. Priority decision: What should be prioritized next?
2. Technical decision: Any architectural changes needed?
3. Process decision: How to improve the development workflow?

For each, provide:
- The decision needed
- Options to consider (2-3 options)
- Your recommendation

Be specific and actionable."""

        response = research_with_perplexity(panel, query)

        if response:
            # Add to Decisions sheet
            try:
                decisions_ws = spreadsheet.worksheet("Decisions")
            except:
                decisions_ws = spreadsheet.add_worksheet("Decisions", rows=200, cols=10)
                headers = [
                    "ID",
                    "Decision",
                    "Category",
                    "Options",
                    "Status",
                    "Owner",
                    "Deadline",
                    "Outcome",
                    "Rationale",
                    "Created",
                ]
                decisions_ws.update(values=[headers], range_name="A1")

            rows = decisions_ws.get_all_values()
            next_id = f"D{len(rows) + 1}"

            # Add the decision request
            new_decision = [
                next_id,
                f"Milestone Review: Strategic decisions needed",
                "strategic",
                "See notes for full analysis",
                "pending",
                "admin",
                "",
                "",
                response[:1000],
                datetime.now().strftime("%Y-%m-%d %H:%M"),
            ]
            decisions_ws.append_row(new_decision)
            log(f"Created admin decision request: {next_id}")

            # Also add to Summary sheet
            try:
                summary_ws = spreadsheet.worksheet("Summary")
                current = summary_ws.get_all_values()

                # Find and update milestone section or add new one
                milestone_row = [
                    "",
                    f'=== MILESTONE REVIEW ({datetime.now().strftime("%Y-%m-%d %H:%M")}) ===',
                    "",
                ]
                summary_ws.append_row(milestone_row)
                summary_ws.append_row(["", "Admin decisions pending in Decisions sheet", ""])
                summary_ws.append_row(
                    ["", f"Completed tasks: {get_completed_tasks_count(spreadsheet)}", ""]
                )
            except:
                pass

            return True

    except Exception as e:
        log(f"Error generating admin decisions: {e}")
        return False


# Track cycles for milestone decisions
_cycle_count = 0


def run_cycle(spreadsheet, panel: PerplexityPanel):
    """Run one cycle of the orchestrator."""
    global _cycle_count
    _cycle_count += 1

    log(f"=== Starting orchestration cycle #{_cycle_count} ===")

    # Check if we need to generate admin decisions (every N tasks or cycles)
    completed_count = get_completed_tasks_count(spreadsheet)
    if (
        completed_count > 0
        and completed_count % MILESTONE_SIZE == 0
        and _cycle_count % DECISION_CHECK_INTERVAL == 0
    ):
        log(f"Milestone reached ({completed_count} tasks). Generating admin decisions...")
        generate_admin_decisions(spreadsheet, panel)

    # Get pending tasks
    tasks = get_pending_tasks(spreadsheet)
    log(f"Found {len(tasks)} pending tasks")

    if not tasks:
        # No tasks - generate some improvement tasks (if Perplexity available)
        if panel:
            log("No pending tasks. Generating improvement suggestions...")
            generate_improvement_tasks(spreadsheet, panel)
        else:
            log("No pending tasks. Add tasks to the Orchestrator sheet.")
        return

    # Process the highest priority task
    task = tasks[0]
    process_task(spreadsheet, panel, task)


def run_daemon():
    """Run the orchestrator as a daemon."""
    log("Starting Project Orchestrator daemon...")

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    init_db()

    # Initialize connections
    client = get_sheets_client()
    if not client:
        log("Failed to connect to Google Sheets")
        return

    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        setup_orchestrator_sheet(spreadsheet)
    except Exception as e:
        log(f"Failed to open spreadsheet: {e}")
        return

    # Initialize Perplexity panel (optional - will retry later if fails)
    panel = PerplexityPanel()
    if not panel.connect():
        log("Warning: Could not connect to Perplexity. Research will be skipped.")
        panel = None  # Will work without research

    log("Orchestrator ready. Starting continuous improvement loop...")

    while True:
        try:
            run_cycle(spreadsheet, panel)
        except Exception as e:
            log(f"Cycle error: {e}")
            # Try to reconnect Perplexity if it was working before
            if panel:
                try:
                    panel.close()
                except:
                    pass
            panel = PerplexityPanel()
            if not panel.connect():
                panel = None

        log(f"Next cycle in {CYCLE_INTERVAL}s...")
        time.sleep(CYCLE_INTERVAL)


def main():
    parser = argparse.ArgumentParser(description="Project Orchestrator - Autonomous Development")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--status", action="store_true", help="Check status")
    parser.add_argument("--stop", action="store_true", help="Stop daemon")
    parser.add_argument("--setup", action="store_true", help="Set up sheets")
    parser.add_argument("--generate", action="store_true", help="Generate improvement tasks")

    args = parser.parse_args()

    if args.status:
        if PID_FILE.exists():
            pid = PID_FILE.read_text().strip()
            try:
                os.kill(int(pid), 0)
                print(f"Orchestrator running (PID {pid})")
                # Show recent log
                print("\nRecent activity:")
                subprocess.run(["tail", "-10", str(LOG_FILE)])
            except:
                print("Orchestrator not running (stale PID)")
        else:
            print("Orchestrator not running")
        return

    if args.stop:
        if PID_FILE.exists():
            pid = PID_FILE.read_text().strip()
            try:
                os.kill(int(pid), 15)
                print(f"Stopped orchestrator (PID {pid})")
                PID_FILE.unlink()
            except:
                print("Failed to stop")
        return

    if args.setup:
        client = get_sheets_client()
        if client:
            spreadsheet = client.open_by_key(SPREADSHEET_ID)
            setup_orchestrator_sheet(spreadsheet)
            print("Orchestrator sheet set up successfully")
        return

    if args.generate:
        client = get_sheets_client()
        panel = PerplexityPanel()
        if client and panel.connect():
            spreadsheet = client.open_by_key(SPREADSHEET_ID)
            generate_improvement_tasks(spreadsheet, panel)
            panel.close()
        return

    if args.daemon:
        run_daemon()
        return

    # Default: run once
    init_db()
    client = get_sheets_client()
    if not client:
        return

    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        setup_orchestrator_sheet(spreadsheet)

        panel = PerplexityPanel()
        if not panel.connect():
            log("Failed to connect to Perplexity")
            return

        run_cycle(spreadsheet, panel)
        panel.close()

    except Exception as e:
        log(f"Error: {e}")


if __name__ == "__main__":
    main()
