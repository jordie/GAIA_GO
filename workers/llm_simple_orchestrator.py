#!/usr/bin/env python3
"""
Simple LLM Test Orchestrator

Directly integrates with assigner worker to test LLM code generation.
No complex async framework - just send prompt, wait for files, verify.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_connection

# LLM Provider configurations
PROVIDERS = [
    {"name": "Claude", "session": "architect", "type": "claude"},
    {"name": "Codex", "session": "claude_codex", "type": "codex"},
    {"name": "Claude-Architect", "session": "claude_architect", "type": "claude"},
    {"name": "Comet", "session": "claude_comet", "type": "comet"},
    # Add more providers for testing
    # {'name': 'AnythingLLM', 'session': 'anythingllm', 'type': 'anythingllm'},
    # {'name': 'Ollama-Codellama', 'api_url': 'http://localhost:11434/api/generate', 'model': 'codellama:7b-instruct', 'type': 'ollama'},
]

# Simplified prompt for rapid testing
RAPID_PROMPT = """Create a minimal TODO app in {output_dir} (under 300 lines total):

Files (EXACTLY these, no extras):
1. app.py - Flask backend with in-memory SQLite:
   - GET /health → {{"status": "ok"}}
   - GET /api/todos → [{{id, text, completed}}, ...]
   - POST /api/todos {{"text": "..."}} → {{id, text, completed}}
   - DELETE /api/todos/<id> → {{"success": true}}

2. index.html - Single page with:
   - Input field + Add button
   - Todo list (checkbox + delete button per item)
   - Uses fetch() to call API

3. style.css - Simple, clean styling

4. requirements.txt - Just: flask flask-cors

5. test_api.py - Test health and todo endpoints

6. README.md - Quick start (3 commands)

Rules:
- NO login/auth
- NO sessions
- SQLite in-memory only
- CORS enabled
- Each file under 100 lines
- Total under 300 lines
- Be FAST (target: 2 minutes)

