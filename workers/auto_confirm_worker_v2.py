#!/usr/bin/env python3
"""
Auto-Confirm Worker V2 - Optimized with Risk-Based Delays + Pattern Learning

KEY IMPROVEMENTS over V1:
- 93% faster: 0.05-1.0s delays (vs 1-2s)
- Risk-based classification (low/medium/high)
- Continuous operation (no gaps between cycles)
- Better prompt detection
- PATTERN LEARNING: Adapts to tool UI changes automatically

Run as daemon:
    python3 workers/auto_confirm_worker_v2.py --daemon

Check status:
    ps aux | grep auto_confirm_worker_v2

Stop:
    pkill -f auto_confirm_worker_v2
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

# Pattern tracking integration
PATTERN_TRACKING_ENABLED = False
try:
    # Add workers directory to path if needed
    workers_dir = Path(__file__).parent
    if str(workers_dir) not in sys.path:
        sys.path.insert(0, str(workers_dir))

    from pattern_integration import PatternDetector, adaptive_confirm

    PATTERN_TRACKING_ENABLED = True
except ImportError as e:
    print(f"⚠️  Pattern tracking not available: {e}")


# ===== V2 OPTIMIZED TIMING =====
CHECK_INTERVAL = 0.2  # Check every 200ms (faster detection)
SESSION_COOLDOWN = 3  # 3s cooldown between same-session confirms

# Risk-based confirmation delays (93% faster than V1's 1-2s)
RISK_DELAYS = {
    "low": (0.05, 0.2),  # 50-200ms for safe ops (read, grep, glob)
    "medium": (0.3, 0.6),  # 300-600ms for edits
    "high": (0.8, 1.2),  # 800ms-1.2s for bash/write
}

# Operation risk classification
OPERATION_RISK = {
    # Low risk - read-only operations
    "read": "low",
    "grep": "low",
    "glob": "low",
    "list": "low",
    "search": "low",
    # Medium risk - file modifications
    "edit": "medium",
    "accept_edits": "medium",
    "patch": "medium",
    # High risk - execution and writes
    "write": "high",
    "bash": "high",
    "execute": "high",
    "delete": "high",
}

# Sessions to exclude
EXCLUDED_SESSIONS = {
    "autoconfirm",
    "auto_confirm_v2",
}

# Files
LOCK_FILE = Path("/tmp/auto_confirm_v2.lock")
DB_FILE = Path("/tmp/auto_confirm_v2.db")
LOG_FILE = Path("/tmp/auto_confirm_v2.log")
DB_TIMEOUT = 30

# Patterns
ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
UNICODE_BOX = re.compile(r"[╌─━┌┐└┘├┤┬┴┼│▶❯▸►]")

# Prompt detection patterns
EDIT_PROMPT_PATTERN = re.compile(
    r"Do you want to (?:make this edit to|proceed with editing)\s+(?P<filename>\S+)\?\s*\n"
    r".*?(?P<options>(?:.*?\d+\..*?\n)+)"
    r".*?(?:Esc to cancel|Tab to amend)",
    re.MULTILINE | re.DOTALL,
)

PROCEED_PROMPT_PATTERN = re.compile(
    r"Do you want to proceed\?\s*\n" r".*?(?P<options>(?:.*?\d+\..*?\n)+)" r".*?Esc to cancel",
    re.MULTILINE | re.DOTALL,
)

SIMPLE_PROMPT_PATTERN = re.compile(
    r"(?:Do you want to|Allow|Proceed)\s+[^\n]+\?\s*\n" r".*?[❯>]\s*1\.\s*Yes",
    re.MULTILINE | re.DOTALL,
)


def log(msg):
    """Log with timestamp."""
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
        log("Another instance is running")
        return None


def get_db_connection():
    """Get database connection with WAL mode."""
    conn = sqlite3.connect(str(DB_FILE), timeout=DB_TIMEOUT)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db():
    """Initialize database with V2 schema."""
    conn = get_db_connection()
    c = conn.cursor()

    c.execute(
        """CREATE TABLE IF NOT EXISTS confirmations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_name TEXT NOT NULL,
        operation_type TEXT NOT NULL,
        risk_level TEXT NOT NULL,
        command TEXT NOT NULL,
        delay_used REAL,
        confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    # V2: Track confirmation cooldowns to prevent duplicate confirms
    c.execute(
        """CREATE TABLE IF NOT EXISTS session_cooldowns (
        session_name TEXT PRIMARY KEY,
        last_confirm_time REAL NOT NULL
    )"""
    )

    c.execute("CREATE INDEX IF NOT EXISTS idx_confirmations_session ON confirmations(session_name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_confirmations_time ON confirmations(confirmed_at)")

    conn.commit()
    conn.close()


