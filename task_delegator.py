#!/usr/bin/env python3
"""
Task Delegator - Interactive CLI for managing distributed agent work
"""

import json
import os
import select
import sqlite3
import subprocess
import sys
import termios
import time
import tty
from datetime import datetime
from pathlib import Path

DB_PATH = "/Users/jgirmay/Desktop/gitrepo/pyWork/architect/data/task_delegator.db"
COMMAND_LOG_DB = "/Users/jgirmay/Desktop/gitrepo/pyWork/architect/data/command_log.db"
RESPONSE_LOG_DB = "/Users/jgirmay/Desktop/gitrepo/pyWork/architect/data/response_log.db"
ENVS_PATH = Path(
    "/Users/jgirmay/Desktop/gitrepo/pyWork/basic_edu_apps_final/environments/feature_environments"
)
APPS_PATH = Path("/Users/jgirmay/Desktop/gitrepo/pyWork/architect/apps")
MAX_ENVS = 5

# ANSI escape codes
CLEAR = "\033[2J\033[H"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BLUE = "\033[34m"
CYAN = "\033[36m"
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"
BG_RED = "\033[41m"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            priority TEXT DEFAULT 'normal',
            status TEXT DEFAULT 'pending',
            assigned_env INTEGER,
            assigned_session TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS environments (
            env_id INTEGER PRIMARY KEY,
            status TEXT DEFAULT 'idle',
            current_task_id INTEGER,
            session_name TEXT,
            branch TEXT,
            last_activity TIMESTAMP
        )
    """
    )
    for i in range(1, MAX_ENVS + 1):
        conn.execute("INSERT OR IGNORE INTO environments (env_id) VALUES (?)", (i,))
    conn.commit()
    return conn


def init_command_log_db():
    """Initialize command logging database"""
    conn = sqlite3.connect(COMMAND_LOG_DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS command_log (
            id INTEGER PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            session_name TEXT,
            env_id INTEGER,
            app_name TEXT,
            command_type TEXT,
            command_summary TEXT,
            task_id INTEGER,
            success INTEGER DEFAULT 1,
            error_message TEXT
        )
    """
    )
    conn.commit()
    conn.close()


