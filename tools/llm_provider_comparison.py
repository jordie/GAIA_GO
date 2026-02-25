#!/usr/bin/env python3
"""
LLM Provider Comparison Tool

Compare performance, quality, and cost across different LLM providers:
- Claude (Anthropic)
- Gemini (Google)
- Ollama (Local)
- Codex (OpenAI)

Usage:
    python3 tools/llm_provider_comparison.py --test basic
    python3 tools/llm_provider_comparison.py --providers claude gemini ollama --timeout 60
    python3 tools/llm_provider_comparison.py --compare-all
"""

import argparse
import asyncio
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
import requests

# Resolved endpoints
OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
ANYTHINGLLM_ENDPOINT = os.getenv("ANYTHINGLLM_ENDPOINT", "http://localhost:3001")


# Test prompts categorized by complexity/type
TEST_PROMPTS = {
    "basic": [
        {
            "name": "simple_question",
            "prompt": "What is Python?",
            "category": "knowledge",
            "timeout": 10,
        },
        {
            "name": "code_generation",
            "prompt": "Write a Python function that reverses a string",
            "category": "coding",
            "timeout": 15,
        },
        {
            "name": "explanation",
            "prompt": "Explain what a REST API is in simple terms",
            "category": "explanation",
            "timeout": 10,
        },
    ],
    "intermediate": [
        {
            "name": "debugging",
            "prompt": """
Here's a Python function with a bug:

```python
def find_duplicate(arr):
    seen = set()
    for num in arr:
        if num in seen:
            return num
        seen.add(num)
```

Find and explain the bug.
            """,
            "category": "debugging",
            "timeout": 20,
        },
        {
            "name": "architecture",
            "prompt": "Design a microservices architecture for an e-commerce platform. What are the main services?",
            "category": "architecture",
            "timeout": 20,
        },
        {
            "name": "optimization",
            "prompt": "How would you optimize a Python loop that processes 1 million items?",
            "category": "optimization",
            "timeout": 15,
        },
    ],
    "complex": [
        {
            "name": "system_design",
            "prompt": """
Design a distributed caching system that:
- Handles 100k concurrent users
- Provides sub-millisecond latency
- Survives node failures
- Is horizontally scalable

Describe the architecture, data structures, and failure scenarios.
            """,
            "category": "system_design",
            "timeout": 30,
        },
        {
            "name": "algorithm",
            "prompt": """
Implement an efficient algorithm for the traveling salesman problem.
Explain the approach and complexity trade-offs.
            """,
            "category": "algorithm",
            "timeout": 30,
        },
    ],
}


class ProviderTester:
    """Test a single LLM provider."""

    def __init__(self, provider: str, timeout: int = 30):
        self.provider = provider
        self.timeout = timeout
        self.results = []

    async def test_claude(self, prompt: str) -> Tuple[bool, float, str]:
        """Test Claude API."""
        try:
            start = time.time()
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            message = client.messages.create(
                model="claude-opus-4-5-20251101",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
                timeout=self.timeout,
            )
            duration = time.time() - start
            response = message.content[0].text
            return (True, duration, response)
        except Exception as e:
            return (False, 0, str(e))

    async def test_gemini(self, prompt: str) -> Tuple[bool, float, str]:
        """Test Gemini API."""
        try:
            import google.generativeai as genai

            start = time.time()
            genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
            model = genai.GenerativeModel("gemini-pro")
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=1024,
                ),
                request_options={"timeout": self.timeout},
            )
            duration = time.time() - start
            return (True, duration, response.text)
        except Exception as e:
            return (False, 0, str(e))

    async def test_ollama(self, prompt: str) -> Tuple[bool, float, str]:
        """Test Ollama local LLM."""
        try:
            start = time.time()
            response = requests.post(
                f"{OLLAMA_ENDPOINT}/api/generate",
                json={
                    "model": "llama2",  # or mistral
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 1024},
                },
                timeout=self.timeout,
            )
            duration = time.time() - start
            if response.status_code == 200:
                result = response.json()
                return (True, duration, result.get("response", ""))
            else:
                return (False, 0, f"HTTP {response.status_code}")
        except Exception as e:
            return (False, 0, str(e))

    async def test_codex(self, prompt: str) -> Tuple[bool, float, str]:
        """Test Codex (via OpenAI)."""
        try:
            import openai

            start = time.time()
            openai.api_key = os.getenv("OPENAI_API_KEY")
            response = openai.ChatCompletion.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                timeout=self.timeout,
            )
            duration = time.time() - start
            return (True, duration, response["choices"][0]["message"]["content"])
        except Exception as e:
            return (False, 0, str(e))

    async def test(self, prompt: str) -> Dict:
        """Run test for this provider."""
        test_name = f"{self.provider}_{int(time.time())}"

        if self.provider == "claude":
            success, duration, response = await self.test_claude(prompt)
        elif self.provider == "gemini":
            success, duration, response = await self.test_gemini(prompt)
        elif self.provider == "ollama":
            success, duration, response = await self.test_ollama(prompt)
        elif self.provider == "codex":
            success, duration, response = await self.test_codex(prompt)
        else:
            return {
                "provider": self.provider,
                "success": False,
                "error": "Unknown provider",
            }

        return {
            "provider": self.provider,
            "prompt_length": len(prompt),
            "success": success,
            "duration": duration,
            "response_length": len(response) if success else 0,
            "response": response[:500] if success else response,  # First 500 chars
            "timestamp": datetime.now().isoformat(),
        }


