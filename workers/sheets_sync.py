#!/usr/bin/env python3
"""
Google Sheets Two-Way Sync Worker

Full bidirectional sync between Architect Dashboard and Google Sheets:
- Bugs: Add/edit in Sheet → syncs to database
- Tasks: Priority changes in Sheet → updates queue
- Progress: Worker sessions update Sheet with status
- Documentation: Project docs synced to Sheet

Usage:
    python3 sheets_sync.py              # One-time sync
    python3 sheets_sync.py --daemon     # Continuous sync every 2 minutes
    python3 sheets_sync.py --status     # Check status
    python3 sheets_sync.py --stop       # Stop daemon
"""

import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration
SPREADSHEET_ID = "12i2uO6-41uZdHl_a9BbhBHhR1qbNlAqOgH-CWQBz7rA"
ARCHITECTURE_DOC_ID = None  # Will be auto-created/discovered
SYNC_INTERVAL = 120  # 2 minutes for more responsive updates
CREDENTIALS_PATH = Path.home() / ".config" / "gspread" / "service_account.json"
DB_PATH = Path(__file__).parent.parent / "data" / "prod" / "architect.db"
LOG_FILE = Path("/tmp/sheets_sync.log")
PID_FILE = Path("/tmp/sheets_sync.pid")
ARCHITECTURE_DOC_TITLE = "Architect Dashboard - Architecture Guide"


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except:
        pass


def get_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def get_sheets_client():
    import gspread
    from google.oauth2.service_account import Credentials

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


# =============================================================================
# DATA COLLECTION
# =============================================================================


def get_tmux_sessions():
    """Get all tmux sessions with current activity."""
    try:
        result = subprocess.run(
            [
                "tmux",
                "list-sessions",
                "-F",
                "#{session_name}\t#{session_created}\t#{session_attached}\t#{session_windows}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []

        sessions = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 4:
                name = parts[0]
                # Get last few lines of session output
                try:
                    capture = subprocess.run(
                        ["tmux", "capture-pane", "-t", name, "-p", "-S", "-5"],
                        capture_output=True,
                        text=True,
                        timeout=3,
                    )
                    last_output = (
                        capture.stdout.strip().split("\n")[-1][:100]
                        if capture.returncode == 0
                        else ""
                    )
                except:
                    last_output = ""

                sessions.append(
                    {
                        "name": name,
                        "created": datetime.fromtimestamp(int(parts[1])).strftime("%Y-%m-%d %H:%M"),
                        "attached": "Yes" if parts[2] == "1" else "No",
                        "windows": parts[3],
                        "last_output": last_output,
                    }
                )
        return sessions
    except Exception as e:
        log(f"Error getting tmux sessions: {e}")
        return []


def get_bugs():
    """Get all bugs from database."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT b.id, b.title, b.description, b.severity, b.status,
                   b.assigned_to, b.tmux_session, b.created_at, b.updated_at,
                   p.name as project_name
            FROM bugs b
            LEFT JOIN projects p ON b.project_id = p.id
            ORDER BY b.severity DESC, b.created_at DESC
            LIMIT 100
        """
        )
        bugs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return bugs
    except Exception as e:
        log(f"Error getting bugs: {e}")
        return []


def get_features():
    """Get all features from database."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT f.id, f.name as title, f.description, f.status, f.priority,
                   f.assigned_to, f.tmux_session, f.created_at, f.updated_at,
                   p.name as project_name, m.name as milestone_name,
                   p.id as project_id, m.id as milestone_id
            FROM features f
            LEFT JOIN projects p ON f.project_id = p.id
            LEFT JOIN milestones m ON f.milestone_id = m.id
            ORDER BY p.name, m.name, f.priority DESC, f.name
        """
        )
        features = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return features
    except Exception as e:
        log(f"Error getting features: {e}")
        return []


def get_features_hierarchy():
    """Get features organized by project and milestone hierarchy."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Get all projects
        cursor.execute(
            """
            SELECT id, name, description, status
            FROM projects
            WHERE status = 'active'
            ORDER BY name
        """
        )
        projects = {row["id"]: dict(row) for row in cursor.fetchall()}

        # Get all milestones
        cursor.execute(
            """
            SELECT id, name, project_id, status, target_date
            FROM milestones
            ORDER BY project_id, target_date, name
        """
        )
        milestones = {}
        for row in cursor.fetchall():
            m = dict(row)
            if m["project_id"] not in milestones:
                milestones[m["project_id"]] = []
            milestones[m["project_id"]].append(m)

        # Get all features
        cursor.execute(
            """
            SELECT f.id, f.name as title, f.description, f.status, f.priority,
                   f.assigned_to, f.tmux_session, f.project_id, f.milestone_id
            FROM features f
            ORDER BY f.priority DESC, f.name
        """
        )
        features = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return {"projects": projects, "milestones": milestones, "features": features}
    except Exception as e:
        log(f"Error getting features hierarchy: {e}")
        return {"projects": {}, "milestones": {}, "features": []}


def get_tasks():
    """Get task queue."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, task_type, task_data, priority, status,
                   assigned_worker, created_at, started_at, error_message
            FROM task_queue
            WHERE status IN ('pending', 'in_progress', 'running')
            ORDER BY priority DESC, created_at ASC
            LIMIT 50
        """
        )
        tasks = []
        for row in cursor.fetchall():
            task = dict(row)
            # Parse task_data JSON
            try:
                data = json.loads(task["task_data"] or "{}")
                task["title"] = data.get("title", "")[:50]
                task["description"] = data.get("description", "")[:100]
            except:
                task["title"] = ""
                task["description"] = ""
            tasks.append(task)
        conn.close()
        return tasks
    except Exception as e:
        log(f"Error getting tasks: {e}")
        return []


def get_projects():
    """Get all projects."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, description, status, source_path, created_at
            FROM projects
            WHERE status = 'active'
            ORDER BY name
        """
        )
        projects = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return projects
    except Exception as e:
        log(f"Error getting projects: {e}")
        return []


def get_errors():
    """Get open errors."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, error_type, message, source, status, occurrence_count,
                   first_seen, last_seen
            FROM errors
            WHERE status = 'open'
            ORDER BY occurrence_count DESC, last_seen DESC
            LIMIT 50
        """
        )
        errors = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return errors
    except Exception as e:
        log(f"Error getting errors: {e}")
        return []


def get_worker_progress():
    """Get progress from auto-confirm database."""
    try:
        confirm_db = Path("/tmp/auto_confirm.db")
        if not confirm_db.exists():
            return []

        conn = sqlite3.connect(str(confirm_db), timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT session_name, total_confirmations, last_confirmation
            FROM session_stats
            ORDER BY last_confirmation DESC
        """
        )
        progress = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return progress
    except Exception as e:
        log(f"Error getting worker progress: {e}")
        return []


# =============================================================================
# SHEET SYNC (TO GOOGLE)
# =============================================================================


def sync_sessions_to_sheet(spreadsheet):
    """Sync tmux sessions to Sessions sheet."""
    ws = get_or_create_worksheet(spreadsheet, "Sessions")
    sessions = get_tmux_sessions()

    ws.clear()
    headers = ["Session", "Status", "Windows", "Created", "Last Activity", "Last Sync"]
    ws.update(values=[headers], range_name="A1")
    ws.format(
        "A1:F1",
        {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}},
    )

    if sessions:
        rows = [
            [
                s["name"],
                "Attached" if s["attached"] == "Yes" else "Detached",
                s["windows"],
                s["created"],
                s["last_output"][:50],
                datetime.now().strftime("%H:%M:%S"),
            ]
            for s in sessions
        ]
        ws.update(values=rows, range_name="A2")

    log(f"Synced {len(sessions)} sessions")


def sync_bugs_to_sheet(spreadsheet):
    """Sync bugs to Bugs sheet (two-way sync enabled)."""
    ws = get_or_create_worksheet(spreadsheet, "Bugs")
    bugs = get_bugs()

    ws.clear()
    headers = [
        "ID",
        "Title",
        "Severity",
        "Status",
        "Project",
        "Assigned To",
        "Session",
        "Description",
        "Created",
    ]
    ws.update(values=[headers], range_name="A1")
    ws.format(
        "A1:I1",
        {"textFormat": {"bold": True}, "backgroundColor": {"red": 1, "green": 0.8, "blue": 0.8}},
    )

    if bugs:
        rows = [
            [
                b["id"],
                b["title"] or "",
                b["severity"] or "medium",
                b["status"] or "open",
                b["project_name"] or "",
                b["assigned_to"] or "",
                b["tmux_session"] or "",
                (b["description"] or "")[:100],
                b["created_at"] or "",
            ]
            for b in bugs
        ]
        ws.update(values=rows, range_name="A2")

    # Add "NEW BUG" row template at the end
    next_row = len(bugs) + 3
    ws.update(
        values=[["NEW", "(Enter title here)", "medium", "open", "", "", "", "(description)", ""]],
        range_name=f"A{next_row}",
    )
    ws.format(f"A{next_row}:I{next_row}", {"backgroundColor": {"red": 1, "green": 1, "blue": 0.8}})

    log(f"Synced {len(bugs)} bugs")


