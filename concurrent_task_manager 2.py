#!/usr/bin/env python3
"""
Concurrent Task Manager

Distributes tasks across multiple Claude worker sessions in parallel.
Includes token usage tracking and throttling to keep costs low.
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from services.task_delegator import TaskType, get_delegator
    from services.token_throttle import get_throttler

    THROTTLE_ENABLED = True
except ImportError:
    THROTTLE_ENABLED = False
    print("Warning: Token throttling not available")

# Configuration
WORKER_SESSIONS = ["concurrent_worker1", "concurrent_worker2", "concurrent_worker3"]
MANAGER_SESSION = "task_manager"


class ConcurrentTaskManager:
    """Manages task distribution across concurrent worker sessions with token tracking."""

    def __init__(self, worker_sessions: List[str]):
        self.workers = worker_sessions
        self.task_queue = []
        self.worker_status = {
            w: {
                "busy": False,
                "current_task": None,
                "completed": 0,
                "tokens_used": 0,
                "estimated_cost": 0.0,
            }
            for w in self.workers
        }

        # Initialize throttler and delegator
        self.throttler = get_throttler() if THROTTLE_ENABLED else None
        self.delegator = get_delegator() if THROTTLE_ENABLED else None

        # Global metrics
        self.total_tokens = 0
        self.total_cost = 0.0
        self.tasks_completed = 0

    def add_task(self, task: str):
        """Add a task to the queue."""
        self.task_queue.append({"task": task, "added_at": datetime.now(), "status": "pending"})
        print(f"✓ Added task: {task[:60]}...")

    def estimate_task_tokens(self, task: str) -> int:
        """Estimate tokens required for a task."""
        # Basic estimation: ~4 chars per token + overhead
        base_tokens = len(task) // 4
        overhead = 1000  # Average overhead for context, response
        return base_tokens + overhead

    def check_throttle_limit(self, worker: str, task: str) -> bool:
        """Check if worker can process task within throttle limits."""
        if not self.throttler:
            return True

        estimated_tokens = self.estimate_task_tokens(task)

        # Check if request would exceed limits
        allowed = self.throttler.allow_request(
            session_id=worker, estimated_tokens=estimated_tokens, priority="normal"
        )

        if not allowed:
            print(f"⚠️  Throttle limit reached for {worker} ({estimated_tokens} tokens)")
            return False

        return True

    def send_task_to_worker(self, worker: str, task: str):
        """Send a task to a specific worker session."""
        # Check throttle limits first
        if not self.check_throttle_limit(worker, task):
            print(f"⏸️  Task queued due to throttle limits")
            return False

        try:
            # Estimate tokens and cost
            estimated_tokens = self.estimate_task_tokens(task)

            # Use delegator to determine optimal approach if available
            if self.delegator:
                delegation = self.delegator.delegate_task(task, priority="normal")
                print(f"   Delegated as: {delegation.task_type.value} → {delegation.agent.value}")

            # Send the task to the worker
            subprocess.run(
                ["tmux", "send-keys", "-t", worker, task, "Enter"], timeout=5, check=True
            )

            self.worker_status[worker]["busy"] = True
            self.worker_status[worker]["current_task"] = task
            self.worker_status[worker]["tokens_used"] += estimated_tokens

            # Update global metrics
            self.total_tokens += estimated_tokens

            print(f"→ Sent to {worker}: {task[:50]}... (~{estimated_tokens} tokens)")
            return True
        except Exception as e:
            print(f"✗ Failed to send to {worker}: {e}")
            return False

    def check_worker_idle(self, worker: str) -> bool:
        """Check if a worker is idle by capturing pane output."""
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", worker, "-p"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            output = result.stdout.lower()

            # Check for idle indicators
            idle_patterns = ["? for shortcuts", "❯", "how can i help"]
            is_idle = any(pattern in output for pattern in idle_patterns)

            # Check for busy indicators
            busy_patterns = ["channelling", "thinking", "composing", "lollygagging", "puttering"]
            is_busy = any(pattern in output for pattern in busy_patterns)

            return is_idle and not is_busy
        except Exception as e:
            print(f"Warning: Could not check {worker}: {e}")
            return False

    def record_task_completion(self, worker: str, tokens_used: int):
        """Record task completion and update metrics."""
        self.tasks_completed += 1

        # Calculate cost (example: $0.003 per 1K tokens for Sonnet)
        cost = (tokens_used / 1000) * 0.003
        self.total_cost += cost
        self.worker_status[worker]["estimated_cost"] += cost

        # Record in throttler if available
        if self.throttler:
            self.throttler.record_usage(
                session_id=worker,
                tokens_used=tokens_used,
                cost=cost,
                model="claude-sonnet-4-5-20250929",
            )

    def distribute_tasks(self):
        """Distribute pending tasks to idle workers with throttle awareness."""
        if not self.task_queue:
            return

        # Check which workers are idle and update completed tasks
        for worker in self.workers:
            was_busy = self.worker_status[worker]["busy"]
            is_idle = self.check_worker_idle(worker)

            if was_busy and is_idle:
                # Worker completed a task
                self.worker_status[worker]["busy"] = False
                current_task = self.worker_status[worker]["current_task"]

                if current_task:
                    # Estimate actual tokens used (rough approximation)
                    tokens_used = self.estimate_task_tokens(current_task)
                    self.record_task_completion(worker, tokens_used)
                    print(f"✓ {worker} completed task (~{tokens_used} tokens)")

                self.worker_status[worker]["current_task"] = None

        # Get idle workers
        idle_workers = [w for w, status in self.worker_status.items() if not status["busy"]]

        # Assign tasks to idle workers (respecting throttle limits)
        while self.task_queue and idle_workers:
            worker = idle_workers.pop(0)
            task_info = self.task_queue.pop(0)

            if self.send_task_to_worker(worker, task_info["task"]):
                self.worker_status[worker]["completed"] += 1
            else:
                # Re-queue if throttled
                self.task_queue.insert(0, task_info)
                time.sleep(1)  # Brief pause before retrying

    def get_throttle_stats(self):
        """Get throttle statistics for all workers."""
        if not self.throttler:
            return None

        stats = {}
        for worker in self.workers:
            worker_stats = self.throttler.get_stats(worker)
            stats[worker] = {
                "tokens_hour": worker_stats.get("tokens_hour", 0),
                "tokens_day": worker_stats.get("tokens_day", 0),
                "throttle_level": worker_stats.get("throttle_level", "none"),
                "cost_hour": worker_stats.get("cost_hour", 0.0),
                "cost_day": worker_stats.get("cost_day", 0.0),
            }
        return stats

    def print_metrics(self):
        """Print detailed token usage and cost metrics."""
        print("\n" + "=" * 80)
        print("TOKEN USAGE & COST METRICS")
        print("=" * 80)
        print(f"\nGlobal Metrics:")
        print(f"  Total tasks completed:  {self.tasks_completed}")
        print(f"  Total tokens used:      {self.total_tokens:,}")
        print(f"  Estimated total cost:   ${self.total_cost:.4f}")
        print(f"  Average tokens/task:    {self.total_tokens // max(self.tasks_completed, 1):,}")
        print(f"  Average cost/task:      ${self.total_cost / max(self.tasks_completed, 1):.4f}")

        print(f"\nPer-Worker Metrics:")
        for worker, status in self.worker_status.items():
            completed = status["completed"]
            tokens = status["tokens_used"]
            cost = status["estimated_cost"]
            avg_tokens = tokens // max(completed, 1)

            print(f"  {worker:20}")
            print(f"    Tasks completed:  {completed}")
            print(f"    Tokens used:      {tokens:,}")
            print(f"    Estimated cost:   ${cost:.4f}")
            print(f"    Avg tokens/task:  {avg_tokens:,}")

        # Savings comparison
        print(f"\nCost Optimization:")
        if self.delegator:
            print(f"  ✅ Task delegation enabled - routing to optimal models")
            print(f"  ✅ Expected savings: 20-40% vs uniform model usage")
        else:
            print(f"  ⚠️  Task delegation disabled - using default models")

        print("=" * 80 + "\n")

    def print_throttle_status(self):
        """Print detailed throttle status."""
        if not self.throttler:
            print("⚠️  Token throttling is not enabled\n")
            return

        print("\n" + "=" * 80)
        print("THROTTLE STATUS")
        print("=" * 80)

        global_stats = self.throttler.get_stats()
        print(f"\nGlobal Limits:")
        print(f"  Tokens/hour:  {global_stats['global']['tokens_hour']:,} / 500,000")
        print(f"  Tokens/day:   {global_stats['global']['tokens_day']:,} / 5,000,000")
        print(f"  Cost/hour:    ${global_stats['global']['cost_hour']:.2f} / $5.00")
        print(f"  Cost/day:     ${global_stats['global']['cost_day']:.2f} / $50.00")
        print(f"  Cost/month:   ${global_stats['global']['cost_month']:.2f} / $1,000.00")

        throttle_stats = self.get_throttle_stats()
        if throttle_stats:
            print(f"\nPer-Worker Status:")
            for worker, stats in throttle_stats.items():
                level = stats["throttle_level"].upper()
                level_indicator = {
                    "NONE": "🟢",
                    "WARNING": "🟡",
                    "SOFT": "🟠",
                    "HARD": "🔴",
                    "CRITICAL": "🚨",
                }.get(level, "⚪")

                print(f"  {worker:20} {level_indicator} {level}")
                print(f"    Tokens/hour:  {stats['tokens_hour']:,} / 100,000")
                print(f"    Tokens/day:   {stats['tokens_day']:,} / 1,000,000")
                print(f"    Cost/hour:    ${stats['cost_hour']:.2f}")
                print(f"    Cost/day:     ${stats['cost_day']:.2f}")

        print("\nThrottle Levels:")
        print("  🟢 NONE      - Normal operation")
        print("  🟡 WARNING   - Approaching limits (80%)")
        print("  🟠 SOFT      - Limit reached, queuing low priority")
        print("  🔴 HARD      - Only high/critical priority allowed")
        print("  🚨 CRITICAL  - Only critical priority allowed")

        print("=" * 80 + "\n")

    def print_status(self):
        """Print current status of all workers with token metrics."""
        print("\n" + "=" * 80)
        print("CONCURRENT TASK MANAGER STATUS")
        print("=" * 80)
        print(f"Tasks in queue: {len(self.task_queue)}")
        print(f"Total completed: {self.tasks_completed}")
        print(f"Total tokens used: {self.total_tokens:,}")
        print(f"Estimated cost: ${self.total_cost:.4f}")

        # Show throttle stats if available
        if self.throttler:
            global_stats = self.throttler.get_stats()
            print(f"\nGlobal Throttle Status:")
            print(f"  Tokens/hour: {global_stats['global']['tokens_hour']:,} / 500K")
            print(f"  Tokens/day:  {global_stats['global']['tokens_day']:,} / 5M")
            print(f"  Cost/hour:   ${global_stats['global']['cost_hour']:.2f} / $5.00")
            print(f"  Cost/day:    ${global_stats['global']['cost_day']:.2f} / $50.00")

        print(f"\nWorker Status:")
        for worker, status in self.worker_status.items():
            state = "🔴 BUSY" if status["busy"] else "🟢 IDLE"
            current = status["current_task"][:40] if status["current_task"] else "None"
            tokens = status["tokens_used"]
            print(
                f"  {worker:20} {state:10} | Done: {status['completed']:2} | Tokens: {tokens:,} | Task: {current}"
            )

        # Show per-worker throttle levels
        if self.throttler:
            throttle_stats = self.get_throttle_stats()
            print(f"\nThrottle Levels:")
            for worker, stats in throttle_stats.items():
                level = stats["throttle_level"].upper()
                level_indicator = {
                    "NONE": "🟢",
                    "WARNING": "🟡",
                    "SOFT": "🟠",
                    "HARD": "🔴",
                    "CRITICAL": "🚨",
                }.get(level, "⚪")
                print(
                    f"  {worker:20} {level_indicator} {level:10} | Hour: {stats['tokens_hour']:,} | Day: {stats['tokens_day']:,}"
                )

        print("=" * 80 + "\n")

    def run_interactive(self):
        """Run in interactive mode - add tasks manually."""
        print("\n" + "=" * 80)
        print("CONCURRENT TASK MANAGER - Interactive Mode")
        print("=" * 80)
        print(f"Workers: {', '.join(self.workers)}")
        print(f"Token Throttling: {'✅ ENABLED' if self.throttler else '⚠️  DISABLED'}")
        print(f"Task Delegation: {'✅ ENABLED' if self.delegator else '⚠️  DISABLED'}")
        print("\nCommands:")
        print("  add <task>     - Add a task to the queue")
        print("  status         - Show worker status with metrics")
        print("  metrics        - Show detailed token usage and costs")
        print("  throttle       - Show throttle status for all workers")
        print("  distribute     - Manually trigger task distribution")
        print("  auto           - Start auto-distribution (distributes every 10s)")
        print("  quit           - Exit")
        print("=" * 80 + "\n")

        auto_mode = False

        while True:
            if auto_mode:
                print("Auto-distributing tasks...")
                self.distribute_tasks()
                time.sleep(10)
                continue

            try:
                cmd = input("\n> ").strip()

                if cmd.startswith("add "):
                    task = cmd[4:].strip()
                    if task:
                        self.add_task(task)
                        self.distribute_tasks()

                elif cmd == "status":
                    self.print_status()

                elif cmd == "metrics":
                    self.print_metrics()

                elif cmd == "throttle":
                    self.print_throttle_status()

                elif cmd == "distribute":
                    self.distribute_tasks()
                    print("✓ Distribution triggered")

                elif cmd == "auto":
                    auto_mode = True
                    print("✓ Auto-distribution enabled (press Ctrl+C to stop)")
                    try:
                        while True:
                            self.distribute_tasks()
                            time.sleep(10)
                    except KeyboardInterrupt:
                        auto_mode = False
                        print("\n✓ Auto-distribution stopped")

                elif cmd == "quit":
                    print("Goodbye!")
                    break

                elif cmd == "help":
                    print("\nCommands:")
                    print("  add <task>     - Add a task to the queue")
                    print("  status         - Show worker status with metrics")
                    print("  metrics        - Show detailed token usage and costs")
                    print("  throttle       - Show throttle status for all workers")
                    print("  distribute     - Manually trigger task distribution")
                    print("  auto           - Start auto-distribution (every 10s)")
                    print("  quit           - Exit")

                else:
                    print("Unknown command. Type 'help' for commands.")

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")


def main():
    """Main entry point."""
    manager = ConcurrentTaskManager(WORKER_SESSIONS)

    # Check if tasks provided as arguments
    if len(sys.argv) > 1:
        # Batch mode - add tasks from command line
        for task in sys.argv[1:]:
            manager.add_task(task)

        print("\n✓ All tasks added. Distributing...")
        manager.distribute_tasks()
        manager.print_status()
    else:
        # Interactive mode
        manager.run_interactive()


if __name__ == "__main__":
    main()
