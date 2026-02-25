#!/usr/bin/env python3
"""
Distributed Task Router
Routes tasks to agents across multiple nodes with file locking.
"""

import json
import subprocess
from pathlib import Path
from typing import Optional
from agent_task_router import AgentTaskRouter


class DistributedTaskRouter(AgentTaskRouter):
    """Extended task router that supports remote nodes."""

    def _send_to_agent(self, agent_name: str, task: str, work_dir: Path):
        """Send task to agent (local or remote)."""
        # Find agent's node
        agent_info = next((a for a in self.team_config.get('agents', [])
                          if a['name'] == agent_name), None)

        if not agent_info:
            print(f"❌ Agent {agent_name} not found")
            return

        node_ip = agent_info.get('node_ip')

        if node_ip and node_ip != '100.112.58.92':
            # Remote agent - send via SSH
            self._send_to_remote_agent(agent_name, task, work_dir, node_ip)
        else:
            # Local agent - use tmux
            super()._send_to_agent(agent_name, task, work_dir)

    def _send_to_remote_agent(self, agent_name: str, task: str, work_dir: Path, node_ip: str):
        """Send task to remote agent via SSH and submit to LLM."""
        import time as time_module

        # Update session state
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent / 'workers'))
            from session_state_manager import SessionStateManager

            # Update state via SSH (remote)
            state_update = {
                "session_name": agent_name,
                "current_task": task,
                "working_directory": str(work_dir),
                "status": "working"
            }
            import subprocess
            subprocess.run([
                "ssh", node_ip,
                f"python3 -c \"from pathlib import Path; import sys; sys.path.insert(0, str(Path.home() / 'agent_deployment' / 'workers')); from session_state_manager import SessionStateManager; sm = SessionStateManager('{agent_name}'); sm.set_task('{task}', '{work_dir}')\""
            ], capture_output=True, timeout=5)
        except Exception as e:
            print(f"Warning: Could not update remote session state: {e}")

        # Format as direct command to LLM
        task_command = f"{task}. Working directory is {work_dir}. Start now."

        # Send to remote tmux session
        try:
            # Clear any existing input
            subprocess.run(
                ["ssh", node_ip, f"/opt/homebrew/bin/tmux send-keys -t {agent_name} C-c"],
                check=False,
                capture_output=True
            )
            time_module.sleep(0.5)

            # Type task command
            # Need to escape single quotes for SSH
            escaped_task = task_command.replace("'", "'\\''")
            subprocess.run(
                ["ssh", node_ip, f"/opt/homebrew/bin/tmux send-keys -t {agent_name} '{escaped_task}'"],
                check=False,
                capture_output=True
            )
            time_module.sleep(0.2)

            # Submit with Enter
            subprocess.run(
                ["ssh", node_ip, f"/opt/homebrew/bin/tmux send-keys -t {agent_name} Enter"],
                check=False,
                capture_output=True
            )

            print(f"✅ Task sent to {agent_name} on {node_ip}")

        except Exception as e:
            print(f"❌ Failed to send task to remote agent {agent_name}: {e}")

    def show_status(self):
        """Show router status with node information."""
        print("\n" + "="*70)
        print("📊 DISTRIBUTED TASK ROUTER STATUS")
        print("="*70)

        # Show nodes
        nodes = self.team_config.get('nodes', [])
        if nodes:
            print(f"\n🌐 Nodes ({len(nodes)}):")
            for node in nodes:
                status_icon = "🟢" if node.get('status') == 'online' else "🔴"
                agent_count = len(node.get('agents', []))
                print(f"  {status_icon} {node['node_id']} ({node['node_ip']}) - {agent_count} agents")

        # Show active tasks
        print(f"\n🏃 Active Tasks ({len(self.active_tasks)}):")
        if self.active_tasks:
            for agent_name, task in self.active_tasks.items():
                agent_info = next((a for a in self.team_config.get('agents', [])
                                  if a['name'] == agent_name), {})
                node = agent_info.get('node', 'local')
                duration = __import__('time').time() - task['assigned_at']
                print(f"  • {agent_name} [{node}]: {task['description'][:50]}... ({duration:.0f}s)")
        else:
            print("  (none)")

        # Show queued tasks
        print(f"\n📬 Queued Tasks ({len(self.task_queue)}):")
        if self.task_queue:
            for task in self.task_queue:
                print(f"  • [{task['priority']}] {task['description'][:50]}...")
        else:
            print("  (none)")

        # Show available agents by node
        available = self.get_available_agents()

        print(f"\n✅ Available Agents ({len(available)}):")

        # Group by node
        local_agents = [a for a in available if not a.get('node_ip') or a.get('node_ip') == '100.112.58.92']
        remote_agents = [a for a in available if a.get('node_ip') and a.get('node_ip') != '100.112.58.92']

        if local_agents:
            print(f"  📍 Local (100.112.58.92):")
            for agent in local_agents:
                print(f"    • {agent['name']} ({agent['role']})")

        if remote_agents:
            # Group by node
            nodes_dict = {}
            for agent in remote_agents:
                node_ip = agent.get('node_ip', 'unknown')
                if node_ip not in nodes_dict:
                    nodes_dict[node_ip] = []
                nodes_dict[node_ip].append(agent)

            for node_ip, agents in nodes_dict.items():
                node_name = next((n['node_id'] for n in nodes if n['node_ip'] == node_ip), node_ip)
                print(f"  📍 {node_name} ({node_ip}):")
                for agent in agents:
                    print(f"    • {agent['name']} ({agent['role']})")

        # Show locks
        from file_lock_manager import FileLockManager
        lock_manager = FileLockManager("router")
        locks = lock_manager.list_all_locks()
        print(f"\n🔒 Active Directory Locks ({len(locks)}):")
        if locks:
            for lock in locks:
                print(f"  • {lock['directory']}")
                print(f"    Held by: {lock['agent']}")
        else:
            print("  (none)")


def main():
    """CLI entry point."""
    import sys

    router = DistributedTaskRouter()

    if len(sys.argv) < 2:
        router.show_status()
        print("\nUsage:")
        print("  python distributed_task_router.py status")
        print("  python distributed_task_router.py assign <description> <work_dir> [agent_name]")
        print("  python distributed_task_router.py complete <agent_name>")
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

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
