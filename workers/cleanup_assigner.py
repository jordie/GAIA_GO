#!/usr/bin/env python3
"""
Cleanup script for the assigner worker database.

This script:
- Removes stale sessions that no longer exist in tmux
- Resets failed prompts that targeted non-existent sessions
- Verifies database integrity
- Provides options to retry failed prompts

Usage:
    python3 cleanup_assigner.py              # Show what would be cleaned
    python3 cleanup_assigner.py --apply      # Actually clean the database
    python3 cleanup_assigner.py --retry-failed  # Retry failed prompts after cleanup
"""

import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import List, Set

# Setup paths
WORKER_DIR = Path(__file__).parent
BASE_DIR = WORKER_DIR.parent
DATA_DIR = BASE_DIR / "data"
ASSIGNER_DIR = DATA_DIR / "assigner"
ASSIGNER_DB = ASSIGNER_DIR / "assigner.db"


def get_tmux_sessions() -> Set[str]:
    """Get list of currently running tmux sessions."""
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return set(s.strip() for s in result.stdout.strip().split("\n") if s.strip())
    except Exception as e:
        print(f"Error listing tmux sessions: {e}")
        return set()
    return set()


def get_db_sessions(conn: sqlite3.Connection) -> List[dict]:
    """Get all sessions from the database."""
    cursor = conn.execute(
        """
        SELECT name, status, provider, is_claude, current_task_id,
               last_activity, updated_at
        FROM sessions
        ORDER BY name
    """
    )
    return [
        {
            "name": row[0],
            "status": row[1],
            "provider": row[2],
            "is_claude": row[3],
            "current_task_id": row[4],
            "last_activity": row[5],
            "updated_at": row[6],
        }
        for row in cursor.fetchall()
    ]


def get_failed_prompts(conn: sqlite3.Connection) -> List[dict]:
    """Get all failed prompts with their details."""
    cursor = conn.execute(
        """
        SELECT id, content, assigned_session, target_session, error,
               created_at, retry_count, max_retries
        FROM prompts
        WHERE status = 'failed'
        ORDER BY created_at DESC
    """
    )
    return [
        {
            "id": row[0],
            "content": row[1][:50] + "..." if len(row[1]) > 50 else row[1],
            "assigned_session": row[2],
            "target_session": row[3],
            "error": row[4],
            "created_at": row[5],
            "retry_count": row[6],
            "max_retries": row[7],
        }
        for row in cursor.fetchall()
    ]


def analyze_database(conn: sqlite3.Connection):
    """Analyze the database and report issues."""
    print("\n" + "=" * 80)
    print("ASSIGNER DATABASE ANALYSIS")
    print("=" * 80 + "\n")

    # Get current tmux sessions
    tmux_sessions = get_tmux_sessions()
    print(f"✓ Found {len(tmux_sessions)} active tmux sessions:")
    for session in sorted(tmux_sessions):
        print(f"  - {session}")
    print()

    # Get database sessions
    db_sessions = get_db_sessions(conn)
    print(f"✓ Found {len(db_sessions)} sessions in database\n")

    # Find stale sessions
    stale_sessions = []
    for session in db_sessions:
        if session["name"] not in tmux_sessions:
            stale_sessions.append(session)

    if stale_sessions:
        print(f"⚠ Found {len(stale_sessions)} STALE sessions (in DB but not in tmux):")
        for session in stale_sessions:
            task_info = (
                f" [task: {session['current_task_id']}]" if session["current_task_id"] else ""
            )
            print(
                f"  - {session['name']:<20} status={session['status']:<15} "
                f"provider={session['provider'] or 'unknown'}{task_info}"
            )
        print()
    else:
        print("✓ No stale sessions found\n")

    # Get failed prompts
    failed_prompts = get_failed_prompts(conn)
    if failed_prompts:
        print(f"⚠ Found {len(failed_prompts)} failed prompts:")

        # Group by target session
        by_target = {}
        for prompt in failed_prompts:
            target = prompt["assigned_session"] or prompt["target_session"] or "unknown"
            if target not in by_target:
                by_target[target] = []
            by_target[target].append(prompt)

        for target, prompts in by_target.items():
            exists = "EXISTS" if target in tmux_sessions else "MISSING"
            print(f"\n  Target: {target} ({exists})")
            for p in prompts:
                retry_info = f" (retries: {p['retry_count']}/{p['max_retries']})"
                print(f"    ID {p['id']}: {p['content']}{retry_info}")
                if p["error"]:
                    print(f"      Error: {p['error']}")
        print()
    else:
        print("✓ No failed prompts\n")

    # Get prompt statistics
    cursor = conn.execute(
        """
        SELECT status, COUNT(*) as count
        FROM prompts
        GROUP BY status
        ORDER BY count DESC
    """
    )
    print("Prompt Statistics:")
    for row in cursor.fetchall():
        print(f"  {row[0]:<15} {row[1]}")
    print()

    return stale_sessions, failed_prompts