def sync_features_to_sheet(spreadsheet):
    """Sync features to Features sheet with project/milestone hierarchy."""
    ws = get_or_create_worksheet(spreadsheet, "Features")
    hierarchy = get_features_hierarchy()

    ws.clear()
    headers = ["Level", "ID", "Name", "Status", "Priority", "Assigned To", "Session", "Description"]
    ws.update(values=[headers], range_name="A1")
    ws.format(
        "A1:H1",
        {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.8, "green": 0.9, "blue": 0.8}},
    )

    rows = []
    project_rows = []  # Track rows to format as project headers
    milestone_rows = []  # Track rows to format as milestone headers

    projects = hierarchy["projects"]
    milestones = hierarchy["milestones"]
    features = hierarchy["features"]

    # Group features by project and milestone
    features_by_project = {}
    features_no_project = []

    for f in features:
        if f["project_id"]:
            if f["project_id"] not in features_by_project:
                features_by_project[f["project_id"]] = {"no_milestone": [], "by_milestone": {}}
            if f["milestone_id"]:
                if f["milestone_id"] not in features_by_project[f["project_id"]]["by_milestone"]:
                    features_by_project[f["project_id"]]["by_milestone"][f["milestone_id"]] = []
                features_by_project[f["project_id"]]["by_milestone"][f["milestone_id"]].append(f)
            else:
                features_by_project[f["project_id"]]["no_milestone"].append(f)
        else:
            features_no_project.append(f)

    row_num = 2  # Start after header

    # Add features organized by project and milestone
    for project_id, project in sorted(projects.items(), key=lambda x: x[1]["name"]):
        if project_id not in features_by_project:
            continue

        # Project header row
        rows.append(
            [
                "PROJECT",
                "",
                f"📁 {project['name']}",
                project["status"],
                "",
                "",
                "",
                project["description"] or "",
            ]
        )
        project_rows.append(row_num)
        row_num += 1

        project_features = features_by_project[project_id]

        # Add milestones for this project
        for milestone in milestones.get(project_id, []):
            mid = milestone["id"]
            if mid in project_features["by_milestone"]:
                # Milestone header row
                target = milestone.get("target_date") or ""
                rows.append(
                    [
                        "  MILESTONE",
                        "",
                        f"  📌 {milestone['name']}",
                        milestone["status"],
                        "",
                        "",
                        "",
                        f"Target: {target}",
                    ]
                )
                milestone_rows.append(row_num)
                row_num += 1

                # Features under this milestone
                for f in project_features["by_milestone"][mid]:
                    rows.append(
                        [
                            "    Feature",
                            f["id"],
                            f"    {f['title'] or ''}",
                            f["status"] or "planned",
                            f["priority"] or 0,
                            f["assigned_to"] or "",
                            f["tmux_session"] or "",
                            (f["description"] or "")[:80],
                        ]
                    )
                    row_num += 1

        # Features with no milestone
        if project_features["no_milestone"]:
            rows.append(["  NO MILESTONE", "", "  (Unassigned to milestone)", "", "", "", "", ""])
            row_num += 1
            for f in project_features["no_milestone"]:
                rows.append(
                    [
                        "    Feature",
                        f["id"],
                        f"    {f['title'] or ''}",
                        f["status"] or "planned",
                        f["priority"] or 0,
                        f["assigned_to"] or "",
                        f["tmux_session"] or "",
                        (f["description"] or "")[:80],
                    ]
                )
                row_num += 1

        # Blank row between projects
        rows.append(["", "", "", "", "", "", "", ""])
        row_num += 1

    # Features with no project
    if features_no_project:
        rows.append(["NO PROJECT", "", "📂 Unassigned Features", "", "", "", "", ""])
        project_rows.append(row_num)
        row_num += 1
        for f in features_no_project:
            rows.append(
                [
                    "  Feature",
                    f["id"],
                    f"  {f['title'] or ''}",
                    f["status"] or "planned",
                    f["priority"] or 0,
                    f["assigned_to"] or "",
                    f["tmux_session"] or "",
                    (f["description"] or "")[:80],
                ]
            )
            row_num += 1

    if rows:
        ws.update(values=rows, range_name="A2")

        # Format project rows with bold and background color
        for r in project_rows:
            try:
                ws.format(
                    f"A{r}:H{r}",
                    {
                        "textFormat": {"bold": True},
                        "backgroundColor": {"red": 0.9, "green": 0.95, "blue": 1},
                    },
                )
            except:
                pass

        # Format milestone rows
        for r in milestone_rows:
            try:
                ws.format(
                    f"A{r}:H{r}",
                    {
                        "textFormat": {"bold": True},
                        "backgroundColor": {"red": 0.95, "green": 1, "blue": 0.95},
                    },
                )
            except:
                pass

    log(f"Synced {len(features)} features in hierarchy")


def sync_tasks_to_sheet(spreadsheet):
    """Sync task queue to Tasks sheet."""
    ws = get_or_create_worksheet(spreadsheet, "Tasks")
    tasks = get_tasks()

    ws.clear()
    headers = [
        "ID",
        "Type",
        "Title",
        "Priority",
        "Status",
        "Worker",
        "Description",
        "Created",
        "Started",
    ]
    ws.update(values=[headers], range_name="A1")
    ws.format(
        "A1:I1",
        {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.8, "green": 0.8, "blue": 1}},
    )

    if tasks:
        rows = [
            [
                t["id"],
                t["task_type"],
                t["title"],
                t["priority"] or 0,
                t["status"],
                t["assigned_worker"] or "",
                t["description"],
                t["created_at"] or "",
                t["started_at"] or "",
            ]
            for t in tasks
        ]
        ws.update(values=rows, range_name="A2")

    log(f"Synced {len(tasks)} tasks")


def sync_errors_to_sheet(spreadsheet):
    """Sync errors to Errors sheet."""
    ws = get_or_create_worksheet(spreadsheet, "Errors")
    errors = get_errors()

    ws.clear()
    headers = ["ID", "Type", "Message", "Source", "Count", "First Seen", "Last Seen", "Status"]
    ws.update(values=[headers], range_name="A1")
    ws.format(
        "A1:H1",
        {"textFormat": {"bold": True}, "backgroundColor": {"red": 1, "green": 0.7, "blue": 0.7}},
    )

    if errors:
        rows = [
            [
                e["id"],
                e["error_type"] or "",
                (e["message"] or "")[:80],
                e["source"] or "",
                e["occurrence_count"] or 1,
                e["first_seen"] or "",
                e["last_seen"] or "",
                e["status"] or "open",
            ]
            for e in errors
        ]
        ws.update(values=rows, range_name="A2")

    log(f"Synced {len(errors)} errors")


def sync_progress_to_sheet(spreadsheet):
    """Sync worker progress to Progress sheet."""
    ws = get_or_create_worksheet(spreadsheet, "Progress")
    progress = get_worker_progress()
    sessions = get_tmux_sessions()

    ws.clear()
    headers = ["Session", "Confirmations", "Last Activity", "Current Status", "Last Output"]
    ws.update(values=[headers], range_name="A1")
    ws.format(
        "A1:E1",
        {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.8, "green": 1, "blue": 0.8}},
    )

    # Merge progress with session data
    session_map = {s["name"]: s for s in sessions}
    rows = []
    for p in progress:
        session = session_map.get(p["session_name"], {})
        rows.append(
            [
                p["session_name"],
                p["total_confirmations"] or 0,
                p["last_confirmation"] or "",
                "Active" if session.get("attached") == "Yes" else "Background",
                session.get("last_output", "")[:60],
            ]
        )

    if rows:
        ws.update(values=rows, range_name="A2")

    log(f"Synced {len(rows)} progress entries")


