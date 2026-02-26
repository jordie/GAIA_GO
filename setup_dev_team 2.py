#!/usr/bin/env python3
"""
Development Team Setup using Go Wrapper
Spawns a complete development team with role-based agents.
"""

import subprocess
import time
import json
import sys
from pathlib import Path
from typing import List, Dict

# Team configuration
TEAM_CONFIG = {
    "developers": [
        {"name": "dev-backend-1", "tool": "codex", "role": "Backend Developer", "focus": "API development"},
        {"name": "dev-frontend-1", "tool": "codex", "role": "Frontend Developer", "focus": "UI/UX implementation"},
        {"name": "dev-fullstack-1", "tool": "gemini", "role": "Full Stack Developer", "focus": "Feature development"},
    ],
    "qa": [
        {"name": "qa-tester-1", "tool": "codex", "role": "QA Engineer", "focus": "Test automation"},
        {"name": "qa-tester-2", "tool": "codex", "role": "QA Engineer", "focus": "Manual testing"},
    ],
    "managers": [
        {"name": "manager-product", "tool": "claude", "role": "Product Manager", "focus": "Requirements and planning"},
        {"name": "manager-tech", "tool": "claude", "role": "Technical Manager", "focus": "Architecture decisions"},
    ],
    "operations": [
        {"name": "architect", "tool": "claude", "role": "Solutions Architect", "focus": "System design"},
        {"name": "devops", "tool": "gemini", "role": "DevOps Engineer", "focus": "CI/CD and infrastructure"},
    ]
}

GO_WRAPPER_DIR = Path("/Users/jgirmay/Desktop/gitrepo/pyWork/architect/go_wrapper")
TAILSCALE_IP = "100.112.58.92"  # Tailscale IP
API_BASE = f"http://{TAILSCALE_IP}:8151"


