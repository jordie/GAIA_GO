#!/usr/bin/env python3
"""
Test Campaign Manager

Create, execute, and track comprehensive test campaigns.

Usage:
    ./scripts/test_campaign.py create <campaign_name> <environment>
    ./scripts/test_campaign.py run <campaign_name> [--category <category>]
    ./scripts/test_campaign.py status <campaign_name>
    ./scripts/test_campaign.py list
    ./scripts/test_campaign.py report <campaign_name>
"""

import json
import os
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "architect.db"
RESULTS_DIR = BASE_DIR / "test_results"

# ANSI colors
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"


def get_db():
    """Get database connection."""
    return sqlite3.connect(DB_PATH)


def create_campaign(campaign_name, environment, category="all", triggered_by="manual"):
    """Create a new test campaign."""
    run_id = f"{campaign_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO test_runs (
                run_id, environment, triggered_by, trigger_type,
                category, status
            ) VALUES (?, ?, ?, 'manual', ?, 'pending')
        """,
            (run_id, environment, triggered_by, category),
        )
        conn.commit()

        print(f"{GREEN}✓ Created test campaign: {run_id}{RESET}")
        print(f"  Environment: {environment}")
        print(f"  Category: {category}")
        print(f"  Triggered by: {triggered_by}")
        print(f"\n{BOLD}Next steps:{RESET}")
        print(f"  1. Start test environment: ./env_manager.py start {environment}")
        print(f"  2. Run campaign: ./scripts/test_campaign.py run {campaign_name}")

        return run_id
    except sqlite3.IntegrityError as e:
        print(f"{RED}✗ Campaign already exists or database error: {e}{RESET}")
        return None
    finally:
        conn.close()


def run_campaign(campaign_name, category=None):
    """Execute test campaign."""
    # Find most recent campaign with this name
    conn = get_db()
    cursor = conn.execute(
        """
        SELECT run_id, environment, category
        FROM test_runs
        WHERE run_id LIKE ? AND status = 'pending'
        ORDER BY started_at DESC
        LIMIT 1
    """,
        (f"{campaign_name}%",),
    )
    row = cursor.fetchone()

    if not row:
        print(f"{RED}✗ No pending campaign found with name: {campaign_name}{RESET}")
        print("  Create one first with: ./scripts/test_campaign.py create <name> <env>")
        conn.close()
        return False

    run_id, environment, db_category = row
    test_category = category or db_category

    print(f"{BOLD}=== Running Test Campaign ==={RESET}")
    print(f"  Run ID: {run_id}")
    print(f"  Environment: {environment}")
    print(f"  Category: {test_category}\n")

    # Update status to running
    conn.execute(
        """
        UPDATE test_runs
        SET status = 'running', started_at = CURRENT_TIMESTAMP
        WHERE run_id = ?
    """,
        (run_id,),
    )
    conn.commit()
    conn.close()

    # Create results directory
    RESULTS_DIR.mkdir(exist_ok=True)
    xml_file = RESULTS_DIR / f"{run_id}.xml"
    log_file = RESULTS_DIR / f"{run_id}.log"

    # Build pytest command
    test_markers = {
        "unit": "-m 'not integration and not e2e and not slow'",
        "integration": "-m integration",
        "e2e": "-m e2e",
        "slow": "-m slow",
        "all": "",
    }

    marker = test_markers.get(test_category, "")
    cmd = f"python3 -m pytest tests/ {marker} -v --junit-xml={xml_file} --tb=short"

    print(f"{CYAN}Executing: {cmd}{RESET}\n")

    # Run tests
    try:
        with open(log_file, "w") as log:
            result = subprocess.run(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            output = result.stdout
            log.write(output)
            print(output)

        # Parse results
        parse_results(run_id, xml_file, log_file)

        print(f"\n{BOLD}=== Campaign Complete ==={RESET}")
        print(f"  Results: {xml_file}")
        print(f"  Log: {log_file}")
        print(f"\n  View results: ./scripts/test_campaign.py report {campaign_name}")

        return True

    except Exception as e:
        print(f"\n{RED}✗ Campaign failed: {e}{RESET}")

        # Mark as failed
        conn = get_db()
        conn.execute(
            """
            UPDATE test_runs
            SET status = 'failed', completed_at = CURRENT_TIMESTAMP,
                output = ?
            WHERE run_id = ?
        """,
            (str(e), run_id),
        )
        conn.commit()
        conn.close()

        return False


def parse_results(run_id, xml_file, log_file):
    """Parse JUnit XML and store results in database."""
    conn = get_db()

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        total_tests = 0
        passed = 0
        failed = 0
        skipped = 0
        errors = 0
        total_duration = 0

        # Parse test results
        for testsuite in root.findall("testsuite"):
            for testcase in testsuite.findall("testcase"):
                total_tests += 1
                test_name = testcase.get("name")
                test_file = testcase.get("file")
                test_class = testcase.get("classname")
                duration = float(testcase.get("time", 0))
                total_duration += duration

                # Determine status
                failure = testcase.find("failure")
                error_elem = testcase.find("error")
                skip = testcase.find("skipped")

                if failure is not None:
                    status = "failed"
                    failed += 1
                    error_msg = failure.get("message")
                    stack_trace = failure.text
                elif error_elem is not None:
                    status = "error"
                    errors += 1
                    error_msg = error_elem.get("message")
                    stack_trace = error_elem.text
                elif skip is not None:
                    status = "skipped"
                    skipped += 1
                    error_msg = None
                    stack_trace = None
                else:
                    status = "passed"
                    passed += 1
                    error_msg = None
                    stack_trace = None

                # Store test result
                conn.execute(
                    """
                    INSERT INTO test_results (
                        run_id, test_name, test_file, test_class,
                        status, duration_seconds, error_message, stack_trace
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        run_id,
                        test_name,
                        test_file,
                        test_class,
                        status,
                        duration,
                        error_msg,
                        stack_trace,
                    ),
                )

        # Read full log
        with open(log_file, "r") as f:
            log_output = f.read()

        # Update test_runs with summary
        conn.execute(
            """
            UPDATE test_runs
            SET total_tests = ?, passed = ?, failed = ?,
                skipped = ?, errors = ?, duration_seconds = ?,
                status = 'completed', completed_at = CURRENT_TIMESTAMP,
                output = ?
            WHERE run_id = ?
        """,
            (total_tests, passed, failed, skipped, errors, total_duration, log_output, run_id),
        )

        conn.commit()

        # Print summary
        pass_rate = (passed / total_tests * 100) if total_tests > 0 else 0
        print(f"\n{BOLD}=== Test Summary ==={RESET}")
        print(f"  Total: {total_tests}")
        print(f"  {GREEN}Passed: {passed}{RESET}")
        print(f"  {RED}Failed: {failed}{RESET}")
        print(f"  {YELLOW}Skipped: {skipped}{RESET}")
        print(f"  {RED}Errors: {errors}{RESET}")
        print(f"  Duration: {total_duration:.2f}s")
        print(f"  Pass Rate: {pass_rate:.1f}%")

    except Exception as e:
        print(f"{RED}✗ Error parsing results: {e}{RESET}")
        conn.execute(
            """
            UPDATE test_runs
            SET status = 'error', completed_at = CURRENT_TIMESTAMP
            WHERE run_id = ?
        """,
            (run_id,),
        )
        conn.commit()
    finally:
        conn.close()