def sync_summary_to_sheet(spreadsheet):
    """Sync dashboard summary to Summary sheet."""
    ws = get_or_create_worksheet(spreadsheet, "Summary")

    ws.clear()

    rows = [
        ["ARCHITECT DASHBOARD SUMMARY"],
        [f'Last Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'],
        [""],
    ]

    try:
        conn = get_db()
        cursor = conn.cursor()

        # ===== QUICK STATS =====
        cursor.execute("SELECT COUNT(*) FROM projects WHERE status='active'")
        project_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tmux_sessions")
        session_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM bugs WHERE status NOT IN ('resolved', 'closed')")
        open_bugs = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM features WHERE status='in_progress'")
        active_features = cursor.fetchone()[0]

        rows.extend(
            [
                ["QUICK STATS", "", ""],
                ["Projects", project_count, ""],
                ["tmux Sessions", session_count, ""],
                ["Open Bugs", open_bugs, ""],
                ["Active Features", active_features, ""],
                [""],
            ]
        )

        # ===== ENVIRONMENTS =====
        rows.append(["ENVIRONMENTS", "Branch", "Changes"])

        env_data = get_environment_data()
        if env_data and "environments" in env_data:
            envs = env_data["environments"]
            if "architect" in envs:
                rows.append(
                    [
                        "Architect",
                        envs["architect"].get("branch", "")[:30],
                        envs["architect"].get("uncommitted_changes", 0),
                    ]
                )
            if "edu_apps" in envs and "main" in envs["edu_apps"]:
                rows.append(
                    [
                        "Edu Apps",
                        envs["edu_apps"]["main"].get("branch", "")[:30],
                        envs["edu_apps"]["main"].get("uncommitted_changes", 0),
                    ]
                )
        rows.append([""])

        # ===== SERVICES =====
        rows.append(["SERVICES", "Status", "Port"])
        if env_data and "services" in env_data:
            for svc_name, svc_data in list(env_data["services"].items())[:8]:
                status = "ONLINE" if svc_data.get("running") else "offline"
                rows.append([svc_name, status, svc_data.get("port", "")])
        rows.append([""])

        # ===== BUGS =====
        rows.append(["BUGS", "Count", ""])
        cursor.execute("SELECT status, COUNT(*) FROM bugs GROUP BY status")
        for status, count in cursor.fetchall():
            rows.append([status, count, ""])
        rows.append([""])

        # ===== FEATURES =====
        rows.append(["FEATURES", "Count", ""])
        cursor.execute("SELECT status, COUNT(*) FROM features GROUP BY status")
        for status, count in cursor.fetchall():
            rows.append([status, count, ""])
        rows.append([""])

        # ===== TASK QUEUE =====
        rows.append(["TASK QUEUE", "Count", ""])
        cursor.execute("SELECT status, COUNT(*) FROM task_queue GROUP BY status")
        for status, count in cursor.fetchall():
            rows.append([status, count, ""])
        rows.append([""])

        # ===== DEV TASKS (from sheet) =====
        rows.append(["DEV TASKS", "Count", ""])
        try:
            dev_ws = spreadsheet.worksheet("DevTasks")
            dev_rows = dev_ws.get_all_values()
            dev_statuses = {}
            for row in dev_rows[1:]:
                if len(row) > 4:
                    status = row[4].lower() if row[4] else "pending"
                    dev_statuses[status] = dev_statuses.get(status, 0) + 1
            for status, count in dev_statuses.items():
                rows.append([status, count, ""])
        except:
            rows.append(["(no data)", "", ""])
        rows.append([""])

        # ===== TESTING =====
        rows.append(["TESTING", "Count", ""])
        try:
            test_ws = spreadsheet.worksheet("Testing")
            test_rows = test_ws.get_all_values()
            test_statuses = {}
            for row in test_rows[1:]:
                if len(row) > 4:
                    status = row[4].lower() if row[4] else "pending"
                    test_statuses[status] = test_statuses.get(status, 0) + 1
            for status, count in test_statuses.items():
                rows.append([status, count, ""])
        except:
            rows.append(["(no data)", "", ""])
        rows.append([""])

        # ===== WORKERS =====
        rows.append(["WORKERS", "Status", ""])
        cursor.execute(
            """
            SELECT session_name, attached
            FROM tmux_sessions
            WHERE session_name LIKE 'task_worker%'
            ORDER BY session_name
        """
        )
        for session in cursor.fetchall():
            status = "active" if session["attached"] else "idle"
            rows.append([session["session_name"], status, ""])

        conn.close()

    except Exception as e:
        rows.append([f"Error: {e}", "", ""])
        log(f"Error syncing summary: {e}")

    # Write all data at once
    ws.update(values=rows, range_name="A1")

    # Format header
    ws.format("A1", {"textFormat": {"bold": True, "fontSize": 14}})

    # Format section headers
    section_rows = [4, 10, 14, 24, 30, 36, 42, 48, 54]
    for r in section_rows:
        if r <= len(rows):
            try:
                ws.format(
                    f"A{r}",
                    {
                        "textFormat": {"bold": True},
                        "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.95},
                    },
                )
            except:
                pass

    log("Synced summary")


# =============================================================================
# SHEET SYNC (FROM GOOGLE - Two-way)
# =============================================================================


def sync_bugs_from_sheet(spreadsheet):
    """Read bugs from sheet and sync new/updated ones to database."""
    try:
        ws = spreadsheet.worksheet("Bugs")
        rows = ws.get_all_values()

        if len(rows) < 2:
            return

        headers = rows[0]
        conn = get_db()
        cursor = conn.cursor()

        new_bugs = 0
        updated_bugs = 0

        for row in rows[1:]:
            if len(row) < 4:
                continue

            bug_id = row[0] if row[0] else None
            title = row[1] if len(row) > 1 else ""
            severity = row[2] if len(row) > 2 else "medium"
            status = row[3] if len(row) > 3 else "open"
            # Project is col 4, assigned_to is col 5, session is col 6, description is col 7
            assigned_to = row[5] if len(row) > 5 and row[5] else None
            tmux_session = row[6] if len(row) > 6 and row[6] else None
            description = row[7] if len(row) > 7 else ""

            # Skip empty or template rows
            if not title or title == "(Enter title here)":
                continue

            if bug_id == "NEW" or not bug_id:
                # Insert new bug (need project_id, default to 1)
                cursor.execute(
                    """
                    INSERT INTO bugs (project_id, title, description, severity, status, assigned_to, tmux_session)
                    VALUES (1, ?, ?, ?, ?, ?, ?)
                """,
                    (title, description, severity, status, assigned_to, tmux_session),
                )
                new_bugs += 1
            else:
                # Update existing bug
                cursor.execute(
                    """
                    UPDATE bugs SET title=?, description=?, severity=?, status=?,
                                    assigned_to=?, tmux_session=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                """,
                    (title, description, severity, status, assigned_to, tmux_session, bug_id),
                )
                if cursor.rowcount > 0:
                    updated_bugs += 1

        conn.commit()
        conn.close()

        if new_bugs > 0 or updated_bugs > 0:
            log(f"From Sheet: {new_bugs} new bugs, {updated_bugs} updated")

    except Exception as e:
        log(f"Error syncing bugs from sheet: {e}")


def sync_tasks_from_sheet(spreadsheet):
    """Read task priority changes from sheet."""
    try:
        ws = spreadsheet.worksheet("Tasks")
        rows = ws.get_all_values()

        if len(rows) < 2:
            return

        conn = get_db()
        cursor = conn.cursor()
        updated = 0

        for row in rows[1:]:
            if len(row) < 4:
                continue

            task_id = row[0]
            priority = row[3] if len(row) > 3 else "0"

            if not task_id or not task_id.isdigit():
                continue

            try:
                priority = int(priority)
                cursor.execute("UPDATE task_queue SET priority=? WHERE id=?", (priority, task_id))
                if cursor.rowcount > 0:
                    updated += 1
            except:
                pass

        conn.commit()
        conn.close()

        if updated > 0:
            log(f"From Sheet: {updated} task priorities updated")

    except Exception as e:
        log(f"Error syncing tasks from sheet: {e}")


# =============================================================================
# DEVELOPMENT TASKS - Pulled by tmux sessions
# =============================================================================


