#!/usr/bin/env python3
"""
Comprehensive LLM Provider Test
Tests creation, functionality, and SOP compliance across different LLM providers
"""

import json
import os
import shutil
import signal
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

from db import get_connection

# Test configuration
PROVIDERS = [
    {"name": "Claude", "session": "architect", "type": "claude"},
    {"name": "Codex", "session": "codex", "type": "codex"},
    {"name": "Claude-Architect", "session": "claude_architect", "type": "claude"},
    {
        "name": "AnythingLLM",
        "session": None,
        "type": "anything_llm",
        "api": "http://localhost:3001",
    },
    {"name": "Ollama", "session": None, "type": "ollama", "api": "http://localhost:11434"},
    {"name": "Comet", "session": "claude_comet", "type": "comet"},
]

TEST_PROMPT = """Create a simple Calculator web application in {output_dir} with:

Files to create:
1. calculator.html - Main HTML page with calculator interface
2. calculator.js - JavaScript for calculator logic
3. calculator.css - Styling
4. api.py - Python Flask API backend (optional but recommended)
5. test_api.py - API tests
6. README.md - Setup and usage instructions

Requirements:
- Basic arithmetic operations (add, subtract, multiply, divide)
- Display calculation history (last 5 calculations)
- Clear button to reset
- Responsive design
- If you create an API, it should have endpoints for calculations
- Keep it simple and functional
- Total implementation under 1000 lines

Generate ALL files now in {output_dir}.
"""

SOP_CHECKS = {
    "file_structure": {
        "required": ["calculator.html", "calculator.js", "calculator.css"],
        "optional": ["api.py", "test_api.py", "README.md"],
    },
    "max_lines": 1000,
    "min_files": 3,
    "has_tests": lambda files: any("test" in f.lower() for f in files),
    "has_docs": lambda files: any("readme" in f.lower() for f in files),
}


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
        idle_indicators = [">", "how can i help", "claude>", "$", "#"]
        return any(indicator in output for indicator in idle_indicators)
    except:
        return False


def send_to_session(session_name, prompt):
    """Send prompt to tmux session"""
    try:
        escaped = prompt.replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
        cmd = f'tmux send-keys -t {session_name} "{escaped}" Enter'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except:
        return False


def verify_file_structure(output_dir):
    """Verify generated files meet requirements"""
    output_path = Path(output_dir)

    if not output_path.exists():
        return {"exists": False, "files": [], "sop_compliant": False}

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

            files.append({"name": file.name, "size": size, "lines": lines, "path": str(file)})
            total_lines += lines
            total_bytes += size

    # Check SOP compliance
    file_names = [f["name"] for f in files]

    required_met = all(req in file_names for req in SOP_CHECKS["file_structure"]["required"])
    lines_ok = total_lines <= SOP_CHECKS["max_lines"]
    files_ok = len(files) >= SOP_CHECKS["min_files"]
    has_tests = SOP_CHECKS["has_tests"](file_names)
    has_docs = SOP_CHECKS["has_docs"](file_names)

    sop_score = sum(
        [
            required_met * 40,  # 40 points for required files
            lines_ok * 20,  # 20 points for line limit
            files_ok * 20,  # 20 points for min files
            has_tests * 10,  # 10 points for tests
            has_docs * 10,  # 10 points for docs
        ]
    )

    return {
        "exists": True,
        "files": files,
        "total_lines": total_lines,
        "total_bytes": total_bytes,
        "sop_compliant": sop_score >= 80,
        "sop_score": sop_score,
        "checks": {
            "required_files": required_met,
            "line_limit": lines_ok,
            "min_files": files_ok,
            "has_tests": has_tests,
            "has_docs": has_docs,
        },
    }


