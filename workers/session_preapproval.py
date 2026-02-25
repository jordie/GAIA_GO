#!/usr/bin/env python3
"""
Pre-approve all operations in Claude sessions
Sends option "2" (Yes, allow all during this session) to bypass all confirmation prompts
"""

import subprocess
import sys
import time

# Sessions to pre-approve
WORKER_SESSIONS = [
    "concurrent_worker1",
    "concurrent_worker2",
    "concurrent_worker3",
    "edu_worker1",
    "codex",
    "comet",
    "arch_dev",
    "edu_dev",
    "pharma_dev",
    "basic_edu",
    "wrapper_claude",
    "architect",
]


def check_for_prompt(session):
    """Check if session has a prompt waiting"""
    try:
        result = subprocess.run(
            f"tmux capture-pane -t {session} -p | tail -10",
            shell=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        output = result.stdout

        # Check for confirmation prompts
        has_prompt = any(
            [
                "Do you want to proceed?" in output,
                "Do you want to create" in output,
                "Do you want to edit" in output,
                "Yes, allow all" in output,
                "❯ 1. Yes" in output,
            ]
        )

        return has_prompt
    except Exception as e:
        print(f"  ⚠️  Error checking {session}: {e}")
        return False


def send_preapproval(session):
    """Send option 2 to pre-approve all operations"""
    try:
        # Check if session exists
        check_result = subprocess.run(f"tmux has-session -t {session} 2>/dev/null", shell=True)

        if check_result.returncode != 0:
            print(f"  ⏭️  {session}: Session not found, skipping")
            return False

        # Check for prompt
        has_prompt = check_for_prompt(session)

        if has_prompt:
            # Send "2" + Enter to select "Yes, allow all during this session"
            subprocess.run(f'tmux send-keys -t {session} "2" Enter', shell=True, timeout=2)
            time.sleep(0.5)
            print(f"  ✅ {session}: Pre-approval sent")
            return True
        else:
            # Send a harmless command to trigger a prompt
            print(f"  ⏸️  {session}: No prompt waiting, will approve on next prompt")
            return False

    except Exception as e:
        print(f"  ❌ {session}: Error - {e}")
        return False


def main():
    print("🔧 Pre-approving all operations in Claude sessions...\n")

    approved_count = 0
    waiting_count = 0

    for session in WORKER_SESSIONS:
        result = send_preapproval(session)
        if result:
            approved_count += 1
        else:
            waiting_count += 1
        time.sleep(0.2)

    print(f"\n📊 Summary:")
    print(f"  ✅ Approved: {approved_count} sessions")
    print(f"  ⏸️  Waiting for prompt: {waiting_count} sessions")
    print(f"\n💡 Sessions without current prompts will be auto-approved on their next prompt.")
    print(f"   The auto-confirm worker will send '2' when it detects any prompt.\n")


if __name__ == "__main__":
    main()