def sync_dev_tasks_to_sheet(spreadsheet):
    """Sync development tasks to DevTasks sheet for tmux sessions to pull."""
    ws = get_or_create_worksheet(spreadsheet, "DevTasks")

    # Check if sheet needs initialization
    try:
        first_cell = ws.acell("A1").value
        if first_cell != "ID":
            ws.clear()
            headers = [
                "ID",
                "Task",
                "Type",
                "Priority",
                "Status",
                "Assigned To",
                "Session",
                "Created",
                "Started",
                "Completed",
                "Notes",
            ]
            ws.update(values=[headers], range_name="A1")
            ws.format(
                "A1:K1",
                {
                    "textFormat": {"bold": True},
                    "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.9},
                },
            )
            # Add template row
            ws.update(
                values=[
                    [
                        "NEW",
                        "(Enter task description)",
                        "feature",
                        "5",
                        "pending",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                ],
                range_name="A2",
            )
    except:
        pass

    # Get existing dev tasks from database
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, task_type, task_data, priority, status, assigned_worker,
                   created_at, started_at, completed_at, error_message
            FROM task_queue
            WHERE task_type IN ('dev', 'feature', 'bug_fix', 'refactor', 'test')
            ORDER BY priority DESC, created_at DESC
            LIMIT 100
        """
        )
        tasks = [dict(row) for row in cursor.fetchall()]
        conn.close()

        if tasks:
            rows = ws.get_all_values()
            existing_ids = {row[0] for row in rows[1:] if row and row[0].isdigit()}

            # Only add tasks not already in sheet
            new_rows = []
            for t in tasks:
                if str(t["id"]) not in existing_ids:
                    data = json.loads(t["task_data"]) if t["task_data"] else {}
                    new_rows.append(
                        [
                            t["id"],
                            data.get("description", data.get("title", ""))[:100],
                            t["task_type"],
                            t["priority"] or 5,
                            t["status"],
                            t["assigned_worker"] or "",
                            data.get("tmux_session", ""),
                            t["created_at"] or "",
                            t["started_at"] or "",
                            t["completed_at"] or "",
                            t["error_message"] or "",
                        ]
                    )

            if new_rows:
                next_row = len(rows) + 1
                ws.update(values=new_rows, range_name=f"A{next_row}")

        log(f"Synced dev tasks to sheet")
    except Exception as e:
        log(f"Error syncing dev tasks: {e}")


def sync_dev_tasks_from_sheet(spreadsheet):
    """Read new dev tasks from sheet and add to database."""
    try:
        ws = spreadsheet.worksheet("DevTasks")
        rows = ws.get_all_values()

        if len(rows) < 2:
            return

        conn = get_db()
        cursor = conn.cursor()
        new_tasks = 0
        updated_tasks = 0

        for i, row in enumerate(rows[1:], start=2):
            if len(row) < 5:
                continue

            task_id = row[0]
            task_desc = row[1] if len(row) > 1 else ""
            task_type = row[2] if len(row) > 2 else "dev"
            priority = row[3] if len(row) > 3 else "5"
            status = row[4] if len(row) > 4 else "pending"
            assigned_to = row[5] if len(row) > 5 else ""
            session = row[6] if len(row) > 6 else ""

            if not task_desc or task_desc.startswith("(Enter"):
                continue

            # New task - add to database
            if task_id == "NEW" or not task_id:
                try:
                    task_data = json.dumps(
                        {
                            "description": task_desc,
                            "title": task_desc[:50],
                            "tmux_session": session,
                            "source": "google_sheet",
                        }
                    )
                    cursor.execute(
                        """
                        INSERT INTO task_queue (task_type, task_data, priority, status, assigned_worker, created_at)
                        VALUES (?, ?, ?, 'pending', ?, CURRENT_TIMESTAMP)
                    """,
                        (task_type, task_data, int(priority), assigned_to or None),
                    )

                    new_id = cursor.lastrowid
                    # Update sheet with new ID
                    ws.update_acell(f"A{i}", str(new_id))
                    new_tasks += 1
                except Exception as e:
                    log(f"Error adding task: {e}")

            # Existing task - update status/assignment
            elif task_id.isdigit():
                try:
                    cursor.execute(
                        """
                        UPDATE task_queue
                        SET status=?, priority=?, assigned_worker=?
                        WHERE id=?
                    """,
                        (status, int(priority), assigned_to or None, int(task_id)),
                    )
                    if cursor.rowcount > 0:
                        updated_tasks += 1
                except:
                    pass

        conn.commit()
        conn.close()

        if new_tasks > 0 or updated_tasks > 0:
            log(f"From Sheet: {new_tasks} new dev tasks, {updated_tasks} updated")

    except Exception as e:
        log(f"Error syncing dev tasks from sheet: {e}")


# =============================================================================
# TESTING - Test cases and results
# =============================================================================


def sync_testing_to_sheet(spreadsheet):
    """Sync testing sheet for test management."""
    ws = get_or_create_worksheet(spreadsheet, "Testing")

    try:
        first_cell = ws.acell("A1").value
        if first_cell != "ID":
            ws.clear()
            headers = [
                "ID",
                "Test Name",
                "Type",
                "Target",
                "Status",
                "Assigned To",
                "Session",
                "Result",
                "Last Run",
                "Notes",
            ]
            ws.update(values=[headers], range_name="A1")
            ws.format(
                "A1:J1",
                {
                    "textFormat": {"bold": True},
                    "backgroundColor": {"red": 0.9, "green": 0.7, "blue": 0.2},
                },
            )

            # Add example test cases
            examples = [
                [
                    "NEW",
                    "(Add test name)",
                    "unit",
                    "(target file/module)",
                    "pending",
                    "",
                    "",
                    "",
                    "",
                    "",
                ],
                [
                    "T1",
                    "Dashboard health check",
                    "integration",
                    "http://100.112.58.92:8080/health",
                    "pending",
                    "",
                    "",
                    "",
                    "",
                    "Check dashboard responds",
                ],
                [
                    "T2",
                    "API authentication",
                    "integration",
                    "/api/stats",
                    "pending",
                    "",
                    "",
                    "",
                    "",
                    "Verify auth required",
                ],
                [
                    "T3",
                    "Database connection",
                    "unit",
                    "data/architect.db",
                    "pending",
                    "",
                    "",
                    "",
                    "",
                    "Check DB connectivity",
                ],
            ]
            ws.update(values=examples, range_name="A2")
    except:
        pass

    log("Synced testing sheet")


def sync_testing_from_sheet(spreadsheet):
    """Read test results from sheet and log them."""
    try:
        ws = spreadsheet.worksheet("Testing")
        rows = ws.get_all_values()

        if len(rows) < 2:
            return

        # Count test statuses
        statuses = {"passed": 0, "failed": 0, "pending": 0, "running": 0}
        for row in rows[1:]:
            if len(row) > 4:
                status = row[4].lower() if row[4] else "pending"
                if status in statuses:
                    statuses[status] += 1

        # Log test summary
        total = sum(statuses.values())
        if total > 0:
            log(
                f"Tests: {statuses['passed']} passed, {statuses['failed']} failed, {statuses['pending']} pending"
            )

    except Exception as e:
        log(f"Error reading tests from sheet: {e}")


# =============================================================================
# DECISIONS - Decision tracking and management
# =============================================================================


def sync_decisions_to_sheet(spreadsheet):
    """Sync decisions sheet for decision tracking."""
    ws = get_or_create_worksheet(spreadsheet, "Decisions")

    try:
        first_cell = ws.acell("A1").value
        if first_cell != "ID":
            ws.clear()
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
            ws.update(values=[headers], range_name="A1")
            ws.format(
                "A1:J1",
                {
                    "textFormat": {"bold": True},
                    "backgroundColor": {"red": 0.8, "green": 0.4, "blue": 0.8},
                },
            )

            # Add template
            ws.update(
                values=[
                    [
                        "NEW",
                        "(Describe decision needed)",
                        "architecture",
                        "(Option A, Option B)",
                        "pending",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                ],
                range_name="A2",
            )
    except:
        pass

    log("Synced decisions sheet")


# =============================================================================
# ENVIRONMENTS - System environments and services
# =============================================================================


def get_environment_data():
    """Get environment and service data from the dashboard API."""
    try:
        import requests

        # Login and get data
        session = requests.Session()
        session.post(
            "http://100.112.58.92:8080/login", data={"username": "architect", "password": "peace5"}
        )

        resp = session.get("http://100.112.58.92:8080/api/system/overview", timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        log(f"Error getting environment data: {e}")
    return None


def sync_environments_to_sheet(spreadsheet):
    """Sync environments and services to Environments sheet."""
    ws = get_or_create_worksheet(spreadsheet, "Environments")

    ws.clear()

    # Get environment data from API
    data = get_environment_data()

    rows = [
        ["ENVIRONMENTS & SERVICES"],
        [f'Last Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'],
        [""],
        ["=" * 60],
        ["ENVIRONMENTS"],
        ["=" * 60],
        [""],
        ["Environment", "Branch", "Uncommitted Changes", "Status"],
    ]

    if data and "environments" in data:
        envs = data["environments"]

        # Architect environment
        if "architect" in envs:
            arch = envs["architect"]
            rows.append(
                [
                    "Architect",
                    arch.get("branch", "unknown"),
                    arch.get("uncommitted_changes", 0),
                    "active",
                ]
            )

        # Edu Apps environments
        if "edu_apps" in envs:
            edu = envs["edu_apps"]
            if "main" in edu:
                rows.append(
                    [
                        "Edu Apps (main)",
                        edu["main"].get("branch", "unknown"),
                        edu["main"].get("uncommitted_changes", 0),
                        "active",
                    ]
                )
            if "feature_envs" in edu:
                for env_name, env_data in edu["feature_envs"].items():
                    rows.append(
                        [
                            f"Edu Apps ({env_name})",
                            env_data.get("branch", "unknown"),
                            env_data.get("uncommitted_changes", 0),
                            "active",
                        ]
                    )

        # KanbanFlow
        if "kanbanflow" in envs:
            kf = envs["kanbanflow"]
            rows.append(
                [
                    "KanbanFlow",
                    kf.get("branch", "unknown"),
                    kf.get("uncommitted_changes", 0),
                    "active",
                ]
            )

    rows.extend(
        [
            [""],
            ["=" * 60],
            ["SERVICES"],
            ["=" * 60],
            [""],
            ["Service", "Port", "Environment", "Status", "Host"],
        ]
    )

    if data and "services" in data:
        for svc_name, svc_data in data["services"].items():
            status = "online" if svc_data.get("running") else "offline"
            rows.append(
                [
                    svc_name,
                    svc_data.get("port", ""),
                    svc_data.get("env", ""),
                    status,
                    svc_data.get("host", "localhost"),
                ]
            )

    rows.extend(
        [
            [""],
            ["=" * 60],
            ["DATABASES"],
            ["=" * 60],
            [""],
            ["Database", "Size (MB)", "Status"],
        ]
    )

    if data and "databases" in data:
        for db_name, db_data in data["databases"].items():
            rows.append([db_name, db_data.get("size_mb", 0), db_data.get("status", "unknown")])

    rows.extend(
        [
            [""],
            ["=" * 60],
            ["TMUX SESSIONS BY ENVIRONMENT"],
            ["=" * 60],
            [""],
        ]
    )

    # Get tmux sessions grouped by environment
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT session_name, attached,
                   CASE
                       WHEN session_name LIKE 'arch_%' THEN REPLACE(session_name, 'arch_', '')
                       WHEN session_name LIKE 'task_worker%' THEN 'workers'
                       ELSE 'other'
                   END as env
            FROM tmux_sessions
            ORDER BY env, session_name
        """
        )
        sessions = cursor.fetchall()
        conn.close()

        current_env = None
        for session in sessions:
            env = session["env"]
            if env != current_env:
                rows.append([f"--- {env.upper()} ---", "", ""])
                current_env = env
            status = "attached" if session["attached"] else "detached"
            rows.append(["", session["session_name"], status])
    except Exception as e:
        rows.append([f"Error getting sessions: {e}"])

    # Write all data
    ws.update(values=rows, range_name="A1")

    # Format headers
    ws.format("A1", {"textFormat": {"bold": True, "fontSize": 14}})
    ws.format("A5", {"textFormat": {"bold": True}})
    ws.format(
        "A8:D8",
        {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.8, "green": 0.9, "blue": 1}},
    )

    log("Synced environments sheet")


