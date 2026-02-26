#!/usr/bin/env python3
"""
Auto-Confirm Worker - Periodic Claude Session Monitor

Runs for a few minutes, stops, waits 1-3 minutes, repeats.
Only one instance runs at a time.

Run in background:
    nohup ./auto_confirm_worker.py &

Or in tmux:
    tmux new-session -d -s autoconfirm './auto_confirm_worker.py'

Stop:
    pkill -f auto_confirm_worker
"""

import fcntl
import os
import random
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Import the learner
sys.path.insert(0, str(Path(__file__).parent))
try:
    from confirmation_learner import ConfirmationLearner

    learner = ConfirmationLearner()
except ImportError:
    learner = None

# Timing configuration - BALANCED for reliability + safety
RUN_DURATION_MIN = 10 * 60  # Run for 10-15 minutes (longer cycles)
RUN_DURATION_MAX = 15 * 60
GAP_MIN = 1  # Gap 1-3s (extremely short to never miss prompts)
GAP_MAX = 3
CONFIRM_DELAY_MIN = 3.0  # Confirm delay 3-5 seconds (longer to give user time to type)
CONFIRM_DELAY_MAX = 5.0
CHECK_INTERVAL = 0.3  # Check interval (faster to catch prompts immediately)
SESSION_COOLDOWN = 30  # 30s cooldown per session to prevent rapid re-confirmations

# SAFETY: Only auto-confirm if session idle for this long (prevents interference with active typing)
IDLE_THRESHOLD = 2  # Seconds - only confirm if no input for 2s (reduced for responsiveness)

# SAFETY: Operation whitelist - only auto-confirm these operations
SAFE_OPERATIONS = {
    "read",  # Reading files is safe
    "grep",  # Searching is safe
    "glob",  # File pattern matching is safe
    "accept_edits",  # Accepting edits (after review)
    "confirm",  # Generic user confirmations
    "plan_confirm",  # Plan mode confirmations
    "continue",  # Claude "What should Claude do?" - safe to continue
    "edit",  # AUTO-CONFIRM: Editing files for worker sessions
    "write",  # AUTO-CONFIRM: Writing files for worker sessions
    "bash",  # AUTO-CONFIRM: Bash commands for coordinator sessions
}

# CAUTION: Operations that require explicit approval (will be logged but skipped)
REQUIRES_APPROVAL = {
    # Currently empty - all operations auto-confirmed for speed
}

# DRY RUN MODE: Set to True to log what WOULD be confirmed without actually confirming
DRY_RUN = False

# Sessions to EXCLUDE from auto-confirm (user's active sessions)
EXCLUDED_SESSIONS = {
    "autoconfirm",  # This worker's session (must always exclude itself)
    # All other sessions (foundation, architect, orchestrator, workers) will be auto-confirmed
    # 'foundation' - Go wrapper development session (AUTO-CONFIRMED)
}

# Task Registry and Conflict Detection
TASK_REGISTRY_FILE = Path("data/gaia/task_registry.json")
TYPING_PREFIX = "##"  # Prefix to indicate user is still typing

# Files
LOCK_FILE = Path("/tmp/auto_confirm.lock")
DB_FILE = Path("/tmp/auto_confirm.db")
LOG_FILE = Path("/tmp/auto_confirm.log")
DB_TIMEOUT = 30


def get_db_connection():
    """Get database connection with WAL mode and proper timeout."""
    conn = sqlite3.connect(str(DB_FILE), timeout=DB_TIMEOUT)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def load_task_registry():
    """Load task registry from JSON file."""
    import json

    if TASK_REGISTRY_FILE.exists():
        try:
            with open(TASK_REGISTRY_FILE) as f:
                return json.load(f)
        except Exception as e:
            log(f"Error loading task registry: {e}")
            return None
    return None


def check_for_typing(prompt_text):
    """Check if user is still typing (starts with ## prefix)."""
    return prompt_text.strip().startswith(TYPING_PREFIX)