def save_confirmation(session, operation, risk, command, delay):
    """Save confirmation to database."""
    try:
        conn = get_db_connection()
        c = conn.cursor()

        c.execute(
            """INSERT INTO confirmations (session_name, operation_type, risk_level, command, delay_used)
                     VALUES (?, ?, ?, ?, ?)""",
            (session, operation, risk, command[:200], delay),
        )

        c.execute(
            """INSERT INTO session_stats (session_name, total_confirmations, last_confirmation)
                     VALUES (?, 1, CURRENT_TIMESTAMP)
                     ON CONFLICT(session_name) DO UPDATE SET
                         total_confirmations = total_confirmations + 1,
                         last_confirmation = CURRENT_TIMESTAMP""",
            (session,),
        )

        # Update cooldown
        c.execute(
            """INSERT INTO session_cooldowns (session_name, last_confirm_time)
                     VALUES (?, ?)
                     ON CONFLICT(session_name) DO UPDATE SET
                         last_confirm_time = ?""",
            (session, time.time(), time.time()),
        )

        conn.commit()
        conn.close()
    except Exception as e:
        log(f"DB error: {e}")


def is_session_on_cooldown(session):
    """Check if session is on cooldown (recently confirmed)."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "SELECT last_confirm_time FROM session_cooldowns WHERE session_name = ?", (session,)
        )
        row = c.fetchone()
        conn.close()

        if row:
            elapsed = time.time() - row[0]
            # Ignore stale timestamps (older than 1 hour) - treat as not on cooldown
            if elapsed > 3600:
                return False
            return elapsed < SESSION_COOLDOWN
        return False
    except:
        return False


def get_sessions():
    """Get all tmux sessions."""
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
    """Get session output."""
    try:
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


def clean_text(text):
    """Remove ANSI codes and unicode box drawing."""
    text = ANSI_ESCAPE.sub("", text)
    text = UNICODE_BOX.sub("", text)
    return text


def detect_operation(output):
    """Detect operation type from prompt text.

    Returns: (operation_type, risk_level) or (None, None)
    """
    # Check for specific operation keywords in the prompt
    lower = output.lower()

    # Read operations
    if any(word in lower for word in ["read", "reading", "view", "show"]):
        return "read", "low"
    elif any(word in lower for word in ["grep", "search", "find", "glob"]):
        return "grep", "low"

    # Edit operations
    elif any(word in lower for word in ["edit", "patch", "modify", "accept"]):
        if "accept" in lower and "edit" in lower:
            return "accept_edits", "medium"
        return "edit", "medium"

    # High risk operations
    elif any(word in lower for word in ["write", "create file", "writing"]):
        return "write", "high"
    elif any(word in lower for word in ["bash", "execute", "run", "command"]):
        return "bash", "high"
    elif "delete" in lower or "remove" in lower:
        return "delete", "high"

    # Default to medium risk for unknown prompts
    return "unknown", "medium"


def find_prompt(output):
    """Find confirmation prompt in output.

    Returns: dict with prompt info or None
    """
    clean = clean_text(output)
    lines = clean.split("\n")

    # Must have recent content (not just empty)
    if len([l for l in lines[-20:] if l.strip()]) < 3:
        return None

    # Get last 15 lines for analysis
    last_15 = "\n".join(lines[-15:])
    last_15_text = last_15.lower()

    # NEW: Check for "accept edits on" interface (Claude Code v2 style)
    # NOTE: This appears to be a STATUS INDICATOR, not a confirmation prompt
    # It auto-dismisses when processing completes - DO NOT try to confirm it
    has_accept_edits = any(
        "accept edits on" in line.lower()
        or ("shift+tab to cycle" in line.lower() and "esc to interrupt" in line.lower())
        for line in lines[-5:]
    )

    if has_accept_edits:
        # Skip - this is a status indicator, not an interactive prompt
        return None

    # Check for permission prompt markers
    has_permission_prompt = any(
        "esc to cancel" in line.lower() or "tab to amend" in line.lower() for line in lines[-5:]
    )

    # Skip if session appears busy (unless it's a permission prompt)
    if not has_permission_prompt:
        if any(
            indicator in last_15_text
            for indicator in [
                "thinking",
                "running",
                "searching",
                "executing",
                "analyzing",
                "processing",
                "loading",
                "fetching",
                "swooping",
                "simmering",
                "grooving",
            ]
        ):
            return None

    # Check for YES option format (handle both "1. Yes" and "1.Yes" and wrapped text)
    has_yes_option = "1. Yes" in last_15 or "1.Yes" in last_15 or "1. yes" in last_15_text
    has_second_option = (
        "2. Yes" in last_15
        or "2.Yes" in last_15
        or "2. No" in last_15
        or "2.No" in last_15
        or "2. yes" in last_15_text
        or "2. no" in last_15_text
    )

    if not (has_yes_option and has_second_option):
        return None

    # Check for cancel instruction
    if not ("esc to cancel" in last_15_text or "tab to amend" in last_15_text):
        return None

    # Extract operation type and risk level
    operation, risk = detect_operation(last_15)

    return {"type": "confirmation", "operation": operation, "risk": risk, "text": last_15}


def confirm_prompt(session, prompt_info):
    """Send confirmation to session.

    Returns: True if confirmed, False otherwise
    """
    try:
        # Get risk-based delay
        risk = prompt_info.get("risk", "medium")
        delay_min, delay_max = RISK_DELAYS.get(risk, RISK_DELAYS["medium"])
        delay = random.uniform(delay_min, delay_max)

        time.sleep(delay)

        # Handle different prompt types
        prompt_type = prompt_info.get("type", "confirmation")

        if prompt_type == "accept_edits":
            # New Claude Code interface - try sending "1" then Enter
            subprocess.run(
                ["tmux", "send-keys", "-t", session, "1"], capture_output=True, timeout=5
            )
            time.sleep(0.1)
            subprocess.run(
                ["tmux", "send-keys", "-t", session, "Enter"], capture_output=True, timeout=5
            )
        else:
            # Traditional interface - send "1" then Enter
            subprocess.run(
                ["tmux", "send-keys", "-t", session, "1", "Enter"], capture_output=True, timeout=5
            )

        # Log and save
        operation = prompt_info.get("operation", "unknown")
        log(f"✓ {session}: {operation} ({risk} risk, {delay*1000:.0f}ms) [{prompt_type}]")
        save_confirmation(session, operation, risk, prompt_info.get("text", "")[:100], delay)

        return True
    except Exception as e:
        log(f"Error confirming {session}: {e}")
        return False


def process_session(session, pattern_detector=None):
    """Process one session, return True if confirmed."""
    # Skip excluded sessions
    if session in EXCLUDED_SESSIONS:
        return False

    # Skip if on cooldown
    if is_session_on_cooldown(session):
        return False

    # Get output and check for prompt
    output = get_output(session)
    if not output:
        return False

    # TRY PATTERN-BASED DETECTION FIRST (adaptive learning)
    if PATTERN_TRACKING_ENABLED and pattern_detector:
        should_confirm, key, pattern = adaptive_confirm(session, output, pattern_detector)

        if pattern and pattern_detector.should_skip_pattern(pattern):
            # Pattern exists but should be skipped (e.g., status indicators)
            return False

        if should_confirm and key and pattern:
            # Pattern detected and has action - use it!
            try:
                # Send the key specified by the pattern
                delay_min, delay_max = RISK_DELAYS.get("medium", (0.3, 0.6))
                delay = random.uniform(delay_min, delay_max)
                time.sleep(delay)

                subprocess.run(
                    ["tmux", "send-keys", "-t", session, key, "Enter"],
                    capture_output=True,
                    timeout=5,
                )

                # Log
                log(f"✓ {session}: {pattern['pattern_name']} (pattern-based, {delay*1000:.0f}ms)")

                # Record occurrence in pattern tracker
                pattern_detector.record_pattern_occurrence(
                    pattern_id=pattern["pattern_id"],
                    session_name=session,
                    matched_text=pattern["matched_text"],
                    context=output[-200:],
                    action_taken=f"send_key:{key}",
                    success=True,
                )

                # Also save in confirmation DB
                save_confirmation(
                    session, pattern["pattern_name"], "medium", pattern["matched_text"][:100], delay
                )

                return True
            except Exception as e:
                log(f"Pattern-based confirm failed for {session}: {e}")
                # Fall through to legacy detection

    # FALLBACK: Legacy detection (backward compatibility)
    prompt_info = find_prompt(output)
    if not prompt_info:
        return False

    # Confirm the prompt using legacy method
    return confirm_prompt(session, prompt_info)


def cleanup_stale_cooldowns():
    """Remove cooldowns older than 1 hour."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        # Delete cooldowns older than 1 hour
        c.execute(
            "DELETE FROM session_cooldowns WHERE (? - last_confirm_time) > 3600", (time.time(),)
        )
        deleted = c.rowcount
        conn.commit()
        conn.close()
        if deleted > 0:
            log(f"Cleaned up {deleted} stale cooldowns")
    except Exception as e:
        log(f"Error cleaning cooldowns: {e}")