# =============================================================================
# TMUX SESSION TASK MANAGEMENT
# =============================================================================


def get_next_task_for_session(session_name):
    """Get the next available task for a tmux session from the sheet.

    Returns task dict or None if no tasks available.
    Called by tmux sessions to pull work.
    """
    try:
        client = get_sheets_client()
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        ws = spreadsheet.worksheet("DevTasks")
        rows = ws.get_all_values()

        if len(rows) < 2:
            return None

        # Find first pending task not assigned to anyone
        for i, row in enumerate(rows[1:], start=2):
            if len(row) < 5:
                continue

            task_id = row[0]
            task_desc = row[1]
            status = row[4] if len(row) > 4 else ""
            assigned = row[5] if len(row) > 5 else ""

            if status.lower() == "pending" and not assigned and task_id.isdigit():
                # Claim this task
                ws.update_acell(f"E{i}", "in_progress")
                ws.update_acell(f"F{i}", session_name)
                ws.update_acell(f"G{i}", session_name)
                ws.update_acell(f"I{i}", datetime.now().strftime("%Y-%m-%d %H:%M"))

                return {
                    "id": task_id,
                    "description": task_desc,
                    "type": row[2] if len(row) > 2 else "dev",
                    "priority": row[3] if len(row) > 3 else "5",
                    "row": i,
                }

        return None
    except Exception as e:
        log(f"Error getting task for {session_name}: {e}")
        return None


def update_task_status(task_id, status, result=None, session_name=None):
    """Update task status in sheet when tmux session completes work.

    Args:
        task_id: Task ID or row number
        status: 'completed', 'failed', 'blocked'
        result: Optional result notes
        session_name: Session that completed the task
    """
    try:
        client = get_sheets_client()
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        ws = spreadsheet.worksheet("DevTasks")
        rows = ws.get_all_values()

        # Find the task row
        task_row = None
        for i, row in enumerate(rows[1:], start=2):
            if row and row[0] == str(task_id):
                task_row = i
                break

        if task_row:
            ws.update_acell(f"E{task_row}", status)
            ws.update_acell(f"J{task_row}", datetime.now().strftime("%Y-%m-%d %H:%M"))
            if result:
                ws.update_acell(f"K{task_row}", result[:200])

            log(f"Task {task_id} marked as {status} by {session_name}")
            return True

        return False
    except Exception as e:
        log(f"Error updating task {task_id}: {e}")
        return False


def assign_task_to_session(task_id, session_name):
    """Assign a specific task to a tmux session."""
    try:
        client = get_sheets_client()
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        ws = spreadsheet.worksheet("DevTasks")
        rows = ws.get_all_values()

        for i, row in enumerate(rows[1:], start=2):
            if row and row[0] == str(task_id):
                ws.update_acell(f"E{i}", "assigned")
                ws.update_acell(f"F{i}", session_name)
                ws.update_acell(f"G{i}", session_name)
                log(f"Task {task_id} assigned to {session_name}")
                return True

        return False
    except Exception as e:
        log(f"Error assigning task: {e}")
        return False


def get_session_tasks(session_name):
    """Get all tasks assigned to a specific session."""
    try:
        client = get_sheets_client()
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        ws = spreadsheet.worksheet("DevTasks")
        rows = ws.get_all_values()

        tasks = []
        for row in rows[1:]:
            if len(row) > 6 and row[6] == session_name:
                tasks.append(
                    {
                        "id": row[0],
                        "description": row[1],
                        "type": row[2],
                        "priority": row[3],
                        "status": row[4],
                    }
                )

        return tasks
    except Exception as e:
        log(f"Error getting tasks for {session_name}: {e}")
        return []


# =============================================================================
# SOP DOCUMENTATION
# =============================================================================


