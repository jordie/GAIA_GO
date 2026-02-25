#!/usr/bin/env python3
"""
Session State Manager
Dynamically tracks and persists agent session state for monitoring and coordination.
"""

import json
import time
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime


class SessionStateManager:
    """Manages persistent state for agent sessions."""

    def __init__(self, session_name: str, state_dir: str = "/tmp/agent_states"):
        self.session_name = session_name
        self.state_dir = Path(state_dir)
        self.state_file = self.state_dir / f"{session_name}.json"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Initialize state
        self.state = {
            "session_name": session_name,
            "status": "initializing",
            "current_task": None,
            "last_activity": time.time(),
            "started_at": time.time(),
            "tool": None,
            "model": None,
            "prompts_handled": 0,
            "errors": 0,
            "working_directory": None,
            "last_prompt": None,
            "last_response": None,
            "metadata": {},
        }

    def update_state(self, **kwargs):
        """Update session state with new values."""
        self.state.update(kwargs)
        self.state["last_activity"] = time.time()
        self._write_state()

    def set_status(self, status: str):
        """Set session status (idle, working, waiting, error, stopped)."""
        self.state["status"] = status
        self.state["last_activity"] = time.time()
        self._write_state()

    def set_task(self, task_description: str, work_dir: str = None):
        """Set current task being worked on."""
        self.state["current_task"] = task_description
        self.state["status"] = "working"
        if work_dir:
            self.state["working_directory"] = work_dir
        self.state["last_activity"] = time.time()
        self._write_state()

    def clear_task(self):
        """Clear current task (mark as completed)."""
        self.state["current_task"] = None
        self.state["status"] = "idle"
        self.state["last_activity"] = time.time()
        self._write_state()

    def increment_prompts(self):
        """Increment prompt counter."""
        self.state["prompts_handled"] += 1
        self.state["last_activity"] = time.time()
        self._write_state()

    def increment_errors(self):
        """Increment error counter."""
        self.state["errors"] += 1
        self.state["last_activity"] = time.time()
        self._write_state()

    def set_tool_info(self, tool: str, model: str = None):
        """Set tool and model information."""
        self.state["tool"] = tool
        if model:
            self.state["model"] = model
        self._write_state()

    def set_last_prompt(self, prompt_text: str):
        """Record last prompt received."""
        self.state["last_prompt"] = {
            "text": prompt_text[:200],  # First 200 chars
            "timestamp": time.time(),
        }
        self.state["last_activity"] = time.time()
        self._write_state()

    def set_last_response(self, response_text: str):
        """Record last response given."""
        self.state["last_response"] = {
            "text": response_text[:200],  # First 200 chars
            "timestamp": time.time(),
        }
        self.state["last_activity"] = time.time()
        self._write_state()

    def set_metadata(self, key: str, value: Any):
        """Set custom metadata."""
        self.state["metadata"][key] = value
        self._write_state()

    def heartbeat(self):
        """Update last_activity timestamp (keep-alive)."""
        self.state["last_activity"] = time.time()
        self._write_state()

    def _write_state(self):
        """Write state to JSON file."""
        try:
            # Add computed fields
            enriched_state = self.state.copy()
            enriched_state["uptime_seconds"] = time.time() - self.state["started_at"]
            enriched_state["last_activity_ago"] = time.time() - self.state["last_activity"]
            enriched_state["timestamp"] = datetime.now().isoformat()

            # Write atomically
            temp_file = self.state_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(enriched_state, f, indent=2)
            temp_file.replace(self.state_file)
        except Exception as e:
            print(f"Error writing state for {self.session_name}: {e}")

    def cleanup(self):
        """Remove state file on session shutdown."""
        try:
            if self.state_file.exists():
                self.state_file.unlink()
        except Exception as e:
            print(f"Error cleaning up state for {self.session_name}: {e}")

    @staticmethod
    def get_all_sessions(state_dir: str = "/tmp/agent_states") -> Dict[str, Dict]:
        """Get state of all sessions."""
        state_dir = Path(state_dir)
        if not state_dir.exists():
            return {}

        sessions = {}
        for state_file in state_dir.glob("*.json"):
            try:
                with open(state_file) as f:
                    state = json.load(f)
                    sessions[state["session_name"]] = state
            except Exception as e:
                print(f"Error reading {state_file}: {e}")

        return sessions

    @staticmethod
    def get_session_state(
        session_name: str, state_dir: str = "/tmp/agent_states"
    ) -> Optional[Dict]:
        """Get state for a specific session."""
        state_file = Path(state_dir) / f"{session_name}.json"
        if not state_file.exists():
            return None

        try:
            with open(state_file) as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading state for {session_name}: {e}")
            return None

    @staticmethod
    def cleanup_stale_states(
        max_age_seconds: int = 3600, state_dir: str = "/tmp/agent_states"
    ):
        """Remove state files for sessions that haven't updated in a while."""
        state_dir = Path(state_dir)
        if not state_dir.exists():
            return 0

        removed = 0
        current_time = time.time()

        for state_file in state_dir.glob("*.json"):
            try:
                with open(state_file) as f:
                    state = json.load(f)
                    last_activity = state.get("last_activity", 0)

                    if current_time - last_activity > max_age_seconds:
                        state_file.unlink()
                        removed += 1
            except Exception:
                pass

        return removed


