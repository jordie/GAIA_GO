#!/usr/bin/env python3
"""
Simple provider comparison using gaia CLI directly.

Routes prompts through gaia to different providers and measures response time.
"""

import subprocess
import time
from datetime import datetime
from typing import Dict, List, Tuple


class SimpleProviderComparison:
    """Simple comparison by calling gaia with different providers."""

    PROMPTS = {
        "quick": [
            ("hello", "Hello, respond with just 'hello'"),
            ("python", "What is Python?"),
            ("func", "Write a hello world function in Python"),
        ],
        "moderate": [
            ("api", "Design 3 REST API endpoints for a todo app"),
            ("bug", "This Python code has a bug: `x = [1,2,3]; x[10]`. Fix it."),
            ("optimize", "How would you optimize a loop with 1M items?"),
        ],
    }

    def __init__(self):
        self.results = []

    def test_provider(
        self, provider: str, prompt: str, timeout: int = 30
    ) -> Tuple[bool, float, str]:
        """Test a provider using gaia."""
        start = time.time()

        try:
            # Use gaia to route through the provider
            result = subprocess.run(
                ["gaia", "--provider", provider, "-p", prompt],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            duration = time.time() - start
            output = result.stdout + result.stderr

            if result.returncode == 0:
                return (True, duration, output)
            else:
                return (False, duration, f"Error: {output[:100]}")

        except subprocess.TimeoutExpired:
            return (False, time.time() - start, "Timeout")
        except Exception as e:
            return (False, time.time() - start, str(e))

    def run_comparison(
        self,
        providers: List[str],
        complexity: str = "quick",
        limit: int = None,
    ) -> None:
        """Run comparison across providers."""
        prompts = self.PROMPTS.get(complexity, self.PROMPTS["quick"])
        if limit:
            prompts = prompts[:limit]

        print(f"\n{'='*80}")
        print(f"Gaia Provider Comparison")
        print(f"Providers: {', '.join(providers)}")
        print(f"Complexity: {complexity}")
        print(f"Tests: {len(prompts)}")
        print(f"{'='*80}\n")

        for test_name, prompt in prompts:
            print(f"Test: {test_name}")
            print(f"Prompt: {prompt[:70]}...")
            print()

            test_results = {
                "test_name": test_name,
                "prompt_length": len(prompt),
                "timestamp": datetime.now().isoformat(),
                "providers": {},
            }

            for provider in providers:
                print(f"  Testing {provider}...", end=" ", flush=True)
                success, duration, response = self.test_provider(provider, prompt)
                test_results["providers"][provider] = {
                    "success": success,
                    "duration": duration,
                    "response_length": len(response),
                }

                if success:
                    status = "✓"
                    msg = f"{duration:.2f}s - {len(response)} chars"
                else:
                    status = "✗"
                    msg = response[:50]

                print(f"{status} {msg}")

            print()
            self.results.append(test_results)

    def print_summary(self) -> None:
        """Print summary statistics."""
        if not self.results:
            return

        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}\n")

        providers = set()
        for result in self.results:
            providers.update(result["providers"].keys())

        summary = {
            p: {"success": 0, "total": 0, "avg_duration": 0, "total_duration": 0} for p in providers
        }

        for result in self.results:
            for provider, provider_result in result["providers"].items():
                if provider_result["success"]:
                    summary[provider]["success"] += 1
                    summary[provider]["total_duration"] += provider_result["duration"]
                summary[provider]["total"] += 1

        # Calculate averages
        for provider in summary:
            if summary[provider]["total"] > 0:
                summary[provider]["avg_duration"] = (
                    summary[provider]["total_duration"] / summary[provider]["total"]
                )

        # Print table
        print(f"{'Provider':<15} {'Success':<12} {'Avg Time':<15} {'Tests':<10}")
        print("-" * 52)

        for provider in sorted(providers):
            s = summary[provider]
            success_rate = f"{(s['success']/s['total']*100):.0f}%"
            avg_time = f"{s['avg_duration']:.2f}s"
            tests = f"{s['success']}/{s['total']}"
            print(f"{provider:<15} {success_rate:<12} {avg_time:<15} {tests:<10}")

        return summary


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Compare gaia providers")
    parser.add_argument(
        "--providers",
        nargs="+",
        default=["claude", "gemini", "ollama", "codex"],
        help="Providers to test",
    )
    parser.add_argument(
        "--complexity",
        choices=["quick", "moderate"],
        default="quick",
        help="Test complexity",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit tests",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout per test",
    )

    args = parser.parse_args()

    comp = SimpleProviderComparison()
    comp.run_comparison(
        providers=args.providers,
        complexity=args.complexity,
        limit=args.limit,
    )
    comp.print_summary()


if __name__ == "__main__":
    main()