def test_web_interface(output_dir):
    """Test if HTML/JS works by checking syntax"""
    output_path = Path(output_dir)
    results = {"html_valid": False, "js_valid": False, "css_valid": False}

    # Check HTML
    html_file = output_path / "calculator.html"
    if html_file.exists():
        content = html_file.read_text()
        results["html_valid"] = (
            "<!DOCTYPE html>" in content
            and "<html" in content
            and "</html>" in content
            and "<body" in content
        )

    # Check JS
    js_file = output_path / "calculator.js"
    if js_file.exists():
        content = js_file.read_text()
        results["js_valid"] = "function" in content or "const" in content or "let" in content

    # Check CSS
    css_file = output_path / "calculator.css"
    if css_file.exists():
        content = css_file.read_text()
        results["css_valid"] = "{" in content and "}" in content

    return results


def test_api(output_dir):
    """Test API if it exists"""
    output_path = Path(output_dir)
    api_file = output_path / "api.py"

    if not api_file.exists():
        return {"has_api": False}

    results = {
        "has_api": True,
        "api_startable": False,
        "api_responsive": False,
        "port": None,
        "pid": None,
    }

    try:
        # Try to start the API
        process = subprocess.Popen(
            ["python3", str(api_file)],
            cwd=str(output_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        results["pid"] = process.pid
        results["api_startable"] = True

        # Wait for startup
        time.sleep(3)

        # Try to find port (check common ports)
        for port in [5000, 8000, 8080, 3000]:
            try:
                import urllib.request

                urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
                results["port"] = port
                results["api_responsive"] = True
                break
            except:
                continue

        # Clean up
        os.kill(process.pid, signal.SIGTERM)
        process.wait(timeout=5)

    except Exception as e:
        results["error"] = str(e)

    return results


def run_comprehensive_test(provider, test_run_id):
    """Run comprehensive test for a provider"""
    log(f"=" * 80)
    log(f"TESTING: {provider['name']}")
    log(f"=" * 80)

    output_dir = f"/tmp/llm_test_{provider['name'].lower().replace(' ', '_').replace('-', '_')}"

    # Clean previous test
    if Path(output_dir).exists():
        log(f"Cleaning previous test: {output_dir}")
        shutil.rmtree(output_dir)

    Path(output_dir).mkdir(parents=True)

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

    # Check availability
    if provider["session"]:
        log(f"Checking session: {provider['session']}")
        if not check_session_idle(provider["session"]):
            log(f"  Session is BUSY", "WARNING")

            with get_connection("main") as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE llm_test_results
                    SET status = 'failed',
                        error_message = 'Session busy',
                        completed_at = CURRENT_TIMESTAMP,
                        duration_seconds = ?
                    WHERE id = ?
                """,
                    (int(time.time() - start_time), result_id),
                )

            return {"success": False, "reason": "session_busy"}

    # Send prompt
    log(f"Sending prompt...")
    prompt = TEST_PROMPT.format(output_dir=output_dir)

    if provider["session"]:
        if not send_to_session(provider["session"], prompt):
            log(f"  Failed to send prompt", "ERROR")

            with get_connection("main") as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE llm_test_results
                    SET status = 'failed',
                        error_message = 'Failed to send prompt',
                        completed_at = CURRENT_TIMESTAMP,
                        duration_seconds = ?
                    WHERE id = ?
                """,
                    (int(time.time() - start_time), result_id),
                )

            return {"success": False, "reason": "send_failed"}

    # Monitor for generation (max 3 minutes)
    log(f"Monitoring generation (max 3 minutes)...")
    timeout = 180
    check_interval = 5

    for elapsed in range(0, timeout, check_interval):
        time.sleep(check_interval)

        verification = verify_file_structure(output_dir)

        if verification["exists"] and len(verification["files"]) >= 3:
            duration = int(time.time() - start_time)

            log(f"  ✓ Generation complete! ({duration}s)")
            log(f"    Files: {len(verification['files'])}")
            log(f"    Lines: {verification['total_lines']}")
            log(f"    SOP Score: {verification['sop_score']}/100")

            # Test web interface
            log(f"Testing web interface...")
            web_test = test_web_interface(output_dir)
            log(f"  HTML valid: {'✓' if web_test['html_valid'] else '✗'}")
            log(f"  JS valid: {'✓' if web_test['js_valid'] else '✗'}")
            log(f"  CSS valid: {'✓' if web_test['css_valid'] else '✗'}")

            # Test API if exists
            log(f"Testing API...")
            api_test = test_api(output_dir)
            if api_test["has_api"]:
                log(f"  API exists: ✓")
                log(f"  API startable: {'✓' if api_test['api_startable'] else '✗'}")
                log(f"  API responsive: {'✓' if api_test['api_responsive'] else '✗'}")
            else:
                log(f"  No API generated")

            # Calculate overall score
            web_score = sum(web_test.values())
            api_score = 20 if api_test.get("api_responsive") else 0
            overall_passed = (
                verification["sop_compliant"]
                and web_score >= 2
                and verification["total_lines"] <= 1000
            )

            # Save results
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
                        overall_passed,
                        json.dumps(
                            {
                                "sop_score": verification["sop_score"],
                                "sop_checks": verification["checks"],
                                "web_test": web_test,
                                "api_test": api_test,
                                "files": verification["files"],
                            }
                        ),
                        result_id,
                    ),
                )

            log(f"  Overall: {'✅ PASS' if overall_passed else '⚠️  PARTIAL'}")
            log(f"")

            return {
                "success": True,
                "duration": duration,
                "files": len(verification["files"]),
                "lines": verification["total_lines"],
                "sop_score": verification["sop_score"],
                "overall_passed": overall_passed,
            }

        if elapsed > 0 and elapsed % 30 == 0:
            log(f"    Still waiting... ({elapsed}s)")

    # Timeout
    duration = int(time.time() - start_time)
    log(f"  ✗ Timeout after {duration}s", "WARNING")

    verification = verify_file_structure(output_dir)

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
                error_message = 'Timeout waiting for generation'
            WHERE id = ?
        """,
            (
                duration,
                len(verification["files"]) if verification["exists"] else 0,
                verification.get("total_lines", 0),
                verification.get("total_bytes", 0),
                result_id,
            ),
        )

    log(f"")
    return {"success": False, "reason": "timeout"}


def main():
    """Main test execution"""
    log("=" * 80)
    log("COMPREHENSIVE LLM PROVIDER TEST")
    log("=" * 80)
    log("Testing: Code generation + Functionality + SOP compliance")
    log("")

    # Get test run
    with get_connection("main") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM llm_test_runs WHERE test_name = 'Calculator Web App'")
        test_run = cursor.fetchone()

        if not test_run:
            log("Test run not found!", "ERROR")
            return 1

        test_run_id = test_run[0]

    log(f"Test Run ID: {test_run_id}")
    log(f"Providers to test: {len(PROVIDERS)}")
    log("")

    results = []

    for idx, provider in enumerate(PROVIDERS, 1):
        log(f"[{idx}/{len(PROVIDERS)}] {provider['name']}")

        result = run_comprehensive_test(provider, test_run_id)
        results.append({"provider": provider["name"], **result})

        # Wait between tests
        if idx < len(PROVIDERS):
            log("Waiting 10 seconds before next test...")
            time.sleep(10)
            log("")

    # Final summary
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
            status = "✅ PASS" if r.get("overall_passed") else "⚠️  PARTIAL"
            log(
                f"  {status} {r['provider']}: {r.get('duration')}s, {r.get('files')} files, {r.get('lines')} lines, SOP: {r.get('sop_score')}/100"
            )

    log("")

    failed = [r for r in results if not r.get("success")]
    if failed:
        log("Failed Tests:")
        for r in failed:
            log(f"  ✗ FAIL {r['provider']}: {r.get('reason', 'unknown')}")

    log("")
    log("Results saved to database")
    log("View on dashboard: http://localhost:8081/#llm-tests")
    log("=" * 80)

    return 0 if len(successful) > 0 else 1


if __name__ == "__main__":
    exit(main())