# Integration with existing wrappers
class WrapperStateTracker:
    """Wrapper integration for session state tracking."""

    def __init__(self, session_name: str, tool: str, model: str = None):
        self.state_manager = SessionStateManager(session_name)
        self.state_manager.set_tool_info(tool, model)
        self.state_manager.set_status("idle")

    def on_task_received(self, task_description: str, work_dir: str = None):
        """Called when task is received."""
        self.state_manager.set_task(task_description, work_dir)

    def on_task_completed(self):
        """Called when task is completed."""
        self.state_manager.clear_task()

    def on_prompt_detected(self, prompt_text: str):
        """Called when a prompt is detected."""
        self.state_manager.set_last_prompt(prompt_text)
        self.state_manager.increment_prompts()

    def on_response_sent(self, response_text: str):
        """Called when a response is sent."""
        self.state_manager.set_last_response(response_text)

    def on_error(self, error_message: str):
        """Called when an error occurs."""
        self.state_manager.increment_errors()
        self.state_manager.set_metadata("last_error", error_message)

    def on_status_change(self, status: str):
        """Called when status changes."""
        self.state_manager.set_status(status)

    def heartbeat(self):
        """Send heartbeat."""
        self.state_manager.heartbeat()

    def cleanup(self):
        """Cleanup on shutdown."""
        self.state_manager.set_status("stopped")
        self.state_manager.cleanup()


def main():
    """CLI for session state management."""
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python session_state_manager.py list         # List all sessions")
        print("  python session_state_manager.py get <name>   # Get specific session")
        print("  python session_state_manager.py cleanup      # Remove stale states")
        sys.exit(0)

    command = sys.argv[1]

    if command == "list":
        sessions = SessionStateManager.get_all_sessions()

        if not sessions:
            print("No active sessions found")
            sys.exit(0)

        print("\n" + "=" * 80)
        print("ACTIVE AGENT SESSIONS")
        print("=" * 80)

        for name, state in sorted(sessions.items()):
            status_icon = {
                "idle": "⏸️",
                "working": "🔄",
                "waiting": "⏳",
                "error": "❌",
                "stopped": "⏹️",
            }.get(state.get("status", "unknown"), "❓")

            uptime = state.get("uptime_seconds", 0)
            uptime_str = f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m"

            print(f"\n{status_icon} {name}")
            print(f"  Status:     {state.get('status', 'unknown')}")
            print(f"  Tool:       {state.get('tool', 'unknown')}")
            print(f"  Uptime:     {uptime_str}")
            print(f"  Prompts:    {state.get('prompts_handled', 0)}")

            if state.get("current_task"):
                task = state["current_task"]
                print(f"  Task:       {task[:60]}...")

            if state.get("working_directory"):
                print(f"  Work Dir:   {state['working_directory']}")

    elif command == "get":
        if len(sys.argv) < 3:
            print("Error: Usage: get <session_name>")
            sys.exit(1)

        session_name = sys.argv[2]
        state = SessionStateManager.get_session_state(session_name)

        if not state:
            print(f"Session '{session_name}' not found")
            sys.exit(1)

        print(json.dumps(state, indent=2))

    elif command == "cleanup":
        removed = SessionStateManager.cleanup_stale_states()
        print(f"Removed {removed} stale session states")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