def init_response_log_db():
    """Initialize response type tracking database"""
    conn = sqlite3.connect(RESPONSE_LOG_DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS response_types (
            id INTEGER PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            session_name TEXT,
            env_id INTEGER,
            app_name TEXT,
            response_type TEXT,
            status_indicator TEXT,
            is_idle INTEGER,
            is_busy INTEGER,
            is_error INTEGER,
            has_prompt INTEGER
        )
    """
    )
    conn.commit()
    conn.close()


def log_command(
    session, env_id, app_name, command_type, command_summary, task_id=None, success=True, error=None
):
    """Log a command sent to a session"""
    try:
        conn = sqlite3.connect(COMMAND_LOG_DB)
        conn.execute(
            """
            INSERT INTO command_log
            (session_name, env_id, app_name, command_type, command_summary, task_id, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                session,
                env_id,
                app_name,
                command_type,
                command_summary[:200] if command_summary else None,
                task_id,
                1 if success else 0,
                error,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        pass  # Don't fail on logging errors


def log_response_type(
    session,
    env_id,
    app_name,
    response_type,
    status_indicator=None,
    is_idle=False,
    is_busy=False,
    is_error=False,
    has_prompt=False,
):
    """Log a response type from a session"""
    try:
        conn = sqlite3.connect(RESPONSE_LOG_DB)
        conn.execute(
            """
            INSERT INTO response_types
            (session_name, env_id, app_name, response_type, status_indicator, is_idle, is_busy, is_error, has_prompt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                session,
                env_id,
                app_name,
                response_type,
                status_indicator,
                1 if is_idle else 0,
                1 if is_busy else 0,
                1 if is_error else 0,
                1 if has_prompt else 0,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        pass  # Don't fail on logging errors


def detect_app_from_path(env_path):
    """Detect which app is being worked on based on environment path"""
    path_str = str(env_path).lower()
    if "edu" in path_str or "basic_edu" in path_str:
        return "edu_apps"
    elif "browser" in path_str:
        return "browser_agent"
    elif "architect" in path_str:
        return "architect"
    return "unknown"


def get_env_branch(env_id):
    """Get git branch for environment"""
    env_path = ENVS_PATH / f"env_{env_id}"
    if not env_path.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(env_path), "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip() or None
    except:
        return None


def get_tmux_sessions():
    """Get list of tmux sessions"""
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip().split("\n") if result.stdout.strip() else []
    except:
        return []


def is_session_idle(session, log_response=True, env_id=None):
    """Check if a tmux session is idle (waiting for input)"""
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", session, "-p"], capture_output=True, text=True, timeout=2
        )
        output = result.stdout.strip()
        last_lines = output.split("\n")[-5:] if output else []
        last_text = " ".join(last_lines).lower()

        # Idle indicators (Claude Code waiting for input)
        idle_patterns = [
            "> ",
            "$ ",
            "how can i help",
            "bypass permissions",
            "waiting",
            "ready",
            "idle",
        ]

        # Busy indicators (actively working)
        busy_patterns = [
            "thinking",
            "running",
            "analyzing",
            "reading",
            "writing",
            "searching",
            "compacting",
            "...",
            "⠋",
            "⠙",
            "⠹",
            "⠸",
        ]

        # Error indicators
        error_patterns = ["error", "failed", "exception", "traceback"]

        # Determine response type
        is_idle = False
        is_busy = False
        is_error = any(p in last_text for p in error_patterns)
        has_prompt = ">" in last_text or "$" in last_text
        status_indicator = None

        # Check for busy first
        for pattern in busy_patterns:
            if pattern in last_text:
                is_busy = True
                status_indicator = pattern
                break

        # Check for idle
        if not is_busy:
            for pattern in idle_patterns:
                if pattern in last_text:
                    is_idle = True
                    status_indicator = pattern
                    break

        # Default: assume idle if prompt visible
        if not is_idle and not is_busy:
            is_idle = has_prompt

        # Determine response type
        if is_busy:
            response_type = "busy"
        elif is_error:
            response_type = "error"
        elif is_idle:
            response_type = "idle"
        else:
            response_type = "unknown"

        # Log response type
        if log_response:
            log_response_type(
                session=session,
                env_id=env_id,
                app_name="unknown",
                response_type=response_type,
                status_indicator=status_indicator,
                is_idle=is_idle,
                is_busy=is_busy,
                is_error=is_error,
                has_prompt=has_prompt,
            )

        return is_idle
    except:
        return False


def get_assigned_sessions(conn):
    """Get list of sessions currently assigned to tasks"""
    cursor = conn.execute(
        "SELECT session_name FROM environments WHERE status='busy' AND session_name IS NOT NULL"
    )
    return [row[0] for row in cursor.fetchall()]


def get_available_sessions(conn):
    """Get worker sessions that are available (not assigned and idle)"""
    all_sessions = get_tmux_sessions()
    assigned = get_assigned_sessions(conn)

    # Filter to worker sessions
    workers = [s for s in all_sessions if "worker" in s.lower() or "fixer" in s.lower()]

    # Filter out already assigned
    available = [s for s in workers if s not in assigned]

    # Check which are actually idle
    idle_available = []
    for session in available:
        if is_session_idle(session):
            idle_available.append(session)

    return idle_available


def send_to_session(session, message, env_id=None, task_id=None):
    """Send command to tmux session with logging"""
    try:
        subprocess.run(
            ["tmux", "send-keys", "-t", session, message, "Enter"], capture_output=True, timeout=2
        )

        # Log the command
        app_name = detect_app_from_path(ENVS_PATH / f"env_{env_id}") if env_id else "unknown"
        log_command(
            session=session,
            env_id=env_id,
            app_name=app_name,
            command_type="task_assignment",
            command_summary=message,
            task_id=task_id,
            success=True,
        )
        return True
    except Exception as e:
        # Log failure
        log_command(
            session=session,
            env_id=env_id,
            app_name="unknown",
            command_type="task_assignment",
            command_summary=message,
            task_id=task_id,
            success=False,
            error=str(e),
        )
        return False


def get_checkout_status(conn):
    """Get full checkout status of sessions and environments"""
    status = {
        "environments": [],
        "sessions": {"all": [], "workers": [], "assigned": [], "available": [], "busy": []},
    }

    # Environment status
    for i in range(1, MAX_ENVS + 1):
        env = conn.execute(
            "SELECT status, current_task_id, session_name FROM environments WHERE env_id=?", (i,)
        ).fetchone()
        env_path = ENVS_PATH / f"env_{i}"
        has_code = env_path.exists() and len(list(env_path.iterdir())) > 2
        branch = get_env_branch(i) if has_code else None

        status["environments"].append(
            {
                "id": i,
                "status": env[0] if env else "unknown",
                "task_id": env[1] if env else None,
                "session": env[2] if env else None,
                "has_code": has_code,
                "branch": branch,
            }
        )

    # Session status
    all_sessions = get_tmux_sessions()
    assigned = get_assigned_sessions(conn)

    status["sessions"]["all"] = all_sessions
    status["sessions"]["workers"] = [
        s for s in all_sessions if "worker" in s.lower() or "fixer" in s.lower()
    ]
    status["sessions"]["assigned"] = assigned

    for session in status["sessions"]["workers"]:
        if session in assigned:
            continue
        if is_session_idle(session):
            status["sessions"]["available"].append(session)
        else:
            status["sessions"]["busy"].append(session)

    return status


def print_checkout_status(conn):
    """Print formatted checkout status"""
    status = get_checkout_status(conn)

    print(f"\n{BOLD}=== ENVIRONMENT CHECKOUT ==={RESET}")
    print(f"{'ENV':<6} {'STATUS':<8} {'TASK':<8} {'SESSION':<15} {'BRANCH':<25}")
    print("-" * 70)
    for e in status["environments"]:
        st = f"{GREEN}BUSY{RESET}" if e["status"] == "busy" else f"{DIM}idle{RESET}"
        task = f"#{e['task_id']}" if e["task_id"] else "-"
        session = e["session"] or "-"
        branch = (
            e["branch"][:22]
            if e["branch"]
            else (f"{RED}no code{RESET}" if not e["has_code"] else "-")
        )
        print(f"env_{e['id']:<2} {st:<17} {task:<8} {session:<15} {branch}")

    print(f"\n{BOLD}=== SESSION CHECKOUT ==={RESET}")
    print(f"  Workers:   {len(status['sessions']['workers'])}")
    print(
        f"  {GREEN}Available: {len(status['sessions']['available'])}{RESET} - {', '.join(status['sessions']['available'][:5]) or 'none'}"
    )
    print(
        f"  {YELLOW}Assigned:  {len(status['sessions']['assigned'])}{RESET} - {', '.join(status['sessions']['assigned'][:5]) or 'none'}"
    )
    print(
        f"  {RED}Busy:      {len(status['sessions']['busy'])}{RESET} - {', '.join(status['sessions']['busy'][:5]) or 'none'}"
    )


def draw_header():
    """Draw the header"""
    now = datetime.now().strftime("%H:%M:%S")
    print(f"{BG_BLUE}{BOLD}  TASK DELEGATOR  {RESET}  {DIM}{now}{RESET}")
    print(f"{DIM}{'─' * 60}{RESET}")


def draw_environments(conn):
    """Draw environment status"""
    print(f"\n{BOLD}ENVIRONMENTS{RESET}")

    envs = conn.execute(
        """
        SELECT env_id, status, current_task_id, session_name
        FROM environments ORDER BY env_id
    """
    ).fetchall()

    for e in envs:
        env_path = ENVS_PATH / f"env_{e[0]}"
        has_code = env_path.exists() and len(list(env_path.iterdir())) > 2
        branch = get_env_branch(e[0]) if has_code else None

        if e[1] == "busy":
            status_icon = f"{GREEN}●{RESET}"
            status_text = f"{GREEN}BUSY{RESET}"
        else:
            status_icon = f"{DIM}○{RESET}"
            status_text = f"{DIM}idle{RESET}"

        branch_text = f"{CYAN}{branch[:20]}{RESET}" if branch else f"{RED}no branch{RESET}"
        session_text = e[3] if e[3] else "-"
        task_text = f"T#{e[2]}" if e[2] else "-"

        print(
            f"  {status_icon} env_{e[0]}  {status_text:20}  {branch_text:25}  {session_text:15}  {task_text}"
        )


def draw_tasks(conn):
    """Draw task queue"""
    print(f"\n{BOLD}TASKS{RESET}")

    tasks = conn.execute(
        """
        SELECT id, description, status, assigned_env, priority
        FROM tasks WHERE status != 'completed'
        ORDER BY
            CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,
            id
        LIMIT 8
    """
    ).fetchall()

    if not tasks:
        print(f"  {DIM}No pending tasks{RESET}")
    else:
        for t in tasks:
            if t[2] == "running":
                status = f"{GREEN}▶ RUN{RESET}"
            elif t[2] == "pending":
                status = f"{YELLOW}○ PND{RESET}"
            else:
                status = f"{DIM}? {t[2][:3]}{RESET}"

            pri = f"{RED}!{RESET}" if t[4] == "high" else " "
            env = f"env_{t[3]}" if t[3] else "    -"
            desc = t[1][:35] + ".." if len(t[1]) > 37 else t[1]

            print(f"  {pri}#{t[0]:<3} {status}  {env:6}  {desc}")


def draw_sessions():
    """Draw active tmux sessions"""
    print(f"\n{BOLD}SESSIONS{RESET}")
    sessions = get_tmux_sessions()
    workers = [s for s in sessions if any(x in s.lower() for x in ["worker", "fixer", "edu"])]

    if workers:
        line = "  "
        for w in workers[:6]:
            line += f"{CYAN}{w[:12]}{RESET}  "
        print(line)
        if len(workers) > 6:
            print(f"  {DIM}+{len(workers)-6} more...{RESET}")
    else:
        print(f"  {DIM}No worker sessions{RESET}")


def draw_commands():
    """Draw command help"""
    print(f"\n{DIM}{'─' * 60}{RESET}")
    print(
        f"{BOLD}Commands:{RESET}  {CYAN}a{RESET}dd  {CYAN}s{RESET}tart  {CYAN}c{RESET}omplete  {CYAN}d{RESET}elegate  {CYAN}r{RESET}efresh  {CYAN}q{RESET}uit"
    )


def draw_input_line(prompt="", input_text=""):
    """Draw input line"""
    print(f"\n{BG_BLUE} > {RESET} {prompt}{input_text}", end="", flush=True)


def get_char():
    """Get single character from stdin (non-blocking)"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        if select.select([sys.stdin], [], [], 0.5)[0]:
            return sys.stdin.read(1)
        return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def get_input(prompt):
    """Get full line input"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    print(f"\n{BG_BLUE} > {RESET} {prompt}", end="", flush=True)
    try:
        return input()
    except:
        return ""


def add_task(conn):
    """Add a new task"""
    desc = get_input("Task description: ")
    if not desc:
        return

    pri = get_input("Priority (h)igh/(n)ormal: ").lower()
    priority = "high" if pri.startswith("h") else "normal"

    cur = conn.execute("INSERT INTO tasks (description, priority) VALUES (?, ?)", (desc, priority))
    conn.commit()
    return cur.lastrowid


def start_task(conn):
    """Assign pending task to idle environment and available session"""
    # Find pending task
    task = conn.execute(
        """
        SELECT id, description FROM tasks
        WHERE status = 'pending'
        ORDER BY CASE priority WHEN 'high' THEN 0 ELSE 1 END, id
        LIMIT 1
    """
    ).fetchone()

    if not task:
        return "No pending tasks"

    # Get available sessions (not assigned and idle)
    available_sessions = get_available_sessions(conn)
    if not available_sessions:
        return "No available sessions (all busy or assigned)"

    # Find idle environment with code
    for i in range(1, MAX_ENVS + 1):
        env = conn.execute("SELECT status FROM environments WHERE env_id = ?", (i,)).fetchone()

        env_path = ENVS_PATH / f"env_{i}"
        has_code = env_path.exists() and len(list(env_path.iterdir())) > 2

        if env and env[0] == "idle" and has_code:
            # Use first available session
            session = available_sessions[0]

            conn.execute(
                """
                UPDATE tasks SET status='running', assigned_env=?,
                assigned_session=?, started_at=? WHERE id=?
            """,
                (i, session, datetime.now().isoformat(), task[0]),
            )

            conn.execute(
                """
                UPDATE environments SET status='busy', current_task_id=?,
                session_name=?, last_activity=? WHERE env_id=?
            """,
                (task[0], session, datetime.now().isoformat(), i),
            )

            conn.commit()

            # Send instruction to session with env path
            env_path_str = str(ENVS_PATH / f"env_{i}")
            send_to_session(
                session,
                f"TASK: {task[1][:60]}. WORK ONLY IN: {env_path_str}. Do NOT modify files outside this directory.",
                env_id=i,
                task_id=task[0],
            )

            return f"Task #{task[0]} → env_{i} ({session})"

    return "No idle environment with code"


def complete_task(conn):
    """Mark a task as complete"""
    task_id = get_input("Task ID to complete: ")
    if not task_id.isdigit():
        return "Invalid ID"

    task = conn.execute("SELECT assigned_env FROM tasks WHERE id = ?", (int(task_id),)).fetchone()

    if not task:
        return "Task not found"

    conn.execute(
        """
        UPDATE tasks SET status='completed', completed_at=? WHERE id=?
    """,
        (datetime.now().isoformat(), int(task_id)),
    )

    if task[0]:
        conn.execute(
            """
            UPDATE environments SET status='idle', current_task_id=NULL,
            session_name=NULL WHERE env_id=?
        """,
            (task[0],),
        )

    conn.commit()
    return f"Task #{task_id} completed"


def delegate_task(conn):
    """Manually delegate task to specific env/session"""
    task_id = get_input("Task ID: ")
    if not task_id.isdigit():
        return "Invalid ID"

    env_id = get_input("Environment (1-5): ")
    if not env_id.isdigit() or int(env_id) < 1 or int(env_id) > 5:
        return "Invalid env"

    session = get_input("Session name (or Enter for none): ")

    task = conn.execute("SELECT description FROM tasks WHERE id=?", (int(task_id),)).fetchone()
    if not task:
        return "Task not found"

    conn.execute(
        """
        UPDATE tasks SET status='running', assigned_env=?,
        assigned_session=?, started_at=? WHERE id=?
    """,
        (int(env_id), session or None, datetime.now().isoformat(), int(task_id)),
    )

    conn.execute(
        """
        UPDATE environments SET status='busy', current_task_id=?,
        session_name=?, last_activity=? WHERE env_id=?
    """,
        (int(task_id), session or None, datetime.now().isoformat(), int(env_id)),
    )

    conn.commit()

    if session:
        env_path = str(ENVS_PATH / f"env_{env_id}")
        send_to_session(
            session,
            f"Work ONLY in {env_path}. Task: {task[0][:50]}",
            env_id=int(env_id),
            task_id=int(task_id),
        )

    return f"Task #{task_id} → env_{env_id}"


def main_loop():
    """Main interactive loop"""
    conn = init_db()
    init_command_log_db()
    init_response_log_db()
    message = ""

    while True:
        # Draw screen
        print(CLEAR, end="")
        draw_header()
        draw_environments(conn)
        draw_tasks(conn)
        draw_sessions()
        draw_commands()

        if message:
            print(f"\n{GREEN}✓ {message}{RESET}")
            message = ""

        draw_input_line()

        # Get input
        ch = get_char()

        if ch is None:
            continue
        elif ch == "q":
            print(CLEAR)
            print("Goodbye!")
            break
        elif ch == "a":
            task_id = add_task(conn)
            if task_id:
                message = f"Added task #{task_id}"
        elif ch == "s":
            message = start_task(conn)
        elif ch == "c":
            message = complete_task(conn)
        elif ch == "d":
            message = delegate_task(conn)
        elif ch == "r":
            message = "Refreshed"
        # else: just refresh


def cli_mode():
    """Original CLI mode for scripting"""
    if len(sys.argv) < 2:
        return False

    cmd = sys.argv[1]
    conn = init_db()
    init_command_log_db()
    init_response_log_db()

    if cmd == "add" and len(sys.argv) >= 3:
        desc = sys.argv[2]
        priority = "high" if "--priority" in sys.argv and "high" in sys.argv else "normal"
        cur = conn.execute(
            "INSERT INTO tasks (description, priority) VALUES (?, ?)", (desc, priority)
        )
        conn.commit()
        print(f"Added task #{cur.lastrowid}")
        return True

    elif cmd == "status":
        print("\n=== ENVIRONMENT STATUS ===")
        for i in range(1, MAX_ENVS + 1):
            env = conn.execute(
                "SELECT status, current_task_id, session_name FROM environments WHERE env_id=?",
                (i,),
            ).fetchone()
            env_path = ENVS_PATH / f"env_{i}"
            has_code = "✓" if env_path.exists() and len(list(env_path.iterdir())) > 2 else "✗"
            task = f"Task #{env[1]}" if env[1] else "None"
            print(
                f"  env_{i}: {env[0]:<8} | Path: {has_code} | Task: {task} | Session: {env[2] or '-'}"
            )

        pending = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='pending'").fetchone()[0]
        running = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='running'").fetchone()[0]
        print(f"\n=== TASK QUEUE ===\n  Pending: {pending} | Running: {running}")
        return True

    elif cmd == "checkout":
        print_checkout_status(conn)
        return True

    elif cmd == "available":
        available = get_available_sessions(conn)
        if available:
            print(f"Available sessions: {', '.join(available)}")
        else:
            print("No available sessions")
        return True

    elif cmd == "start":
        # Auto-assign next pending task to available env/session
        result = start_task(conn)
        print(result)
        return True

    elif cmd == "list":
        tasks = conn.execute(
            "SELECT id, description, status, assigned_env FROM tasks ORDER BY id"
        ).fetchall()
        for t in tasks:
            print(f"#{t[0]} [{t[2]}] env_{t[3] or '-'}: {t[1][:50]}")
        return True

    elif cmd == "complete" and len(sys.argv) >= 3:
        task_id = int(sys.argv[2])
        task = conn.execute("SELECT assigned_env FROM tasks WHERE id=?", (task_id,)).fetchone()
        if task:
            conn.execute(
                "UPDATE tasks SET status='completed', completed_at=? WHERE id=?",
                (datetime.now().isoformat(), task_id),
            )
            if task[0]:
                conn.execute(
                    "UPDATE environments SET status='idle', current_task_id=NULL WHERE env_id=?",
                    (task[0],),
                )
            conn.commit()
            print(f"Completed task #{task_id}")
        return True

    elif cmd == "assign" and len(sys.argv) >= 4:
        task_id, env_id = int(sys.argv[2]), int(sys.argv[3])
        session = sys.argv[4] if len(sys.argv) > 4 else None

        # Get task description
        task = conn.execute("SELECT description FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not task:
            print(f"Task #{task_id} not found")
            return True

        conn.execute(
            "UPDATE tasks SET status='running', assigned_env=?, assigned_session=? WHERE id=?",
            (env_id, session, task_id),
        )
        conn.execute(
            "UPDATE environments SET status='busy', current_task_id=?, session_name=? WHERE env_id=?",
            (task_id, session, env_id),
        )
        conn.commit()

        # Send instruction to session with env path
        if session:
            env_path = str(ENVS_PATH / f"env_{env_id}")
            send_to_session(
                session,
                f"TASK: {task[0][:60]}. WORK ONLY IN: {env_path}. Do NOT modify files outside this directory.",
                env_id=env_id,
                task_id=task_id,
            )

        print(
            f"Assigned task #{task_id} to env_{env_id}"
            + (f" (sent to {session})" if session else "")
        )
        return True

    elif cmd == "logs":
        # Show recent command logs
        log_type = sys.argv[2] if len(sys.argv) > 2 else "commands"
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 20

        if log_type in ["commands", "cmd"]:
            log_conn = sqlite3.connect(COMMAND_LOG_DB)
            logs = log_conn.execute(
                """
                SELECT timestamp, session_name, env_id, app_name, command_type, command_summary, success
                FROM command_log ORDER BY id DESC LIMIT ?
            """,
                (limit,),
            ).fetchall()
            log_conn.close()

            print(f"\n{BOLD}=== COMMAND LOG (last {limit}) ==={RESET}")
            print(
                f"{'TIME':<20} {'SESSION':<15} {'ENV':<6} {'APP':<12} {'TYPE':<15} {'OK':<4} SUMMARY"
            )
            print("-" * 100)
            for log in logs:
                ts = log[0][:19] if log[0] else "-"
                sess = (log[1] or "-")[:14]
                env = f"env_{log[2]}" if log[2] else "-"
                app = (log[3] or "-")[:11]
                cmd_type = (log[4] or "-")[:14]
                ok = "✓" if log[5] else "✗"
                summary = (log[6] or "-")[:40]
                print(f"{ts:<20} {sess:<15} {env:<6} {app:<12} {cmd_type:<15} {ok:<4} {summary}")

        elif log_type in ["responses", "resp"]:
            log_conn = sqlite3.connect(RESPONSE_LOG_DB)
            logs = log_conn.execute(
                """
                SELECT timestamp, session_name, env_id, response_type, status_indicator, is_idle, is_busy, is_error
                FROM response_types ORDER BY id DESC LIMIT ?
            """,
                (limit,),
            ).fetchall()
            log_conn.close()

            print(f"\n{BOLD}=== RESPONSE LOG (last {limit}) ==={RESET}")
            print(
                f"{'TIME':<20} {'SESSION':<15} {'ENV':<6} {'TYPE':<10} {'STATUS':<15} {'IDLE':<6} {'BUSY':<6} {'ERR':<4}"
            )
            print("-" * 90)
            for log in logs:
                ts = log[0][:19] if log[0] else "-"
                sess = (log[1] or "-")[:14]
                env = f"env_{log[2]}" if log[2] else "-"
                rtype = (log[3] or "-")[:9]
                status = (log[4] or "-")[:14]
                idle = "Y" if log[5] else "N"
                busy = "Y" if log[6] else "N"
                err = "Y" if log[7] else "N"
                print(
                    f"{ts:<20} {sess:<15} {env:<6} {rtype:<10} {status:<15} {idle:<6} {busy:<6} {err:<4}"
                )

        else:
            print("Usage: ./task_delegator.py logs [commands|responses] [limit]")
        return True

    return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if not cli_mode():
            print("Usage: ./task_delegator.py [command] or run without args for interactive mode")
    else:
        try:
            main_loop()
        except KeyboardInterrupt:
            print(CLEAR)
            print("Goodbye!")