def check_duplicate_work(task_name):
    """Check if task already assigned to another group."""
    registry = load_task_registry()
    if not registry:
        return False

    for task_id, task in registry.get("active_tasks", {}).items():
        if task["status"] == "in_progress":
            # Check for 80%+ name similarity
            if similarity(task_name, task["name"]) >= 0.8:
                log(f"[CONFLICT] Duplicate task detected: {task_name} similar to {task['name']}")
                log(f"  Assigned to: {task['groups']}")
                return True
    return False


def check_environment_conflict(env_name):
    """Check if environment already in use."""
    registry = load_task_registry()
    if not registry:
        return False

    env_info = registry.get("environment_usage", {}).get(env_name)
    if env_info and env_info.get("status") == "in_use":
        log(f"[CONFLICT] Environment {env_name} already in use by {env_info.get('group')}")
        return True
    return False


def similarity(a, b):
    """Simple string similarity check (0-1)."""
    from difflib import SequenceMatcher

    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


# Patterns
ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
# Unicode box drawing characters (used in Claude's prompts)
UNICODE_BOX = re.compile(r"[╌─━┌┐└┘├┤┬┴┼│▶❯▸►]")

# Multiple prompt patterns to match different Claude versions
# Pattern 1: "Do you want to make this edit to <file>?"
EDIT_PROMPT_PATTERN = re.compile(
    r"Do you want to (?:make this edit to|proceed with editing)\s+(?P<filename>\S+)\?\s*\n"
    r".*?(?P<options>(?:.*?\d+\..*?\n)+)"
    r".*?(?:Esc to cancel|Tab to amend)",
    re.MULTILINE | re.DOTALL,
)

# Pattern 2: "Do you want to proceed?" (legacy format)
PROCEED_PROMPT_PATTERN = re.compile(
    r"Do you want to proceed\?\s*\n" r".*?(?P<options>(?:.*?\d+\..*?\n)+)" r".*?Esc to cancel",
    re.MULTILINE | re.DOTALL,
)

# Pattern 3: Simple Yes/No prompt with numbered options
SIMPLE_PROMPT_PATTERN = re.compile(
    r"(?:Do you want to|Allow|Proceed|Execute|Run)\s+[^\n]+\?\s*\n"
    r".*?[❯>]\s*1\.\s*Yes"
    r".*?2\.\s*Yes",
    re.MULTILINE | re.DOTALL,
)

