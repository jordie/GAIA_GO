#!/usr/bin/env python3
"""
Multi-threaded Auto-Confirm Worker
Each session monitored in its own thread for instant response
"""

import logging
import random
import sqlite3
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(threadName)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.FileHandler("/tmp/threaded_auto_confirm.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Database for tracking
DB_PATH = "/tmp/auto_confirm.db"
db_lock = threading.Lock()

# Sessions to monitor (EXCLUDES 'architect' - user's active session)
TARGET_SESSIONS = [
    "concurrent_worker1",
    "concurrent_worker2",
    "concurrent_worker3",
    "edu_worker1",
    "edu_worker2",
    "edu_worker3",
    "dev_worker1",
    "dev_worker2",  # Added dev_worker sessions
    "task_worker1",
    "task_worker2",
    "task_worker3",
    "task_worker4",
    "task_worker5",
    "codex",
    "codex2",
    "codex3",
    "codex_edu",
    "comet",
    "comet2",
    "claude_codex",
    "claude_comet",
    "claude_orchestrator",  # Added claude_ prefixed sessions
    "arch_dev",
    "edu_dev",
    "pharma_dev",
    "basic_edu",
    "wrapper_claude"
    # 'architect' - EXCLUDED (user's active session)
]


def init_db():
    """Initialize confirmation tracking database"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS confirmations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_name TEXT NOT NULL,
            operation_type TEXT NOT NULL,
            command TEXT NOT NULL,
            description TEXT,
            delay_used REAL,
            confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            dry_run INTEGER DEFAULT 0
        )
    """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_confirmations_session ON confirmations(session_name)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_confirmations_time ON confirmations(confirmed_at)")
    conn.commit()
    conn.close()


def log_confirmation(session, operation_type, command, description=""):
    """Thread-safe confirmation logging"""
    try:
        with db_lock:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                """
                INSERT INTO confirmations (session_name, operation_type, command, description)
                VALUES (?, ?, ?, ?)
            """,
                (session, operation_type, command, description),
            )
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error(f"Error logging: {e}")


def get_tmux_sessions():
    """Get list of existing tmux sessions"""
    try:
        result = subprocess.run(
            "tmux list-sessions -F '#{session_name}'",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return [s.strip() for s in result.stdout.strip().split("\n") if s.strip()]
    except Exception as e:
        logger.error(f"Error getting sessions: {e}")
        return []


def monitor_session_thread(session_name):
    """
    Monitor a single session in its own thread
    Responds instantly to any prompt
    """
    logger.info(f"Started monitoring {session_name}")
    last_confirm = 0

    while True:
        try:
            # Capture pane output
            result = subprocess.run(
                f"tmux capture-pane -t {session_name} -p | tail -20",
                shell=True,
                capture_output=True,
                text=True,
                timeout=2,
            )

            output = result.stdout

            # Check for prompts
            has_prompt = any(
                phrase in output
                for phrase in [
                    "Do you want to proceed?",
                    "Do you want to create",
                    "Do you want to edit",
                    "Do you want to write",
                    "Do you want to read",
                    "accept edits on",  # Claude Code edit acceptance
                    "shift+tab to cycle",  # Claude Code option cycling
                ]
            )

            if has_prompt:
                # Cooldown check (15 seconds - increased to reduce aggressiveness)
                now = time.time()
                if now - last_confirm < 15:
                    time.sleep(0.5)
                    continue

                last_confirm = now

                # Check if this is "accept edits on" prompt (just needs Enter)
                is_accept_edits = "accept edits on" in output.lower()

                # Check if option 2 (allow all) exists
                use_option_2 = any(
                    phrase in output.lower()
                    for phrase in [
                        "allow all",
                        "during this session",
                        "allow reading",
                        "allow writing",
                        "allow edits",
                    ]
                )

                # Add random 1-5 second delay before confirming
                confirm_delay = random.uniform(1.0, 5.0)
                logger.info(
                    f"⏱️  {session_name}: Waiting {confirm_delay:.1f}s before confirming..."
                )
                time.sleep(confirm_delay)

                if is_accept_edits:
                    logger.info(f"✅ {session_name}: Accept edits (Enter)")
                    subprocess.run(f"tmux send-keys -t {session_name} Enter", shell=True, timeout=1)
                    log_confirmation(session_name, "accept_edits", "Enter", "Accept edits")
                    time.sleep(1)
                elif use_option_2:
                    logger.info(f"✅ {session_name}: Pre-approve ALL (option 2)")
                    subprocess.run(f"tmux send-keys -t {session_name} 2", shell=True, timeout=1)
                    time.sleep(0.2)
                    subprocess.run(f"tmux send-keys -t {session_name} Enter", shell=True, timeout=1)
                    log_confirmation(session_name, "pre_approve_all", "2+Enter", "Allow all")
                    time.sleep(2)  # Longer wait after pre-approval
                else:
                    logger.info(f"✅ {session_name}: Confirm (option 1)")
                    subprocess.run(f"tmux send-keys -t {session_name} 1", shell=True, timeout=1)
                    time.sleep(0.2)
                    subprocess.run(f"tmux send-keys -t {session_name} Enter", shell=True, timeout=1)
                    log_confirmation(session_name, "confirm", "1+Enter", "Single confirm")
                    time.sleep(1)

            # Check every 0.5 seconds
            time.sleep(0.5)

        except subprocess.TimeoutExpired:
            time.sleep(1)
        except Exception as e:
            logger.debug(f"{session_name}: {e}")
            time.sleep(2)


def main():
    """Launch a thread for each session"""
    logger.info("🚀 Starting Multi-Threaded Auto-Confirm Worker")

    # Initialize database
    init_db()

    # Get active sessions
    active_sessions = get_tmux_sessions()
    sessions_to_monitor = [s for s in TARGET_SESSIONS if s in active_sessions]

    logger.info(f"   Monitoring {len(sessions_to_monitor)} sessions with dedicated threads")

    # Launch threads
    threads = []
    for session in sessions_to_monitor:
        thread = threading.Thread(
            target=monitor_session_thread, args=(session,), name=session, daemon=True
        )
        thread.start()
        threads.append(thread)
        time.sleep(0.1)  # Stagger thread starts

    logger.info(f"   All {len(threads)} threads started")

    # Keep main thread alive
    try:
        while True:
            time.sleep(60)
            # Check thread health
            alive = sum(1 for t in threads if t.is_alive())
            logger.debug(f"Threads alive: {alive}/{len(threads)}")
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down")


if __name__ == "__main__":
    main()
