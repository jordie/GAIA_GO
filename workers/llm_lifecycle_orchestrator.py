#!/usr/bin/env python3
"""
LLM Full Lifecycle Test Orchestrator

Runs comprehensive tests across different LLM provider combinations:
- Code generation
- Deployment
- UI testing (login, session, user flows)
- API testing
- Data isolation
- Cleanup and verification

Results stored in database and displayed on dashboard.
"""

import asyncio
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_connection
from testing.loader import load_test_suite
from testing.runner import TestRunner

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# LLM Provider configurations
PROVIDERS = [
    {"name": "Claude", "session": "architect", "type": "claude"},
    {"name": "Codex", "session": "codex", "type": "codex"},
    {"name": "Claude-Architect", "session": "claude_architect", "type": "claude"},
    {"name": "Comet", "session": "claude_comet", "type": "comet"},
    {
        "name": "AnythingLLM",
        "session": None,
        "type": "anything_llm",
        "api": "http://localhost:3001",
    },
    {"name": "Ollama", "session": None, "type": "ollama", "api": "http://localhost:11434"},
]

# Test configurations
TEST_CONFIGS = [
    {
        "name": "Standard Flow",
        "suite": "llm_full_lifecycle",
        "description": "Full lifecycle with all tests",
        "env": "test",
        "port": 5000,
    },
    {
        "name": "Quick Validation",
        "suite": "llm_quick_validation",
        "description": "Quick smoke test",
        "env": "test",
        "port": 5001,
        "skip_ui": True,
    },
    {
        "name": "Production Simulation",
        "suite": "llm_full_lifecycle",
        "description": "Production-like environment",
        "env": "staging",
        "port": 5002,
        "require_https": True,
    },
]


def create_test_run(provider: str, config: Dict) -> int:
    """Create test run entry in database"""
    with get_connection("main") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO llm_test_runs
            (test_name, description, prompt_template, max_lines, created_by)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                f"{provider} - {config['name']}",
                config["description"],
                config["suite"],
                1000,
                "orchestrator",
            ),
        )
        return cursor.lastrowid