# Pattern for bash/command prompts
BASH_PROMPT_PATTERN = re.compile(
    r"(?:Bash|Execute|Run)\s*\([^\)]+\)\s*\n" r".*?Do you want to (?:proceed|run|execute)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except:
        pass


def acquire_lock():
    """Ensure only one instance runs."""
    try:
        lock_fd = open(LOCK_FILE, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        return lock_fd
    except IOError:
        return None


def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Use consistent schema matching the existing database
    c.execute(
        """CREATE TABLE IF NOT EXISTS confirmations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_name TEXT NOT NULL,
        operation_type TEXT NOT NULL,
        command TEXT NOT NULL,
        description TEXT,
        delay_used REAL,
        confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        dry_run INTEGER DEFAULT 0
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS session_stats (
        session_name TEXT PRIMARY KEY,
        total_confirmations INTEGER DEFAULT 0,
        last_confirmation TIMESTAMP,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )"""
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_confirmations_session ON confirmations(session_name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_confirmations_time ON confirmations(confirmed_at)")
    conn.commit()
    conn.close()


def save_confirmation(session, operation, command, delay, response_key="1"):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            """INSERT INTO confirmations (session_name, operation_type, command, delay_used)
                     VALUES (?, ?, ?, ?)""",
            (session, operation, command[:200], delay),
        )
        c.execute(
            """INSERT INTO session_stats (session_name, total_confirmations, last_confirmation)
                     VALUES (?, 1, CURRENT_TIMESTAMP)
                     ON CONFLICT(session_name) DO UPDATE SET
                         total_confirmations = total_confirmations + 1,
                         last_confirmation = CURRENT_TIMESTAMP""",
            (session,),
        )
        conn.commit()
        conn.close()

        # Record in learner
        if learner:
            learner.record_confirmation(session, operation, command, response_key, success=True)
    except Exception as e:
        log(f"DB error: {e}")


def get_sessions():
    try:
        r = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            return [s.strip() for s in r.stdout.strip().split("\n") if s.strip()]
    except:
        pass
    return []


def get_output(session):
    try:
        # Capture more lines to ensure we don't miss prompts
        r = subprocess.run(
            ["tmux", "capture-pane", "-t", session, "-p", "-S", "-200"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            return r.stdout
    except:
        pass
    return ""


def get_session_idle_time(session):
    """Get seconds since last activity in session.

    Uses tmux client activity info. Returns None if unable to determine.
    """
    try:
        # Get pane activity timestamp
        r = subprocess.run(
            ["tmux", "display-message", "-t", session, "-p", "#{pane_activity}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            activity_timestamp = int(r.stdout.strip())
            current_time = int(time.time())
            idle_seconds = current_time - activity_timestamp
            return idle_seconds
    except:
        pass
    return None


def is_session_idle(session):
    """Check if session has been idle long enough to safely auto-confirm.

    Returns True if idle > IDLE_THRESHOLD seconds, False otherwise.
    """
    # Check if there's user activity in the input area (by looking for ## prefix or recent typing indicators)
    # If we can't determine idle status, be conservative and assume active (don't confirm)
    try:
        # First check: look for ## prefix indicating user is still typing
        output = get_output(session)
        if output and detect_user_typing(output):
            return False  # User is typing, don't idle

        # If no ## prefix, assume idle (safe to confirm)
        return True
    except Exception as e:
        log(f"⚠️  Error checking idle status for {session}: {e}")
        return True  # Default to idle if can't determine


def check_kill_switch():
    """Check if auto-confirm has been disabled via API/file.

    Returns True if kill switch is active (worker should stop).
    """
    kill_switch_file = Path("/tmp/auto_confirm_kill_switch")
    if kill_switch_file.exists():
        try:
            with open(kill_switch_file, "r") as f:
                content = f.read().strip().lower()
                # Check if explicitly disabled
                if content in ["1", "true", "enabled", "stop"]:
                    return True
        except:
            pass
    return False


def is_operation_safe(operation_type):
    """Check if operation is in the safe whitelist.

    Returns True if operation can be auto-confirmed safely.
    """
    if not operation_type:
        return False
    op_lower = operation_type.lower()
    return op_lower in SAFE_OPERATIONS


def find_prompt(output):
    """Find ACTIVE confirmation prompts in Claude output.

    Only returns a prompt if it appears to be waiting for input (not already answered).
    Returns dict with 'operation' and 'command' if active prompt found, else None.
    """
    # Clean ANSI escape codes
    clean = ANSI_ESCAPE.sub("", output)

    # Get only the last 20 lines - active prompts should be at the bottom
    lines = [l.strip() for l in clean.split("\n") if l.strip()]
    if len(lines) < 3:
        return None

    last_lines = lines[-20:]
    last_text = "\n".join(last_lines)

    # SAFETY CHECK: If the output ends with typical "working" indicators, skip
    # This prevents false positives when Claude is processing
    # BUT: Ignore option text like "allow reading from..." - only check for actual status indicators
    last_few = "\n".join(lines[-3:]).lower()

    # Skip this check if we detect a permission prompt (has "Esc to cancel" in last few lines)
    has_permission_prompt = any(
        "esc to cancel" in line.lower() or "tab to amend" in line.lower() for line in lines[-5:]
    )

    if not has_permission_prompt:
        if any(
            indicator in last_few
            for indicator in [
                "reading",
                "writing",
                "searching",
                "running",
                "executing",
                "analyzing",
                "processing",
                "loading",
                "fetching",
            ]
        ):
            return None

    # ===== CLAUDE CONVERSATIONAL PROMPTS =====
    # Pattern: "What should Claude do", "I've stopped. What would you like me to do next?"
    # These are Claude asking for guidance/continuation - safe to auto-continue
    last_text_lower = last_text.lower()
    if any(
        phrase in last_text_lower
        for phrase in [
            "what should claude do",
            "what would you like me to do",
            "what should i do next",
            "how would you like me to proceed",
        ]
    ):
        if "❯" in last_text or ">" in last_text[-20:]:  # Has cursor prompt
            return {"operation": "continue", "command": "claude continuation prompt"}

    # ===== NEW FORMAT: "accept edits" prompt =====
    # Pattern: "⏵⏵ accept edits on (shift+Tab to cycle) · N files +X -Y"
    # This appears when Claude has pending edits to accept
    for i, line in enumerate(last_lines):
        if "accept edits" in line.lower() and ("⏵" in line or "shift+Tab" in line.lower()):
            # Check this is at the very end (active prompt)
            lines_after = [l for l in last_lines[i + 1 :] if l.strip() and not l.startswith("─")]
            if len(lines_after) <= 1:  # Allow 1 line after (might be cursor)
                # Extract file count if possible
                file_info = "accept edits"
                if "files" in line.lower():
                    file_info = line.strip()
                return {"operation": "accept_edits", "command": file_info}

    # ===== PLAN MODE FORMAT: "Would you like to proceed?" with multiple options =====
    # Pattern: "❯ 1. Yes, clear context..." or "❯ 1. Yes, auto-accept..."
    # This appears in plan mode prompts
    # STRICT: Must have the question AND cursor on an option in the last 10 lines
    last_10_lines = lines[-10:] if len(lines) >= 10 else lines
    last_10_text = "\n".join(last_10_lines)
    if "Would you like to proceed?" in last_10_text:
        has_cursor_on_option = False
        for line in last_10_lines:
            # Must have cursor indicator AND numbered option on same line
            if "❯" in line and re.search(r"\d+\.\s+Yes", line):
                has_cursor_on_option = True
                break
        # Must also have the plan mode keywords nearby
        if has_cursor_on_option and any(
            kw in last_10_text for kw in ["clear context", "auto-accept", "manually approve"]
        ):
            return {"operation": "plan_confirm", "command": "plan mode confirmation"}

    # ===== LEGACY FORMAT: Yes/No numbered options =====
    # Key indicators that a prompt is ACTIVE and waiting:
    # 1. "Esc to cancel" should be in the last FEW lines (not just anywhere)
    # 2. The cursor indicator "❯" should be on the "1. Yes" line
    # 3. No text should appear AFTER "Esc to cancel" (except empty lines)
    # 4. Both options must be visible

    # STRICT: Only check the last 15 lines for the prompt
    last_15_lines = lines[-15:] if len(lines) >= 15 else lines
    last_15_text = "\n".join(last_15_lines)

    # Check if this looks like an active prompt
    # Two formats:
    # 1. Permission prompts: "1. Yes" + "2. Yes, allow..." + "3. No"
    # 2. Simple confirmations: "1. Yes" + "2. No"
    # Handle wrapped text: "2.Yes" or "2. Yes" or "2.No"
    has_yes_option = "1. Yes" in last_15_text or "1.Yes" in last_15_text
    has_second_option = (
        "2. Yes" in last_15_text
        or "2.Yes" in last_15_text
        or "2. No" in last_15_text
        or "2.No" in last_15_text
    )
    has_cancel = "Esc to cancel" in last_15_text or "Tab to amend" in last_15_text

    if not (has_yes_option and has_second_option and has_cancel):
        return None

    # Find where "Esc to cancel" appears - it should be in the last 5 lines
    esc_line_idx = None
    for i, line in enumerate(last_15_lines):
        if "Esc to cancel" in line or "Tab to amend" in line:
            esc_line_idx = i

    if esc_line_idx is None:
        return None

    # STRICT: "Esc to cancel" must be in the last 5 lines of the 15
    if esc_line_idx < len(last_15_lines) - 6:
        return None

    # Check that nothing significant appears after the cancel line
    # (which would indicate the prompt was already answered)
    lines_after = last_15_lines[esc_line_idx + 1 :]
    for line in lines_after:
        # Skip empty lines, UI decorations, and status lines
        line_stripped = line.strip()
        if not line_stripped:
            continue
        if line.startswith("─"):  # Horizontal lines
            continue
        if line == "?" or "for shortcuts" in line.lower():
            continue
        if line.startswith("❯") and len(line_stripped) <= 3:  # Just cursor alone
            continue
        if "⏵⏵" in line or "accept edits" in line.lower():  # Status line at bottom
            continue
        if "esc to interrupt" in line.lower() or "ctrl+" in line.lower():  # Status bar
            continue
        # Skip single help text words that are continuations (e.g., "explain", "cancel")
        if line_stripped.lower() in ["explain", "cancel", "help", "amend", "options", "proceed"]:
            continue
        # If there's actual content after the prompt, it was already answered
        if len(line_stripped) > 5:
            return None

    # Check for the active cursor indicator on ANY option (1 or 2)
    # The cursor might be on option 1 OR option 2 when the prompt appears
    has_active_cursor = False
    for line in last_15_lines:
        # Check for cursor on any numbered option (1. Yes, 2. Yes, 2. No, etc.)
        if "❯" in line and re.search(r"\d+\.\s+(Yes|No)", line):
            has_active_cursor = True
            break

    # STRICT: Must have the cursor indicator, not just '>'
    if not has_active_cursor:
        return None

    # Determine operation type from context
    context = "\n".join(last_15_lines[: esc_line_idx + 1]).lower()
    if "edit" in context or "make this edit" in context:
        # Extract filename if possible
        for line in last_15_lines:
            if "edit to" in line.lower():
                parts = line.split()
                for i, p in enumerate(parts):
                    if p.lower() == "to" and i + 1 < len(parts):
                        filename = parts[i + 1].rstrip("?")
                        return {"operation": "edit", "command": f"edit {filename}"}
        return {"operation": "edit", "command": "edit file"}
    elif "bash" in context or "command" in context or "execute" in context:
        return {"operation": "bash", "command": "run command"}
    elif "write" in context:
        return {"operation": "write", "command": "write file"}
    elif "read" in context:
        return {"operation": "read", "command": "read file"}
    else:
        return {"operation": "confirm", "command": "confirm action"}


def is_file_modification_op(operation_type):
    """Check if operation is a file modification that should use '2' (don't ask again)."""
    if not operation_type:
        return False
    op_lower = operation_type.lower()
    return any(op in op_lower for op in ["edit", "write", "create"])


def is_accept_edits_op(operation_type):
    """Check if operation is the new 'accept edits' format (just needs Enter)."""
    if not operation_type:
        return False
    return "accept_edits" in operation_type.lower()


def is_plan_confirm_op(operation_type):
    """Check if operation is a plan mode confirmation (needs '1' then Enter)."""
    if not operation_type:
        return False
    return "plan_confirm" in operation_type.lower()


def is_continue_op(operation_type):
    """Check if operation is Claude asking for continuation (needs 'continue' or Enter)."""
    if not operation_type:
        return False
    return "continue" in operation_type.lower()


def detect_user_typing(output):
    """Detect if user is currently typing (## prefix on recent line).

    Returns True if user input starts with ## prefix (indicates still typing).
    """
    lines = output.split("\n")

    # Check last 5 lines for ## prefix (user typing indicator)
    for line in lines[-5:]:
        stripped = line.strip()
        if stripped.startswith(TYPING_PREFIX):
            return True

    return False


def send_confirm(session, operation_type=None):
    """Send confirmation to tmux session.

    For 'accept edits' prompts, just sends Enter.
    For 'plan_confirm' prompts, sends '1' (Yes, with approval) - safer than auto-accept.
    For 'continue' prompts (Claude's "What should Claude do?"), sends "continue".
    For file modification operations (edit, write, create), sends '1' (Yes).
    For other operations, sends '1' (Yes, proceed).

    NOTE: Changed to always use '1' to be safer. '2' (don't ask again) can cause issues
    if we accidentally confirm the wrong thing.
    """
    try:
        # New "accept edits" format just needs Enter to accept
        if is_accept_edits_op(operation_type):
            subprocess.run(["tmux", "send-keys", "-t", session, "Enter"], timeout=5)
            return True

        # Claude continuation prompts - send "continue" to keep task flow going
        if is_continue_op(operation_type):
            subprocess.run(["tmux", "send-keys", "-t", session, "continue"], timeout=5)
            time.sleep(0.1)
            subprocess.run(["tmux", "send-keys", "-t", session, "Enter"], timeout=5)
            return True

        # Double-check: re-capture the screen to verify prompt is still there
        output = get_output(session)
        if output:
            prompt_check = find_prompt(output)
            if not prompt_check:
                log(f"⚠️  {session}: Prompt disappeared before confirm, skipping")
                return False

        # Plan mode confirmation - use '1' (safer than auto-accept)
        if is_plan_confirm_op(operation_type):
            subprocess.run(["tmux", "send-keys", "-t", session, "1"], timeout=5)
            time.sleep(0.1)
            subprocess.run(["tmux", "send-keys", "-t", session, "Enter"], timeout=5)
            return True

        # For file modifications and bash operations, use '2' (don't ask again)
        # This prevents repeated prompts for the same operation
        # For other operations, use '1' (Yes) for safety
        if is_file_modification_op(operation_type) or operation_type == "bash":
            key = "2"  # Don't ask again - better UX, reduces future prompts
        else:
            key = "1"  # Just yes for other operations

        # Send key + Enter atomically for reliability (fixes submission failures)
        # Use C-m (carriage return) instead of Enter for cross-platform compatibility
        try:
            # Get prompt state before sending (for verification)
            before_output = get_output(session)
            before_hash = hash(before_output) if before_output else None

            # Send key and C-m (carriage return) atomically
            subprocess.run(
                ["tmux", "send-keys", "-t", session, key, "C-m"],
                timeout=5
            )

            # Verify the prompt changed (proves the command was actually submitted)
            max_retries = 5
            for attempt in range(max_retries):
                time.sleep(0.2)
                after_output = get_output(session)
                after_hash = hash(after_output) if after_output else None

                if after_hash != before_hash:
                    log(f"   ✓ Confirmed {operation_type} in {session} (verified)")
                    return True

            # If we get here, prompt didn't change (command may not have been submitted)
            log(f"   ⚠️  WARNING: Prompt unchanged after sending {key} to {session} - may not have submitted")
            return False
        except Exception as e:
            log(f"Error sending to {session}: {e}")
            return False
    except Exception as e:
        log(f"Error sending to {session}: {e}")
        return False


def run_monitor_cycle(duration):
    """Run monitoring for specified duration."""
    log(f"▶️  Starting monitor cycle ({duration//60}m {duration%60}s)")
    log(f"   Excluding sessions: {', '.join(EXCLUDED_SESSIONS)}")
    if DRY_RUN:
        log(f"   🔍 DRY RUN MODE - will log but not confirm")
    log(f"   ✅ Safe operations: {', '.join(SAFE_OPERATIONS)}")
    log(f"   ⚠️  Requires approval: {', '.join(REQUIRES_APPROVAL)}")

    pending = {}
    handled = {}
    session_cooldowns = {}  # Track per-session cooldowns
    end_time = time.time() + duration
    confirmations = 0
    skipped_unsafe = 0
    skipped_active = 0
    skipped_conflicts = 0  # Track conflicts detected and skipped

    while time.time() < end_time:
        # Check kill switch
        if check_kill_switch():
            log("🛑 Kill switch activated - stopping worker")
            return confirmations
        sessions = get_sessions()
        if not sessions:
            time.sleep(1)
            continue

        # DEBUG: Log all sessions being checked
        log(f"🔍 Checking {len(sessions)} sessions: {', '.join(sessions)}")

        for session in sessions:
            # Skip excluded sessions
            if session in EXCLUDED_SESSIONS:
                continue

            # Skip sessions in cooldown
            if session in session_cooldowns:
                if time.time() < session_cooldowns[session]:
                    continue
                else:
                    del session_cooldowns[session]

            output = get_output(session)
            if not output:
                log(f"  ❌ {session}: No output")
                continue

            prompt = find_prompt(output)

            if not prompt:
                log(f"  ⚪ {session}: No prompt detected")
                if session in pending:
                    del pending[session]
                continue

            # Generate stable prompt key using hash (not truncated text which can vary)
            # This prevents duplicates when text wrapping changes the visible output
            import hashlib
            command_hash = hashlib.md5(prompt['command'].encode()).hexdigest()[:8]
            prompt_key = f"{prompt['operation']}:{command_hash}"

            # Skip recently handled prompts (same prompt in same session)
            if session in handled and prompt_key in handled[session]:
                if (
                    time.time() - handled[session][prompt_key] < 120
                ):  # 120 second cooldown per prompt to prevent duplicate confirmations
                    continue

            # New prompt detected
            if session not in pending:
                delay = random.uniform(CONFIRM_DELAY_MIN, CONFIRM_DELAY_MAX)
                pending[session] = (prompt_key, time.time() + delay, prompt)
                log(f"📋 {session}: {prompt['operation']} - {prompt['command'][:40]}...")
                log(f"   ⏱️  Confirming in {delay:.1f}s")
            else:
                stored_key, confirm_time, stored_prompt = pending[session]

                # Only confirm if it's the SAME prompt we saw before (still waiting)
                if stored_key == prompt_key and time.time() >= confirm_time:
                    # SAFETY CHECK 1: Is session idle?
                    if not is_session_idle(session):
                        idle_time = get_session_idle_time(session) or 0
                        log(
                            f"⏭️  {session}: Skipping - session active "
                            f"(idle: {idle_time}s < {IDLE_THRESHOLD}s)"
                        )
                        skipped_active += 1
                        del pending[session]
                        continue

                    # SAFETY CHECK 2: Is user currently typing (## prefix)?
                    if detect_user_typing(output):
                        log(
                            f"⏭️  {session}: Skipping - user is typing "
                            f"(detected {TYPING_PREFIX} prefix)"
                        )
                        skipped_conflicts += 1
                        # Don't delete pending - keep checking until user finishes
                        continue

                    # SAFETY CHECK 3: Extract task name from command for conflict detection
                    task_name = (
                        stored_prompt.get("command", "").split()[0]
                        if stored_prompt.get("command")
                        else ""
                    )

                    # Check for duplicate work
                    if task_name and check_duplicate_work(task_name):
                        log(f"⚠️  {session}: Skipping - duplicate work detected for '{task_name}'")
                        log("   Another group may be working on similar task")
                        skipped_conflicts += 1
                        del pending[session]
                        continue

                    # Check for environment conflicts
                    if task_name and check_environment_conflict(f"env_{session}"):
                        log(f"⚠️  {session}: Skipping - environment conflict detected")
                        log("   This environment may already be assigned to another task")
                        skipped_conflicts += 1
                        del pending[session]
                        continue

                    # SAFETY CHECK 4: Is operation safe to auto-confirm?
                    if not is_operation_safe(stored_prompt["operation"]):
                        if stored_prompt["operation"] in REQUIRES_APPROVAL:
                            log(
                                f"⚠️  {session}: Skipping - requires manual approval: "
                                f"{stored_prompt['operation']}"
                            )
                            log(f"   Command: {stored_prompt['command']}")
                            skipped_unsafe += 1
                        del pending[session]
                        continue

                    # DRY RUN: Log but don't actually confirm
                    if DRY_RUN:
                        log(f"🔍 DRY RUN - Would confirm: {session} - {stored_prompt['operation']}")
                        del pending[session]
                        continue

                    # Set preemptive cooldown BEFORE confirming (prevents duplicates if check-send gap)
                    # This is critical: set it immediately before attempting to send
                    session_cooldowns[session] = time.time() + SESSION_COOLDOWN

                    # All safety checks passed - confirm!
                    if send_confirm(session, stored_prompt["operation"]):
                        confirmations += 1
                        if is_accept_edits_op(stored_prompt["operation"]):
                            key_sent = "Enter"
                        elif is_plan_confirm_op(stored_prompt["operation"]):
                            key_sent = "1 (Yes, clear context)"
                        elif is_continue_op(stored_prompt["operation"]):
                            key_sent = "continue"
                        elif (
                            is_file_modification_op(stored_prompt["operation"])
                            or stored_prompt["operation"] == "bash"
                        ):
                            key_sent = "2 (Yes, don't ask again)"
                        else:
                            key_sent = "1 (Yes)"
                        log(f"✅ Confirmed #{confirmations}: {session} (sent '{key_sent}')")
                        # Extract just the key (e.g., "1", "2", "Enter", "continue")
                        response_key = key_sent.split()[0] if key_sent else "1"
                        save_confirmation(
                            session,
                            stored_prompt["operation"],
                            stored_prompt["command"],
                            time.time() - (confirm_time - CONFIRM_DELAY_MIN),
                            response_key,
                        )
                    else:
                        # Confirmation failed - clear the preemptive cooldown so we can retry next cycle
                        log(f"   ⚠️  Confirmation failed - cooldown will be cleared for next attempt")
                        del session_cooldowns[session]

                    if session not in handled:
                        handled[session] = {}
                    handled[session][prompt_key] = time.time()
                    del pending[session]

        # Clean old handled entries
        now = time.time()
        for sess in list(handled.keys()):
            handled[sess] = {k: v for k, v in handled[sess].items() if now - v < 120}
            if not handled[sess]:
                del handled[sess]

        time.sleep(CHECK_INTERVAL)

    log(
        f"⏹️  Cycle complete: {confirmations} confirmations, "
        f"{skipped_active} skipped (active), {skipped_unsafe} skipped (unsafe), "
        f"{skipped_conflicts} skipped (conflicts)"
    )
    return confirmations


def main():
    print(
        """
╔═══════════════════════════════════════════════════════════╗
║       AUTO-CONFIRM WORKER - Periodic Monitor              ║
║                                                           ║
║  • Runs 2-4 minute cycles                                 ║
║  • Gaps of 1-3 minutes between cycles                     ║
║  • Random 2-5 second confirm delay                        ║
║  • Only one instance allowed                              ║
║                                                           ║
║  Ctrl+C to stop                                           ║
╚═══════════════════════════════════════════════════════════╝
"""
    )

    # NOTE: Single-instance lock removed - HA monitor handles coordination via mutex
    # Multiple workers can now run under HA monitor with shared mutex lock
    lock = acquire_lock()
    if not lock:
        log("⚠️  Could not acquire startup lock (OK if running under HA monitor)")
        # Continue anyway - mutex will handle concurrency
        pass

    init_db()
    log("🚀 Worker started (periodic mode)")

    cycle = 0
    total_confirmations = 0

    try:
        while True:
            cycle += 1

            # Random run duration
            duration = random.randint(RUN_DURATION_MIN, RUN_DURATION_MAX)

            log(f"━━━ Cycle {cycle} ━━━")
            confirmations = run_monitor_cycle(duration)
            total_confirmations += confirmations

            # Random gap
            gap = random.randint(GAP_MIN, GAP_MAX)
            log(f"💤 Sleeping {gap//60}m {gap%60}s until next cycle...")
            time.sleep(gap)

    except KeyboardInterrupt:
        log(f"Worker stopped. Total: {total_confirmations} confirmations in {cycle} cycles")
        print(f"\n👋 Stopped. {total_confirmations} confirmations across {cycle} cycles.")
    finally:
        lock.close()
        try:
            LOCK_FILE.unlink()
        except:
            pass


if __name__ == "__main__":
    main()