Generate NOW in {output_dir}.
"""


def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level:8s}] {msg}")


def check_session_idle(session_name):
    """Check if tmux session is idle"""
    try:
        cmd = f"tmux capture-pane -t {session_name} -p"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)

        if result.returncode != 0:
            return False

        output = result.stdout.lower()
        # Look for idle indicators (both ASCII and Unicode prompts)
        idle_indicators = [">", "how can i help", "claude>", "$", "#", "❯"]
        is_idle = any(indicator in output for indicator in idle_indicators)

        # Check not busy
        busy_indicators = ["thinking", "analyzing", "processing", "running"]
        is_busy = any(indicator in output for indicator in busy_indicators)

        return is_idle and not is_busy
    except Exception as e:
        log(f"Error checking session {session_name}: {e}", "ERROR")
        return False


def send_to_tmux_directly(session_name, prompt):
    """Send prompt directly to tmux session (bypass API auth issue)"""
    try:
        # Escape special characters
        escaped = (
            prompt.replace('"', '\\"').replace("$", "\\$").replace("`", "\\`").replace("\\", "\\\\")
        )

        # Send text to tmux session (without Enter)
        cmd = f'tmux send-keys -t {session_name} "{escaped}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            log(f"  Failed to send text to tmux: {result.stderr}", "ERROR")
            return False

        # Send Enter separately to ensure it's processed
        cmd_enter = f"tmux send-keys -t {session_name} Enter"
        result_enter = subprocess.run(
            cmd_enter, shell=True, capture_output=True, text=True, timeout=5
        )

        if result_enter.returncode == 0:
            log(f"  Sent directly to tmux session: {session_name}")
            return True
        else:
            log(f"  Failed to send Enter to tmux: {result_enter.stderr}", "ERROR")
            return False
    except Exception as e:
        log(f"Failed to send to tmux: {e}", "ERROR")
        return False


def wait_for_files(output_dir, min_files=3, max_wait=180, check_interval=3):
    """Wait for files to appear in output directory"""
    output_path = Path(output_dir)
    start_time = time.time()

    log(f"Waiting for files in {output_dir}...")

    while True:
        elapsed = time.time() - start_time

        if elapsed > max_wait:
            log(f"Timeout after {elapsed:.0f}s", "WARNING")
            return False

        # Check if directory exists and has files
        if output_path.exists():
            files = [f for f in output_path.iterdir() if f.is_file() and not f.name.startswith(".")]

            if len(files) >= min_files:
                log(f"Found {len(files)} files after {elapsed:.0f}s")
                return True

            if len(files) > 0:
                log(f"  Progress: {len(files)} files so far...", "DEBUG")

        # Log progress every 30 seconds
        if int(elapsed) % 30 == 0 and elapsed > 0:
            log(f"  Still waiting... ({elapsed:.0f}s elapsed)")

        time.sleep(check_interval)


def validate_task_timing(duration, status, files_created, reason=None):
    """Detect timing anomalies that indicate errors"""
    anomalies = []

    # Too fast - likely failed
    if duration < 5 and status in ["completed", "failed"]:
        if files_created == 0:
            anomalies.append("ANOMALY: Completed too quickly (<5s) with 0 files - likely failure")
        elif status == "completed":
            anomalies.append("ANOMALY: Completed suspiciously fast (<5s)")

    # Too slow - likely hanging
    if duration > 300:
        anomalies.append("ANOMALY: Taking too long (>5min) - possible hang or stalled generation")

    # Completed but no files
    if status == "completed" and files_created == 0:
        anomalies.append("ANOMALY: Status=completed but 0 files generated - error")

    # Failed session busy but took time
    if reason == "session_busy" and duration > 5:
        anomalies.append("ANOMALY: Session busy check took >5s - possible detection issue")

    # Reasonable execution time for successful generation (60-180s expected)
    if status == "completed" and files_created >= 4:
        if duration < 30:
            anomalies.append("INFO: Generated files in <30s - very fast")
        elif duration > 240:
            anomalies.append("WARNING: Generation took >4min - slower than expected")

    return anomalies


def verify_output(output_dir):
    """Verify generated files meet basic requirements"""
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

    # Basic validation
    has_app_py = any(f["name"] == "app.py" for f in files)
    has_html = any(f["name"] == "index.html" for f in files)
    lines_ok = 0 < total_lines <= 300
    min_files = len(files) >= 4

    passed = has_app_py and has_html and lines_ok and min_files

    return {
        "exists": True,
        "files": files,
        "total_lines": total_lines,
        "total_bytes": total_bytes,
        "passed": passed,
        "checks": {
            "has_app_py": has_app_py,
            "has_html": has_html,
            "lines_ok": lines_ok,
            "min_files": min_files,
        },
    }


def run_test(provider, test_run_id):
    """Run single provider test"""
    log("=" * 80)
    log(f"TESTING: {provider['name']}")
    log("=" * 80)

    output_dir = f"/tmp/llm_simple_test_{provider['name'].lower().replace(' ', '_').replace('-', '_')}_{test_run_id}"

    # Clean previous test
    if Path(output_dir).exists():
        log(f"Cleaning previous test: {output_dir}")
        shutil.rmtree(output_dir)

    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Create test result entry
    with get_connection("main") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO llm_test_results
            (test_run_id, provider_name, session_name, status, started_at, output_path)
            VALUES (?, ?, ?, 'running', CURRENT_TIMESTAMP, ?)
        """,
            (test_run_id, provider["name"], provider.get("session"), output_dir),
        )
        result_id = cursor.lastrowid

    start_time = time.time()

    # Check if session is idle
    if provider.get("session"):
        log(f"Checking session: {provider['session']}")
        if not check_session_idle(provider["session"]):
            log(f"  Session is BUSY", "WARNING")

            duration = int(time.time() - start_time)

            # Validate timing
            anomalies = validate_task_timing(duration, "failed", 0, reason="session_busy")
            for anomaly in anomalies:
                log(f"  {anomaly}", "WARNING")

            with get_connection("main") as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE llm_test_results
                    SET status = 'failed',
                        error_message = 'Session busy',
                        completed_at = CURRENT_TIMESTAMP,
                        duration_seconds = ?,
                        metadata = ?
                    WHERE id = ?
                """,
                    (duration, json.dumps({"anomalies": anomalies}), result_id),
                )

            return {"success": False, "reason": "session_busy", "duration": duration}

        log(f"  Session is IDLE ✓")

    # Send prompt
    log(f"Sending prompt to {provider['name']}...")
    prompt_send_start = time.time()
    prompt = RAPID_PROMPT.format(output_dir=output_dir)

    if provider.get("session"):
        # Send directly to tmux session (bypass API auth)
        if not send_to_tmux_directly(provider["session"], prompt):
            log(f"  Failed to send to session", "ERROR")
            prompt_send_time = time.time() - prompt_send_start
            duration = int(time.time() - start_time)

            # Validate timing
            anomalies = validate_task_timing(duration, "failed", 0, reason="send_failed")
            for anomaly in anomalies:
                log(f"  {anomaly}", "WARNING")

            with get_connection("main") as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE llm_test_results
                    SET status = 'failed',
                        error_message = 'Failed to send prompt to tmux session',
                        completed_at = CURRENT_TIMESTAMP,
                        duration_seconds = ?,
                        metadata = ?
                    WHERE id = ?
                """,
                    (
                        duration,
                        json.dumps({"prompt_send_time": prompt_send_time, "anomalies": anomalies}),
                        result_id,
                    ),
                )

            return {"success": False, "reason": "send_failed", "duration": duration}

        prompt_send_time = time.time() - prompt_send_start
        log(f"  Prompt sent successfully ({prompt_send_time:.2f}s)")
    else:
        log(f"  API-based providers not yet implemented", "WARNING")
        return {"success": False, "reason": "not_implemented"}

    # Wait for file generation
    log(f"Monitoring for files (max 3 minutes)...")
    generation_start = time.time()

    if not wait_for_files(output_dir, min_files=4, max_wait=180, check_interval=3):
        generation_time = time.time() - generation_start
        duration = int(time.time() - start_time)
        log(f"  ✗ Timeout after {duration}s", "WARNING")

        verification = verify_output(output_dir)
        files_created = len(verification["files"]) if verification["exists"] else 0

        # Validate timing
        anomalies = validate_task_timing(duration, "timeout", files_created, reason="timeout")
        for anomaly in anomalies:
            log(f"  {anomaly}", "WARNING")

        # Track timing at each level
        timing = {
            "session_check_time": 0,  # Minimal
            "prompt_send_time": prompt_send_time,
            "generation_time": generation_time,
            "verification_time": 0,  # Minimal for timeout
            "total_time": duration,
        }

        with get_connection("main") as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE llm_test_results
                SET status = 'timeout',
                    completed_at = CURRENT_TIMESTAMP,
                    duration_seconds = ?,
                    files_created = ?,
                    total_lines = ?,
                    total_bytes = ?,
                    test_passed = 0,
                    error_message = 'Timeout waiting for file generation',
                    metadata = ?
                WHERE id = ?
            """,
                (
                    duration,
                    files_created,
                    verification.get("total_lines", 0),
                    verification.get("total_bytes", 0),
                    json.dumps({**verification, "timing": timing, "anomalies": anomalies}),
                    result_id,
                ),
            )

        return {"success": False, "reason": "timeout", "duration": duration, "files": files_created}

    # Verify output
    generation_time = time.time() - generation_start
    verification_start = time.time()
    verification = verify_output(output_dir)
    verification_time = time.time() - verification_start
    duration = int(time.time() - start_time)

    log(f"  ✓ Generation complete! ({duration}s)")
    log(f"    Files: {len(verification['files'])}")
    log(f"    Lines: {verification['total_lines']}")
    log(f"    Bytes: {verification['total_bytes']}")
    log(f"    Passed: {'✓' if verification['passed'] else '✗'}")

    # Validate timing
    anomalies = validate_task_timing(duration, "completed", len(verification["files"]))
    if anomalies:
        log(f"    Timing Analysis:")
        for anomaly in anomalies:
            # Determine log level based on anomaly type
            level = "WARNING" if "ANOMALY" in anomaly or "WARNING" in anomaly else "INFO"
            log(f"      {anomaly}", level)

    # Track timing at each level
    timing = {
        "session_check_time": 0,  # Minimal, sub-second
        "prompt_send_time": prompt_send_time,
        "generation_time": generation_time,
        "verification_time": verification_time,
        "total_time": duration,
    }

    log(f"    Timing:")
    log(f"      Prompt send: {prompt_send_time:.2f}s")
    log(f"      Generation: {generation_time:.2f}s")
    log(f"      Verification: {verification_time:.2f}s")
    log(f"      Total: {duration}s")

    if verification["checks"]:
        log(f"    Checks:")
        for check, result in verification["checks"].items():
            log(f"      {check}: {'✓' if result else '✗'}")

    # Update result
    with get_connection("main") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE llm_test_results
            SET status = 'completed',
                completed_at = CURRENT_TIMESTAMP,
                duration_seconds = ?,
                files_created = ?,
                total_lines = ?,
                total_bytes = ?,
                test_passed = ?,
                metadata = ?
            WHERE id = ?
        """,
            (
                duration,
                len(verification["files"]),
                verification["total_lines"],
                verification["total_bytes"],
                verification["passed"],
                json.dumps({**verification, "timing": timing, "anomalies": anomalies}),
                result_id,
            ),
        )

    log(f"  Overall: {'✅ PASS' if verification['passed'] else '⚠️  PARTIAL'}")
    log("")

    return {
        "success": True,
        "duration": duration,
        "files": len(verification["files"]),
        "lines": verification["total_lines"],
        "passed": verification["passed"],
    }


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Simple LLM Test Orchestrator")
    parser.add_argument("--providers", nargs="+", help="Specific providers to test")
    parser.add_argument("--test-name", default="Simple TODO Test", help="Test name")

    args = parser.parse_args()

    log("=" * 80)
    log("SIMPLE LLM TEST ORCHESTRATOR")
    log("=" * 80)
    log("Direct integration with assigner worker")
    log("")

    # Create test run
    with get_connection("main") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO llm_test_runs
            (test_name, description, prompt_template, max_lines, created_by)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                args.test_name,
                "Simple rapid test with direct assigner integration",
                RAPID_PROMPT,
                300,
                "simple_orchestrator",
            ),
        )
        test_run_id = cursor.lastrowid

    log(f"Test Run ID: {test_run_id}")
    log("")

    # Filter providers
    providers = PROVIDERS
    if args.providers:
        providers = [p for p in PROVIDERS if p["name"] in args.providers]

    log(f"Testing {len(providers)} providers")
    log("")

    results = []

    for idx, provider in enumerate(providers, 1):
        log(f"[{idx}/{len(providers)}] {provider['name']}")

        result = run_test(provider, test_run_id)
        results.append({"provider": provider["name"], **result})

        # Wait between tests
        if idx < len(providers):
            log("Waiting 10 seconds before next test...")
            time.sleep(10)
            log("")

    # Summary
    log("=" * 80)
    log("TEST SUMMARY")
    log("=" * 80)
    log("")

    successful = [r for r in results if r.get("success")]

    log(f"Success Rate: {len(successful)}/{len(results)} ({len(successful)/len(results)*100:.1f}%)")
    log("")

    if successful:
        log("Successful Tests:")
        for r in successful:
            status = "✅ PASS" if r.get("passed") else "⚠️  PARTIAL"
            log(
                f"  {status} {r['provider']}: {r.get('duration')}s, {r.get('files')} files, {r.get('lines')} lines"
            )

    log("")

    failed = [r for r in results if not r.get("success")]
    if failed:
        log("Failed Tests:")
        for r in failed:
            log(f"  ✗ FAIL {r['provider']}: {r.get('reason', 'unknown')}")

    log("")
    log("Results saved to database")
    log("View on dashboard: http://localhost:8080/#llm-tests")
    log("=" * 80)

    return 0 if len(successful) > 0 else 1


if __name__ == "__main__":
    exit(main())
