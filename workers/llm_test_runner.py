#!/usr/bin/env python3
"""
LLM Provider Test Runner
Runs standardized tests across different LLM providers and stores results
"""

import json
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

from db import get_connection

DB_TYPE = "main"

# Available providers
PROVIDERS = [
    {"name": "Claude", "session": "architect", "type": "claude"},
    {"name": "Codex", "session": "codex", "type": "codex"},
    {"name": "Claude-Architect", "session": "claude_architect", "type": "claude"},
    {"name": "Comet", "session": "claude_comet", "type": "comet"},
]


def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level:8s}] {msg}")


def get_test_run(test_name):
    """Get test run configuration"""
    with get_connection(DB_TYPE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, prompt_template, max_lines FROM llm_test_runs WHERE test_name = ?",
            (test_name,),
        )
        result = cursor.fetchone()
        return dict(result) if result else None


def create_test_result(test_run_id, provider_name, session_name):
    """Create a new test result entry"""
    with get_connection(DB_TYPE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO llm_test_results
               (test_run_id, provider_name, session_name, status, started_at)
               VALUES (?, ?, ?, 'pending', CURRENT_TIMESTAMP)""",
            (test_run_id, provider_name, session_name),
        )
        return cursor.lastrowid


def update_test_result(result_id, status, **kwargs):
    """Update test result"""
    with get_connection(DB_TYPE) as conn:
        cursor = conn.cursor()

        fields = ["status = ?"]
        values = [status]

        if status in ["completed", "failed", "timeout"]:
            fields.append("completed_at = CURRENT_TIMESTAMP")

        for key, value in kwargs.items():
            fields.append(f"{key} = ?")
            values.append(value)

        values.append(result_id)

        query = f"UPDATE llm_test_results SET {', '.join(fields)} WHERE id = ?"
        cursor.execute(query, values)


def send_to_session(session_name, prompt):
    """Send prompt to tmux session"""
    escaped = prompt.replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
    cmd = f'tmux send-keys -t {session_name} "{escaped}" Enter'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0


def check_session_idle(session_name):
    """Check if session is idle"""
    cmd = f"tmux capture-pane -t {session_name} -p"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        return False

    output = result.stdout.lower()
    idle_indicators = [">", "how can i help", "claude>", "$", "#"]
    return any(indicator in output for indicator in idle_indicators)


def verify_output(output_dir, max_lines):
    """Verify generated output"""
    output_path = Path(output_dir)

    if not output_path.exists():
        return {"exists": False, "files": [], "total_lines": 0, "total_bytes": 0, "passed": False}

    files = []
    total_lines = 0
    total_bytes = 0

    for file in output_path.iterdir():
        if file.is_file() and not file.name.startswith("."):
            size = file.stat().st_size
            try:
                lines = len(file.read_text().splitlines())
            except:
                lines = 0

            files.append({"name": file.name, "size": size, "lines": lines})
            total_lines += lines
            total_bytes += size

    passed = (
        len(files) >= 3
        and total_lines > 0  # At least 3 files
        and total_lines <= max_lines
        and total_bytes > 0
    )

    return {
        "exists": True,
        "files": files,
        "total_lines": total_lines,
        "total_bytes": total_bytes,
        "passed": passed,
    }


def run_test_for_provider(test_run, provider, result_id):
    """Run test for a specific provider"""
    log(f"Testing provider: {provider['name']}")

    # Prepare output directory
    output_dir = f"/tmp/llm_test_{provider['name'].lower().replace(' ', '_').replace('-', '_')}"
    if Path(output_dir).exists():
        shutil.rmtree(output_dir)
    Path(output_dir).mkdir(parents=True)

    # Update status to running
    update_test_result(result_id, "running", output_path=output_dir)

    # Check if session is idle
    if not check_session_idle(provider["session"]):
        log(f"  Session {provider['session']} is busy", "WARNING")
        update_test_result(
            result_id, "failed", error_message="Session busy - not available", duration_seconds=0
        )
        return False

    # Prepare prompt
    prompt = test_run["prompt_template"].format(
        output_dir=output_dir, max_lines=test_run["max_lines"]
    )

    # Send to session
    log(f"  Sending prompt to {provider['session']}")
    start_time = time.time()

    if not send_to_session(provider["session"], prompt):
        log(f"  Failed to send to session", "ERROR")
        update_test_result(
            result_id,
            "failed",
            error_message="Failed to send prompt to session",
            duration_seconds=int(time.time() - start_time),
        )
        return False

    # Monitor for completion (max 3 minutes)
    log(f"  Monitoring output (max 3 minutes)...")
    timeout = 180
    check_interval = 5

    for elapsed in range(0, timeout, check_interval):
        time.sleep(check_interval)

        verification = verify_output(output_dir, test_run["max_lines"])

        if verification["exists"] and len(verification["files"]) >= 3:
            duration = int(time.time() - start_time)

            log(f"  ✓ Generation complete! ({duration}s)")
            log(f"    Files: {len(verification['files'])}")
            log(f"    Lines: {verification['total_lines']}")
            log(f"    Bytes: {verification['total_bytes']}")

            # Update result
            update_test_result(
                result_id,
                "completed",
                files_created=len(verification["files"]),
                total_lines=verification["total_lines"],
                total_bytes=verification["total_bytes"],
                test_passed=verification["passed"],
                duration_seconds=duration,
                metadata=json.dumps(verification),
            )

            return True

        if elapsed > 0 and elapsed % 30 == 0:
            log(f"    Still waiting... ({elapsed}s)")

    # Timeout
    duration = int(time.time() - start_time)
    verification = verify_output(output_dir, test_run["max_lines"])

    log(f"  ✗ Timeout after {duration}s", "WARNING")

    update_test_result(
        result_id,
        "timeout",
        files_created=len(verification["files"]) if verification["exists"] else 0,
        total_lines=verification["total_lines"] if verification["exists"] else 0,
        total_bytes=verification["total_bytes"] if verification["exists"] else 0,
        test_passed=False,
        duration_seconds=duration,
        error_message="Timeout waiting for generation",
        metadata=json.dumps(verification) if verification["exists"] else None,
    )

    return False


def run_test(test_name, providers=None):
    """Run test across multiple providers"""
    log("=" * 80)
    log(f"LLM Provider Test: {test_name}")
    log("=" * 80)

    # Get test configuration
    test_run = get_test_run(test_name)
    if not test_run:
        log(f"Test '{test_name}' not found", "ERROR")
        return False

    # Use provided providers or default
    test_providers = providers or PROVIDERS

    log(f"Testing {len(test_providers)} providers")
    log(f"Max lines: {test_run['max_lines']}")
    log("")

    results = []

    for idx, provider in enumerate(test_providers, 1):
        log(f"[{idx}/{len(test_providers)}] {provider['name']}")

        # Create result entry
        result_id = create_test_result(test_run["id"], provider["name"], provider["session"])

        # Run test
        success = run_test_for_provider(test_run, provider, result_id)
        results.append({"provider": provider["name"], "success": success})

        log("")

        # Wait between tests
        if idx < len(test_providers):
            log("Waiting 10 seconds before next test...")
            time.sleep(10)
            log("")

    # Summary
    log("=" * 80)
    log("TEST SUMMARY")
    log("=" * 80)

    successful = sum(1 for r in results if r["success"])
    log(f"Success rate: {successful}/{len(results)} ({successful/len(results)*100:.1f}%)")

    for result in results:
        status = "✓ PASS" if result["success"] else "✗ FAIL"
        log(f"  {status} - {result['provider']}")

    log("")
    log("Results saved to database and available on dashboard")
    log("=" * 80)

    return successful == len(results)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="LLM Provider Test Runner")
    parser.add_argument("--test", default="Calculator Web App", help="Test name to run")
    parser.add_argument("--providers", nargs="+", help="Specific providers to test")

    args = parser.parse_args()

    # Filter providers if specified
    providers = PROVIDERS
    if args.providers:
        providers = [p for p in PROVIDERS if p["name"] in args.providers]

    success = run_test(args.test, providers)

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
