#!/usr/bin/env python3
"""
Automated Status Update Sender
Sends operational status updates via Dialpad SMS.
"""

import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

from dialpad_sms import DialpadSMS


def get_status_summary():
    """Get operational status summary with error resilience."""
    base_path = Path(__file__).parent.parent
    architect_db = base_path / "data" / "architect.db"
    assigner_db = base_path / "data" / "assigner" / "assigner.db"

    now = datetime.now()
    status_parts = []
    health_issues = []

    try:
        # === SESSION STATUS ===
        try:
            conn_assigner = sqlite3.connect(str(assigner_db))
            cursor = conn_assigner.cursor()

            # Get session activity details
            cursor.execute(
                """
                SELECT name, status, provider, last_activity
                FROM sessions
                WHERE status IN ('idle', 'busy', 'waiting_input')
                ORDER BY last_activity DESC
            """
            )
            sessions = cursor.fetchall()

            # Analyze sessions
            idle_sessions = []
            active_count = 0
            claude_count = 0
            codex_count = 0

            for name, status, provider, last_activity in sessions:
                last_act = datetime.strptime(last_activity, "%Y-%m-%d %H:%M:%S")
                idle_minutes = int((now - last_act).total_seconds() / 60)

                if provider == "claude":
                    claude_count += 1
                elif provider == "codex":
                    codex_count += 1

                # Flag sessions idle >30 mins
                if idle_minutes > 30:
                    idle_sessions.append((name, idle_minutes))
                elif status == "busy" or status == "waiting_input":
                    active_count += 1

            status_parts.append(f"Sessions: {active_count} active, {len(idle_sessions)} idle")
            status_parts.append(f"  Claude: {claude_count} | Codex: {codex_count}")

            # Report idle sessions
            if idle_sessions:
                top_idle = sorted(idle_sessions, key=lambda x: x[1], reverse=True)[:3]
                for name, mins in top_idle:
                    hours = mins // 60
                    if hours > 0:
                        status_parts.append(f"  ⏸ {name}: {hours}h {mins % 60}m idle")
                    else:
                        status_parts.append(f"  ⏸ {name}: {mins}m idle")
                health_issues.append(f"{len(idle_sessions)} sessions stale")

            conn_assigner.close()

        except Exception as e:
            status_parts.append(f"Sessions: Error ({str(e)[:30]})")
            health_issues.append("Session tracking broken")

        # === PROMPT QUEUE ===
        try:
            conn_assigner = sqlite3.connect(str(assigner_db))
            cursor = conn_assigner.cursor()

            cursor.execute("SELECT COUNT(*) FROM prompts WHERE status = 'pending'")
            pending_prompts = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM prompts WHERE status = 'in_progress'")
            active_prompts = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*) FROM prompts
                WHERE status = 'completed'
                AND completed_at > datetime('now', '-1 hour')
            """
            )
            recent_completed = cursor.fetchone()[0]

            if pending_prompts > 0 or active_prompts > 0:
                status_parts.append(
                    f"Prompts: {pending_prompts} queued | {active_prompts} active | {recent_completed} done (1h)"
                )
            else:
                status_parts.append(f"Prompts: None active | {recent_completed} done (1h)")

            if pending_prompts > 5:
                health_issues.append(f"{pending_prompts} prompts backlogged")

            conn_assigner.close()

        except Exception as e:
            status_parts.append(f"Prompts: Error")

        # === TASK QUEUE ===
        try:
            conn_architect = sqlite3.connect(str(architect_db))
            cursor = conn_architect.cursor()

            cursor.execute("SELECT COUNT(*) FROM task_queue WHERE status = 'pending'")
            pending_tasks = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM task_queue WHERE status = 'in_progress'")
            active_tasks = cursor.fetchone()[0]

            # Check for stuck tasks (pending >24h)
            cursor.execute(
                """
                SELECT COUNT(*) FROM task_queue
                WHERE status = 'pending'
                AND created_at < datetime('now', '-1 day')
            """
            )
            stuck_tasks = cursor.fetchone()[0]

            status_parts.append(f"Tasks: {pending_tasks} pending | {active_tasks} active")

            if stuck_tasks > 0:
                status_parts.append(f"  ⚠️ {stuck_tasks} tasks stuck >24h")
                health_issues.append(f"{stuck_tasks} stuck tasks")

            conn_architect.close()

        except Exception as e:
            status_parts.append(f"Tasks: Error")

        # === PROJECTS & FEATURES ===
        try:
            conn_architect = sqlite3.connect(str(architect_db))
            cursor = conn_architect.cursor()

            cursor.execute("SELECT COUNT(*) FROM projects WHERE status = 'active'")
            active_projects = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM features WHERE status = 'in_progress'")
            active_features = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*) FROM features
                WHERE status = 'completed'
                AND completed_at > datetime('now', '-1 day')
            """
            )
            recent_features = cursor.fetchone()[0]

            status_parts.append(
                f"Features: {active_features} active | {recent_features} done (24h)"
            )

            conn_architect.close()

        except Exception as e:
            status_parts.append(f"Features: Error")

        # === OVERALL HEALTH ===
        if health_issues:
            health = "⚠️ DEGRADED"
            status_parts.append(f"\nHealth: {health}")
            status_parts.append("Issues:")
            for issue in health_issues[:3]:  # Top 3 issues
                status_parts.append(f"  • {issue}")
        else:
            health = "✅ HEALTHY"
            status_parts.append(f"\nHealth: {health}")

        # Build final message
        timestamp = now.strftime("%I:%M%p")
        header = f"🔧 Architect {timestamp}\n"

        return header + "\n".join(status_parts)

    except Exception as e:
        # Catastrophic failure - log internally, send minimal SMS
        error_log = base_path / "logs" / "status_errors.log"
        with open(error_log, "a") as f:
            f.write(f"{now.isoformat()} - Critical error: {str(e)}\n")

        return f"⚠️ Architect {now.strftime('%I:%M%p')}\n\nStatus system offline\nCheck logs/status_errors.log"


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Send automated status updates")
    parser.add_argument("--phone", default="+15103886759", help="Phone number to send to")
    parser.add_argument(
        "--interval", type=int, default=60, help="Interval in minutes (default: 60)"
    )
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--once", action="store_true", help="Send once and exit")

    args = parser.parse_args()

    sms = DialpadSMS()

    print(f"📱 Automated Update Sender")
    print(f"   Phone: {args.phone}")
    print(f"   Interval: {args.interval} minutes")
    print(f"   Mode: {'Daemon' if args.daemon else 'Once' if args.once else 'Foreground'}")
    print()

    if args.once:
        # Send once and exit
        message = get_status_summary()
        print(f"Sending update...")
        result = sms.send_sms(args.phone, message)
        if result["success"]:
            print("✅ Update sent!")
        else:
            print(f"❌ Failed: {result['error']}")
        return

    # Continuous loop
    interval_seconds = args.interval * 60

    try:
        while True:
            message = get_status_summary()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Sending update...")

            result = sms.send_sms(args.phone, message)

            if result["success"]:
                print(f"✅ Update sent to {args.phone}")
            else:
                print(f"❌ Failed: {result['error']}")

            print(f"   Next update in {args.interval} minutes...")
            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\n\n⚠️  Update sender stopped by user")


if __name__ == "__main__":
    main()
