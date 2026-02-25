#!/usr/bin/env python3
"""
Monitor what each environment is currently doing.
Shows git status, running tasks, active sessions, and recent activity.
"""

import os
import subprocess


class EnvironmentMonitor:
    def __init__(self, base_path="/Users/jgirmay/Desktop/gitrepo/pyWork"):
        self.base_path = base_path
        self.environments = ["dev1", "dev2", "dev3", "dev4", "dev5"]

    def get_env_path(self, env_name):
        return f"{self.base_path}/architect-{env_name}"

    def get_git_status(self, env_path):
        """Get git branch and uncommitted changes."""
        try:
            result = subprocess.run(
                ["git", "-C", env_path, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            branch = result.stdout.strip()

            result = subprocess.run(
                ["git", "-C", env_path, "status", "--short"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            changes = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0

            return {"branch": branch, "changes": changes}
        except Exception as e:
            return {"branch": "unknown", "changes": 0, "error": str(e)}

    def get_worker_status(self, env_name):
        """Check if worker session is active."""
        try:
            result = subprocess.run(
                ["pgrep", "-f", f"{env_name}_worker"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                pids = result.stdout.strip().split("\n")
                return {"active": True, "count": len(pids), "pids": pids}
            return {"active": False, "count": 0}
        except Exception as e:
            return {"active": False, "error": str(e)}

    def get_dashboard_status(self, env_name):
        """Check if dashboard is running for this environment."""
        env_num = env_name[-1]
        port = 8080 + int(env_num)

        try:
            result = subprocess.run(
                ["lsof", "-Pi", f":{port}", "-sTCP:LISTEN", "-t"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return {"running": result.returncode == 0, "port": port}
        except Exception:
            return {"running": False, "port": port}

    def get_tasks_for_env(self, env_name):
        """Get pending tasks for this environment."""
        try:
            result = subprocess.run(
                ["python3", "workers/assigner_worker.py", "--prompts"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            lines = result.stdout.strip().split("\n")
            tasks = []
            for line in lines:
                if env_name in line:
                    tasks.append(line)
            return tasks
        except Exception:
            return []

    def show_status(self):
        """Display status of all environments."""
        print("\n" + "=" * 100)
        print("ENVIRONMENT STATUS OVERVIEW")
        print("=" * 100 + "\n")

        for env in self.environments:
            env_path = self.get_env_path(env)
            exists = os.path.exists(env_path)

            print(f"📦 {env.upper()}")
            print(f"   Path: {env_path}")

            if exists:
                # Git status
                git_info = self.get_git_status(env_path)
                print(f"   🔀 Git: {git_info.get('branch')} ({git_info.get('changes')} changes)")

                # Worker status
                worker_info = self.get_worker_status(env)
                if worker_info["active"]:
                    print(f"   ✓ Worker: ACTIVE ({worker_info['count']} process(es))")
                else:
                    print("   ✗ Worker: inactive")

                # Dashboard status
                dash_info = self.get_dashboard_status(env)
                if dash_info["running"]:
                    print(f"   🌐 Dashboard: RUNNING (port {dash_info['port']})")
                else:
                    print(f"   ⊘ Dashboard: not running (port {dash_info['port']})")
            else:
                print("   ❌ Directory not found")

            print()

        print("=" * 100)
        print("ACTIVE SESSIONS & PROCESSES")
        print("=" * 100 + "\n")

        # Tmux sessions
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}: #{session_windows}w"],
                capture_output=True,
                text=True,
            )
            sessions = result.stdout.strip().split("\n")
            print(f"Tmux Sessions: {len([s for s in sessions if s])}")
            for session in sessions[:10]:
                if session:
                    print(f"  • {session}")
        except Exception:
            print("Tmux: error querying sessions")

        # Claude processes
        try:
            result = subprocess.run(
                ["pgrep", "-c", "-f", "claude"],
                capture_output=True,
                text=True,
            )
            count = result.stdout.strip()
            print(f"\nClaude Processes: {count}")
        except Exception:
            print("\nClaude Processes: error")

        print("\n" + "=" * 100 + "\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Monitor environment activity")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch continuously (updates every 10 seconds)",
    )
    parser.add_argument(
        "--env",
        help="Show details for specific environment",
    )

    args = parser.parse_args()

    monitor = EnvironmentMonitor()

    if args.watch:
        import time

        print("Watching environment status (Ctrl+C to stop)...")
        try:
            while True:
                monitor.show_status()
                time.sleep(10)
        except KeyboardInterrupt:
            print("\nStopped watching.")
    else:
        monitor.show_status()


if __name__ == "__main__":
    main()
