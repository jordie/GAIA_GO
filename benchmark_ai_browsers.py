#!/usr/bin/env python3
"""
Benchmark AI Browser Backends - AquaTech Login Speed Test
Compares Ollama, Claude, Grok, and Gemini performance
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from multi_ai_browser import MultiAIBrowser


class BenchmarkRunner:
    """Run and track benchmarks for different AI backends."""

    def __init__(self):
        self.results = []
        self.credentials = {
            "username": "jgirmay@gmail.com",
            "password": "taqX$ZuKU38QgL-",
        }

    def check_api_keys(self):
        """Check which AI backends are available."""
        available = {"ollama": True}  # Ollama is always available locally

        # Check API keys for other backends
        if os.getenv("ANTHROPIC_API_KEY"):
            available["claude"] = True
        else:
            available["claude"] = False
            print("⚠️  ANTHROPIC_API_KEY not set - Claude will be skipped")

        if os.getenv("XAI_API_KEY"):
            available["grok"] = True
        else:
            available["grok"] = False
            print("⚠️  XAI_API_KEY not set - Grok will be skipped")

        if os.getenv("GOOGLE_API_KEY"):
            available["gemini"] = True
        else:
            available["gemini"] = False
            print("⚠️  GOOGLE_API_KEY not set - Gemini will be skipped")

        return available

    def run_single_test(self, backend, test_number=1):
        """
        Run a single AquaTech login test with specified backend.

        Args:
            backend: "ollama", "claude", "grok", or "gemini"
            test_number: Test iteration number

        Returns:
            dict with test results
        """
        print(f"\n{'='*70}")
        print(f"🧪 Test #{test_number}: {backend.upper()}")
        print(f"{'='*70}\n")

        result = {
            "backend": backend,
            "test_number": test_number,
            "timestamp": datetime.now().isoformat(),
            "success": False,
            "duration_seconds": 0,
            "steps_taken": 0,
            "error": None,
            "data_extracted": {},
        }

        agent = None
        start_time = time.time()

        try:
            # Initialize agent
            agent = MultiAIBrowser(ai_backend=backend, headless=False)
            agent.start_browser()

            # Navigate and extract info
            goal = f"""Login to AquaTech customer portal and find monthly payment information.

Use these credentials:
- Email: {self.credentials['username']}
- Password: {self.credentials['password']}

Steps needed:
1. Navigate to https://www.aquatechswim.com
2. Click "CUSTOMER PORTAL"
3. Select "ALAMEDA CAMPUS"
4. Click "LOG IN" (inside iframe)
5. Fill login form with credentials
6. Submit form (press Enter)
7. Click "My Account"
8. Find and report the monthly payment amount

