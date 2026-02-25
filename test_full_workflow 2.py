#!/usr/bin/env python3
"""
Complete workflow demonstration:
Agent receives task → Acquires lock → Performs work → Releases lock
"""

from file_lock_manager import DirectoryLock
from pathlib import Path
import subprocess
import time

def execute_task_with_locking(agent_name, task_description, work_dir):
    """Execute a task with automatic file locking."""

    print(f"\n{'='*70}")
    print(f"🤖 Agent: {agent_name}")
    print(f"📋 Task: {task_description}")
    print(f"📁 Work Directory: {work_dir}")
    print(f"{'='*70}\n")

    # Ensure work directory exists
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Acquire lock with timeout
        print(f"🔒 Acquiring lock on {work_dir}...")
        with DirectoryLock(agent_name, work_dir, timeout=60) as lock:
            print(f"✅ Lock acquired by {agent_name}!")
            print(f"⏰ Lock acquired at: {time.strftime('%H:%M:%S')}")

            # Simulate work
            print(f"\n🔨 Performing work...")

            # Example: List Python files and count them
            result = subprocess.run(
                ['find', str(work_dir), '-name', '*.py'],
                capture_output=True,
                text=True
            )

            py_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
            py_file_count = len([f for f in py_files if f])

            print(f"   Found {py_file_count} Python files in {work_dir}")

            # Simulate some processing time
            print(f"   Processing...")
            time.sleep(2)

            print(f"\n✅ Work completed!")
            print(f"⏰ Completed at: {time.strftime('%H:%M:%S')}")

            # Lock automatically released when exiting 'with' block

    except TimeoutError as e:
        print(f"❌ Could not acquire lock: {e}")
        return False
    except Exception as e:
        print(f"❌ Error executing task: {e}")
        return False

    print(f"🔓 Lock released by {agent_name}")
    return True


if __name__ == "__main__":
    # Test 1: Single agent
    print("\n" + "="*70)
    print("TEST 1: Single Agent Task Execution")
    print("="*70)

    execute_task_with_locking(
        "dev-backend-1",
        "List all Python files in the current directory",
        "/Users/jgirmay/Desktop/gitrepo/pyWork/architect"
    )

    # Test 2: Simulate two agents trying to work on same directory
    print("\n" + "="*70)
    print("TEST 2: File Locking Prevents Conflicts")
    print("="*70)

    import threading

    def agent1_work():
        print("\n[Agent 1] Starting...")
        execute_task_with_locking(
            "dev-backend-1",
            "Agent 1 working on shared directory",
            "/tmp/shared_work"
        )

    def agent2_work():
        time.sleep(1)  # Start slightly after agent 1
        print("\n[Agent 2] Starting...")
        execute_task_with_locking(
            "dev-frontend-1",
            "Agent 2 also wants shared directory",
            "/tmp/shared_work"
        )

    # Run both agents
    thread1 = threading.Thread(target=agent1_work)
    thread2 = threading.Thread(target=agent2_work)

    thread1.start()
    thread2.start()

    thread1.join()
    thread2.join()

    print("\n" + "="*70)
    print("✅ All tests complete!")
    print("="*70)