def sync_usage_to_sheet(spreadsheet):
    """Sync Usage guide to Usage sheet - quick reference for daily use."""
    ws = get_or_create_worksheet(spreadsheet, "Usage")

    try:
        first_cell = ws.acell("A1").value
        if first_cell and "USAGE GUIDE" in first_cell:
            return  # Already exists
    except:
        pass

    ws.clear()

    usage_content = [
        ["USAGE GUIDE - Quick Reference for Daily Operations"],
        [""],
        ["=" * 80],
        ["DEVELOPMENT WORKFLOW"],
        ["=" * 80],
        [""],
        ["1. ADD A TASK (for tmux session to work on):"],
        ["   - Go to DevTasks sheet"],
        ["   - Add row: NEW | Task description | feature | 5 | pending"],
        ["   - tmux session will auto-claim and start working"],
        [""],
        ["2. MONITOR PROGRESS:"],
        ["   - DevTasks: Check Status column (pending → in_progress → completed)"],
        ["   - Sessions: See which sessions are active"],
        ["   - Progress: Auto-confirm worker activity"],
        [""],
        ["3. PRIORITIZE WORK:"],
        ["   - Change Priority column (1-10, higher = more urgent)"],
        ["   - Tasks with higher priority get picked first"],
        [""],
        ["=" * 80],
        ["TESTING WORKFLOW"],
        ["=" * 80],
        [""],
        ["1. ADD TEST CASE:"],
        ["   - Go to Testing sheet"],
        ["   - Add: Test Name | Type (unit/integration/e2e) | Target | pending"],
        [""],
        ["2. RUN TESTS:"],
        ["   - tmux session or manually run test"],
        ["   - Update Status: running → passed/failed"],
        ["   - Add Result notes"],
        [""],
        ["3. TRACK RESULTS:"],
        ["   - Summary shows pass/fail counts"],
        ["   - Last Run column shows when tested"],
        [""],
        ["=" * 80],
        ["DECISION MAKING"],
        ["=" * 80],
        [""],
        ["1. ADD DECISION:"],
        ["   - Go to Decisions sheet"],
        ["   - Add: Decision needed | Category | Options | pending"],
        [""],
        ["2. REVIEW & DECIDE:"],
        ["   - Discuss in team or session"],
        ["   - Update Status: pending → in_review → decided"],
        ["   - Fill Outcome and Rationale"],
        [""],
        ["3. IMPLEMENT:"],
        ["   - Create DevTask from decision"],
        ["   - Update Status: decided → implemented"],
        [""],
        ["=" * 80],
        ["BUG TRACKING"],
        ["=" * 80],
        [""],
        ["1. REPORT BUG:"],
        ["   - Go to Bugs sheet"],
        ["   - Add: NEW | Title | severity | open | project | description"],
        [""],
        ["2. ASSIGN & FIX:"],
        ["   - Assign to session"],
        ["   - Status: open → in_progress → resolved"],
        [""],
        ["=" * 80],
        ["CLI COMMANDS (from terminal)"],
        ["=" * 80],
        [""],
        ["Pull task:     python3 workers/sheet_task_cli.py pull <session>"],
        ['Complete:      python3 workers/sheet_task_cli.py complete <id> "notes"'],
        ['Fail:          python3 workers/sheet_task_cli.py fail <id> "reason"'],
        ["List tasks:    python3 workers/sheet_task_cli.py list <session>"],
        ["Status:        python3 workers/sheet_task_cli.py status"],
        [""],
        ["=" * 80],
        ["STATUS MEANINGS"],
        ["=" * 80],
        [""],
        ["pending      - Waiting to be started"],
        ["assigned     - Claimed by a session"],
        ["in_progress  - Currently being worked on"],
        ["completed    - Successfully finished"],
        ["failed       - Could not complete"],
        ["blocked      - Waiting on dependency"],
        [""],
        ["=" * 80],
        ["PRIORITY LEVELS"],
        ["=" * 80],
        [""],
        ["1-3:  Low priority - nice to have"],
        ["4-6:  Normal priority - standard work"],
        ["7-8:  High priority - needs attention"],
        ["9-10: Critical - do immediately"],
        [""],
        ["=" * 80],
        ["SYNC SCHEDULE"],
        ["=" * 80],
        [""],
        ["- Changes sync every 2 minutes"],
        ["- tmux sessions auto-pull tasks when idle"],
        ["- Auto-confirm worker keeps sessions moving"],
        [""],
        ["Dashboard: http://100.112.58.92:8080"],
        ["Login: architect / peace5"],
    ]

    ws.update(values=usage_content, range_name="A1")
    ws.format("A1", {"textFormat": {"bold": True, "fontSize": 14}})

    log("Synced usage guide")


def sync_sop_to_sheet(spreadsheet, force: bool = False):
    """Sync Standard Operating Procedures to SOP sheet."""
    ws = get_or_create_worksheet(spreadsheet, "SOP")

    # Only update if sheet is empty or has template marker
    try:
        first_cell = ws.acell("A1").value
        if not force and first_cell and "STANDARD OPERATING PROCEDURES" in first_cell:
            return  # SOP already exists, don't overwrite
    except:
        pass

    ws.clear()

    sop_content = [
        ["STANDARD OPERATING PROCEDURES - Architect Dashboard Management"],
        [""],
        [
            "This sheet provides two-way sync with the Architect Dashboard. Changes made here sync automatically every 2 minutes."
        ],
        [""],
        ["=" * 80],
        ["SHEET OVERVIEW"],
        ["=" * 80],
        [""],
        ["Sheet", "Purpose", "Two-Way Sync"],
        ["Sessions", "View all tmux sessions and their status", "Read-only"],
        [
            "Bugs",
            "Track and manage bugs - ADD NEW BUGS HERE",
            'Yes - Add rows with "NEW" in ID column',
        ],
        ["Features", "View features organized by Project > Milestone", "Read-only"],
        ["Tasks", "View and prioritize task queue", "Yes - Change Priority column"],
        ["DevTasks", "DEVELOPMENT TASKS - tmux sessions pull from here", "Yes - Full two-way sync"],
        ["Testing", "TEST CASES - manage tests and results", "Yes - Update status and results"],
        [
            "Decisions",
            "DECISION TRACKING - architecture and design decisions",
            "Yes - Add and resolve decisions",
        ],
        [
            "Environments",
            "SYSTEM STATUS - environments, services, databases",
            "Read-only (auto-updated)",
        ],
        ["Errors", "View aggregated errors from all nodes", "Read-only"],
        ["Progress", "View auto-confirm worker activity", "Read-only"],
        ["Summary", "Dashboard statistics overview", "Read-only"],
        [""],
        ["=" * 80],
        ["SYSTEM INTEGRATION OVERVIEW"],
        ["=" * 80],
        [""],
        ["How the parts work together:"],
        ["- tmux AI agents (Claude/Codex/Ollama) receive work via assigners"],
        ["- Session assigner enforces env/scopes; assigner worker auto-routes prompts"],
        ["- Comet/Perplexity handles research tasks and feeds implementation"],
        ["- Google Sheets syncs DevTasks/Tasks/Bugs with the dashboard"],
        ["- Dashboard provides central visibility and status"],
        [""],
        ["=" * 80],
        ["TASK ROUTING ENTRY POINTS"],
        ["=" * 80],
        [""],
        ["Use ONE of these paths based on your workflow:"],
        ["- session_assigner.py: SOP-compliant assignment with env/scopes"],
        ["- assigner_worker.py: generic tmux inbox (claude/codex/ollama)"],
        ["- session_terminal.py: interactive os: prompt queue"],
        ["- DevTasks sheet: tmux sessions pull tasks"],
        ["- project_orchestrator.py: research + implement pipeline"],
        [""],
        ["=" * 80],
        ["HOW TO ADD DEVELOPMENT TASKS (For tmux Sessions)"],
        ["=" * 80],
        [""],
        ['1. Go to the "DevTasks" sheet'],
        ['2. Add a row with "NEW" in the ID column'],
        ["3. Fill in:"],
        ["   - Task: Description of the work to do"],
        ["   - Type: feature, bug_fix, refactor, test, dev"],
        ["   - Priority: 1-10 (higher = more urgent)"],
        ["   - Status: pending (tmux session will change to in_progress)"],
        ['4. Leave "Assigned To" and "Session" empty'],
        ["5. tmux sessions will automatically pull pending tasks"],
        ['6. When complete, session updates Status to "completed"'],
        [""],
        ["=" * 80],
        ["HOW TO ADD TEST CASES"],
        ["=" * 80],
        [""],
        ['1. Go to the "Testing" sheet'],
        ["2. Add a row with test details:"],
        ["   - Test Name: Descriptive name for the test"],
        ["   - Type: unit, integration, e2e, manual"],
        ["   - Target: File, URL, or module to test"],
        ["   - Status: pending, running, passed, failed"],
        ["3. tmux sessions can run tests and update results"],
        ["4. Result column shows pass/fail details"],
        [""],
        ["=" * 80],
        ["HOW TO TRACK DECISIONS"],
        ["=" * 80],
        [""],
        ['1. Go to the "Decisions" sheet'],
        ["2. Add decision details:"],
        ["   - Decision: What needs to be decided"],
        ["   - Category: architecture, design, process, tooling"],
        ["   - Options: List of choices (comma-separated)"],
        ["   - Status: pending, in_review, decided, implemented"],
        ["   - Outcome: Final decision made"],
        ["   - Rationale: Why this option was chosen"],
        [""],
        ["=" * 80],
        ["HOW TO ADD A NEW BUG"],
        ["=" * 80],
        [""],
        ['1. Go to the "Bugs" sheet'],
        ['2. Find the row with "NEW" in the ID column (or add a new row at the bottom)'],
        ["3. Fill in the following columns:"],
        ["   - Title: Brief description of the bug"],
        ["   - Severity: critical, high, medium, or low"],
        ["   - Status: open, in_progress, resolved, or closed"],
        ["   - Project: Project name (must match existing project)"],
        ["   - Description: Detailed description of the bug"],
        ["4. Wait 2 minutes for the sync to pick up your changes"],
        ["5. The ID will be updated to show the database ID once synced"],
        [""],
        ["=" * 80],
        ["HOW TO CHANGE TASK PRIORITY"],
        ["=" * 80],
        [""],
        ['1. Go to the "Tasks" sheet'],
        ["2. Find the task you want to reprioritize"],
        ['3. Change the "Priority" column value (higher number = higher priority)'],
        ["4. Wait 2 minutes for the sync to update the database"],
        ["5. Task workers will pick up higher priority tasks first"],
        [""],
        ["=" * 80],
        ["UNDERSTANDING SESSIONS"],
        ["=" * 80],
        [""],
        ["Session Types:"],
        ["- task_worker1-5: Background task processors (auto-confirmed)"],
        ["- arch_dev/qa/prod: Environment-specific sessions"],
        ["- architect: Main development session (excluded from auto-confirm)"],
        ["- autoconfirm: Auto-confirm worker session"],
        [""],
        ["Session Statuses:"],
        ["- attached: User is actively viewing this session"],
        ["- detached: Session is running but not being viewed"],
        ["- idle: Session is waiting for input"],
        [""],
        ["=" * 80],
        ["MONITORING WORKERS"],
        ["=" * 80],
        [""],
        ['The "Progress" sheet shows auto-confirm worker activity:'],
        ["- Which sessions received confirmations"],
        ["- What operations were confirmed (edit, bash, accept_edits)"],
        ["- When confirmations were sent"],
        [""],
        ["Worker excludes these sessions from auto-confirm:"],
        ["- architect (user's main session)"],
        ["- basic_edu (user's edu session)"],
        ["- autoconfirm (the worker itself)"],
        [""],
        ["=" * 80],
        ["FEATURE STATUS MEANINGS"],
        ["=" * 80],
        [""],
        ["- draft: Feature is planned but not started"],
        ["- in_progress: Feature is being actively developed"],
        ["- completed: Feature implementation is done"],
        ["- cancelled: Feature was abandoned"],
        [""],
        ["=" * 80],
        ["BUG SEVERITY GUIDE"],
        ["=" * 80],
        [""],
        ["- critical: System is down or data loss occurring"],
        ["- high: Major feature broken, no workaround"],
        ["- medium: Feature partially broken, workaround exists"],
        ["- low: Minor issue, cosmetic, or enhancement"],
        [""],
        ["=" * 80],
        ["SYNC SCHEDULE"],
        ["=" * 80],
        [""],
        ["- Full sync runs every 2 minutes"],
        ["- Sheet → Database: Bugs, Task priorities"],
        ["- Database → Sheet: All data"],
        ["- Changes you make may take up to 2 minutes to appear in dashboard"],
        [""],
        ["=" * 80],
        ["TROUBLESHOOTING"],
        ["=" * 80],
        [""],
        ["If changes don't appear:"],
        ['1. Check the Summary sheet "Last Updated" time'],
        ["2. Verify the project name matches exactly (case-sensitive)"],
        ["3. Ensure required fields are filled (Title, Severity, Status)"],
        ["4. Check /tmp/sheets_sync.log on the server for errors"],
        [""],
        ["If bugs aren't syncing:"],
        ['- Make sure ID column shows "NEW" for new bugs'],
        ["- Verify project name exists in the database"],
        ["- Check that all required fields are filled"],
        [""],
        ["=" * 80],
        ["CONTACT"],
        ["=" * 80],
        [""],
        ["Dashboard: http://100.112.58.92:8080"],
        ["Logs: /tmp/sheets_sync.log"],
        ["Config: workers/sheets_sync.py"],
    ]

    # Write all content
    ws.update(values=sop_content, range_name="A1")

    # Format header
    ws.format("A1", {"textFormat": {"bold": True, "fontSize": 14}})

    # Format section headers
    for i, row in enumerate(sop_content, start=1):
        if row and row[0] and "=" * 20 in str(row[0]):
            continue  # Skip separator lines
        if row and row[0] and row[0].isupper() and len(row[0]) > 5:
            try:
                ws.format(f"A{i}", {"textFormat": {"bold": True}})
            except:
                pass

    log("Synced SOP documentation")