class ComparisonRunner:
    """Run comparisons across all providers."""

    def __init__(self, providers: List[str], timeout: int = 30):
        self.providers = providers
        self.timeout = timeout
        self.results = {"comparisons": [], "summary": {}}

    async def run_comparison(self, test_name: str, prompt: str, category: str) -> Dict:
        """Run prompt through all providers."""
        print(f"\n{'='*60}")
        print(f"Test: {test_name} ({category})")
        print(f"Prompt: {prompt[:100]}...")
        print(f"{'='*60}")

        comparison = {
            "test_name": test_name,
            "category": category,
            "prompt_length": len(prompt),
            "timestamp": datetime.now().isoformat(),
            "providers": {},
        }

        tasks = []
        for provider in self.providers:
            tester = ProviderTester(provider, self.timeout)
            tasks.append((provider, tester.test(prompt)))

        results = await asyncio.gather(*[task[1] for task in tasks])

        for (provider, _), result in zip(tasks, results):
            comparison["providers"][provider] = result
            status = "✓" if result["success"] else "✗"
            duration = f"{result['duration']:.2f}s" if result["success"] else "N/A"
            response_len = f"{result['response_length']} chars" if result["success"] else "N/A"
            print(f"{status} {provider:10} - {duration:10} - {response_len}")

        return comparison

    async def run_suite(self, suite_name: str = "basic") -> None:
        """Run all tests in a suite."""
        prompts = TEST_PROMPTS.get(suite_name, TEST_PROMPTS["basic"])

        print(f"\n\n{'='*60}")
        print(f"LLM Provider Comparison Suite: {suite_name}")
        print(f"Providers: {', '.join(self.providers)}")
        print(f"Timeout: {self.timeout}s per test")
        print(f"{'='*60}")

        for test in prompts:
            comparison = await self.run_comparison(test["name"], test["prompt"], test["category"])
            self.results["comparisons"].append(comparison)

        self.print_summary()

    def print_summary(self) -> None:
        """Print summary of all comparisons."""
        print(f"\n\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")

        summary = {
            provider: {"success": 0, "avg_duration": 0, "total_duration": 0, "count": 0}
            for provider in self.providers
        }

        for comparison in self.results["comparisons"]:
            for provider, result in comparison["providers"].items():
                if result["success"]:
                    summary[provider]["success"] += 1
                    summary[provider]["total_duration"] += result["duration"]
                summary[provider]["count"] += 1

        # Calculate averages
        for provider in summary:
            if summary[provider]["count"] > 0:
                summary[provider]["avg_duration"] = (
                    summary[provider]["total_duration"] / summary[provider]["count"]
                )
            summary[provider]["success_rate"] = (
                summary[provider]["success"] / summary[provider]["count"]
            )

        # Print table
        print(f"\n{'Provider':<12} {'Success Rate':<15} {'Avg Duration':<15} {'Success Count':<15}")
        print("-" * 60)

        for provider in self.providers:
            s = summary[provider]
            success_rate = f"{s['success_rate']*100:.1f}%"
            avg_duration = f"{s['avg_duration']:.2f}s"
            success_count = f"{s['success']}/{s['count']}"
            print(f"{provider:<12} {success_rate:<15} {avg_duration:<15} {success_count:<15}")

        self.results["summary"] = summary

    def save_results(self, filename: str = None) -> str:
        """Save results to JSON file."""
        if not filename:
            filename = (
                f"data/comparisons/comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )

        Path(filename).parent.mkdir(parents=True, exist_ok=True)

        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)

        print(f"\nResults saved to: {filename}")
        return filename


async def main():
    parser = argparse.ArgumentParser(description="Compare LLM providers")
    parser.add_argument(
        "--test",
        choices=["basic", "intermediate", "complex", "all"],
        default="basic",
        help="Test suite to run",
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        default=["claude", "gemini", "ollama"],
        help="Providers to test",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout per request in seconds",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save results to file",
    )

    args = parser.parse_args()

    runner = ComparisonRunner(args.providers, args.timeout)

    if args.test == "all":
        for suite in ["basic", "intermediate", "complex"]:
            await runner.run_suite(suite)
    else:
        await runner.run_suite(args.test)

    if args.save:
        runner.save_results()


if __name__ == "__main__":
    asyncio.run(main())
