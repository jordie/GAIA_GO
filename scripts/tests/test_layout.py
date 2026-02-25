#!/usr/bin/env python3
"""
Layout Test for Architect Dashboard

Tests that panel headers are visible without scrolling when panels are activated.
Reports which panels have layout issues where content starts too low.

Usage:
    python3 scripts/tests/test_layout.py [--url URL] [--username USER] [--password PASS]

Requirements:
    pip install playwright
    playwright install chromium
"""

import argparse
import json
import sys

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

# Panels to test - these are the ones reported to have issues
PANELS_TO_TEST = [
    {"id": "docs", "name": "Documentation"},
    {"id": "accounts", "name": "Cross-Node Accounts"},
    {"id": "tasks", "name": "Task Queue"},
    {"id": "workers", "name": "Offline Workers"},
    {"id": "nodes", "name": "Cluster Nodes"},
    {"id": "deployments", "name": "Deployments"},
]


def test_panel_layout(page, panel_id, panel_name):
    """
    Test if a panel's header is visible without scrolling.

    Returns:
        dict: Test result with status and details
    """
    result = {
        "panel_id": panel_id,
        "panel_name": panel_name,
        "passed": False,
        "header_visible": False,
        "scroll_position": None,
        "header_position": None,
        "viewport_height": None,
        "error": None,
    }

    try:
        # Navigate to the panel
        print(f"  Testing panel: {panel_name} (#{panel_id})")
        page.goto(f'{page.url.split("#")[0]}#{panel_id}')

        # Wait for panel to be active
        page.wait_for_selector(f"#panel-{panel_id}.active", timeout=5000)

        # Small delay to let any animations/scroll happen
        page.wait_for_timeout(200)

        # Get viewport height
        viewport_height = page.evaluate("window.innerHeight")
        result["viewport_height"] = viewport_height

        # Get scroll position of main content area
        scroll_info = page.evaluate(
            """() => {
            const mainContent = document.getElementById('main-content');
            return {
                scrollTop: mainContent ? mainContent.scrollTop : 0,
                scrollLeft: mainContent ? mainContent.scrollLeft : 0,
                windowScrollY: window.scrollY,
                documentScrollTop: document.documentElement.scrollTop
            };
        }"""
        )
        result["scroll_position"] = scroll_info

        # Find the panel header
        header_selector = f"#panel-{panel_id} .panel-header h1.panel-title"
        header = page.query_selector(header_selector)

        if not header:
            result["error"] = f"Panel header not found: {header_selector}"
            print(f"    ❌ FAILED: {result['error']}")
            return result

        # Get header position and visibility
        header_info = header.evaluate(
            """(element) => {
            const rect = element.getBoundingClientRect();
            const mainContent = document.getElementById('main-content');
            const mainContentRect = mainContent ? mainContent.getBoundingClientRect() : null;

            return {
                top: rect.top,
                bottom: rect.bottom,
                left: rect.left,
                right: rect.right,
                visible: rect.top >= 0 && rect.top < window.innerHeight,
                mainContentTop: mainContentRect ? mainContentRect.top : null,
                offsetTop: element.offsetTop,
                clientTop: element.clientTop
            };
        }"""
        )
        result["header_position"] = header_info
        result["header_visible"] = header_info["visible"]

        # Check if header is visible in viewport without scrolling
        # Header should be near the top of the viewport (allowing for header + padding)
        # Main content typically starts at ~85px (header height) + 20px padding = ~105px
        # If header.top > 150, it's likely scrolled down or layout is broken
        header_top = header_info["top"]
        max_acceptable_y = 150  # Allow for header (85px) + content padding (20-40px)

        if header_info["visible"] and header_top < max_acceptable_y:
            result["passed"] = True
            print(f"    ✅ PASSED: Header visible at top (y={header_top:.1f}px)")
        else:
            result["passed"] = False
            if not header_info["visible"]:
                print(f"    ❌ FAILED: Header NOT visible in viewport")
            else:
                print(
                    f"    ❌ FAILED: Header too far down (y={header_top:.1f}px, expected <{max_acceptable_y}px)"
                )
                print(
                    f"       Scroll info: main-content scrollTop={scroll_info['scrollTop']}, window.scrollY={scroll_info['windowScrollY']}"
                )

    except PlaywrightTimeout as e:
        result["error"] = f"Timeout: {str(e)}"
        print(f"    ❌ FAILED: {result['error']}")
    except Exception as e:
        result["error"] = str(e)
        print(f"    ❌ FAILED: {result['error']}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Test Architect Dashboard panel layouts")
    parser.add_argument(
        "--url",
        default="https://127.0.0.1:8085",
        help="Dashboard URL (default: https://127.0.0.1:8085)",
    )
    parser.add_argument("--username", default="architect", help="Username (default: architect)")
    parser.add_argument("--password", default="peace5", help="Password (default: peace5)")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    results = []

    with sync_playwright() as p:
        print(f"Launching browser (headless={args.headless})...")
        browser = p.chromium.launch(headless=args.headless)

        # Create context with ignore HTTPS errors for self-signed certs
        context = browser.new_context(
            ignore_https_errors=True, viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        try:
            # Login
            print(f"\nLogging in to {args.url}...")
            page.goto(args.url)

            # Check if already logged in or need to login
            if page.url.endswith("/login") or "login" in page.url:
                page.fill('input[name="username"]', args.username)
                page.fill('input[name="password"]', args.password)
                page.click('button[type="submit"]')
                # Wait for redirect to dashboard (URL will be something like https://127.0.0.1:8085/#queue)
                page.wait_for_selector(".sidebar", timeout=10000)
                print("✅ Logged in successfully")
            else:
                print("✅ Already logged in")

            # Wait for dashboard to load
            page.wait_for_selector(".sidebar", timeout=5000)

            print("\n" + "=" * 60)
            print("Testing Panel Layouts")
            print("=" * 60 + "\n")

            # Test each panel
            for panel in PANELS_TO_TEST:
                result = test_panel_layout(page, panel["id"], panel["name"])
                results.append(result)
                print()  # Empty line between tests

            # Summary
            print("=" * 60)
            print("SUMMARY")
            print("=" * 60)

            passed = sum(1 for r in results if r["passed"])
            failed = len(results) - passed

            print(f"\nTotal: {len(results)} panels tested")
            print(f"Passed: {passed}")
            print(f"Failed: {failed}")

            if failed > 0:
                print("\nFailed panels:")
                for r in results:
                    if not r["passed"]:
                        print(f"  - {r['panel_name']} (#{r['panel_id']})")
                        if r["error"]:
                            print(f"    Error: {r['error']}")
                        elif r["header_position"]:
                            print(f"    Header position: y={r['header_position']['top']:.1f}px")
                            print(f"    Scroll position: {r['scroll_position']}")

            # Output JSON if requested
            if args.json:
                print("\n" + "=" * 60)
                print("JSON OUTPUT")
                print("=" * 60)
                print(json.dumps(results, indent=2))

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback

            traceback.print_exc()
            browser.close()
            sys.exit(1)

        browser.close()

    # Exit with error code if any tests failed
    sys.exit(0 if all(r["passed"] for r in results) else 1)


if __name__ == "__main__":
    main()
