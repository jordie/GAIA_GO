"""
Session state management for Claude Code wrapper.

Maintains state that persists across module reloads.
State is also persisted to disk for API access.
"""

import json
from datetime import datetime
from pathlib import Path
from threading import Lock

__version__ = "1.0.0"

STATE_FILE = Path("/tmp/claude_wrapper_state.json")

# Thread-safe state management
_state_lock = Lock()
_state = {
    "session_id": None,
    "start_time": None,
    "prompts_detected": 0,
    "prompts_approved": 0,
    "prompts_denied": 0,
    "bytes_received": 0,
    "bytes_sent": 0,
    "last_activity": None,
    "last_prompt": None,
    "reload_count": 0,
    "errors": [],
    "status": "stopped",
}


def init_session(session_id=None):
    """Initialize a new session state."""
    global _state
    with _state_lock:
        _state = {
            "session_id": session_id or datetime.now().strftime("%Y%m%d_%H%M%S"),
            "start_time": datetime.now().isoformat(),
            "prompts_detected": 0,
            "prompts_approved": 0,
            "prompts_denied": 0,
            "bytes_received": 0,
            "bytes_sent": 0,
            "last_activity": datetime.now().isoformat(),
            "last_prompt": None,
            "reload_count": 0,
            "errors": [],
            "status": "running",
        }
        _save_state()
    return _state["session_id"]


def get_state():
    """Get current session state."""
    with _state_lock:
        # Add computed fields
        state = _state.copy()
        if state["start_time"]:
            start = datetime.fromisoformat(state["start_time"])
            uptime = datetime.now() - start
            state["uptime_seconds"] = int(uptime.total_seconds())
            state["uptime"] = str(uptime).split(".")[0]  # Remove microseconds
        return state


def update_state(**kwargs):
    """Update state fields."""
    global _state
    with _state_lock:
        for key, value in kwargs.items():
            if key in _state:
                _state[key] = value
        _state["last_activity"] = datetime.now().isoformat()
        _save_state()


def increment_counter(counter_name, amount=1):
    """Increment a counter in the state."""
    global _state
    with _state_lock:
        if counter_name in _state and isinstance(_state[counter_name], int):
            _state[counter_name] += amount
            _state["last_activity"] = datetime.now().isoformat()
            _save_state()


def record_prompt(prompt_type, command, approved=True):
    """Record a prompt detection."""
    global _state
    with _state_lock:
        _state["prompts_detected"] += 1
        if approved:
            _state["prompts_approved"] += 1
        else:
            _state["prompts_denied"] += 1
        _state["last_prompt"] = {
            "type": prompt_type,
            "command": command[:100],
            "timestamp": datetime.now().isoformat(),
            "approved": approved,
        }
        _state["last_activity"] = datetime.now().isoformat()
        _save_state()


def record_error(error_msg):
    """Record an error."""
    global _state
    with _state_lock:
        _state["errors"].append(
            {"message": str(error_msg)[:200], "timestamp": datetime.now().isoformat()}
        )
        # Keep only last 10 errors
        _state["errors"] = _state["errors"][-10:]
        _save_state()


def increment_reload():
    """Increment reload counter."""
    global _state
    with _state_lock:
        _state["reload_count"] += 1
        _save_state()


def end_session():
    """Mark session as ended."""
    update_state(status="stopped")


def _save_state():
    """Save state to disk for API access."""
    try:
        STATE_FILE.write_text(json.dumps(_state, indent=2))
    except Exception:
        pass  # Ignore save errors


def load_state():
    """Load state from disk (for API access)."""
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
    except Exception:
        pass
    return None
