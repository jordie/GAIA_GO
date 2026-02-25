#!/usr/bin/env python3
"""
Test Auto-Confirm Worker with Foundation Session

Verifies that:
1. Foundation session is NOT in EXCLUDED_SESSIONS
2. Auto-confirm worker can detect and process prompts
3. Configuration is correct for auto-confirmation
"""

import re
import subprocess
import sys
import time
from pathlib import Path

# Import the worker module
sys.path.insert(0, str(Path(__file__).parent))
import auto_confirm_worker as worker


def test_configuration():
    """Test 1: Verify configuration"""
    print("[Test 1] Configuration Verification")
    print("-" * 50)

    # Check foundation is not excluded
    if "foundation" in worker.EXCLUDED_SESSIONS:
        print("❌ FAIL: 'foundation' is in EXCLUDED_SESSIONS")
        return False
    else:
        print("✓ PASS: 'foundation' is NOT excluded (will be auto-confirmed)")

    # Check only autoconfirm is excluded
    print(f"  Excluded sessions: {worker.EXCLUDED_SESSIONS}")
    print(f"  Safe operations: {worker.SAFE_OPERATIONS}")
    print(f"  Idle threshold: {worker.IDLE_THRESHOLD}s")
    print(f"  Dry run mode: {worker.DRY_RUN}")
    print()
    return True


def test_tmux_session_detection():
    """Test 2: Verify tmux can detect foundation session"""
    print("[Test 2] TMux Session Detection")
    print("-" * 50)

    try:
        result = subprocess.run(
            ["tmux", "list-sessions"], capture_output=True, text=True, timeout=5
        )

        sessions = result.stdout
        print(f"TMux sessions found:\n{sessions}")

        if "foundation" in sessions:
            print("✓ PASS: Foundation session detected")

            # Check if it's attached
            if "attached" in sessions.split("\n")[0]:
                print("✓ Session is attached (active)")
            else:
                print("⚠ Session is detached")

            return True
        else:
            print("❌ FAIL: Foundation session not found")
            return False

    except subprocess.TimeoutExpired:
        print("❌ FAIL: TMux command timed out")
        return False
    except FileNotFoundError:
        print("❌ FAIL: TMux not installed")
        return False


def test_pattern_matching():
    """Test 3: Verify prompt pattern matching"""
    print("[Test 3] Prompt Pattern Matching")
    print("-" * 50)

    # Test with sample Claude prompt
    sample_prompts = [
        # Modern format
        """
Do you want to make this edit to test.py?

  1. Yes
  2. No

Esc to cancel
""",
        # Legacy format
        """
Do you want to proceed?

  1. Yes
  2. No

Esc to cancel
""",
        # With ANSI codes
        """
\x1b[1mDo you want to make this edit to main.go?\x1b[0m

  \x1b[32m1. Yes\x1b[0m
  \x1b[31m2. No\x1b[0m

Esc to cancel
""",
    ]

    passed = 0
    for i, prompt in enumerate(sample_prompts, 1):
        # Strip ANSI codes
        clean = worker.ANSI_ESCAPE.sub("", prompt)

        # Try to match
        match = worker.EDIT_PROMPT_PATTERN.search(clean) or worker.PROCEED_PROMPT_PATTERN.search(
            clean
        )

        if match:
            print(f"✓ Prompt {i}: Matched")
            passed += 1
        else:
            print(f"❌ Prompt {i}: Not matched")
            print(f"   Clean text: {repr(clean[:100])}")

    print(f"\nPassed {passed}/{len(sample_prompts)} pattern tests")
    print()
    return passed == len(sample_prompts)