def cleanup_stale_sessions(
    conn: sqlite3.Connection, stale_sessions: List[dict], apply: bool = False
):
    """Remove stale sessions from the database."""
    if not stale_sessions:
        print("✓ No stale sessions to clean\n")
        return

    print("\n" + "=" * 80)
    print("CLEANUP: STALE SESSIONS")
    print("=" * 80 + "\n")

    if apply:
        print(f"🗑️  Removing {len(stale_sessions)} stale sessions from database...")
        for session in stale_sessions:
            # Free up any tasks assigned to this session
            if session["current_task_id"]:
                conn.execute(
                    """
                    UPDATE prompts
                    SET status = 'pending',
                        assigned_session = NULL,
                        assigned_at = NULL
                    WHERE id = ? AND status IN ('assigned', 'in_progress')
                """,
                    (session["current_task_id"],),
                )
                print(f"  ↻ Freed task {session['current_task_id']} from {session['name']}")

            # Delete the session
            conn.execute("DELETE FROM sessions WHERE name = ?", (session["name"],))
            print(f"  ✗ Deleted session: {session['name']}")

        conn.commit()
        print(f"\n✓ Removed {len(stale_sessions)} stale sessions\n")
    else:
        print(f"[DRY RUN] Would remove {len(stale_sessions)} stale sessions:")
        for session in stale_sessions:
            print(f"  - {session['name']}")
        print("\nRun with --apply to actually clean\n")


def cleanup_failed_prompts(
    conn: sqlite3.Connection,
    failed_prompts: List[dict],
    tmux_sessions: Set[str],
    apply: bool = False,
):
    """Reset failed prompts that targeted non-existent sessions."""
    if not failed_prompts:
        print("✓ No failed prompts to clean\n")
        return

    # Find failed prompts that targeted sessions that don't exist
    to_reset = []
    for prompt in failed_prompts:
        target = prompt["assigned_session"] or prompt["target_session"]
        if target and target not in tmux_sessions:
            # Check if error is about missing session
            if "can't find pane" in (prompt["error"] or ""):
                to_reset.append(prompt)

    if not to_reset:
        print("✓ No failed prompts targeting non-existent sessions\n")
        return

    print("\n" + "=" * 80)
    print("CLEANUP: FAILED PROMPTS")
    print("=" * 80 + "\n")

    if apply:
        print(f"🔄 Resetting {len(to_reset)} failed prompts to pending...")
        for prompt in to_reset:
            conn.execute(
                """
                UPDATE prompts
                SET status = 'pending',
                    assigned_session = NULL,
                    target_session = NULL,
                    assigned_at = NULL,
                    error = NULL
                WHERE id = ?
            """,
                (prompt["id"],),
            )
            print(f"  ↻ Reset prompt {prompt['id']}: {prompt['content']}")

        conn.commit()
        print(f"\n✓ Reset {len(to_reset)} failed prompts to pending\n")
    else:
        print(f"[DRY RUN] Would reset {len(to_reset)} failed prompts:")
        for prompt in to_reset:
            print(f"  ID {prompt['id']}: {prompt['content']}")
        print("\nRun with --apply to actually reset\n")


def verify_database(conn: sqlite3.Connection):
    """Verify database integrity."""
    print("\n" + "=" * 80)
    print("DATABASE INTEGRITY CHECK")
    print("=" * 80 + "\n")

    try:
        # Check for foreign key violations
        cursor = conn.execute("PRAGMA foreign_key_check")
        violations = cursor.fetchall()
        if violations:
            print(f"⚠ Found {len(violations)} foreign key violations:")
            for v in violations:
                print(f"  {v}")
        else:
            print("✓ No foreign key violations")

        # Check for integrity
        cursor = conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        if result == "ok":
            print("✓ Database integrity OK")
        else:
            print(f"⚠ Database integrity issues: {result}")

        print()

    except Exception as e:
        print(f"✗ Error checking database: {e}\n")


