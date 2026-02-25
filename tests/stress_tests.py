"""
Stress Tests ST-5, ST-6, ST-10, ST-11: System Performance & Load Analysis

Tests concurrent load, database performance, browser automation workload,
and end-to-end system stress under various conditions.
"""

import json
import sqlite3
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict

import requests

# Configuration
API_BASE_URL = "http://localhost:8080"
DB_PATH = "data/architect.db"
REPORT_FILE = "stress_test_report.json"


class StressTestMetrics:
    """Track metrics for stress tests."""

    def __init__(self, test_name: str):
        self.test_name = test_name
        self.start_time = time.time()
        self.response_times = []
        self.errors = []
        self.success_count = 0
        self.fail_count = 0

    def add_response(self, duration_ms: float, success: bool, error: str = None):
        """Record a response."""
        self.response_times.append(duration_ms)
        if success:
            self.success_count += 1
        else:
            self.fail_count += 1
            if error:
                self.errors.append(error)

    def get_summary(self) -> Dict:
        """Get test summary."""
        elapsed = time.time() - self.start_time
        sorted_times = sorted(self.response_times)

        return {
            "test_name": self.test_name,
            "elapsed_seconds": round(elapsed, 2),
            "total_requests": len(self.response_times),
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "success_rate": round(
                100 * self.success_count / (self.success_count + self.fail_count), 2
            )
            if (self.success_count + self.fail_count) > 0
            else 0,
            "response_times_ms": {
                "min": round(min(sorted_times), 2) if sorted_times else 0,
                "max": round(max(sorted_times), 2) if sorted_times else 0,
                "avg": round(statistics.mean(sorted_times), 2) if sorted_times else 0,
                "median": round(statistics.median(sorted_times), 2) if sorted_times else 0,
                "p95": round(sorted_times[int(len(sorted_times) * 0.95)] if sorted_times else 0, 2),
                "p99": round(sorted_times[int(len(sorted_times) * 0.99)] if sorted_times else 0, 2),
            },
            "throughput_rps": round(len(self.response_times) / elapsed, 2) if elapsed > 0 else 0,
            "errors": list(set(self.errors))[:10],  # Top 10 unique errors
        }


class ST5_ConcurrentAPILoadTest:
    """ST-5: Concurrent API Load Test - 100-1000 concurrent requests"""

    def __init__(self):
        self.metrics = StressTestMetrics("ST-5: Concurrent API Load Test")
        self.concurrent_users = 100
        self.requests_per_user = 10

    def make_request(self, user_id: int, req_num: int) -> tuple:
        """Make single API request."""
        try:
            start = time.time()

            # Vary endpoint being tested
            endpoints = [
                "/api/browser-tasks",
                "/api/browser-tasks/queue/status",
                "/api/browser-tasks/metrics",
            ]
            endpoint = endpoints[req_num % len(endpoints)]

            response = requests.get(f"{API_BASE_URL}{endpoint}", timeout=10)
            duration_ms = (time.time() - start) * 1000

            success = response.status_code == 200
            self.metrics.add_response(
                duration_ms, success, None if success else f"Status {response.status_code}"
            )
            return success, duration_ms

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            self.metrics.add_response(duration_ms, False, str(e))
            return False, duration_ms

    def run(self):
        """Execute ST-5."""
        print("\n" + "=" * 70)
        print("ST-5: CONCURRENT API LOAD TEST")
        print("=" * 70)
        print(f"Concurrent Users: {self.concurrent_users}")
        print(f"Requests per User: {self.requests_per_user}")
        print(f"Total Requests: {self.concurrent_users * self.requests_per_user}")

        with ThreadPoolExecutor(max_workers=self.concurrent_users) as executor:
            futures = []
            for user_id in range(self.concurrent_users):
                for req_num in range(self.requests_per_user):
                    futures.append(executor.submit(self.make_request, user_id, req_num))

            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % 100 == 0:
                    print(f"  Progress: {completed}/{len(futures)} requests completed")
                try:
                    future.result()
                except Exception as e:
                    print(f"  Error: {e}")

        return self.metrics.get_summary()