def create_test_result(test_run_id: int, provider: Dict, config: Dict) -> int:
    """Create test result entry"""
    with get_connection("main") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO llm_test_results
            (test_run_id, provider_name, session_name, status, started_at, metadata)
            VALUES (?, ?, ?, 'running', CURRENT_TIMESTAMP, ?)
        """,
            (
                test_run_id,
                provider["name"],
                provider.get("session"),
                json.dumps(
                    {
                        "config": config,
                        "provider_type": provider["type"],
                        "api_endpoint": provider.get("api"),
                    }
                ),
            ),
        )
        return cursor.lastrowid


def update_test_result(result_id: int, status: str, **kwargs):
    """Update test result with outcome"""
    fields = ["status = ?", "completed_at = CURRENT_TIMESTAMP"]
    values = [status]

    for key, value in kwargs.items():
        if value is not None:
            fields.append(f"{key} = ?")
            values.append(value if not isinstance(value, (dict, list)) else json.dumps(value))

    values.append(result_id)

    with get_connection("main") as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE llm_test_results SET {', '.join(fields)} WHERE id = ?", values)


async def run_test_suite(provider: Dict, config: Dict, test_run_id: int, result_id: int) -> Dict:
    """Run test suite for a provider"""
    logger.info(f"Starting test: {provider['name']} - {config['name']}")

    start_time = datetime.now()

    try:
        # Load test suite
        suite_path = (
            Path(__file__).parent.parent / "testing" / "test_suites" / f"{config['suite']}.json"
        )

        if not suite_path.exists():
            raise FileNotFoundError(f"Test suite not found: {suite_path}")

        suite = load_test_suite(str(suite_path))

        # Set environment variables for test
        os.environ["LLM_PROVIDER"] = provider["name"]
        os.environ["TEST_RUN_ID"] = str(test_run_id)

        # Override suite variables with config
        suite.global_variables.update(
            {
                "provider": provider["name"],
                "test_run_id": test_run_id,
                "app_port": str(config["port"]),
                "deploy_url": f"http://localhost:{config['port']}",
            }
        )

        # Create test runner
        runner = TestRunner(
            headless=True,
            screenshot_dir=f"/tmp/llm_test_screenshots/{provider['name']}_{test_run_id}",
        )

        # Run test suite
        result = await runner.execute_suite(suite)

        # Calculate metrics
        duration = (datetime.now() - start_time).total_seconds()

        # Extract metrics from results
        files_created = 0
        total_lines = 0
        sop_score = 0
        test_details = {}

        for test_result in result.test_results:
            test_details[test_result.test_case.id] = {
                "status": test_result.status.value,
                "duration": test_result.duration,
                "steps_passed": sum(
                    1 for s in test_result.step_results if s.status.value == "passed"
                ),
                "steps_total": len(test_result.step_results),
                "error": test_result.error,
            }

            # Extract specific metrics
            if test_result.test_case.id == "sop_compliance":
                for step_result in test_result.step_results:
                    if "total_lines" in step_result.extracted_data:
                        total_lines = step_result.extracted_data["total_lines"]
                    if "file_list" in step_result.extracted_data:
                        files_created = len(step_result.extracted_data["file_list"])

        # Calculate SOP score
        sop_score = calculate_sop_score(files_created, total_lines, test_details)

        # Determine overall pass/fail
        test_passed = result.status.value == "passed"

        # Update database
        update_test_result(
            result_id,
            "completed",
            duration_seconds=int(duration),
            files_created=files_created,
            total_lines=total_lines,
            test_passed=test_passed,
            metadata=json.dumps(
                {
                    "sop_score": sop_score,
                    "test_details": test_details,
                    "suite_result": result.to_dict(),
                }
            ),
        )

        logger.info(
            f"Test completed: {provider['name']} - {config['name']} - {'PASSED' if test_passed else 'FAILED'}"
        )

        return {
            "success": True,
            "status": result.status.value,
            "duration": duration,
            "files_created": files_created,
            "total_lines": total_lines,
            "sop_score": sop_score,
            "test_passed": test_passed,
        }

    except Exception as e:
        logger.error(f"Test failed: {provider['name']} - {config['name']}: {e}", exc_info=True)

        duration = (datetime.now() - start_time).total_seconds()

        update_test_result(
            result_id, "failed", duration_seconds=int(duration), error_message=str(e)
        )

        return {"success": False, "error": str(e), "duration": duration}


def calculate_sop_score(files_created: int, total_lines: int, test_details: Dict) -> int:
    """Calculate SOP compliance score (0-100)"""
    score = 0

    # Required files (40 points)
    required_files = ["calculator.html", "calculator.js", "calculator.css", "app.py"]
    if files_created >= len(required_files):
        score += 40
    else:
        score += (files_created / len(required_files)) * 40

    # Line limit (20 points)
    if 0 < total_lines <= 1000:
        score += 20
    elif total_lines > 1000:
        score += max(0, 20 - ((total_lines - 1000) / 100))

    # Tests exist (10 points)
    if "api_calculate_endpoint" in test_details:
        if test_details["api_calculate_endpoint"]["status"] == "passed":
            score += 10

    # Documentation (10 points)
    if files_created >= 5:  # Assumes README exists
        score += 10

    # UI tests (20 points)
    ui_tests = ["ui_login_flow", "ui_calculator_operations", "ui_session_persistence"]
    ui_passed = sum(1 for t in ui_tests if test_details.get(t, {}).get("status") == "passed")
    score += (ui_passed / len(ui_tests)) * 20

    return min(100, int(score))


async def run_all_tests(providers: List[Dict] = None, configs: List[Dict] = None):
    """Run tests for all provider/config combinations"""
    providers = providers or PROVIDERS
    configs = configs or TEST_CONFIGS

    logger.info("=" * 80)
    logger.info("LLM FULL LIFECYCLE TEST ORCHESTRATOR")
    logger.info("=" * 80)
    logger.info(f"Providers: {len(providers)}")
    logger.info(f"Configurations: {len(configs)}")
    logger.info(f"Total tests: {len(providers) * len(configs)}")
    logger.info("")

    results = []

    for provider_idx, provider in enumerate(providers, 1):
        for config_idx, config in enumerate(configs, 1):
            test_num = (provider_idx - 1) * len(configs) + config_idx
            total_tests = len(providers) * len(configs)

            logger.info(f"[{test_num}/{total_tests}] {provider['name']} - {config['name']}")

            # Create test run
            test_run_id = create_test_run(provider["name"], config)

            # Create test result entry
            result_id = create_test_result(test_run_id, provider, config)

            # Run test
            result = await run_test_suite(provider, config, test_run_id, result_id)

            results.append({"provider": provider["name"], "config": config["name"], **result})

            # Wait between tests
            if test_num < total_tests:
                logger.info("Waiting 10 seconds before next test...")
                await asyncio.sleep(10)
                logger.info("")

    # Summary
    logger.info("=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    logger.info("")

    successful = [r for r in results if r.get("success")]

    logger.info(
        f"Success Rate: {len(successful)}/{len(results)} ({len(successful)/len(results)*100:.1f}%)"
    )
    logger.info("")

    if successful:
        logger.info("Successful Tests:")
        for r in successful:
            passed_status = "✅ PASS" if r.get("test_passed") else "⚠️  PARTIAL"
            logger.info(f"  {passed_status} {r['provider']} - {r['config']}")
            logger.info(
                f"    Duration: {r.get('duration', 0):.1f}s, "
                f"Files: {r.get('files_created', 0)}, "
                f"Lines: {r.get('total_lines', 0)}, "
                f"SOP: {r.get('sop_score', 0)}/100"
            )

    logger.info("")

    failed = [r for r in results if not r.get("success")]
    if failed:
        logger.info("Failed Tests:")
        for r in failed:
            logger.info(f"  ✗ FAIL {r['provider']} - {r['config']}: {r.get('error', 'unknown')}")

    logger.info("")
    logger.info("Results saved to database")
    logger.info("View on dashboard: http://localhost:8080/#llm-tests")
    logger.info("=" * 80)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="LLM Full Lifecycle Test Orchestrator")
    parser.add_argument("--providers", nargs="+", help="Specific providers to test")
    parser.add_argument("--config", help="Specific config to use")
    parser.add_argument("--quick", action="store_true", help="Run quick validation only")

    args = parser.parse_args()

    # Filter providers
    providers = PROVIDERS
    if args.providers:
        providers = [p for p in PROVIDERS if p["name"] in args.providers]

    # Filter configs
    configs = TEST_CONFIGS
    if args.quick:
        configs = [c for c in TEST_CONFIGS if "Quick" in c["name"]]
    elif args.config:
        configs = [c for c in TEST_CONFIGS if c["name"] == args.config]

    # Run tests
    asyncio.run(run_all_tests(providers, configs))


if __name__ == "__main__":
    main()