def run_continuous():
    """Run continuously with optimized checking."""
    global PATTERN_TRACKING_ENABLED

    log("Starting V2 auto-confirm (continuous mode)")
    log(
        f"Risk delays: low={RISK_DELAYS['low']}, med={RISK_DELAYS['medium']}, high={RISK_DELAYS['high']}"
    )

    # Initialize pattern detector if available
    pattern_detector = None
    if PATTERN_TRACKING_ENABLED:
        try:
            pattern_detector = PatternDetector()
            pattern_detector.load_patterns()
            log(f"✓ Pattern tracking enabled ({len(pattern_detector.pattern_cache)} tools)")
        except Exception as e:
            log(f"⚠️  Pattern tracking init failed: {e}")
            PATTERN_TRACKING_ENABLED = False

    cycle_count = 0
    confirm_count = 0
    last_cleanup = time.time()
    last_pattern_refresh = time.time()

    try:
        while True:
            cycle_count += 1

            # Periodic cleanup of stale cooldowns (every 5 minutes)
            if time.time() - last_cleanup > 300:
                cleanup_stale_cooldowns()
                last_cleanup = time.time()

            # Periodic pattern refresh (every 5 minutes)
            if pattern_detector and time.time() - last_pattern_refresh > 300:
                try:
                    pattern_detector.refresh_cache_if_needed()
                    last_pattern_refresh = time.time()
                except Exception as e:
                    log(f"Pattern refresh error: {e}")

            # Get all sessions
            sessions = get_sessions()
            active_sessions = [s for s in sessions if s not in EXCLUDED_SESSIONS]

            if cycle_count % 100 == 0:  # Log every 100 cycles
                mode = "pattern+legacy" if pattern_detector else "legacy"
                log(
                    f"Cycle {cycle_count}: {len(active_sessions)} sessions, {confirm_count} confirms ({mode})"
                )

            # Process each session
            for session in active_sessions:
                try:
                    if process_session(session, pattern_detector):
                        confirm_count += 1
                except Exception as e:
                    log(f"Error processing {session}: {e}")

            # Short sleep before next check
            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        log(f"Stopped. Processed {cycle_count} cycles, {confirm_count} confirmations")
    except Exception as e:
        log(f"Fatal error: {e}")


def main():
    """Main entry point."""
    # Check for daemon flag
    if "--daemon" in sys.argv:
        # Fork to background
        pid = os.fork()
        if pid > 0:
            print(f"V2 auto-confirm started as daemon (PID: {pid})")
            sys.exit(0)

        # Detach from terminal
        os.setsid()
        sys.stdin = open("/dev/null", "r")
        sys.stdout = open("/tmp/auto_confirm_v2.out", "a")
        sys.stderr = open("/tmp/auto_confirm_v2.err", "a")

    # Acquire lock
    lock_fd = acquire_lock()
    if not lock_fd:
        print("Another V2 instance is already running")
        sys.exit(1)

    # Initialize database
    init_db()

    # Run continuous monitoring
    run_continuous()


if __name__ == "__main__":
    main()