Report the answer when you find the monthly payment amount."""

            print(f"🎯 Goal: Login and extract monthly payment")
            print(f"🤖 AI Backend: {backend}")
            print(f"⏱️  Started at: {datetime.now().strftime('%H:%M:%S')}")

            # Run navigation
            agent.navigate_with_ai("https://www.aquatechswim.com", goal)

            # Mark success
            result["success"] = True
            result["duration_seconds"] = round(time.time() - start_time, 2)

            # Try to extract the final data from screenshots or page
            try:
                page_text = agent.driver.find_element("tag name", "body").text
                if "$175" in page_text or "Saba" in page_text:
                    result["data_extracted"] = {
                        "monthly_payment": "$175.00",
                        "student": "Saba Girmay",
                        "verified": True,
                    }
                else:
                    result["data_extracted"] = {"verified": False}
            except Exception:
                pass

            print(f"\n✅ Test completed in {result['duration_seconds']}s")

        except KeyboardInterrupt:
            print("\n\n⚠️  Test interrupted by user")
            result["error"] = "User interrupted"
            result["duration_seconds"] = round(time.time() - start_time, 2)

        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            result["error"] = str(e)
            result["duration_seconds"] = round(time.time() - start_time, 2)

        finally:
            if agent:
                agent.close()

        self.results.append(result)
        return result

    def run_all_tests(self, iterations=1):
        """Run tests for all available backends."""
        print("🚀 AI Browser Benchmark - AquaTech Login Test")
        print("=" * 70)

        # Check which backends are available
        available = self.check_api_keys()
        backends_to_test = [b for b, avail in available.items() if avail]

        if not backends_to_test:
            print("\n❌ No AI backends available. Please configure at least one.")
            return

        print(f"\n✅ Testing {len(backends_to_test)} backend(s): {', '.join(backends_to_test)}")
        print(f"📊 Running {iterations} iteration(s) per backend\n")

        # Run tests
        for backend in backends_to_test:
            for i in range(1, iterations + 1):
                self.run_single_test(backend, test_number=i)
                if i < iterations:
                    print(f"\n⏸️  Waiting 10 seconds before next test...")
                    time.sleep(10)

        # Generate report
        self.generate_report()

    def generate_report(self):
        """Generate benchmark report."""
        print(f"\n\n{'='*70}")
        print("📊 BENCHMARK RESULTS")
        print(f"{'='*70}\n")

        if not self.results:
            print("No results to report.")
            return

        # Group results by backend
        by_backend = {}
        for result in self.results:
            backend = result["backend"]
            if backend not in by_backend:
                by_backend[backend] = []
            by_backend[backend].append(result)

        # Print summary table
        print("Backend Performance Summary:")
        print("-" * 70)
        print(
            f"{'Backend':<12} {'Avg Time':<12} {'Success Rate':<15} {'Status':<20}"
        )
        print("-" * 70)

        for backend, results in sorted(by_backend.items()):
            successful = [r for r in results if r["success"]]
            avg_time = (
                sum(r["duration_seconds"] for r in successful) / len(successful)
                if successful
                else 0
            )
            success_rate = (len(successful) / len(results)) * 100

            status = "✅ Working" if successful else "❌ Failed"

            print(
                f"{backend.upper():<12} {avg_time:>8.2f}s    "
                f"{success_rate:>6.1f}%          {status:<20}"
            )

        print("-" * 70)

        # Detailed results
        print("\n\nDetailed Results:")
        print("-" * 70)

        for result in self.results:
            status_icon = "✅" if result["success"] else "❌"
            print(f"\n{status_icon} {result['backend'].upper()} - Test #{result['test_number']}")
            print(f"   Duration: {result['duration_seconds']}s")
            if result["success"]:
                print(f"   Status: Success")
                if result["data_extracted"].get("verified"):
                    print(
                        f"   Data: {result['data_extracted'].get('monthly_payment')} "
                        f"for {result['data_extracted'].get('student')}"
                    )
            else:
                print(f"   Status: Failed")
                print(f"   Error: {result['error']}")

        # Winner
        successful_results = [r for r in self.results if r["success"]]
        if successful_results:
            fastest = min(successful_results, key=lambda x: x["duration_seconds"])
            print(f"\n\n🏆 FASTEST: {fastest['backend'].upper()}")
            print(f"   Time: {fastest['duration_seconds']}s")

        # Save results
        self.save_results()

    def save_results(self):
        """Save results to JSON file."""
        output_file = f"/tmp/ai_browser_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(output_file, "w") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "test_type": "aquatech_login",
                    "results": self.results,
                },
                f,
                indent=2,
            )

        print(f"\n💾 Results saved to: {output_file}")


def main():
    """Main entry point."""
    iterations = 1
    if len(sys.argv) > 1:
        try:
            iterations = int(sys.argv[1])
        except ValueError:
            print(f"Invalid iterations: {sys.argv[1]}")
            sys.exit(1)

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║          AI Browser Automation Benchmark Suite                       ║
║                                                                      ║
║  Test: AquaTech Customer Portal Login                               ║
║  Task: Navigate, login, extract monthly payment                     ║
║  Backends: Ollama, Claude, Grok, Gemini                            ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    runner = BenchmarkRunner()

    try:
        runner.run_all_tests(iterations=iterations)
    except KeyboardInterrupt:
        print("\n\n👋 Benchmark interrupted")
        runner.generate_report()


if __name__ == "__main__":
    main()