# =============================================================================
# ARCHITECTURE SETUP SYNC
# =============================================================================


def sync_architecture_setup_to_sheet(spreadsheet):
    """Sync architecture setup and configuration data to sheet."""
    try:
        ws = get_or_create_worksheet(spreadsheet, "Architecture Setup", rows=100, cols=10)

        # Header
        headers = [
            "Component",
            "Type",
            "Port/Path",
            "Status",
            "Purpose",
            "PID",
            "Memory",
            "CPU",
            "Notes",
            "Last Updated",
        ]
        ws.update("A1:J1", [headers])

        # Collect system component data
        components = []

        # 1. Architect Dashboard
        try:
            result = subprocess.run(
                ["lsof", "-ti", ":8080"], capture_output=True, text=True, timeout=5
            )
            dashboard_pid = result.stdout.strip() if result.returncode == 0 else "N/A"
            dashboard_status = "🟢 Running" if dashboard_pid != "N/A" else "🔴 Stopped"
        except:
            dashboard_pid, dashboard_status = "N/A", "❓ Unknown"

        components.append(
            [
                "Architect Dashboard",
                "Flask Web App",
                "Port 8080",
                dashboard_status,
                "Main UI and API",
                dashboard_pid,
                "-",
                "-",
                "Central management interface",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )

        # 2. Comet Browser
        try:
            result = subprocess.run(
                ["pgrep", "-f", "Comet.*9222"], capture_output=True, text=True, timeout=5
            )
            comet_pid = result.stdout.strip().split("\n")[0] if result.stdout else "N/A"
            comet_status = "🟢 Running" if comet_pid != "N/A" else "🔴 Stopped"
        except:
            comet_pid, comet_status = "N/A", "❓ Unknown"

        components.append(
            [
                "Comet Browser",
                "Chromium",
                "CDP Port 9222",
                comet_status,
                "Browser automation",
                comet_pid,
                "-",
                "-",
                "Remote debugging enabled",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )

        # 3. Comet Backend
        try:
            result = subprocess.run(
                ["lsof", "-ti", ":9090"], capture_output=True, text=True, timeout=5
            )
            backend_pid = result.stdout.strip() if result.returncode == 0 else "N/A"
            backend_status = "🟢 Running" if backend_pid != "N/A" else "🔴 Stopped"
        except:
            backend_pid, backend_status = "N/A", "❓ Unknown"

        components.append(
            [
                "Comet Backend",
                "Go API Server",
                "Port 9090",
                backend_status,
                "Automation API",
                backend_pid,
                "-",
                "-",
                "CDP integration",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )

        # 4. AnythingLLM
        try:
            result = subprocess.run(
                ["pgrep", "-f", "AnythingLLM"], capture_output=True, text=True, timeout=5
            )
            anything_pid = result.stdout.strip().split("\n")[0] if result.stdout else "N/A"
            anything_status = "🟢 Running" if anything_pid != "N/A" else "🔴 Stopped"
        except:
            anything_pid, anything_status = "N/A", "❓ Unknown"

        components.append(
            [
                "AnythingLLM",
                "Desktop App",
                "Internal",
                anything_status,
                "Local LLM interface",
                anything_pid,
                "-",
                "-",
                "Connects to Ollama",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )

        # 5. Ollama
        try:
            result = subprocess.run(
                ["lsof", "-ti", ":11434"], capture_output=True, text=True, timeout=5
            )
            ollama_pid = result.stdout.strip() if result.returncode == 0 else "N/A"
            ollama_status = "🟢 Running" if ollama_pid != "N/A" else "🔴 Stopped"
        except:
            ollama_pid, ollama_status = "N/A", "❓ Unknown"

        components.append(
            [
                "Ollama",
                "LLM Server",
                "Port 11434",
                ollama_status,
                "Local model hosting",
                ollama_pid,
                "-",
                "-",
                "7 models available",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )

        # 6. Sheets Sync Worker
        sheets_pid = os.getpid()
        components.append(
            [
                "Sheets Sync Worker",
                "Python Worker",
                "N/A",
                "🟢 Running",
                "Google Sheets sync",
                str(sheets_pid),
                "-",
                "-",
                "Bidirectional sync every 2min",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )

        # 7. Session Watchdog
        try:
            result = subprocess.run(
                ["pgrep", "-f", "session_watchdog"], capture_output=True, text=True, timeout=5
            )
            watchdog_pid = result.stdout.strip().split("\n")[0] if result.stdout else "N/A"
            watchdog_status = "🟢 Running" if watchdog_pid != "N/A" else "🔴 Stopped"
        except:
            watchdog_pid, watchdog_status = "N/A", "❓ Unknown"

        components.append(
            [
                "Session Watchdog",
                "Python Monitor",
                "N/A",
                watchdog_status,
                "Session health monitoring",
                watchdog_pid,
                "-",
                "-",
                "Checks every 3 minutes",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )

        # 8. Database
        db_exists = DB_PATH.exists()
        db_size = f"{DB_PATH.stat().st_size / (1024*1024):.1f} MB" if db_exists else "N/A"
        components.append(
            [
                "Architect DB",
                "SQLite",
                str(DB_PATH),
                "🟢 Active" if db_exists else "🔴 Missing",
                "Primary data store",
                "N/A",
                db_size,
                "-",
                "WAL mode enabled",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )

        # Write to sheet
        if components:
            ws.update(f"A2:J{len(components)+1}", components)

        log(f"Synced architecture setup ({len(components)} components)")

    except Exception as e:
        log(f"Error syncing architecture setup: {e}")


def get_or_create_google_doc(client):
    """Get existing architecture Google Doc or create new one."""
    global ARCHITECTURE_DOC_ID

    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        # Set up Google Docs API
        scopes = [
            "https://www.googleapis.com/auth/documents",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(str(CREDENTIALS_PATH), scopes=scopes)
        drive_service = build("drive", "v3", credentials=creds)
        docs_service = build("docs", "v1", credentials=creds)

        # Search for existing doc
        results = (
            drive_service.files()
            .list(
                q=f"name='{ARCHITECTURE_DOC_TITLE}' and mimeType='application/vnd.google-apps.document' and trashed=false",
                spaces="drive",
                fields="files(id, name)",
            )
            .execute()
        )

        files = results.get("files", [])

        if files:
            ARCHITECTURE_DOC_ID = files[0]["id"]
            log(f"Found existing architecture doc: {ARCHITECTURE_DOC_ID}")
            return docs_service, ARCHITECTURE_DOC_ID
        else:
            # Create new doc
            doc = docs_service.documents().create(body={"title": ARCHITECTURE_DOC_TITLE}).execute()
            ARCHITECTURE_DOC_ID = doc["documentId"]
            log(f"Created new architecture doc: {ARCHITECTURE_DOC_ID}")
            return docs_service, ARCHITECTURE_DOC_ID

    except Exception as e:
        log(f"Error with Google Doc: {e}")
        return None, None


def sync_architecture_to_google_doc(client):
    """Sync architecture documentation to Google Doc."""
    try:
        docs_service, doc_id = get_or_create_google_doc(client)
        if not docs_service or not doc_id:
            return

        # Build documentation content
        content = []
        content.append(
            {
                "insertText": {
                    "text": "Architect Dashboard - Architecture Guide\n",
                    "location": {"index": 1},
                }
            }
        )
        content.append(
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": 1, "endIndex": 45},
                    "paragraphStyle": {"namedStyleType": "HEADING_1"},
                    "fields": "namedStyleType",
                }
            }
        )

        # System Overview
        overview = f"\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        overview += "## System Overview\n\n"
        overview += "The Architect Dashboard is a distributed project management and automation system with the following components:\n\n"

        # Read architecture setup from database or discover live
        overview += "### Core Components\n\n"
        overview += "1. **Architect Dashboard (Port 8080)** - Flask-based web UI and REST API\n"
        overview += "2. **Comet Browser (Port 9222)** - Chromium with CDP for browser automation\n"
        overview += "3. **Comet Backend (Port 9090)** - Go-based automation API server\n"
        overview += "4. **AnythingLLM** - Local LLM interface connecting to Ollama\n"
        overview += "5. **Ollama (Port 11434)** - Local LLM model server (7 models)\n"
        overview += "6. **Google Sheets Sync** - Bidirectional data synchronization\n"
        overview += "7. **Session Watchdog** - Monitors session health every 3 minutes\n\n"

        # Integration points
        overview += "## Integration Points\n\n"
        overview += "- **CDP (Chrome DevTools Protocol)**: Port 9222 for browser control\n"
        overview += "- **Backend API**: Port 9090 for automation commands\n"
        overview += "- **Ollama API**: Port 11434 for local LLM inference\n"
        overview += "- **Google Sheets**: Bidirectional sync every 2 minutes\n"
        overview += "- **SQLite Database**: WAL mode for concurrent access\n\n"

        # Read progress summaries
        try:
            progress_file = Path("/tmp/progress_summary.md")
            if progress_file.exists():
                overview += "## Latest Progress Summary\n\n"
                overview += progress_file.read_text()
                overview += "\n\n"
        except:
            pass

        # Append content to doc (replace existing content)
        requests = [
            {
                "deleteContentRange": {"range": {"startIndex": 1, "endIndex": 1000000}}
            },  # Clear existing
            {"insertText": {"text": overview, "location": {"index": 1}}},
        ]

        docs_service.documents().batchUpdate(
            documentId=doc_id, body={"requests": requests}
        ).execute()

        log(
            f"Synced architecture documentation to Google Doc: https://docs.google.com/document/d/{doc_id}"
        )

    except Exception as e:
        log(f"Error syncing to Google Doc: {e}")


# =============================================================================
# MAIN SYNC
# =============================================================================


def full_sync(client):
    """Perform full bidirectional sync."""
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        log(f"Connected to: {spreadsheet.title}")

        # First, read changes from sheet (user edits)
        sync_bugs_from_sheet(spreadsheet)
        sync_tasks_from_sheet(spreadsheet)
        sync_dev_tasks_from_sheet(spreadsheet)
        sync_testing_from_sheet(spreadsheet)

        # Then, sync current state to sheet
        sync_sessions_to_sheet(spreadsheet)
        sync_bugs_to_sheet(spreadsheet)
        sync_features_to_sheet(spreadsheet)
        sync_tasks_to_sheet(spreadsheet)
        sync_errors_to_sheet(spreadsheet)
        sync_progress_to_sheet(spreadsheet)

        # Development, Testing, and Decisions sheets
        sync_dev_tasks_to_sheet(spreadsheet)
        sync_testing_to_sheet(spreadsheet)
        sync_decisions_to_sheet(spreadsheet)
        sync_environments_to_sheet(spreadsheet)

        sync_summary_to_sheet(spreadsheet)
        sync_usage_to_sheet(spreadsheet)
        sync_sop_to_sheet(spreadsheet)

        # Architecture and documentation sync
        sync_architecture_setup_to_sheet(spreadsheet)
        sync_architecture_to_google_doc(client)

        log("Full sync complete!")
        return True

    except Exception as e:
        log(f"Sync error: {e}")
        return False


def run_daemon():
    """Run continuous sync daemon."""
    log("Starting sheets sync daemon (2-way sync)...")

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    try:
        import gspread
    except ImportError:
        log("Missing gspread. Run: pip3 install gspread google-auth")
        return

    client = get_sheets_client()
    if not client:
        return

    while True:
        try:
            full_sync(client)
        except Exception as e:
            log(f"Sync error: {e}")

        log(f"Next sync in {SYNC_INTERVAL}s...")
        time.sleep(SYNC_INTERVAL)


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--daemon":
            run_daemon()
            return
        elif sys.argv[1] == "--sync-sop":
            try:
                import gspread
            except ImportError:
                log("Missing gspread. Run: pip3 install gspread google-auth")
                return
            client = get_sheets_client()
            if client:
                spreadsheet = client.open_by_key(SPREADSHEET_ID)
                sync_sop_to_sheet(spreadsheet, force=True)
            return
        elif sys.argv[1] == "--status":
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
        elif sys.argv[1] == "--stop":
            if PID_FILE.exists():
                pid = PID_FILE.read_text().strip()
                try:
                    os.kill(int(pid), 15)
                    print(f"Stopped daemon (PID {pid})")
                    PID_FILE.unlink()
                except:
                    print("Failed to stop")
            return

    # One-time sync
    try:
        import gspread
    except ImportError:
        log("Missing gspread. Run: pip3 install gspread google-auth")
        return

    client = get_sheets_client()
    if client:
        full_sync(client)


if __name__ == "__main__":
    main()