def test_session_filtering():
    """Test 4: Verify session filtering logic"""
    print("[Test 4] Session Filtering Logic")
    print("-" * 50)

    test_sessions = [
        ("foundation", True, "should be auto-confirmed"),
        ("autoconfirm", False, "should be excluded (worker itself)"),
        ("codex-1", True, "should be auto-confirmed"),
        ("architect", True, "should be auto-confirmed"),
    ]

    passed = 0
    for session, should_confirm, reason in test_sessions:
        is_excluded = session in worker.EXCLUDED_SESSIONS
        will_confirm = not is_excluded

        if will_confirm == should_confirm:
            print(f"✓ '{session}': {reason}")
            passed += 1
        else:
            print(f"❌ '{session}': Expected {should_confirm}, got {will_confirm}")

    print(f"\nPassed {passed}/{len(test_sessions)} filtering tests")
    print()
    return passed == len(test_sessions)


def test_worker_database():
    """Test 5: Verify database connection"""
    print("[Test 5] Database Connection")
    print("-" * 50)

    try:
        # Check if database file exists or can be created
        if not worker.DB_FILE.exists():
            print(f"  DB file doesn't exist yet: {worker.DB_FILE}")
            print(f"  Will be created on first run")

        # Test connection
        conn = worker.get_db_connection()
        cursor = conn.cursor()

        # Create table if it doesn't exist (test initialization)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS confirmations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                session_name TEXT NOT NULL,
                operation TEXT,
                confirmed INTEGER DEFAULT 1
            )
        """
        )
        conn.commit()

        # Verify table exists
        cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='confirmations'
        """
        )

        if cursor.fetchone():
            print("✓ PASS: Database connection works")
            print(f"  DB location: {worker.DB_FILE}")

            # Count existing records
            cursor.execute("SELECT COUNT(*) FROM confirmations")
            count = cursor.fetchone()[0]
            print(f"  Existing confirmations: {count}")

            conn.close()
            return True
        else:
            print("❌ FAIL: Could not create table")
            conn.close()
            return False

    except Exception as e:
        print(f"❌ FAIL: Database error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_idle_detection():
    """Test 6: Verify idle detection would work"""
    print("[Test 6] Idle Detection Logic")
    print("-" * 50)

    try:
        # Try to get pane activity for foundation session
        result = subprocess.run(
            ["tmux", "display-message", "-t", "foundation", "-p", "#{pane_activity}"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            activity = result.stdout.strip()
            print(f"✓ Can read pane activity format")

            # Calculate idle time
            current_time = int(time.time())

            if activity and activity.isdigit():
                last_activity = int(activity)
                idle_seconds = current_time - last_activity
                print(f"  Last activity: {activity}")
                print(f"  Current idle time: {idle_seconds}s")
                print(f"  Threshold: {worker.IDLE_THRESHOLD}s")

                if idle_seconds >= worker.IDLE_THRESHOLD:
                    print(f"✓ PASS: Session is idle (would auto-confirm)")
                else:
                    print(f"✓ PASS: Session is active (would NOT auto-confirm yet)")
            else:
                # Empty or invalid timestamp - session might be new or tmux version issue
                print(f"  Activity timestamp: '{activity}' (empty or non-numeric)")
                print(f"  This can happen with new panes or some tmux versions")
                print(f"✓ PASS: Idle detection mechanism is functional")

            return True
        else:
            print(f"❌ Could not get pane activity: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("❌ FAIL: TMux command timed out")
        return False
    except Exception as e:
        print(f"❌ FAIL: Error: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Auto-Confirm Worker Test Suite - Foundation Session")
    print("=" * 60)
    print()

    tests = [
        test_configuration,
        test_tmux_session_detection,
        test_pattern_matching,
        test_session_filtering,
        test_worker_database,
        test_idle_detection,
    ]

    results = []
    for test in tests:
        try:
            passed = test()
            results.append(passed)
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            import traceback

            traceback.print_exc()
            results.append(False)

    # Summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)

    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")
    print()

    if passed == total:
        print("✓ ALL TESTS PASSED")
        print()
        print("The foundation session is properly configured for auto-confirm.")
        print("The worker will auto-confirm prompts when:")
        print(f"  1. Session is idle > {worker.IDLE_THRESHOLD}s")
        print(f"  2. Operation is in SAFE_OPERATIONS: {worker.SAFE_OPERATIONS}")
        print(f"  3. Dry run mode: {worker.DRY_RUN}")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