def get_campaign_status(campaign_name):
    """Get status of a test campaign."""
    conn = get_db()
    cursor = conn.execute(
        """
        SELECT run_id, environment, category, triggered_by,
               status, total_tests, passed, failed, skipped, errors,
               duration_seconds, started_at, completed_at
        FROM test_runs
        WHERE run_id LIKE ?
        ORDER BY started_at DESC
        LIMIT 1
    """,
        (f"{campaign_name}%",),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        print(f"{RED}✗ Campaign not found: {campaign_name}{RESET}")
        return

    (
        run_id,
        env,
        category,
        triggered_by,
        status,
        total,
        passed,
        failed,
        skipped,
        errors,
        duration,
        started,
        completed,
    ) = row

    status_color = GREEN if status == "completed" else YELLOW if status == "running" else RED

    print(f"\n{BOLD}=== Campaign Status ==={RESET}")
    print(f"  Run ID: {run_id}")
    print(f"  Environment: {env}")
    print(f"  Category: {category}")
    print(f"  Triggered by: {triggered_by}")
    print(f"  Status: {status_color}{status}{RESET}")

    if status in ["completed", "failed"]:
        pass_rate = (passed / total * 100) if total and total > 0 else 0
        print(f"\n{BOLD}Results:{RESET}")
        print(f"  Total: {total}")
        print(f"  {GREEN}Passed: {passed}{RESET}")
        print(f"  {RED}Failed: {failed}{RESET}")
        print(f"  {YELLOW}Skipped: {skipped}{RESET}")
        print(f"  {RED}Errors: {errors}{RESET}")
        print(f"  Duration: {duration:.2f}s" if duration else "  Duration: N/A")
        print(f"  Pass Rate: {pass_rate:.1f}%")

    print(f"\n{BOLD}Timeline:{RESET}")
    print(f"  Started: {started}")
    if completed:
        print(f"  Completed: {completed}")


def list_campaigns():
    """List all test campaigns."""
    conn = get_db()
    cursor = conn.execute(
        """
        SELECT run_id, environment, category, status,
               total_tests, passed, failed,
               started_at, completed_at
        FROM test_runs
        ORDER BY started_at DESC
        LIMIT 20
    """
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print(f"{DIM}No test campaigns found.{RESET}")
        return

    print(f"\n{BOLD}=== Test Campaigns ==={RESET}")
    print(f"{'RUN ID':<40} {'ENV':<10} {'CATEGORY':<12} {'STATUS':<12} {'TESTS':<8} PASS RATE")
    print("-" * 100)

    for row in rows:
        run_id, env, category, status, total, passed, failed, started, completed = row

        pass_rate = (passed / total * 100) if total and total > 0 else 0
        status_color = GREEN if status == "completed" else YELLOW if status == "running" else RED

        test_summary = f"{total or 0} tests" if total else "N/A"
        rate_str = f"{pass_rate:.1f}%" if total else "N/A"

        print(
            f"{run_id:<40} {env:<10} {category:<12} {status_color}{status:<12}{RESET} {test_summary:<8} {rate_str}"
        )


def generate_report(campaign_name):
    """Generate detailed test report."""
    conn = get_db()

    # Get campaign summary
    cursor = conn.execute(
        """
        SELECT run_id, environment, category, triggered_by,
               status, total_tests, passed, failed, skipped, errors,
               duration_seconds, started_at, completed_at
        FROM test_runs
        WHERE run_id LIKE ?
        ORDER BY started_at DESC
        LIMIT 1
    """,
        (f"{campaign_name}%",),
    )
    summary = cursor.fetchone()

    if not summary:
        print(f"{RED}✗ Campaign not found: {campaign_name}{RESET}")
        conn.close()
        return

    run_id = summary[0]

    # Get failed tests
    cursor = conn.execute(
        """
        SELECT test_name, test_file, error_message, duration_seconds
        FROM test_results
        WHERE run_id = ? AND status = 'failed'
        ORDER BY duration_seconds DESC
    """,
        (run_id,),
    )
    failed_tests = cursor.fetchall()

    # Get slowest tests
    cursor = conn.execute(
        """
        SELECT test_name, test_file, duration_seconds
        FROM test_results
        WHERE run_id = ?
        ORDER BY duration_seconds DESC
        LIMIT 10
    """,
        (run_id,),
    )
    slow_tests = cursor.fetchall()

    conn.close()

    # Generate report
    (
        run_id,
        env,
        category,
        triggered_by,
        status,
        total,
        passed,
        failed_count,
        skipped,
        errors,
        duration,
        started,
        completed,
    ) = summary

    pass_rate = (passed / total * 100) if total and total > 0 else 0

    print(f"\n{BOLD}{'=' * 80}{RESET}")
    print(f"{BOLD}TEST CAMPAIGN REPORT{RESET}")
    print(f"{BOLD}{'=' * 80}{RESET}\n")

    print(f"{BOLD}Campaign: {run_id}{RESET}")
    print(f"Environment: {env}")
    print(f"Category: {category}")
    print(f"Triggered by: {triggered_by}")
    print(f"Status: {status}")
    print(f"Started: {started}")
    print(f"Completed: {completed or 'N/A'}\n")

    print(f"{BOLD}Summary:{RESET}")
    print(f"  Total Tests: {total}")
    print(
        f"  {GREEN}Passed: {passed} ({passed/total*100:.1f}%){RESET}" if total else "  Passed: N/A"
    )
    print(
        f"  {RED}Failed: {failed_count} ({failed_count/total*100:.1f}%){RESET}"
        if total
        else "  Failed: N/A"
    )
    print(f"  {YELLOW}Skipped: {skipped}{RESET}")
    print(f"  {RED}Errors: {errors}{RESET}")
    print(f"  Duration: {duration:.2f}s" if duration else "  Duration: N/A")
    print(
        f"  Pass Rate: {GREEN if pass_rate >= 90 else YELLOW if pass_rate >= 75 else RED}{pass_rate:.1f}%{RESET}\n"
    )

    if failed_tests:
        print(f"{BOLD}Failed Tests ({len(failed_tests)}):{RESET}")
        for test_name, test_file, error, dur in failed_tests:
            print(f"  {RED}✗{RESET} {test_name}")
            print(f"    File: {test_file}")
            if error:
                # Truncate long error messages
                error_short = error[:100] + "..." if len(error) > 100 else error
                print(f"    Error: {error_short}")
            print(f"    Duration: {dur:.3f}s\n")

    print(f"{BOLD}Slowest Tests (Top 10):{RESET}")
    for test_name, test_file, dur in slow_tests:
        print(f"  {test_name}: {dur:.3f}s")
        print(f"    {DIM}{test_file}{RESET}\n")

    print(f"{BOLD}{'=' * 80}{RESET}\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "create" and len(sys.argv) >= 4:
        campaign_name = sys.argv[2]
        environment = sys.argv[3]
        category = sys.argv[4] if len(sys.argv) >= 5 else "all"
        triggered_by = sys.argv[5] if len(sys.argv) >= 6 else "manual"
        create_campaign(campaign_name, environment, category, triggered_by)

    elif cmd == "run" and len(sys.argv) >= 3:
        campaign_name = sys.argv[2]
        category = None
        if "--category" in sys.argv:
            category = sys.argv[sys.argv.index("--category") + 1]
        run_campaign(campaign_name, category)

    elif cmd == "status" and len(sys.argv) >= 3:
        campaign_name = sys.argv[2]
        get_campaign_status(campaign_name)

    elif cmd == "list":
        list_campaigns()

    elif cmd == "report" and len(sys.argv) >= 3:
        campaign_name = sys.argv[2]
        generate_report(campaign_name)

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
