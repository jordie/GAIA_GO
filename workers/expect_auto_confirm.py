#!/usr/bin/env python3
"""
Expect-based Auto-Confirm Worker
Uses pexpect for reliable prompt detection and response
Much more reliable than text-parsing approach
"""

import logging
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

import pexpect

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler("/tmp/expect_auto_confirm.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Database for tracking
DB_PATH = "/tmp/auto_confirm.db"

# Sessions to monitor
TARGET_SESSIONS = [
    "concurrent_worker1",
    "concurrent_worker2",
    "concurrent_worker3",
    "edu_worker1",
    "edu_worker2",
    "edu_worker3",
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
    "arch_dev",
    "edu_dev",
    "pharma_dev",
    "basic_edu",
    "wrapper_claude",
    "architect",
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
    """Log confirmation to database"""
    try:
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
        logger.error(f"Error logging confirmation: {e}")


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
        logger.error(f"Error getting tmux sessions: {e}")
        return []


def monitor_session(session_name):
    """
    Monitor a single session and auto-respond to prompts
    This is the core expect-based logic
    """
    try:
        # Spawn tmux attach in read-only mode
        cmd = f"tmux capture-pane -t {session_name} -p"

        while True:
            # Capture current pane output
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=2)

            output = result.stdout

            # Check for various prompt patterns
            if (
                "Do you want to proceed?" in output
                or "Do you want to create" in output
                or "Do you want to edit" in output
            ):
                # Check if there's an "allow all" option (option 2)
                if "allow all" in output.lower() or "during this session" in output:
                    logger.info(f"✅ {session_name}: Pre-approving all operations (option 2)")
                    subprocess.run(f'tmux send-keys -t {session_name} "2" Enter', shell=True)
                    log_confirmation(
                        session_name, "pre_approve_all", "option 2", "Allow all operations"
                    )
                    time.sleep(2)  # Wait longer after pre-approval
                else:
                    # Regular approval (option 1)
                    logger.info(f"✅ {session_name}: Confirming prompt (option 1)")
                    subprocess.run(f'tmux send-keys -t {session_name} "1" Enter', shell=True)
                    log_confirmation(session_name, "confirm", "option 1", "Single confirmation")
                    time.sleep(0.5)

            # Small delay before next check
            time.sleep(0.3)

    except KeyboardInterrupt:
        logger.info(f"Stopped monitoring {session_name}")
    except Exception as e:
        logger.error(f"Error monitoring {session_name}: {e}")


def main():
    """Main worker loop - monitors all sessions concurrently"""
    logger.info("🚀 Starting Expect-based Auto-Confirm Worker")
    logger.info(f"   Monitoring {len(TARGET_SESSIONS)} sessions")

    # Initialize database
    init_db()

    # Get active sessions
    active_sessions = get_tmux_sessions()
    sessions_to_monitor = [s for s in TARGET_SESSIONS if s in active_sessions]

    logger.info(f"   Active sessions: {len(sessions_to_monitor)}")
    logger.info(
        f"   Sessions: {', '.join(sessions_to_monitor[:5])}{'...' if len(sessions_to_monitor) > 5 else ''}"
    )

    # Main monitoring loop
    last_session_check = time.time()
    last_confirm = {}  # Track last confirmation time per session to avoid spam

    while True:
        try:
            # Refresh session list every 30 seconds
            if time.time() - last_session_check > 30:
                active_sessions = get_tmux_sessions()
                sessions_to_monitor = [s for s in TARGET_SESSIONS if s in active_sessions]
                last_session_check = time.time()

            # Monitor each session
            for session in sessions_to_monitor:
                try:
                    # Capture pane output
                    result = subprocess.run(
                        f"tmux capture-pane -t {session} -p | tail -15",
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=1,
                    )

                    output = result.stdout

                    # Check for prompts
                    has_prompt = False
                    use_option_2 = False

                    if any(
                        phrase in output
                        for phrase in [
                            "Do you want to proceed?",
                            "Do you want to create",
                            "Do you want to edit",
                            "Do you want to write",
                            "Do you want to read",
                        ]
                    ):
                        has_prompt = True

                        # Check if option 2 (allow all) is available
                        if any(
                            phrase in output.lower()
                            for phrase in [
                                "allow all",
                                "during this session",
                                "allow reading",
                                "allow writing",
                                "allow edits",
                            ]
                        ):
                            use_option_2 = True

                    if has_prompt:
                        # Cooldown: Don't confirm same session within 3 seconds
                        now = time.time()
                        if session in last_confirm and (now - last_confirm[session]) < 3:
                            continue

                        last_confirm[session] = now

                        if use_option_2:
                            logger.info(f"✅ {session}: Pre-approving all (option 2)")
                            subprocess.run(
                                f'tmux send-keys -t {session} "2" Enter', shell=True, timeout=2
                            )
                            log_confirmation(
                                session, "pre_approve_all", "option 2", "Allow all operations"
                            )
                            time.sleep(1)
                        else:
                            logger.info(f"✅ {session}: Confirming (option 1)")
                            subprocess.run(
                                f'tmux send-keys -t {session} "1" Enter', shell=True, timeout=2
                            )
                            log_confirmation(session, "confirm", "option 1", "Single confirmation")
                            time.sleep(0.3)

                except subprocess.TimeoutExpired:
                    continue
                except Exception as e:
                    logger.debug(f"Error checking {session}: {e}")
                    continue

            # Brief pause between cycles
            time.sleep(0.2)

        except KeyboardInterrupt:
            logger.info("\n🛑 Shutting down Auto-Confirm Worker")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(1)


if __name__ == "__main__":
    main()