class ST6_DatabaseQueryPerformance:
    """ST-6: Database Query Performance - 10,000+ concurrent queries"""

    def __init__(self):
        self.metrics = StressTestMetrics("ST-6: Database Query Performance")
        self.concurrent_queries = 100
        self.queries_per_connection = 100

    def execute_query(self, query_num: int) -> tuple:
        """Execute single database query."""
        try:
            start = time.time()
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()

            # Vary query types
            queries = [
                "SELECT COUNT(*) FROM projects;",
                "SELECT COUNT(*) FROM tasks;",
                "SELECT COUNT(*) FROM errors WHERE created_at > datetime('now', '-1 day');",
                "SELECT * FROM projects LIMIT 10;",
            ]
            query = queries[query_num % len(queries)]

            c.execute(query)
            c.fetchall()
            conn.close()

            duration_ms = (time.time() - start) * 1000
            self.metrics.add_response(duration_ms, True)
            return True, duration_ms

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            self.metrics.add_response(duration_ms, False, str(e))
            return False, duration_ms

    def run(self):
        """Execute ST-6."""
        print("\n" + "=" * 70)
        print("ST-6: DATABASE QUERY PERFORMANCE TEST")
        print("=" * 70)
        total_queries = self.concurrent_queries * self.queries_per_connection
        print(f"Concurrent Connections: {self.concurrent_queries}")
        print(f"Queries per Connection: {self.queries_per_connection}")
        print(f"Total Queries: {total_queries}")

        with ThreadPoolExecutor(max_workers=self.concurrent_queries) as executor:
            futures = []
            for conn_id in range(self.concurrent_queries):
                for query_num in range(self.queries_per_connection):
                    query_id = conn_id * self.queries_per_connection + query_num
                    futures.append(executor.submit(self.execute_query, query_id))

            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % 500 == 0:
                    print(f"  Progress: {completed}/{len(futures)} queries completed")
                try:
                    future.result()
                except Exception as e:
                    print(f"  Error: {e}")

        return self.metrics.get_summary()


class ST10_BrowserAutomationWorkload:
    """ST-10: Browser Automation Workload - 50+ concurrent automation tasks"""

    def __init__(self):
        self.metrics = StressTestMetrics("ST-10: Browser Automation Workload")
        self.concurrent_tasks = 50
        self.task_duration_ms = 100  # Simulated

    def simulate_task(self, task_id: int) -> tuple:
        """Simulate browser automation task execution."""
        try:
            start = time.time()

            # Create task
            task_data = {
                "goal": f"Automated task {task_id}",
                "site_url": "https://example.com",
                "priority": 5,
                "timeout_minutes": 30,
            }

            response = requests.post(
                f"{API_BASE_URL}/api/browser-tasks", json=task_data, timeout=10
            )

            # Simulate task processing
            time.sleep(self.task_duration_ms / 1000)

            duration_ms = (time.time() - start) * 1000
            success = response.status_code == 201
            self.metrics.add_response(
                duration_ms, success, None if success else f"Status {response.status_code}"
            )
            return success, duration_ms

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            self.metrics.add_response(duration_ms, False, str(e))
            return False, duration_ms

    def run(self):
        """Execute ST-10."""
        print("\n" + "=" * 70)
        print("ST-10: BROWSER AUTOMATION WORKLOAD TEST")
        print("=" * 70)
        print(f"Concurrent Tasks: {self.concurrent_tasks}")
        print(f"Simulated Task Duration: {self.task_duration_ms}ms")
        print(f"Total Tasks: {self.concurrent_tasks}")

        with ThreadPoolExecutor(max_workers=self.concurrent_tasks) as executor:
            futures = [
                executor.submit(self.simulate_task, task_id)
                for task_id in range(self.concurrent_tasks)
            ]

            completed = 0
            for future in as_completed(futures):
                completed += 1
                print(f"  Progress: {completed}/{len(futures)} tasks completed")
                try:
                    future.result()
                except Exception as e:
                    print(f"  Error: {e}")

        return self.metrics.get_summary()