class DevTeamManager:
    """Manages the development team agents."""

    def __init__(self):
        self.go_wrapper = GO_WRAPPER_DIR / "wrapper"
        self.api_server = GO_WRAPPER_DIR / "apiserver"
        self.agents: List[Dict] = []

    def check_wrapper_exists(self) -> bool:
        """Check if go wrapper binaries exist."""
        if not self.go_wrapper.exists():
            print(f"❌ Wrapper binary not found at {self.go_wrapper}")
            print(f"   Run: cd {GO_WRAPPER_DIR} && go build -o wrapper main.go")
            return False
        if not self.api_server.exists():
            print(f"❌ API server binary not found at {self.api_server}")
            print(f"   Run: cd {GO_WRAPPER_DIR} && go build -o apiserver cmd/apiserver/main.go")
            return False
        return True

    def is_api_server_running(self) -> bool:
        """Check if API server is running."""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex((TAILSCALE_IP, 8151))
        sock.close()
        return result == 0

    def start_api_server(self):
        """Start the go wrapper API server."""
        print("🚀 Starting Go Wrapper API Server...")

        # Create data directory if not exists
        data_dir = GO_WRAPPER_DIR / "data"
        data_dir.mkdir(exist_ok=True)

        # Start API server in background (simplified flags)
        cmd = [
            str(self.api_server),
            "-host", "0.0.0.0",  # Listen on all interfaces for Tailscale access
            "-port", "8151"
        ]

        log_file = GO_WRAPPER_DIR / "logs" / "apiserver.log"
        log_file.parent.mkdir(exist_ok=True)

        with open(log_file, 'w') as f:
            subprocess.Popen(cmd, stdout=f, stderr=f, cwd=GO_WRAPPER_DIR)

        # Wait for server to start
        print("⏳ Waiting for API server to start...")
        for i in range(10):
            time.sleep(1)
            if self.is_api_server_running():
                print(f"✅ API Server running at {API_BASE}")
                print(f"📊 Dashboard: {API_BASE}")
                print(f"📈 Performance: {API_BASE}/performance")
                print(f"🎮 Interactive: {API_BASE}/interactive")
                return True

        print("❌ API server failed to start within 10 seconds")
        return False

    def spawn_agent(self, name: str, tool: str, role: str, focus: str) -> bool:
        """Spawn an agent using the go wrapper."""
        print(f"\n👤 Spawning {role}: {name}")
        print(f"   Tool: {tool}")
        print(f"   Focus: {focus}")

        # Map tool names to actual commands
        tool_commands = {
            "codex": "claude",  # Using Claude for codex
            "gemini": "gemini",
            "claude": "claude"
        }

        actual_command = tool_commands.get(tool, "claude")

        # Spawn agent via wrapper
        cmd = [str(self.go_wrapper), name, actual_command]

        try:
            # Create tmux session for agent
            tmux_cmd = [
                "tmux", "new-session", "-d", "-s", name,
                str(self.go_wrapper), name, actual_command
            ]

            result = subprocess.run(tmux_cmd, capture_output=True, text=True, cwd=GO_WRAPPER_DIR)

            if result.returncode == 0:
                print(f"   ✅ Agent spawned in tmux session: {name}")

                self.agents.append({
                    "name": name,
                    "tool": tool,
                    "role": role,
                    "focus": focus,
                    "status": "running"
                })

                return True
            else:
                print(f"   ❌ Failed to spawn agent: {result.stderr}")
                return False

        except Exception as e:
            print(f"   ❌ Error spawning agent: {e}")
            return False

    def spawn_team(self):
        """Spawn all team members."""
        print("\n" + "="*70)
        print("🏗️  DEVELOPMENT TEAM SETUP")
        print("="*70)

        total_agents = 0
        successful = 0

        for category, members in TEAM_CONFIG.items():
            print(f"\n📋 {category.upper()} ({len(members)} members)")
            print("-" * 70)

            for member in members:
                total_agents += 1
                if self.spawn_agent(
                    member["name"],
                    member["tool"],
                    member["role"],
                    member["focus"]
                ):
                    successful += 1

                # Small delay between spawning agents
                time.sleep(0.5)

        print("\n" + "="*70)
        print(f"✅ Team Setup Complete: {successful}/{total_agents} agents spawned")
        print("="*70)

        return successful == total_agents

    def list_agents(self):
        """List all spawned agents."""
        print("\n📊 TEAM ROSTER")
        print("="*70)

        for category, members in TEAM_CONFIG.items():
            print(f"\n{category.upper()}:")
            for member in members:
                agent = next((a for a in self.agents if a["name"] == member["name"]), None)
                status = "🟢" if agent and agent["status"] == "running" else "🔴"
                print(f"  {status} {member['name']:<20} | {member['role']:<25} | {member['tool']}")

    def show_tmux_sessions(self):
        """Show all tmux sessions for team members."""
        print("\n🖥️  TMUX SESSIONS")
        print("="*70)

        result = subprocess.run(["tmux", "list-sessions"], capture_output=True, text=True)

        if result.returncode == 0:
            sessions = result.stdout.strip().split('\n')
            team_sessions = [s for s in sessions if any(member["name"] in s for category in TEAM_CONFIG.values() for member in category)]

            if team_sessions:
                for session in team_sessions:
                    print(f"  {session}")
            else:
                print("  No team sessions found")
        else:
            print("  ❌ Failed to list tmux sessions")

    def save_config(self):
        """Save team configuration to file."""
        config_file = Path("team_config.json")

        config = {
            "team": TEAM_CONFIG,
            "agents": self.agents,
            "api_server": API_BASE,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)

        print(f"\n💾 Team configuration saved to {config_file}")

    def show_dashboard_urls(self):
        """Show dashboard URLs."""
        print("\n🎯 DASHBOARDS")
        print("="*70)
        print(f"📊 Main Dashboard:      {API_BASE}")
        print(f"🎮 Interactive Control: {API_BASE}/interactive")
        print(f"📈 Performance:         {API_BASE}/performance")
        print(f"🗄️  Database Queries:    {API_BASE}/database")
        print(f"▶️  Session Replay:      {API_BASE}/replay")
        print(f"🔍 Query Builder:       {API_BASE}/query")

    def run(self):
        """Main execution."""
        # Check prerequisites
        if not self.check_wrapper_exists():
            sys.exit(1)

        # Start API server if not running
        if not self.is_api_server_running():
            if not self.start_api_server():
                sys.exit(1)
        else:
            print(f"✅ API Server already running at {API_BASE}")

        # Spawn team
        if not self.spawn_team():
            print("\n⚠️  Some agents failed to spawn. Check logs for details.")

        # Show summary
        self.list_agents()
        self.show_tmux_sessions()
        self.save_config()
        self.show_dashboard_urls()

        print("\n" + "="*70)
        print("🎉 Development Team is Ready!")
        print("="*70)
        print("\nUseful Commands:")
        print("  tmux attach -t <agent-name>    - Attach to agent session")
        print("  tmux list-sessions              - List all sessions")
        print(f"  curl {API_BASE}/api/agents    - List agents via API")
        print(f"  open {API_BASE}                - Open dashboard (accessible from any Tailscale device)")
        print("\nTo stop all agents:")
        print("  tmux kill-server")
        print(f"\nTailscale IP: {TAILSCALE_IP}")
        print(f"Access dashboards from any device on your Tailscale network!")


def main():
    """Entry point."""
    try:
        manager = DevTeamManager()
        manager.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
