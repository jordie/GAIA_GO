#!/usr/bin/env python3
"""
Agent Task Router with File Locking
Routes tasks to agents and ensures only one agent works on a directory at a time.
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Optional
from file_lock_manager import FileLockManager, DirectoryLock
import subprocess


class AgentTaskRouter:
    """Routes tasks to agents with automatic file locking."""

    def __init__(self, team_config_path: str = "team_config.json"):
        self.team_config_path = Path(team_config_path)
        self.load_team_config()
        self.task_queue: List[Dict] = []
        self.active_tasks: Dict[str, Dict] = {}

    def load_team_config(self):
        """Load team configuration."""
        if not self.team_config_path.exists():
            print("⚠️  Team config not found. Run setup_dev_team.py first.")
            self.team_config = {"agents": []}
            return

        with open(self.team_config_path, 'r') as f:
            self.team_config = json.load(f)

        print(f"✅ Loaded {len(self.team_config.get('agents', []))} agents")

    def get_available_agents(self, role: Optional[str] = None) -> List[Dict]:
        """Get list of available agents, optionally filtered by role."""
        agents = self.team_config.get("agents", [])

        if role:
            agents = [a for a in agents if a.get("role") == role]

        # Filter out agents currently working
        available = [a for a in agents if a["name"] not in self.active_tasks]

        return available

    def assign_task(
        self,
        task_description: str,
        work_directory: Path,
        agent_name: Optional[str] = None,
        role: Optional[str] = None,
        priority: str = "normal"
    ) -> bool:
        """
        Assign a task to an agent with automatic locking.

        Args:
            task_description: Description of the task
            work_directory: Directory where work will be performed
            agent_name: Specific agent to assign to (optional)
            role: Agent role to filter by (optional)
            priority: Task priority (low, normal, high, critical)

        Returns:
            True if task assigned, False otherwise
        """
        work_directory = Path(work_directory).absolute()

        # Create task object
        task = {
            "id": f"task_{int(time.time() * 1000)}",
            "description": task_description,
            "work_directory": str(work_directory),
            "priority": priority,
            "requested_agent": agent_name,
            "requested_role": role,
            "status": "pending",
            "created_at": time.time()
        }

        # Find agent
        if agent_name:
            agents = [a for a in self.team_config.get("agents", [])
                     if a["name"] == agent_name]
        else:
            agents = self.get_available_agents(role)

        if not agents:
            print(f"❌ No available agents found (role: {role}, name: {agent_name})")
            self.task_queue.append(task)
            return False

        agent = agents[0]

        # Check if work directory is locked
        lock_manager = FileLockManager("router")
        if lock_manager.is_locked(work_directory):
            lock_holder = lock_manager.get_lock_holder(work_directory)
            print(f"⏳ Directory {work_directory} is locked by {lock_holder['agent']}")
            print(f"   Task queued: {task_description}")
            self.task_queue.append(task)
            return False

        # Assign task
        print(f"\n📋 Assigning Task: {task_description}")
        print(f"   Agent: {agent['name']} ({agent['role']})")
        print(f"   Directory: {work_directory}")
        print(f"   Priority: {priority}")

        # Send task to agent via tmux
        self._send_to_agent(agent["name"], task_description, work_directory)

        # Track active task
        self.active_tasks[agent["name"]] = task
        task["status"] = "assigned"
        task["assigned_to"] = agent["name"]
        task["assigned_at"] = time.time()

        return True

    def _send_to_agent(self, agent_name: str, task: str, work_dir: Path):
        """Send task to agent's tmux session and submit it to the LLM."""
        # Create work directory if it doesn't exist
        Path(work_dir).mkdir(parents=True, exist_ok=True)

        # Update session state
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent / 'workers'))
            from session_state_manager import SessionStateManager

            state_manager = SessionStateManager(agent_name)
            state_manager.set_task(task, str(work_dir))
        except Exception as e:
            print(f"Warning: Could not update session state: {e}")

        # Format as a direct command/question to the LLM
        # This will be typed into the Claude/Gemini prompt
        task_command = f"{task}. Working directory is {work_dir}. Start now."

        # Send to tmux session
        try:
            # Clear any existing input first
            subprocess.run(
                ["tmux", "send-keys", "-t", agent_name, "C-c"],
                check=False,
                capture_output=True
            )
            time.sleep(0.5)

            # Type the task command into the prompt
            subprocess.run(
                ["tmux", "send-keys", "-t", agent_name, task_command],
                check=False,
                capture_output=True
            )
            time.sleep(0.2)

            # Submit it (press Enter)
            subprocess.run(
                ["tmux", "send-keys", "-t", agent_name, "Enter"],
                check=False,
                capture_output=True
            )

            print(f"✅ Task sent to {agent_name}")
        except Exception as e:
            print(f"❌ Failed to send task to {agent_name}: {e}")

    def mark_task_complete(self, agent_name: str):
        """Mark agent's task as complete."""
        if agent_name in self.active_tasks:
            task = self.active_tasks[agent_name]
            task["status"] = "completed"
            task["completed_at"] = time.time()

            duration = task["completed_at"] - task["assigned_at"]
            print(f"✅ Task completed by {agent_name} in {duration:.1f}s")

            # Update session state
            try:
                import sys
                sys.path.insert(0, str(Path(__file__).parent / 'workers'))
                from session_state_manager import SessionStateManager

                state_manager = SessionStateManager(agent_name)
                state_manager.clear_task()
            except Exception as e:
                print(f"Warning: Could not update session state: {e}")

            del self.active_tasks[agent_name]

            # Process queue for next task
            self.process_queue()

    def process_queue(self):
        """Process queued tasks."""
        if not self.task_queue:
            return

        print(f"\n📬 Processing task queue ({len(self.task_queue)} tasks)...")

        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        self.task_queue.sort(key=lambda t: priority_order.get(t["priority"], 2))

        # Try to assign queued tasks
        assigned = []
        for task in self.task_queue:
            if self.assign_task(
                task["description"],
                Path(task["work_directory"]),
                agent_name=task.get("requested_agent"),
                role=task.get("requested_role"),
                priority=task["priority"]
            ):
                assigned.append(task)

        # Remove assigned tasks from queue
        for task in assigned:
            self.task_queue.remove(task)

    def show_status(self):
        """Show router status."""
        print("\n" + "="*70)
        print("📊 AGENT TASK ROUTER STATUS")
        print("="*70)

        print(f"\n🏃 Active Tasks ({len(self.active_tasks)}):")
        if self.active_tasks:
            for agent_name, task in self.active_tasks.items():
                duration = time.time() - task["assigned_at"]
                print(f"  • {agent_name}: {task['description'][:50]}... ({duration:.0f}s)")
        else:
            print("  (none)")

        print(f"\n📬 Queued Tasks ({len(self.task_queue)}):")
        if self.task_queue:
            for task in self.task_queue:
                print(f"  • [{task['priority']}] {task['description'][:50]}...")
        else:
            print("  (none)")

        available = self.get_available_agents()
        print(f"\n✅ Available Agents ({len(available)}):")
        for agent in available:
            print(f"  • {agent['name']} ({agent['role']})")

        # Show locks
        lock_manager = FileLockManager("router")
        locks = lock_manager.list_all_locks()
        print(f"\n🔒 Active Directory Locks ({len(locks)}):")
        for lock in locks:
            print(f"  • {lock['directory']}")
            print(f"    Held by: {lock['agent']}")


def main():
    """CLI entry point."""
    import sys

    router = AgentTaskRouter()

    if len(sys.argv) < 2:
        router.show_status()
        print("\nUsage:")
        print("  python agent_task_router.py status")
        print("  python agent_task_router.py assign <description> <work_dir> [agent_name]")
        print("  python agent_task_router.py complete <agent_name>")
        print("  python agent_task_router.py queue")
        sys.exit(0)

    command = sys.argv[1]

    if command == "status":
        router.show_status()

    elif command == "assign":
        if len(sys.argv) < 4:
            print("Error: Usage: assign <description> <work_dir> [agent_name]")
            sys.exit(1)

        description = sys.argv[2]
        work_dir = sys.argv[3]
        agent_name = sys.argv[4] if len(sys.argv) > 4 else None

        router.assign_task(description, Path(work_dir), agent_name=agent_name)

    elif command == "complete":
        if len(sys.argv) < 3:
            print("Error: Usage: complete <agent_name>")
            sys.exit(1)

        agent_name = sys.argv[2]
        router.mark_task_complete(agent_name)

    elif command == "queue":
        router.process_queue()

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