class ST11_EndToEndSystemStress:
    """ST-11: End-to-End System Stress - Combined API + DB + Workers"""

    def __init__(self):
        self.metrics = StressTestMetrics("ST-11: End-to-End System Stress")
        self.concurrent_operations = 50

    def stress_operation(self, op_id: int) -> tuple:
        """Execute combined stress operation."""
        try:
            start = time.time()

            # Phase 1: API call
            task_data = {
                "goal": f"Stress test operation {op_id}",
                "site_url": "https://example.com",
                "priority": 5,
            }
            api_response = requests.post(
                f"{API_BASE_URL}/api/browser-tasks", json=task_data, timeout=10
            )

            if api_response.status_code != 201:
                duration_ms = (time.time() - start) * 1000
                self.metrics.add_response(
                    duration_ms, False, f"API Status {api_response.status_code}"
                )
                return False, duration_ms

            # Phase 2: Database query
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM projects;")
            c.fetchall()
            conn.close()

            # Phase 3: Get task status
            tasks = api_response.json().get("data", {})
            if "task_id" in tasks:
                requests.get(f"{API_BASE_URL}/api/browser-tasks/{tasks['task_id']}", timeout=10)

            duration_ms = (time.time() - start) * 1000
            self.metrics.add_response(duration_ms, True)
            return True, duration_ms

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            self.metrics.add_response(duration_ms, False, str(e))
            return False, duration_ms

    def run(self):
        """Execute ST-11."""
        print("\n" + "=" * 70)
        print("ST-11: END-TO-END SYSTEM STRESS TEST")
        print("=" * 70)
        print(f"Concurrent Operations: {self.concurrent_operations}")
        print("Each operation: API call → DB query → Status check")

        with ThreadPoolExecutor(max_workers=self.concurrent_operations) as executor:
            futures = [
                executor.submit(self.stress_operation, op_id)
                for op_id in range(self.concurrent_operations)
            ]

            completed = 0
            for future in as_completed(futures):
                completed += 1
                print(f"  Progress: {completed}/{len(futures)} operations completed")
                try:
                    future.result()
                except Exception as e:
                    print(f"  Error: {e}")

        return self.metrics.get_summary()


def run_all_stress_tests():
    """Run all stress tests and generate report."""
    print("\n" + "=" * 70)
    print("STRESS TEST SUITE: SYSTEM PERFORMANCE & LOAD ANALYSIS")
    print("=" * 70)
    print(f"Start Time: {datetime.now().isoformat()}")
    print(f"Target: {API_BASE_URL}")
    print(f"Database: {DB_PATH}")

    results = {"start_time": datetime.now().isoformat(), "tests": []}

    # Run ST-5
    st5 = ST5_ConcurrentAPILoadTest()
    results["tests"].append(st5.run())

    # Run ST-6
    st6 = ST6_DatabaseQueryPerformance()
    results["tests"].append(st6.run())

    # Run ST-10
    st10 = ST10_BrowserAutomationWorkload()
    results["tests"].append(st10.run())

    # Run ST-11
    st11 = ST11_EndToEndSystemStress()
    results["tests"].append(st11.run())

    results["end_time"] = datetime.now().isoformat()

    # Print summary
    print("\n" + "=" * 70)
    print("STRESS TEST SUMMARY")
    print("=" * 70)

    for test_result in results["tests"]:
        print(f"\n{test_result['test_name']}")
        print(f"  Total Requests: {test_result['total_requests']}")
        print(f"  Success Rate: {test_result['success_rate']}%")
        print(f"  Throughput: {test_result['throughput_rps']} req/sec")
        print("  Response Times (ms):")
        print(f"    Min: {test_result['response_times_ms']['min']}")
        print(f"    Avg: {test_result['response_times_ms']['avg']}")
        print(f"    P95: {test_result['response_times_ms']['p95']}")
        print(f"    P99: {test_result['response_times_ms']['p99']}")
        print(f"    Max: {test_result['response_times_ms']['max']}")

    # Save report
    with open(REPORT_FILE, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n✅ Report saved to: {REPORT_FILE}")
    print("=" * 70 + "\n")

    return results


if __name__ == "__main__":
    run_all_stress_tests()