def retry_failed_prompts(conn: sqlite3.Connection, apply: bool = False):
    """Retry all failed prompts that can be retried."""
    cursor = conn.execute(
        """
        SELECT id, content, retry_count, max_retries
        FROM prompts
        WHERE status = 'failed' AND retry_count < max_retries
    """
    )
    prompts = cursor.fetchall()

    if not prompts:
        print("✓ No failed prompts available for retry\n")
        return

    print("\n" + "=" * 80)
    print("RETRY FAILED PROMPTS")
    print("=" * 80 + "\n")

    if apply:
        print(f"🔄 Retrying {len(prompts)} failed prompts...")
        for prompt_id, content, retry_count, max_retries in prompts:
            conn.execute(
                """
                UPDATE prompts
                SET status = 'pending',
                    retry_count = retry_count + 1,
                    assigned_session = NULL,
                    assigned_at = NULL,
                    completed_at = NULL,
                    error = NULL
                WHERE id = ?
            """,
                (prompt_id,),
            )
            short_content = content[:50] + "..." if len(content) > 50 else content
            print(
                f"  ↻ Queued prompt {prompt_id} for retry "
                f"({retry_count + 1}/{max_retries}): {short_content}"
            )

        conn.commit()
        print(f"\n✓ Queued {len(prompts)} prompts for retry\n")
    else:
        print(f"[DRY RUN] Would retry {len(prompts)} failed prompts:")
        for prompt_id, content, retry_count, max_retries in prompts:
            short_content = content[:50] + "..." if len(content) > 50 else content
            print(f"  ID {prompt_id} ({retry_count}/{max_retries}): {short_content}")
        print("\nRun with --retry-failed --apply to actually retry\n")


def main():
    parser = argparse.ArgumentParser(description="Cleanup assigner database")
    parser.add_argument(
        "--apply", action="store_true", help="Actually apply changes (default: dry run)"
    )
    parser.add_argument(
        "--retry-failed", action="store_true", help="Retry failed prompts after cleanup"
    )
    parser.add_argument("--verify-only", action="store_true", help="Only verify database integrity")
    args = parser.parse_args()

    if not ASSIGNER_DB.exists():
        print(f"✗ Database not found: {ASSIGNER_DB}")
        sys.exit(1)

    print(f"📊 Analyzing assigner database: {ASSIGNER_DB}")

    # Connect to database
    conn = sqlite3.connect(str(ASSIGNER_DB))
    conn.row_factory = sqlite3.Row

    try:
        # Verify database integrity
        verify_database(conn)

        if args.verify_only:
            return

        # Analyze database
        tmux_sessions = get_tmux_sessions()
        stale_sessions, failed_prompts = analyze_database(conn)

        # Cleanup stale sessions
        cleanup_stale_sessions(conn, stale_sessions, apply=args.apply)

        # Cleanup failed prompts
        cleanup_failed_prompts(conn, failed_prompts, tmux_sessions, apply=args.apply)

        # Retry failed prompts if requested
        if args.retry_failed:
            retry_failed_prompts(conn, apply=args.apply)

        if not args.apply:
            print("\n" + "=" * 80)
            print("💡 TIP: Run with --apply to actually clean the database")
            print("💡 TIP: Run with --retry-failed to retry failed prompts")
            print("=" * 80 + "\n")
        else:
            print("\n" + "=" * 80)
            print("✓ CLEANUP COMPLETE")
            print("=" * 80 + "\n")
            print("Next steps:")
            print("  1. Check assigner worker status: python3 workers/assigner_worker.py --status")
            print("  2. Monitor logs: tail -f /tmp/architect_assigner_worker.log")
            print(
                "  3. If needed, restart worker: "
                "python3 workers/assigner_worker.py --stop && "
                "python3 workers/assigner_worker.py --daemon"
            )
            print()

    finally:
        conn.close()


if __name__ == "__main__":
    main()
